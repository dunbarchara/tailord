# Day 16 — Chunk Hardening

**Date:** TBD
**Reference:** `17-chunk-model.md` — read before touching anything here.
**Theme:** Make the chunk model production-grade: correct taxonomy, clean lifecycle,
user-facing control over every claim in their profile, and a real gap enrichment loop.

This day bridges the infrastructure work of Days 11–15 (chunks exist, embeddings exist,
gap detection exists) with the user-facing product that makes those things meaningful.

---

## Goal

A user should be able to:
1. Submit experience in any form and see it parsed into individual editable claims
2. Understand what's in their profile and manage it at the claim level
3. Answer a gap question from a tailoring and immediately see their match score improve
4. Have that answer persist and benefit all future tailorings automatically

---

## Part 1 — Schema Foundation

### Alembic migration: `metadata` column
- [x] Add `chunk_metadata JSON NULL` to `experience_chunks` — migration `d5e6f7a8b9c0`; column and Python attribute both named `chunk_metadata` (avoids SQLAlchemy reserved `metadata`); chains from `c4d5e6f7a8b9`; applied and verified

---

## Part 2 — Backend: user_input Overhaul

The single-blob user_input model is replaced with a multi-chunk flow.

### LLM parse endpoint
- [x] `POST /experience/user-input/parse` — accepts `{text: str}`, returns `{chunks: [str]}`
  - Short input heuristic (≤ 200 chars or single sentence): return `[text]` immediately, no LLM call
  - Longer input: LLM extracts atomic claims, returns list for client preview
  - Does NOT write to DB — preview only
  - New prompt in `app/prompts/user_input_parse.py`; single-responsibility: "extract atomic claims, do not invent"
  - Heuristic: `_is_short_input` checks len ≤ 200 or no `[.!?]+\s+[A-Z]` pattern; fallback to `[text]` if LLM returns empty
  - Frontend API route: `POST /api/experience/user-input/parse/route.ts` (new)

### Persist endpoint
- [x] `POST /experience/user-input/chunks` — accepts `{chunks: [str]}`, creates N `user_input` ExperienceChunks
  - Replaces `set_user_input` (which created one blob chunk)
  - Each chunk: `source_type="user_input"`, `claim_type="other"`, `group_key=null`, `metadata=null`
  - Embeds each chunk (background task, same pattern as existing embed-after-chunk)
  - Does NOT replace existing user_input chunks — additive; user manages deletions individually
  - Returns created chunk IDs for the frontend to display
  - Position: `max(position across all source_types) + 1` — appends correctly
  - IDs collected before commit (SQLAlchemy `default=uuid.uuid4` generates in Python)
  - Frontend API route: `POST /api/experience/user-input/chunks/route.ts` (new)
  - `_ensure_experience` helper creates Experience row if not yet exists

### Individual chunk deletion
- [x] `DELETE /experience/chunks/{chunk_id}` — deletes a single ExperienceChunk by ID
  - Validates ownership (chunk must belong to the authenticated user's experience)
  - Works for any `source_type` — the endpoint is general-purpose
  - Frontend API route: `DELETE /api/experience/chunks/[id]` — added DELETE handler to existing route.ts
  - Note: existing `delete_*_chunks` bulk functions are unchanged (used for source-level cleanup)

### Remove legacy user_input blob behavior
- [x] Remove `set_user_input` — removed from `experience.py`; old `POST /experience/user-input` route deleted
- [x] Remove the existing `chunk_user_input` function (replaced by the new persist endpoint) — removed from `experience_chunker.py`; 3 tests removed from `test_experience_chunker.py`
- [x] Repurposed `DELETE /experience/user-input` to delete all `user_input` chunks (clears `user_input_text` field too for legacy compat); no longer checks `user_input_text` presence before deleting

---

## Part 3 — Backend: gap_response Wiring

### Gap response creation endpoint
- [x] `POST /experience/gap-response` — accepts `{job_chunk_id: str, tailoring_id: str, question: str, answer: str}`
  - Creates one `gap_response` ExperienceChunk with `chunk_metadata={question, job_chunk_id, tailoring_id}`
  - Ownership validated: tailoring must belong to user; job_chunk must belong to tailoring's job
  - Embeds synchronously via `embed_experience_chunks(experience.id, db)` before re-enrich
  - Calls `re_enrich_single_chunk(...)` synchronously — user is waiting
  - Re-queries JobChunk after re_enrich (separate session committed) for fresh score
  - Returns `{chunk_id, updated_score, updated_rationale}`
  - Frontend API route: `POST /api/experience/gap-response/route.ts` (new)

### gap_response lifecycle verification
- [x] Confirmed: all three delete functions delegate to `_delete_chunks` with their specific `source_type` — gap_response is never passed; lifecycle tests verify this

### Tests
- [x] `tests/services/test_chunk_lifecycle.py` (new, 9 tests) — asserts source_type isolation for all three delete functions; asserts `Experience.chunks` cascade config includes `delete` + `delete-orphan`
- [x] Updated `test_experience_chunker.py` for the removed `chunk_user_input` (done in Part 2)

---

## Part 4 — Frontend: My Experience UI Overhaul

Design reference: `planning/19-experience-ui-design.md` — read before implementing.

**Core direction:** single scrollable page (no tabs), all chunks editable + deletable
regardless of source, user is the author and owner of everything.

### Step 1 — TypeScript types (`frontend/src/types/index.ts`)
- [x] Add `'gap_response'` to `ExperienceChunk.source_type` union
- [x] Add `chunk_metadata: Record<string, string> | null` to `ExperienceChunk`
- [x] Change `ExperienceChunksResponse.user_input` from `ExperienceChunk | null`
  to `ExperienceChunk[] | null`
- [x] Add `gap_response: ExperienceChunk[] | null` to `ExperienceChunksResponse`

### Step 2 — Extend `EditableChunk` with delete support
- [x] Add `onDelete?: (id: string) => Promise<void>` prop to `EditableChunk`
- [x] In view state: render × button alongside pencil, both in `opacity-0 group-hover:opacity-100`
- [x] × calls `onDelete(chunk.id)` — no confirmation (individual chunks are small, re-addable)
- [x] For skill pills: × appears inside the pill on hover (not a separate trailing icon) — implemented as `SkillPill` component with inline × in `ChunkedProfile`

### Step 3 — Rewrite `ChunkedProfile` → sectioned single-scroll view
- [x] Remove tabs entirely (`SourceTab`, tab bar, tab content switch) — full rewrite of `ChunkedProfile.tsx`
- [x] Render all sections in one scroll: Resume → GitHub → Additional Experience → Gap Responses
- [x] Each section only rendered if it has data (same as before, just no tabs)
- [x] Add `onDelete` handler: calls `DELETE /api/experience/chunks/[id]`, then
  removes chunk from local state optimistically via `removeChunkFromResponse`
- [x] Update `patchChunkInResponse` helper to handle array `user_input` and `gap_response`; added `removeChunkFromResponse` for delete
- [x] Wire delete to all chunk types: resume bullets, resume skills, resume education/certs,
  GitHub project summaries, GitHub skill tags, user_input claims, gap_response answers
- [x] `hasData` check: include `user_input?.length > 0` and `gap_response?.length > 0`

### Step 4 — `GapResponseSection` component (new, inside `ChunkedProfile`)
- [x] Only rendered if `data.gap_response?.length > 0`
- [x] Each chunk shows question context line above answer:
  format `"Asked when applying to [Company] — [question]"` (or just question if no company)
  — read from `chunk.chunk_metadata.question`; company resolution deferred (use question only for now)
- [x] Answer rendered via `EditableChunk` with delete

### Step 5 — `AddExperienceForm` component (new, inside `ChunkedProfile` or `ExperienceManager`)
- [x] Textarea (placeholder: "Describe experience, projects, or skills not captured above")
- [x] "Parse & Add" button
- [x] On submit:
  - Call `POST /api/experience/user-input/parse` with `{text}`
  - If response has 1 chunk OR input is short: skip preview, persist immediately
  - If response has 2+ chunks: show preview list with checkboxes (all checked by default)
  - "Confirm" → `POST /api/experience/user-input/chunks` with selected chunks
  - On success: prepend/append new chunks to `data.user_input` in local state; clear textarea
- [x] Loading and error states on both parse and persist calls

### Step 6 — `ExperienceManager` cleanup
- [x] Remove the "Additional Context" `SettingRow` (textarea + Save button + Remove button)
- [x] Remove `directText` / `directState` state and `handleDirectSave` / `handleUserInputRemove`
- [x] Remove `'user-input-clear'` from `CONFIRM_CONFIGS` and `handleConfirmAction`
- [x] Update `hasExperience` — kept as `uploadState.phase === 'ready'`; `ChunkedProfile` handles its own empty state; `textareaCls` also removed (no longer used)
- [x] Keep `chunksRefreshKey` pattern — still needed after resume/GitHub changes

---

## Part 5 — Frontend: Tailoring Analysis UI Overhaul

The gap enrichment loop needs a real UX surface in the tailoring detail.

### Current state
Gap questions exist in some form in the tailoring detail but are not well-integrated
with the requirement scoring view. The answer flow is unclear and routes to user_input.

### New direction

**Analysis tab layout:**
- [ ] Group requirements by score: STRONG (2) → PARTIAL (1) → GAP (0) → N/A (hidden or collapsed)
- [ ] Each requirement card shows: requirement text, score badge, rationale (collapsed by default, expand on click)
- [ ] STRONG and PARTIAL requirements: read-only (collapsible rationale is the only interaction)

**GAP requirements — enrichment inline:**
- [ ] For each GAP requirement that has a gap question (from `gap_analyzer`):
  - Show the question below the requirement text
  - Inline text area: "Your answer..."
  - Submit button → calls `POST /api/experience/gap-response`
  - Loading state while re-match runs (typically < 2s)
  - On success: score badge animates to new value (PARTIAL or STRONG if evidence is strong)
  - Below the updated badge: "Your response has been saved to your experience and will help future tailorings"
- [ ] For GAP requirements with no gap question (non-evaluable or gap analyzer didn't run):
  - Show score badge with no input field — just the requirement and a "—" rationale

**Already-answered gaps:**
- [ ] If a gap_response chunk exists for this job_chunk_id (check metadata):
  - Show "You answered this" with the response text and a small edit link
  - Do not show the answer input again (it's been answered)

**Score summary bar:**
- [ ] Top of Analysis tab: `X Strong  ·  Y Partial  ·  Z Gap` — updates reactively as gaps are answered
- [ ] Not a progress bar — just counts. Clean and scannable.

---

## Part 6 — Gaps and Edge Cases Worth Handling

These are smaller items that would be easy to overlook but matter for correctness.

- [ ] **Gap response deduplication signal**: if a user submits a gap response and then regenerates
  the tailoring, the gap_response chunk now participates in the new matching run — the gap
  question may not appear again (because the requirement is now PARTIAL/STRONG). The UI should
  handle this gracefully: "this requirement was previously a gap but your added experience resolved it"
  rather than the gap question silently disappearing.

- [ ] **Position ordering for user_input chunks**: new user_input chunks should append after
  existing ones. `position` should be set to `max(position) + 1` for the experience, not reset
  to 0. (Currently position is only set correctly for the first chunk_user_input call.)

- [ ] **Embed-before-re-enrich ordering**: gap response embed must complete before `re_enrich_single_chunk`
  runs — otherwise the new chunk has no vector and cannot be retrieved. The gap response endpoint
  should embed synchronously (not background task) before calling re-enrich.

- [ ] **Re-match with gap_response context**: `re_enrich_single_chunk` currently uses the existing
  `experience_id` to retrieve top-K experience chunks via cosine similarity. The newly created
  gap_response chunk will be in that pool (after embedding). No code change needed — the
  architecture already handles this correctly.

- [x] **`chunk_metadata` in API responses**: added `chunk_metadata` to `_serialize_exp_chunk` in `experience.py`; `_group_experience_chunks` now also collects `gap_response` chunks into a dedicated `gap_response` list in the response; GET `/experience/chunks` returns `{resume, github, user_input, gap_response}` shape

---

## Acceptance

- `POST /experience/user-input/parse` returns a list of strings for longer input; returns
  the input directly for short input
- Submitting multi-sentence user input → N individual chunks in the DB, each independently
  editable and deletable
- Answering a gap question in the tailoring detail → creates a `gap_response` chunk with
  `metadata.job_chunk_id` set → re-match runs → score badge updates inline
- Gap response chunks are NOT deleted when the resume is removed or a GitHub repo is
  disconnected
- Gap response chunks appear in My Experience under "Your Gap Responses" with the question
  as context
- `make check` passes

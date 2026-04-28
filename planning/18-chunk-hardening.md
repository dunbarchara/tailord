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
- [ ] `POST /experience/gap-response` — accepts `{job_chunk_id: str, tailoring_id: str, question: str, answer: str}`
  - Creates one `gap_response` ExperienceChunk:
    - `content = answer`
    - `source_type = "gap_response"`
    - `claim_type = "other"`
    - `metadata = {question, job_chunk_id, tailoring_id}`
  - Embeds the chunk immediately (not background — user is waiting for re-match result)
  - Calls `re_enrich_single_chunk(job_chunk_id, experience_id, candidate_name)` to re-score the requirement
  - Returns `{chunk_id, updated_score, updated_rationale}` so the frontend can update the badge inline
  - Frontend API route: `POST /api/experience/gap-response`

### gap_response lifecycle verification
- [ ] Confirm `delete_resume_chunks`, `delete_github_chunks`, `delete_user_input_chunks` do NOT
  touch `gap_response` chunks (they filter by source_type — should already be safe; add a test)

### Tests
- [ ] `tests/services/test_chunk_lifecycle.py` (new) — assert gap_response chunks survive resume delete,
  github disconnect, and user_input clear; assert they ARE deleted on Experience delete (cascade)
- [ ] Update existing `test_experience_chunker.py` for the removed `chunk_user_input` function

---

## Part 4 — Frontend: My Experience UI Overhaul

The My Experience view needs to reflect the new chunk model: individual claims, clear
source grouping, and gap responses as a first-class section.

### user_input section — replaced
- [ ] Remove the single text area + Save button flow
- [ ] New "Add Experience" section:
  - Text area (placeholder: "Describe experience, projects, or skills not captured above")
  - "Parse & Add" button → calls `/api/experience/user-input/parse`
  - Short input: add one chunk immediately (skip preview)
  - Longer input: show parsed chunk list with checkboxes — user can deselect unwanted claims
  - "Confirm" → calls `/api/experience/user-input/chunks` to persist selected chunks
  - Each persisted chunk renders inline with edit (pencil, existing `EditableChunk`) and delete (×) controls

### gap_response section — new
- [ ] Add "Your Gap Responses" section below the existing experience sections
  - Only shown if ≥ 1 gap_response chunk exists
  - Each response rendered with:
    - The question as muted context: *"Asked when applying to [Company] — [question text]"*
    - The answer as the main content (editable via existing `EditableChunk` PATCH)
    - Delete (×) — calls `DELETE /api/experience/chunks/[id]`
  - Empty state: section hidden (not "no responses yet")

### Chunk deletion (cross-section)
- [ ] Wire delete (×) button to `DELETE /api/experience/chunks/[id]` for user_input and gap_response chunks
  - Optimistic removal from local state on success
  - Resume and GitHub chunks are managed at source level (remove resume / disconnect repo) — do not add per-bullet delete for those

### Empty state handling
- [ ] `hasExperience` check should include `user_input` and `gap_response` chunks
  — a user with only gap_response chunks should see their experience view, not the empty upload prompt

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

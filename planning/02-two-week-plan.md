# Two-Week Work Plan

*Feb–Mar 2026 | Solo developer sprint*

---

## Guiding Principles for This Sprint

1. **Ship complete features, not half-features.** The GitHub input being UI-only is worse than it not existing. Everything in this sprint should go end-to-end.
2. **Prioritize what makes the product shareable.** Right now it's private-only. A shareable tailoring URL or Notion integration changes the product's reach.
3. **Each day's work should be demonstrable.** If you can't show it to someone at the end of the day, the task was too big.
4. **Portfolio signal matters.** Given the employment context, the Notion integration is week 2's priority over anything else — it's a direct signal for the companies you're targeting.

---

## Week 1: Complete the Core Product

The goal of week 1 is to eliminate every "this feature is half-built" area. By Friday, every visible feature in the UI should actually work.

---

### ✅ Day 1 — Experience Pivot + GitHub Integration (Backend)

**Goal:** When a user provides a GitHub username, fetch their repositories and merge them into the candidate profile.

**Tasks:**
- [x] Add `GET /experience/github/{username}/repos` endpoint — fetches public repos, no auth token needed
  - [x] Pull: repo name, description, primary language, star count, last pushed
  - [x] Filter out forks, archived repos, and anything with 0 stars + no description (noise)
  - [x] Return top 10 by recency
- [x] Add `POST /experience/github` endpoint: accepts `github_username`, fetches repos, updates Experience record
  - Note: implemented as **additive sourced profile merge** rather than LLM re-run. `extracted_profile` is now a source-keyed envelope `{ resume: {...}, github: {...}, user_input: {...} }` — provenance is preserved and surfaced in tailoring output citations.
- [x] **Foundational (unplanned but necessary):** Renamed `Resume` → `Experience` across the full stack — model, API, frontend routes, types. Introduced alembic for migrations (`resumes` → `experiences` table rename + github fields).

**Why now:** The data enrichment story depends on this. A Tailoring generated with GitHub context is measurably better — the LLM can reference specific repos.

---

### ✅ Day 2 — GitHub Integration (Frontend) + Additional Context

**Goal:** The GitHub and additional context inputs actually save and affect the profile.

**Tasks:**
- [x] Wire the GitHub URL field in `ExperienceManager` to call `POST /api/experience/github`
  - [x] Show saving/saved/error states
  - [x] Update displayed profile summary when complete (refetch on save)
- [x] Show connected state when a GitHub username is saved — username + repo count, Change / Remove actions
- [x] Wire the "Additional Context" textarea to `POST /experience/user-input`
  - [x] Store as `user_input_text` column on the Experience record, written into `extracted_profile["user_input"]`
- [x] Database migration: `user_input_text TEXT` column on `experiences` table
- [x] Visual feedback: sonner toasts after saving GitHub or additional context ("GitHub profile added", "Additional context saved")
- [x] **Bug fix (unplanned):** `tailorings.py` was using a lazy-loaded relationship in an async context — replaced with explicit `db.query(Experience)` so GitHub-only users can generate tailorings

---

### ✅ Day 3 — Tailoring Regeneration + Delete

**Goal:** A tailoring is not a dead end. Users can regenerate it and delete ones they don't want.

**Tasks:**
- [x] Add `POST /tailorings/{id}/regenerate` backend endpoint
  - Re-runs `generate_tailoring()` with the same `job_id` and current user experience
  - Replaces the existing `generated_output` in place (simpler than keeping history for MVP)
- [x] Add `DELETE /tailorings/{id}` backend endpoint
  - Deletes the Tailoring and Job records for that tailoring
- [x] Add frontend API routes for both (GET/POST/DELETE on `/api/tailorings/[id]`)
- [x] In `TailoringDetail`: "Regenerate" button with confirmation dialog (it overwrites)
  - Loading/spinner state during regeneration; re-fetches full tailoring on complete
  - Copy-to-clipboard button with visual feedback
- [x] In the Sidebar tailoring list: hover trash icon → confirm dialog → delete + redirect if viewing deleted tailoring
- [x] `router.refresh()` after create (NewTailoringForm) and delete (Sidebar) so sidebar list stays in sync

**Why now:** Without regeneration, every bad output is a permanent failure. This is basic product completeness.

---

### ✅ Day 4 — Shareable Tailoring URLs

**Goal:** A tailoring can be made public and shared via a URL that doesn't require login.

**Tasks:**
- [x] Add `is_public` boolean + `public_slug` (unique string) columns to `tailorings` table via alembic migration
  - Slug format: `{company-slug}-{title-slug}-{random-6chars}` — readable and collision-resistant
- [x] Add backend endpoints: `POST /tailorings/{id}/share`, `DELETE /tailorings/{id}/share`, `GET /tailorings/public/{slug}`
  - Public endpoint requires no user auth — API key only
  - Slug generated once on first share, preserved across share/unshare toggles
- [x] Add share popover in `TailoringDetail` toolbar (Notion-inspired):
  - `Share` button (private) → popover with "Make public" CTA → confirmation dialog
  - `Public` button (shared) → popover with shareable URL + copy icon + "Make private" (secondary, behind confirm)
  - Two-click friction on "Make private" to prevent accidental unpublishing
- [x] Add frontend public route: `/t/{slug}` — server component, no auth required
  - Clean, print-friendly layout — document header, prose content, no nav chrome
  - Shows "Generated with Tailord" footer link
- [x] Refactored `TailoringDetail` layout: Notion-style 44px toolbar with breadcrumb + icon actions; document body is chrome-free

**Why now:** Shareable URLs unlock multiple things at once — you can share your own work, users can share their tailorings with hiring managers, and it creates organic discovery.

---

### ✅ Day 5 — Polish, Error States, Loading States

**Goal:** The product feels complete, not like a prototype. No dead ends, no blank screens.

**Tasks:**
- [x] Error handling across the backend: scrape failures, LLM parse errors, experience processing errors — all return structured messages
- [x] Add processing timeouts: Playwright scrape + LLM calls now have explicit timeouts (no more infinite hangs)
- [x] Recent Tailorings component on the dashboard home page — replaces the empty shell, surfaces your most recent work immediately
- [x] Sidebar search — filter tailorings by title/company as you type
- [x] Duplicate URL confirmation — creating a new tailoring for a URL that already has one prompts "are you sure?" instead of silently creating a duplicate
- [x] `lib/tailorings.ts` — shared fetch logic extracted from components
- [x] **Unplanned:** Documented North Star — wrote `planning/06-north-star-empowerment.md` capturing the product direction (conversational, guided enrichment) that should inform future feature decisions

**What was deprioritized:**
- Mini onboarding flow (step indicator) — the Recent Tailorings dashboard page serves the same new-user orientation purpose, less overhead
- Explicit loading state audit — handled implicitly by existing sonner toasts and skeleton states already in place

---

### ✅ Day 5.5 — Pipeline Robustness + Dual Pipeline + Match Analysis

**Goal:** The core generate-a-tailoring pipeline produces consistently high-quality output, not just output. Fix the pipeline's weak points and build the analytical infrastructure to iterate on matching quality.

**Completed:**

#### Scrape content gating ✅
- [x] `validate_job_content()` in `core/extract.py` — rejects bot-detection pages, login walls, removed/expired job postings (phrase matching against full HTML text), and near-empty content (plain-text length check after stripping markdown syntax and image URLs)
- [x] Playwright switched to `networkidle` wait state so SPA-rendered job boards (Ashby, Greenhouse) fully hydrate before extraction
- [x] Form elements (`<form>`, `<select>`, `<option>`, `<input>`, `<button>`) stripped from HTML before markdownify — eliminates phone country code dropdowns and application form noise from chunk extraction
- [x] Apply-section truncation — content after "Apply for this job" / "Apply now" headings is cut before the markdown reaches the LLM or chunk extractor

#### Deterministic title/company extraction ✅
- [x] JSON-LD cascade → meta tag signals → LLM fallback, with pre-extracted hints seeded into the LLM prompt and applied post-hoc if the model returns null
- [x] `extract_jsonld()`, `parse_title_tag()`, `extract_meta_signals()` in `core/extract.py`

#### Regeneration full pipeline ✅
- [x] `regenerate_tailoring` now re-scrapes and re-extracts (only the job URL is preserved) — title, company, and requirements reflect the latest job posting data
- [x] `_fetch_and_extract_job()` helper deduplicates scrape logic between create and regenerate
- [x] Sidebar updates after regeneration via `router.refresh()`

#### PDF extraction ✅
- [x] Switched from `pypdf` to `pdfminer.six` for layout-aware text extraction — handles multi-column resumes and preserves reading order
- [x] `raw_resume_text` stored on Experience record and returned via API — visible in Parsed Profile debug panel as "Raw Text" tab

#### Dual pipeline ✅
- [x] **Fast pipeline:** `match_requirements()` — single LLM call scoring all requirements 0/1/2 before tailoring generation; ranked matches passed to `generate_tailoring()` so the document reflects pre-scored fit
- [x] **Slow pipeline:** `enrich_job_chunks()` — background task, runs after response; extracts structured chunks from job markdown, batches per section, scores each against candidate profile
- [x] `JobChunk` model + `enrichment_status` on `Tailoring` — Alembic migration applied
- [x] Chunk scoring: -1 (non-evaluable), 0 (gap), 1 (partial), 2 (strong) — with mandatory rationale for every chunk
- [x] Pre-computed profile signals (`_compute_profile_signals`) — total YOE and role list injected as ground truth before profile JSON, eliminating date-arithmetic errors
- [x] Few-shot examples in chunk matching prompt — covers Strong/Partial/Gap/N/A with worked examples including mixed-section batches
- [x] `BATCH_SIZE` reduced to 5 for reliable JSON completion on local/smaller models

#### Match Analysis tab ✅
- [x] `MatchAnalysis` component — polls `/api/tailorings/{id}/chunks` every 3s while pending, displays chunks grouped by section
- [x] Developer-oriented card layout: metadata row (id, type, pos, section, score, source) + content row + rationale row
- [x] Score badges: Strong (green), Partial (yellow), Gap (red), N/A (grey), Pending (pulse)
- [x] Tab switcher in `TailoringDetail` toolbar — absolutely centered regardless of left/right content width
- [x] Tab-aware copy button: Document tab copies markdown, Match Analysis tab copies all chunks as structured markdown for pasting into Claude Code
- [x] Per-chunk copy button in metadata row

#### Parsed Profile debug panel ✅
- [x] `ParsedProfile` component on the experience page — tabbed by source (Resume / GitHub / Direct Input / Raw Text)
- [x] Resume tab: Summary, Work Experience (role/company/duration/bullets), Skills, Education, Projects, Certifications
- [x] GitHub tab: card per repo with language, stars, last pushed, description
- [x] Raw Text tab: shows `raw_resume_text` exactly as extracted — immediately reveals text extraction quality issues

#### Async pipeline isolation ✅
- [x] `match_requirements` and `generate_tailoring` wrapped in `anyio.to_thread.run_sync()` — sync LLM calls no longer block the asyncio event loop during request handling
- [x] Background task (`enrich_job_chunks`) was already correctly deferred post-response via FastAPI `BackgroundTasks`

#### Tailoring format + philosophy ✅
- [x] Defined the Tailoring product philosophy — third-party advocacy document, not a cover letter or requirements matrix; goal is to earn a conversation, not close a hire (`planning/09-tailoring-philosophy.md`)
- [x] Agreed output format: direct company greeting, single job-posting reference sentence, candidate-strength headings, brief `[Resume]`/`[GitHub]`/`[Direct Input]` source tags, synthesis closing, compact candidate brief footer
- [x] Gap handling hierarchy: strong matches lead; partial matches reframe positively; gaps with no signals omitted; gaps with adjacent signals get a brief constructive reframe only when prominent
- [x] Structured output: LLM now returns `TailoringContent` (`advocacy_statements[]` + `closing`) via `llm_parse` rather than free-form markdown — format is deterministic, owned in `_render_tailoring()`
- [x] `AdvocacyStatement(header, body, sources[])` + `TailoringContent` added to `schemas/llm_outputs.py`
- [x] `_render_tailoring()` assembles final markdown from structured content + deterministic data (name, email, education, company, job title)
- [x] `candidate_email` threaded through from `User` record; education extracted from profile for footer
- [x] Tailoring generation prompt rewritten to encode the advocacy philosophy and ask for JSON

**What was deprioritized (moved to Day 8.5):**
- Empty profile detection (minimum text length + field validation before marking ready)
- LLM output validation (finish_reason=length → LLMTruncationError, minimum quality check before persisting)
- Profile formatting as compact prose instead of JSON (partial: COMPUTED SIGNALS block added; full rewrite deferred)
- Token budget cap utility
- Job URL caching/reuse (skip re-scrape when Job record for URL already exists)
- Tailoring and profile extraction prompt iteration

---

## Week 2: Notion Integration + Strategic Feature

Week 2's goal is to build the one feature that most clearly demonstrates product sophistication and directly signals relevant skills for the companies you want to work at.

---

### Day 6 — Notion OAuth Setup + Settings Page

**Goal:** Users can connect their Notion workspace to Tailord.

**Tasks:**
- [ ] Register Tailord as a Notion OAuth app at [notion.so/my-integrations](https://www.notion.so/my-integrations)
  - Callback URL: `{NEXTAUTH_URL}/api/auth/notion/callback`
- [ ] Add Notion OAuth flow:
  - New NextAuth provider OR a standalone OAuth handler (simpler: standalone)
  - `/api/auth/notion` — redirects to Notion OAuth
  - `/api/auth/notion/callback` — exchanges code for access token, stores in DB
- [ ] Add `notion_access_token TEXT` + `notion_bot_id TEXT` columns to `users` table
- [ ] In `SettingsPanel`: add "Connected Apps" section
  - "Connect Notion" button → initiates OAuth
  - Shows connected state (workspace name) once linked
  - "Disconnect" button

**Note on Notion OAuth:** Notion uses OAuth 2.0. The access token is scoped to the pages/databases the user explicitly shares with your integration. This is actually a cleaner model than full workspace access.

---

### Day 7 — Notion Page Creation

**Goal:** A user can export any tailoring directly to a Notion page with one click.

**Tasks:**
- [ ] Add `POST /tailorings/{id}/export/notion` backend endpoint:
  - Requires user to have a Notion access token
  - Uses Notion API `POST /v1/pages` to create a new page
  - Parent: a page/database the user selects (or a default "Tailord Exports" page created automatically)
  - Content: parse the generated Markdown → Notion block format
    - `#` headings → `heading_1` blocks
    - `##` headings → `heading_2` blocks
    - Paragraphs → `paragraph` blocks
    - `*italic*` / `**bold**` → inline annotations
    - Bullet lists → `bulleted_list_item` blocks
  - Return the created page URL
- [ ] Frontend: "Export to Notion" button in `TailoringDetail`
  - If Notion not connected: prompt to connect (link to settings)
  - If connected: click → loading → opens created Notion page in new tab
  - Show success toast with link

**Markdown → Notion blocks is the hard part.** The Notion API doesn't accept markdown directly. You'll need a conversion function. There are open-source libraries (`md-to-notion`, `martian`) but given the project constraint of minimal dependencies, consider writing a targeted converter for just the headings/paragraphs/bullets/bold/italic that the tailoring template produces — it's a finite set of elements.

---

### Day 8 — Notion Parent Page Selection + Polish

**Goal:** The Notion integration feels polished, not janky.

**Tasks:**
- [ ] After Notion OAuth, fetch the user's accessible pages via `GET /v1/search`
  - Filter to pages only (not databases)
  - Store a default export location preference in the user record
- [ ] In Settings: "Notion Export Location" — a dropdown of their accessible pages
  - Saves their preferred parent page for future exports
- [ ] Add a `notion_page_url TEXT` column to `tailorings` table
  - Once exported, show the Notion page URL permanently in the tailoring detail
  - "View in Notion" button alongside "Copy" and "View Posting"
- [ ] Handle token expiry: Notion tokens don't expire, but if the user revokes access, handle the 401 gracefully with a prompt to reconnect

---

### Day 8.5 — Pipeline Hardening (Deferred from Day 5.5)

**Goal:** Close the robustness gaps that were deprioritized in Day 5.5 — output validation, resource protection, and prompt quality.

**Tasks:**
- [ ] **Empty profile detection:** Minimum text length check on extracted resume text (e.g. < 200 chars → reject with helpful error). Non-empty field validation: at least one work experience entry and a non-blank summary before marking experience `status=ready`. Prevents silently generating tailorings from blank or failed profiles.
- [ ] **LLM output validation:** Check `finish_reason == "length"` on all LLM responses — raise `LLMTruncationError` instead of silently persisting truncated output. Add a minimum quality check on profile extraction (e.g. non-empty `work_experience` array) before persisting.
- [ ] **Profile formatting as compact prose:** Replace the raw JSON profile dump fed to the LLM with a compact prose block (partial progress: COMPUTED SIGNALS block already added as ground truth header). Goal: more natural, shorter context that performs better on smaller models.
- [ ] **Token budget cap utility:** `truncate_to_tokens(text, max_tokens)` helper using tiktoken — apply to scraped job markdown before it enters any LLM prompt. Prevents runaway costs and context length errors on unusually long job postings.
- [ ] **Job URL caching/reuse:** Before scraping, check if a `Job` record already exists for the submitted URL (same `user_id`). If found and recent (< 7 days), reuse `extracted_job` — skip the Playwright scrape and re-extraction entirely. Avoids duplicate LLM calls and latency on retries.
- [ ] **Tailoring and profile extraction prompt iteration:** Review and tighten the `generate_tailoring` system prompt. Consider adding few-shot examples for the profile extraction pass (same pattern as chunk matching).

**Context:** These were all planned for Day 5.5 but deprioritized in favour of the dual pipeline, match analysis, and parsed profile debug panel — all of which shipped. The hardening items here are primarily defensive (cost, correctness, error messaging) rather than user-visible features, which is why they're slotted after the Notion integration days rather than before.

---

### Day 8.6 — Streaming + Perceived Performance

**Goal:** The tailoring generation flow feels as responsive as Claude Code — the user starts reading their document within seconds, not after a 60+ second blank wait.

**Context:** The fast pipeline currently takes 60–90 seconds end-to-end before anything renders. This is four sequential operations: Playwright scrape (15–30s on JS-heavy job boards) → job extraction LLM call → fast match LLM call → tailoring generation LLM call. All four must complete before the user sees anything. Wall-clock time is hard to eliminate, but *perceived* time can be dramatically reduced through streaming and honest progress feedback — the same techniques that make Claude Code feel fast.

**Tasks:**

#### 1. Stream the tailoring generation output
- [ ] Switch `generate_tailoring()` to use `stream=True` on the OpenAI SDK call
- [ ] Change `POST /tailorings` and `POST /tailorings/{id}/regenerate` to return a `StreamingResponse` using SSE (`text/event-stream`)
- [ ] Emit `data: <token>` events as the model generates, plus a terminal `data: [DONE]` event
- [ ] Frontend: replace the single `fetch` call in `NewTailoringForm` with an `EventSource` or `fetch` + `ReadableStream` consumer
  - Append tokens to a local state string as they arrive
  - Render with `ReactMarkdown` updating live — user reads as the model writes
  - TTFT (time to first token) for most models is < 1 second; user is reading within 2–3 seconds of generation starting
- [ ] Persist the completed output to the DB only after `[DONE]` — same as current behaviour, just deferred to stream end

This is the single highest-leverage change. Wall-clock time is unchanged; perceived time drops from "90 second spinner" to "document appearing in real time."

#### 2. SSE progress events for pre-generation pipeline stages
- [ ] Extend the SSE stream to include named stage events before generation begins:
  - `event: stage\ndata: scraping` — Playwright fetch starts
  - `event: stage\ndata: extracting` — job extraction LLM call starts
  - `event: stage\ndata: matching` — fast match LLM call starts
  - `event: stage\ndata: generating` — tailoring generation starts (then token stream follows)
- [ ] Frontend: render a stage indicator that updates as each event arrives — e.g. "Fetching job posting... → Extracting requirements... → Matching to your profile... → Generating document..."
- [ ] These are honest pipeline states, not fake progress animations — the message reflects what the backend is actually doing

#### 3. Streaming-aware regeneration
- [ ] Apply the same streaming approach to `POST /tailorings/{id}/regenerate`
- [ ] `TailoringDetail` document view enters a live-typing state during regeneration rather than going opaque with a spinner

#### 4. Visual loading treatment (optional, build on top of streaming)
- [ ] Once streaming is in place, the stage labels above can be paired with a simple animated treatment — e.g. a subtle progress bar that advances at each stage event, or a small icon that changes per stage
- [ ] A mascot concept (small pixel-art or vector character performing each operation) is brand-differentiating and worth exploring as a design iteration once the underlying stream is live — the mascot reacting to real pipeline events is satisfying in a way that a mascot animating over a spinner is not
- [ ] Keep it subtle and skippable — not every user wants whimsy

**Note on scrape latency:** The Playwright scrape (15–30s) is the one stage that is fundamentally slow and cannot be streamed. Job URL caching (Day 8.5) eliminates it entirely on retries for the same URL. Together, streaming + caching means: first visit has an honest progress indicator and streaming output; repeat visits skip the slow stage and jump straight to generation.

**Why this is slotted before public portfolio:** A product that feels slow and unresponsive is harder to share confidently. Streaming makes tailoring generation a delight to watch, which matters when users are sharing their tailoring page or showing the product to someone.

---

### Day 9 — Public Profile / Tailoring Portfolio Page

**Goal:** Each user has a public portfolio page that lists their public tailorings.

**Tasks:**
- [ ] Add `/u/{username_slug}` frontend route — public, no auth required
  - Derive username slug from Google display name on first login, stored on User
  - Shows: user name, avatar (from Google), list of public tailorings (role + company)
  - Each tailoring links to `/t/{slug}`
- [ ] This is a lightweight but impactful addition: it gives users a URL they can put in a bio or LinkedIn
- [ ] Add `username_slug` column to `users` table with unique constraint
  - Auto-generate on user creation from name (e.g., "Chara Dunbar" → "chara-dunbar")
  - If collision, append a number
- [ ] In Settings: allow the user to see and copy their public profile URL
- [ ] **If implemented:** migrate `/t/{slug}` URLs to `/t/{username_slug}/{shortcode}` — namespaces sharing URLs under the user's identity and makes the public profile the natural root

**Why this matters for the employment search:** A user's Tailord portfolio page shows *targeted, role-specific documents* — not a generic resume. Sharing `tailord.app/u/chara-dunbar` in an application is itself a signal of craft and product thinking.

---

### Day 10 — Documentation, Portfolio Write-Up, Cleanup

**Goal:** The project is polished enough to reference directly in applications. Legacy code is removed.

**Tasks:**
- [ ] Remove dead backend endpoints: `/parse`, `/generate` (the legacy match endpoint), `/job` (job.py — functionality now lives in tailorings.py)
- [ ] Remove dead frontend routes if any remain
- [ ] Write a clear, concise `README.md` at the repo root:
  - What Tailord is (one paragraph)
  - How to run it locally (dev commands from CLAUDE.md)
  - Architecture overview (brief)
  - Screenshots of the main UI states
- [ ] Update `CLAUDE.md` to reflect any new routes/files added this sprint
- [ ] Take 3–4 good screenshots of the product for portfolio use
- [ ] Write a 3-paragraph product case study (can go in README or a separate `/planning/portfolio-write-up.md`):
  - The problem it solves
  - Key technical decisions and why
  - What you'd do next

---

### Day 11 — Security Review

**Goal:** Identify and fix vulnerabilities before this product is referenced publicly or used with real user data.

**Threat model for Tailord:** single-tenant SaaS, authenticated users, LLM pipeline ingesting untrusted content (job URLs, resume text), public endpoints at `/t/{slug}`.

---

#### Prompt Injection
The LLM pipeline ingests content from two untrusted sources: job postings (scraped from arbitrary URLs) and user-provided resume/additional context text. A malicious job posting could embed instructions designed to manipulate the LLM output — e.g., override the tailoring prompt, exfiltrate experience data, or produce harmful content.

- [ ] Audit `generate_tailoring()` and all LLM calls: are system prompts and user-supplied content cleanly separated? Is user content always in the `user` role, never interpolated into the `system` prompt?
- [ ] Add a scrape sanitization step: strip `<script>`, hidden text, and suspiciously long invisible elements before passing scraped content to the LLM
- [ ] Consider capping scraped content length fed to the LLM (e.g., 8k tokens) — limits both injection surface and cost
- [ ] Review whether LLM output is ever executed, eval'd, or rendered as raw HTML — it should only ever be rendered as Markdown

#### SQL Injection
- [ ] Confirm all DB queries go through SQLAlchemy ORM parameterization — no raw SQL string interpolation anywhere
- [ ] Grep for `text(`, `execute(`, `f"SELECT`, `f"INSERT` — any raw SQL needs review
- [ ] Verify alembic migration scripts don't introduce unsafe patterns

#### Auth & Token Abuse
- [ ] **API key exposure:** The `X-API-Key` header is used by the frontend to authenticate backend calls. Confirm it is never logged, never returned in error responses, and not accessible to client-side JS (should only live in Next.js API routes server-side)
- [ ] **Session abuse:** NextAuth JWT sessions — confirm `session.user.id` (google_sub) is validated on every backend call via the `get_current_user` dependency; a forged `X-User-Id` header from a direct backend call should not bypass auth (the backend is internal-only, but belt-and-suspenders)
- [ ] **Public slug enumeration:** `/t/{slug}` is intentionally public, but verify there's no way to enumerate all public slugs (no `/tailorings/public` list endpoint, no sequential IDs)
- [ ] **Rate limiting:** No rate limiting exists on the tailoring creation endpoint — a single user could spam LLM calls, running up cost. Add a per-user limit (e.g., 10 tailorings/hour) or at minimum log a warning and review.
- [ ] **OAuth state validation:** Confirm NextAuth CSRF token / state param is validated on the Google OAuth callback

#### Input Validation & Injection Surface
- [ ] **URL validation:** `job_url` is passed to Playwright. Confirm it is validated as an HTTP/HTTPS URL before scraping — prevent `file://`, `ftp://`, or SSRF via internal Azure metadata URLs (e.g., `http://169.254.169.254/`)
- [ ] **File upload:** Resume uploads go directly to Azure Blob via presigned URL — confirm the backend enforces file type (PDF/DOCX/TXT only) and size limits at the presigned URL generation step, not just client-side
- [ ] **XSS:** Tailoring output is rendered as Markdown. Confirm the Markdown renderer sanitizes HTML — no `dangerouslySetInnerHTML` with raw LLM output

#### Cost & Performance
- [ ] **LLM token usage:** Add logging of prompt + completion token counts per tailoring generation. Establish a baseline; set an alert threshold.
- [ ] **Runaway scraping:** Playwright has a timeout now (Day 5), but confirm it applies to both navigation and content extraction, not just page load
- [ ] **No caching on scrape:** If a user creates two tailorings for the same URL, it scrapes twice. Consider caching the extracted job by URL (already stored in the `Job` record — check if it's being reused or re-scraped)
- [ ] **DB query patterns:** Check for N+1 queries in the tailoring list endpoint — if it fetches jobs for each tailoring separately, add a join

#### Secrets & Config
- [ ] Grep for hardcoded secrets, API keys, or connection strings in source (should be zero — all via env vars)
- [ ] Confirm `.env` files are in `.gitignore` and not tracked
- [ ] Review Azure Key Vault usage — are all production secrets actually coming from Key Vault, or are any set as plain Container App env vars?

---

## Day-by-Day Summary

| Day | Focus | Output | Status |
|-----|-------|--------|--------|
| 1 | Experience pivot + GitHub backend | `/experience/github` endpoint, repo fetching, sourced profile architecture | ✅ |
| 2 | GitHub + context frontend | Experience section fully functional, toasts, GitHub remove | ✅ |
| 3 | Regenerate + Delete | Tailoring lifecycle complete | ✅ |
| 3.5 | Cloud-agnostic infra | StorageClient abstraction, Terraform module refactor, Azure provider, backend containerized | ✅ |
| 4 | Sharing | Public tailoring URLs at `/t/{slug}` | ✅ |
| 5 | Polish | Error states, timeouts, recent tailorings dashboard, sidebar search, duplicate URL guard | ✅ |
| 5.5 | Pipeline robustness + Tailoring format | Scrape gating, PDF extraction, dual pipeline, match analysis tab, parsed profile panel, async isolation, Tailoring philosophy + structured output | ✅ |
| 6 | Notion OAuth | Connect/disconnect Notion from Settings | |
| 7 | Notion export | One-click export, Markdown→Notion blocks | |
| 8 | Notion polish | Parent page selection, stored export URL | |
| 8.5 | Pipeline hardening (deferred) | Empty profile detection, LLM output validation, token budgeting, job URL caching, prompt iteration | |
| 8.6 | Streaming + perceived performance | SSE streaming for tailoring generation, stage progress events, streaming-aware regeneration | |
| 9 | Public portfolio | `/u/{slug}` page with public tailorings | |
| 10 | Documentation + cleanup | README, remove legacy code, screenshots | |
| 11 | Security review | Prompt injection, SQL injection, token abuse, cost controls, SSRF | |

---

## What to Cut If Time Is Short

If any day runs long, cut in this order (least to most impactful to cut):

1. ~~Additional context textarea backend (Day 2)~~ — shipped
2. Public portfolio page (Day 9) — nice to have, not essential
3. Notion parent page selection (Day 8) — auto-create a default "Tailord Exports" page instead
4. Tailoring delete (Day 3) — keep regeneration, cut delete
5. Never cut: GitHub backend (Day 1), Notion export (Day 7), shareable URLs (Day 4)

---

## What Not to Build in This Sprint

- PDF export — too much scope for the value it adds; Notion export is better
- Team/sharing features — solo user tool for now
- A mobile app — the web product needs to be complete first
- Pricing / paywall — premature for portfolio purposes
- Re-engineering the LLM pipeline — the current one works; don't over-optimize

---

## Future / Backlog

### Azure Document Intelligence for Resume Text Extraction

**Context:** The current pipeline uses `pypdf`/`python-docx` for step 1 (document → raw text) and an LLM prompt for step 2 (raw text → structured JSON). The LLM step is the right approach and aligns with where the industry is moving (newer resume parsing APIs use LLMs internally). The vulnerability is step 1.

**Problem:** Badly formatted PDFs — multi-column layouts, embedded tables, fancy resume templates — produce garbled raw text that no amount of prompt engineering can fix downstream.

**Proposal:** Replace `pypdf` with Azure Document Intelligence's Layout model for PDF text extraction. It is structure-aware (handles columns, tables, reading order) and produces much cleaner output.

**Constraints:**
- Azure Doc Intelligence SDK must be abstracted behind the existing storage/client abstraction layer (do not import `azure.*` directly in app code per cloud-portability rules)
- Adds an API call with cost and latency implications — worth benchmarking against current pypdf failures before committing
- DOCX extraction via `python-docx` is generally reliable; probably not worth replacing

**When to consider:** If users report extraction failures (missing bullets, garbled work history) that can be traced to complex PDF layouts rather than LLM parsing errors. Not urgent until there is evidence of real failures at scale.

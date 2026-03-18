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
- [x] Tab switcher in `TailoringDetail` toolbar — absolutely centered regardless of left/right content width; tabs renamed: **Letter** (generated document), **Posting** (job view), **Analysis** (debug chunks)
- [x] Tab-aware copy button: Letter tab copies markdown, Analysis tab copies all chunks as structured markdown for pasting into Claude Code
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

---

### ✅ Day 5.6 — Enriched Job Posting View + Per-View Public Sharing

**Goal:** Surface a human-readable, enriched view of the scraped job posting in the tailoring detail. Extend the sharing system to allow each view (Letter, Posting) to be shared independently.

#### Enriched Job Posting View ✅
- [x] **Posting tab** in `TailoringDetail` toolbar — sits alongside Letter and Analysis; renders `JobChunk` data as a clean reading view (sections, bullets, paragraphs), not a debug card layout
- [x] **Score bar indicators** — 2px absolute-positioned left border per chunk: green (strong), amber (partial), red (gap). N/A chunks have no border and are non-interactive. Pre-enrichment chunks render as plain text.
- [x] **Click-to-expand rationale** — clicking a scored chunk expands a panel with the LLM's match reasoning and evidence source (Resume / GitHub / Direct Input). One chunk expanded at a time; clicking again collapses. Smooth height animation via CSS grid trick.
- [x] **Content alignment** — score bars sit at `-left-3` (12px offset) from the content edge, counter-translating on expand so the bar stays anchored while text slides. Letter and Posting views share the same `px-6 py-10` content width (720px at `max-w-3xl`).
- [x] **Clean degradation** — pending enrichment shows chunks without borders or interaction; errors surface a readable message rather than a blank panel.

**Why separate from Match Analysis:** Match Analysis is a developer/debug view with metadata rows, copy buttons, and raw score badges. The Posting tab is for reading and orientation — "what does this role actually require?" — and should feel like a clean document.

#### Per-View Public Sharing ✅
- [x] **`letter_public` + `posting_public`** columns on `Tailoring` (alembic migration `b8c9d0e1f2a3`), replacing the single `is_public` boolean. `is_public` retained as a SQLAlchemy `@hybrid_property` (`letter_public or posting_public`) for backwards-compatible querying.
- [x] **Migration backfills** `letter_public = is_public` for existing records; `posting_public` defaults false.
- [x] **`POST /tailorings/{id}/share`** now accepts `{ letter: bool, posting: bool }` body — updates both flags independently, generates slug on first activation. Returns `{ public_slug, letter_public, posting_public }`.
- [x] **`DELETE /tailorings/{id}/share`** clears both flags.
- [x] **`GET /tailorings/public/{slug}`** filters on `letter_public | posting_public`; includes chunks in response only when `posting_public=True`. Gap chunks (score=0) are included but render without a color bar or click interaction — present but unscored in the public view.
- [x] **Share popover redesigned** — per-view `Switch` toggles (new `Switch` UI component) replace the single "Make public" button. Toolbar button label reflects active state: `Share` / `Public · Letter` / `Public · Posting` / `Public`. Inline note explains the public posting view behavior (gaps rendered plain, partial matches shown as muted green instead of amber).
- [x] **`--color-score-partial-public`** CSS token (`#5A9E78` light / `#5A8E6E` dark) — muted green used for partial matches on public-facing views.
- [x] **Public page (`/t/{slug}`) updated** — tab switcher rendered when both views are public; letter-only and posting-only modes work without tabs. `JobPosting` receives `publicMode={true}` and `hideHeader={true}`.
- [x] **Content alignment on public page** — `px-6` wrapper pattern (padding on outer, `border-b`/`border-t` on inner) prevents borders from extending through padding. All sections — page header, tab switcher, letter content, posting content, footer — resolve to the same 720px content width.

---

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

### Day 6 — Notion OAuth Setup + Settings Page ✅

**Goal:** Users can connect their Notion workspace to Tailord.

**Tasks:**
- [x] Register Tailord as a Notion OAuth app at [notion.so/my-integrations](https://www.notion.so/my-integrations)
  - Callback URL: `{NEXTAUTH_URL}/api/auth/notion/callback`
  - Tagline: "Export your tailored advocacy documents to Notion, instantly."
  - Privacy policy and Terms of Use pages created and live at `tailord.app/privacy` and `tailord.app/terms` (required for integration registration)
- [x] Add Notion OAuth flow — standalone handler (not NextAuth provider):
  - `GET /api/auth/notion` — fetches auth URL from backend, sets CSRF state cookie, redirects to Notion
  - `GET /api/auth/notion/callback` — validates state, exchanges code via backend, redirects to `/dashboard/settings?notion=connected`
  - `DELETE /api/notion` — disconnect proxy
- [x] Backend `notion` router (`backend/app/api/notion.py`):
  - `GET /notion/auth-url` — constructs and returns the Notion OAuth authorize URL
  - `POST /notion/callback` — exchanges code for token via Notion API, stores all workspace fields on the user record
  - `DELETE /notion/disconnect` — clears all Notion fields
- [x] DB migration `c2d3e4f5a6b7`: added `notion_access_token`, `notion_bot_id`, `notion_workspace_id`, `notion_workspace_name` to `users` table
- [x] `_user_response` updated to include `notion_workspace_name`
- [x] `SettingsPanel`: "Connected Apps" section with Connect/Disconnect button, workspace name display, and error feedback via `?notion=error` query param. Settings page wrapped in `Suspense` for `useSearchParams`.
- [x] Terraform: `notion_client_id` + `notion_client_secret` added as Key Vault secrets and injected into the backend Container App. `NOTION_REDIRECT_URI` set as plain env var using `var.domain_name`.

**Implementation notes:**
- Used standalone OAuth handler rather than a NextAuth provider — cleaner separation, avoids re-triggering the NextAuth session flow
- Single Notion integration handles both local and production (dev mode supports up to 10 workspaces; separate dev integration is a pre-launch task)
- OAuth tokens stored as plaintext in Postgres for now (Azure encrypts at rest); application-layer encryption is noted in the pre-launch checklist
- `NOTION_CLIENT_ID` does not need to be in the frontend — the auth URL is constructed entirely server-side in the backend

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

#### 5. Progressive disclosure — show structure before content is ready
- [ ] As soon as the job scrape + extraction completes (before match scoring or tailoring generation), enough data exists to render skeleton views of both tabs:
  - **Job Posting tab:** render the un-enriched chunks immediately — the user can start reading the job description while the rest of the pipeline runs. Score indicators can fade in as chunk enrichment completes.
  - **Document tab:** render a template shell — greeting, company name, job title, dividers, footer — with placeholder blocks where advocacy sections will appear. Makes it visually obvious something real is being built, not just a spinner.
- [ ] Both views should clearly signal in-progress state (subtle pulse on placeholders, a "Generating..." label) so the user understands the content is incomplete — not that the product is broken
- [ ] This is intentionally designed before streaming is in place: it reduces perceived wait time by giving the user something to read immediately after job parsing completes, even if tailoring generation hasn't started yet. When streaming is later added, the Document tab transitions smoothly from skeleton → live token stream → complete.

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
| 5.6 | Enriched job posting view + per-view public sharing | Posting tab (score bars, expandable rationale, content alignment); `letter_public`/`posting_public` per-view sharing with redesigned popover, muted public color token, tab switcher on public page | ✅ |
| 6 | Notion OAuth | Connect/disconnect Notion from Settings; legal pages live; Terraform Key Vault secrets for Notion | ✅ |
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

---

### Custom Pronouns in User Settings

**Context:** The LLM currently infers pronouns from the candidate's name (e.g. "Charles" → he/him). This is unreliable and excludes candidates who use she/her, they/them, or other pronouns.

**Proposal:** Add a pronouns field to user settings (free-text or a small set of common options: he/him, she/her, they/them, other). Surface it prominently in the settings panel — not buried — since it directly affects generated output.

**Pipeline integration:**
- Primary: inject the candidate's pronouns into the tailoring system prompt so the LLM uses them natively throughout generation. This is the cleanest approach and handles grammatical agreement naturally (e.g. "they have" not "they has").
- Safety net: after LLM generation, run a deterministic pronoun replacement pass to catch any gendered pronouns the LLM may have inferred despite instructions. A regex pass over he/him/his/she/her/hers with the correct forms is straightforward for binary pronoun sets; they/them requires more care around verb agreement.

**Schema changes:**
- Add `pronouns: str | None` to the `User` model
- Expose via a settings endpoint
- Pass through to `generate_tailoring()` and into the tailoring prompt

**Note:** If pronouns are not set, default to they/them in the prompt rather than inferring from name — safer and more inclusive default.

---

### Pre-Launch Checklist — Before Opening to External Users

Everything below is a non-issue while Tailord is single-user. These items become necessary before the product is opened to real external users. None of them require a lawyer, but all of them require deliberate attention.

#### Legal Documents
- **Rewrite the Privacy Policy** — the current policy was generated with "one US user, no EU/UK users" assumptions. Before external users, commission a proper policy that accurately reflects all data practices, third-party processors, and applicable jurisdictions (at minimum GDPR if any EU users are possible, CCPA if US users).
- **Rewrite the Terms of Use** — the current terms were generated with minimal configuration. A real terms document should reflect the actual product, acceptable use, AI-generated content disclaimers, and the liability posture you want.
- **Host both documents on `tailord.app`** — the current pages at `/privacy` and `/terms` serve from `src/content/`. Update the content and ensure the "Last updated" dates are accurate.
- **Add Privacy and Terms links** to the product footer — at minimum the public tailoring page (`/t/[slug]`) and the marketing/landing page. The dashboard footer is optional but good practice.

#### Cookie Consent
- Tailord currently uses only essential session cookies (NextAuth JWT). No analytics, no advertising, no tracking.
- If that remains true, a cookie consent banner is **not required** under GDPR for essential-only cookies — you just need to disclose them in the Privacy Policy (already done).
- If you ever add analytics (e.g. PostHog, Plausible, Google Analytics), a consent banner becomes required for EU users. Use a lightweight library like `cookie-consent` or a managed solution like Termly's banner widget.
- **Decision point:** choose an analytics tool (or consciously choose none) before opening to external users, then add the banner if needed.

#### Notion Integration
- **Separate dev and prod integrations** — currently a single Notion integration handles both `localhost` and `tailord.app`. Before external users, create a separate "Tailord Dev" integration for local development so that test activity doesn't appear in production logs or affect production OAuth flows.
- **Submit for Notion public review** — the integration currently runs in development mode (max 10 workspaces). To support external users, submit for Notion's public integration review. This requires: live privacy policy URL, live terms URL, integration logo/icon (256×256px minimum), description of permissions requested, and screenshots or a demo. Review is manual and takes days to weeks — submit early.
- **Scope review** — before public review, audit the permissions your integration requests. Tailord should only request `insert_content` (to create pages). No `read_content`, no `update_content`, no user information beyond what OAuth provides. Minimal scope = faster approval and better user trust.
- **Notion integration icon** — you need a square logo at 256×256px minimum for the Notion listing. Worth investing in a proper icon before the public submission.

#### Account Management
- **Account deletion** — the Privacy Policy states users can request deletion by contacting you. Before external users, build a self-serve account deletion flow in Settings. This is required under GDPR (right to erasure) and CCPA. Deletion should remove: User record, Experience record and resume file from storage, all Jobs, all Tailorings, Notion token.
- **Email on critical actions** — consider transactional emails for account-level events (welcome, account deletion confirmation). Not required but expected by users.

#### Access Control
- **Remove the manual approval gate** — the `status: pending | approved` field on `User` currently gates access. This was appropriate for solo use. Before external users, decide: open signup, waitlist, or invite-only. The current approval mechanism requires manual intervention which doesn't scale.
- **Rate limiting** — no per-user rate limiting exists on tailoring creation (each tailoring triggers multiple LLM calls). Add a reasonable limit (e.g. 10 tailorings/day per user) before external users can run up LLM costs unchecked.
- **Cost controls** — set spend alerts on your LLM provider before external users. A single motivated user could generate significant cost without limits.

#### Security
- **Application-layer encryption for user OAuth tokens** — currently `notion_access_token` (and any future third-party tokens) are stored as plaintext in Postgres. Azure encrypts at rest by default, which is acceptable for solo use. Before external users, add application-layer encryption: store a single symmetric key in Key Vault, fetch it once at backend startup, and encrypt/decrypt tokens in the app before writing to / after reading from the DB. This is the correct pattern — do not store per-user secrets as individual Key Vault secrets, which doesn't scale and isn't what Key Vault is designed for.

#### Infrastructure
- **Custom domain email** — `hello@tailord.app` or similar for user-facing communications and legal contact. Currently the privacy policy lists a personal Gmail address.
- **Monitoring and alerting** — set up basic uptime monitoring and error alerting before relying on the product being available for others.
- **Prometheus + Grafana** — structured metrics collection and dashboarding. The backend (FastAPI/uvicorn) can expose a `/metrics` endpoint via `prometheus-fastapi-instrumentator`; the frontend can emit custom metrics via an OpenTelemetry collector. Grafana provides dashboards over both. Azure Managed Grafana is available if staying within the Azure ecosystem.
- **Azure Chaos Studio** *(stretch goal)* — fault injection and resilience testing against the Container Apps and PostgreSQL infrastructure. Useful for validating graceful degradation (e.g. DB connectivity loss, container restarts) before the platform carries real user traffic. Low priority until the user base justifies the operational overhead.

---

### Chunk-Informed Letter Regeneration

**Context:** The current Letter is generated during the fast pipeline, before chunk enrichment completes. The slow pipeline produces per-chunk match scores and rationales — pre-computed evidence chains (which bullets in the profile support which job requirements) that the fast letter has to re-derive from scratch.

**Hypothesis:** Once chunk enrichment is complete, triggering a second letter generation pass that feeds the scored chunks as context could produce a more precise, evidence-driven Letter — particularly for postings with rich prose sections that don't map cleanly into the extracted requirements list.

**What it could improve:**
- Advocacy statements grounded in explicit evidence chains rather than re-derived profile-to-requirement connections
- More deliberate weighting: strong-match chunks (score=2) lead; gaps handled strategically based on scored context rather than inferred
- Better coverage of signals that live in paragraph/culture content, not bullet requirements

**Key uncertainty:** The quality delta is likely real but variable. For structured, bullet-heavy postings where extraction captures everything, the fast letter may already be near-ceiling. The improvement would be most noticeable on postings with dense prose sections. The only way to know if it's worth the extra LLM call is to generate both versions for the same tailoring and compare directly.

**Before building:** Generate enriched vs. fast letters side-by-side for 5–10 real tailorings. If the enriched version is clearly more specific and evidence-driven, the UX pattern ("fast draft → enhanced version available") makes sense. If the delta requires squinting, it's not ready to surface to users.

**UX pattern if pursued:** The client already polls for enrichment status — extending this to trigger a letter update when enrichment completes is straightforward. The enhanced letter would need to be stored separately (new DB column) to avoid clobbering the fast letter. The indicator should be specific ("Using full job analysis to strengthen this") not generic ("Processing").

---

### North Star — Personal Site Publishing

**The idea:** Tailord already knows a user's experience in structured form — work history, skills, projects, GitHub activity, and now the public tailorings they've produced. A lot of people have resumes and maybe a GitHub profile; far fewer have personal websites. Tailord could bridge that gap by offering a standard template-based personal site that users can publish directly from the platform.

**The integration vision:**
- User clicks "Publish my site" in Tailord — selects a template, reviews auto-populated content from their Experience, and deploys to Vercel via the Vercel API with one click
- The deployed site gets a `{username}.tailord.app` subdomain by default (or Tailord walks the user through pointing a custom domain)
- The site is pre-wired to the Tailord public API — public tailorings automatically appear on the personal site as they're created, no manual export needed
- A later addition: a limited chat widget on individual tailoring pages that lets a recruiter or hiring manager ask follow-up questions about the candidate's experience, answered via the Tailord API using the user's structured profile as context

**Why this makes sense for Tailord:**
- Tailord's data advantage is that it holds structured, LLM-processed experience data — a personal site is a natural second output of that data, not a pivot
- Public tailorings are already shareable; a personal site just gives them a permanent home under the user's own brand
- The Vercel integration is a well-documented deploy API — not a heavy lift technically, and a meaningful portfolio piece (OAuth, deploy pipelines, subdomain provisioning, webhook-driven site updates)
- The chat feature on tailorings is a direct extension of the existing enrichment infrastructure — the scored chunks are already a structured evidence base for a retrieval-augmented Q&A over someone's experience

**Business reality check:** This is speculative — personal site builders are a crowded space and this is only differentiated if Tailord's experience data is genuinely richer than what a user would paste into Squarespace. Worth building as a technical exercise and portfolio demonstration before committing to it as a product direction.

**Technical building blocks (in order):**
1. **Tailord public API** — versioned REST API exposing public tailoring data; rate-limited, API-key-gated per user. The `/t/[slug]` page already renders this data; the API is just a structured version of the same endpoint.
2. **Site template** — a Next.js starter (or Astro) that fetches from the Tailord API at build time and/or on-demand. Open-sourceable; users could fork and customise.
3. **Vercel deploy integration** — OAuth with Vercel, trigger a deploy of the template with the user's API key baked in as an env var, provision the subdomain via Cloudflare.
4. **Chat on tailorings** — retrieval-augmented Q&A using scored chunks + profile as context, streamed via the Tailord API. Scoped to public tailorings only; rate-limited per session.

---

### Feature — Resume Enrichment (Per-Element Context)

**The problem:** A resume is a compressed document. One page forces candidates to reduce real experience down to a single bullet or a skill keyword. When Tailord extracts a profile from a resume, it inherits that compression — a line like "Led migration to microservices architecture" contains almost no signal about the actual scope, the decisions made, the constraints navigated, or the outcome. GitHub can fill some of this gap for engineers with public work, but most candidates — in any discipline — don't have publicly visible artefacts at all.

**The idea:** After a profile is extracted, surface each parsed element to the user and let them annotate it directly. Not a form to rewrite their resume, but targeted prompts: *"Tell us more about this."* Each annotation becomes part of the structured profile, available to the LLM when generating tailorings. The resume stays compressed; Tailord's internal representation of the candidate does not.

**Why this matters:**
- For users without GitHub or a portfolio, this is the primary mechanism for providing depth beyond the resume
- Even for users with public work, resume items often cover experience that doesn't appear anywhere online — internal tools, org-scale decisions, cross-functional projects
- The advocacy letter is only as specific as the evidence it has to draw from; richer annotations directly improve letter quality and chunk scoring accuracy
- It aligns with the platform's north star: Tailord as a tool that helps candidates surface and articulate their experience, not just process it

**What enrichment could look like per element type:**

| Element | Prompt direction |
|---------|-----------------|
| Work experience bullet | Scope, constraints, outcome, what you'd do differently |
| Skill keyword | Context of use, depth/years, notable application |
| Project | What problem it solved, your specific contribution, stack decisions |
| Education | Relevant coursework, research, what you actually learned vs what's listed |
| Achievement/award | What it was for, who it was against, why it mattered |

**Relationship to post-tailoring gap prompts:** These are complementary but different. Gap prompts are reactive — they fire after a tailoring and ask for missing context specific to a job. Resume enrichment is proactive — it happens once at the profile level and benefits all future tailorings. The data model should store enrichments on the Experience record, keyed to extracted profile elements, so they flow into every generation automatically.

**UX consideration:** The enrichment flow shouldn't feel like homework. The right framing is: *"Your resume tells us what you did. Help us understand what it was actually like."* Each prompt should be specific to the element, optional, and easy to skip. A short free-text input per item is enough — this isn't a structured form, it's an invitation to add colour. Progress should be visible so users know their profile is getting stronger as they add context.

**Data model:** `extracted_profile` is currently a JSON blob on the `Experience` record. Enrichments could be stored as a parallel `enrichment_notes` JSON field, keyed by element identifier (e.g. `work[0].bullets[2]`, `skills.python`), or by merging annotation fields directly into the extracted profile schema. The former is simpler to implement; the latter makes enriched context transparent to the LLM without prompt engineering to stitch two structures together.

---

### Technical Debt — Integrations Table

**Context:** Notion integration metadata (access token, bot ID, workspace ID/name, parent page ID) currently lives as flat columns on the `users` table. This was the right call for a single integration, but becomes a maintenance problem as more integrations are added — each one adds a column cluster and widens a table that should stay narrow.

**When to act:** When a second integration is added. The refactor at that point is bounded and the pattern will be clear.

**Target schema:**
```sql
integrations (
  id           UUID PK,
  user_id      UUID FK → users,
  provider     VARCHAR,   -- 'notion', 'linear', etc.
  access_token VARCHAR,
  metadata     JSONB,     -- workspace_id, workspace_name, bot_id, parent_page_id, etc.
  created_at   TIMESTAMP,
  UNIQUE (user_id, provider)
)
```

The `metadata` JSONB column absorbs provider-specific fields without requiring schema changes per integration. The `UNIQUE (user_id, provider)` constraint enforces one connected account per provider per user — relax to allow multiple accounts per provider if that ever becomes a requirement (e.g. connecting two Notion workspaces).

**Migration path:**
1. Create `integrations` table
2. Backfill one row per user where `notion_access_token IS NOT NULL` with `provider = 'notion'` and metadata populated from the flat columns
3. Update all query sites in `app/api/notion.py` and `app/api/users.py` to read/write via the new table
4. Drop the `notion_*` columns from `users`

Frontend is unaffected — the API contract doesn't change.

# Adjusted Sprint Plan — 6 Days to Ship-Ready

*Replaces the remaining days in `02-two-week-plan.md` (Days 8.5–12).*

Two phases, clear split:

- **Days A1–A3 — User-facing:** ship everything a real user or hiring manager would see or experience
- **Days P1–P3 — Platform:** harden the foundation once the product surface is stable

---

## Phase 1 — User-Facing (Days A1–A3)

### Day A1 — Streaming + Perceived Performance ✅

**Goal:** The tailoring generation flow feels fast. Users start reading their document within seconds, not after a 60–90 second blank wait.

**Why first:** This is the single highest-leverage UX change available. Wall-clock time is hard to eliminate across four sequential LLM + scrape operations, but perceived time can drop dramatically. Every other user-facing feature lands better if the baseline generation experience doesn't feel broken.

**Approach taken:** Phase list with elapsed timers (Claude Code style) + early redirect, rather than token streaming. Token streaming added backend complexity without meaningful UX gain given the ~10s generation window.

#### 1. SSE stream — scraping + extracting only (early redirect)
- [x] `POST /tailorings` and `POST /tailorings/{id}/regenerate` return `StreamingResponse` (SSE)
- [x] Emit `event: stage` / `data: scraping` and `event: stage` / `data: extracting` as each phase begins
- [x] On extraction complete: create `Job` + `Tailoring` records with `generation_status="generating"`, emit `event: ready` with tailoring ID
- [x] Matching + generation run in a `BackgroundTasks` task (`_finalize_tailoring`), updating `generation_stage` and `generation_started_at` in DB
- [x] Added `generation_status`, `generation_stage`, `generation_error`, `generation_started_at` columns to `Tailoring` + Alembic migration

#### 2. Frontend — phase list + early redirect
- [x] `NewTailoringForm`: phase list with per-phase elapsed timers (scraping, extracting); redirect to `/dashboard/tailorings/{id}` on `event: ready`
- [x] `TailoringDetail`: polls `GET /tailorings/{id}` every 2s while `generation_status === 'generating'`; shows matching/writing phase list with server-side elapsed computed from `generation_started_at`
- [x] 1s tick effect forces elapsed re-renders during background generation
- [x] `JobPosting` tab: contextual loading message when `generationReady === false` or `enrichment_status` is pending/processing

---

### Day A2 — Public Profile Page

**Goal:** Each user has a public portfolio URL they can drop in a bio or application.

**Why second:** The sharing infrastructure (`/t/{slug}`) is already live. The profile page is a lightweight addition that meaningfully expands the product's reach — one URL that surfaces all of a user's public work in context.

#### 1. Data model
- [x] Add `username_slug` column to `users` table (unique, nullable)
  - Auto-generate on user creation from display name (`"Chara Dunbar"` → `"chara-dunbar"`); append number on collision
  - Migration: backfill existing users
- [x] Alembic migration

#### 2. Backend
- [x] `GET /users/public/{username_slug}` endpoint — gated behind `profile_public=True`
  - Returns: `name`, `avatar_url`, `username_slug`, `github_username`, `profile` (extracted resume)
  - Tailorings intentionally excluded — see "Future: Tailorings on profile page" note above
- [x] `profile_public` bool on User (default False) + migration `d7e8f9a0b1c2`
- [x] Extended `ExtractedProfile` schema with `phone`, `location`, `headline`, `title`, `work_experience.location`, `education.location`
- [x] Added `title` field: 2–5 word role (e.g. "Software Engineer"), distinct from `headline`
- [x] Updated LLM extraction prompt to extract all new fields; LLM now generates a summary if none is present in the resume
- [x] `github_username` included in public profile response from `experience.github_username`

#### 3. Frontend
- [x] `/u/[slug]` route — two-pane layout (sticky sidebar + scrollable content), renders summary, work experience, education, skills, certifications, projects, contact
- [x] `/dashboard/profile` — private preview of the public profile with sticky visibility banner (Public/Private status, link to live URL, link to visibility settings)
- [x] Shared `ProfileSidebar` component: name, title, headline, location, social links (LinkedIn, GitHub), animated scroll-based nav (scroll-position threshold with first/last section clamping), back-to-top button
- [x] Section headers: icon + label + divider line; skill group sub-labels (Technical, Soft Skills, Certifications)
- [x] OG and Twitter card meta tags on `/u/[slug]` (`generateMetadata`); description priority: headline → summary excerpt → fallback
- [x] Settings: `profile_public` toggle (Public/Private); profile URL with copy button only shown when enabled
- [x] Link from `/t/{slug}` back to author's profile page
- [x] "Profile" nav item added to dashboard sidebar

#### Future: Tailorings on profile page
Tailorings were intentionally removed from the public profile. The philosophy: the profile surfaces *who you are and what you're capable of*, not your active job search. Showing all targeted companies/roles to any recruiter who visits is a liability for the candidate — it exposes competitive intelligence, signals desperation, and undercuts negotiating position.

When we revisit this, the right model is a **third toggle** per tailoring: `show_on_profile` (distinct from `letter_public` / `posting_public`). This keeps individual sharing opt-in separate from portfolio showcasing, and lets the candidate curate exactly which tailorings (if any) appear on their profile. Left sidebar placement would be preferred over right panel, so they appear above the fold regardless of scroll position.

---

### Day A3 — Polish, Cleanup + Documentation

**Goal:** The product is clean, self-explanatory, and reference-ready.

**Why third:** Before locking in the platform (testing, staging, security), the surface needs to be stable. Dead code makes tests harder to write, and a clear README makes security review faster.

#### 1. Dead code removal
- [ ] Remove legacy backend endpoints: `/parse`, `/generate` (old match endpoint), `/job` (`job.py` — superseded by `tailorings.py`)
- [ ] Remove any dead frontend routes
- [x] Audit `CLAUDE.md` — update file paths and routing table to reflect current state

#### 2. README
- [x] Write `README.md` at repo root (what Tailord is, architecture, local dev, env vars, key concepts, deployment)

#### 3. Portfolio write-up
- [ ] `planning/12-portfolio-writeup.md`:
  - The problem it solves
  - Key technical decisions and why (dual pipeline, streaming, Notion integration, chunk scoring)
  - What I'd do next

#### 4. Minor UX cleanup (opportunistic — only if clearly needed)
- [x] Settings: Notion disconnect error surfaced inline
- [x] Bullets: LLM prompt rule + `_clean_profile()` post-processing strips leading bullet chars at source; frontend band-aid removed
- [x] Bug: GitHub data preserved when resume added after GitHub (`extracted_profile` spread fix)
- [x] Bug: Source-aware remove/replace resume logic — `_has_non_resume_sources()` + `_clear_resume_fields()` helpers
- [x] Bug: `title` field added to `ProfileUpdate` Pydantic model

#### 5. URL structure + username settings
- [x] Tailoring public URL restructured: `/t/{slug}` → `/u/{userSlug}/{tailoringSlug}`
  - `Tailoring.public_slug` global unique constraint dropped; composite unique `(user_id, public_slug)` added
  - Alembic migration `e1f2a3b4c5d6`
  - Backend endpoint `GET /tailorings/public/{slug}` → `GET /tailorings/public/{username_slug}/{tailoring_slug}` (validates user ownership)
  - `GET /tailorings/{id}` response now includes `author_username_slug`
  - Frontend: `/u/[slug]/[tailoringSlug]/` page created; `/t/[slug]/` deleted; API proxy routes updated
  - `TailoringDetail.tsx` share URL updated to `/u/{author_username_slug}/{public_slug}`
- [x] User-settable username in Settings
  - Backend: `username_slug` added to `UserUpdate` with format validation (3–30 chars, `[a-z0-9-]`, no leading/trailing hyphen) + reserved words check + uniqueness enforcement (409 on conflict)
  - Backend: `GET /users/check-username/{slug}` endpoint for availability check
  - Frontend: username section in Settings with debounced availability check, format validation, link-breaking warning, save via `PATCH /api/users`

---

### Day A4 — My Experience Improvements

**Goal:** The experience processing flow feels responsive, and users have control over how their profile is interpreted.

**Why fourth:** The experience pipeline is the foundation everything else builds on — bad or incomplete parsing silently degrades every tailoring. Giving users visibility and edit access turns a black box into something they trust. The timer work is also a direct extension of the perceived-performance pattern established in A1.

#### 1. Processing progress indicator
- [x] Replace the static "Processing…" state in the Experience page with a phase list + elapsed timers (same pattern as tailoring generation)
- [x] Backend: `POST /experience/process` now returns SSE `StreamingResponse` — phases: `extracting` (text extraction), `analyzing` (LLM profile extraction), `ready`
- [x] Frontend: reads SSE stream directly from POST response; shows phase list with per-phase elapsed timers; transitions to parsed view on `ready`; falls back to polling on page reload if SSE gone

#### 2. Parsed profile review and editing
- [x] `EditableResumeProfile` component: editable fields for all resume sections (personal info, work experience with bullets, skills, certifications, education)
- [x] `PATCH /experience/profile` backend endpoint: merges partial update into `extracted_profile.resume`, updates `processed_at`
- [x] Edit/Cancel/Save pattern — explicit save, no auto-save; "Edit" button in Parsed Profile section header
- [x] After saving: "Profile updated — you may want to regenerate tailorings" banner with link to tailorings list

---

### Day A5 — Miscellaneous UX

**Goal:** Targeted user experience improvements directed session by session.

- [x] Settings: Replace profile visibility button with a `Switch` component (state clearly visible at a glance; consistent with tailoring share popover). Confirmation dialog required when enabling public — instant when disabling.
- [x] Settings: Account deletion — "Danger zone" section with confirmation dialog; checkbox acknowledgment required; deletes storage file + tailorings + jobs + experience + user in FK-safe order; signs out and redirects to `/` on success.
- [x] Settings: Custom pronouns — preset chips (she/her, he/him, they/them) + custom free-text option. Pronouns injected into all LLM prompts via `_format_sourced_profile()` as a `[CANDIDATE]` block — single injection point covering tailoring generation, requirement matching, and chunk scoring. Tailoring system prompt updated with explicit pronoun rule; defaults to gender-neutral language if unset.
- [x] Job Posting view: personal advocacy blurbs per chunk. `ChunkMatchResult` gains `advocacy_blurb` (populated by LLM for score ≥ 1 using candidate name/pronouns from `[CANDIDATE]` block; null for gaps/n/a). Public/recruiter view renders `advocacy_blurb`; internal Analysis tab surfaces both fields labelled. Migration `a3b4c5d6e7f8` adds column to `job_chunks`.
  - Rationale and advocacy convey the same core argument with different register and audience: rationale is analytical (explains the score, written for internal review); advocacy is advocating (same evidence, written in the candidate's voice for a recruiter).
  - Advocacy respects the score — a partial match reads like a partial. Honest representation of proximity is a platform value: a candid partial makes the strong matches more credible.
  - Advocacy must anchor to specific evidence (role, project, technology, outcome) — generic platitudes without specifics are prohibited by the prompt.

---

## Phase 2 — Platform (Days P1–P3)

### Day P1 — Security Review

**Goal:** Identify and fix vulnerabilities before the product is referenced publicly or used with real user data.

**Threat model:** single-tenant SaaS, authenticated users, LLM pipeline ingesting untrusted content (job URLs, resume text), public endpoints at `/t/{slug}` and `/u/{slug}`.

#### Prompt Injection
- [ ] Audit all LLM calls: user-supplied content always in the `user` role, never interpolated into `system` prompt
- [ ] Add a scrape sanitization step: strip `<script>`, hidden text, and suspiciously long invisible elements before passing scraped content to the LLM
- [ ] Cap scraped content length fed to the LLM (e.g., 8k tokens) — limits injection surface and cost
- [ ] Confirm LLM output is only ever rendered as Markdown, never as raw HTML or executed

#### Auth & Token Abuse
- [ ] **API key exposure:** `X-API-Key` header never logged, never returned in error responses, not accessible to client-side JS
- [ ] **Session abuse:** confirm `session.user.id` (google_sub) is validated on every backend call; a forged `X-User-Id` header from a direct backend call should not work (backend is internal-only, but belt-and-suspenders)
- [ ] **Public slug enumeration:** verify no endpoint leaks a list of all public slugs (now scoped per user — `/tailorings/public/{username_slug}/{tailoring_slug}`)
- [ ] **Rate limiting:** no per-user limit on tailoring creation — add a guard (e.g., 10/hour) or at minimum log a warning on high-frequency creation
- [ ] **OAuth state validation:** confirm CSRF state param is validated on Google OAuth callback and Notion OAuth callback

#### Input Validation
- [ ] **SSRF:** `job_url` passed to Playwright — validate as HTTP/HTTPS only; block `file://`, `ftp://`, internal Azure metadata URLs (`169.254.169.254`)
- [ ] **File upload:** confirm backend enforces file type (PDF/DOCX/TXT) and size limits at presigned URL generation, not just client-side
- [ ] **XSS:** tailoring output rendered as Markdown — confirm renderer sanitizes HTML, no `dangerouslySetInnerHTML` with raw LLM output

#### SQL Injection
- [ ] Confirm all DB queries go through SQLAlchemy ORM — grep for `text(`, `execute(`, `f"SELECT`, `f"INSERT`
- [ ] Verify alembic migrations don't introduce unsafe patterns

#### Secrets & Config
- [ ] Grep for hardcoded secrets, API keys, connection strings in source
- [ ] Confirm `.env` files are gitignored and untracked
- [ ] Review Azure Key Vault usage — confirm all production secrets come from Key Vault, not plain Container App env vars

#### Cost & Performance
- [ ] Confirm Playwright timeout applies to both navigation and content extraction
- [ ] Check for N+1 queries in the tailoring list endpoint
- [ ] LLM token logging baseline: establish prompt + completion token averages per operation; set a cost alert threshold

---

### Day P2 — Testing + CI Gate

**Goal:** Merges to `main` are gated by automated tests. The test suite covers the critical paths, not every line.

#### Backend — pytest
- [ ] Set up pytest with `pytest-asyncio` and a test database (PostgreSQL via `pytest-postgresql` or SQLite in-memory)
- [ ] Unit tests — pure functions: `notion_export.py` (`chunks_to_notion_markdown`, `_escape`, `_strip_links`, `_strip_formatting`), `chunk_display.py` (`is_display_ready`), `tailorings.py` (`_validate_profile`, `_generate_slug`)
- [ ] Integration tests — FastAPI `TestClient`: tailoring CRUD, share/unshare, public slug lookup, Notion export (mock Notion API with `responses` or `httpx` mock transport), 401 revoke flow
- [ ] Fixture helpers: factories for `User`, `Tailoring`, `Job`, `JobChunk` — no setup duplication across tests
- [ ] Coverage target: 80%+ on `app/api/` and `app/services/` — focused on auth checks, ownership guards, enrichment status gating

#### Frontend — Jest
- [ ] Unit tests: `InlineMarkdown` rendering, `scoreBarColor` logic, `groupBySection` filtering
- [ ] Consider `next-test-api-route-handler` for testing Next.js API proxy routes in isolation

#### GitHub Actions — CI Gate
- [ ] `.github/workflows/ci.yml`: triggers on every PR to `main` and on push to `main`
  - Backend job: `uv run pytest`
  - Frontend job: `npm run lint && npm run build && npm test` (type-check + build + unit tests)
  - Run both jobs in parallel
- [ ] Cache `uv` deps and `node_modules` between runs — target < 3 min total
- [ ] Branch protection rule on `main`: require CI to pass before merge

---

### Day P3 — Staging Environment + Pipeline Hardening

**Goal:** A staging environment exists with near-zero idle cost. Remaining pipeline robustness gaps are closed.

#### Staging — Azure Container Apps Revisions
- [ ] Create a `staging` revision alongside `prod` within the same Container App
  - `staging`: min replicas = 0, max = 1 — scales to zero when not in use (zero idle cost)
  - `prod`: min replicas = 1 (always on)
  - `staging` receives 0% external traffic but is accessible at its revision-specific URL
- [ ] Deployment workflow update (`.github/workflows/deploy-azure.yml`):
  - On merge to `main`: deploy image → activate `staging` revision → smoke test (`/health` 200) → promote to `prod`
  - On manual trigger or tag: deploy directly to `prod`
- [ ] Staging database: use same DB with clearly-labelled staging data (Option C from P3 notes) — simplest for a solo project; revisit if data bleed becomes a concern
- [ ] Cloudflare: route `staging.tailord.app` → staging revision FQDN via proxied CNAME
- [ ] `ENVIRONMENT=staging` env var for more verbose logging in staging

#### Pipeline Hardening (remaining from Day 8.5)
- [ ] **Token budget cap:** `truncate_to_tokens(text, max_tokens)` helper (tiktoken) — apply to scraped job markdown before any LLM prompt. Prevents runaway costs and context length errors on unusually long postings.
- [ ] **Job URL caching:** skip Playwright scrape + job extraction LLM for recently-seen URLs (< 7 days); rerun all other LLM steps fresh. Implement once extraction quality feels stable enough to trust cached output.
- [ ] **Profile formatting as compact prose:** replace the raw JSON profile dump fed to the LLM with a compact prose block — more natural context, better performance on smaller models.
- [ ] **Prompt iteration:** review and tighten `generate_tailoring` system prompt; consider few-shot examples for profile extraction.
- [ ] **LLM response validation + retry:** after each `llm_parse` call, assert that the response meets minimum content expectations before committing the result. Retry the full LLM request (up to 2 additional attempts) on validation failure before falling back. Validation rules to implement per call site:
  - **Chunk matching (`chunk_matcher.py`):** for each `ChunkMatchResult` with `score >= 1`, assert `advocacy_blurb` is non-null and non-empty. A batch where all scored chunks lack advocacy blurbs should be treated as a failed response and retried — this is the known failure mode where the LLM silently omits advocacy statements entirely.
  - **Tailoring generation (`tailoring_generator.py`):** assert output is non-empty and exceeds a minimum character threshold (e.g., 200 chars).
  - **Profile extraction (`profile_extractor.py`):** assert `summary` is non-empty and `work_experience` list is non-empty (or absent from resume — distinguish "no work history" from "extraction failure").
  - **Requirement matching (`requirement_matcher.py`):** assert at least one `RequirementMatch` result is returned.
  - Implement as a shared `llm_parse_with_retry(client, ..., validate_fn, max_retries=2)` wrapper around `llm_parse`, or as inline retry loops per call site — prefer the wrapper to avoid duplicating retry logic.

---

## Summary

| Day | Phase | Focus | Key output |
|-----|-------|-------|-----------|
| A1 ✅ | User | Streaming + perceived performance | SSE stage events, early redirect, phase timers, background generation with DB polling |
| A2 ✅ | User | Public profile page | `/u/{slug}` two-pane layout, experience rendering, `profile_public` opt-in, Settings toggle |
| A3 | User | Polish, cleanup, docs | Dead code removed, README, portfolio write-up |
| A4 ✅ | User | My Experience improvements | SSE phase list during processing, `EditableResumeProfile`, `PATCH /experience/profile`, stale tailoring banner |
| A5 | User | Miscellaneous UX | Directed improvements session by session |
| P1 | Platform | Security review | Prompt injection, auth/token abuse, SSRF, rate limiting, secrets audit |
| P2 | Platform | Testing + CI gate | pytest, Jest, GitHub Actions PR gate |
| P3 | Platform | Staging + pipeline hardening | Azure revision-based staging, token budget cap, URL caching, prompt iteration |

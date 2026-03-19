# Adjusted Sprint Plan — 6 Days to Ship-Ready

*Replaces the remaining days in `02-two-week-plan.md` (Days 8.5–12).*

Two phases, clear split:

- **Days A1–A3 — User-facing:** ship everything a real user or hiring manager would see or experience
- **Days A4–A6 — Platform:** harden the foundation once the product surface is stable

---

## Phase 1 — User-Facing (Days A1–A3)

### Day A1 — Streaming + Perceived Performance

**Goal:** The tailoring generation flow feels fast. Users start reading their document within seconds, not after a 60–90 second blank wait.

**Why first:** This is the single highest-leverage UX change available. Wall-clock time is hard to eliminate across four sequential LLM + scrape operations, but perceived time can drop dramatically. Every other user-facing feature lands better if the baseline generation experience doesn't feel broken.

#### 1. Stream the tailoring generation output
- [ ] Switch `generate_tailoring()` to `stream=True` on the OpenAI SDK call
- [ ] Change `POST /tailorings` and `POST /tailorings/{id}/regenerate` to return `StreamingResponse` using SSE (`text/event-stream`)
- [ ] Emit named stage events before generation begins:
  - `event: stage` / `data: scraping` — Playwright fetch starts
  - `event: stage` / `data: extracting` — job extraction LLM call starts
  - `event: stage` / `data: matching` — requirement matching starts
  - `event: stage` / `data: generating` — tailoring generation starts, then token stream follows
- [ ] Emit `data: <token>` events during generation, `data: [DONE]` on completion
- [ ] Persist completed output to DB only after `[DONE]`

#### 2. Frontend — live generation view
- [ ] Replace single `fetch` call in `NewTailoringForm` with `fetch` + `ReadableStream` consumer
- [ ] Stage indicator updates as each stage event arrives: "Fetching job posting… → Extracting requirements… → Matching to your profile… → Generating document…"
- [ ] Tokens append to local state as they arrive; render with `ReactMarkdown` updating live — user is reading within 2–3 seconds of generation starting
- [ ] `TailoringDetail` document view enters a live-typing state during regeneration rather than going opaque with a spinner

---

### Day A2 — Public Profile Page

**Goal:** Each user has a public portfolio URL they can drop in a bio or application.

**Why second:** The sharing infrastructure (`/t/{slug}`) is already live. The profile page is a lightweight addition that meaningfully expands the product's reach — one URL that surfaces all of a user's public work in context.

#### 1. Data model
- [ ] Add `username_slug` column to `users` table (unique, nullable)
  - Auto-generate on user creation from display name (`"Chara Dunbar"` → `"chara-dunbar"`); append number on collision
  - Migration: backfill existing users
- [ ] Alembic migration

#### 2. Backend
- [ ] `GET /users/public/{username_slug}` endpoint — no auth required
  - Returns: name, avatar URL (from Google), list of public tailorings (title, company, public_slug, created_at)
  - Only tailorings where `letter_public OR posting_public` are included

#### 3. Frontend
- [ ] `/u/[slug]` route — public, no auth, server-rendered
  - Displays: name, list of public tailorings as cards linking to `/t/{slug}`
  - Empty state if user has no public tailorings
- [ ] Settings: show the user their public profile URL with a copy button
- [ ] Consider: link from the public tailoring page (`/t/{slug}`) back to the author's profile

---

### Day A3 — Polish, Cleanup + Documentation

**Goal:** The product is clean, self-explanatory, and reference-ready.

**Why third:** Before locking in the platform (testing, staging, security), the surface needs to be stable. Dead code makes tests harder to write, and a clear README makes security review faster.

#### 1. Dead code removal
- [ ] Remove legacy backend endpoints: `/parse`, `/generate` (old match endpoint), `/job` (`job.py` — superseded by `tailorings.py`)
- [ ] Remove any dead frontend routes
- [ ] Audit `CLAUDE.md` — update file paths and routing table to reflect current state

#### 2. README
- [ ] Write `README.md` at repo root:
  - What Tailord is (one paragraph, direct)
  - Architecture overview (brief — frontend/backend/infra, key tech)
  - How to run locally (dev commands, env var setup)
  - Screenshots of the main UI states (dashboard, tailoring detail, public page)

#### 3. Portfolio write-up
- [ ] `planning/12-portfolio-writeup.md`:
  - The problem it solves
  - Key technical decisions and why (dual pipeline, streaming, Notion integration, chunk scoring)
  - What I'd do next

#### 4. Minor UX cleanup (opportunistic — only if clearly needed)
- [ ] Review error states: are all API errors surfaced to the user in plain language?
- [ ] Review empty states: dashboard with no tailorings, public profile with no public tailorings
- [ ] Check loading states are consistent across all data-fetching views

---

## Phase 2 — Platform (Days A4–A6)

### Day A4 — Security Review

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
- [ ] **Public slug enumeration:** verify no endpoint leaks a list of all public slugs
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

### Day A5 — Testing + CI Gate

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

### Day A6 — Staging Environment + Pipeline Hardening

**Goal:** A staging environment exists with near-zero idle cost. Remaining pipeline robustness gaps are closed.

#### Staging — Azure Container Apps Revisions
- [ ] Create a `staging` revision alongside `prod` within the same Container App
  - `staging`: min replicas = 0, max = 1 — scales to zero when not in use (zero idle cost)
  - `prod`: min replicas = 1 (always on)
  - `staging` receives 0% external traffic but is accessible at its revision-specific URL
- [ ] Deployment workflow update (`.github/workflows/deploy-azure.yml`):
  - On merge to `main`: deploy image → activate `staging` revision → smoke test (`/health` 200) → promote to `prod`
  - On manual trigger or tag: deploy directly to `prod`
- [ ] Staging database: use same DB with clearly-labelled staging data (Option C from Day 12 notes) — simplest for a solo project; revisit if data bleed becomes a concern
- [ ] Cloudflare: route `staging.tailord.app` → staging revision FQDN via proxied CNAME
- [ ] `ENVIRONMENT=staging` env var for more verbose logging in staging

#### Pipeline Hardening (remaining from Day 8.5)
- [ ] **Token budget cap:** `truncate_to_tokens(text, max_tokens)` helper (tiktoken) — apply to scraped job markdown before any LLM prompt. Prevents runaway costs and context length errors on unusually long postings.
- [ ] **Job URL caching:** skip Playwright scrape + job extraction LLM for recently-seen URLs (< 7 days); rerun all other LLM steps fresh. Implement once extraction quality feels stable enough to trust cached output.
- [ ] **Profile formatting as compact prose:** replace the raw JSON profile dump fed to the LLM with a compact prose block — more natural context, better performance on smaller models.
- [ ] **Prompt iteration:** review and tighten `generate_tailoring` system prompt; consider few-shot examples for profile extraction.

---

## Summary

| Day | Phase | Focus | Key output |
|-----|-------|-------|-----------|
| A1 | User | Streaming + perceived performance | SSE generation stream, stage progress events, live typing view |
| A2 | User | Public profile page | `/u/{slug}`, `username_slug` on users, Settings profile URL |
| A3 | User | Polish, cleanup, docs | Dead code removed, README, portfolio write-up |
| A4 | Platform | Security review | Prompt injection, auth/token abuse, SSRF, rate limiting, secrets audit |
| A5 | Platform | Testing + CI gate | pytest, Jest, GitHub Actions PR gate |
| A6 | Platform | Staging + pipeline hardening | Azure revision-based staging, token budget cap, URL caching, prompt iteration |

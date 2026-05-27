# Remaining Work — Reorganized 2026-05-24

*Aggregated from: `24-sprint-plan-20260510-20260517.md`, `30-frontend-refactoring-plan.md`, `25-observability-strategy.md`, `28-conversational-experience-agent.md`, `18-chunk-hardening.md`, `10-sprint-plan-20260421-20260425.md`, `11-chunk-driven-platform.md`, `03-sprint-plan-20260410-20260419.md`, `04-github-experience-feature.md`, `01-remaining-work-dump.md` (prior dump). Prior planning archived to `planning/archive_20260524/`.*

---

## Epic 1 — LLM Quality & Evaluation
**Vision:** Make matching quality deterministic, improvable, and cheap enough to iterate on with confidence.

### Feature 1.1 — Evidence Extraction Architecture (Two-Phase)
- `[ ]` Phase 1: single LLM call over candidate profile extracts flat list of explicit, atomic evidence claims ("Has Kubernetes experience", "No mention of Terraform"); Phase 2: scoring calls match requirements against evidence list, not raw profile. Structurally prevents inferred claims; evidence list is auditable. **Prerequisite: eval pipeline ✓**

### Feature 1.2 — Pre-Filtering and Signal Reduction
- `[ ]` Section pre-filtering — classify sections as evaluable/non-evaluable before chunk enrichment; skip "What We Offer", "Benefits", "About Us", "Compensation" etc.; eliminates false Gap scores for company perks at zero LLM cost
- `[ ]` Candidate fact sheet indexing pass — single LLM call before scoring produces compact structured "candidate fact sheet" from raw profile; all chunk scoring uses fact sheet instead of full profile; reduces context per scoring call; fact sheet cacheable across tailorings

### Feature 1.3 — Scoring Reliability
- `[ ]` Targeted self-verification on Gap scores — for chunks scored 0 on items likely to match (YOE requirements, named technologies, education), run a second focused verification call: "Does the candidate meet this? yes/no + one sentence reason"; small context, binary output, significantly reduces false gaps
- `[ ]` Prompt iteration — systematically review and tighten `generate_tailoring` system prompt; add few-shot examples to profile extraction prompt; neither reviewed since early iterations

### Feature 1.4 — Eval Infrastructure Completion
- `[~]` `make eval` in CI — eval runner is manual; deferred until targeting a hosted model (local LLM non-determinism makes CI assertions unreliable)
- `[~]` Admin "Matching Quality" observability card in admin panel — deferred; needs sufficient data volume in `tailoring_debug_logs` first
- `[~]` Gap detection retrospective — fixture 04 N/A→GAP edge case; `should_render` filter mitigates production impact; low priority

### Feature 1.5 — Tailoring Review Mode & Iteration Queue
**Context:** The smoke test (Feature 1.6) surfaces quality issues but provides no fast path to fixing them. Without structured tooling, the iteration loop is: notice a bad output → manually inspect → guess at a prompt fix → re-run → hope nothing regressed. This feature closes that loop — flag issues with context, queue them for iteration, validate fixes against the full corpus.

**Admin Review Mode (local only)**
- `[ ]` Per-tailoring pipeline step inspector in the admin panel — replay each stage of a tailoring: raw scraped content → job chunk extraction → candidate evidence list → per-chunk scores → final generation. Each step shows its input, output, and the model/prompt used. Uses `TailoringDebugLog` as the backing store — this is the feature that actually populates it.
- `[ ]` Step-level diff view — when a tailoring is re-run after a prompt change, show before/after output side-by-side for each pipeline step. Makes regressions visible immediately rather than requiring manual comparison.
- `[ ]` "Review mode" navigation — in the admin panel, a dedicated view that pages through flagged tailorings one at a time (or tailorings from the smoke test corpus). Keyboard shortcuts to flag, approve, or skip. Designed for rapid review sessions, not incidental one-off inspection.

**Flag Mechanism**
- `[ ]` `TailoringFlag` model — `tailoring_id` (FK), `scope` (`whole_tailoring | pipeline_step | chunk`), `step_name` (nullable — e.g. `"scrape"`, `"chunk_extraction"`, `"scoring"`, `"generation"`), `chunk_id` (nullable FK), `flag_type` (enum — see below), `notes` (free text, nullable), `status` (`open | in_progress | resolved | wont_fix`), `created_at`, `resolved_at`. Alembic migration.
- `[ ]` Flag type enum — structured categories that map to specific pipeline components: `webpage_noise_not_removed`, `item_misclassified_as_requirement`, `requirement_missed`, `score_incorrect` (STRONG/PARTIAL/Gap wrong), `hallucinated_claim`, `letter_missing_context` (wrong company/role/title), `extraction_incomplete`, `other`. New types can be added; the enum is a hint for prioritization not a constraint.
- `[ ]` Flag UI — a "Flag" button on tailoring detail (admin only) and on individual chunk/score rows in the admin debug view. Opens a small popover: flag type dropdown + optional notes field. One click for the common case, notes optional. Flags attach at the appropriate scope automatically (chunk-level flag from a chunk row, step-level flag from a step inspector).

**Iteration Queue**
- `[ ]` Iteration queue view in admin panel — lists all `open` and `in_progress` flags grouped by `flag_type`, with count per type. Shows which pipeline component has the most outstanding issues at a glance. Clicking a flag type shows the associated tailorings/steps.
- `[ ]` Queue-driven iteration workflow for Claude — the iteration queue is the input to prompt/pipeline work. A Claude Code session starts by reading the open flags, groups them by root cause (e.g. 12 `webpage_noise_not_removed` flags → scraper or pre-processing issue), proposes a fix, then re-runs the affected tailorings and marks flags `resolved` or `wont_fix`. The smoke test corpus (Feature 1.6) serves as the regression set — pass rate must not drop after a fix.
- `[ ]` Flag resolution — when a fix is verified, flags are marked `resolved` with a `resolved_at` timestamp. If a fix causes a regression elsewhere, new flags are opened. No flag is silently dropped; the queue grows and shrinks explicitly.
- `[ ]` Export iteration queue as markdown — `GET /admin/flags/export?format=md` returns a Claude-readable summary of all open flags with tailoring IDs, flag types, and notes. Intended to be pasted into a Claude Code session as the starting context for an iteration pass.

### Feature 1.6 — Pre-Launch Tailoring Quality Gate
**Context:** Tailorings are the primary output artifact and the centrepiece of conversion — especially for free-tier users with a limited number of generations (e.g. 2 free tailorings). A bad first Tailoring doesn't just lose a paid conversion; it destroys trust in the platform. The gate for public launch must be a large-scale smoke test across the breadth of job postings real users will bring.

- `[ ]` Build a smoke test corpus of 200+ job postings spanning the dev/software engineering domain — include: senior IC roles (SWE, SRE, platform, ML, data), engineering management, DevOps/infra, product-adjacent roles (TPM, solutions engineer), and a sample of adjacent non-dev roles (product manager, data analyst). Source from Greenhouse, Lever, Workday, LinkedIn, and direct company careers pages to cover ATS scraping diversity. Store as fixtures in `backend/tests/fixtures/jobs/`.
- `[ ]` Automated quality scoring pass over the corpus — for each fixture job + a representative synthetic candidate profile, generate a Tailoring and score it across: (a) no generation errors or timeouts, (b) STRONG/PARTIAL/Gap ratio is within expected range (no all-Gap or all-STRONG outputs), (c) generated letter references the job role and company correctly, (d) no hallucinated claims (requires evidence extraction from Feature 1.1). Pass rate threshold: 95% before public launch.
- `[ ]` Scraper coverage check — separately track what fraction of the 200+ URLs the Playwright/Firecrawl scraper successfully extracts from. A Tailoring can't be good if the job content wasn't scraped. Target: 90%+ successful extractions across ATS types. Failures should be categorized (timeout, JS-blocked, empty content) to prioritize scraper fixes.
- `[ ]` Treat this as a **launch gate, not a CI gate** — the corpus run is manual/scheduled, not per-commit. Run it: (1) before opening registration to the public, (2) before enabling paid plans, (3) after any significant prompt or pipeline change. Document the last run date and pass rate in `planning/launch-readiness.md`.
- `[ ]` Create `planning/launch-readiness.md` — checklist of conditions that must be true before public launch: smoke test pass rate, scraper coverage, free tier limits defined, payment infrastructure live, privacy policy published, feedback mechanism in place. Single source of truth for "are we ready?"

---

## Epic 2 — Experience Capture
**Vision:** Lower the activation energy for logging experience to near zero, so Tailord becomes a working memory tool candidates reach for throughout their career, not just at job-search time.

### Feature 2.1 — Quick Log (Phase 1)
- `[ ]` Quick Log UI on `/dashboard/experience`: textarea ("What did you build or ship?") + confirmation flow; extend `ParsedClaims` with `suggested_group_key: str | None` and `needs_attribution: bool`; attribution inferred from text signals ("at Acme Corp" → `group_key = "Acme Corp"`); Review state shows editable claim list + group_key field pre-filled; Confirm → `POST /experience/user-input/chunks`

### Feature 2.2 — Conversational Experience Agent (Phase 2)
- `[ ]` `ConversationThread` + `ConversationMessage` DB models + Alembic migration; one thread per user; last 15 messages as LLM context; `pending_action` JSON on assistant messages for confirmation pattern
- `[ ]` `POST /chat` endpoint: `IntentClassification` LLM call (add_experience / create_tailoring / query / confirmation / rejection / unclear); `add_experience` handler wired to existing parse + chunk endpoints; rate limit via `LlmTriggerLog` (60 messages/hour per user)
- `[ ]` Frontend chat panel: floating button → slide-out overlay accessible on all dashboard pages; optimistic message display; thread ID in localStorage; typing indicator
- `[ ]` `create_tailoring` intent handler: extract job URL → kick off tailoring pipeline as `BackgroundTask` → return immediately → write follow-up `ConversationMessage` when `generation_status = "ready"`; frontend polls for new messages
- `[ ]` `query` intent handler: profile Q&A using formatted profile snapshot as LLM context; no tool calls needed; answers "what's my strongest skill for backend roles?", "do I have any ML experience?"
- `[ ]` Attribution clarification loop (two-turn max): agent asks for employer/project when no attribution inferred; claims saved with `group_key = null` if user skips

### Feature 2.4 — File and Image Attachments for Claims
- `[ ]` Allow users to attach images, screenshots, or files to individual experience claims as supporting evidence — e.g. a screenshot of a Slack message, a performance review PDF, a design artifact. Attachments are stored in blob storage and linked via `source_urls` on the chunk. Rendered as expandable evidence links in the claim detail view and on the public tailoring/profile page. Not sent to the LLM — evidence only.
- `[ ]` Attachment upload endpoint: `POST /experience/chunks/{id}/attachments` → presigned PUT URL → client uploads directly to blob storage → `PATCH /experience/chunks/{id}` to append URL to `source_urls`. Mirror the existing resume upload pattern.
- `[ ]` Attachment display in chunk UI: collapsed by default, expandable "View evidence" toggle showing thumbnail or file icon + label.

### Feature 2.5 — Multiple Output Content Types
- `[ ]` Tailord generates Tailorings today (job application documents). The same experience repository should support additional output types: performance review self-assessments, interview story prep (STAR format), resume bullet generation, LinkedIn summary drafts. Design a `GenerationTarget` abstraction so the generation pipeline accepts a target type alongside the job context. Prerequisite: stable experience chunk model.
- `[ ]` UI surface for on-demand generation: from the dashboard, allow "Generate from experience" with a type selector (Tailoring, Performance Review, Interview Stories, Resume Bullets). Each type has its own prompt template and output format.

### Feature 2.3 — Experience Chunk Correctness
- `[ ]` Position ordering for user_input chunks — new chunks should set `position = max(position for all source_types) + 1`; currently resets to 0
- `[ ]` Embed-before-re-enrich ordering — gap response endpoint must embed synchronously (not background task) before calling `re_enrich_single_chunk`; otherwise new chunk has no vector and cannot be retrieved in top-K
- `[ ]` Gap response deduplication signal — after user answers a gap and regenerates, gap question may not reappear (requirement now PARTIAL/STRONG); UI should explain "this requirement was previously a gap but your added experience resolved it" rather than silently disappearing

---

## Epic 3 — Tailoring & Generation
**Vision:** The tailoring workbench is the user's primary artifact — fully editable, shareable, and progressively enriched over time.

### Feature 3.1 — Editor Mode Polish
- `[~]` Reorder chunks within a group — `position` field is in PATCH contract and save loop, but no drag/arrow UI built; deferred
- `[~]` Merge chunks — `POST /tailorings/{id}/chunks/merge` endpoint done; no selection UI in `ChunkItem`; deferred
- `[~]` Letter edit surface — edit controls for the generated letter (rephrase, tone); deferred out of scope

### Feature 3.2 — Gap Enrichment UX
- `[~]` bfcache/pageShowKey in `TailoringDetail.tsx` — attempted, reverted; deferred to avoid bfcache edge cases

### Feature 3.3 — Integrations
- `[ ]` Notion database export mode — export to a Notion database (not just page); creates row with company, role, date, job URL as properties; optional toggle after page export is stable
- `[~]` Notion public integration review submission — deferred; submit once screenshots ready and usage justifies unlocking beyond 10 workspaces

### Feature 3.4 — Tailoring Archiving
- `[ ]` Archive state on `Tailoring` — `archived_at` timestamp column (Alembic migration); archived tailorings are hidden from the default dashboard list but retrievable via `?include_archived=true`
- `[ ]` Manual archive action — archive/unarchive button on tailoring list item and tailoring detail header; confirm dialog for archive
- `[ ]` Smart archive suggestions on dashboard home — surface a "Clean up" notification tray when the user has tailorings for jobs that appear stale (no activity in 30+ days, or job URL returns 404). One-click bulk archive. Home screen should be actionable, not just a list.
- `[ ]` Archived tailorings view — accessible via sidebar toggle or `/dashboard?view=archived`; soft-delete, not permanent; user can restore at any time

---

## Epic 4 — Frontend UX
**Vision:** Every surface should give users a clear picture of what the platform knows about them and what actions are available — no dead ends, no empty confusion.

### Feature 4.1 — Experience Page
- `[ ]` My Experience: always-visible section shells — render all experience section shells (Resume, GitHub, Additional Experience, Inferred Profile) with empty states and descriptions even when unpopulated; users understand the full surface area on first page scan
- `[ ]` Experience claims table view — the current source-as-section layout does not scale as claims accumulate. Redesign as a filterable table/list where `source_type` is a column (not a section header), with view options: grouped by `group_key` (employer/project) or flat by date. Nesting should be preserved in the grouped view — sub-rows under each employer/project group. Source, date range, and status (pending/approved) are visible at a glance.
- `[ ]` Experience claims filtering — filter by source (`resume`, `github`, `user_input`, etc.), date range, status (`pending`, `approved`, `archived`), and group/employer. Search within claim text. Prerequisite: table view above.
- `[ ]` Copy button on experience claims — one-click copy of claim text to clipboard; rendered as an icon button on hover in the claim row/card

### Feature 4.2 — LinkedIn URL Fix
- `[ ]` LinkedIn URL missing protocol — normalize `authorLinkedin` in `CandidateFooter` with `startsWith('http') ? url : 'https://${url}'`; strip protocol/www at extraction in `profile_extractor.py` so values stored consistently; always prepend `https://` at render

### Feature 4.3 — Mobile & Accessibility
- `[ ]` Mobile layout — tailoring detail header buttons (View Posting / Copy / Regenerate / Export to Notion) need a dropdown or different layout at small screens
- `[ ]` Accessibility audit — add `aria-label` on icon-only buttons (copy, delete), `role="alert"` on error states, keyboard navigation through sidebar tailoring list

### Feature 4.4 — Design System
- `[~]` `btn-primary-*` design token — CSS vars + `@theme inline` exposure; consolidate raw `primaryBtn` string across 6 files; `MintButton` component already extracted as prerequisite; deferred
- `[~]` `btn-primary-*` token not added to `CLAUDE.md` token table — depends on token work above; deferred

### Feature 4.5 — Component Refactoring
- `[~]` `UserInputSection.tsx` — extract from `ExperienceManager`; blocked by tight coupling to parsing state; left for future pass
- `[~]` `GET /jobs/{job_id}/chunks` endpoint — deferred; `GET /tailorings/{id}/chunks` already serves this data
- `[~]` Remove `extracted_profile` / `extracted_job` from API responses — still consumed by tailoring generator internally; deferred

### Feature 4.6 — Onboarding & Getting Started
- `[ ]` Getting started progress bar on dashboard home — task checklist for new users: (1) Add your experience, (2) Create your first Tailoring, (3) Share a Tailoring. Each step links to the relevant surface. Dismissed once all three are complete or the user explicitly dismisses it. Makes the home screen actionable on first visit.
- `[ ]` Empty state copy throughout dashboard — when tailoring list is empty, show an actionable prompt ("Create your first tailoring — paste a job URL to get started") rather than a blank surface

### Feature 4.7 — Usage Visibility
- `[ ]` Usage summary visible to the user — show at all times (sidebar or settings): tailorings generated (total + this month), experience claims stored, integrations connected. Contextualizes platform value and sets expectations around any future usage limits.
- `[ ]` Usage displayed in account settings page alongside plan status — free / premium tier indicator, limits remaining if applicable

### Feature 4.8 — User Feedback
- `[ ]` In-app feedback mechanism — a persistent, low-friction way for users to submit feedback (bug report, feature request, general comment). Options: floating "?" button → short textarea overlay, or a dedicated `/dashboard/feedback` route. Feedback stored in DB or forwarded via webhook (e.g. to a Discord channel or email). Design the data model before building.

### Feature 4.9 — Resources & Documentation
- `[ ]` Resources / documentation section within the app — `/dashboard/resources` or a Help link in the sidebar linking to articles explaining: how GitHub integration works and what it extracts, how Tailorings are generated, what experience claims are and how to get the most out of them, privacy model (what data is stored, how to export/delete). Can be static MDX pages or an external docs site. Reduces support load and builds user trust.

### Feature 4.10 — Demo Video
- `[ ]` Product demo video — short walkthrough showing the core flow: add experience → create a Tailoring → review the fit analysis → share. To be embedded on the homepage and optionally within the app onboarding. Record after UI is stable enough not to require frequent updates.

### Feature 4.11 — Homepage
- `[ ]` Homepage revamp — full product homepage that communicates the value proposition clearly, showcases the UI, and converts visitors. Existing items below are components of this; treat as a single design pass once the product surface is stable enough to screenshot.
- `[ ]` Homepage ProductPreview — replace stylized mockup with real screenshot of Fit Analysis view showing STRONG/PARTIAL/Gap scoring; deferred until UI is stable
- `[ ]` Homepage social proof section — "X tailorings generated", "X job requirements matched"; testimonials with concrete outcomes; blocked on real usage numbers
- `[ ]` Interactive homepage demo — visitor pastes job URL → preview analysis without sign-up; blocked on guest/anonymous analysis flow; Day P4+ feature

---

## Epic 5 — Platform Hardening
**Vision:** The platform should be observable, secure, and instrumented enough that issues surface before users report them.

### Feature 5.1 — Observability
- `[ ]` Job scrape failure spike alert — `azurerm_monitor_scheduled_query_rules_alert_v2` in `monitoring.tf`; KQL query over `ContainerAppConsoleLogs_CL` counting `playwright_scrape_failed`, `playwright_timeout`, `job_content_invalid` in 15-min window; fire when count > 5
- `[ ]` Observability standards Claude hook — extend `.claude/hooks/post-edit.py` to warn (advisory, non-blocking) when backend edits add: LLM call without OTel span; FastAPI endpoint without `require_api_key` / `get_current_user`; `logging.getLogger` instead of `structlog.get_logger`

### Feature 5.2 — Testing
- `[ ]` Backend test coverage to 80%+ — currently ~49%; remaining gap: SSE streaming, background tasks, Notion export, experience endpoints; requires additional mocking strategies
- `[~]` Frontend API route tests with next-test-api-route-handler — routes are thin proxies; revisit if routes gain meaningful logic; deferred

### Feature 5.4 — Data Protection
- `[ ]` Tier 1 baseline (Startup Standard): verify Transparent Data Encryption (TDE) is active on Azure PostgreSQL Flexible Server (enabled by default on Azure — confirm in Terraform config); enforce RBAC so only the backend Container App identity has DB access; document the current posture in `infra/providers/azure/SECURITY.md`.
- `[ ]` Tier 2 roadmap (Mid-Market Standard): field-level / application-layer encryption (ALE) for highest-sensitivity user data — specifically `raw_resume_text`, `extracted_profile`, and any PII fields (`email`, `name`) stored in the `users` table. Design the key management approach (Azure Key Vault + envelope encryption) before implementing. Deferred until compliance requirements or enterprise customer demand.

### Feature 5.3 — Infrastructure
- `[ ]` GitHub App Terraform wiring — add `github_app_id_prod/staging`, `github_app_installation_id_prod/staging` as variables; `data "azurerm_key_vault_secret"` sources for private key secrets; wire `GITHUB_APP_ID`, `GITHUB_APP_INSTALLATION_ID`, `GITHUB_APP_PRIVATE_KEY` into backend Container Apps (prod + staging); then `az keyvault secret set` manual step for `.pem` files
- `[ ]` Portfolio write-up — `planning/12-portfolio-writeup.md`: problem Tailord solves, key technical decisions (dual pipeline, streaming, chunk scoring, Notion), what I'd do next; for job conversations
- `[ ]` SARIF-based CVE monitoring — Trivy SARIF upload step in CI (`format: sarif`, upload via `codeql-action/upload-sarif`); free on public repos; tracks CVEs across runs; do when repo goes public
- `[~]` VNet integration for PostgreSQL — security debt: public endpoint + `0.0.0.0/0.0.0.0` firewall; fix is destructive (recreate Container App Environments); +$10–15/month; deferred until compliance requirement
- `[ ]` Separate Tailord Staging Google OAuth client — create when there is a team with independently controlled staging vs prod access
- `[ ]` Cloudflare API token — 1Password CLI injection: `op run -- terraform apply`; same pattern for `TF_VAR_db_password`; no urgency while running from local machine

---

## Epic 6 — Infra & Observability
**Vision:** Instrument everything that matters; keep infra reproducible and auditable.

*(Observability items in Epic 5.1 above. Infra items in Epic 5.3 above.)*

---

## Epic 7 — Developer Experience
**Vision:** Claude Code sessions should be faster, catch errors earlier, and reduce context-switching for common tasks.

### Feature 7.1 — Claude Code Workflow
- `[ ]` Subagent definitions — `.claude/agents/` directory with `backend.md` (FastAPI/SQLAlchemy/LLM expert), `frontend.md` (Next.js/React/Tailwind), `reviewer.md` (security + correctness review, read-only, reports Auth bypass/SQLi/N+1 grouped by severity)
- `[ ]` GitHub MCP server — configure in project-level `.mcp.json` for PR creation, issue viewing, CI status, PR comment reading without copy-pasting
- `[ ]` PostgreSQL MCP — configure for direct DB access to debug issues or verify migrations; credentials in personal `~/.claude.json` only, never in `.mcp.json`

---

## Epic 8 — Platform Architecture & Integration Model
**Vision:** The core Tailord platform is an industry-agnostic claims ledger. Developer-specific ingestion logic (GitHub enrichment, codebase scanning, PR extraction) lives in an integration spoke that could be joined by Audio, Trades, Design, or any other vertical without touching the core schema.

### Feature 8.1 — Platform/Integration Boundary
- `[ ]` Platform/Integration boundary audit — review `ExperienceChunk`, FastAPI routes, and API contracts for dev-specific vocabulary baked into the core platform vs. properly isolated in integration code. Document what should move and when.
- `[ ]` Universal atomic claims schema — extend `ExperienceChunk` (or introduce a `Claim` model) to support: `status` (pending/approved/archived), `pillar` (competency category), `provenance_url` + `provenance_label` (external link to source of truth), and `industry_context` in metadata. Covers Alembic migration + Pydantic schema + API contract.

### Feature 8.2 — Claim Approval Workflow
- `[ ]` `status` enum on `ExperienceChunk` — `pending / approved / archived` (Alembic migration). Claims from automated integrations start as `pending`; only `approved` claims feed into tailoring generation, chunk scoring, and profile snapshots.
- `[ ]` Claim deduplication — before inserting new ExperienceChunks from any integration, run embedding cosine similarity check (≥0.92 = duplicate → skip or merge) against existing approved chunks for the same user. Required prerequisite before enabling GitHub silent capture.
- `[ ]` Claim review / reconciliation UI — lightweight ledger: claim text | inferred pillar | provenance link (outbound, no in-app code viewer) | [Approve] [Edit] [Reject]. Pending claims surface on the Experience page or a dedicated "Review" tab.
- `[ ]` Digest notification system — background worker tracks pending claim count per user; sends a low-frequency weekly summary ("3 new experience claims from this week — review here"). Design schema and worker first; email (Resend) vs. in-app notification centre is a separate decision.

### Feature 8.3 — GitHub Silent Capture
- `[ ]` GitHub App webhook endpoint (`POST /integrations/github/webhook`) — receive `push` and `pull_request` (merged) events; verify payload signature; enqueue background job. Zero overhead on the developer's machine — all processing happens on Tailord's infrastructure.
- `[ ]` PR-description claim extraction — agent processes merged PR metadata (title, description, labels, linked issues) and synthesizes atomic `pending` ExperienceChunks. No raw diff parsing; human-readable PR descriptions are the signal source, consistent with multi-industry extensibility.

### Feature 8.4 — 6 Product Pillars Framework (Dev Integration)
- `[ ]` Define and document the 6 Product Pillars schema — finalize pillar names/boundaries (draft: Observability & Incident Response, Security/Identity/Trust, Reliability/Resilience/Performance, Developer Experience & Continuous Delivery, Architecture & Longevity, Usability & User Centricity). Map each pillar to: structural codebase signatures the scanner targets; competency keywords found in job descriptions. Store as reference doc for the GitHub enrichment agent prompt.
- `[ ]` Wire pillar classification into GitHub enrichment output — update `GitHubRepoEnrichment` LLM schema and prompt to output a `pillar` field per claim; add `pillar` key to `ExperienceChunk.chunk_metadata` for dev-integration-sourced claims.

### Feature 8.5 — TAILORD.md Artifact
- `[ ]` Design TAILORD.md spec — repo-level manifest auto-generated by agentic scan; claims organized by pillar with links to source directories/files. Two-artifact model: `TAILORD.md` (product-level, checked in, describes the system); `.tailord/claims.json` (personal, gitignored, maps the specific user's contributions). Design schema first.
- `[ ]` Build TAILORD.md for the Tailord repo itself — portfolio artifact + live demo of the feature before it's user-facing.
- `[ ]` Agentic TAILORD.md generation — background task: structural scan (directory layout, dependency manifests, CI config, observability setup) → draft `TAILORD.md` → user reviews/approves in dashboard; connects to the pending claims workflow.

### Feature 8.6 — Firecrawl
- `[ ]` Evaluate Firecrawl as alternative/supplement to current Playwright + BeautifulSoup scraper — purpose-built for SPA-to-markdown conversion; evaluate (a) hosted API (cost/reliability vs. current infra), (b) self-hosted open-source fork. Test against ATS-hosted postings (Greenhouse, Lever, Workday). Run against existing job scrape eval fixtures for quality comparison.
- `[ ]` Implement Firecrawl free tier — replace `backend/app/core/scraper.py` Playwright flow with Firecrawl hosted API (500 scrapes/month free tier) for initial page fetch; keep BeautifulSoup for content extraction. Validate against Greenhouse, Lever, Workday pages.

### Feature 8.7 — Auth & Onboarding
- `[ ]` [CONVERSATION TODO] Email infrastructure — evaluate free-tier transactional email providers (Resend, Postmark, SendGrid) for: magic link auth, weekly claim digest, account welcome. Decide on provider before building.
- `[ ]` [CONVERSATION TODO] Magic link login — add email/magic-link as second auth method alongside Google OAuth; lowers barrier for non-Google users.
- `[ ]` [CONVERSATION TODO] LinkedIn OAuth + profile import — LinkedIn login as alternative to Google; primary value is importing initial professional profile as bootstrap for experience claims before resume upload.

---

## Epic 9 — B2B / Platform North Stars
**Vision:** Tailord as infrastructure — invisible enrichment layer for job boards and ATS platforms; agent-friendly data surface.

### Feature 9.1 — Headless Enrichment API

- `[ ]` `POST /enrich` — job URL (or raw text) + user profile → chunks with scores, advocacy blurbs, fit summary; partner API key auth; synchronous or async job ID + poll/webhook; prerequisite: working B2C product with usage evidence

### Feature 9.2 — Agent-Friendly Surface
- `[ ]` OpenAPI schema cleanup — consistent response shapes (no ad-hoc dict returns), meaningful operation IDs, documented error codes; prerequisite for any B2B integration partner
- `[ ]` JSON endpoint for public tailoring/profile pages — `?format=json` or `Accept: application/json` on `/u/{slug}` and public tailoring URL; returns structured JSON readable by any HTTP-capable agent
- `[ ]` Webhooks for async enrichment events — `tailoring.ready`, `tailoring.enriched`, `experience.processed`; design event model alongside headless enrichment API

### Feature 9.3 — MCP Server
- `[ ]` MCP server for Tailord — resources: `tailord://experience`, `tailord://tailorings`, `tailord://tailoring/{id}`; tools: `generate_tailoring(job_url)`, `get_fit_analysis(tailoring_id)`, `export_to_notion(tailoring_id, view)`; start with read-only

### Feature 9.4 — Cross-Job Intelligence
- `[ ]` AI job search assistant features — cross-job queries on top of stored data: "which saved jobs best match my skills?", "what skills am I missing most often?", "draft interview questions for {company}"; no new architecture required

### Feature 9.5 — Public Profile Chat
- `[ ]` Public profile chat interface — recruiter/interviewer asks questions on `/u/{slug}`; answered from candidate's structured experience using Haiku-class model + SSE streaming; prerequisites: high-quality extracted profiles + hosted fast model + rate limiting on public endpoint; defer until static profile surface is mature

### Feature 9.6 — Interactive Tailoring Format
- `[ ]` Interactive tailoring format — alternate view re-rendering job posting as frame with candidate experience woven in; each requirement annotated inline with sourced evidence; useful during live interviews; prerequisite: mature static tailoring surface

### Feature 9.7 — Tailorings on Public Profile
- `[ ]` `show_on_profile` toggle per tailoring (distinct from `letter_public` / `posting_public`); candidates curate which tailorings appear on `/u/{slug}`; left sidebar placement preferred

### Feature 9.8 — Partnership
- `[ ]` Platform partnership pitch to Simplify / Teal / Ashby — approach one platform (Simplify recommended) with usage evidence: user count, output samples, API readiness; prerequisite: working B2C product with real users

---

## Epic 10 — Monetization
**Vision:** Sustainable platform with a free tier that demonstrates value and premium features that justify ongoing payment. Free users experience the core product fully; premium unlocks high-value integrations and usage expansion.

### Feature 10.1 — Tier Definition
*Full pricing model and open questions live in `planning/private/pricing-model.md` (gitignored). Summary here for planning purposes.*

**Three tiers:**
- **Free** — 2 resume uploads, GitHub light scan (2 repos, README + metadata only), 2 tailoring generations (no sharing), unlimited public profile page, 10 additional experience claims from any source
- **Capture** *(name TBD)* — continuous experience capture: unlimited claims, GitHub deep scan + silent capture (webhook), future integrations; no tailoring generation included; Tailoring packs purchasable as one-time add-ons from this tier
- **Premium** *(name TBD)* — everything in Capture plus high-limit/unlimited tailoring generation and sharing

**Tailoring packs:** one-time purchases available to Capture-tier users; include sharing; sized and priced to nudge conversion to Premium if bought repeatedly.

- `[ ]` Finalize tier names, Tailoring pack sizes/prices, and Premium generation limit — see `planning/private/pricing-model.md`
- `[ ]` Confirm per-user cost floor before setting prices — requires June cost tracking (see Feature 10.5)

### Feature 10.2 — Payment Infrastructure
- `[ ]` [CONVERSATION TODO] Select payment provider — Stripe is the default choice (subscriptions, customer portal, webhooks). Evaluate once tier definition is confirmed.
- `[ ]` Add `subscription_status` and `subscription_tier` to `User` model (Alembic migration) — `free / premium / trial`; `trial_ends_at` timestamp; set by Stripe webhook handler
- `[ ]` Stripe webhook endpoint (`POST /webhooks/stripe`) — handle `customer.subscription.created`, `customer.subscription.deleted`, `invoice.payment_failed`; update `User.subscription_status` accordingly
- `[ ]` Premium feature gate dependency — FastAPI dependency `require_premium()` analogous to `require_api_key()`; returns 402 with structured error if user is not on premium tier; apply to gated endpoints (GitHub integration, future connectors)
- `[ ]` Frontend premium gate — when a user hits a premium-gated feature, show an upgrade prompt (modal or inline) explaining what the feature does and linking to the upgrade flow; never a dead end

### Feature 10.3 — Free Trial
- `[ ]` Free trial flow — new users get a time-limited trial of premium features (e.g. 14 days) before payment is required; `trial_ends_at` set at registration; trial expiry shows a gentle conversion prompt, not a hard lock
- `[ ]` Trial expiry notification — in-app banner when trial is within 3 days of expiring; email notification on expiry (requires email infrastructure from Feature 8.7)

### Feature 10.4 — Billing UI
- `[ ]` Account settings billing section — current plan, next billing date, upgrade/downgrade button, cancel subscription. Prefer Stripe Customer Portal (hosted) over building a custom billing UI from scratch.
- `[ ]` Plan status visible in sidebar or top-level settings at all times — connects to Feature 4.7 (usage visibility)

### Feature 10.5 — Per-Operation Cost Tracking (June)
**Context:** Pricing cannot be set responsibly without knowing the per-user cost floor. June is a full-time iteration period running `gpt-5.4` in prod — the most expensive model, giving the upper bound. Track every LLM operation so costs can be extrapolated to a typical active user/month.

- `[ ]` Extend `LlmTriggerLog` with `input_tokens`, `output_tokens`, `cost_usd`, and `operation_type` columns (Alembic migration) — `operation_type` enum: `profile_extraction`, `github_enrichment`, `job_extraction`, `evidence_extraction`, `fact_sheet`, `requirement_scoring`, `tailoring_generation`, `gap_enrichment`, `chat_message`, `pr_claim_extraction`
- `[ ]` Populate token counts in all existing LLM call sites — `llm_client.py` wrapper should capture `usage` from the OpenAI response and write to `LlmTriggerLog`; `cost_usd` calculated at log time from a config-driven token price table (so price updates don't require code changes)
- `[ ]` Admin cost dashboard — aggregate view: cost per operation type (last 30 days), cost per tailoring (total pipeline cost averaged), estimated monthly cost per active user. Read from `LlmTriggerLog`. Used to validate pricing assumptions before launch.
- `[ ]` After June: run the same key operations with `gpt-5.4-mini` against eval fixtures; measure quality delta; identify which operations can drop to the smaller model without regression. Document findings in `planning/private/pricing-model.md`.

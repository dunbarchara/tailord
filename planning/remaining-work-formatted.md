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

---

## Epic 4 — Frontend UX
**Vision:** Every surface should give users a clear picture of what the platform knows about them and what actions are available — no dead ends, no empty confusion.

### Feature 4.1 — Experience Page
- `[ ]` My Experience: always-visible section shells — render all experience section shells (Resume, GitHub, Additional Experience, Inferred Profile) with empty states and descriptions even when unpopulated; users understand the full surface area on first page scan

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

### Feature 4.6 — Homepage
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

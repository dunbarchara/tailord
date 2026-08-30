# Remaining Work — Reorganized 2026-07-18

*Aggregated from: `33-sprint-plan-20260527.md`, `31-platform-integration-boundary.md`, `35-billing-data-model.md`, `41-github-silent-capture.md`, `42-sms-capture.md`, `remaining-work-dump.md` (prior dump, items cross-referenced). Prior planning archived to `planning/archive_20260718/`.*

---

## Epic 1 — Experience Capture

**Vision:** Build ambient, zero-friction capture surfaces that continuously enrich the candidate's experience ledger — turning merged PRs, text messages, and other signals into pending claims that feed into tailoring generation after user review.

### Feature 1.1 — GitHub Silent Capture: Webhook Backend (Phase 3)

*Prerequisite for Phase 4 — must ship before the install UX.*

- [ ] GitHub App registration — create App in GitHub console, configure permissions (`pull_requests:read`, `contents:read`, `metadata:read`), set webhook URL, generate private key
- [ ] `POST /integrations/github/webhook` — HMAC verification (`X-Hub-Signature-256`), event/bot/branch filtering, insert `capture_signals` row, `BackgroundTask` enqueue, 202 response
- [ ] User linking via `installation_id` on `ExperienceSource`
- [ ] Signal processor: fetch user's commits via GitHub API, assemble signal dict, LLM extraction call (`PRClaimExtractionResult`), dedup pass, insert `pending` claims
- [ ] GitHub App credentials wired into Key Vault + Container App env vars via Terraform
- [ ] Tests: webhook handler (HMAC, event filters, bot filter); extraction unit tests with fixture PR descriptions

### Feature 1.2 — GitHub Silent Capture: Installation UX (Phase 4)

- [ ] "Connect GitHub App" button on Sources page → GitHub App installation page
- [ ] Post-install callback route — stores `installation_id` in `ExperienceSource.config`, upserts `UserIntegration(provider="github")`
- [ ] Initial light scan after callback using installation token (replaces unauthenticated public API scan)
- [ ] Sources page connected state: GitHub login (`@username`), "Capture active" badge, Disconnect button
- [ ] Disconnect — removes `UserIntegration(provider="github")`, clears `installation_id` from `ExperienceSource.config`

### Feature 1.3 — Repo-to-Role Suggestion UX (Phase 4c)

*Data already computed (`suggested_parent_id` in `type_meta`) — this is purely surfacing it.*

- [ ] `PATCH /experience/groups/{id}` — accept `parent_id` to link repo group to role group
- [ ] `PATCH /experience/groups/{id}/dismiss-suggestion` (or fold into PATCH) — sets `type_meta.suggestion_dismissed = true`
- [ ] Frontend: read `type_meta.suggested_parent_id` + `suggestion_confidence == "high"`, render dismissable "Associate with [Role Name]?" chip on repo group cards
- [ ] Add `suggested_parent_name: str | None` to `type_meta` in `_store_suggestion` so frontend never needs a second lookup

### Feature 1.4 — SMS Capture: Phone Binding (Phase 1)

- [ ] Backend: `POST /integrations/sms/verify/start` — Twilio Verify send OTP
- [ ] Backend: `POST /integrations/sms/verify/confirm` — check OTP, upsert `UserIntegration(provider="sms")`
- [ ] Backend: `DELETE /integrations/sms` — disconnect binding
- [ ] Frontend API routes proxying the above
- [ ] Sources page: SMS card with Connect / Disconnect / masked phone number
- [ ] Env vars and Key Vault entries for Twilio credentials (`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_MESSAGING_SERVICE_SID`, `TWILIO_VERIFY_SERVICE_SID`)
- [ ] Tests: verify start/confirm happy path and failure cases

### Feature 1.5 — SMS Capture: Ingest + Extraction (Phases 2–3)

- [ ] `POST /integrations/sms/webhook` — Twilio signature verification, phone lookup, signal insert, 200 TwiML reply
- [ ] BackgroundTask stub (Phase 2 — signal inserted, not yet processed)
- [ ] Tests: webhook handler (valid sig, invalid sig 403, unbound number, signal row created)
- [ ] SMS extraction prompt + `SMSClaimExtractionResult` Pydantic schema
- [ ] Background processor: extract claims, dedup pass, insert `pending` claims, send outbound reply
- [ ] Skip/dedup reply variants
- [ ] Tests: extraction unit tests with fixture brain dumps

### Feature 1.6 — SMS Capture: Approval Commands (Phase 4)

- [ ] Command parser: `APPROVE ALL`, `APPROVE 1 2`, `REJECT`, `REJECT 1`, etc.
- [ ] Command handler: resolve pending claims from most recent signal, apply status transitions, send confirmation reply
- [ ] Edge cases: no pending claims, invalid indices, already-approved claims
- [ ] Tests: command parsing unit tests, transition integration tests

### Feature 1.7 — Experience Signal Layer (ExperienceSignal schema)

*Enables the `Surface → Signal → Claim` dedup pipeline. Schema work only in this feature — pipeline wiring deferred.*

- [ ] Add `ExperienceSignal` ORM model to `database.py` (fields: `id`, `user_id` FK, `surface_type`, `source_ref`, `claim_type`, `content`, `confidence`, `status`, `canonical_claim_id` FK, `group_id` FK, `extraction_metadata` JSONB, `created_at`, `updated_at`; indexes on `user_id`, `status`, `(user_id, surface_type)`, `canonical_claim_id`)
- [ ] Alembic migration for `experience_signals` table
- [ ] Add `supplementary` (JSONB nullable) to `experience_claims`
- [ ] Add `ownership` (varchar 20, default `"auto"`) to `experience_claims`
- [ ] Alembic migration for claim dedup columns (`supplementary`, `ownership`)
- [ ] Update `ExperienceClaim` ORM model with `supplementary`, `ownership`, and `signals` relationship (`lazy="select"`)
- [ ] Update `frontend/src/types/index.ts` — add `supplementary: Record<string, unknown> | null` and `ownership: 'auto' | 'locked'` to `ExperienceClaim`

### Feature 1.8 — Pillar Classification Framework

- [ ] Define and document 6 Product Pillars schema — finalize pillar names, structural signatures, competency keywords; store as reference doc used by enrichment agent prompts
- [ ] Wire `pillar` field into GitHub enrichment LLM schema and prompt (`GitHubRepoEnrichment.pillar`)
- [ ] Add `pillar` key standardization to `ExperienceClaim.chunk_metadata` for dev-integration-sourced claims

---

## Epic 2 — LLM Quality & Pipeline

**Vision:** Improve the accuracy, reliability, and cost-efficiency of LLM calls — better scoring, resilience under load, and structured evidence extraction.

### Feature 2.1 — LLM Resilience (429 backoff + concurrency cap)

- [ ] Catch `openai.RateLimitError` in `llm_parse_with_retry` separately from validation errors
- [ ] Exponential backoff with jitter: start 1s, double each attempt, ±25% jitter, cap 30s
- [ ] Separate `rate_limit_retries` budget (default 4), distinct from `max_retries`
- [ ] Log each backoff attempt as `llm_rate_limit_backoff` WARNING with attempt number and wait_ms
- [ ] Increment `LLM_RETRIES_TOTAL` with `reason="rate_limit"` label
- [ ] Add module-level asyncio `Semaphore` in `llm_utils.py` — `settings.llm_max_concurrent_requests` (default 16)
- [ ] Acquire semaphore in `llm_parse` and `llm_generate` before every LLM call
- [ ] Expose current concurrency level as Prometheus gauge `llm_inflight_requests`
- [ ] Write load script `scripts/stress_test_tailoring.py` — N concurrent `POST /tailorings`, record time + error rate
- [ ] Run at N = 1, 2, 5, 10, 25 — document throughput ceiling and P95 latency

### Feature 2.2 — Evidence Extraction Architecture

- [ ] Evidence extraction (two-phase) — Phase 1: single call extracts flat evidence claims from profile; Phase 2: scoring matches requirements against evidence list; prevents inferred claims
- [ ] Section pre-filtering — classify sections as evaluable/non-evaluable before chunk enrichment; skip "What We Offer", "Benefits", "About Us", "Compensation"
- [ ] Candidate fact sheet indexing pass — single LLM call before scoring produces compact fact sheet; all chunk scoring uses fact sheet instead of full profile
- [ ] Targeted self-verification on Gap scores — second focused call for chunks scoring 0 on YOE, named technologies, education: "Does the candidate meet this? yes/no + one sentence reason"
- [ ] Prompt iteration — systematically review `generate_tailoring` system prompt; add few-shot examples to profile extraction prompt

### Feature 2.3 — Chunk Hardening

- [ ] Gap response deduplication signal — when user regenerates after answering a gap, UI handles gracefully if requirement no longer appears ("this requirement was resolved by your added experience")
- [ ] Position ordering for user_input chunks — new chunks set `position = max(position) + 1`; currently resets to 0
- [ ] Embed-before-re-enrich ordering — gap response endpoint must embed synchronously before `re_enrich_single_chunk`

---

## Epic 3 — Platform Hardening

**Vision:** Establish the architecture boundaries, billing infrastructure, and data model that let the platform scale to paid tiers without accruing integration-specific coupling debt.

### Feature 3.1 — Platform/Integration Boundary (Phase 1)

- [ ] Alembic migration: add `pillar` (varchar 50 nullable) to `experience_claims`
- [ ] ORM model: add `pillar` field to `ExperienceClaim` in `database.py`
- [ ] `experience_chunker.py` — set `status='pending'` for GitHub chunk creation (automated capture sources)
- [ ] Filter `WHERE status = 'approved'` in `tailoring_generator.py` and `chunk_matcher.py`
- [ ] Add `pillar` to `ExperienceClaimResponse` Pydantic schema and PATCH body model in `experience.py`
- [ ] Add `pillar?: string` to `ExperienceClaim` TypeScript interface
- [ ] Remove hardcoded `"GitHub:"` prefix in `chunk_matcher.py` — read from `provenance_label` instead
- [ ] Add "Platform/Integration Boundary" section to `CLAUDE.md`

### Feature 3.2 — Billing Data Model

- [ ] Implement `user_subscriptions` table + Alembic migration
- [ ] Implement `user_entitlements` table + Alembic migration
- [ ] Implement `referrals` table + Alembic migration
- [ ] Write `entitlements.py` service with `get_effective_limits()` — single source of truth for tier + entitlement + usage math
- [ ] Wire Stripe webhook handler → upsert `user_subscriptions` on subscription lifecycle events
- [ ] Implement `/r/{code}` claim flow + activation trigger on tailoring `generation_status = "ready"`
- [ ] Decide: referral cap (5/account) — lifetime or annual reset?
- [ ] Decide: pack-purchased tailorings for Capture — include Notion export?
- [ ] Decide: Capture base tier — include Notion export?
- [ ] Decide: Premium tailoring limit — hard unlimited or soft cap with overage warning?

### Feature 3.3 — Backend Test Coverage

- [ ] Increase backend test coverage to 80%+ — currently ~49%; gap areas: SSE streaming, background tasks, Notion export, experience endpoints
- [~] Frontend API route tests (next-test-api-route-handler) — revisit if routes gain meaningful logic

---

## Epic 4 — Frontend UX

**Vision:** Eliminate friction points in the core experience flow and ensure the UI scales gracefully as the claims data model grows more complex.

### Feature 4.1 — Claims Data Layer Cleanup

- [ ] Centralize `flattenClaims` and `removeClaimFromResponse` into `experience-claim-utils.tsx` (currently duplicated in `ProfileChunkEditor` and `ExperienceManager`)
- [ ] Lift `/claims` fetch into `ExperienceManager`, pass `data: ExperienceClaimsResponse` as prop to `ProfileChunkEditor` — eliminates duplicate network request, gives both a consistent data view

### Feature 4.2 — My Experience UX Polish

- [ ] Always-visible section shells — render Resume, GitHub, Additional Experience, Inferred Profile shells with empty states so users understand the full surface area on first load
- [ ] LinkedIn URL missing protocol — normalize `authorLinkedin` in `CandidateFooter`: prepend `https://` at render, strip at extraction
- [ ] Mobile layout — tailoring detail header (View Posting / Copy / Regenerate / Export) needs dropdown or collapsed layout at small screens
- [ ] Accessibility audit — `aria-label` on icon-only buttons, `role="alert"` on error states, keyboard nav through sidebar tailoring list
- [~] Reorder chunks within a group — `position` field exists in PATCH contract, no drag/arrow UI built
- [~] Merge chunks — endpoint done, no selection UI in `ChunkItem`
- [~] Design edit surface for the generated letter

### Feature 4.3 — Repo Selector UX (43-repo-selector-ux.md)

*Design spec complete — implementation pending.*

- [ ] Tri-tier layout: Recommended (pinned + most-starred + most-recently-pushed) / All repos / Organizations placeholder
- [ ] High-density repo rows: name, public/private badge, language dot, stars, forks, last commit date
- [ ] Quick filters: [All] [Public] [Private] [Sources] [Forks]
- [ ] Global search bar (client-side, sticky)
- [ ] "Show only enabled" toggle
- [ ] Persist `stargazers_count`, `fork`, `pushed_at` in `source_data.repos` during scanner step

---

## Epic 5 — Infra & Observability

**Vision:** Harden the production deployment — close security gaps, automate alerting, and clean up credential management.

### Feature 5.1 — GitHub App Infra

- [ ] Terraform: add `github_app_id_prod/staging` and `github_app_installation_id_prod/staging` variables; `data "azurerm_key_vault_secret"` for private key; wire `GITHUB_APP_ID`, `GITHUB_APP_INSTALLATION_ID`, `GITHUB_APP_PRIVATE_KEY` into backend Container Apps (prod + staging)
- [ ] Manual step: `az keyvault secret set` for prod + staging private key PEM files; add App IDs to `terraform.tfvars`; `terraform apply`

### Feature 5.2 — Alerting

- [ ] Add `azurerm_monitor_scheduled_query_rules_alert_v2` in `monitoring.tf` for job scrape failure spikes — KQL over `ContainerAppConsoleLogs_CL`, count `playwright_scrape_failed`/`playwright_timeout`/`job_content_invalid` in 15-min window, fire when > 5
- [~] AMP OTLP endpoint path — verify in staging by checking Container App logs for export errors

### Feature 5.3 — Credential & Security Hygiene

- [ ] Cloudflare API token — 1Password CLI injection: `op run -- terraform apply` (same pattern for `TF_VAR_db_password`)
- [ ] Separate Tailord Staging Google OAuth client — currently sharing prod client
- [ ] SARIF-based CVE monitoring (when repo goes public) — Trivy SARIF upload to GitHub Security code scanning (free on public repos)
- [~] VNet integration for PostgreSQL — security debt (public endpoint + `0.0.0.0/0.0.0.0`); destructive to fix (+$10–15/month); deferred until compliance requirement

---

## Epic 6 — Auth & Onboarding

**Vision:** Lower the sign-up barrier and add email as a communication and auth channel.

### Feature 6.1 — Email Infrastructure

- [ ] Evaluate transactional email providers (Resend, Postmark, SendGrid) for: magic link auth, weekly claim digest, account welcome
- [ ] Magic link login — email/magic-link as second auth method alongside Google OAuth; lowers barrier for non-Google users
- [ ] LinkedIn OAuth + profile import — LinkedIn login as alternative to Google; primary value is importing work history + education as bootstrap for experience claims

### Feature 6.2 — Digest Notifications

- [ ] Digest notification system — low-frequency background worker counting pending claims per user; weekly summary: "You generated N new experience claims this week — review them here"; design schema + worker first; delivery channel (Resend, in-app) separate decision

---

## Epic 7 — Developer Experience

**Vision:** Automate the common patterns and make the codebase self-enforcing.

### Feature 7.1 — Claude Code Tooling

- [ ] Claude Code: Subagent definitions — `.claude/agents/` with `backend.md`, `frontend.md`, `reviewer.md` (security + correctness review, read-only)
- [ ] Claude Code: GitHub MCP — configure for PR creation, issue viewing, CI status, PR comments; project-level `.mcp.json`
- [ ] Claude Code: PostgreSQL MCP — direct DB access for debugging migrations; credentials in personal `~/.claude.json` only
- [ ] Observability standards hook — post-edit hook warns when backend adds LLM call without OTel span, FastAPI endpoint without `require_api_key`, or `logging.getLogger` instead of `structlog`

### Feature 7.2 — Documentation

- [ ] Portfolio write-up — `planning/12-portfolio-writeup.md`: problem, key technical decisions (dual pipeline, streaming, chunk scoring, Notion), what I'd do next

---

## Epic 8 — Conversational Experience Agent

**Vision:** A chat interface embedded in the dashboard that lets users add experience, create tailorings, and query their profile conversationally — modelled on the Claude Code "guided partner" pattern.**

### Feature 8.1 — Quick Log UI (Phase 1)

- [ ] Textarea + confirmation flow on `/dashboard/experience`
- [ ] Extend `ParsedClaims` with `suggested_group_key: str | None` and `needs_attribution: bool`; attribution inferred from text ("at Acme Corp" → `group_key`)
- [ ] Review state shows editable claim list + `group_key` field

### Feature 8.2 — Chat Backend (Phase 2)

- [ ] `ConversationThread` + `ConversationMessage` SQLAlchemy models + Alembic migration; one thread per user; last 15 messages as LLM context
- [ ] `POST /chat` endpoint: `IntentClassification` LLM call (`add_experience / create_tailoring / query / confirmation / rejection / unclear`); `add_experience` handler wired to existing parse + chunk endpoints
- [ ] `create_tailoring` intent: extract URL → kick off tailoring pipeline → follow-up message when `generation_status = "ready"` (frontend polls for new messages)
- [ ] `query` intent: profile Q&A using formatted profile as LLM context; no tool calls
- [ ] Attribution clarification loop (Phase 3): two-turn max; agent asks for employer/project when no attribution inferred; saves with `group_key = null` on skip

### Feature 8.3 — Chat Frontend (Phase 2)

- [ ] Floating button → slide-out overlay on all dashboard pages
- [ ] Optimistic message display; thread ID in localStorage

---

## Epic 9 — Product Features

**Vision:** Deepen the Tailord surface for candidates and recruiters, expanding from single-tailoring utility to a portfolio and intelligence platform.

### Feature 9.1 — Tailoring & Profile Surfaces

- [ ] Interactive tailoring format — alternate view rendering job posting as frame with candidate experience woven in inline per requirement
- [ ] Tailorings on public profile — `show_on_profile` toggle per tailoring (distinct from `letter_public`/`posting_public`)
- [ ] Notion database export mode — export to Notion database with company, role, date, job URL properties

### Feature 9.2 — Homepage

- [ ] Interactive homepage demo — visitor pastes job URL → preview analysis without sign-up (blocked on guest/anonymous analysis flow)
- [ ] Homepage social proof section — "X tailorings generated", testimonials with concrete outcomes (blocked on real usage data)
- [ ] Homepage `ProductPreview` — replace stylized mockup with real screenshot of Fit Analysis view
- [~] Notion public integration review submission — deferred; submit once screenshots ready and usage justifies > 10 workspaces

### Feature 9.3 — TAILORD.md Artifact

- [ ] Design TAILORD.md spec — repo-level manifest: `TAILORD.md` (product-level, public, checked in) + `.tailord/claims.json` (personal, gitignored)
- [ ] Build TAILORD.md for the Tailord repo itself — portfolio artifact and live demo before user-facing feature
- [ ] Agentic TAILORD.md generation — background task: structural scan (dirs, dependency manifests, CI config, observability) → draft manifest → user review in dashboard

---

## Epic 10 — North Star / Platform API

**Vision:** Establish Tailord as invisible infrastructure for the job application ecosystem — headless enrichment, MCP integration, and partner platform deals.**

- [ ] Headless enrichment API — `POST /enrich` with partner API key; async job ID + poll/webhook; prerequisite: working B2C product with usage evidence
- [ ] MCP server for Tailord — expose experience, tailoring, analysis as MCP tools and resources
- [ ] Public profile chat interface — recruiter/interviewer asks questions on `/u/{slug}`, answered from candidate's structured experience
- [ ] AI job search assistant — cross-job intelligence: "which saved jobs best match my skills?", "what skills am I missing most often?"
- [ ] Platform partnership pitch to Simplify / Teal / Ashby — one platform with usage evidence
- [ ] OpenAPI schema cleanup — consistent response shapes, meaningful operation IDs, documented error codes; prerequisite for B2B partners
- [ ] JSON endpoint for public tailoring/profile pages — `?format=json` or `Accept: application/json` on `/u/{slug}` and `/t/{slug}`
- [ ] Webhooks for async enrichment events — `tailoring.ready`, `tailoring.enriched`, `experience.processed`

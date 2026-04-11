# Remaining Work Dump

*Compiled 2026-04-10 from all files in `planning/archive_20260410/`. Every unimplemented work item, feature, north star, and idea captured in one place.*

*Format per item: `type`, `title`, `description`, and `source` file(s). Duplicates across files merged into single entries.*

---

## Tech Debt / Cleanup

**type:** Tech Debt
**title:** Remove legacy backend endpoints
**description:** Delete `/parse` (legacy scrape+parse), `/generate` (old one-paragraph match endpoint), and `/job` (`job.py` — superseded by `tailorings.py`). Keeping dead endpoints creates maintenance burden and confusion when reading the codebase.
**source:** `05-technical-debt-and-polish.md`, `11-adjusted-sprint-plan.md`

---

**type:** Tech Debt
**title:** Remove dead frontend routes
**description:** Audit and remove any frontend routes that are no longer wired to anything in the current product.
**source:** `11-adjusted-sprint-plan.md`

---

**type:** Tech Debt
**title:** Portfolio write-up
**description:** Create `planning/12-portfolio-writeup.md` covering: the problem Tailord solves, key technical decisions and why (dual pipeline, streaming, Notion integration, chunk scoring), and what I'd do next. For job application conversations.
**source:** `11-adjusted-sprint-plan.md`, `04-employment-strategy.md`

---

**type:** Tech Debt
**title:** Rate limit soft warning
**description:** Currently users hit a hard block at 10 LLM triggers/hour. Add a softer tier: warn at 8 triggers ("you're approaching your generation limit"), block at 10. More informative UX than a sudden 429.
**source:** `11-adjusted-sprint-plan.md`

---

**type:** Tech Debt
**title:** Accessibility audit
**description:** Missing `aria-label` on icon-only buttons (copy, delete). Missing `role="alert"` on error states. Keyboard navigation through sidebar tailoring list. Fast fixes, not blocking.
**source:** `05-technical-debt-and-polish.md`

---

**type:** Tech Debt
**title:** Mobile layout — tailoring detail header
**description:** The header with View Posting / Copy / Regenerate / Export to Notion buttons will need a dropdown or different layout at small screen sizes.
**source:** `05-technical-debt-and-polish.md`

---

## Known Bugs

**type:** Bug
**title:** Race condition: GitHub added while resume is processing
**description:** If a user adds GitHub mid-processing, the GitHub endpoint sets `status → "ready"` prematurely. The experience processor then finishes and overwrites `github_repos` with `None` (stale read-modify-write). Fix: (1) GitHub endpoint should not touch `status` if currently `"processing"`; (2) experience processor should update only its own columns (`extracted_profile`, `status`, `processed_at`) rather than saving the full record.
**source:** `11-adjusted-sprint-plan.md`

---

## Testing

**type:** Testing
**title:** Backend test coverage to 80%+
**description:** Currently 42% overall. `app/api/users.py` at 78%, `app/api/tailorings.py` at 39%. Remaining gap: SSE streaming, background tasks, Notion export API, experience endpoints. These require additional mocking strategies or integration harness work.
**source:** `11-adjusted-sprint-plan.md`

---

**type:** Testing
**title:** Frontend API route tests with next-test-api-route-handler
**description:** Deferred — API routes are thin proxies with no independent logic, so testing them mostly tests the mock. Revisit if routes gain meaningful logic.
**source:** `11-adjusted-sprint-plan.md`

---

## Admin

**type:** Feature
**title:** Internal admin page
**description:** `/admin` route in Next.js protected by a separate `ADMIN_KEY` env var (not user session). Three views: pending users list (name, email, sign-up date, avatar, one-click Approve), all users list (status badge, revoke access button). Backend: `GET /admin/users`, `POST /admin/users/{id}/approve`, `POST /admin/users/{id}/revoke` — protected by `ADMIN_KEY` header, separate from `X-API-Key`. Replaces `dev_approve.py` for staging and prod.
**source:** `11-adjusted-sprint-plan.md`

---

## Infrastructure / DevOps

**type:** Infra
**title:** Branch protection rule on main
**description:** GitHub UI setting (not a file change). Repo Settings → Branches → Add rule for `main`, check "Require status checks to pass" and select: `pre-commit`, `backend`, `frontend`, `infra`. Required before the CI gate is meaningful.
**source:** `11-adjusted-sprint-plan.md`

---

**type:** Infra
**title:** Complete staging environment bootstrap
**description:** Several manual steps remain from the infra refactor: (1) set up `staging-azure` GitHub environment with OIDC secrets matching `production-azure`; (2) run `terraform apply` with new variable set (`db_prod_password`, `db_staging_password`); (3) execute PostgreSQL user bootstrap SQL (BOOTSTRAP.md step 4); (4) bind TLS certs for `tailord.app` (CLI) and `staging.tailord.app` (portal); (5) restore Cloudflare CNAMEs to proxied after cert binding; (6) trigger first CI deploy to replace placeholder images with real app images.
**source:** `15-infra-improvements.md`

---

**type:** Infra
**title:** VNet integration for PostgreSQL
**description:** Security debt: PostgreSQL server has a public endpoint with `0.0.0.0/0.0.0.0` "allow Azure services" firewall rule. Proper fix: create VNet with delegated subnets, recreate Container App Environments with `infrastructure_subnet_id`, deploy PostgreSQL with `delegated_subnet_id` + `private_dns_zone_id`. Recreating Container App Environments is destructive (all apps must be recreated) and adds ~$10–15/month. Deferred — revisit before handling sensitive user data at volume or before any compliance requirement.
**source:** `11-adjusted-sprint-plan.md`, `15-infra-improvements.md`

---

**type:** Infra
**title:** Separate Tailord Staging Google OAuth client
**description:** Currently staging uses the prod Google OAuth client with `staging.tailord.app` added as an authorized origin/redirect. Create a separate client when there is a team with independently controlled staging vs prod access.
**source:** `11-adjusted-sprint-plan.md`

---

**type:** Infra
**title:** SARIF-based CVE monitoring (when repo goes public)
**description:** When the GitHub repo is made public: add a Trivy SARIF upload step to CI (`format: sarif`, `ignore-unfixed: false`). Upload via `github/codeql-action/upload-sarif` — results appear in Security → Code scanning tab. Tracks CVEs across runs, shows when status changes (affected → fixed), provides suppress-with-reason workflow for `will_not_fix` findings. Free on public repos. Closes the gap where the deploy gate silences unfixed CVEs but nothing tracks them.
**source:** `dependabot-workflow.md`, `11-adjusted-sprint-plan.md`

---

## Design

**type:** Design
**title:** text-link CSS variable
**description:** `--color-text-link` is not yet set to accent green. Inline text links throughout the dashboard should use the same emerald accent as active nav items and CTAs — consistent with Mintlify's sparse green application. One token change, affects all `<a>` tags that use `text-text-link`.
**source:** `15-mintlify-design-match.md`

---

**type:** Design
**title:** Homepage ProductPreview — real screenshot
**description:** The homepage `ProductPreview` section currently shows a stylized mockup. Once the Analysis tab design is stable (it is now), replace with a real screenshot of the Fit Analysis view showing Strong/Partial/Gap scoring. The Analysis tab's redesign was specifically done to make this possible. See `16-tailoring-detail-architecture.md` for the two-panel framing (Analysis left, enriched posting right).
**source:** `11-adjusted-sprint-plan.md`, `13-homepage-redesign.md`, `15-mintlify-design-match.md`

---

## LLM Pipeline

**type:** Pipeline
**title:** Evidence extraction architecture
**description:** Decompose chunk matching into two sequential phases instead of one combined call. Phase 1: one call over the candidate profile extracts a flat list of explicit, atomic evidence claims (e.g. "Has Kubernetes experience", "No mention of Terraform"). Phase 2: scoring calls match requirement chunks against the evidence list — not the raw profile. Benefits: structurally prevents inferred claims, smaller context per scoring call, evidence list is auditable as a standalone artifact. Validate against eval baseline before committing. See `18-scoring-reliability.md` for full tradeoff analysis. **Prerequisite: eval pipeline (Level 4).**
**source:** `11-adjusted-sprint-plan.md`, `18-scoring-reliability.md`

---

**type:** Pipeline
**title:** Section pre-filtering for non-evaluable chunks
**description:** A pre-filter pass before chunk enrichment — classify sections as evaluable or non-evaluable based on section header, skip enrichment entirely for non-evaluable sections. Zero LLM cost for "What We Offer", "Benefits", "About Us", "Our Culture", "Compensation", "Equal Opportunity", "Apply for this job" sections. Eliminates false Gap scores for company perks without prompt changes.
**source:** `07-model-selection-and-orchestration.md`

---

**type:** Pipeline
**title:** Candidate fact sheet indexing pass
**description:** A single LLM call before scoring begins that produces a compact structured "candidate fact sheet" from the raw profile — key skills with evidence, total YOE, education, notable projects. All subsequent chunk scoring calls use the fact sheet instead of the full raw profile. Benefits: dramatically reduces context size for scoring calls, concentrates profile summarisation into one high-quality call, fact sheet can be cached and reused across multiple tailorings for the same candidate.
**source:** `07-model-selection-and-orchestration.md`

---

**type:** Pipeline
**title:** Targeted self-verification on Gap scores
**description:** For chunks scored 0 (Gap) on items that seem likely to match — YOE requirements, named technologies, education — run a second focused verification call: "Does the candidate meet this? Respond yes/no with a one-sentence reason." Cheap (small context, binary output), significantly reduces false gaps. Run as a review pass before persisting results.
**source:** `07-model-selection-and-orchestration.md`

---

**type:** Pipeline
**title:** Prompt iteration — tailoring generation + profile extraction
**description:** Review and tighten the `generate_tailoring` system prompt. Consider adding few-shot examples to the profile extraction prompt. Both calls have not been systematically reviewed since early iterations.
**source:** `11-adjusted-sprint-plan.md`

---

**type:** Pipeline
**title:** GitHub deep crawl
**description:** Move GitHub from surface-level metadata (name, language, stars, description) to genuine experience signal by crawling high-signal files per repo using the GitHub Contents API. Priority targets: `README.md`, `CLAUDE.md`, `package.json`, `pyproject.toml`, `go.mod`, `Dockerfile`, CI workflow files. Per-repo output: `readme_summary`, `detected_stack`, `notable_files` (LLM-generated from crawled content). Background task, same pattern as `enrich_job_chunks`. Store as `github_repo_details` JSON column on `experiences`. Surface enriched repo data in ParsedProfile GitHub tab. **Rate-limit friendly**: 30 repos × 5 files = ~180 API requests, well within GitHub's 5,000 req/hr unauthenticated limit.
**source:** `08-github-deep-crawl.md`

---

**type:** Pipeline
**title:** Embeddings / pgvector for profile retrieval
**description:** At profile processing time, embed each experience bullet, skill, and education entry individually. At scoring time, embed the requirement chunk and retrieve top-K most semantically similar profile entries. Send only retrieved entries to the LLM — not the full profile. PostgreSQL already supports vectors via `pgvector` extension. Build after evidence extraction architecture is validated. Reduces scoring call context from "full evidence list" to "semantically retrieved evidence subset".
**source:** `18-scoring-reliability.md`

---

## Debug / Eval

**type:** Eval
**title:** Level 2 — Profile snapshot on Tailoring
**description:** Store a `profile_snapshot` JSON column on `Tailoring` at generation time: the exact `formatted_profile` string (or structured dict) sent to the LLM. Motivation: `Experience` is mutable — users edit it after tailorings are generated. The debug tab currently reconstructs the profile from the *current* experience, which may differ from what was used at generation time. A snapshot makes the debug view accurate and enables "what would change if I regenerated now?" comparisons. Also enables future diff views between profile versions.
**source:** `11-adjusted-sprint-plan.md`

---

**type:** Eval
**title:** Level 3 — Debug log table
**description:** A `tailoring_debug_logs` table: one row per generation run, storing `chunk_batch_payloads` (JSON), `chunk_batch_responses` (JSON), `llm_call_log` (sequence of model/prompt/response triples). Gate behind `DEBUG_LOGGING_ENABLED` env flag — off by default in production due to storage cost and PII. Enable selectively for specific users (`debug_logging` flag on `User` model) or for local dev. Foundation for Level 4 eval pipeline.
**source:** `11-adjusted-sprint-plan.md`

---

**type:** Eval
**title:** Level 4 — Eval pipeline
**description:** Build a test set of (job URL, profile) pairs with human-labeled expected chunk scores and advocacy blurb quality ratings. Eval runner: re-runs chunk matching on the test set using the current prompt + model, computes agreement with human labels. Diff view: side-by-side comparison of two runs (prompt change A vs B, or model X vs Y) — highlight chunks where scores diverged. CI integration: run eval on PR when `prompts/chunk_matching.py` changes, fail/warn if agreement drops below threshold. Makes prompt iteration measurable rather than anecdotal.
**source:** `11-adjusted-sprint-plan.md`, `14-claude-ai-workflows.md`

---

## Features — User-Facing

**type:** Feature
**title:** Post-tailoring gap detection and follow-up questions
**description:** After a tailoring is generated, run a second LLM pass that identifies requirements that could not be sourced from the candidate's profile and surfaces targeted follow-up questions (specific to this job and this candidate — never generic). User answers inline. Answers stored under `user_input` source key in Experience profile, immediately available to the next tailoring. New schemas: `ProfileGap` (job_requirement, question_for_candidate, context, source_searched), `GapAnalysis` (gaps list, sourced/unsourced counts). New files: `app/prompts/gap_analysis.py`, `app/services/gap_analyzer.py`.
**source:** `06-north-star-empowerment.md`

---

**type:** Feature
**title:** Interactive tailoring format
**description:** An alternate Tailoring view that re-renders the job posting as the frame, with the candidate's experience woven in. Each requirement is annotated inline or on hover with sourced evidence from the candidate's profile. The job description becomes the shared interface for use during live interviews — both parties can see it simultaneously. Different output schema: `RequirementAnnotation` (requirement, category, candidate_evidence[], evidence_sources[], strength). Same `/u/{slug}/{tailoringSlug}` URL, toggle at generation time or switchable on the public page. **Prerequisite: more mature static tailoring surface.**
**source:** `06-north-star-empowerment.md`

---

**type:** Feature
**title:** Tailorings on public profile — show_on_profile toggle
**description:** Currently tailorings are intentionally excluded from public profiles (exposes competitive intelligence, signals active job search). When revisiting: add a third per-tailoring toggle `show_on_profile` (distinct from `letter_public` / `posting_public`). Lets candidates curate which tailorings appear on their profile. Left sidebar placement preferred — appears above the fold regardless of scroll position.
**source:** `11-adjusted-sprint-plan.md`

---

**type:** Feature
**title:** Notion database export mode
**description:** Export tailorings to a Notion database (not just a page). Creates a row in a "Tailorings" database with properties for company, role, date created, job URL. More powerful than page export — user can filter, sort, and track all tailorings from Notion. Build as optional toggle after page export is stable.
**source:** `03-strategic-direction.md`

---

**type:** Feature
**title:** Interactive homepage demo
**description:** Let a visitor paste a job URL directly on the homepage and see a preview analysis without signing up. Most powerful conversion mechanism — shows the product before asking for commitment. **Blocked on:** guest/anonymous analysis flow. Day P4+ feature.
**source:** `13-homepage-redesign.md`

---

**type:** Feature
**title:** Homepage social proof section
**description:** Once real usage numbers are available: "X tailorings generated", "X job requirements matched". Testimonials with specifics — not generic praise but concrete outcomes ("scored 8 Strong matches for a role I almost didn't apply to").
**source:** `13-homepage-redesign.md`

---

## Privacy / Legal

**type:** Legal
**title:** Privacy policy page
**description:** Create `frontend/src/app/(marketing)/privacy/page.tsx`. Content covers: what data Tailord collects (Google OAuth data, resume, extracted profile, GitHub metadata, job URLs, generated tailorings, Notion tokens), what it does NOT do (no advertising data sale, no Notion workspace reads, no LLM training use), third-party services (Google, LLM provider, Azure, Notion), data retention, user rights (GDPR/CCPA), cookie policy (session-only). Required for Notion public integration review. Use Termly as generator starting point.
**source:** `10-privacy-and-terms-setup.md`

---

**type:** Legal
**title:** Terms of use page
**description:** Create `frontend/src/app/(marketing)/terms/page.tsx`. Content covers: what the service is, acceptable use, AI-generated content disclaimer (model may produce errors/hallucinations, user is responsible for review), Notion integration scope (create only, no reads), account termination rights, limitation of liability, changes to terms. Required for Notion public integration review. Add links to both pages in `/u/{slug}/{tailoringSlug}` footer.
**source:** `10-privacy-and-terms-setup.md`

---

**type:** Legal
**title:** Notion public integration review submission
**description:** Submit Tailord Notion integration for public review (removes 10-workspace development mode limit). Requires: live privacy policy URL, live terms URL, integration name/description, 256×256px logo/icon, explanation of permissions requested (insert content only — no read/update/delete/user info), screenshots or demo. Review is manual and can take days to weeks — submit early.
**source:** `10-privacy-and-terms-setup.md`

---

## North Stars

**type:** North Star
**title:** Public profile chat interface
**description:** A recruiter or interviewer lands on `/u/{slug}` and can ask questions directly: "Does she have experience with distributed systems?" Platform answers using the candidate's structured experience as context. Left pane of the two-pane profile layout is the natural home — persistent chat interface alongside static profile. **Latency requirements:** Haiku-class model (1–3s) + streaming (SSE already exists). **Prerequisites before building:** user-verified extracted_profile with high extraction quality, hosted fast model endpoint (not local LLM), rate limiting on public profile endpoint. **Defer until static profile surface is mature.**
**source:** `06-north-star-empowerment.md`

---

**type:** North Star
**title:** Headless enrichment API for job board integration
**description:** `POST /enrich` — body contains job URL (or raw job text) + user profile (or reference to stored profile); response returns chunks with scores, advocacy blurbs, and fit summary. No UI dependency — synchronous blocking or async job ID + poll/webhook. Partner API key auth (separate from user `X-API-Key`). Two consumer postures: candidate-facing (job board shows fit analysis to applicant before applying) or recruiter-facing (job board shows scoring to hiring team for each applicant — candidate unaware). This is Tailord as infrastructure (Clearbit/Stripe model). **Prerequisite: working B2C product with usage evidence to pitch with.**
**source:** `17-ai-agent-friendly.md`, `03-strategic-direction.md`

---

**type:** North Star
**title:** MCP server for Tailord
**description:** Expose Tailord data and actions as MCP tools/resources so any Claude Desktop or Claude Code user can query their tailoring data from within their agent environment without switching contexts. Resources: `tailord://experience`, `tailord://tailorings`, `tailord://tailoring/{id}`, `tailord://analysis/{id}`. Tools: `generate_tailoring(job_url)`, `get_fit_analysis(tailoring_id)`, `export_to_notion(tailoring_id, view)`. Start with read-only access to experience and tailoring data; add write actions once data surface feels right.
**source:** `17-ai-agent-friendly.md`, `14-claude-ai-workflows.md`

---

**type:** North Star
**title:** AI job search assistant features
**description:** Cross-job intelligence built on top of data already stored: "Which of my saved jobs best matches my skills?" (match scoring across all jobs), "What skills am I missing most often in my target roles?" (gap analysis), "Draft questions to ask at the {company} interview" (interview prep from job data). No new architecture required — additional features on top of existing data model.
**source:** `03-strategic-direction.md`

---

**type:** North Star
**title:** Platform partnership pitch to Simplify / Teal / Ashby
**description:** Approach one platform (Simplify is the recommended target) with evidence — user count, output samples, API readiness. Simplify's flow is: find job → autofill application → track. Tailord adds: find job → generate tailoring → autofill → track. The tailoring becomes part of Simplify's application prep flow. **Prerequisite: working B2C product with real users and usage evidence.**
**source:** `03-strategic-direction.md`

---

**type:** North Star
**title:** OpenAPI schema cleanup
**description:** Make the FastAPI auto-generated OpenAPI schema at `/openapi.json` clean, well-described, and stable: consistent response shapes (no ad-hoc dict returns), meaningful operation IDs (not `post_tailorings_tailorings_post`), documented error codes and meanings. Prerequisite for any B2B integration partner (they'll look at this first) and for the Tailord MCP server.
**source:** `17-ai-agent-friendly.md`

---

**type:** North Star
**title:** JSON endpoint for public tailoring and profile pages
**description:** Add `?format=json` query param (or `Accept: application/json` header) to `/u/{slug}/{tailoringSlug}` and `/u/{slug}` returning the same data as structured JSON — chunks, scores, advocacy blurbs, company, role, experience. Makes public tailoring data readable by any agent that can make HTTP requests without parsing HTML.
**source:** `17-ai-agent-friendly.md`

---

**type:** North Star
**title:** Webhooks for async enrichment events
**description:** For agent-driven and B2B workflows: `tailoring.ready`, `tailoring.enriched`, `experience.processed` webhook events so consumers can react to completion rather than polling. Not needed yet — design the event model with this in mind when building the headless enrichment API.
**source:** `17-ai-agent-friendly.md`

---

## Claude Code / Developer Workflow

**type:** Claude Code
**title:** Path-specific CLAUDE.md rules
**description:** Create `.claude/rules/` directory with path-scoped rule files: `frontend.md` (`paths: "frontend/**"`), `backend.md` (`paths: "backend/**"`), `api-contracts.md` (`paths: "frontend/src/app/api/**"`), `infra.md` (`paths: "infra/**"`). Each file is short and focused — specific beats general. Main `CLAUDE.md` becomes a lightweight orientation doc. Reduces context waste for monorepo work and improves adherence to stack-specific conventions.
**source:** `14-claude-ai-workflows.md`

---

**type:** Claude Code
**title:** Post-edit lint hooks
**description:** Configure hooks in `.claude/settings.local.json`: (1) after any frontend Edit: run `tsc --noEmit` to catch type errors before they compound; (2) after any backend Edit: run `ruff check` on changed file; (3) before Bash: block `git push --force`, `DROP TABLE`, `rm -rf` patterns (exit code 2 with reason). Start minimal — one hook that auto-lints after edits provides most of the value.
**source:** `14-claude-ai-workflows.md`

---

**type:** Claude Code
**title:** Skills for repeated tasks
**description:** Create `.claude/skills/` directory with reusable workflow prompts: `new-api-route` (scaffold Next.js API proxy route with auth, reading proxy.ts first), `new-backend-endpoint` (FastAPI endpoint + Pydantic schema + router registration), `alembic-migration` (generate migration, verify down_revision chain, remind to test), `new-component` (React component following design token conventions), `security-audit` (OWASP checklist for a given file or route).
**source:** `14-claude-ai-workflows.md`

---

**type:** Claude Code
**title:** Subagent definitions
**description:** Create `.claude/agents/` directory: `backend.md` (FastAPI, SQLAlchemy, Alembic, LLM pipeline expert), `frontend.md` (Next.js App Router, React, Tailwind v4, design system), `reviewer.md` (security + correctness review — read-only, no edits; reports Auth bypass, SQL injection, prompt injection, SSRF, N+1 queries, unhandled error cases grouped by severity: Critical/High/Medium/Low).
**source:** `14-claude-ai-workflows.md`

---

**type:** Claude Code
**title:** GitHub MCP
**description:** Configure GitHub MCP server so Claude can create PRs, view issues, check CI status, and read PR comments without copy-pasting. Scope to project-level (not global) in `.mcp.json`.
**source:** `14-claude-ai-workflows.md`

---

**type:** Claude Code
**title:** PostgreSQL MCP for direct DB access
**description:** Configure PostgreSQL MCP server so Claude can query the database directly to debug issues or verify migrations ran correctly. Invaluable for iterating on LLM pipeline output stored in the DB. **Keep credentials out of committed config** — personal `~/.claude.json` only, never `.mcp.json`.
**source:** `14-claude-ai-workflows.md`

---

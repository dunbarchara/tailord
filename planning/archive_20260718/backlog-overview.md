# Backlog Overview

High-level work items for sprint planning. Each item is a self-contained sprint candidate.

---

## LLM Quality

**Evidence Extraction (Two-Phase)**
Replace raw-profile scoring with a two-phase pipeline: extract a flat evidence list first, then score requirements against it — preventing hallucinated or inferred claims.

**Candidate Fact Sheet**
Single LLM call before scoring that produces a compact structured summary of the candidate; all chunk scoring uses it instead of the full profile, reducing context size and cost.

**Job Content Bounds Detection**
Detect where the job description ends and application-form/footer noise begins, cutting wasted scoring calls and preventing garbage chunks from appearing in the UI.

**Section Pre-Filtering**
Classify job chunks as evaluable/non-evaluable before scoring; skip "Benefits", "About Us", "EEO" sections that produce false Gap scores at zero LLM cost.

**Scoring Self-Verification**
For chunks scored as Gap on items likely to match (YOE, named technologies, education), run a targeted second verification call to reduce false negatives.

**Prompt Iteration**
Systematic review of the tailoring generation and profile extraction prompts; add few-shot examples to profile extraction; neither has been reviewed since early iterations.

---

## Tailoring Quality Gate

**Smoke Test Corpus**
Build a 200+ job fixture corpus spanning ATS platforms and role types; automated quality scoring pass; scraper coverage check. This is the gate before public launch — not a CI gate.

**Tailoring Review Mode & Flag Queue**
Admin pipeline step inspector (replay each stage of a tailoring), per-tailoring flag mechanism with structured flag types, and an iteration queue that groups open flags by root cause for prompt iteration sessions.

**Tailoring Archiving**
Archive state on tailorings hidden from the dashboard by default; manual archive action; smart stale-tailoring suggestions; restore at any time.

---

## Scraping

**Firecrawl Integration**
Evaluate and implement Firecrawl as a replacement or supplement to the current Playwright scraper; test against Greenhouse, Lever, and Workday ATS pages against existing eval fixtures.

---

## Experience Capture

**Quick Log**
Lightweight textarea on the Experience page for logging work in plain text — parses to claims with inferred employer attribution. Entry point for conversational capture.

**Conversational Experience Agent**
Chat overlay accessible across all dashboard pages; intent classification (add experience, create tailoring, query profile); two-turn attribution clarification; polls for async tailoring completion.

**GitHub Silent Capture**
GitHub App webhook endpoint receiving merged PR events; background agent extracts atomic experience claims from PR metadata (title, description, labels); claims land as `pending` for review. Zero overhead on the developer's machine.

**Linear Integration**
Capture experience signals from Linear work item completion — closed issues and milestones synthesized into pending experience claims via webhook.

**Text Message Experience Capture**
Enable inbound SMS (e.g. via Twilio) so users can text a line about what they shipped and have it parsed into a pending experience claim.

**File and Image Attachments on Claims**
Attach screenshots, PDFs, or design artifacts to individual experience claims as evidence; stored in blob storage; rendered as expandable links on the claim card and public profile.

---

## Claims Model

**Claim Approval Workflow**
`status` enum (`pending / approved / archived`) on `ExperienceClaim`; claims from automated integrations start as `pending`; only `approved` claims feed into tailoring generation and scoring.

**Claim Review UI**
Lightweight ledger surface showing pending claims: content, inferred pillar, provenance link, Approve / Edit / Reject actions. Surfaces on the Experience page or a dedicated Review tab.

**Claim Deduplication**
Before inserting new claims from any integration, run embedding cosine similarity check (≥0.92 = duplicate → skip or merge). Required prerequisite before enabling GitHub silent capture.

**Digest Notification**
Weekly background worker summarising pending claims per user ("3 new claims from this week — review here"). Design schema and worker first; email vs. in-app notification is a separate decision.

**Claim Table View & Filtering**
Redesign the Experience page claims list as a filterable table: source, date range, status, group/employer. Flat and grouped views. Replaces the current source-as-section layout which doesn't scale.

---

## Experience Groupings

**GitHub Repo ↔ Role Identity Resolution**
When a GitHub repo fuzzy-matches a role group name (e.g. `tailord` repo ≈ `Tailord` employer), merge their claims into one context block for the LLM — or link via `parent_group_id`. Prevents artificial signal doubling.

**Deduplication Within Logical Boundaries**
Deduplicate claims within the same logical boundary (same role + nested repos) while preserving identical claims across separate employers. Depends on group hierarchy being established.

---

## Product Pillars Framework

**6 Pillars Schema**
Define and document the six competency pillars for the developer integration (draft: Observability, Security, Reliability, DX/CD, Architecture, Usability). Map each to codebase signatures and JD keyword patterns.

**Pillar Classification in GitHub Enrichment**
Wire pillar output into the GitHub enrichment LLM schema; store per-claim in `chunk_metadata`; enables competency-category filtering and JD matching at the pillar level.

**TAILORD.md Artifact**
Design and build a repo-level manifest auto-generated by agentic codebase scan: claims organised by pillar with source links. Two-artifact model: `TAILORD.md` (public, checked in) + `.tailord/claims.json` (personal, gitignored). Build Tailord's own first as a portfolio demo.

---

## Output Types

**Resume Export**
Generate a targeted single-page PDF resume from an existing Tailoring — not generic, not an ATS optimizer. The resume reflects the same match intelligence that produced the Tailoring.

**Multiple Output Content Types**
Extend the generation pipeline beyond Tailorings: performance review self-assessments, STAR interview story prep, resume bullet generation, LinkedIn summary drafts. Requires a `GenerationTarget` abstraction.

**Tailorings on Public Profile**
`show_on_profile` toggle per tailoring (separate from `letter_public` / `posting_public`) so candidates can curate which tailorings appear on their public `/u/[slug]` page.

**Interactive Tailoring Format**
Alternate tailoring view that re-renders the job posting as a frame with candidate evidence woven inline against each requirement. Useful during live interviews.

---

## Public Profile

**Public Experience Search**
Opt-in searchable index of a user's approved claims on their public profile — visitors search "Kubernetes" and get back the specific bullets, not the whole resume. Rate-limited for unauthenticated requests.

**Public Profile Chat**
Recruiter or interviewer asks questions on `/u/[slug]`; answered from the candidate's structured experience using a fast model + SSE streaming. Prerequisite: high-quality profiles and rate limiting on the public endpoint.

---

## Frontend UX

**Onboarding Getting Started**
Progress bar checklist on dashboard home for new users: Add experience → Create first Tailoring → Share a Tailoring. Dismissed once complete. Actionable empty states throughout.

**Usage Visibility**
Always-visible usage summary (sidebar or settings): tailorings generated, claims stored, integrations connected. Sets expectations around tier limits.

**In-App Feedback**
Persistent low-friction feedback entry: floating button or short textarea overlay. Feedback stored in DB or forwarded via webhook. Design the data model before building.

**Mobile Layout**
Tailoring detail header action buttons (View Posting / Copy / Regenerate / Export) need a dropdown or stacked layout at small screens.

**Accessibility Audit**
Add `aria-label` on icon-only buttons, `role="alert"` on error states, keyboard navigation through the sidebar tailoring list.

**Resources / Help Section**
`/dashboard/resources` or sidebar Help link with articles explaining GitHub integration, how tailorings are generated, what claims are, and the privacy model. Reduces support load.

**Homepage Revamp**
Full product homepage communicating the value proposition, showcasing the UI with real screenshots, and converting visitors. Includes social proof section and interactive demo (paste a job URL without sign-up).

---

## Auth & Onboarding

**Email Infrastructure**
Evaluate and select a transactional email provider (Resend, Postmark, SendGrid) for magic link auth, weekly claim digest, and account welcome. Decision required before any email-dependent features.

**Magic Link Login**
Email/magic-link as a second auth method alongside Google OAuth; lowers barrier for non-Google users.

**LinkedIn OAuth + Profile Import**
LinkedIn login and profile import — primary value is bootstrapping experience claims from work history and education before resume upload.

---

## Monetisation

**Billing Data Model**
`user_subscriptions`, `user_entitlements` tables; tier enum (`free / capture / premium`); Stripe webhook handler; `require_premium()` FastAPI dependency; frontend upgrade prompt on gated features.

**Free Trial Flow**
14-day trial of premium features at registration; `trial_ends_at` on the subscription row; in-app banner at 3 days remaining; email on expiry.

**LLM Cost Visibility**
Extend `LlmTriggerLog` with per-call token counts, cached tokens, and cost; admin cost dashboard showing cost per operation type, per tailoring, and estimated per-user monthly cost. Required to set pricing responsibly.

---

## Platform Architecture

**Jobs & Job Chunks Refactor**
Rename `is_requirement` → `include_in_scoring` (accuracy); add `semantic_type` classification to job chunks; other schema cleanup identified in the DB schema review.

**Platform/Integration Boundary Audit**
Audit `ExperienceClaim`, FastAPI routes, and API contracts for developer-specific vocabulary baked into the core platform; document what should move and when.

**Headless Enrichment API**
`POST /enrich` endpoint with partner API key auth: job URL + user profile → chunks with scores, advocacy blurbs, fit summary. Synchronous or async job ID + poll/webhook. Prerequisite: working B2C product with usage evidence.

**MCP Server**
Expose Tailord experience and tailoring data as MCP tools: `generate_tailoring`, `get_fit_analysis`, `export_to_notion`; resources for experience and tailorings. Start read-only.

**Agent-Friendly API Surface**
OpenAPI schema cleanup (consistent shapes, meaningful operation IDs, documented errors); JSON endpoint for public profile and tailoring pages; webhooks for async events (`tailoring.ready`, `experience.processed`).

**Cross-Job Intelligence**
Stored-job queries using existing data: "which saved jobs best match my skills?", "what skills am I missing most often?", "draft interview prep for {company}".

---

## Developer Workflow

**Claude Code Subagents**
`.claude/agents/` directory with `backend.md`, `frontend.md`, and `reviewer.md` (read-only security + correctness review) subagent definitions.

**GitHub MCP**
Project-level `.mcp.json` configuring the GitHub MCP server for PR creation, issue viewing, CI status, and PR comments without copy-pasting.

**PostgreSQL MCP**
Configure PostgreSQL MCP for direct DB access during debugging and migration verification; credentials in personal `~/.claude.json` only.

**Observability Standards Hook**
Extend `.claude/hooks/post-edit.py` to warn (advisory, non-blocking) when backend edits add an LLM call without an OTel span, a FastAPI endpoint without `require_api_key`/`get_current_user`, or a `logging.getLogger` call instead of `structlog.get_logger`.

---

## Hardening & Testing

**Typed Unit Fixtures**
Convert `SimpleNamespace` test helpers in `tests/services/` to dataclasses or actual ORM objects. Catches attribute contract bugs silently missed by namespace-based fixtures.

**ORM Integration Tests**
`pytest` fixture spinning up a real Postgres test DB; run key ORM operations against the actual schema. Catches migration regressions and ORM → DB round-trip bugs.

**Backend Test Coverage to 80%**
Currently ~53%; remaining gap: SSE streaming, background tasks, Notion export, experience endpoints.

**Infrastructure Security Baseline**
Document and verify TDE on Azure PostgreSQL; enforce RBAC so only the backend identity has DB access; document posture in `infra/providers/azure/SECURITY.md`.

**SARIF CVE Monitoring**
Trivy SARIF upload step in CI; free on public repos; tracks CVEs across runs. Add when repo goes public.

---

## Portfolio

**Portfolio Write-Up**
`planning/12-portfolio-writeup.md`: the problem Tailord solves, key technical decisions (dual pipeline, streaming, chunk scoring, Notion), and what I'd do next. For job conversations.

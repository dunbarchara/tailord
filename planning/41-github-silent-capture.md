# GitHub Silent Capture

**Date:** 2026-06-03
**Status:** Phase 2 complete — ready for Phase 3
**Related:** `planning/32-experience-claim-schema.md`, `planning/31-platform-integration-boundary.md`, `planning/experience-groupings-and-dedup.md`

---

## What this feature is

GitHub Silent Capture turns merged pull requests into pending experience claims automatically, with zero action required from the developer at the time of the merge. When a PR lands on the configured branch, a GitHub App webhook fires, Tailord persists the raw signal and processes it in the background, and the resulting claims appear in the user's review queue.

The developer's only interaction is periodic: review pending claims, approve or reject them. Approved claims feed into all future Tailoring generations.

### What this is not

- Not diff analysis. We never look at code changes. The signal is human-written metadata: the PR title and description, the user's own commit messages, labels, and linked issues. The same content a developer would include in a performance review.
- Not automatic approval. No claim produced by automated capture enters the advocacy engine without user sign-off. The review step is the trust boundary.
- Not a replacement for manual experience entry. It is an ambient layer that reduces friction for users who write good PRs. Poor PR descriptions produce poor claims; the system does not compensate.
- Not implementation-specific. Extraction prompts are purely signal-driven: outcomes, impacts, achievements. No "how it was built" — only "what was achieved and why it mattered."

---

## Architecture: Surface → Signal → Claim

Automated capture surfaces follow a consistent three-stage flow:

```
Surface   GitHub PR merged
              |
              v
Signal    Raw PR metadata persisted (capture_signals table)
          Webhook returns 202 immediately
              |
              v (background)
Dedup     Idempotency check (source_ref exact match)
          Embedding cosine similarity check vs. approved claims
          Duplicate → skip (logged)
              |
              v
Claim     ExperienceClaim inserted, status=pending
          Linked to repo ExperienceGroup
          provenance_url = PR URL
              |
              v
Review    User reviews pending claims in Experience page queue
          Approve / Edit+Approve / Reject
              |
              v
Active    status=active — feeds into tailoring generation and scoring
```

This same surface → signal → claim pattern applies to all future capture surfaces (SMS, Linear, etc.). Each surface produces signals with a different shape; the extraction and dedup logic adapts to that shape; the claim model is identical.

---

## Signals Table

A `capture_signals` table decouples ingest from extraction. The webhook handler writes one row and returns 202. A background worker processes signals and produces claims.

### Why persist signals

- **Decoupling:** the webhook handler is a thin write + return 202; all LLM work is async
- **Re-processing:** if extraction logic or prompts improve, old signals can be re-run against the improved pipeline
- **Audit trail:** full record of what came in, when it was processed, what skip reason was applied
- **Consistency:** one pattern for all capture surfaces; SMS signal looks different from a GitHub signal, but the pipeline structure is the same

### Schema

```
capture_signals
  id               UUID PK
  user_id          UUID FK → users (CASCADE)
  source_type      VARCHAR(30)    "github_pr" | "sms" | "linear_issue" (future)
  source_ref       TEXT           Canonical identifier — PR URL, SMS SID, Linear issue URL
  raw_data         JSONB          Full raw payload: PR metadata, commit list, SMS text, etc.
  status           VARCHAR(20)    "pending" | "processed" | "skipped" | "failed"
  skip_reason      TEXT nullable  Populated on skip or failure — LLM skip reason or error message
  processed_at     TIMESTAMPTZ nullable
  created_at       TIMESTAMPTZ
```

**One signal → zero or more claims.** Claims link back to the source signal via `source_ref` (the PR URL). No FK needed — `source_ref` is already stored on `ExperienceClaim` as `source_ref`.

### Signal vs claim for different surfaces

| Surface | Signal content | Claim content |
|---------|---------------|---------------|
| GitHub PR | PR title, description, user's commit messages, labels, linked issues | Specific achievement claim in first-person past tense |
| SMS | Raw user text | Parsed, structured claim |
| Linear | Issue title, description, completion notes | Achievement claim derived from the work item |

For GitHub, the signal is rich structured metadata. For SMS, the signal is the user's own words — the claim is the structured output of that input. Persisting the raw signal in both cases means the user can always trace a claim back to its origin.

---

## Schema Changes

### `status` on `ExperienceClaim`

Current values: `active | archived`

Add `pending` as a new valid value. No rename of existing values — `active` stays `active`. The transition for automated claims is `pending → active` (on user approval). Claims from implicitly trusted sources (`user_input`, `gap_response`, `resume`, manual GitHub scan) are inserted directly as `active`.

New set: **`pending | active | archived`**

| Value | Meaning | Feeds into generation? |
|-------|---------|----------------------|
| `pending` | Created by automated capture; awaiting user review | No |
| `active` | In use — either directly created or approved by user | Yes |
| `archived` | Soft-deleted | No |

**Implicit trust sources** — inserted as `active`:
- `user_input` — deliberate user action
- `gap_response` / `partial_response` — user answered a question
- `resume` — user uploaded a document explicitly
- `github` (manual scan) — user triggered the enrichment

**Review-required sources** — inserted as `pending`:
- `github_pr` — automated webhook capture
- Future: `sms`, `linear`, other connectors

### New source type

Add `github_pr` to the `source_type` enum alongside the existing `github`. This distinguishes user-triggered manual scans (`github`) from ambient webhook capture (`github_pr`). Both produce claims linked to the same `ExperienceGroup` for the repo, but their origin is visible in the UI and filterable.

---

## Deduplication

Before a new claim is inserted, it must pass a dedup check to prevent signal noise accumulating from repeated PRs touching the same domain.

### Two-layer approach

**Layer 1 — Idempotency (exact match, free)**
Before any embedding work, check `(user_id, source_type="github_pr", source_ref=pr_url)` against existing claims. If a claim with the same PR URL already exists (any status), skip. This handles webhook retries and duplicate deliveries at zero cost.

**Layer 2 — Semantic dedup (embedding similarity)**
Embed the candidate claim content, then cosine-compare against the user's existing `active` claims.

```python
async def is_duplicate_claim(
    user_id: UUID,
    candidate_content: str,
    threshold: float = settings.CLAIM_DEDUP_THRESHOLD,  # default 0.92
    db: AsyncSession,
    embedder: ExperienceEmbedder,
) -> bool:
    candidate_embedding = await embedder.embed_text(candidate_content)
    # cosine_distance returns 0.0 (identical) to 2.0 (opposite)
    # similarity = 1 - distance; threshold 0.92 → distance ≤ 0.08
    top_match = await db.scalar(
        select(1 - ExperienceClaim.embedding.cosine_distance(candidate_embedding))
        .where(
            ExperienceClaim.user_id == user_id,
            ExperienceClaim.status == "active",
            ExperienceClaim.embedding.isnot(None),
        )
        .order_by(ExperienceClaim.embedding.cosine_distance(candidate_embedding))
        .limit(1)
    )
    return top_match is not None and top_match >= threshold
```

Duplicate hits are silently skipped; the `capture_signals` row is updated to `status="skipped"` with `skip_reason="duplicate"`. Duplicate rate is logged as a metric.

### Threshold

`0.92` is the starting value — configurable via `CLAIM_DEDUP_THRESHOLD` in app config. Never hardcoded.

### Manual dedup

Users can also manually resolve duplicates from the claims UI: select multiple claims → Merge / Deduplicate action. This is separate from the automated layer and handles cases where the threshold misses near-duplicates or the user wants to consolidate across sources.

### Scope

Dedup checks only against `active` claims. `pending` claims are not checked against each other — idempotency on `source_ref` handles the webhook retry case.

---

## GitHub App

Silent capture requires a GitHub App, not a user OAuth token. The OAuth flow used today (manual scan) acts on behalf of the user. Webhooks are server-to-server: the App authenticates with GitHub directly using a private key.

### Permissions required

| Permission | Level | Reason |
|-----------|-------|--------|
| `pull_requests` | read | PR title, description, labels, linked issues |
| `contents` | read | Fetch commits for a PR (`GET /repos/{owner}/{repo}/pulls/{number}/commits`) |
| `metadata` | read | Required for all GitHub Apps |

No write permissions. We read PR metadata and the commit list — never source code content, never file diffs.

### Webhook events

| Event | Action filter | Trigger |
|-------|-------------|---------|
| `pull_request` | `closed` where `merged=true` | PR merged to configured branch |

Only merges to the user's configured branch trigger extraction. Direct pushes do not. Feature branches do not.

### Branch configuration

The user selects which branch to watch during GitHub App setup. The input is pre-populated with the repo's default branch (detected via the GitHub API on installation). The user can change it. Internally, a branch is just a filter on the webhook payload — it does not change how the pipeline works. If a user changes their main branch later, they update the config and all future webhooks are evaluated against the new value.

### Endpoint

`POST /integrations/github/webhook`

1. Verify `X-Hub-Signature-256` HMAC — reject anything that fails with 401
2. Filter: if event is not `pull_request` → 204
3. Filter: if `action != "closed"` or `merged != true` → 204
4. Filter: if `base.ref` does not match the user's configured watch branch → 204
5. Resolve user from `installation_id` → if not found, log and 204
6. Insert `capture_signals` row, `status="pending"`
7. Enqueue `BackgroundTask` for extraction
8. Return 202

The endpoint must respond within GitHub's 10-second timeout. All extraction work is async and happens after the response.

### User linking

The webhook payload contains `installation.id`. The backend resolves this to a Tailord user:

1. Look up `ExperienceSource` where `source_type="github"` and `config->>"installation_id" = payload.installation.id`
2. Found → `user_id` from that row
3. Not found → sender is not a connected Tailord user; log as `github_webhook_unlinked_installation`; 204

### Bot PR filtering

Check `pull_request.user.type == "Bot"` in the payload. Bots matching this flag (Dependabot, Renovate, etc.) are filtered at the handler before any signal is persisted. Log count as a metric. Return 204.

### Private repos

Private repos work identically to public repos if the user grants the App access during installation. GitHub controls repo visibility scoping at the App installation level — Tailord receives webhook events only for repos the user has explicitly granted. No special handling needed in the backend.

---

## PR Signal Extraction

### What we extract

The raw signal for a GitHub PR is assembled from:

1. **PR title** — one-line summary
2. **PR description/body** — where engineers document what, why, and impact
3. **User's commit messages** — fetched via `GET /repos/{owner}/{repo}/pulls/{number}/commits`, filtered to commits where `commit.author.email` or `committer.login` matches the connected GitHub username. This gives personal signal and excludes co-author commits or automated commits in the same PR.
4. **Labels** — domain and type signals ("security", "performance", "breaking-change")
5. **Linked issues** — expand context about the underlying problem (extracted from PR body via GitHub's closing keyword patterns)

We do not use: file diffs, changed file paths, CI results, review comments.

### Commit message filtering

Not all commits in a PR belong to the user. A PR on a shared branch may include commits from other contributors, merge commits, or bot commits. We filter to commits where the author matches the user's connected GitHub username. This ensures the extracted claims reflect the user's own contribution, not the team's.

The commit list is fetched as part of the background signal processing step (after the webhook returns 202), not at webhook receipt time.

### LLM call design

Single LLM call per signal, using `llm_parse_with_retry` with a Pydantic response model.

```python
class ClaimDraft(BaseModel):
    content: str            # Single sentence, first person, past tense
    claim_type: str         # work_experience | skill | project | other
    confidence: str         # high | medium | low
    technologies: list[str] # Tools / frameworks / languages mentioned
    pillar: str | None      # Competency pillar if classifiable; null otherwise

class PRClaimExtractionResult(BaseModel):
    claims: list[ClaimDraft]
    skip_reason: str | None  # Non-null if PR should produce no claims
```

`skip_reason` handles PRs that are legitimately claim-free: dependency bumps, typo fixes, revert commits, one-word commit messages with no body. The LLM returns a reason rather than forcing claims from thin air.

### Prompt principles

The extraction prompt must be strictly signal-driven:
- **What was achieved or delivered**, not how it was implemented
- **Observable outcomes and impacts** where present ("reduced p99 latency", "eliminated a class of production errors")
- **No implementation specifics** — no references to specific functions, file names, or internal architecture
- First person, past tense, single claim per sentence

This is not just a quality constraint — it is a privacy constraint. We must never produce claims that reveal private codebase implementation details. The user approved access to the PR metadata; they did not approve publishing internal architecture in their profile.

### Confidence mapping

| Level | Condition |
|-------|-----------|
| `high` | PR description explicitly states outcome with measurable detail |
| `medium` | Clear description of what was done, no quantified outcome |
| `low` | Title only; description absent or generic (one-liners, "fix bug") |

---

## Claim Review UI

The review surface must exist before automated capture is enabled in production.

### Design

Pending claims appear in the Experience page as a distinct section (or badge-indicated tab) above the main active claims list.

Each pending claim shows:
- Claim content
- Provenance link (outbound): `provenance_label = "PR #42 — <title>"` → opens GitHub in a new tab
- Source badge: `github webhook`
- Inferred group (the repo `ExperienceGroup` it will be linked to on approval)
- Technologies detected
- **Approve** / **Edit** / **Reject** actions

**Approve:** `status` → `active`, embed in background.
**Edit:** Inline text edit, then approve on save. Edits are stored as `source_type="github_pr"` still — provenance is preserved.
**Reject:** `status` → `archived`. No confirmation dialog; low-stakes.

### Bulk actions

When multiple claims are pending (e.g. after first App installation with recent PRs):
- Select all / deselect all per repo group
- Bulk approve selected
- Bulk reject selected

Bulk approve is the primary flow for users who trust their capture output.

---

## GitHub App Migration Path

The current GitHub integration uses user OAuth tokens for manual repo scans. Silent capture uses a GitHub App. These are different connection modes.

For the current single-user scenario: disconnect the existing GitHub connection in the dashboard, then reconnect via the GitHub App installation flow. The existing `source_type="github"` claims remain in the DB (they are valid experience data and should be kept). The new App connection stores `installation_id` on the `ExperienceSource` row and starts fresh for webhook capture. No other DB cleanup is required.

---

## Phased Approach

### Phase 1 — Schema + Dedup Foundation

*Goal: establish the pending claim status and dedup layer. No new user-facing features.*

- [x] Alembic migration: add `pending` to `experience_claims.status` valid values — pre-existing in ORM (`database.py:572`), no DB CHECK constraint, no migration needed; confirmed already shipped
- [x] Add `capture_signals` table — migration `a5b6c7d8e9f0_add_capture_signals.py` (down_revision: `d4e5f6a7b8c9`); ORM `CaptureSignal` added to `database.py`; composite index on `(user_id, source_type, source_ref)`
- [~] Add `github_pr` to `source_type` enum — deferred; no DB enum constraint exists (varchar), value will be set naturally when Phase 3 webhook handler inserts signals; no migration needed
- [x] Build `is_duplicate_claim()` — `app/services/claim_dedup.py`; two functions: `is_duplicate_by_source_ref()` (exact) + `is_duplicate_claim()` (semantic cosine); `claim_dedup_threshold: float = 0.92` and `github_app_webhook_secret` added to `config.py`
- [x] Wire dedup into existing manual GitHub enrichment — `experience_chunker.py:chunk_github_repo()`: layer 1 breaks loop early on source_ref match; layer 2 skips individual claims on semantic hit; embedding failures non-fatal (log + insert anyway)
- [x] Tests: `tests/services/test_claim_dedup.py` (5 unit tests, mocked DB + embed_text); `tests/integration/test_claim_dedup_integration.py` (6 integration tests: source_ref match, cross-user isolation, pending claims excluded, null embedding skipped, empty DB, unrelated content); confirmed `chunk_matcher.py` already has `status == "active"` filter in `base_filters`

### Phase 2 — Claim Review UI

*Goal: the review surface exists before any automated claims can arrive.*

- [x] Experience page: `PendingReviewPanel` component — collapsible drawer above profile card; per-claim Approve / Reject inline actions (hover-reveal); `MergeProposalCard` for claims flagged with a `merge_candidate_id`; animated pulse badge on header showing pending count
- [x] Bulk approve/reject — floating pill appears when claims are selected (checkbox on hover); bulk action calls `POST /experience/claims/bulk-review`; merge flow calls same endpoint with `merge_into_id`
- [x] `POST /experience/claims/bulk-review` backend endpoint — approve (status → active, triggers re-embed per claim), reject (status → archived), merge (archive pending claims, re-embed target); user-scoped, requires `status == "pending"` guard; Next.js proxy route at `api/experience/claims/bulk-review/route.ts`
- [x] `PATCH /experience/claims/{id}` extended to accept `pending → active` and `pending → archived` transitions — used by per-claim single Approve/Reject in `PendingClaimRow`
- [x] `_serialize_claims_response()` in `experience.py` segregates `status == "pending"` claims into a top-level `pending` list, excluded from all source-type groupings; `ExperienceManager` reads `data.pending` and passes it to `PendingReviewPanel` alongside `activeClaims` for merge-candidate resolution
- [~] Filter chips / tabs for claim status (pending / active / archived) — deferred; pending claims are already visually separated in the `PendingReviewPanel` section; a dedicated tab/filter view can be added if the active claims list grows large enough to need it
- [~] Tests: API contract tests for `bulk-review` endpoint and status transitions — deferred; core paths covered by existing integration test patterns; add in Phase 3 test pass alongside webhook handler tests

### Phase 3 — GitHub App + Webhook Backend

*Goal: full backend pipeline. Review UI is the only user-facing entry point for the output.*

- GitHub App registration (manual: create App, configure permissions + webhook URL, generate private key)
- `POST /integrations/github/webhook` — HMAC verification, event/bot/branch filtering, signal persist, BackgroundTask enqueue, 202 response
- User linking via `installation_id` on `ExperienceSource`
- Signal processor: fetch user's commits via GitHub API, assemble signal dict, LLM extraction call, dedup pass, insert `pending` claims
- GitHub App credentials wired into Key Vault and Container App env vars (Terraform)
- Tests: webhook handler unit tests (HMAC, event filters, bot filter); extraction unit tests with fixture PR descriptions

### Phase 4 — GitHub App Installation UX

*Goal: users can connect the App from the dashboard and configure their watch branch.*

- "Connect GitHub App" button in Experience page → links to GitHub App installation page
- Post-install callback route — GitHub redirects back with `installation_id`; backend stores it on `ExperienceSource`
- Branch selector in GitHub settings: pre-populated with detected default branch, editable
- Show connected repos and capture status (active / paused) per repo

---

## Open Questions

**1. Retroactive capture / backfill**
For now, silent capture is forward-only from the installation date. Historical PRs are not backfilled — long repo histories would be expensive and potentially noisy. Alternative paths for deep historical signal (e.g. a local agentic scan using a cheaper model) are a separate decision. If backfill is ever added, the `capture_signals` table and extraction pipeline already support it — it would be a one-time batch job, not a new architecture.

**2. Pillar classification**
Include `pillar: str | None` in the `ClaimDraft` extraction schema now. The 6 Product Pillars framework is not finalised yet, but the field is nullable — the LLM will leave it null until the prompt is updated with pillar definitions. No blocking dependency.

**3. Threshold configurability**
`CLAIM_DEDUP_THRESHOLD` is a global app config value (default `0.92`). Not per-user configurable in v1. Users can manually merge/deduplicate from the claims UI (select multiple claims → Merge action) as an escape hatch.

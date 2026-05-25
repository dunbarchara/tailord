# Surface 03 — GitHub On Commit (PR Merge)

**`source_type`:** `plugin_github`
**Status:** Planned
**Acquisition:** Poll on merged PRs (v1) or inbound webhook on PR close (v2)
**Related:** `planning/28-experience-connectors.md` (section 2 and 3)

---

## 1. What It Captures

Where the GitHub Scan (surface 02) produces a one-time snapshot of a repo's overall character, GitHub On Commit captures individual work events as they happen: each merged PR is a discrete professional contribution with a title, description, changed files, and outcome context.

This turns the GitHub integration from a snapshot into a live feed — a continuous record of what the user ships over time.

Signals extracted from a merged PR:

| Source | Signal |
|---|---|
| PR title + description | Accomplishment claim(s), outcome statements |
| Changed file extensions | Stack signals (`.tsx` → React, `alembic/versions/` → migrations) |
| File path structure | Domain signal (`backend/app/services/` → backend, `frontend/src/components/` → UI) |
| Linked issue titles | Motivation / outcome context |
| Additions/deletions count | Scale signal (rough proxy for scope) |

File content is never fetched — only file paths and metadata. This is a deliberate privacy and cost decision: file paths are usually enough to infer domain, and descriptions provide the outcome signal.

---

## 2. Metadata to Store

| Field | Value |
|---|---|
| `source_type` | `plugin_github` |
| `source_ref` | `"{repo_name}#PR{number}"` — unique per event, enables dedup |
| `claim_type` | `work_experience` (accomplishment) or `skill` (stack signal) |
| `group_key` | `repo_name` — groups PR-derived chunks under the same repo as the scan chunks |
| `date_range` | PR `merged_at` timestamp → formatted as ISO date |
| `technologies` | `detected_stack` from PREnrichment model |
| `confidence` | `medium` (LLM-extracted from PR description — user wrote it but LLM interpreted it) |
| `chunk_metadata` | `{pr_url: "...", merged_at: "...", llm_model: "...", extraction_date: "..."}` |
| `source_urls` | `[pr_url, top_file_permalink_1, top_file_permalink_2]` — see Source URLs below |
| `plugin_connection_id` | FK to `ExperienceConnector` row |

---

## 3. Source URLs

Store up to three URLs per PR event:

1. **PR URL**: `https://github.com/{owner}/{repo}/pull/{number}` — permanent, never rots
2. **Top file permalinks at merge SHA**: `https://github.com/{owner}/{repo}/blob/{merge_sha}/{filepath}` — permanent because the commit SHA is fixed
3. **Directory link** (if the claim is about an architectural area, not a single file): `https://github.com/{owner}/{repo}/tree/{merge_sha}/{dir}/`

Rules for selecting which files to link:
- Use the LLM's `most_relevant_files` ranking from `PREnrichment` — not all changed files
- Store top 1–3 files per claim, not the full changed file list
- Prefer files whose path names make the claim legible at a glance (e.g., `billing/retry_logic.py` over `utils/helpers.py`)

Note: deep file permalinks use the merge commit SHA, which is permanent. These URLs will not rot even if the file is later moved or deleted.

---

## 4. Sensitivity Filters

- Strip company-identifying internal codenames found in PR titles or descriptions
- Strip customer names or client references
- Flag non-public repos: if the repo is private, all PR content should go through the review gate before any chunk is stored — never silently ingest from a private repo

The raw PR payload is stored in `ConnectorEvent.raw_payload` and is deletable by the user on request.

---

## 5. Processing Pipeline

### v1 — Polling (recommended first)

```
1. User connects GitHub (existing flow) — connector record created with last_synced_at = connection time
2. Trigger: user clicks "Sync GitHub" button, OR auto-trigger when last_synced_at > 7 days on page load
3. GitHub API: GET /repos/{owner}/{repo}/pulls?state=closed&sort=updated&since={last_synced_at}
4. Filter to merged: true only
5. Dedup check: skip PRs already stored as ConnectorEvent (dedup key = repo + PR number)
6. For each new merged PR:
   a. Fetch PR details: title, body, changed files (paths only), linked issues, merge_sha
   b. LLM signal-quality gate: PREnrichment model
   c. signal_quality == "low": store ConnectorEvent with extraction_status="skipped", skip_reason visible
   d. signal_quality == "medium" or "high": extract experience_claims, create ConnectorEvent
   e. Queue for user review (status = "pending")
7. Update last_synced_at on connector record
```

### v2 — Webhook

```
1. User sets up webhook in GitHub repo settings (Tailord shows webhook URL + HMAC secret)
2. POST /webhooks/github — validate HMAC-SHA256 signature against stored secret; return 200 immediately
3. Background task: same extraction pipeline as polling (step 6 above)
4. Dedup key = repo + PR number (same as polling — webhook and poll can coexist safely)
```

**Why polling first:**
- Zero additional user friction — they've already connected GitHub
- No public inbound endpoint required for local dev
- Catches PRs merged before the webhook was configured or while it was down
- Webhook adds real-time delivery on top of polling; they are complementary, not competing

### LLM Signal-Quality Gate — `PREnrichment`

```python
class PREnrichment(BaseModel):
    signal_quality: Literal["high", "medium", "low"]
    skip_reason: str | None          # populated if signal_quality == "low"
    experience_claims: list[str]     # empty if signal_quality == "low"
    detected_stack: list[str]
    project_domain: str
    most_relevant_files: list[str]   # ranked subset of changed_files
```

If `signal_quality == "low"`: no ExperienceChunks created. ConnectorEvent stored with `extraction_status="skipped"`. Users can promote a skipped event from the event log if they disagree with the assessment. This keeps the review queue clean while preserving auditability.

---

## 6. Dedup and Atomic Decomposition

**Dedup key for PR events**: `{repo_name}#{pr_number}`. A PR that appears in both a polling pass and a subsequent webhook event is only ingested once. The ConnectorEvent table stores this key and the ingestion pipeline checks it before creating a new event.

**Cross-PR skill dedup**: if a user merges 20 PRs all touching React, the polling pipeline produces 20 potential React skill chunks from `detected_stack`. These should be deduplicated at ingest using the standard cosine threshold check. Skill chunks from the same technology are the strongest case for automatic consolidation — but still route through the review queue rather than silently merging.

---

## 7. Human Approval Gate

**Required before ingestion.** ConnectorEvents go through a review queue in My Experience before any ExperienceChunk is persisted.

Review card per event:
- PR title and description (raw)
- Extracted claims
- Source URLs (rendered as links)
- Signal quality rating + skip reason (if skipped)

User actions: approve all, approve individually, edit claim text, remove a claim, reject the whole event, promote a skipped event.

This gate is mandatory for v1. Silent ingestion (auto-approve without review) can be a user-configurable preference after trust is established.

---

## 8. Backend Entry Points

**Connector registration (planned):**
```
POST /experience/connectors
Request:  { connector_type: "github_poll", config: { repos: [...], branch: "main" } }
Response: ExperienceConnector
```

**Manual sync trigger (planned):**
```
POST /experience/connectors/{id}/sync
Response: { events_queued: int }
```

**Webhook receiver (planned):**
```
POST /webhooks/github
Headers:  X-Hub-Signature-256
Request:  GitHub webhook payload (pull_request event)
Response: 200 immediately; processing is async
```

**Review queue (planned — shared with all connectors):**
```
GET /experience/connectors/events?status=pending
PATCH /experience/connectors/events/{id}
Request:  { action: "approve" | "reject", chunks?: [{ content, claim_type }] }
```

---

## 9. Portability — Other Git Platforms

The GitHub-specific connector is implemented first. The same polling/webhook architecture should abstract to support Azure DevOps and GitLab with a `connector_type` enum on `ExperienceConnector`:

| `connector_type` | Platform | API base |
|---|---|---|
| `github_poll` | GitHub.com | `api.github.com` |
| `github_webhook` | GitHub.com | inbound webhook |
| `gitlab_poll` | GitLab.com or self-hosted | `gitlab.com/api/v4` |
| `azuredevops_poll` | Azure DevOps | `dev.azure.com` |

The PREnrichment model and chunk creation logic are platform-agnostic. Only the API client differs per platform.

---

## 10. Open Questions

1. **Private repo policy**: should private repo PRs require an additional explicit opt-in beyond the existing GitHub connection? The sensitivity risk is higher — unreleased features, internal architecture.

2. **Branch filter**: should users be able to specify which branches trigger extraction (not just `main`)? Some teams merge to `develop` first.

3. **Auto-approve threshold**: should PRs with `signal_quality == "high"` be auto-approved without the review gate, as a user preference? Risks: occasional LLM mis-classification.

4. **PR description quality incentive**: Tailord could surface a nudge to users with consistently low-signal PRs: "Your recent PRs have sparse descriptions — better descriptions produce richer experience signals." Is this appropriate or too presumptuous?

5. **Retroactive backfill**: on first connector setup, how far back should the poll go? 6 months? 1 year? Unlimited? Capped to avoid overwhelming the review queue.

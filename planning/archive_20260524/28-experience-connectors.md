# Experience Connectors: GitHub Merge Hook, MCP Agent Summaries, and Deep Source Links

**Status:** Design doc — no code changes
**Related:** `planning/23-experience-capture-north-star.md`

---

## Context

`planning/23` sketched the plugin concept for passive experience capture — GitHub merge hooks and AI agent session summaries — but left implementation approach unspecified. This document covers how these work as **user-configurable connectors** (parallel to how the Jobs feature is user-initiated), with specific focus on:

1. GitHub merge hook — webhook vs. polling approaches
2. AI agent session summaries — MCP endpoint design
3. Deep source links — storing file/directory-level GitHub URLs on the chunks derived from each event, so Tailorings can cite specific evidence

---

## 1. Connector Model (shared infrastructure)

Connectors are user-visible, user-configured integrations that live in a new "Connections" section of the dashboard (or under My Experience). Each connector:

- Has a setup flow the user completes (webhook secret, OAuth token, etc.)
- Has a visible status: `active | paused | error | pending_setup`
- Has an event log the user can inspect
- Produces ExperienceChunks that are flagged with their connector source and carry `source_urls`

### DB tables (new)

```
ExperienceConnector:
  id (UUID), user_id (FK), connector_type (github_webhook | github_poll | mcp_agent | linear | jira)
  config (JSON — webhook secret, repo filter, branch filter, access token, etc.)
  status (active | paused | error | pending_setup)
  last_event_at, last_error, created_at

ConnectorEvent:
  id (UUID), connector_id (FK), user_id (FK)
  raw_payload (JSON — full webhook body or API response)
  extraction_status (pending | extracted | confirmed | rejected | ingested | skipped)
  skip_reason (nullable text)
  extracted_chunks (JSON array of chunk UUIDs created)
  source_urls (JSON array — file/dir URLs relevant to this event)
  created_at
```

### `source_urls` on ExperienceChunk

Add a new nullable JSON column `source_urls: list[str] | None`. Each URL is a permanent deep link to the evidence behind the claim — GitHub permalink, PR URL, etc. Requires an Alembic migration. Resume-derived chunks have no URLs and remain valid without them.

---

## 2. GitHub Merge Hook (Webhook approach)

### Setup flow

1. User clicks "Add GitHub connector" → selects repo(s) to watch and target branch (default: `main`)
2. Tailord generates a webhook secret and shows the user:
   - Payload URL: `POST https://api.tailord.app/webhooks/github`
   - Secret: `<generated>`
3. User adds the webhook to their repo (Settings → Webhooks). Recommended events: `pull_request` filtered to `closed` + `merged: true`
4. Tailord stores the connector with `status = active`

### Inbound event processing

1. `POST /webhooks/github` — validates HMAC-SHA256 signature against stored secret, returns 200 immediately
2. Background task:
   - Fetch PR data via GitHub API: title, body, `merged_at`, changed file list, linked issue titles
   - Run LLM signal-quality gate (see below)
   - If signal quality is not `low`: create ExperienceChunks with `source_type="github_webhook"`, `source_ref="{repo}#PR{number}"`, `source_urls=[...]`
   - Queue for user review

### LLM signal-quality gate: `PREnrichment`

PR descriptions vary wildly — some are rich ("Implemented exponential backoff with jitter to handle 4xx payment failures"), others are noise ("fix", "wip", "misc changes"). Rather than ingesting everything and letting the user filter, the LLM rates the PR before any chunks are created:

```python
class PREnrichment(BaseModel):
    signal_quality: Literal["high", "medium", "low"]
    skip_reason: str | None          # populated if signal_quality == "low"
    experience_claims: list[str]     # empty if signal_quality == "low"
    detected_stack: list[str]
    project_domain: str
    most_relevant_files: list[str]   # ranked subset of changed_files
```

If `signal_quality == "low"`: no ExperienceChunks are created. The ConnectorEvent is stored with `extraction_status="skipped"` and `skip_reason` visible in the event log. Users can manually promote a skipped event if they disagree. This keeps the review queue clean while preserving auditability.

**LLM context provided:** PR title, description, changed file paths (not code content — we never fetch file contents for privacy/cost reasons), linked issue titles, and additions/deletions count. File paths alone are often enough to infer domain: `backend/app/services/billing/` is self-explanatory; descriptions provide the outcome signal.

### Signal extracted from a merged PR

| Source | Extracted signal |
|--------|-----------------|
| PR title + description | Accomplishment claim(s) |
| Changed file extensions | Stack signals (`.tsx` → React, `alembic/versions/` → DB migrations, `Dockerfile` → containerization) |
| File path structure | Domain signal (`backend/app/services/` → backend, `frontend/src/components/` → UI) |
| Linked issue titles | Outcome / motivation context |

### Source URL capture

For each claim derived, store the most relevant changed files as `source_urls`:

- **PR URL:** `github.com/{owner}/{repo}/pull/{number}`
- **File permalink at merge commit SHA:** `github.com/{owner}/{repo}/blob/{merge_sha}/{filepath}`
- **Directory link** (if the claim is about an architectural area): `github.com/{owner}/{repo}/tree/{merge_sha}/{dir}/`

Rules:
- Store top 1–3 file URLs per claim, not all changed files
- Prefer files whose path names make the claim legible at a glance (e.g., `billing/retry_logic.py` over `utils/helpers.py`)
- LLM's `most_relevant_files` ranking drives selection

---

## 3. GitHub Sync (Polling approach — recommended v1)

### Why polling first

- Lower user friction — they already connected GitHub in the existing flow; no webhook setup needed
- No public inbound endpoint required for local dev
- Catches PRs merged while the webhook was down or before it was set up

### How it works

1. On the existing GitHub connection, record `last_synced_at` (initially = connection time)
2. On trigger: call GitHub API — `GET /repos/{owner}/{repo}/pulls?state=closed&sort=updated&since={last_synced_at}`
3. Filter to `merged: true` only
4. For each new merged PR, run the same extraction pipeline as the webhook approach
5. Capture `source_urls` identically — PR URL + top file permalinks at merge SHA
6. Update `last_synced_at` on the connector record

### Trigger cadence

| Option | Approach | Notes |
|--------|----------|-------|
| On-demand | "Sync GitHub" button in dashboard | Lowest infra cost; transparent to user |
| Periodic | Cron-style background job per user | Higher infra cost; fully passive |
| **Recommended v1** | On-demand button + auto-trigger when user opens My Experience and `last_synced_at` > 7 days ago | Balances cost and freshness |

### Coexistence with webhook

Webhook fires in real-time; polling catches gaps. Deduplication key = PR number per repo — a PR already ingested as a ConnectorEvent is skipped on the next poll.

---

## 4. AI Agent Session Summaries (MCP Endpoint)

### Design

Tailord exposes an MCP server. Users configure it in their agent tool (Claude Code, Cursor, etc.) with their personal API key. One tool is exposed: `capture_session`.

### MCP tool: `capture_session`

```json
{
  "name": "capture_session",
  "description": "Save a summary of this work session to your Tailord experience repository. Tailord will extract experience signals and queue them for your review.",
  "inputSchema": {
    "type": "object",
    "required": ["summary"],
    "properties": {
      "summary": {
        "type": "string",
        "description": "What was accomplished this session (free text)"
      },
      "modified_files": {
        "type": "array",
        "items": { "type": "string" },
        "description": "File paths modified (relative or absolute)"
      },
      "repo_url": {
        "type": "string",
        "description": "GitHub repo URL if applicable"
      },
      "technologies": {
        "type": "array",
        "items": { "type": "string" },
        "description": "Explicit tech signals (optional; LLM also infers)"
      },
      "session_date": {
        "type": "string",
        "description": "ISO date; defaults to today"
      }
    }
  }
}
```

**Output:**
```json
{
  "status": "queued",
  "preview_url": "https://tailord.app/dashboard/experience?review=<event_id>"
}
```

### Processing pipeline

1. `POST /mcp/capture` (authenticated by X-API-Key + X-User-Id) — accepts the tool input
2. Background task:
   - LLM extraction pass → accomplishment claims from `summary`
   - **Source URL capture from `modified_files`:**
     - If `repo_url` is provided and files are repo-relative paths → construct GitHub blob URLs: `{repo_url}/blob/HEAD/{filepath}`
     - If files are absolute local paths → store as-is (human-readable provenance, not clickable links)
     - LLM identifies which files are most relevant to each claim (same ranking heuristic as webhook)
3. Create ConnectorEvent + ExperienceChunks with `source_type="mcp_agent"`, `source_urls=[...]`
4. Return preview URL so the agent can surface it to the user immediately

### Agent integration UX

Users add an MCP server entry to their `~/.claude/settings.json` (or equivalent) pointing to `https://api.tailord.app/mcp` with their personal API key. At end of session, the user says "capture this session" or the agent invokes automatically via a post-session hook. Tailord queues for review; user sees a badge in the dashboard ("3 items to review").

### Structured vs. freeform input

Accept both. Freeform `summary` is always required; structured fields (`modified_files`, `technologies`) are optional enrichment that improves source URL quality and reduces LLM inference burden. Over time, agent tools may generate richer structured summaries — Claude Code already has session context including modified files.

---

## 5. Source Links in Tailorings

### What we store

`source_urls: list[str]` on each ExperienceChunk (new column). Empty array or null for resume/user_input chunks that have no URL provenance.

### What we surface

| Surface | Behavior |
|---------|----------|
| Tailoring output (generated markdown) | When a chunk with `source_urls` is cited, tailoring output can include an inline reference: "…as evidenced in [billing/retry.py](…)" |
| Public tailoring page `/t/{slug}` | Source URLs render as collapsible "evidence" links under each claim section |
| Headless enrichment API | `source_urls` are included in the chunk payload so the job board can surface deep links |

### What we do NOT do

- Do not include source URLs in the LLM prompt — they are metadata, not context
- Do not require source URL presence for chunk validity — resume-derived chunks have no URLs and are equally valid

---

## 6. Confirmation + Review Flow

Both connectors produce chunks that require user review before ingestion (matching `planning/23`'s "confirmation is mandatory for v1" principle).

**Dashboard badge:** "N items to review" (new state in My Experience page)

**Review card per ConnectorEvent:**
- Raw summary or PR description
- Extracted claims
- Source URLs (rendered as links)
- Signal quality rating + skip reason (if skipped)

**User actions:**
- Approve all
- Approve individually
- Edit claim text
- Remove a claim
- Reject the whole event
- Promote a skipped event

Approved chunks merge into the Experience repository immediately. Privacy scrubbing runs before the review card is shown (flags company-identifying terms, customer names).

---

## 7. Sequencing

| Phase | Feature | Notes |
|-------|---------|-------|
| 1 | `source_urls` column on ExperienceChunk + Alembic migration | Prerequisite for everything else |
| 2 | ExperienceConnector + ConnectorEvent DB tables + migration | Shared foundation |
| 3 | GitHub polling ("Sync GitHub" button) | Lowest friction; reuses existing GitHub App auth |
| 4 | Review queue UI (dashboard badge + review card) | Needed before any connector produces visible output |
| 5 | GitHub webhook connector (inbound endpoint + HMAC validation) | Real-time capture; requires public endpoint |
| 6 | MCP server + `capture_session` tool | Agent integration; requires MCP protocol implementation |
| 7 | Source URL surfacing in tailoring output + public tailoring page | Downstream consumer of source_urls data |

This sequencing aligns with `planning/23` — confirmation queue (Phase 4) ships before real-time capture (Phase 5), ensuring no unreviewed data ever silently enters a user's Experience.

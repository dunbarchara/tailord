# Experience Capture — Overview and Canonical Reference

**Date:** 2026-05-24
**Status:** Living reference — update when new surfaces are added or schema evolves.
**Related:** `planning/17-chunk-model.md`, `planning/28-experience-connectors.md`, `planning/23-experience-capture-north-star.md`, `planning/28-experience-claim-management.md`

---

## Purpose

This directory documents the design of every surface through which professional experience enters Tailord. The guiding rule: **every surface must ultimately produce `ExperienceChunk` rows**. The chunk is the atom. Surface docs define how raw input — a file, a webhook payload, a text message, an agent summary — becomes a set of atomic, sourced, embeddable claims.

---

## 1. The Fundamental Unit — `ExperienceChunk`

One table. All chunk types participate equally in cosine similarity retrieval:

```sql
SELECT * FROM experience_chunks
WHERE experience_id = :exp_id
ORDER BY embedding <=> :query_embedding
LIMIT :k
```

The `source_type` column is the discriminator — it controls lifecycle, rendering, and management. It does not control retrieval. Splitting by source type would require UNION ALL on the hottest query in the system.

### Canonical Schema

| Field | Type | Status | Purpose |
|---|---|---|---|
| `id` | UUID | Live | Primary key |
| `experience_id` | UUID FK | Live | Owner (CASCADE delete) |
| `source_type` | enum string | Live | Acquisition method — how it got here |
| `source_ref` | string? | Live | Sub-reference within source (repo name, connector_id, PR number) |
| `claim_type` | enum string | Live | `work_experience \| skill \| project \| education \| other` |
| `content` | string | Live | The atomic claim, self-contained prose |
| `group_key` | string? | Live | Entity grouping — "ACME Corp \| Software Engineer", repo name, project name |
| `date_range` | string? | Live | Human-readable "2020–2023" or "Jan 2024" |
| `technologies` | string[]? | Live | Tech tags extracted at parse time |
| `chunk_metadata` | JSON? | Live | Provenance bag: gap question ref, connector_id, session date, etc. |
| `position` | int | Live | Ordering within experience |
| `embedding` | vector(1536)? | Live | pgvector — populated after background embed run |
| `embedding_model` | string? | Live | Which model produced the embedding |
| `created_at / updated_at` | datetime | Live | Audit trail |
| `source_urls` | string[]? | Planned | Evidence links (PR URL, file permalink, review doc) — metadata only, never sent to LLM |
| `confidence` | enum? | Planned | `high` (user-stated) \| `medium` (LLM-extracted) \| `low` (inferred) |
| `plugin_connection_id` | UUID FK? | Planned | Link to ExperienceConnector row (for plugin sources) |
| `canonical_tag` | string? | Planned | Normalized skill label for faceted search |

### Design Decisions

**Why one table (not sharded by source)**
Retrieval is source-agnostic. The cosine similarity query must search across all source types simultaneously. A per-source table split requires UNION ALL or a materialized view on the most critical query path. The `source_type` column is the discriminator for everything except retrieval.

**Entity vs. source — they are orthogonal**
`source_type` = acquisition method (how the claim entered the system). `group_key` = entity (employer, project, repository). The same entity can accumulate claims from multiple sources: a resume chunk and a gap_response chunk can both carry `group_key = "ACME Corp | Software Engineer"`. This is correct — they are different evidence about the same entity.

**`confidence` and retrieval weighting**
Once the column exists, the retrieval pipeline should post-process results to boost high-confidence chunks. This is a reranking step after cosine retrieval, not a DB-level filter — all chunks participate in retrieval, but high-confidence claims surface higher.

**`source_urls` — metadata, not LLM context**
Never included in the LLM prompt. Rendered as evidence links in the tailoring output and public tailoring page. Resume-derived chunks have no URLs and are equally valid — the absence of `source_urls` is not a quality signal.

**Human approval gate**
Surfaces that produce lower-confidence claims should stage into a ConnectorEvent review queue before chunks are persisted. The user approves, edits, or rejects each event. Confirmed chunks are then embedded and ingested. This is mandatory for v1 of any plugin surface — users must trust the repository before passive capture can be silent.

**Deduplication at ingest**
Before persisting a new chunk: embed the incoming content, query existing chunks for the same user filtered by `claim_type`, apply cosine threshold >= 0.92. Above threshold: route to `DeduplicationCandidate` review queue — never silently merge or drop. The dedup unit is the accomplishment, not the technology ("Reduced latency 40% using Redis" is unique even if Redis is already in the profile).

---

## 2. All Surfaces — Summary Table

| # | Name | `source_type` | Status | Acquisition |
|---|---|---|---|---|
| 1 | Resume | `resume` | Live | File upload → LLM extraction |
| 2 | GitHub Scan | `github` | Live | OAuth + API scan |
| 3 | GitHub On Commit | `plugin_github` | Planned | PR poll (v1) or webhook (v2) |
| 4 | Codebase Offline Scan | `codebase_scan` | Planned | CLI tool → structured JSON upload |
| 5 | Coding Agent Sidecar | `mcp_agent` | Planned | MCP `capture_session` tool |
| 6 | Gap Enrichment | `gap_response` | Live | Post-tailoring Q&A |
| 7 | Text / Messenger | `message` | Planned | In-app, email, SMS, WhatsApp |
| 8 | Direct Input | `user_input` | Live | Dashboard textarea → LLM parse |
| 9 | Performance / Peer Review | `performance_review` | Planned | Paste or generated form |

---

## 3. Cross-Cutting Concerns

### Deduplication

- Ingest-time: embed → cosine similarity check → route above-threshold matches to review queue
- Periodic compaction: weekly or per-N-chunks pass; clusters chunks by `claim_type`, surfaces near-duplicates to user
- Silent merges are forbidden. User review is required for any collapse.
- Dedup key is the accomplishment text, not the technology cluster.
- Context filter: only compare within the same `group_key` if one exists; flat skill chunks (no group_key) compare globally.

### Sensitivity Filtering

Each surface doc defines what gets stripped before LLM processing. Common rules:
- Contact information (phone, email, personal addresses) — strip before storage
- Third-party names (colleagues, customers, clients) — anonymize or strip depending on surface
- Salary / compensation data — strip always
- Internal codenames / unreleased product names — flag for user review

The scrub pass runs before the LLM extraction pass and before the review card is shown to the user.

### LLM Metadata in `chunk_metadata`

All LLM-extracted chunks should include in `chunk_metadata`:
- `llm_model`: model name used for extraction
- `extraction_date`: ISO timestamp

This enables provenance queries ("which claims were extracted by model X?") and supports re-extraction if a prompt improves.

### Entity Tagging and `group_key` Normalization

`group_key` is the entity anchor. Where possible, normalize employer names to a canonical form (avoid "ACME Corp", "ACME Corporation", "Acme" as three different keys for the same entity). Normalization is deferred until `canonical_tag` is built, but the design should not produce obviously divergent keys at ingest time.

### Lifecycle Rules by Source Type

| `source_type` | Deleted when... |
|---|---|
| `resume` | Resume is removed (all resume chunks deleted) |
| `github` | Repo is disconnected (chunks with matching `source_ref` deleted) |
| `user_input` | Per-chunk deletion, or all cleared when user clears input |
| `gap_response` | Only when Experience record is deleted, or user explicitly deletes the chunk |
| `partial_response` | Same as `gap_response` |
| `annotation` | Same as `gap_response` (planned, not built) |
| `message` | Per-chunk deletion (planned) |
| `plugin_github` | Connector deletion (planned) |
| `mcp_agent` | Per-chunk deletion or connector deletion (planned) |
| `performance_review` | Only user-initiated deletion (planned) |

The `delete_resume_chunks`, `delete_github_chunks`, and `delete_user_input_chunks` functions filter by `source_type`. `gap_response`, `partial_response`, and `annotation` chunks are automatically excluded and will not be touched by those functions.

---

## 4. Backend Entry Points — Surface to Chunk Pipeline

| Surface | Endpoint | Notes |
|---|---|---|
| Resume upload | `POST /experience/upload-url` → client PUT → `POST /experience/process` | SSE stream during processing |
| GitHub scan | `POST /experience/github` | Additive merge; preserves resume chunks |
| GitHub on commit | `POST /experience/github/sync` (planned) or `POST /webhooks/github` (planned) | Poll v1; webhook v2 |
| Codebase offline scan | `POST /experience/codebase-scan` (planned) | Accepts structured JSON payload |
| Coding agent sidecar | `POST /mcp/capture` (planned) | Authenticated by X-API-Key + X-User-Id |
| Gap enrichment | `POST /experience/gap-response` | Creates chunk + triggers re-match |
| Text / messenger | `POST /experience/message` (planned) | Ingests raw text; preview before confirm |
| Direct input | `POST /experience/user-input/parse` → `POST /experience/user-input/chunks` | Parse preview before commit |
| Performance review | `POST /experience/performance-review` (planned) | Paste flow or form generation |

---

## 5. Schema Evolution — Prerequisite Order

Before adding any new plugin source type, evaluate these migrations:

| Column / Table | Priority | Rationale |
|---|---|---|
| `source_urls` on `experience_chunks` | High — before plugin sources | Evidence links for PR/file provenance |
| `confidence` on `experience_chunks` | High — before plugin sources | Retrieval weighting, UI warnings |
| `plugin_connection_id` on `experience_chunks` | High — before plugin sources | Attribute plugin chunks to connection |
| `ExperienceConnector` table | High — before plugin sources | Register plugin connections per user |
| `ConnectorEvent` table | High — before plugin sources | Raw payload storage + ingestion lifecycle |
| `DeduplicationCandidate` table | Medium — before dedup review UI | Review queue for above-threshold matches |
| `canonical_tag` on `experience_chunks` | Medium — after dedup is working | Faceted skill search |

Do not add all at once. Add `ExperienceConnector` + `ConnectorEvent` + `plugin_connection_id` + `source_urls` + `confidence` as a single migration block before the first plugin source ships.

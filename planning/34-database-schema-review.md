# Database Schema Review

**Date:** 2026-05-27
**Purpose:** Comprehensive table-by-table reference ahead of sprint planning. Intended as the single source of truth for refactoring decisions — if a column, FK, or relationship looks wrong here, that is the time to flag it.

---

## Table Inventory

| Table | Rows est. | Primary owner | Notes |
|-------|-----------|---------------|-------|
| `users` | per-user | Identity | The root anchor for all user data |
| `experiences` | 1 per user | Ingestion | Pipeline state + raw source data |
| `experience_groups` | many per user | Claims | Parent containers for grouped claims |
| `experience_claims` | many per user | Claims | Atomic experience units; embedded |
| `jobs` | many per user | Tailoring | One per tailoring creation |
| `job_chunks` | many per job | Tailoring | Extracted + scored job requirements |
| `tailorings` | many per user | Tailoring | Generated documents |
| `llm_trigger_log` | many per user | Rate limiting | Sliding-window trigger tracking |
| `tailoring_debug_logs` | many per tailoring | Observability | Generation telemetry (scaffold) |

---

## `users`

**Purpose:** Identity, preferences, integration tokens.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | UUID PK | no | Internal ID used as FK anchor throughout |
| `google_sub` | varchar UNIQUE | no | Google OAuth subject — the stable external identity |
| `email` | varchar | no | |
| `name` | varchar | yes | From Google OAuth |
| `preferred_first_name` | varchar | yes | User-set; overrides `name` for LLM prompts |
| `preferred_last_name` | varchar | yes | |
| `pronouns` | varchar | yes | Used in LLM advocacy blurbs ("she built…") |
| `username_slug` | varchar UNIQUE | yes | Public profile URL segment `/u/<slug>` |
| `avatar_url` | varchar | yes | |
| `profile_public` | boolean | no | `false` default — explicit opt-in |
| `status` | varchar | no | `pending` \| `approved` — admin gate |
| `is_admin` | boolean | no | |
| `notion_access_token` | varchar | yes | Notion OAuth |
| `notion_bot_id` | varchar | yes | |
| `notion_workspace_id` | varchar | yes | |
| `notion_workspace_name` | varchar | yes | |
| `notion_parent_page_id` | varchar | yes | |
| `created_at` | timestamptz | no | |

**Relationships out:**
- → `experiences` (1:1)
- → `jobs` (1:many)
- → `tailorings` (1:many)
- → `experience_claims` (1:many, cascade delete)
- → `experience_groups` (1:many, cascade delete)

**Questions / candidates for change:**
- Notion fields (5 columns) are only populated for Notion-connected users. Could be extracted to a `user_integrations` table if more integrations follow the same pattern — not worth it yet unless Notion fields become more complex.
- No `deleted_at` soft-delete. Deletion is hard (cascades to all claims, tailorings, etc.).

---

## `experiences`

**Purpose:** Ingestion pipeline state and raw source data. One row per user, created on first upload or GitHub connect.

> Not "an experience" in the product sense. It is the **data ingestion record** — what sources the user has connected, what pipeline state those are in, and what LLM-extracted output came out before normalization into claims. A future rename to `profile_records` is under consideration (see planning/32-experience-claim-schema.md deferred section).

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | UUID PK | no | |
| `user_id` | UUID FK → users UNIQUE | no | 1:1 enforced at DB level |
| `storage_key` | varchar | yes | Blob storage key for uploaded file; null if no file |
| `filename` | varchar | yes | Original filename for display |
| `status` | varchar | no | `pending` \| `processing` \| `ready` \| `error` |
| `extracted_profile` | JSONB | yes | LLM extraction output keyed by source: `{ "resume": {...}, "github": {...} }` |
| `raw_resume_text` | text | yes | Normalized text extracted from the uploaded file |
| `error_message` | varchar | yes | Human-readable error for UI display |
| `github_username` | varchar | yes | Connected GitHub username |
| `github_repos` | JSONB | yes | `[{ name, description, language, star_count, pushed_at, scanned_at }]` |
| `github_repo_details` | JSONB | yes | Enriched per-repo LLM output (README summary, detected stack, experience claims). Large. |
| `user_input_text` | text | yes | Plain-text blob of user's direct input |
| `uploaded_at` | timestamptz | yes | Set when file upload completes |
| `processed_at` | timestamptz | yes | Set when processing pipeline completes |
| `last_process_requested_at` | timestamptz | yes | Set at request time — used for cooldown check |

**Relationships out:** none (claims and groups now point to `users` directly)

**Questions / candidates for change:**
- `user_input_text` — currently a plain text blob stored here for historical reference. The actual claims derived from it live in `experience_claims` with `source_type="user_input"`. These two are not kept in sync — `user_input_text` is never updated after claims are created. Consider: should it be dropped? Or kept as the raw input log?
- `extracted_profile` JSONB — this is a pipeline artifact (LLM extraction output). It duplicates data that has been normalized into claims. Long-term, if claims become the authoritative source, this could be deprecated. Not ready yet — the tailoring generator still reads from it.
- `github_repo_details` — potentially large JSONB (per-repo README summaries, stack signals, etc.). Worth monitoring row sizes in production.
- The "profile record rename" decision: see open option in planning docs.

---

## `experience_groups`

**Purpose:** Parent containers for related claims. Context only — never embedded.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | UUID PK | no | |
| `user_id` | UUID FK → users | no | CASCADE delete; indexed |
| `group_type` | varchar(30) | no | `role` \| `project` \| `repository` \| `education` \| `custom` |
| `name` | varchar(255) | no | Display name. Employer for roles, repo name for repositories, etc. |
| `start_date` | varchar(50) | yes | MM/YYYY |
| `end_date` | varchar(50) | yes | MM/YYYY or null (= present) |
| `location` | varchar(255) | yes | Relevant for roles and education |
| `type_meta` | JSONB | yes | Type-specific fields (title, degree, technologies, URL, etc.) |
| `source_type` | varchar(30) | no | `resume` \| `github` \| `user_input` \| `annotation` |
| `source_ref` | varchar(255) | yes | Repo name for github; null otherwise |
| `created_at` | timestamptz | no | |
| `updated_at` | timestamptz | no | |

**Relationships out:**
- → `experience_claims` (1:many, SET NULL on group delete — claims become ungrouped)

**Questions / candidates for change:**
- Groups are currently **write-only by the pipeline** — there is no API to create, update, or delete groups manually. Building a groups CRUD API is deferred.
- `group_key` on `experience_claims` (the old denormalized string) is still present and will shadow group data until backfill is confirmed. Dropping it is explicitly deferred.
- No `position` column — groups are ordered by `created_at` / insertion order. If drag-and-drop reordering becomes a feature, a `position` column will be needed.

---

## `experience_claims`

**Purpose:** Atomic, source-traceable units of professional experience. One row per bullet / skill / education fact / gap answer. Everything flows through here: cosine retrieval, gap analysis, tailoring context.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | UUID PK | no | | |
| `user_id` | UUID FK → users | no | | CASCADE delete; indexed |
| `group_id` | UUID FK → experience_groups | yes | null | SET NULL on group delete |
| `source_type` | varchar(30) | no | | `resume` \| `github` \| `user_input` \| `gap_response` \| `partial_response` \| `annotation` |
| `source_ref` | varchar(255) | yes | null | Repo name for github; null otherwise |
| `claim_type` | varchar(30) | no | | `work_experience` \| `skill` \| `project` \| `education` \| `other` |
| `content` | text | no | | The claim text |
| `group_key` | varchar(255) | yes | null | **Deprecated** denormalized `"Company \| Title"` string. Drop after `group_id` backfill. |
| `date_range` | varchar(100) | yes | null | Temporal context for ungrouped claims |
| `technologies` | JSONB | yes | null | `["React", "PostgreSQL"]` |
| `confidence` | varchar(20) | no | `medium` | `high` \| `medium` \| `low` |
| `status` | varchar(20) | no | `active` | `active` \| `archived` |
| `provenance_url` | varchar(500) | yes | null | Clickable evidence link |
| `provenance_label` | varchar(255) | yes | null | Human-readable label for URL |
| `tags` | JSONB | yes | null | `["performance", "team-leadership"]` — no fixed taxonomy |
| `chunk_metadata` | JSONB | yes | null | Gap/partial/annotation provenance |
| `position` | integer | no | | Sort order; unique within (user_id, source_type) by convention |
| `embedding` | vector(1536) | yes | null | pgvector; null until embed run; not in API responses |
| `embedding_model` | varchar(100) | yes | null | Model name used for current embedding |
| `created_at` | timestamptz | no | | |
| `updated_at` | timestamptz | no | | |

**Questions / candidates for change:**
- `group_key` — actively deprecated. Drop once group_id backfill is confirmed across all environments.
- `position` is a global int across all source types. Insertion appends to `MAX(position) + 1` per user. This works but has a gap risk (deletes leave holes). For rendering purposes, order by position is always relative, so holes are fine.
- `status: "archived"` — implemented in schema but the soft-delete flow is not yet wired in the API or UI. Currently claims are always hard-deleted.
- `tags` — no validation, no taxonomy. Intentionally flexible. If search/filter on tags becomes a feature, a separate `claim_tags` table with a FK would be more queryable.
- `chunk_metadata` naming is legacy (from "chunk" era). Functionally correct; rename is cosmetic only.
- `source_type="annotation"` — in schema docstring and lifecycle table but not yet created by any pipeline code.

---

## `jobs`

**Purpose:** One job posting per tailoring creation. Contains the URL and extracted structured data from the posting.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | UUID PK | no | |
| `user_id` | UUID FK → users | yes | Nullable for backwards compat with pre-auth historical rows |
| `job_url` | varchar | yes | Source URL; null for manually entered jobs |
| `raw_description` | text | yes | Raw description text for manual jobs |
| `extracted_job` | JSONB | yes | `{ title, company, requirements: [] }` |
| `created_at` | timestamptz | no | |

**Relationships out:**
- → `job_chunks` (1:many, cascade delete)
- → `tailorings` (1:many)

**Questions / candidates for change:**
- `user_id` is nullable for legacy reasons only. All new rows have a `user_id`. A migration to make it non-nullable + add a NOT NULL constraint is safe once legacy rows are confirmed to be migrated or irrelevant.
- `raw_description` — stored for manual jobs, but not used after `extracted_job` is populated. Consider whether it has any long-term audit value.
- `extracted_job` contains `requirements` as a flat list of strings — this was the pre-chunk model. The `job_chunks` table is now authoritative for requirements. The `extracted_job.requirements` list is only used as a fallback if chunk enrichment fails.
- A `Job` is shared across regenerations of the same tailoring (the `Tailoring` FK points back to the same `Job`). If the URL changes on regen, a new `Job` is created.

---

## `job_chunks`

**Purpose:** Extracted and LLM-scored requirements from a job posting. One row per requirement/paragraph/header.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | UUID PK | no | |
| `job_id` | UUID FK → jobs | no | CASCADE delete; indexed |
| `chunk_type` | varchar(20) | no | `requirement` \| `paragraph` \| `header` |
| `content` | text | no | The chunk text as extracted |
| `scored_content` | text | yes | The content that was actually scored (may differ post-edit) |
| `position` | integer | no | Extraction order |
| `section` | varchar(255) | yes | Section heading the chunk appeared under |
| `match_score` | integer | yes | `-1` (not scored) \| `0` (no match) \| `1` (partial) \| `2` (strong) |
| `match_rationale` | text | yes | LLM's scoring rationale |
| `advocacy_blurb` | text | yes | LLM-generated 1–2 sentence advocacy statement (score ≥ 1 only) |
| `experience_source` | varchar(50) | yes | **Deprecated.** Single source string. Replaced by `experience_sources`. |
| `experience_sources` | JSONB | yes | `["resume", "github", "gap_response"]` — multi-source attribution |
| `should_render` | boolean | no | LLM flag: display this requirement in the tailoring? |
| `is_requirement` | boolean | no | True for `requirement` type; false for headers/paragraphs |
| `enriched_at` | timestamptz | yes | Set when scoring completes |
| `embedding` | vector(1536) | yes | pgvector; populated by embed_job_chunks |
| `embedding_model` | varchar(100) | yes | |

**Questions / candidates for change:**
- `experience_source` — deprecated, `experience_sources` is the live column. Remove `experience_source` in a future migration once frontend no longer reads it (check `_serialize_chunk` in `tailorings.py`).
- `scored_content` vs `content` split: `scored_content` was added to snapshot the content at scoring time in case the user edits the chunk. In practice, the UI does not currently allow editing job chunks. This column may be redundant.
- `match_score = -1` means "not evaluated" — this includes both scoring errors and header/paragraph chunks. Consider a separate `evaluation_status` column to distinguish "skipped by design" from "failed to score."

---

## `tailorings`

**Purpose:** AI-generated document mapping a candidate to a specific job. The primary product artifact.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | UUID PK | no | |
| `user_id` | UUID FK → users | no | |
| `job_id` | UUID FK → jobs | no | |
| `generated_output` | text | yes | Final markdown letter |
| `letter_content` | JSONB | yes | Structured letter; null for pre-migration rows |
| `model` | varchar | yes | LLM model name used |
| `generation_status` | varchar | no | `pending` \| `generating` \| `ready` \| `error` |
| `generation_stage` | varchar | yes | `extracting` \| `enriching` \| `generating` (null when idle) |
| `generation_error` | text | yes | User-facing error message |
| `generation_started_at` | timestamptz | yes | |
| `generated_at` | timestamptz | yes | Set on completion |
| `last_regenerated_at` | timestamptz | yes | Set on regen trigger |
| `enrichment_status` | varchar | no | `pending` \| `complete` \| `error` |
| `matching_mode` | varchar | yes | `vector` \| `llm`; null for pre-migration rows |
| `generation_duration_ms` | integer | yes | Wall-clock time for generation phase |
| `chunk_batch_count` | integer | yes | Number of LLM scoring batches |
| `chunk_error_count` | integer | yes | Number of batches that failed |
| `profile_snapshot` | text | yes | Exact formatted profile passed to LLM at generation time |
| `gap_analysis` | JSONB | yes | `ProfileGapWithChunk[]`; null until gap analysis runs |
| `gap_analysis_status` | varchar | no | `pending` \| `complete` |
| `letter_public` | boolean | no | |
| `posting_public` | boolean | no | |
| `public_slug` | varchar | yes | UNIQUE per user (`uq_tailorings_user_public_slug`) |
| `notion_container_page_id` | varchar | yes | |
| `notion_page_id` | varchar | yes | |
| `notion_page_url` | varchar | yes | |
| `notion_posting_page_id` | varchar | yes | |
| `notion_posting_page_url` | varchar | yes | |
| `created_at` | timestamptz | no | |

**Questions / candidates for change:**
- Notion fields (5 columns) are only populated for Notion-connected users. Same pattern as `users` — extraction to a separate table would only make sense if Notion becomes significantly more complex.
- `enrichment_status` on `Tailoring` — this is redundant with `generation_status` in most flows (enrichment runs inline during generation). It exists because enrichment used to be a separate async step. Consider collapsing into `generation_status`.
- `profile_snapshot` — a text blob of the formatted profile at generation time. Useful for debug/audit. No API exposure; only visible in the debug panel.
- `gap_analysis_status` has only two values and is always set to `complete` by `run_gap_analysis` regardless of success/failure. The real signal is whether `gap_analysis` is null or not.
- `letter_public` and `posting_public` are separate flags allowing partial sharing. `is_public` is a hybrid property (`letter_public OR posting_public`).

---

## `llm_trigger_log`

**Purpose:** One row per LLM pipeline trigger. Used for sliding-window rate limiting. Records `tailoring_create`, `tailoring_regen`, and `experience_process` events.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | UUID PK | no | |
| `user_id` | UUID FK → users | no | CASCADE delete; indexed |
| `event_type` | varchar(50) | no | `tailoring_create` \| `tailoring_regen` \| `experience_process` |
| `created_at` | timestamptz | no | |

**Questions / candidates for change:**
- No cleanup / TTL. This table grows forever. Old rows (>24h) have no query value. A periodic cleanup job or PostgreSQL partitioning by day would keep it lean.
- `experience_process` events are tracked but not currently rate-limited against (the cooldown is implemented via `last_process_requested_at` on `experiences`, not this table). Decide whether to consolidate or keep both mechanisms.

---

## `tailoring_debug_logs`

**Purpose:** Schema scaffold for per-generation telemetry. Currently populated with basic events (`generation_started`, `phase_complete`, `generation_complete`, `generation_error`, `phase_error`).

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | UUID PK | no | |
| `tailoring_id` | UUID FK → tailorings | no | CASCADE delete |
| `event_type` | varchar(50) | no | |
| `payload` | JSONB | yes | Arbitrary event data |
| `created_at` | timestamptz | no | |

**Questions / candidates for change:**
- No `user_id` — only reachable via `tailoring_id`. For analytics queries spanning users, a `user_id` denorm would save a join.
- No cleanup / TTL — same concern as `llm_trigger_log`.
- `event_type` values are not enforced at the DB level (no CHECK constraint or enum). A mistake in a caller would silently write a garbage type.

---

## Cross-cutting observations

### Ownership scoping
All user-scoped tables now anchor directly to `users.id`:
- `experiences` → `users.id` (unique)
- `experience_claims` → `users.id`
- `experience_groups` → `users.id`
- `jobs` → `users.id`
- `tailorings` → `users.id`
- `llm_trigger_log` → `users.id`

The two-step experience lookup (`user_id → experience.id → claim`) is now gone. Every ownership check is a single-hop `WHERE user_id = ?`.

### Cascade behaviour

| Child table | On user delete | On parent delete |
|-------------|---------------|-----------------|
| `experiences` | CASCADE | — |
| `experience_groups` | CASCADE | — |
| `experience_claims` | CASCADE | group_id SET NULL |
| `jobs` | — (user_id nullable) | — |
| `tailorings` | — (no cascade; user_id not FK-constrained on delete) | — |
| `job_chunks` | — | jobs CASCADE |
| `llm_trigger_log` | CASCADE | — |
| `tailoring_debug_logs` | — | tailorings CASCADE |

> Note: `tailorings` does not cascade-delete when a user is deleted. This is a gap — deleting a user would orphan their tailorings. If hard user deletion becomes a product feature, this needs a migration.

### Nullable FKs
- `jobs.user_id` — nullable for legacy reasons. Safe to make non-nullable after confirming no null rows in production.
- `experience_claims.group_id` — intentionally nullable (ungrouped claims).

### String-typed enums
Several status/type columns use `varchar` with application-level validation rather than PostgreSQL `ENUM` types. This makes migrations easier (no `ALTER TYPE` required) but loses DB-level constraint enforcement. Consistent pattern — not a problem, just a trade-off to be aware of.

### Missing indexes
The following filter patterns are used in hot paths but may not have explicit indexes (worth verifying with `\d` or `pg_indexes`):
- `experience_claims` by `(user_id, source_type)` — used in bulk delete operations
- `experience_claims` by `(user_id, status)` — if archived filtering lands
- `tailorings` by `(user_id, generation_status)` — dashboard list query

---

## Decisions still open

| Decision | Options | Blocker |
|----------|---------|---------|
| Rename `experiences` → `profile_records` | Yes / No | No — cosmetic, can be done any sprint |
| Drop `group_key` from `experience_claims` | After backfill confirmed | Needs `group_id` population in all writers |
| Make `jobs.user_id` non-nullable | After null-row audit | One query in prod to confirm |
| Add cleanup for `llm_trigger_log` | Cron job / partition / TTL | No urgency; defer until table size is visible |
| Drop `experience_source` from `job_chunks` | After frontend audit | Check `_serialize_chunk` in `tailorings.py` |
| Drop `user_input_text` from `experiences` | After audit of read sites | Low priority; data is redundant with claims |

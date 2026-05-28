# Database Schema Review

**Date:** 2026-05-27
**Purpose:** Comprehensive table-by-table reference ahead of sprint planning. Intended as the single source of truth for refactoring decisions — if a column, FK, or relationship looks wrong here, that is the time to flag it.

---

## Table Inventory

| Table | Rows est. | Primary owner | Notes |
|-------|-----------|---------------|-------|
| `users` | per-user | Identity | Root anchor; identity/auth fields extracted to satellite tables |
| `auth_identities` | 1+ per user | Identity | Provider-neutral OAuth subjects; replaces `users.google_sub` |
| `user_profiles` | 1 per user | Identity | Display prefs + public profile; replaces inline fields on `users` |
| `user_integrations` | 0–N per user | Identity | Per-user OAuth tokens (Notion now; GitHub future) |
| `experience_sources` | 1+ per user | Ingestion | One row per (user_id, source_type); replaces monolithic `experiences` table |
| `experience_groups` | many per user | Claims | Parent containers for grouped claims |
| `experience_claims` | many per user | Claims | Atomic experience units; embedded |
| `jobs` | many per user | Tailoring | One per tailoring creation |
| `job_chunks` | many per job | Tailoring | Extracted + scored job requirements |
| `tailorings` | many per user | Tailoring | Generated documents |
| `llm_trigger_log` | many per user | Rate limiting | Sliding-window trigger tracking |
| `tailoring_debug_logs` | many per tailoring | Observability | Generation telemetry (scaffold) |

---

## `users`

**Purpose:** Root identity anchor only. All auth, profile, and integration fields extracted to satellite tables via migration `a7b8c9d0e1f2`.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | UUID PK | no | Internal ID used as FK anchor throughout |
| `email` | varchar | yes | Nullable — cleared on tombstone |
| `name` | varchar | yes | From OAuth; cleared on tombstone |
| `status` | varchar | no | `pending` \| `approved` — admin gate |
| `is_admin` | boolean | no | |
| `created_at` | timestamptz | no | |
| `updated_at` | timestamptz | yes | Set on any mutation |
| `deleted_at` | timestamptz | yes | Set on account deletion (tombstone); PII cleared at same time |

**Relationships out:**
- → `auth_identities` (1:many, cascade delete; selectin-loaded)
- → `user_profiles` (1:1, cascade delete; selectin-loaded)
- → `user_integrations` (1:many, cascade delete; selectin-loaded)
- → `experience_sources` (1:many, cascade delete; selectin-loaded)
- → `jobs` (1:many)
- → `tailorings` (1:many)
- → `experience_claims` (1:many, cascade delete)
- → `experience_groups` (1:many, cascade delete)

**Delete behaviour (v1):** `DELETE /users/me` hard-cascades all user data (tailorings, jobs, experience, claims, groups, integrations, identities, profile), then sets `deleted_at` and clears `email`/`name` on the row as a tombstone. Row is kept indefinitely for platform metrics (account lifetime, churn cohorts). Hard user deletion is now a product feature with a safe implementation.

---

## `auth_identities`

**Purpose:** Provider-neutral OAuth subjects. One row per (provider, subject) pair. Replaces `users.google_sub`. Designed to support multiple auth providers per user.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | UUID PK | no | |
| `user_id` | UUID FK → users | no | CASCADE delete; indexed |
| `provider` | varchar(50) | no | `google` now; future: `linkedin`, `magic_link` |
| `subject` | varchar | no | `google_sub` for google; email for magic_link |
| `email` | varchar | yes | Provider-supplied email at auth time |
| `connected_at` | timestamptz | no | |
| `updated_at` | timestamptz | no | |

**Constraints:** UNIQUE `(provider, subject)`

**Identity lookup pattern:** `X-User-Id` header = google_sub. Backend: `AuthIdentity.query(provider="google", subject=x_user_id)` → loads User. Frontend/header contract unchanged.

---

## `user_profiles`

**Purpose:** Display preferences and public profile settings. Exactly 1 row per user. Replaces the inline profile fields on `users`. Loaded via `lazy="selectin"` — always co-loaded with User.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | UUID PK | no | |
| `user_id` | UUID FK → users | no | CASCADE delete; UNIQUE (1:1) |
| `preferred_first_name` | varchar | yes | User-set display name |
| `preferred_last_name` | varchar | yes | |
| `pronouns` | varchar | yes | Used in LLM advocacy blurbs |
| `avatar_url` | varchar | yes | Provider-supplied; updated on every login |
| `username_slug` | varchar UNIQUE | yes | Public profile URL segment `/u/<slug>`; indexed |
| `profile_public` | boolean | no | `false` default — explicit opt-in |
| `communication_email` | varchar | yes | Future: digest/notification emails separate from auth email |
| `created_at` | timestamptz | no | |
| `updated_at` | timestamptz | no | |

---

## `user_integrations`

**Purpose:** Per-user OAuth tokens and metadata for external service integrations. One row per (user_id, provider) pair. Replaces the 5 `notion_*` columns on `users`. Designed to absorb future integrations (GitHub per-user OAuth, Jira, etc.) without schema changes. Loaded via `lazy="selectin"`.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | UUID PK | no | |
| `user_id` | UUID FK → users | no | CASCADE delete; indexed |
| `provider` | varchar(50) | no | `notion` now; future: `github`, `jira` |
| `credentials` | Text | yes | `{access_token, refresh_token?, expires_at?}` — **never exposed in API responses**; encrypted at rest via `EncryptedJSON` (Fernet, `backend/app/core/crypto.py`); set `FIELD_ENCRYPTION_KEY` in env |
| `metadata` | JSONB | yes | Provider-specific non-secret data. Notion: `{bot_id, workspace_id, workspace_name, parent_page_id}` |
| `connected_at` | timestamptz | no | |
| `updated_at` | timestamptz | no | |

**Constraints:** UNIQUE `(user_id, provider)`

**Encryption:** `credentials` encrypted at rest via `EncryptedJSON` TypeDecorator (Fernet, migration `c5d6e7f8a9b0`). Column type changed JSONB → Text. Set `FIELD_ENCRYPTION_KEY` env var; unset = plaintext with warning (local dev only). Legacy plaintext rows read transparently during migration period.

---

## `experience_sources`

**Purpose:** Ingestion pipeline state and raw source data. One row per `(user_id, source_type)` pair. Replaces the monolithic `experiences` table (dropped in migration `b4d5e6f7a8b9`). Each source tracks its own connection and sync state independently. Profile data is assembled on demand via `sources_to_profile_dict()` in `profile_formatter.py`.

> Not "an experience" in the product sense. Each row is a **data ingestion surface** — a specific source the user has connected (resume, GitHub, etc.), its pipeline state, and the LLM-extracted output for that surface before normalization into claims.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | UUID PK | no | |
| `user_id` | UUID FK → users | no | CASCADE delete; indexed |
| `source_type` | varchar(30) | no | `resume` \| `github`; future: `linear`, `messenger`, etc. |
| `connection_status` | varchar(20) | no | `connected` \| `disconnected` \| `error`; default `connected` |
| `sync_status` | varchar(20) | no | `idle` \| `syncing` \| `error`; default `idle` |
| `last_synced_at` | timestamptz | yes | Set when a sync/process completes |
| `last_requested_at` | timestamptz | yes | Cooldown anchor (was `last_process_requested_at` on `experiences`) |
| `error_message` | varchar | yes | Human-readable error for UI display |
| `config` | JSONB | yes | Surface connection config (non-secret). Resume: `{storage_key, filename}`. GitHub: `{username}` |
| `source_data` | JSONB | yes | Pipeline artifacts + extracted content. Resume: `{extracted, raw_text, corrections}`. GitHub: `{extracted, repos, repo_details}` |
| `created_at` | timestamptz | no | |
| `updated_at` | timestamptz | no | Set on any mutation |

**Constraints:** UNIQUE `(user_id, source_type)`

**Relationships out:** none (claims and groups point to `users` directly)

**Profile assembly:** `sources_to_profile_dict(user.experience_sources)` iterates rows and assembles the legacy `{resume, github, corrections}` dict used by `format_sourced_profile()` and all LLM call sites. Callers do not need to know which row holds which data.

**Questions / candidates for change:**
- `source_data` is a single JSONB column for all pipeline artifacts. For resume sources this includes `raw_text` (potentially large); for GitHub sources it includes `repo_details` (per-repo README summaries — potentially very large). Worth monitoring row sizes in production.
- `config.storage_key` for resume sources exposes the blob storage key inline. This is intentional (non-secret) but worth noting.
- The `corrections` sub-key in `source_data.resume` is a legacy field from user-edited profile overrides. It is not currently written by any pipeline code and may be vestigial.

---

## `experience_groups`

**Purpose:** Parent containers for related claims. Context only — never embedded. Migration `f3c4d5e6a7b8` added ordering, provenance, and tag columns.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | UUID PK | no | |
| `user_id` | UUID FK → users | no | CASCADE delete; indexed |
| `group_type` | varchar(30) | no | `role` \| `project` \| `repository` \| `education` \| `custom` |
| `name` | varchar(255) | no | Display name. Employer for roles, repo name for repositories, etc. |
| `start_date` | varchar(50) | yes | MM/YYYY |
| `end_date` | varchar(50) | yes | MM/YYYY or null (= present) |
| `location` | varchar(255) | yes | Relevant for roles and education |
| `type_meta` | **JSONB** | yes | Type-specific fields (title, degree, technologies, URL, etc.) — was `JSON`, cast to JSONB in `f3c4d5e6a7b8` |
| `source_type` | varchar(30) | no | `resume` \| `github` \| `user_input` \| `annotation` |
| `source_ref` | varchar(255) | yes | Repo name for github; null otherwise |
| `position` | integer | yes | Ordered display position within user's group list; backfilled from `created_at` order; null for rows predating the migration |
| `provenance_url` | varchar(500) | yes | Clickable evidence link for the group (e.g. GitHub org URL) |
| `provenance_label` | varchar(255) | yes | Human-readable label for provenance_url |
| `tags` | JSONB | yes | Group-level tags propagated to claims during retrieval (e.g. `["fintech", "open_source"]`) |
| `description` | text | yes | Free-text context for `custom` group type — name alone isn't enough LLM context |
| `created_at` | timestamptz | no | |
| `updated_at` | timestamptz | no | |

**Relationships out:**
- → `experience_claims` (1:many, SET NULL on group delete — claims become ungrouped)

**Questions / candidates for change:**
- Groups are currently **write-only by the pipeline** — there is no API to create, update, or delete groups manually. Building a groups CRUD API is deferred.
- `group_key` on `experience_claims` (the old denormalized string) is still present and will shadow group data until backfill is confirmed. Dropping it is explicitly deferred (Phase 5 of schema cleanup sprint).
- `position` is nullable; existing rows were backfilled from `created_at` order at migration time.

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
| `keywords` | JSON | yes | null | `["React", "PostgreSQL"]` — formerly `technologies`, renamed in `e2b3c4d5f6a7` for industry neutrality |
| `confidence` | varchar(20) | no | `medium` | `high` \| `medium` \| `low` |
| `status` | varchar(20) | no | `active` | `pending` \| `active` \| `archived` — `pending` reserved for silent-capture pipeline |
| `tags` | JSON | yes | null | `["performance", "team-leadership"]` — no fixed taxonomy |
| `provenance_metadata` | JSONB | yes | null | Consolidated provenance. Replaces `chunk_metadata` + `provenance_url` + `provenance_label` (migration `e2b3c4d5f6a7`). Gap/partial: `{question, job_chunk_id, tailoring_id}`; annotation (future): `{parent_claim_id}` |
| `original_content` | text | yes | null | Set on first user edit; null = never edited. Enables revert to extracted content. |
| `merged_from` | JSONB | yes | null | Set by dedup pipeline: `[{id, source_type, content_snapshot}]`. Null for normal claims. |
| `position` | integer | no | | Sort order; unique within (user_id, source_type) by convention |
| `embedding` | vector(1536) | yes | null | pgvector; null until embed run; not in API responses |
| `embedding_model` | varchar(100) | yes | null | Model name used for current embedding |
| `created_at` | timestamptz | no | | |
| `updated_at` | timestamptz | no | | |

**Questions / candidates for change:**
- `group_key` — actively deprecated. Drop once group_id backfill is confirmed across all environments. Tracked as Phase 5 of schema cleanup sprint.
- `position` is a global int across all source types. Insertion appends to `MAX(position) + 1` per user. This works but has a gap risk (deletes leave holes). For rendering purposes, order by position is always relative, so holes are fine.
- `status: "archived"` — API PATCH now accepts `status` updates (`active` | `archived`). `pending` status is reserved for pipeline use only. Hard-delete still the primary delete path.
- `tags` — no validation, no taxonomy. Intentionally flexible. If search/filter on tags becomes a feature, a separate `claim_tags` table with a FK would be more queryable.
- `source_type="annotation"` — in schema docstring and lifecycle table but not yet created by any pipeline code.
- `chunk_matcher.py` retrieval uses `status == "active"` allowlist — excludes both `pending` (silent-capture, unreviewed) and `archived` (user-dismissed) claims from LLM context.

---

## `jobs`

**Purpose:** One job posting per tailoring creation. Contains the URL and extracted structured data from the posting.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | UUID PK | no | |
| `user_id` | UUID FK → users | **no** | Made non-nullable in migration `a4b5c6d7e8f9` — confirmed 0 null rows in production before applying |
| `job_url` | varchar | yes | Source URL; null for manually entered jobs |
| `raw_description` | text | yes | Raw description text for manual jobs |
| `extracted_job` | JSONB | yes | `{ title, company, requirements: [] }` |
| `created_at` | timestamptz | no | |

**Relationships out:**
- → `job_chunks` (1:many, cascade delete)
- → `tailorings` (1:many)

**Questions / candidates for change:**
- `user_id` was nullable for legacy reasons. Made non-nullable in migration `a4b5c6d7e8f9`.
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
| `experience_sources` | JSONB | yes | `["resume", "github", "gap_response"]` — multi-source attribution. Replaced `experience_source` (dropped in migration `d1a2b3c4e5f6`) |
| `should_render` | boolean | no | LLM flag: display this requirement in the tailoring? |
| `is_requirement` | boolean | no | True for `requirement` type; false for headers/paragraphs |
| `enriched_at` | timestamptz | yes | Set when scoring completes |
| `embedding` | vector(1536) | yes | pgvector; populated by embed_job_chunks |
| `embedding_model` | varchar(100) | yes | |

**Questions / candidates for change:**
- `experience_source` — dropped in migration `d1a2b3c4e5f6`. `experience_sources` (array) is the only source attribution column.
- `scored_content` vs `content` split: `scored_content` was added to snapshot the content at scoring time in case the user edits the chunk. In practice, the UI does not currently allow editing job chunks. This column may be redundant.
- `match_score = -1` means "not evaluated" — this includes both scoring errors and header/paragraph chunks. Consider a separate `evaluation_status` column to distinguish "skipped by design" from "failed to score."

---

## `tailorings`

**Purpose:** AI-generated document mapping a candidate to a specific job. The primary product artifact.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | UUID PK | no | |
| `user_id` | UUID FK → users | no | ON DELETE CASCADE (added migration `a4b5c6d7e8f9`) |
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
- TTL cleanup: rows older than 30 days are deleted as a `BackgroundTasks` call on every tailoring create/regen (amortized). See `_cleanup_old_trigger_logs` in `tailorings.py`.
- `experience_process` events are tracked but not currently rate-limited against (the cooldown is implemented via `last_requested_at` on `experience_sources`, not this table). Decide whether to consolidate or keep both mechanisms.

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
All user-scoped tables anchor directly to `users.id`:
- `auth_identities` → `users.id` (cascade)
- `user_profiles` → `users.id` (1:1, cascade)
- `user_integrations` → `users.id` (cascade)
- `experience_sources` → `users.id` (cascade)
- `experience_claims` → `users.id`
- `experience_groups` → `users.id`
- `jobs` → `users.id`
- `tailorings` → `users.id`
- `llm_trigger_log` → `users.id`

Every ownership check is a single-hop `WHERE user_id = ?`.

### Cascade behaviour

| Child table | On user delete (hard) | On parent delete |
|-------------|----------------------|-----------------|
| `auth_identities` | CASCADE | — |
| `user_profiles` | CASCADE | — |
| `user_integrations` | CASCADE | — |
| `experience_sources` | CASCADE | — |
| `experience_groups` | CASCADE | — |
| `experience_claims` | CASCADE | group_id SET NULL |
| `jobs` | — (user_id non-nullable; app code deletes jobs before user row) | — |
| `tailorings` | CASCADE (added migration `a4b5c6d7e8f9`) | — |
| `job_chunks` | — | jobs CASCADE |
| `llm_trigger_log` | CASCADE | — |
| `tailoring_debug_logs` | — | tailorings CASCADE |

> Note: `tailorings` now cascade-deletes on user delete (migration `a4b5c6d7e8f9`). `jobs` does not — `DELETE /users/me` handles jobs explicitly in application code. `jobs.user_id` is non-nullable as of the same migration.

### Nullable FKs
- `jobs.user_id` — made non-nullable in migration `a4b5c6d7e8f9`.
- `experience_claims.group_id` — intentionally nullable (ungrouped claims).

### String-typed enums
Several status/type columns use `varchar` with application-level validation rather than PostgreSQL `ENUM` types. This makes migrations easier (no `ALTER TYPE` required) but loses DB-level constraint enforcement. Consistent pattern — not a problem, just a trade-off to be aware of.

### Missing indexes
The following filter patterns are used in hot paths but may not have explicit indexes (worth verifying with `\d` or `pg_indexes`):
- `experience_claims` by `(user_id, source_type)` — used in bulk delete operations
- `experience_claims` by `(user_id, status)` — if archived filtering lands
- `tailorings` by `(user_id, generation_status)` — dashboard list query

---

## Post-next-deploy cleanup (do not forget)

These deprecated columns are safe to drop once the next deploy is confirmed stable.

| Column | Table | Status |
|--------|-------|--------|
| `experience_source` | `job_chunks` | ✅ **Dropped** — migration `d1a2b3c4e5f6` |
| `group_key` | `experience_claims` | ⏳ Deferred — Phase 5 of schema cleanup sprint. Still the primary grouping mechanism in `chunk_matcher.py`; requires matching pipeline migration first. |

---

## Decisions still open

| Decision | Status | Notes |
|----------|--------|-------|
| ~~Add `position` to `experience_groups`~~ | ✅ Done — migration `f3c4d5e6a7b8` | Backfilled from `created_at` order |
| ~~Add `provenance_url` + `provenance_label` to `experience_groups`~~ | ✅ Done — migration `f3c4d5e6a7b8` | |
| ~~Add `tags` to `experience_groups`~~ | ✅ Done — migration `f3c4d5e6a7b8` | JSONB nullable |
| ~~Add `description` to `experience_groups`~~ | ✅ Done — migration `f3c4d5e6a7b8` | text nullable |
| ~~Change `experience_groups.type_meta` from `JSON` → `JSONB`~~ | ✅ Done — migration `f3c4d5e6a7b8` | Lossless cast |
| ~~Rename `technologies` → `keywords` on `experience_claims`~~ | ✅ Done — migration `e2b3c4d5f6a7` | |
| ~~Add `pending` to `experience_claims.status`~~ | ✅ Done — schema docstring + API filter updated | `chunk_matcher.py` excludes `pending` claims from retrieval |
| ~~Add `merged_from` to `experience_claims`~~ | ✅ Done — migration `e2b3c4d5f6a7` | |
| ~~Add `original_content` to `experience_claims`~~ | ✅ Done — migration `e2b3c4d5f6a7` | Set on first user PATCH of content |
| ~~Collapse `provenance_url` + `provenance_label` + `chunk_metadata` → `provenance_metadata`~~ | ✅ Done — migration `e2b3c4d5f6a7` | `chunk_metadata` backfilled into `provenance_metadata` |
| ~~Make `jobs.user_id` non-nullable~~ | ✅ Done — migration `a4b5c6d7e8f9` | |
| ~~Add cleanup for `llm_trigger_log`~~ | ✅ Done — amortized cleanup in `tailorings.py` | Rows >30d deleted as BackgroundTask on create/regen |
| ~~Add `ON DELETE CASCADE` to `tailorings.user_id` FK~~ | ✅ Done — migration `a4b5c6d7e8f9` | |
| ~~Encrypt `user_integrations.credentials` at rest~~ | ✅ Done — migration `c5d6e7f8a9b0` | `EncryptedJSON` Fernet, `FIELD_ENCRYPTION_KEY` env var |
| Make `position` on `experience_claims` scoped to `(user_id, group_id)` | Open | Before experience editor reorder UX ships; complex backfill |
| Drop vestigial `corrections` sub-key from `experience_sources.source_data` | Open | Low priority; verify no pipeline code writes it |
| Drop `group_key` from `experience_claims` | Open — Phase 5 | Requires migrating `chunk_matcher.py` grouping logic to `group_id` first |

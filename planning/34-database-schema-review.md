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
| `llm_usage_logs` | many per user | Rate limiting / Billing | Hourly burst limiter + monthly quota source + cost tracking (model/token cols nullable until instrumentation ships) |
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
| `user_id` | UUID FK → users | **no** | Made non-nullable in migration `a4b5c6d7e8f9` |
| `job_url` | varchar | yes | Source URL; null for manually entered jobs |
| `raw_description` | text | yes | Raw description text for manual jobs |
| `extracted_job` | JSONB | yes | `{ title, company, requirements: [] }` |
| `source_type` | varchar(20) | no | `url` \| `manual`; default `url`; added migration `c9d0e1f2a3b4` |
| `created_at` | timestamptz | no | |

**Relationships out:**
- → `job_chunks` (1:many, cascade delete)
- → `tailorings` (1:many)

**Questions / candidates for change:**
- `raw_description` — stored for manual jobs, but not used after `extracted_job` is populated. Consider whether it has any long-term audit value.
- `extracted_job` contains `requirements` as a flat list of strings — the pre-chunk model. `job_chunks` is now authoritative. The `extracted_job.requirements` fallback was only referenced in the now-deleted `requirement_matcher.py` (dead code — never called from active app paths). No runtime fallback exists; chunk enrichment failure surfaces explicitly.
- A `Job` is shared across regenerations of the same tailoring. If the URL changes on regen, a new `Job` is created.

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
| `should_render` | boolean | no | LLM flag: display this chunk in the tailoring? Overridden by `SEMANTIC_TYPE_RULES` for most types |
| `include_in_scoring` | boolean | no | Controls whether this chunk participates in scoring runs. Overridden by `SEMANTIC_TYPE_RULES`; mutable (user can force-include a chunk). Renamed from `is_requirement` in migration `c9d0e1f2a3b4` |
| `semantic_type` | varchar(30) | yes | `job_requirement` \| `role_description` \| `company_description` \| `compensation` \| `location` \| `application_info` \| `legal` \| `other`. Set once at extraction; never updated by refresh. Null for pre-migration rows |
| `evaluation_status` | varchar(20) | yes | `scored` \| `skipped` \| `error`. `scored` = match_score in {0,1,2}; `skipped` = excluded by design (header, non-scoreable type); `error` = scoring attempted but failed. Null for pre-migration rows. Resolves the `match_score=-1` ambiguity |
| `enriched_at` | timestamptz | yes | Set when scoring completes |
| `created_at` | timestamptz | no | Added migration `c9d0e1f2a3b4` |
| `updated_at` | timestamptz | no | Added migration `c9d0e1f2a3b4` |
| `embedding` | vector(1536) | yes | pgvector; populated by embed_job_chunks |
| `embedding_model` | varchar(100) | yes | |

**Questions / candidates for change:**
- `experience_source` — dropped in migration `d1a2b3c4e5f6`. `experience_sources` (array) is the only source attribution column.
- `scored_content` vs `content` split: `scored_content` was added to snapshot the content at scoring time in case the user edits the chunk. In practice, the UI does not currently allow editing job chunks. This column may be redundant.
- ~~`match_score = -1` ambiguity~~ — resolved. `evaluation_status` now distinguishes `skipped` (by design: headers, non-scoreable types) from `error` (scoring attempted but failed). `match_score=-1` is still written for skipped/error chunks as the sentinel but `evaluation_status` is authoritative.
- `semantic_type` is set-once during `enrich_job_chunks` and never updated by `refresh_job_chunks` or `re_enrich_single_chunk`. `SEMANTIC_TYPE_RULES` in `chunk_matcher.py` deterministically overrides `include_in_scoring` and `should_render` for all types except `other` and `company_description.include_in_scoring`.

---

## `tailorings`

**Purpose:** AI-generated document mapping a candidate to a specific job. The primary product artifact.

> Schema cleaned up in migration `d0e1f2a3b4c5`: flat telemetry, Notion, and model columns collapsed into JSONB objects; `enrichment_status` and `gap_analysis_status` dropped; `updated_at` added; `letter_content` promoted to JSONB.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | UUID PK | no | |
| `user_id` | UUID FK → users | no | ON DELETE CASCADE (added migration `a4b5c6d7e8f9`) |
| `job_id` | UUID FK → jobs | no | |
| `generated_output` | text | yes | **Deprecated** — rendered markdown kept as fallback for pre-`letter_content` rows and derived artifact on new generations. Drop once all rows have `letter_content`. |
| `letter_content` | **JSONB** | yes | Structured letter (`AdvocacyStatement[]` + `closing`). Source of truth for new rows. Was `JSON`; promoted to JSONB in `d0e1f2a3b4c5`. |
| `models` | JSONB | yes | `{ letter: "model-id", scoring: "model-id" }`. Replaced flat `model` varchar (dropped `d0e1f2a3b4c5`). |
| `generation_status` | varchar | no | `pending` \| `generating` \| `ready` \| `error` |
| `generation_stage` | varchar | yes | `extracting` \| `enriching` \| `generating` (null when idle) |
| `generation_error` | text | yes | User-facing error message |
| `generation_started_at` | timestamptz | yes | |
| `generated_at` | timestamptz | yes | Set on completion |
| `last_regenerated_at` | timestamptz | yes | Set on regen trigger |
| `generation_telemetry` | JSONB | yes | `{ duration_ms, matching_mode, batch_count, batch_errors }`. Replaced flat `generation_duration_ms`, `chunk_batch_count`, `chunk_error_count`, `matching_mode` (all dropped `d0e1f2a3b4c5`). |
| `profile_snapshot` | text | yes | Exact formatted profile passed to LLM at generation time. Debug/audit only; not in API responses. |
| `gap_analysis` | JSONB | yes | `ProfileGapWithChunk[]`. `null` = not yet run; `[]` = ran but no gaps (or early exit/error). Backend always sets this to a non-null value on completion — `!= null` is the frontend polling signal. |
| `letter_public` | boolean | no | |
| `posting_public` | boolean | no | |
| `public_slug` | varchar | yes | UNIQUE per user (`uq_tailorings_user_public_slug`). Collision-safe generation via `_generate_slug()` with retry loop. |
| `notion_export` | JSONB | yes | `{ container_page_id, page_id, page_url, posting_page_id, posting_page_url }`. Replaced 5 flat `notion_*` columns (dropped `d0e1f2a3b4c5`). |
| `created_at` | timestamptz | no | |
| `updated_at` | timestamptz | yes | Added `d0e1f2a3b4c5`; `server_default=now()`, `onupdate=now()`. |

**Dropped in migration `d0e1f2a3b4c5`:**
`enrichment_status`, `gap_analysis_status`, `generation_duration_ms`, `chunk_batch_count`, `chunk_error_count`, `matching_mode`, `model`, `notion_container_page_id`, `notion_page_id`, `notion_page_url`, `notion_posting_page_id`, `notion_posting_page_url`

**Notes:**
- `enrichment_status` was redundant with job_chunks existence — derived at read time: `"complete" if chunks else "pending"`.
- `gap_analysis_status` was always `"complete"` regardless of success/failure — replaced by the `gap_analysis != null` sentinel.
- `letter_public` and `posting_public` are separate flags allowing partial sharing. `is_public` is a hybrid property (`letter_public OR posting_public`).
- Notion export uses `notion_export` JSONB; SQLAlchemy mutation detection requires creating a new dict (not mutating in-place) before reassigning.

---

## `llm_usage_logs`

**Purpose:** One row per LLM pipeline trigger. Serves three purposes: (1) sliding-window hourly burst rate limiting, (2) monthly tailoring quota enforcement (when billing ships), (3) cost tracking once LLM instrumentation lands (model/token columns nullable until then).

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | UUID PK | no | |
| `user_id` | UUID FK → users | no | CASCADE delete |
| `event_type` | varchar(50) | no | See event types below |
| `model` | varchar(100) | yes | LLM model name; null until instrumentation ships |
| `input_tokens` | integer | yes | Prompt tokens; null until instrumentation ships |
| `output_tokens` | integer | yes | Completion tokens; null until instrumentation ships |
| `cost_usd` | numeric(10,6) | yes | Estimated cost; null until instrumentation ships |
| `created_at` | timestamptz | no | |

**Event types:**
- `tailoring_create` — full tailoring pipeline; counts toward monthly quota and hourly burst
- `tailoring_regen` — full regen; counts toward monthly quota and hourly burst
- `letter_regen` — letter-only regen; counts toward hourly burst, NOT monthly quota
- `resume_process` — LLM resume profile extraction (renamed from `experience_process`)
- `github_enrich` — GitHub repo enrichment (tracked, not yet rate-limited)
- `gap_analysis` — gap question generation (tracked when run independently)

**Index:** `ix_llm_usage_logs_user_event_time` on `(user_id, event_type, created_at)` — covers both hourly burst sliding-window queries and calendar-month quota range scans.

**Retention:** 90 days (covers 3 billing months for dispute resolution). Rows cleaned as `BackgroundTask` on tailoring create/regen and experience process (amortized). See `_cleanup_old_trigger_logs` in `tailorings.py`, `_cleanup_old_usage_logs` in `experience.py`.

**Future (partner API):** When headless enrichment API ships, a nullable `partner_id UUID FK → api_partners` will be added. Rate limiting will then scope to `partner_id` instead of `user_id` for B2B calls.

---

## `tailoring_debug_logs`

**Purpose:** Per-generation telemetry. Populated at ~12 call sites inside `_finalize_tailoring` in `tailorings.py` via `_write_debug_log()`.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | UUID PK | no | |
| `tailoring_id` | UUID FK → tailorings | no | CASCADE delete |
| `user_id` | UUID FK → users | yes | SET NULL on user delete; backfilled from tailoring at write time |
| `event_type` | varchar(50) | no | |
| `payload` | JSONB | no | Arbitrary event data; JSONB for operator support |
| `created_at` | timestamptz | no | |

**Index:** `ix_tailoring_debug_logs_event_time` on `(event_type, created_at)` — covers eval-mining queries (`WHERE event_type = 'generation_complete' AND created_at >= ...`).

**Retention:** 90 days. Amortized cleanup in `_cleanup_old_debug_logs()`, called at the end of every successful `_finalize_tailoring` run.

**`generation_complete` payload keys:**
- `total_duration_ms` — wall-clock ms for the full pipeline
- `phase_durations` — per-phase breakdown dict
- `matching_mode` — `"vector"` or `"llm"`
- `llm_model` — model used for letter generation
- `batch_count` — number of chunk-matching batches dispatched (from `generation_telemetry`)
- `batch_errors` — number of errored batches (from `generation_telemetry`; 0 = clean run)

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
- `llm_usage_logs` → `users.id`

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
| `llm_usage_logs` | CASCADE | — |
| `tailoring_debug_logs` | user_id SET NULL | tailorings CASCADE |

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
| `enrichment_status`, `gap_analysis_status`, `generation_duration_ms`, `chunk_batch_count`, `chunk_error_count`, `matching_mode`, `model`, 5× `notion_*` | `tailorings` | ✅ **Dropped** — migration `d0e1f2a3b4c5` |
| `generated_output` | `tailorings` | ⏳ Deferred — kept as fallback for pre-`letter_content` rows and derived artifact. Drop once all prod rows have `letter_content`. |
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
| ~~Add cleanup for `llm_usage_logs`~~ | ✅ Done — amortized cleanup in `tailorings.py` + `experience.py` | Rows >90d deleted as BackgroundTask on create/regen/process |
| ~~Add `ON DELETE CASCADE` to `tailorings.user_id` FK~~ | ✅ Done — migration `a4b5c6d7e8f9` | |
| ~~Encrypt `user_integrations.credentials` at rest~~ | ✅ Done — migration `c5d6e7f8a9b0` | `EncryptedJSON` Fernet, `FIELD_ENCRYPTION_KEY` env var |
| ~~Rename `is_requirement` → `include_in_scoring` on `job_chunks`~~ | ✅ Done — migration `c9d0e1f2a3b4` | Semantics: "include in scoring runs" vs the ambiguous "is a requirement" |
| ~~Add `semantic_type` to `job_chunks`~~ | ✅ Done — migration `c9d0e1f2a3b4` | 8-value taxonomy; set once at extraction; `SEMANTIC_TYPE_RULES` applies deterministic overrides |
| ~~Add `evaluation_status` to `job_chunks`~~ | ✅ Done — migration `c9d0e1f2a3b4` | Resolves `match_score=-1` ambiguity; `scored` \| `skipped` \| `error`; backfilled from `match_score` at migration time |
| ~~Add `created_at` / `updated_at` to `job_chunks`~~ | ✅ Done — migration `c9d0e1f2a3b4` | Standard audit columns; consistent with all other tables |
| ~~Add `source_type` to `jobs`~~ | ✅ Done — migration `c9d0e1f2a3b4` | `url` \| `manual`; replaces `job_url IS NULL` inference |
| ~~Remove dead `requirement_matcher.py` and `requirement_matching.py`~~ | ✅ Done | Never called from active app code; only referenced by its own test file |
| ~~Collapse `tailorings` telemetry/Notion/model fields into JSONB~~ | ✅ Done — migration `d0e1f2a3b4c5` | `generation_telemetry`, `notion_export`, `models` JSONB; 13 flat columns dropped |
| ~~Drop `enrichment_status` and `gap_analysis_status` from `tailorings`~~ | ✅ Done — migration `d0e1f2a3b4c5` | `enrichment_status` derived at read time; `gap_analysis != null` replaces status polling |
| ~~Add `updated_at` to `tailorings`~~ | ✅ Done — migration `d0e1f2a3b4c5` | `server_default=now()`, `onupdate=now()` |
| ~~Promote `tailorings.letter_content` from JSON → JSONB~~ | ✅ Done — migration `d0e1f2a3b4c5` | Lossless cast |
| ~~Fix `public_slug` collision risk~~ | ✅ Done | `_generate_slug()` now checks uniqueness per user with retry loop |
| ~~Rename `llm_trigger_log` → `llm_usage_logs` and extend for billing~~ | ✅ Done — migration `e0f1a2b3c4d5` | Added `model`, `input_tokens`, `output_tokens`, `cost_usd` (nullable); `experience_process` → `resume_process`; composite index `(user_id, event_type, created_at)`; 30d → 90d retention; cleanup added to `experience.py` as well |
| Drop `generated_output` once all rows have `letter_content` | Open | Requires confirming all prod rows upgraded via "Upgrade Letter" feature or regen |
| Make `position` on `experience_claims` scoped to `(user_id, group_id)` | Open | Before experience editor reorder UX ships; complex backfill |
| Drop vestigial `corrections` sub-key from `experience_sources.source_data` | Open | Low priority; verify no pipeline code writes it |
| Drop `group_key` from `experience_claims` | Open — Phase 5 | Requires migrating `chunk_matcher.py` grouping logic to `group_id` first |

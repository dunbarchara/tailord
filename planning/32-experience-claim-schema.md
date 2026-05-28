# Experience Claim — Schema Reference

**Date:** 2026-05-27
**Status:** Implemented — migrations `d2e3f4a5b6c7` + `e3f4a5b6c7d8` + `f5a6b7c8d9e0` applied.
**Related:** `planning/experience_capture/`, `planning/33-sprint-plan-20260527.md`

> **Note (Day 2):** The parent `users` table was refactored in migration `a7b8c9d0e1f2`. The `user_id` FK columns on `experience_groups` and `experience_claims` are unchanged — they still point to `users.id`. The `users` row itself now carries only identity fields; profile and integration data moved to `user_profiles` and `user_integrations`. No schema changes to either claims table.

---

## Unit Name: Experience Claim

**User-facing name:** Experience Claim
**Short form:** Claim (after first mention in context)
**ORM model:** `ExperienceClaim`
**Table:** `experience_claims`
**URL segment:** `/claims`

An Experience Claim is the atomic unit of a user's professional experience. One row per achievement, skill, project entry, education fact, or gap-response answer. Every Tailoring, every gap question, and every cosine retrieval operation works at the claim level.

**Two states:**
- **Grouped** — belongs to a parent `ExperienceGroup` (e.g., a bullet under a job role, a commit claim under a repo). `group_id` is non-null.
- **Ungrouped** — standalone. `group_id` is null. Typical for skills, certifications, direct user input, and gap responses.

One level of nesting only. No deeper hierarchy.

---

## Parent Container: Experience Group

**User-facing name:** Group (generic); `group_type` provides the specific label in UI
**ORM model:** `ExperienceGroup`
**Table:** `experience_groups`

Groups are context, not claims. They are **never embedded** — they don't participate in cosine retrieval. When a claim with a `group_id` is returned for LLM scoring or tailoring generation, the group context is automatically prepended by the retrieval layer.

LLM sees:
> "At Microsoft as Senior Engineer (Jan 2020 – Apr 2023): Owned infrastructure for 40+ microservices serving 12M daily requests."

Not just:
> "Owned infrastructure for 40+ microservices serving 12M daily requests."

This contract is enforced at the retrieval layer, not optional.

---

## `experience_groups` — Table Schema

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | UUID PK | no | |
| `user_id` | UUID FK → users | no | CASCADE delete |
| `group_type` | varchar(30) | no | `role` \| `project` \| `repository` \| `education` \| `custom` |
| `name` | varchar(255) | no | Display name. For `role`: employer. For others: user-defined label. |
| `start_date` | varchar(50) | yes | MM/YYYY |
| `end_date` | varchar(50) | yes | MM/YYYY or null (= present) |
| `location` | varchar(255) | yes | Relevant for roles and education |
| `type_meta` | JSONB | yes | Type-specific fields — see below |
| `source_type` | varchar(30) | no | `resume` \| `github` \| `user_input` \| `annotation` |
| `source_ref` | varchar(255) | yes | Repo name for github; null otherwise |
| `created_at` | timestamptz | no | |
| `updated_at` | timestamptz | no | |

### `type_meta` by group_type

New group types can be added without a migration — just a new Pydantic variant.

```
role:         { "title": "Senior Engineer", "employment_type": "full_time" }
project:      { "technologies": ["React", "Python"], "url": "https://..." }
repository:   { "primary_language": "Python", "url": "https://github.com/..." }
education:    { "degree": "BSc", "field_of_study": "Computer Science" }
custom:       {}
```

---

## `experience_claims` — Table Schema

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | UUID PK | no | | |
| `user_id` | UUID FK → users | no | | CASCADE delete |
| `group_id` | UUID FK → experience_groups | yes | null | SET NULL on group delete — claim becomes ungrouped |
| `source_type` | varchar(30) | no | | See source types below |
| `source_ref` | varchar(255) | yes | null | Repo name for github; null otherwise |
| `claim_type` | varchar(30) | no | | `work_experience` \| `skill` \| `project` \| `education` \| `other` |
| `content` | text | no | | The claim text |
| `group_key` | varchar(255) | yes | null | **Deprecated.** Denormalized string `"Company \| Title"`. Kept until `group_id` backfill is verified; drop in a future migration. |
| `date_range` | varchar(100) | yes | null | Temporal context for ungrouped claims; grouped claims inherit from their group |
| `technologies` | JSONB | yes | null | `["React", "PostgreSQL"]` — tool/stack signals for this claim |
| `confidence` | varchar(20) | no | `medium` | See confidence levels below |
| `status` | varchar(20) | no | `active` | `active` \| `archived` (soft delete) |
| `provenance_url` | varchar(500) | yes | null | Clickable evidence link (GitHub PR, published paper, award URL) |
| `provenance_label` | varchar(255) | yes | null | Human-readable label: "View PR #12", "Published paper" |
| `tags` | JSONB | yes | null | `["performance", "team-leadership"]` — user or LLM assigned, no fixed taxonomy |
| `chunk_metadata` | JSONB | yes | null | Gap/partial/annotation provenance — see metadata shapes below |
| `position` | integer | no | | Sort order within source group (or globally for ungrouped) |
| `embedding` | vector(1536) | yes | null | pgvector; null until first embed run; not exposed in API |
| `embedding_model` | varchar(100) | yes | null | Model name used for the current embedding vector |
| `created_at` | timestamptz | no | | |
| `updated_at` | timestamptz | no | | |

### Source types and lifecycle

| `source_type` | Created by | Deleted by |
|---------------|-----------|-----------|
| `resume` | Resume processing pipeline | Resume removal |
| `github` | GitHub enrichment | Repo disconnect / GitHub disconnect |
| `user_input` | User submits text claims | Per-claim delete or bulk user-input remove |
| `gap_response` | User answers a gap question | Experience cascade only — never by source events |
| `partial_response` | User answers a path-to-strong question | Same as gap_response |
| `annotation` | (future) User adds claim to a position | Same as gap_response |

### Confidence levels

| Value | Meaning |
|-------|---------|
| `high` | User directly stated (gap_response, user_input, annotation) |
| `medium` | LLM-extracted from structure (resume bullet, PR description) |
| `low` | Inferred by pipeline (GitHub stack detection) |

### `chunk_metadata` shapes

```
gap_response / partial_response:
  { "question": "...", "job_chunk_id": "<uuid>", "tailoring_id": "<uuid>" }

annotation (future):
  { "parent_claim_id": "<uuid>" }

resume / github / user_input: null
```

---

## Mock JSON

### ExperienceGroup — role

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "user_id": "aa11bb22-cc33-dd44-ee55-ff6677889900",
  "group_type": "role",
  "name": "Microsoft",
  "start_date": "01/2020",
  "end_date": "04/2023",
  "location": "Seattle, WA",
  "type_meta": {
    "title": "Senior Software Engineer",
    "employment_type": "full_time"
  },
  "source_type": "resume",
  "source_ref": null,
  "created_at": "2026-05-27T10:00:00Z",
  "updated_at": "2026-05-27T10:00:00Z"
}
```

### ExperienceGroup — repository

```json
{
  "id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
  "user_id": "aa11bb22-cc33-dd44-ee55-ff6677889900",
  "group_type": "repository",
  "name": "tailord",
  "start_date": null,
  "end_date": null,
  "location": null,
  "type_meta": {
    "primary_language": "Python",
    "url": "https://github.com/dunbarchara/tailord"
  },
  "source_type": "github",
  "source_ref": "tailord",
  "created_at": "2026-05-27T10:00:00Z",
  "updated_at": "2026-05-27T10:00:00Z"
}
```

### ExperienceClaim — grouped (resume bullet under role)

```json
{
  "id": "d4e5f6a7-b8c9-0123-defa-234567890123",
  "user_id": "aa11bb22-cc33-dd44-ee55-ff6677889900",
  "group_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "source_type": "resume",
  "source_ref": null,
  "claim_type": "work_experience",
  "content": "Owned infrastructure for 40+ microservices serving 12M daily active requests.",
  "group_key": "Microsoft | Senior Software Engineer",
  "date_range": "01/2020 – 04/2023",
  "technologies": ["Kubernetes", "Go", "Azure"],
  "confidence": "medium",
  "status": "active",
  "provenance_url": null,
  "provenance_label": null,
  "tags": ["scale", "infrastructure", "ownership"],
  "chunk_metadata": null,
  "position": 3,
  "embedding_model": "text-embedding-3-small",
  "created_at": "2026-05-27T10:00:00Z",
  "updated_at": "2026-05-27T10:00:00Z"
}
```

### ExperienceClaim — ungrouped (skill)

```json
{
  "id": "e5f6a7b8-c9d0-1234-efab-345678901234",
  "user_id": "aa11bb22-cc33-dd44-ee55-ff6677889900",
  "group_id": null,
  "source_type": "resume",
  "source_ref": null,
  "claim_type": "skill",
  "content": "Python",
  "group_key": null,
  "date_range": null,
  "technologies": null,
  "confidence": "medium",
  "status": "active",
  "provenance_url": null,
  "provenance_label": null,
  "tags": ["backend", "scripting"],
  "chunk_metadata": null,
  "position": 42,
  "embedding_model": "text-embedding-3-small",
  "created_at": "2026-05-27T10:00:00Z",
  "updated_at": "2026-05-27T10:00:00Z"
}
```

### ExperienceClaim — gap_response (user answered a gap question)

```json
{
  "id": "f6a7b8c9-d0e1-2345-fabc-456789012345",
  "user_id": "aa11bb22-cc33-dd44-ee55-ff6677889900",
  "group_id": null,
  "source_type": "gap_response",
  "source_ref": null,
  "claim_type": "other",
  "content": "Led the Kubernetes migration for our 40-service platform, reducing p99 latency by 30% through resource tuning and HPA configuration.",
  "group_key": null,
  "date_range": null,
  "technologies": null,
  "confidence": "high",
  "status": "active",
  "provenance_url": null,
  "provenance_label": null,
  "tags": null,
  "chunk_metadata": {
    "question": "You have Kubernetes listed but the role emphasizes production incident response. Do you have a specific example of debugging a K8s issue under pressure?",
    "job_chunk_id": "9a8b7c6d-5e4f-3210-9876-543210fedcba",
    "tailoring_id": "1a2b3c4d-5e6f-7890-1234-567890abcdef"
  },
  "position": 101,
  "embedding_model": "text-embedding-3-small",
  "created_at": "2026-05-27T11:30:00Z",
  "updated_at": "2026-05-27T11:30:00Z"
}
```

### ExperienceClaim — GitHub repo claim (grouped under repository)

```json
{
  "id": "a7b8c9d0-e1f2-3456-abcd-567890123456",
  "user_id": "aa11bb22-cc33-dd44-ee55-ff6677889900",
  "group_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
  "source_type": "github",
  "source_ref": "tailord",
  "claim_type": "work_experience",
  "content": "Built a FastAPI + pgvector pipeline that retrieves candidate experience claims by cosine similarity and feeds them to an LLM for requirement scoring.",
  "group_key": "tailord",
  "date_range": null,
  "technologies": ["Python", "FastAPI", "pgvector", "PostgreSQL"],
  "confidence": "medium",
  "status": "active",
  "provenance_url": "https://github.com/dunbarchara/tailord",
  "provenance_label": "View repository",
  "tags": ["retrieval", "llm", "backend"],
  "chunk_metadata": null,
  "position": 0,
  "embedding_model": "text-embedding-3-small",
  "created_at": "2026-05-27T10:00:00Z",
  "updated_at": "2026-05-27T10:00:00Z"
}
```

---

## LLM Context Rule — Groups travel with their Claims

When a claim with a `group_id` is retrieved for scoring or generation, the retrieval layer prepends the group context. The LLM prompt fragment looks like:

```
At Microsoft as Senior Software Engineer (01/2020 – 04/2023):
  • Owned infrastructure for 40+ microservices serving 12M daily active requests.
  • Reduced deploy cycle from 45 min to 8 min by introducing GitOps with ArgoCD.
```

For ungrouped claims, no prefix is added — the claim content stands alone.

This is a **retrieval contract**, not optional rendering logic. Anywhere claims are passed to an LLM, groups must accompany them.

---

## What was explicitly rejected

| Option considered | Decision | Reason |
|------------------|----------|--------|
| `pillar` (fixed enum e.g. "Scale & Performance") | `tags: list[str]` (flexible) | Pillars are software-specific; tags are user/LLM-assigned and work across all industries |
| `provenance: { label, url }` (nested JSON) | Flat columns `provenance_url` + `provenance_label` | Flat columns are directly queryable; no JSON unpacking needed |
| `metadata.industry_context` per-claim | Industry context at User/Experience level | Claims are industry-agnostic primitives |
| `status: "pending"` | `status: "active" \| "archived"` | "pending" is for a future verification workflow; current need is soft delete only |
| "Parent Scope" / "Role" as the container concept | "Group" | Scope is developer-speak; Role is too narrow for repos, projects, custom groupings |
| Embedding groups | Groups not embedded | Groups are context; retrieval always operates at the claim level |

---

## Deferred (explicitly out of scope for now)

- `PluginConnection` FK on claims — wait for plugin architecture
- `canonical_tag` skill normalization — after dedup pipeline exists
- `DeduplicationCandidate` table — after claim volume warrants it
- Verification workflow (`status: "pending" | "verified"`) — after human-in-loop features
- Manual drag-and-drop grouping UI — noted as future, not schema-blocking
- Dropping `group_key` — pending `group_id` backfill verification

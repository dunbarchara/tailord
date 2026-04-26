# Day 12.5 — Chunk-Driven Platform

**Date:** 2026-04-26
**Theme:** Make chunks the single source of truth for all rendered data.

---

## Philosophy

The architecture direction from `09-platform-maturity.md` describes the eventual north star:

```
Vector similarity → Ranked ExperienceChunks → LLM generation → Output
```

Chunks are the connective tissue. Every input source (resume, GitHub, user input) is
broken into atomic, source-traceable claims. Every output (tailoring, gap analysis,
profile display) is derived from those claims.

Day 12 created `ExperienceChunk` rows and wired them to all input sources. Day 12.5
completes the platform pivot: **rendered data comes from chunks, not from JSON blobs**.

The `extracted_profile` and `extracted_job` JSON columns become internal intermediate
storage only — never surfaced directly to the frontend. This eliminates the two-source-
of-truth split that would emerge if rendering used the blob while matching used chunks.

---

## Why not change tailoring generation to use chunks now?

The full value of chunk-based generation comes from the *pre-selection* step in Day 14:

```
Vector similarity → selects top-k relevant ExperienceChunks for this job
        ↓
LLM generates tailoring from that curated, relevant set
```

Without vector pre-selection, passing all chunks to the LLM is roughly the same as
passing the formatted profile string — same volume, worse structure (flat list of
claims vs. narrative with job context). The `09-platform-maturity.md` principle applies:
the LLM doing selection + generation in one call is a compound responsibility.

**Decision: keep tailoring generation on the formatted profile path until Day 14.**
The generation prompt and pipeline will be updated then, not now, when the ranked
chunk input is available. This is not a gap — it is the correct sequencing.

---

## Day 12.5 Scope

### Backend

**ExperienceChunk read + edit API**
- [ ] `GET /experience/chunks` — returns all chunks for the authenticated user's experience,
  structured for rendering (grouped by `source_type` + `group_key`):
  ```json
  {
    "resume": {
      "summary": [{ "id": "...", "content": "..." }],
      "work_experience": [
        { "group_key": "ACME | SWE", "date_range": "2020–2023", "bullets": [...chunks] }
      ],
      "skills": [...chunks],
      "projects": [{ "group_key": "MyApp", "description": chunk, "technologies": [...] }],
      "education": [...chunks],
      "other": [...chunks]
    },
    "github": {
      "repos": [
        { "group_key": "tailord", "summary": chunk, "stack": [...chunks] }
      ]
    },
    "user_input": [...chunks]
  }
  ```
- [ ] `PATCH /experience/chunks/{chunk_id}` — update `content` only (not structural fields);
  returns the updated chunk; emits `updated_at` for cache busting

**JobChunk read API**
- [ ] `GET /jobs/{job_id}/chunks` — returns job chunks grouped by `chunk_type`/`section` for
  rendering the parsed job description in the UI (requirements, skills, responsibilities);
  includes `match_score`, `advocacy_blurb` if present

**Wire user_input into chunk endpoint**
- `set_user_input` already calls `chunk_user_input` — endpoint returns from `GET /experience/chunks`

### Frontend

**Experience view — render from chunks**
- [ ] `GET /api/experience/chunks` proxy route
- [ ] Replace `ExtractedProfile` rendering in the experience tab with chunk-derived data;
  work experience renders as job groups (company + title heading, bullets underneath);
  projects render with name heading, description, tech tags;
  skills render as tag cloud from `claim_type=skill` chunks
- [ ] Each bullet / skill / project description is individually editable inline;
  edit triggers `PATCH /api/experience/chunks/{id}` — only that chunk updates

**Job description view — render from JobChunks**
- [ ] `GET /api/jobs/{id}/chunks` proxy route
- [ ] Tailoring detail page: replace "raw job description" panel with structured chunk view
  (requirements grouped, match scores shown per chunk, advocacy blurbs alongside matched requirements)
- [ ] `extracted_job` JSON no longer surfaced in UI

### Data boundary

`extracted_profile` and `extracted_job` remain in the DB as internal intermediate
storage used by the tailoring generator and requirement matcher. They are not returned
to the frontend after this day. The API contracts use chunked structures only.

---

## Relationship to Future Days

| Day | Dependency on Day 12.5 |
|-----|----------------------|
| Day 13 — pgvector + embeddings | Embeds `ExperienceChunk.content` on write. Schema is already correct. `GET /experience/chunks` is how future UI will show embedding status. |
| Day 14 — vector matching | `ExperienceChunk` rows are the input to cosine similarity ranking. Chunk edit (`PATCH`) invalidates embeddings → triggers re-embed. |
| Conversational enrichment | Gap question answers → new `user_input` chunks → `PATCH` or new chunk insert → re-embed → re-match without full regen. The chunk edit endpoint is the entry point for this flow. |

---

## Acceptance

- `GET /experience/chunks` returns data structured for direct rendering — no blob reshaping in frontend
- `PATCH /experience/chunks/{id}` updates content and `updated_at`; does not alter `source_type`, `group_key`, or `claim_type`
- Experience view in dashboard renders from chunks, not `extracted_profile`
- Job description in tailoring detail renders from `JobChunk` rows, not `extracted_job`
- `extracted_profile` and `extracted_job` no longer appear in any frontend API response
- `make check` passes

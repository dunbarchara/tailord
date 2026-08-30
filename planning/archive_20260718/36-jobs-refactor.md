# Jobs & Job Chunks Refactor

*Created: 2026-05-28. Discussion doc — add findings here until ready to turn into an implementation plan.*

---

## Background

This document captures schema and pipeline decisions for `jobs` and `job_chunks` that emerged from the database schema review (`34-database-schema-review.md`). Nothing here is implemented yet. The goal is to consolidate the design before writing migrations and updating the extraction/scoring pipeline.

---

## 1. Rename `is_requirement` → `include_in_scoring`

**Current state:** `is_requirement` is described in the schema doc as "True for requirement type; false for headers/paragraphs" — implying it's a derived, read-only fact from `chunk_type`. In practice it's mutable:
- Initialized from `chunk_type` on extraction
- Promoted to `true` when a non-requirement chunk is individually rescored (`tailorings.py:1539`)
- Force-set to `true` on manual chunk creation (`tailorings.py:1314`)
- User-editable via PATCH

The real meaning is: **"include this chunk in scoring runs."** Company description paragraphs, for example, can be surfaces to showcase experience and are intentionally included in scoring even though they aren't candidate requirements.

**Decision:** Rename to `include_in_scoring`. Column rename migration only — no logic change.

**On messaging:** This rename is internal only. UI copy, generation stage labels ("Scoring requirements..."), and platform positioning ("your experience mapped to every requirement") all stay requirement-framed. `include_in_scoring` is a more accurate internal name for what the flag does; it doesn't need to surface to users.

---

## 2. Add `semantic_type` — semantic classification for job chunks

**Problem:** `chunk_type` (`requirement`, `paragraph`, `header`, `bullet`) captures *structure* — how the chunk is formatted. It does not capture *content* — what the chunk is about. This means:

- A `header` for company description and a `header` for legal boilerplate are indistinguishable
- A `paragraph` for role responsibilities and a `paragraph` for compensation look the same structurally but have completely different handling implications
- `should_render` is currently an unbounded LLM judgment call per chunk — unpredictable and untestable

**Proposed solution:** Add `semantic_type VARCHAR(30) nullable` to `job_chunks`. Nullable for backwards compat — null for pre-migration rows.

### Semantic taxonomy

| `semantic_type` | `include_in_scoring` | `should_render` | Notes |
|---|---|---|---|
| `job_requirement` | `true` | `true` | Must-have / nice-to-have qualifications |
| `role_description` | `true` | `true` | Responsibilities — surfaces for experience matching |
| `company_description` | conditional | `false` | See note below |
| `compensation` | `false` | `false` | Salary, equity, benefits |
| `location` | `false` | `false` | Remote policy, office location |
| `application_info` | `false` | `false` | How to apply, deadlines, EEO statements |
| `legal` | `false` | `false` | Boilerplate, disclaimers |
| `other` | LLM decides | LLM decides | Fallback |

### `company_description` nuance

`company_description` is **not** unconditionally included in scoring. The distinction is:

- **Include:** "We build distributed systems that process 10M events/second" → this is a surface for the candidate to showcase relevant experience
- **Exclude:** "Spotify was founded in 2006 in Stockholm" → pure company history; no experience surface

**Decision:** Use a single `company_description` label. The LLM classifier emits the type *and* decides `include_in_scoring` only for this type — reasoning about whether there is an experience surface. For all other semantic types, `include_in_scoring` is set deterministically from the rule table above with no LLM judgment required.

### Impact on `should_render` and `include_in_scoring`

After classification, these become **resolved outputs of `semantic_type`** for all known types:

- `include_in_scoring` and `should_render` are set by rule lookup at classification time
- The LLM no longer makes free-form per-chunk rendering decisions
- Only `other` and `company_description` fall back to LLM judgment
- Both fields stay on the row as resolved values — rendering and scoring queries don't re-apply rules

### Impact on the extraction prompt

The LLM's job during chunk extraction changes:

**Before:** Split posting into chunks + decide `should_render` per chunk (free-form judgment)

**After:** Split posting into chunks + classify each with a `semantic_type` from the taxonomy (constrained label from a fixed set)

Classification is a more constrained task than "should this be shown?" — more auditable (logs show "this chunk was classified as `compensation` → not rendered"), more testable (fixture-based eval per type), and less prone to LLM drift.

### `chunk_type` stays

`chunk_type` and `semantic_type` are orthogonal. Keep both:
- `chunk_type` = structural format (`requirement`, `paragraph`, `header`, `bullet`) — used for extraction logic and rendering layout
- `semantic_type` = content classification — drives scoring and render rules

---

## 3. Add `created_at` and `updated_at` to `job_chunks`

**Current state:** The only timestamp on `job_chunks` is `enriched_at` (set when scoring completes). There is no record of when a chunk was created or last modified.

**Gap:**
- `created_at` — no way to tell when chunks were extracted, when a manual chunk was added, or correlate chunk creation to the generation timeline in debug logs
- `updated_at` — no way to tell when content was last edited via PATCH or when a chunk was last rescored. `enriched_at` partially covers "last scored" but is not set on content edits

**Note:** The UI *does* allow chunk content editing. `scored_content` (the snapshot of content at scoring time) is therefore intentionally distinct from `content` (the current content). This is not redundant — if a user edits a chunk's content, `scored_content` preserves what was actually scored, and a subsequent rescore uses the new `content`. The `scored_content` vs `content` split is correct and should be kept.

**Decision:** Add `created_at TIMESTAMPTZ NOT NULL DEFAULT now()` and `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()` to `job_chunks`. Makes the table consistent with every other table in the schema.

---

## 4. Add `evaluation_status` to `job_chunks`

**Current state:** `match_score = -1` is used to mean "not evaluated." This conflates two distinct states:
- Skipped by design (headers, paragraphs, chunks where `include_in_scoring = false`)
- Failed to score (LLM error, timeout, batch failure)

These are meaningfully different for debugging and UI display. A failed score might warrant a retry; a by-design skip never should.

**Decision:** Add `evaluation_status VARCHAR(20) nullable` with values:
- `null` — not yet evaluated (initial state)
- `scored` — scoring completed (match_score is a valid 0/1/2)
- `skipped` — intentionally excluded from scoring (include_in_scoring=false or non-scoreable chunk_type)
- `error` — scoring was attempted and failed

`match_score = -1` can then be reserved or deprecated — `evaluation_status = "error"` or `evaluation_status = null` replace it semantically.

**Backfill strategy:** At migration time, for all existing rows where `match_score = -1`: classify as `error` if `match_rationale` contains the string `"error"` (case-insensitive), otherwise classify as `skipped`. All other rows (`match_score` in 0/1/2) → `scored`. Future scoring operations will use the new `evaluation_status` values directly.

---

## 5. Add `source_type` to `jobs`

**Current state:** Whether a job was scraped from a URL or manually entered is inferred implicitly (`job_url IS NULL` → manual). There is no explicit column.

**Decision:** Add `source_type VARCHAR(20) NOT NULL DEFAULT 'url'` to `jobs` with values:
- `url` — scraped from a job posting URL
- `manual` — user entered the description directly

This makes intent explicit and creates a clean extension point for future sources (e.g. `paste`, `api` for headless enrichment use case from `planning/17-ai-agent-friendly.md`).

**Verified:** No app code uses `job_url IS NULL` as an implicit discriminator for "manual job." All null checks on `job_url` are request-level guards (`if body.job_url:`, `bool(self.job_url and ...)`), not DB-level inference. `job_url` remains nullable — manual jobs legitimately have no URL. Adding `source_type` is purely additive.

---

## 6. Remove `extracted_job.requirements` fallback

**Current state:** `extracted_job` on `jobs` contains a `requirements` key — a flat list of strings from the pre-chunk extraction model. `job_chunks` is now authoritative for requirements. The `extracted_job.requirements` list is only used as a fallback if chunk enrichment fails (`34-database-schema-review.md`).

**Problem:** Two sources of truth for requirements. The fallback path is likely untested and would produce degraded output silently.

**Decision:** Remove the fallback. If chunk enrichment fails, the error should surface explicitly rather than silently degrading.

**Verified:** The only read site is `requirement_matcher.py:20-21` inside `match_requirements()`. That function is **never called from any active app code path** — only referenced in its own test file. It is dead code. Remove `match_requirements()` entirely and its test. `extracted_job` can retain its other fields (`title`, `company`, etc.) — the `requirements` key in existing JSONB rows can be left in place with no migration needed.

---

## 7. Drop deprecated `experience_source` (singular) from `job_chunks`

**Current state:** `experience_source VARCHAR(50)` (singular) is deprecated, replaced by `experience_sources JSONB` (array). The singular column is still serialized in `_serialize_chunk` at `tailorings.py:130-132`.

**Decision:** Drop the column and remove its serialization in `_serialize_chunk` (`tailorings.py:130-132`).

**Verified:** The frontend TypeScript types (`types/index.ts`) only define `experience_sources` (plural) with a comment noting preference for it over the singular. No `.ts` or `.tsx` component reads `experience_source` singular. Mock data files (`mock/data.json`) contain it as `null` fixture values only — irrelevant to live code. Safe to remove serialization and add the column drop to a migration.

Also tracked in `34-database-schema-review.md` post-deploy cleanup table.

---

## Open questions

None outstanding — all pre-implementation questions resolved above. Ready to turn into a sprint plan.

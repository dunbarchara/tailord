# Chunk Model — Reference

**Date:** 2026-04-28
**Status:** Established — use this as the canonical reference before building anything
that touches ExperienceChunks.

This document captures the decisions made after the Platform Maturity sprint about how
experience chunks are defined, how they're created and managed, and how the taxonomy
should evolve. It supersedes the inline comments in `database.py` as the design authority.

---

## Core Principle

**One table. All chunk types participate equally in cosine similarity retrieval.**

The retrieval query is:
```sql
SELECT * FROM experience_chunks
WHERE experience_id = :exp_id
ORDER BY embedding <=> :query_embedding
LIMIT :k
```

This query must search across all source types simultaneously. Splitting into multiple
tables would require UNION ALL or a materialized view on the hottest query path in the
system. The `source_type` column is the discriminator — it controls lifecycle, rendering,
and management, not retrieval.

---

## Source Type Taxonomy

| `source_type` | Origin | Who creates it | Lifecycle |
|---|---|---|---|
| `resume` | Resume upload + LLM extraction | System | Deleted when resume is removed |
| `github` | GitHub repo enrichment | System | Deleted when repo is disconnected |
| `user_input` | Manual submission by user | User (LLM-assisted parse) | Deleted per-chunk; all cleared when user clears input |
| `gap_response` | User's answer to a gap question | User (direct text) | **Never** deleted by source events — only by Experience deletion |
| `annotation` | *(future)* User-added claim attached to a position or project | User (direct text) | **Never** deleted by source events — only by Experience deletion |

### Lifecycle rule for `gap_response` and `annotation`
These represent the user's own explicit assertions about their experience. They are
independent of any source document. Deleting a resume should not erase what the user
has told the system about themselves. These chunks are only removed when the user
explicitly deletes them individually, or when the entire Experience record is deleted.

The existing `delete_resume_chunks`, `delete_github_chunks`, and `delete_user_input_chunks`
functions filter by `source_type` — `gap_response` and `annotation` chunks are
automatically excluded and will not be touched by those functions. No special-casing needed.

---

## GitHub Chunks — Current Structure

For each connected GitHub repo, the enrichment pipeline currently produces:
- **1 `project` chunk**: `content = readme_summary` (LLM-generated description)
- **N `skill` chunks**: one per item in `detected_stack` (e.g., "Python", "FastAPI", "Docker")

All chunks share `group_key = repo_name` so the renderer groups them under the repo heading.
`source_ref = repo_name` enables per-repo delete when a repo is disconnected.

The readme_summary and each stack item are embedded independently. This is intentional:
"FastAPI" as a discrete skill chunk retrieves cleanly against "experience with FastAPI"
requirements. Embedding it inside a paragraph dilutes the cosine signal.

**Ceiling:** GitHub enrichment currently only reads repo metadata (name, language, stars,
description) and generates a summary from that. The GitHub deep crawl feature (README,
pyproject.toml, Dockerfile, CI configs) would produce richer chunks, but the structure
is already correct for that expansion.

---

## user_input — Redesigned

### Old model (deprecated)
Single text box → one `user_input` chunk containing the entire text. Non-editable
per-claim. Cleared as an atomic blob.

### New model
Text area + submit → **LLM parse into individual atomic claims** → persist as N separate
`user_input` ExperienceChunks, each independently editable and deletable.

**Parse behavior:**
- Short input (single sentence / clear single claim): create one chunk immediately,
  no LLM needed.
- Longer input (multiple sentences, paragraph, or multiple claims): LLM parse into
  individual claims, show parsed preview, user confirms before persisting.

**LLM parse prompt intent:** "Extract atomic professional claims — one specific, concrete
statement per chunk. Do not invent or embellish. Return only what is stated."

**Why preview before persist for longer inputs:** The LLM may split incorrectly or merge
claims that should be separate. Showing parsed chunks before committing lets the user
verify what enters their profile. For short unambiguous input, skip straight to persisting.

**New endpoints needed:**
- `POST /experience/user-input/parse` — LLM parse, returns preview (no DB write)
- `POST /experience/user-input/chunks` — persist a list of chunk texts (replaces `set_user_input`)
- `DELETE /experience/chunks/{id}` — individual chunk deletion (needed across all types)

**Rendering:** Each `user_input` chunk renders as an individual editable/deletable item
under "Additional Experience" in My Experience. Not a single text blob.

---

## gap_response — Design

### What it is
A user's answer to a gap question surfaced after tailoring generation. The question
identifies a job requirement that could not be evidenced from the candidate's profile;
the response is the candidate's claim that they have that experience.

### Stored as
A `gap_response` ExperienceChunk with:
- `content`: the user's written response
- `claim_type`: `"other"` (for now — could be more specific later)
- `group_key`: null (not attached to a position/project)
- `metadata` JSON: `{question: "...", job_chunk_id: "...", tailoring_id: "..."}`

The `metadata` column does not yet exist — **adding it is the prerequisite migration
for any gap_response or annotation work.**

### Why not `user_input`
Gap responses have specific provenance (prompted by a job requirement) that is useful
for UI rendering (show the question as context) and for future cross-tailoring features
("you've answered a similar question before"). Lumping them into `user_input` loses this.

### Lifecycle
Gap response chunks are **never deleted by source events**. They survive resume
replacement, GitHub disconnection, and tailoring deletion. The user can delete them
individually from My Experience ("Your Responses" section). They are removed automatically
only when the Experience record itself is deleted.

### Effect on matching
Gap response chunks are embedded immediately on creation. They participate in all
subsequent cosine similarity retrievals — for re-enriching the requirement that prompted
them, and for all future tailorings. This is the core value of the gap enrichment loop:
**answer once, benefit from all future tailorings that test the same experience dimension.**

### Re-match flow
When a gap response is submitted:
1. Create `gap_response` chunk → embed it (background task)
2. Call `re_enrich_single_chunk(job_chunk_id)` to re-score the specific requirement
3. Return updated score to frontend
4. UI updates the requirement's STRONG/PARTIAL/GAP badge inline

---

## annotation — Deferred

Annotations (user-added claims attached to an existing position or project) are
structurally similar to gap_response but triggered by the user proactively rather than
by a gap question. The design is clear:

- `source_type = "annotation"`
- `group_key` matches the position/project being annotated (renders under that heading)
- `metadata`: `{parent_chunk_id: "..."}` if attached to a specific chunk
- Same lifecycle rule: never deleted by source events

Build after `user_input` and `gap_response` are solid. The `metadata` column migration
is the shared prerequisite.

---

## Schema Changes Required

**Migration:** Add `metadata JSON NULL` column to `experience_chunks`.

No new tables. No new FKs. The `metadata` column is the single schema dependency for
gap_response provenance and future annotation support.

All other changes (new source_type values, new endpoints, new rendering) are code-only.

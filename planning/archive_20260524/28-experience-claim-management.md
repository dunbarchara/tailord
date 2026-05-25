# Experience Claim Management — Current State and Forward Strategy

**Date:** 2026-05-14
**Status:** Strategy doc — not a sprint plan. Reference before building anything that adds a new source type, changes chunk rendering, or touches deduplication.

---

## The Problem This Addresses

Today, `ExperienceChunk` has six source types and three claim types. That is manageable. The trajectory is not: passive capture (doc 23), plugin connectors, gap responses, annotations, and AI agent summaries will each produce chunks at different rates, with different quality signals, and with overlapping semantic content. Without a clear strategy for deduplication, tagging, and user-facing visibility, the experience repository degrades into a noise pile that produces worse Tailorings, not better ones.

This document captures where we are, where we are going, and how the system should stay coherent as it grows.

---

## Current State

### Source types (live or designed)

| `source_type` | Origin | Volume profile | Notes |
|---|---|---|---|
| `resume` | Resume upload + LLM extraction | ~20–80 chunks, one batch | Replaced wholesale on re-upload |
| `github` | Repo enrichment | ~3–5 chunks per repo | 1 project + N skills per repo |
| `user_input` | Manual textarea → LLM parse | Low, user-driven | Per-chunk editable since doc 17 |
| `gap_response` | Answer to gap question post-tailoring | Grows with each tailoring | Per-tailoring provenance in metadata |
| `partial_response` | Answer to path-to-strong question | Same lifecycle as gap_response | Same structure |
| `annotation` | (designed, not built) User claim on a position | User-driven | Attached via group_key |

### Claim types (current)

`work_experience` | `skill` | `project` | `education` | `other`

### What the schema knows today

Each chunk has: `source_type`, `source_ref`, `claim_type`, `content`, `group_key`, `date_range`, `technologies[]`, `chunk_metadata{}`, `position`, `embedding`.

This is enough for the current source count. It starts to break down when:
- The same skill appears in three sources (resume skill, github skill, gap_response answer)
- A user has 15 GitHub repos each producing 5 skill chunks → 75 skill entries with no dedup
- gap_responses accumulate across 20 tailorings with no grouping
- The user wants to find "everything I have on TypeScript" and gets 40 results

---

## Incoming Complexity

### Likely new source types (from doc 23)

| `source_type` (proposed) | Origin | Volume profile |
|---|---|---|
| `message` | In-app quick log, email forward, SMS | High — daily/weekly |
| `plugin_github` | GitHub PR merge webhook | Continuous — each merge |
| `plugin_linear` | Linear issue closed | Continuous |
| `plugin_jira` | Jira issue resolved | Continuous |
| `plugin_mcp` | AI agent session summary | High — agent-driven |
| `performance_review` | Pasted perf review / peer feedback | Low, high signal |

Each new source compounds the deduplication and visibility problem. A user with GitHub integration, Linear, and daily messages could accumulate 500+ chunks in a month, most of which overlap.

---

## Strategy 1: Deduplication Pipeline

### Principle

Deduplication must happen **before** a chunk enters the repository, not after. A post-hoc dedup job is harder to explain to users and creates uncertainty about what was removed. The ingestion pipeline is the right choke point.

### Dedup at ingest

When a new chunk is about to be persisted:

1. **Embed the incoming content** (required for ingest anyway).
2. **Query existing chunks** for the same user, filtered by `claim_type`. Cosine similarity threshold: `>= 0.92` (tight — only near-exact rewrites collapse).
3. **Context filter**: only compare within the same `group_key` if one exists (do not collapse "TypeScript at ACME" with "TypeScript at Side Project"). For flat skill chunks (no group_key), compare globally.
4. **Below threshold**: ingest as-is. No dedup.
5. **Above threshold**: queue a `DeduplicationCandidate` event — do not silently drop.

### User-facing dedup review

Above-threshold matches are not silently merged. They are surfaced in a **review queue** in My Experience:

> "This looks similar to an existing entry. Keep both, merge, or discard the new one?"

The user sees both the existing chunk and the incoming chunk, with source badges. They choose. The review queue can be batched — processed async, not blocking the ingest path.

For **skill-type chunks specifically**, the threshold can be tighter because "TypeScript" and "TypeScript" are identical. For `work_experience` or `project` chunks, keep the threshold strict — two different accomplishments at the same company should never auto-merge.

### Periodic compaction

Ingest-time dedup (above) catches duplicates at the point of entry. It does not catch duplicates that arrived via different paths over time — e.g., a skill mentioned in a resume upload, then again in a gap response six months later, then again from a GitHub README scan. Over time, a user with multiple sources accumulates semantic near-duplicates that ingest-time dedup never saw together.

**Periodic compaction pass:**
- Runs on a schedule (e.g., weekly) or triggered when a user's chunk count crosses a threshold (e.g., every 50 new chunks added)
- For each user: cluster all chunks by `claim_type`, compute pairwise cosine similarity within each cluster
- Pairs above the threshold (>= 0.92) that were not already reviewed at ingest time → add to the `DeduplicationCandidate` review queue
- For skill-type chunks with the same canonical text (once normalization exists): auto-suggest merge rather than just flagging

**Surface in My Experience:**
- Same review queue used by ingest-time dedup — the user experience is identical regardless of when the duplicate was detected
- Optionally: a periodic nudge ("You have 7 similar claims that might be worth consolidating") shown on the dashboard or experience page after a compaction run

**Compaction vs. dedup distinction:**
- Dedup: two chunks say the same thing — collapse to one
- Compaction: multiple chunks about the same theme but with different specifics — surface them together so the user can decide if they want a single consolidated claim or to keep the distinct evidence

The compaction pass should not auto-merge. It surfaces candidates; the user decides. Silent compaction undermines trust in the repository.

---

### The dedup unit is the accomplishment, not the technology

This is the key principle from doc 23. "Reduced latency by 40% using Redis" is a unique signal even if Redis is already in the profile. Do not merge accomplishment chunks based on shared technology. Deduplicate the accomplishment text; keep the technology cluster orthogonal.

---

## Strategy 2: Claim Taxonomy — Enrichment and Normalization

### Current taxonomy is too flat

Five claim types (`work_experience`, `skill`, `project`, `education`, `other`) covers current needs but will produce increasingly meaningless search results. "Show me my skills" returns a mix of resume bullet-extracted skills, GitHub detected stack items, gap response answers, and performance review extracts — all typed `skill`, indistinguishable by quality or recency.

### Proposed additions (not yet migrated — plan before building)

**Confidence level** (new column: `confidence` — `high | medium | low`):
- `high`: directly stated by user (gap_response, user_input, annotation, performance_review)
- `medium`: LLM-extracted from structured source (resume, PR description)
- `low`: inferred by enrichment pipeline (github stack detection from README scan)

This lets the retrieval pipeline weight high-confidence claims more heavily, and lets the UI warn the user if a Tailoring relied on a low-confidence signal.

**Claim recency signal** (existing: `date_range` — but underutilized):
- All new source types must populate `date_range` wherever possible. Plugin sources (GitHub PR, Linear issue) have exact timestamps — use them.
- Chunks without a date_range and older than the oldest known position should be flagged as "unanchored" in the UI.

**Canonical skill normalization** (deferred, but design now):
- The problem: "React", "ReactJS", "React 18", "React (v18)" are four representations of one skill.
- The solution is a normalization table (or a lightweight LLM pass at ingest) that maps raw skill strings to canonical labels. Store the canonical label in a new `canonical_tag` column; keep `content` as the original.
- This enables "show me everything tagged `react`" as a faceted search query, not a fuzzy text match.
- Do not build the normalization pass until dedup is working — normalization amplifies dedup accuracy when the canonical labels match.

---

## Strategy 3: User-Facing Visibility

### The current problem

My Experience today shows chunks grouped by source type (resume, GitHub, user input, gap responses). This is a reasonable first pass. At scale it breaks down:

- A user with 6 gap responses spread across 4 tailorings sees 6 disconnected entries with no grouping
- GitHub skill chunks repeat the same technologies across 10 repos
- There is no way to search, filter by date, or find "everything I know about Kubernetes"

### Target UX model: the claim browser

My Experience should evolve into a **claim browser**, not a source-grouped list. The user's mental model is "my experience" — not "my resume claims" vs. "my GitHub claims." The source is a secondary provenance detail, not the primary grouping.

**Primary grouping:** employer → project → claims. This mirrors how a human thinks about their work history.
- Work experience chunks group under the position/employer (`group_key`)
- Project chunks group under the project name
- Skill and education chunks appear in flat sections
- gap_response and annotation chunks group under their parent position/project if one is set, otherwise in a "Responses" section

**Secondary facets (filter/search bar):**
- By source type (badge filter: resume | github | user_input | gap_response | plugin)
- By claim type (work_experience | skill | project | education)
- By confidence (high | medium | low — once that column exists)
- By technology (canonical tag filter — once normalization exists)
- Full-text search across `content`

**Dedup review queue:** a persistent "Needs review" section at the top of My Experience, shown only when there are pending deduplication candidates. Dismissible per-item.

**Source health status:** for plugin-connected sources (GitHub, Linear), a compact status indicator showing last sync time and whether it errored. Not buried in settings — visible alongside the claims it produced.

### Requirement-driven search

A user should be able to bring any requirement string to their experience repository and immediately see how well their record covers it.

**Flow:**
1. User pastes or types a requirement into a search field in My Experience (e.g., "5+ years distributed systems experience with Kafka")
2. Backend temporarily embeds the requirement — no storage, no side effects, transient query only
3. Cosine similarity runs against the user's `experience_chunks` using the existing retrieval infrastructure
4. Returns top-K results with similarity scores, displayed inline with their source badges and claim types

**Why this matters:**
- Gives users agency to probe their own record before submitting an application
- Makes the retrieval pipeline transparent — users see exactly what evidence Tailord would draw on
- Naturally surfaces gaps: low top-K scores or weak similarity on a key requirement tells the user what to add
- Reinforces the repository-as-asset framing: not "here are your chunks" but "here's how your record answers this question"

**Implementation notes:**
- The embedding and retrieval path is already used in tailoring generation; this is the same call exposed as a user-facing query
- Do not store the embedded query — the requirement text is ephemeral
- Consider showing the similarity score to the user in some form (e.g., a match strength indicator) — the absolute number is less useful than a relative signal ("strong match", "partial match", "weak coverage")
- Natural entry point: a search/filter bar at the top of the claim browser, alongside the existing facet filters

---

### Editing

Today: chunks are individually editable if they come from `user_input`, gap_response, or annotation. Resume and GitHub chunks are not editable (they are re-derived from source).

Going forward:
- Resume chunks: show as read-only with a "suggest an edit" path that creates an `annotation` chunk attached to the same group_key. Never overwrite the LLM-extracted source.
- GitHub chunks: same. The source of truth is the repo; an annotation can supplement it.
- This preserves the ability to re-derive from source (re-upload resume, re-crawl GitHub) without losing user-contributed corrections.

---

## Strategy 4: Source Management

As plugin connections multiply, users need a dedicated source management surface — separate from the claim browser.

**Per-source controls:**
- Enable / pause (stop ingesting new events without disconnecting)
- Last sync status + error message
- "Re-sync now" trigger
- Delete source + remove all chunks produced by it (confirm dialog)

**Source lifecycle rules (reinforce what doc 17 established):**
- Deleting a source deletes chunks where `source_type` matches AND `source_ref` matches the source
- `gap_response`, `annotation`, `partial_response` are NEVER deleted by source deletion — they are user assertions
- A source-deletion UI must make this distinction explicit: "Removing GitHub will delete 42 GitHub-derived claims but will preserve your 8 written responses"

---

## Strategy 5: Retrieval Integrity

The retrieval query (`ORDER BY embedding <=> :query_embedding`) runs across all chunks in a user's experience. As chunk count grows, retrieval quality depends on:

1. **Dedup quality**: duplicate chunks dilute the result set and cause the same claim to appear multiple times in a Tailoring
2. **Embedding freshness**: chunks without embeddings (e.g., failed embed background task) silently drop out of retrieval. Need a monitoring signal for `embedding IS NULL` count per user.
3. **Position weighting** (deferred): for requirements that are explicitly about recency ("5+ years of X"), the retrieval query today has no recency signal. A future enhancement is to include `date_range` as a reranking signal after cosine retrieval, not as a filter.
4. **Confidence weighting** (once column exists): boost `high` confidence chunks in retrieval by multiplying their cosine score. Implementation: post-retrieval reranking, not a DB-level filter.

---

## Data Model Evolution — What Needs to Migrate

The current schema is sound for the current source count. Before adding any new source type, these migrations should be evaluated:

| Column | Table | Rationale | Priority |
|---|---|---|---|
| `confidence` (enum: high/medium/low) | `experience_chunks` | Weight retrieval, flag weak signals to user | High — before plugin sources |
| `canonical_tag` (string, nullable) | `experience_chunks` | Skill normalization and faceted search | Medium — after dedup |
| `plugin_connection_id` (FK, nullable) | `experience_chunks` | Attribute plugin-sourced chunks to connection | High — before plugin sources |
| `PluginConnection` table | new | Register plugin connections per user | High — before plugin sources |
| `PluginEvent` table | new | Raw payload storage + ingestion lifecycle | High — before plugin sources |
| `DeduplicationCandidate` table | new | Review queue for above-threshold matches | Medium — before dedup queue UI |

Do not add all of these at once. The ordering constraint is:
1. `PluginConnection` + `PluginEvent` + `plugin_connection_id` on chunks — required for first plugin source
2. `confidence` — required before retrieval weighting
3. `DeduplicationCandidate` — required before dedup review UI
4. `canonical_tag` — required before faceted skill search

---

## What Not to Do

- **Do not build a second chunk table per source type.** The single-table retrieval architecture is a deliberate decision (doc 17). All chunk types must remain in `experience_chunks` to participate in cosine retrieval without UNION ALL.
- **Do not silently merge or drop duplicate chunks at ingest.** Always route above-threshold matches to a user-visible review queue.
- **Do not design the UI around source type as the primary grouping.** The user's mental model is their work history, not their data sources.
- **Do not let plugin sources ingest without a privacy scrub pass.** Raw plugin payloads may contain customer names, unreleased product details, or internal architecture. The scrub pass is mandatory before any chunk is stored.
- **Do not add `canonical_tag` before dedup is working.** Normalization amplifies bad dedup — fixing duplicates becomes harder when both copies have been canonicalized to the same tag.

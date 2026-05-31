# Experience Groupings, Boundaries, and Deduplication

## Core Concept: The Logical Boundary

A **logical boundary** is the highest-level grouping that defines a distinct professional context. Within a boundary, claims about the same thing are noise. Across boundaries, the same claim carries entirely different signal.

The canonical example:
- "Built React components" at **Google** and "Built React components" at **Microsoft** → preserve both. These are separate employments, separate contexts, and separate proof points. An employer cares that you've done this at two different companies.
- "Built React components" in a **role group** and "Built React components" in a **repo nested under that role** → deduplicate. These are the same employment, the same context, and the same proof point. The repo is just a more granular view of work already represented by the role.

The boundary principle: **deduplicate within a boundary, preserve across boundaries.**

---

## Group Types and Their Roles

### `role`
A job position at a company or organization. This is the **primary boundary unit**. A role defines a distinct employment context. All claims (including nested repos/projects) within a role group live inside a single professional context.

- Can contain nested `repository` and `project` groups
- Role + all its nested groups form a single logical entity for LLM purposes
- When building tailoring context: pass the role's full claim tree as one bundle, not piecemeal

### `repository`
A code repository. Can be standalone (e.g. an open-source side project) or **associated with a role** (nested under it). The association means: "this repo was part of my work at this role."

When nested under a role:
- The repo is not a separate employer — it is a sub-context of the role
- Claims in the repo that duplicate claims in the role are noise
- The repo contributes specificity, not breadth

When standalone:
- Treated as its own boundary (equivalent to a standalone project)

### `project`
A named project. Can be standalone (its own boundary) or nested under a role (a major initiative within that employment). Same nesting logic as `repository`.

### `education`
A degree, certification, or course. Each education entry is its own boundary. Deduplication within education makes sense (e.g. the same course listed twice). Cross-boundary deduplication doesn't apply — "Python at MIT" and "Python at Google" are both worth preserving.

### `custom`
User-defined grouping. The user decides the semantic scope. Treat as its own boundary unless nested, in which case follow standard nesting rules.

---

## Claim Types

| Type | Description |
|------|-------------|
| `work_experience` | Narrative accomplishment or responsibility bullet |
| `skill` | A technology, tool, language, or methodology |
| `project` | A project-level achievement (often within a role or repo group) |
| `education` | An education entry |
| `other` | Miscellaneous context |

---

## The Nesting Contract

A nested group (repo/project under a role) is a **more granular view of the same context**, not an independent context. Consequences:

1. **Skills at the role level should be the union of all skills in the role boundary** — including those extracted from nested repos. After extraction, skills at nested repo level that are already represented at the role level are duplicates.

2. **Work experience claims should be checked for semantic overlap within the boundary.** "Led migration from REST to GraphQL" at the role level and "Migrated API to GraphQL" at a nested repo are likely the same claim. One should be the primary, the other archived or merged.

3. **The LLM prompt should present the full role boundary as a unified context**, not as "role claims + repo claims." The hierarchy is for human understanding; the LLM gets a flat, deduped bundle per boundary.

---

## Deduplication Strategy by Claim Type

### Skills (highest priority for dedup)
Skills are the most prone to proliferation — the same tech gets listed at role level, at repo level, and sometimes multiple times within each.

**Within a boundary:**
- Build the canonical skill set at the **top-level boundary group** level
- A skill in a nested repo that is already in the parent role or any sibling repo within that role = duplicate, suppress
- The role-level `SkillsInlineRow` should show the **union** of all skills in the boundary, deduped
- Nested repo `SkillsInlineRow` should show only skills **unique to that repo** (not already present anywhere else in the boundary) — this gives the repo credit for niche tech without repeating common skills

**Across boundaries:**
- Preserve. "React at Google" and "React at Microsoft" are independent proof points.

### Work experience / accomplishments
Harder to dedup than skills because phrasing varies. Approach:

- **Exact/near-exact duplicates within a boundary**: archive one, keep one
- **Same event, different abstraction levels**: keep both if they add different detail ("Led infrastructure migration" at role level + "Migrated Postgres to Aurora, reducing p99 latency by 40%" at repo level = complementary, keep both)
- **Purely redundant**: archive the less specific one

Across boundaries: preserve always.

### Project claims
Similar to work experience. Within a boundary, check if the same project is described multiple times at different levels of detail. Keep the most specific; archive or merge the rest.

---

## Display Counting Convention

Claim counts shown in the UI should reflect **logical density**, not raw claim count. Rules:

- All skill claims in a group → count as **1** (they'll render as one inline row)
- Each non-skill claim → count as **1**
- A role's count = its direct non-skill claims + (1 if any direct skills) + sum of all nested group counts (same rule applied recursively)

This way a role with 5 work experience bullets, 12 skills, and a nested repo with 3 bullets and 8 skills shows as **10** (5 + 1 + 3 + 1), not **28**.

---

## Terminology

See `planning/platform-terminology.md` for full definitions. Key terms used in this document:

| Term | Short definition |
|------|-----------------|
| **Capture Surface** | Where experience data enters the platform (resume, GitHub, Gap Response, etc.) |
| **Experience Signal** | Raw extracted observation from a surface. Persisted but not user-facing. The input to the dedup pipeline. |
| **Experience Claim** | Canonical, active, user-facing unit. The output of the pipeline. One per Claim Domain. |
| **Claim Domain** | Dedup identity key: `(claim_type, normalized_concept, boundary_group_id)` |
| **Logical Boundary** | Top-level grouping that scopes dedup — a role, standalone project/repo, or education entry |
| **Locked Claim** | A user-edited Claim; system preserves provenance but will not overwrite content |

---

## Claim Domain: Precise Definition

A Claim Domain identifies whether two claims are duplicates. It is a composite of:

```
domain = (claim_type, normalized_concept, boundary_group_id)
```

- `claim_type`: `skill`, `work_experience`, `project`, `education`, `other`
- `normalized_concept`: the canonical form of the claim content (lowercased, alias-resolved, embedding-fingerprinted for semantic match)
- `boundary_group_id`: the ID of the top-level boundary group (the role or standalone group)

Two claims in the same domain are candidates for dedup. Claims in different domains — even if semantically similar — are not deduplicated, because they represent distinct contexts.

---

## Deduplication Execution Model

### Why not lazy dedup at LLM call time

Deferring dedup to prompt-build time is tempting (no data mutation, always fresh) but breaks down at scale:

- An engineer who commits daily can accumulate hundreds of near-identical "React" claims from continuous GitHub sync. The claims table becomes unusable for the user.
- Every LLM call must re-run dedup logic, making calls more expensive. This compounds as claim volume grows.
- There is no persistent record of what was deduped and why — no audit trail, no user correction path.

### The persisted dedup model

Dedup produces **canonical Experience Claims** that are persisted, while the Experience Signals they derive from are **archived** (never deleted). Key properties:

- One canonical Experience Claim per Claim Domain — "React at Google" has exactly one active skill claim, regardless of how many signals have contributed to it
- Future new signals landing in the same domain are archived immediately and add a pointer to the existing canonical — no new canonical is created
- The canonical claim accumulates signal pointers over time but its identity is stable
- Archived Experience Signals retain full content and provenance — the system can always reconstruct what was merged and why
- This model is refactor-safe: if dedup strategy changes (different model, different thresholds, different rules), all raw signals still exist and a re-pass can produce different canonicals without data loss

### Canonical claim content: atomic text + supplementary enrichment

The canonical Experience Claim keeps its primary text **atomic and readable** — the user should be able to scan it quickly. But it carries a `supplementary` JSONB field that accumulates specifics, metrics, and context extracted from its sources.

Example:
- Canonical text: "Led API migration to GraphQL"
- `supplementary`: `["REST to GraphQL", "3 services migrated", "reduced p99 latency by 40%", "rolled out over Q3 2024"]`

At prompt-build time, the formatter appends the supplementary data: *"Led API migration to GraphQL [context: REST to GraphQL, 3 services, reduced p99 by 40%]"*

This satisfies the principle of high-quality atomic claims in the UI while maximising LLM context. The supplementary field grows as more sources roll up into the canonical. For skills, supplementary data is typically empty or version-specific ("React 18+").

**When to update supplementary vs. when to create a separate claim:**
- New source is clearly a more specific version of the same event → extract new specifics into supplementary, archive source
- New source describes a different event that is semantically adjacent but distinct → create a new canonical in the same domain, flag for user review

The judgment call on the boundary between "same event, more specific" and "different event" is where medium-confidence human review applies.

### Canonical claim ownership and locked state

A canonical claim can be in one of two states:

- **Auto-generated**: the system manages content. Future dedup passes may update the primary text or supplementary data if a richer source arrives.
- **Locked (user-owned)**: the user has manually edited the claim. The system preserves source pointers and supplementary data but will not overwrite the user's primary text. Future sources still roll up (are archived + pointed), but do not modify content.

The UI should visually indicate locked claims — a small lock icon or similar affordance. Locked claims also signal to the user that they are "first-class" owners of that piece of experience, which is meaningful for trust and understanding.

A separate UI symbol (TBD) should distinguish Experience Claims from Claim Sources in any audit/archived view, so the user can tell at a glance which is the canonical and which are the raw inputs.

### Confidence tiers and triggers

Dedup runs at three moments with different confidence handling:

**1. At ingestion (extraction time)**
- Trigger: new `ExperienceSource` is processed (resume upload, GitHub sync, manual input)
- Scope: deduplicate within each boundary the new claims land in
- High-velocity sources (GitHub sync) especially benefit — daily commits should not produce daily duplicate skill claims
- Confidence: exact/near-exact matches auto-dedup silently; semantic matches queue for review

**2. At association time**
- Trigger: user links a repo to a role (`parent_group_id` set)
- Scope: the newly merged boundary — compare all repo claims against role claims and any sibling repo claims
- This is the highest-signal trigger: the user has just defined the boundary, so dedup is directly motivated
- Medium-confidence matches surface as inline suggestions in the UI immediately after association

**3. On cadence / background pass**
- Trigger: periodic background job (daily or weekly)
- Scope: any boundary where claims have arrived or changed since last run
- Handles gaps that ingestion-time dedup missed (e.g. two sources processed at different times that overlap)
- All suggestions go to a review queue; no auto-application

### Confidence levels and handling

| Confidence | Criterion | Action |
|---|---|---|
| High | Exact match or near-exact after normalization, within same domain | Auto-archive source, roll into canonical silently |
| Medium | Embedding cosine similarity ≥ threshold (~0.92, calibrate with real data) | Surface as suggestion in UI; user approves or dismisses |
| Low | Below similarity threshold but same claim type and boundary | Flag for manual review only; no auto-action |

Start the medium threshold conservatively (0.95) and lower it as we validate quality against real claim data.

### Skill canonicalization

Before any dedup pass, normalize skill text:
- Lowercase for comparison only (store canonical casing from the most-specific source)
- Known aliases: "TS" → "TypeScript", "JS" → "JavaScript", "k8s" → "Kubernetes", etc.
- Normalization table lives in the backend and is extensible

Canonicalization runs before embedding-based dedup — exact-match after normalization is the cheapest and most reliable signal and should be exhausted first.

---

## Boundary Mutations and Impact Weight

Top-level boundary classifications (role, standalone project, etc.) have significant downstream implications. Changing them is not a lightweight edit — it triggers re-dedup, potentially archives or reinstates claims, and changes what gets passed to the LLM for all future tailorings.

**The platform should make this weight visible.** Any operation that mutates a logical boundary (re-associating a repo to a different role, splitting a role, merging two roles) should:

1. Trigger a **dry-run impact preview** before the user confirms. The backend exposes `?dry_run=true` on mutation endpoints, returning a summary: *"This will affect 23 experience claims, re-evaluate 7 claim domains, and may archive 4 claims pending review."*
2. Present this summary in the UI as a confirmation step — not a blocker, but a meaningful pause.
3. After the mutation, run a re-dedup pass on all affected boundaries.

**Re-association edge case (important):** When a repo moves from boundary A to boundary B, claims that were archived as duplicates of boundary A's canonicals may now be valid active claims in boundary B. The re-dedup pass must evaluate them fresh — they should not remain archived simply because they were once deduplicated against a different boundary.

**Design principle:** Classifications should feel *deliberate, not cheap*. The UI should reinforce this — grouping operations get more visual weight and confirmation friction than individual claim edits. The hierarchy is load-bearing; changing it has consequences. Users who understand this will build more stable, trustworthy experience graphs.

---

## LLM Prompt Construction

When building the context string for a tailoring:

1. Group active Experience Claims by top-level boundary
2. For each boundary, collect all active claims recursively (role + nested groups) — no runtime dedup needed, canonicals are already clean
3. For each canonical claim, append its `supplementary` data if present
4. Present as a unified bundle per boundary: *"At [Role/Company]: [work_experience bullets with supplementary context] | Skills: [canonical skills]"*
5. Claims from nested repos carry their repo name as provenance but the bundle is flat for the LLM

Example: *"At Tailord (tailord-api repo): Implemented SSE streaming for generation pipeline [context: FastAPI, ~50 concurrent streams, replaced polling]"*

---

## Open Questions

- **`supplementary` field schema**: flat string array vs. structured `{type, value}` pairs? Structured allows filtering (e.g. only include metrics for certain tailoring types) but adds complexity.
- **Locked claim + richer source**: if a locked claim exists and a new source arrives with substantially richer content, should the user be notified? Probably yes — "a new source has context that might improve this claim" surfaced as a non-blocking suggestion.
- **Canonical claim group ownership**: when two claims from a nested repo and a role merge, the canonical belongs to the role group (top-level boundary owner). The nested repo retains a pointer but not ownership.
- **Threshold calibration**: plan a calibration pass once meaningful claim volume exists in staging — target is identifying the similarity score where human reviewers agree ~90%+ of the time that two claims are duplicates.
- **Audit UI**: archived Claim Sources should be accessible in a collapsed/hidden section of the claims table, clearly labelled and distinguishable from active Experience Claims. Users need a path to recover a bad auto-dedup.

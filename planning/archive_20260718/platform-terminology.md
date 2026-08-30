# Platform Terminology

Precise definitions for concepts used across the Tailord platform. When in doubt, use these terms and definitions — not informal equivalents.

---

## The Core Pipeline

```
Capture Surface  →  Experience Signal  →  Experience Claim  →  Tailoring
```

Data flows in one direction. Each stage transforms raw input into progressively more authoritative, user-facing representations. The platform's deduplication, synthesis, and enrichment work happens at the **Signal → Claim** boundary.

---

## Capture Surface

**What it is:** Any integration or mechanism through which a user's experience enters the platform.

**Key property:** A surface produces Experience Signals. It does not produce Experience Claims directly — Claims are the output of processing, not ingestion.

**Current surfaces:**

| Surface | Description |
|---------|-------------|
| Resume upload | PDF/DOCX/TXT file; text extracted and parsed into signals |
| GitHub scan | Repository analysis; commits, READMEs, and languages produce signals |
| GitHub capture | Continuous/periodic sync; ongoing signal emission |
| Response | User answers a targeted question surfaced by Tailord post-tailoring. Display label: **"Response"** — the name communicates provenance mechanism (something was asked, user answered) without requiring platform knowledge. Covers both gap responses (missing requirement) and partial-match strengthening prompts — that distinction is metadata, not a separate surface. Internal DB values `gap_response` / `partial_response` are preserved until the signal layer migration consolidates them to a single `response` surface type. |
| Direct | User submits experience text through any direct input channel. Display label: **"Direct"**. Channel (webapp, SMS, Slack, WhatsApp, CLI, etc.) is metadata on the signal — `extraction_metadata: { channel: "webapp" }`. Internal DB values `user_input` / `additional_experience` are preserved until signal layer migration consolidates them to a single `direct` surface type. |
| Linear integration | (planned) Issue/project history produces signals |

**Trust level varies by surface.** User-authored surfaces (Response, Direct Input) produce high-trust signals that typically pass through to Claims with minimal processing. Automated surfaces (GitHub scan) produce lower-trust signals that warrant more aggressive dedup and quality filtering.

**The Signal → Claim pipeline applies uniformly to all surfaces.** The raw content from every surface is an Experience Signal; the processed, atomic output is an Experience Claim. This means the original user-authored text (e.g. a verbatim response to a targeted question, or the raw text pasted into Direct Input) is always preserved as the signal, regardless of how the claim is eventually phrased or merged. No surface bypasses the signal layer.

**Relationship to `ExperienceSource` (DB):** The `ExperienceSource` table represents the connection to a surface (status, config, sync metadata). Signals are the output of that source being processed.

---

## Experience Signal

**What it is:** A single raw extracted observation from a Capture Surface. The atomic unit of raw experience data before deduplication or synthesis.

**Key property:** A signal asserts *observation*, not *fact*. A GitHub scan signals "we observed TypeScript usage in this repo." Three separate signals saying the same thing are evidence that compounds — not three facts, not noise.

**Properties of a signal:**
- Tagged with its originating surface and source reference
- Carries a claim type (`skill`, `work_experience`, `project`, etc.)
- Has a confidence score reflecting extraction quality
- Is **always persisted** — signals are never discarded, even after processing. This preserves the ability to reprocess with improved models or revised dedup rules.
- Is not visible to the user by default — signals are plumbing

**Signal → Claim cardinality:**
- **N → 1 (dedup):** Multiple signals about the same concept within a boundary merge into one canonical Claim
- **1 → 1 (happy path):** A unique signal produces one Claim directly
- **1 → 0 (filtered):** A signal below quality threshold, flagged as noise, or superseded by a richer signal produces no active Claim

---

## Experience Claim

**What it is:** The canonical, active, user-facing unit of experience. The authoritative record of one piece of the candidate's background within a logical boundary.

**Key property:** An Experience Claim is the *output* of the pipeline, not the input. The user manages Claims. The LLM receives Claims. Claims represent what Tailord considers established about the candidate.

**Properties:**
- Belongs to exactly one group (or is ungrouped)
- Has a primary text that is **atomic and readable** — one bullet, one skill, one clear statement
- Carries a `supplementary` JSONB field with accumulated metrics, specifics, and context from its source signals — appended at prompt-build time for the LLM, not displayed prominently in the UI
- Has a list of source signal pointers (provenance) — the signals that produced or contributed to it
- Has an ownership state: **auto-generated** (system may update) or **locked** (user has edited; system preserves provenance but will not overwrite content)

**Locked Claims:**
When a user manually edits an Experience Claim, it becomes locked. The UI displays a visual indicator (e.g. a lock icon). Future signals in the same Claim Domain will still be archived with a pointer to the locked Claim, but the Claim's text is user-owned and will not be overwritten by the system. The user may explicitly unlock a Claim to return it to auto-generated status.

**What users see:** Active (non-archived) Claims only. Archived signals and superseded states are accessible through an audit path but hidden by default.

---

## Claim Domain

**What it is:** The deduplication identity key. Two signals or Claims in the same domain are candidates for dedup. Two signals in different domains are never merged, regardless of semantic similarity.

**Definition:**
```
Claim Domain = (claim_type, normalized_concept, boundary_group_id)
```

- `claim_type`: `skill`, `work_experience`, `project`, `education`, `other`
- `normalized_concept`: canonical form of the content (lowercased, alias-resolved, embedding-fingerprinted for semantic match)
- `boundary_group_id`: the ID of the top-level logical boundary group

**Examples:**
- "React" skill at the Google role → domain A
- "React" skill at the Microsoft role → domain B (different boundary — preserve both)
- "React" skill in the Google role group AND in a repo nested under that role → same domain A (same boundary — deduplicate)

One canonical Experience Claim exists per active Claim Domain.

---

## Logical Boundary

**What it is:** The top-level grouping that scopes deduplication. Within a boundary, duplicate signals should be merged. Across boundaries, the same concept carries independent signal.

**Current boundary types:**
- `role` — a job position (primary boundary unit; can contain nested repos and projects)
- standalone `repository` — a repo not associated with any role
- standalone `project` — a project not nested under any role
- `education` — a degree, course, or certification

**Key rule:** A `role` and all its nested `repository`/`project` groups form a **single boundary**. The role is the boundary owner. Nested groups are sub-contexts within that boundary, not independent boundaries.

**Boundary mutations are high-impact.** Re-associating a repo to a different role, splitting a role, or merging two roles changes the boundary structure and triggers re-dedup across all affected Claims. See *Boundary Mutations* below.

---

## Experience Group

**What it is:** A named container for related Experience Claims. Groups provide the organizational structure of the claims table and determine which Claims belong to which Logical Boundary.

**Group types:**

| Type | Description |
|------|-------------|
| `role` | A job position. Primary boundary unit. Can have nested repos/projects. |
| `repository` | A code repo. Can be standalone (own boundary) or nested under a role. |
| `project` | A named project. Can be standalone or nested under a role. |
| `education` | A degree, course, or certification. Its own boundary. |
| `custom` | User-defined grouping. Standalone boundary unless nested. |

**Nesting:** A nested group (repo or project under a role) is a more granular view of the same context, not an independent context. Claims in nested groups belong to the parent role's boundary.

---

## Tailoring

**What it is:** An AI-generated, role-specific document that maps a candidate's Experience Claims to a specific job description. Answers the question: *"Why is this candidate a strong fit for this role?"*

**Input:** Active Experience Claims (canonical, deduped, with supplementary context) + a Job.
**Output:** A structured document with scored requirement matches, advocacy blurbs, and fit analysis.

A Tailoring is not a resume rewrite. It is a targeted argument for fit.

---

## Boundary Mutations

Operations that change a Logical Boundary (associating/dissociating a repo from a role, merging groups) are structural changes with downstream consequences:

- Trigger re-dedup across all affected boundaries
- May archive Claims that become duplicates in the new boundary
- May reinstate archived signals that are now unique in the new boundary
- Require an **impact preview** before confirmation: *"This will affect 14 Experience Claims and re-evaluate 6 Claim Domains."*

The platform should communicate the weight of these operations. Top-level group classifications should feel deliberate — they are structural, not cosmetic. The UI should apply appropriate confirmation friction to boundary mutations.

---

## Signal Trust Levels

| Surface | Trust | Rationale |
|---------|-------|-----------|
| Direct input | High | User explicitly authored it |
| Direct | High | User explicitly submitted content through a direct channel |
| Response | High | User answered a targeted job-specific prompt; high-trust, low-noise |
| Resume upload | Medium-high | User intentionally submitted it; may have stale or generic content |
| GitHub scan (manual) | Medium | Reflects actual work, but may over-represent tools used peripherally |
| GitHub capture (continuous) | Medium-low | High volume, high noise; daily activity should not produce daily new Claims |
| Linear (planned) | Medium | Issue/project history reflects real work but is coarse-grained |

Trust level influences dedup aggressiveness and whether a Signal auto-promotes to a Claim or waits for review.

---

## Ingestion Pipeline Architecture

### Current model (direct ingestion)

Signals are produced synchronously during surface processing (resume parse, GitHub sync, etc.) and persisted immediately. Claims are derived in the same request or a background task.

```
Surface processing  →  persist ExperienceSignal  →  derive ExperienceClaim
```

This is appropriate for current scale. Signal volume is bounded by user action (explicit uploads, manual syncs).

### Future model (high-volume capture surfaces)

As continuous capture surfaces mature — GitHub capture running daily, Linear integration tracking issues in real time, future passive surfaces — signal volume can become high and bursty. A single active engineer could emit dozens of signals per day. Direct synchronous ingestion creates pressure on the pipeline and risks blocking or losing signals during processing spikes.

The natural evolution is a **message broker** (e.g. Kafka) between surface emission and signal persistence:

```
Capture Surface  →  [broker queue]  →  Signal consumer  →  persist ExperienceSignal  →  derive ExperienceClaim
```

Benefits:
- **Durability**: signals are not lost if the processing pipeline is slow or temporarily unavailable — they wait in the queue
- **Backpressure**: high-volume surfaces (continuous GitHub capture) produce signals at their own rate; the consumer processes them at a sustainable rate
- **Replay**: if dedup logic or extraction quality improves, the queue can be replayed to reprocess signals without re-triggering the surface
- **Decoupling**: adding a new surface means producing to the queue — the downstream processing pipeline is unchanged

This is not a near-term concern, but the data model should not preclude it. Persisting signals as first-class DB rows (rather than transient processing artifacts) ensures the platform can slot a broker in front of persistence without redesigning the storage layer. The signal row IS the durable record regardless of whether it arrived via direct write or queue consumer.

---

## Supplementary Data

Accumulated context on a canonical Experience Claim that goes beyond the primary text. Metrics, specifics, version details, and quantified outcomes extracted from source signals.

- Stored in a `supplementary` JSONB field on the Claim
- **Not displayed prominently in the UI** — the Claim's primary text stays atomic
- **Appended at prompt-build time** — the LLM receives both the primary text and supplementary context

Example:
- Primary text: *"Led API migration to GraphQL"*
- Supplementary: `["REST to GraphQL", "3 services", "reduced p99 latency by 40%", "Q3 2024"]`
- LLM sees: *"Led API migration to GraphQL [context: REST to GraphQL, 3 services, reduced p99 by 40%, Q3 2024]"*

Supplementary data grows as new signals roll up into the Claim. For skills, it is typically empty or version-specific.

# Platform Maturity: Architecture Direction

**Date:** 2026-04-20

This document captures the architectural direction agreed on during the Day 8 gap detection work.
It is a turning point — Tailord transitions from "works for demos" to "measurable, improvable, production-grade."

---

## The Core Diagnosis: LLM Calls Must Have Single Responsibilities

### What went wrong with the original gap analyzer

The initial `gap_analyzer.py` made one large LLM call that asked the model to:
1. Read the candidate's full profile
2. Read all job requirements
3. Score each requirement (STRONG / PARTIAL / GAP)
4. Write targeted questions for the gaps

This is a compound task. The LLM was asked to be a scorer AND a question writer in the same pass.

The result: gap scores diverged from the chunk matcher scores. One gap question appeared for a
requirement that `chunk_matcher.py` had already scored STRONG (2). The LLM re-derived its own scores
independently — and they disagreed.

### The fix

Use `JobChunk.match_score` (set by the chunk matcher) as the **authoritative source of truth**.
The gap analyzer now:
- Queries `JobChunk` where `match_score == 0` and `should_render == True`
- Treats those as confirmed gaps — no re-scoring
- Makes **one focused LLM call per gap chunk** to generate a targeted question only
- Derives `sourced_claim_count` / `unsourced_claim_count` arithmetically — no LLM

Each LLM call now has exactly one job: "given this confirmed gap requirement, write a question."

### The principle

> Every LLM call should have a single, narrow responsibility. If you can state it in one verb, it's right.

Examples of good single-responsibility calls:
- "Extract structured profile from resume text"
- "Score this requirement chunk against this profile"
- "Write an advocacy blurb for this evidenced requirement"
- "Generate a follow-up question for this confirmed gap"

Examples of compound calls to avoid:
- "Score requirements AND generate questions"
- "Extract profile AND assess quality AND suggest improvements"
- "Parse job AND score fit AND write advocacy text"

This principle also makes LLM calls independently testable and independently replaceable
(e.g. swap the question generator for a different model without touching the scorer).

---

## The Vector/Embedding Roadmap

### Why we're not doing it now

Before adding infrastructure (pgvector, embeddings), we need a measurement baseline.
Without an eval pipeline, we cannot know if embeddings make things better or worse.
The architecture is "right" enough for now — the chunk-based matching works. Fix
quality issues you can measure before adding new systems.

### What the architecture will eventually look like

```
Job Requirements
      │
      ▼ [chunk splitter — deterministic]
Job Chunks (text)
      │
      ▼ [embedding model — deterministic, fast]
Chunk Embeddings (pgvector)
      │
      ▼ [cosine similarity — deterministic, instant]
Top-K ranked ExperienceChunks per JobChunk  ← context reducer, not scorer
      │
      ▼ [LLM — scoring + generation]
STRONG / PARTIAL / GAP score + advocacy blurb
(LLM sees: job requirement + top-K relevant chunks only — not the full profile)
```

Key insight: cosine similarity is a **retrieval mechanism, not a reasoning mechanism**. Use it to
reduce the LLM's context from "full profile" to "the most semantically relevant experience chunks
for this requirement." The LLM still assigns STRONG/PARTIAL/GAP — it reasons about temporal
constraints ("5+ years"), contextual relevance, and partial matches in ways that threshold math
cannot. What changes is the *input* to the LLM scoring call, not the presence of the LLM itself.

Keep LLM for: scoring (on pre-selected context), advocacy blurbs, gap questions, tailored letter.

### Context-attached retrieval: preserving reasoning quality

Embeddings and LLM prompts have opposing context needs:
- **Best embedding:** claim content only — "Developed backend microservices in TypeScript." Company
  name, job title, and dates are noise that distorts cosine similarity. The vector should represent
  *what was done*, not *where*.
- **Best LLM reasoning:** full provenance — the LLM needs to know the company, role, and years to
  write "In your role as Software Engineer at ACME (2020–2025)..." and to reason about "5+ years."

The resolution: **embed claim content only; attach context at retrieval time.**

`ExperienceChunk` already stores `group_key`, `date_range`, `source_ref`, `technologies`. When
building the LLM scoring call, annotate each top-K chunk with these fields and group chunks from
the same position together. The LLM receives structured, position-grouped context rather than a
flat list of 8 unrelated bullets. This mirrors the full profile format — scoped to relevant chunks.

Do NOT enrich chunk content with position context at write time. Baking "Software Engineer at ACME
2020–2025:" into the chunk text dilutes the semantic signal for embeddings, causes data duplication
(every bullet repeats the same position header), and locks prompt formatting to write time instead
of retrieval time.

### What changes with embeddings

| Today | With embeddings |
|-------|----------------|
| LLM scores requirement against full formatted profile | LLM scores requirement against top-K most similar ExperienceChunks |
| High LLM context = noisy, unfocused reasoning | Smaller, targeted context = sharper LLM reasoning |
| Scoring varies run-to-run (temperature > 0) | Pre-selection is deterministic; scoring still LLM-driven |
| Hard to measure "did this change make matching better?" | Directly measurable: recall@k, precision of pre-selection |
| LLM re-derives scores on every regen | Cache embeddings; only re-embed on profile change |

---

## Recommended Sequencing

### 1. Fix gap analyzer (now — this session) ✅
Rewrite `gap_analyzer.py` to use chunk scores. Single-responsibility question generation.
See `08-gap-detection-implementation.md`.

### 2. Day 9: Claude Code workflow
Path-specific rules, hooks, pre-commit quality gates. Internal tooling, not product.

### 3. Day 10: Test coverage + eval pipeline foundation
- pytest coverage push (target: chunk_matcher, gap_analyzer, requirement_matcher)
- Eval harness: fixture jobs + candidate profiles → expected chunk scores
- Regression gate: "did this change break known-good match outcomes?"
- This baseline makes all future matching improvements measurable

### 4. Experience chunking model (post-Day 10 sprint)
Break `extracted_profile` JSON into first-class `ExperienceChunk` records.
Each chunk = one atomic claim (e.g. "Led rewrite of payment service, reduced latency 40%").
Structured: `source`, `claim_type`, `date_range`, `technologies[]`, `embedding` (nullable).
This is the data model prerequisite for vector matching.

### 5. Embeddings infrastructure
- Add `pgvector` extension to PostgreSQL
- Add `embedding` column to `ExperienceChunk` and `JobChunk`
- Embed on write (background task); re-embed on profile update
- Pre-selection: cosine similarity retrieves top-K ExperienceChunks per JobChunk
- Scoring: LLM still assigns STRONG/PARTIAL/GAP, but against top-K chunks instead of full profile
- Keep LLM for: scoring (focused context), advocacy blurb generation, gap question generation, tailored letter

### 6. Eval integration
- Re-run eval harness against vector-matched results
- Compare recall, precision, and tailoring quality vs. LLM-scored baseline
- Ship when vector matching is measurably better (or equal + faster)

### 7. Conversational enrichment UX (TBD)
Gap questions → conversational follow-up → experience claims added inline.
The gap detection we built in Day 8 is the first step toward this.
The "Proactive Guided Enrichment" north star from product memory.

---

## What This Unlocks

When matching is deterministic (vectors) and measurable (eval pipeline):
- A/B test model changes with confidence
- Surface accuracy metrics in admin panel
- Partner API (`POST /enrich`) can guarantee SLA on match quality
- Candidate experience becomes a knowledge graph, not a blob of text

This is the foundation for the headless enrichment layer (north star #2 from product memory):
job boards call Tailord's API, get structured enrichment data, surface it in their own UI.
That requires deterministic, fast, measurable matching — which is what this roadmap delivers.

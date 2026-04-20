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
Ranked candidate experience chunks
      │
      ▼ [LLM — generation only]
Advocacy blurbs + tailored output
```

Key insight: move all **matching** to vectors (deterministic, measurable, fast), keep LLM for
**generation** (advocacy blurbs, gap questions, tailored letter). This minimises the LLM's exposure
to decisions it tends to make inconsistently.

### What changes with embeddings

| Today | With embeddings |
|-------|----------------|
| LLM scores each job requirement against full profile | Cosine similarity ranks experience chunks against requirement vector |
| Scoring varies run-to-run (temperature > 0) | Matching is deterministic |
| Hard to measure "did this change make matching better?" | Directly measurable: recall@k, MRR |
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
- Scoring: cosine similarity replaces LLM scoring call
- Keep LLM for: advocacy blurb generation, gap question generation, tailored letter

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

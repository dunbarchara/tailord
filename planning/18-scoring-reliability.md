# Scoring Reliability — Philosophy and Architecture

*How we think about chunk matching quality, why prompt engineering alone can't scale, and the architectural direction toward more reliable scoring.*

---

## The Core Problem

Chunk matching asks an LLM to simultaneously:
- Hold a full candidate profile in context (hundreds of tokens of JSON)
- Read N requirement chunks
- Score each one independently on a 4-point scale
- Write a sourced rationale per chunk
- Write a 1–2 sentence advocacy blurb per chunk (for scored results)
- Determine whether each chunk should render in the public view
- Follow 11 scoring rules and study 7 detailed examples

All in a single call. For a capable hosted model (GPT-4, Claude) this mostly works. For a local 12B model with limited effective context, the quality of any individual decision degrades as the prompt grows — attention is finite, and a large system prompt competes with the actual task.

The visible failures (Terraform being inferred from Kubernetes, advocacy blurbs using placeholder names literally) aren't isolated bugs to fix individually. They're symptoms of the same root cause: the model is doing too much at once and the signal-to-noise ratio in the prompt is too low.

---

## Why Prompt Iteration Doesn't Scale

A job posting has potentially hundreds of requirements across thousands of possible skill domains. The prompt cannot anticipate all of them. Every time a specific case is handled by adding a rule ("do not infer Terraform from Kubernetes"), the prompt grows, the model's attention per instruction decreases, and a new edge case somewhere else appears.

The goal of the system prompt should be to teach the model *how to think about scoring*, not to enumerate every case that could go wrong. The more the prompt tries to prevent specific errors by example, the less generalizable it becomes.

**Principle: prompts should be minimal and abstract.** Rules describe *reasoning patterns*, not domain-specific exceptions. Examples illustrate *structure*, not encyclopedic coverage. If a rule is needed to prevent a specific hallucination on a specific technology, it's a sign the architecture is doing too much in one call.

---

## The Evidence Extraction Architecture

The highest-leverage fix is decomposing the combined scoring call into two distinct, simpler tasks.

### Phase 1 — Evidence Extraction (profile-side)

One call over the candidate profile. The task is narrow and well-defined:

> *"Given this candidate profile, extract a flat list of explicit, atomic evidence claims. Each claim must be directly stated in the profile — do not infer. Include negative claims for notable absences."*

Output:
```
- Has Kubernetes experience in production (AKS, 3+ years, Microsoft)
- Has used Docker, Helm, and Istio explicitly in work experience
- Has TypeScript in technical skills
- Led CI/CD pipeline overhaul (tripled deployment frequency)
- No mention of Terraform, Pulumi, or AWS anywhere in profile
- 5.0 years total professional experience (computed)
- BS in Computer Science, University of Arizona
```

This is a simpler task with a constrained output. The model is reading and summarizing, not scoring. The evidence list is human-readable, auditable, and useful as a standalone artifact (see: profile snapshot, Level 2 in the debug roadmap).

### Phase 2 — Scoring Against Evidence (requirement-side)

Score each requirement chunk not against the raw profile JSON but against the condensed evidence list. Each call is now:

- ~15–20 evidence bullets (constant per tailoring)
- 3–5 requirement chunks
- Shorter, simpler system prompt (no complex examples needed — the task is unambiguous: does evidence match requirement?)

The Terraform hallucination becomes structurally impossible: the evidence list explicitly states "No Terraform" and the model cannot invent it because it's not present to reason about.

### Tradeoffs

| | Current (one call) | Evidence extraction (two phases) |
|--|--|--|
| LLM calls per tailoring | 1 call per batch of N chunks | 1 extraction call + N/batch scoring calls |
| Context per scoring call | Large (full profile + chunks + long prompt) | Small (evidence list + chunks + short prompt) |
| Failure isolation | One batch parse error corrupts N chunks | Error in extraction propagates; scoring errors isolated to one call |
| Reliability on local models | Degrades with context size | More stable — each call is simpler |
| Evidence list as artifact | Not available | Auditable, storable as profile snapshot |
| Implementation complexity | Current state | Requires new extraction step + evidence model |

The latency cost is partially offset by smaller, more parallelizable scoring calls. The total token usage may actually decrease because the scoring prompt is much smaller.

### When to build this

This is a meaningful architectural change. It should be validated before committing:
1. Trim the current prompt first (remove redundant examples, tighten rules) — quick wins that may be sufficient for hosted models
2. Reduce batch size from ~8–10 to 3–5 chunks — reduces per-call context with no architecture change
3. Build the eval pipeline (Level 4) to establish a measurement baseline
4. Prototype evidence extraction and compare agreement scores against baseline

Without measurement, there's no way to confirm the architecture change improved things.

---

## Vectors, Embeddings, and Semantic Retrieval

Embeddings are a natural next step after evidence extraction is validated.

### What they are

An embedding model converts a piece of text into a high-dimensional numerical vector. Texts with similar meaning cluster together in vector space — you can measure how semantically similar two pieces of text are by computing the distance between their vectors.

This is different from keyword matching. "Led CI/CD pipeline overhaul" and "built deployment automation" have no words in common but are semantically close; an embedding model will place them near each other.

LLMs use embeddings internally to represent token relationships. Embedding models are separate, smaller, purpose-built models (e.g. OpenAI `text-embedding-3-small`, or locally runnable sentence transformers) that just produce vectors — no generation.

### How this applies to Tailord

The evidence extraction phase is essentially a retrieval problem: *"which parts of this profile are relevant to this requirement?"* Right now we hand the entire profile to the LLM and ask it to figure that out. With embeddings, you can do this retrieval computationally before the LLM call:

1. At profile processing time: embed each experience bullet, skill, and education entry individually. Store the vectors.
2. At scoring time: embed the requirement chunk. Retrieve the top-K most semantically similar profile entries (cosine similarity).
3. Send only those retrieved entries to the LLM for scoring — not the full profile.

This is **RAG (Retrieval-Augmented Generation)** applied to the candidate profile. The LLM call gets a small, pre-filtered context window of the most relevant evidence, rather than the full unfiltered profile.

### Why this matters for the architecture

- Scoring calls become even smaller — instead of 15–20 evidence bullets, you might send 3–5 semantically relevant ones per requirement
- The retrieval step is fast and cheap (vector math, no LLM call)
- It scales naturally: a profile with 50 experience bullets is no more expensive to score against than one with 10, because retrieval pre-selects the relevant subset
- It's the right foundation for the "breaking large JSON into bite-sized chunks" direction — you're not sending the whole profile anywhere, you're retrieving relevant pieces on demand

### Infrastructure

Postgres already supports vectors via the `pgvector` extension — no new database needed. Sentence transformers can run locally. The only new moving part is the embedding step at profile processing time and a vector similarity query at scoring time.

### When to build this

Embeddings are additive on top of the evidence extraction architecture. The right order is:
1. Evidence extraction (Phase 1 above) — establishes the retrieval pattern without vectors
2. Eval pipeline — measurement baseline
3. Replace the "full evidence list" with "semantically retrieved evidence" — validate that agreement scores improve

Jumping straight to embeddings without first validating evidence extraction adds two unknowns at once.

---

## Summary

| Principle | Application |
|-----------|------------|
| Prompts should be minimal and abstract | Rules teach reasoning patterns, not domain exceptions. Examples show structure, not coverage. |
| Don't iterate prompts to chase specific failures | Specific errors are symptoms of architectural overload, not prompt gaps. |
| Decompose combined tasks into simpler sequential calls | Evidence extraction + scoring separately outperforms combined extraction+scoring+advocacy in one shot. |
| Measure before committing to architecture changes | The eval pipeline exists to make prompt and architecture changes verifiable, not anecdotal. |
| Vectors augment retrieval, not generation | Embeddings pre-select relevant evidence; the LLM still does the reasoning. Add after extraction architecture is stable. |

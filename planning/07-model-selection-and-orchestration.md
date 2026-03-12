# Model Selection and LLM Orchestration Strategy

## Context

This document captures thinking on model selection and system-level orchestration for Tailord's LLM pipeline. The goal is to extract maximum quality from a range of model tiers — including smaller, budget-friendly options — through smart orchestration rather than defaulting to expensive frontier models for every call.

The motivating observation: during chunk enrichment evaluation, a mid-tier model failed to connect "owned infrastructure for a 40+ microservice Kubernetes cluster" to the requirement "design and implement complex, scalable software architectures." It also miscalculated total years of experience from raw date ranges, and incorrectly stated a candidate had no CS degree when one was explicitly in the profile. These are not fundamentally hard problems — they are fixable through better context preparation and prompt design, independent of model choice.

---

## The Model Landscape

| Tier | Models | Strengths | Weaknesses |
|---|---|---|---|
| **Frontier** | Claude Opus 4.6, GPT-4o | Best reasoning depth, nuanced implicit signal detection, strong instruction following | Cost (~$15/M input tokens), latency |
| **Mid-tier** | Claude Sonnet 4.6, GPT-4o-mini | Strong at structured extraction, reliable JSON, good reasoning on focused tasks | Occasional failure on multi-step inference, misses implicit connections |
| **Small/local** | Llama 3.1 8B/70B, Mistral, Qwen 2.5 | Near-zero cost, privacy-preserving, offline-capable | Inconsistent JSON output, struggles with large context, misses implicit signals |

---

## Core Insight: Models Are Not the Only Lever

The right framing is treating **each LLM call as a precision instrument**. Model capability requirements drop significantly when you tighten what each call actually needs to do. The goal is to reduce the reasoning burden on the model by doing as much as possible in deterministic code before the LLM is invoked.

---

## Orchestration Improvements (Highest ROI First)

### 1. Pre-computation Over LLM Inference

Every factual calculation handed off to Python is one less reasoning step the LLM can fail. Implemented in Day 5.5: total years of experience and a chronological role list are now pre-computed and injected as `[COMPUTED SIGNALS — treat as ground truth]` before the raw profile data.

**Further opportunities:**
- Pre-compute skill frequency: how many roles mention Docker vs how many job requirements mention Docker
- Pre-extract structured signals: degree name, graduation year, named technologies — structured lookups before unstructured reasoning
- Pre-label sections: classify each job posting section as `evaluable | non-evaluable` before enrichment, so the LLM never processes "What We Offer" or application form content

### 2. Section-Aware Pre-Filtering

"What We Offer" items (benefits, perks, compensation, culture statements) being scored as Gap is a section-awareness problem. The model receives the section label but doesn't weight it appropriately.

A pre-filter pass before chunk enrichment — classifying sections as evaluable or non-evaluable based on section header — would let the platform skip enrichment entirely for non-evaluable sections. Zero LLM cost, zero false Gap scores for company perks.

**Candidate non-evaluable sections:** "What We Offer", "Benefits", "About Us", "Our Culture", "Compensation", "Equal Opportunity", "Apply for this job"

### 3. Few-Shot Examples in Scoring Prompts

The current chunk matching prompt uses rules. Models follow examples more reliably than rules, especially smaller models. Adding 2–3 worked examples (chunk + profile snippet → correct score + rationale) directly in the system prompt would significantly improve consistency across model tiers.

The gap between Opus and Sonnet on structured scoring tasks narrows substantially with good few-shot examples. This is likely the highest-leverage prompt improvement remaining.

**Example structure for each shot:**
```
CHUNK: "4+ years of professional software engineering experience"
SECTION: Requirements
PROFILE SIGNAL: Total professional experience: 5.2 years
CORRECT: score=2, rationale="Pre-computed total of 5.2 years directly satisfies the 4+ year requirement.", source=resume
```

### 4. Candidate Fact Sheet Indexing Pass

A single call that produces a compact structured "candidate fact sheet" from the raw profile — key skills with evidence, total YOE, education, notable projects — before scoring begins. All subsequent chunk scoring calls use the fact sheet instead of the full raw profile.

**Benefits:**
- Dramatically reduces context size for scoring calls, enabling smaller/cheaper models
- Concentrates profile summarisation into one call where a larger model can be used if needed
- Fact sheet can be cached and reused across multiple tailorings for the same candidate

### 5. Targeted Self-Verification on Low-Confidence Scores

For chunks scored 0 (Gap) on items that seem likely to match — particularly YOE requirements, named technologies, and education — run a second focused verification call:

> "Here is the specific requirement and the candidate's relevant experience. Does the candidate meet this? Respond yes/no with a one-sentence reason."

This is cheap (small context, binary output) and significantly reduces false gaps. Appropriate as a review pass on the slow enrichment pipeline before persisting results.

---

## Suggested Model Allocation by Task

| Task | Suggested Model | Rationale |
|---|---|---|
| Profile extraction (resume parse) | Sonnet 4.6 or local 70B | Structured fill-in, tolerant of larger context, highly deterministic |
| Job extraction | Sonnet 4.6 | Moderate reasoning, structured output, repeated frequently |
| Requirement matching (fast pipeline) | Sonnet 4.6 | Single call, small context, structured JSON |
| Chunk enrichment (slow pipeline) | Sonnet 4.6 + few-shot examples | Repeated structured scoring — few-shot design closes most gap to Opus |
| Tailoring generation | Opus 4.6 | Only call where prose quality and nuanced advocacy directly affect the user-visible output — this is what users judge the product by |
| Candidate fact sheet (if implemented) | Sonnet 4.6 | Summarisation task, cached result |

### Rationale for Opus on Tailoring Only

The tailoring document is the primary user-visible output. Quality there has direct product impact. Opus pays for itself here. All other calls are infrastructure — the user never directly reads the chunk scores or extracted job JSON — so optimising for cost and reliability in the pipeline while reserving quality budget for the final output is the right trade-off.

---

## Local Model Considerations

Running a local LLM (Ollama, LM Studio) via the configurable `LLM_BASE_URL` is already supported. For extraction and scoring tasks, a well-prompted 70B model (Llama 3.1, Qwen 2.5) performs comparably to Sonnet on structured tasks when:

1. Context is kept small (fact sheet approach helps significantly)
2. Few-shot examples are provided
3. Temperature is low (0.0–0.1)
4. Response format is strictly specified (JSON schema)

The main failure modes for local models are: silent truncation on long contexts, drifting from JSON format mid-response, and missing implicit semantic connections. All three are mitigatable through the orchestration improvements above.

### Local Model Recommendations (M1 Max 32GB, no latency constraint)

At 4-bit quantization, rough memory requirements are ~0.55 bytes/parameter.

| Model | Est. memory | Notes |
|---|---|---|
| **Qwen2.5-32B-Instruct Q4_K_M** | ~18–20GB | Top pick — best JSON array reliability, strong multi-step reasoning, excellent instruction following |
| Qwen2.5-14B-Instruct Q8_0 | ~15GB | Strong second choice; Q8 preserves more quality than Q4 at 14B |
| Phi-4 14B Q5_K_M | ~10GB | Significant upgrade over phi-4-mini within the same family |
| Llama 3.3 70B Q4_K_M | ~40GB | Does not fit in 32GB |

Qwen2.5's JSON adherence is the primary reason to prefer it over Llama for structured scoring tasks. Exact array length compliance — returning exactly N results for N input chunks — is the most common local model failure point, and Qwen2.5-32B handles it reliably.

**Batch size:** Reduce `BATCH_SIZE` to 5 (from 10) when running local models. Smaller batches significantly reduce JSON truncation errors — the model has fewer elements to track before closing the array.

---

## Summary: Improvement Priority

| Priority | Improvement | Effort | Impact |
|---|---|---|---|
| ✅ Done | Pre-computed YOE and role signals | Low | High — eliminates factual errors on any model |
| ✅ Done | Explicit N/A guidance for company perks | Low | Medium — eliminates false Gap scores for benefits |
| Next | Section pre-filtering (skip non-evaluable sections entirely) | Low | Medium — reduces cost, eliminates a class of errors |
| Next | Few-shot examples in chunk matching prompt | Medium | High — narrows Sonnet/Opus quality gap |
| Later | Candidate fact sheet indexing pass | Medium | High — enables smaller models for scoring |
| Later | Targeted self-verification on Gap scores | Medium | Medium — reduces false negatives on requirements |

# Prompt Optimization Strategy

A brainstorm and strategy document for building a continuous improvement pipeline for Tailord's LLM prompts. The goal: move from prompts that were written once and never revisited to prompts that improve automatically, with stronger models reviewing the work of faster/cheaper ones.

---

## The Problem

We have 8 production prompts spanning three problem classes:

| Prompt | Class | Temperature | Output type |
|--------|-------|-------------|-------------|
| `profile_extraction` | Structured extraction | 0.1 | JSON |
| `github_enrichment` | Structured extraction | 0.1 | JSON |
| `user_input_parse` | Structured extraction | 0.1 | JSON |
| `job_extraction` | Structured extraction | 0.2 | JSON |
| `requirement_matching` | Classification | 0.1 | JSON |
| `chunk_matching` | Classification + advocacy | 0.1 | JSON |
| `tailoring` | Generation | 0.3 | JSON (prose fields) |
| `gap_analysis` | Generation | 0.3 | JSON (prose fields) |

These prompts are currently static Python constants. When output quality degrades, we notice anecdotally or not at all. There is no systematic way to:
- Know whether a prompt change made things better or worse
- Test a prompt across a range of realistic inputs before deploying
- Detect that a model update caused a regression
- Improve prompts automatically without developer time

---

## Mental Model: Three Loops

Think of prompt quality improvement as three nested loops:

**Loop 1 — Online evaluation (real traffic)**
Every production call is scored automatically by a judge. No golden dataset required. Gives a continuous quality signal over real, diverse inputs.

**Loop 2 — Offline evaluation (golden dataset)**
A curated set of hand-labeled examples. A prompt candidate must pass this before touching production. This is your regression safety net.

**Loop 3 — Automated optimization (unsupervised improvement)**
A scheduled process that reads Loop 1/2 scores, generates prompt candidates using a stronger model, evaluates them offline, and promotes winners. This is the unsupervised loop.

The three loops reinforce each other: Loop 1 surfaces new failures worth adding to Loop 2, and Loop 2 is the test suite that Loop 3 must pass.

---

## Part 1 — What "Good" Means Per Prompt

Before building any pipeline, we need to define what we're optimizing. This is the hardest part.

### Structured extraction prompts

These are the easiest to evaluate — the output is JSON and correctness is largely objective.

**`profile_extraction`**
- Field coverage rate: how many expected fields are populated vs. blank?
- Bullet fidelity: are work experience bullets extracted verbatim, or are they paraphrased/truncated?
- No hallucination: is there anything in the output that has no basis in the input?
- Contact field accuracy: is the email/phone/LinkedIn correct when present?
- Summary quality: if generated (no summary on resume), is it accurate and non-generic?

Evaluation approach: diff expected vs. actual JSON on a golden set. Rule-based checks + LLM-as-judge for summary quality.

**`github_enrichment`**
- Stack accuracy: does `detected_stack` match a manual review of the repo's dependencies and code?
- Domain accuracy: is `project_domain` correct?
- Summary conciseness: is `readme_summary` within the expected token range and non-redundant?

Evaluation approach: spot-check against real repos; rule-based length checks; LLM-as-judge for accuracy.

**`user_input_parse`**
- Claim atomicity: are the output claims truly atomic, or are compound claims merged?
- Completeness: are any claims from the input omitted?
- No fabrication: are all claims grounded in the input?

Evaluation approach: count expected claims vs. actual, check for dropped content.

**`job_extraction`**
- Requirements recall: are all stated requirements captured? Are any fabricated?
- Category accuracy: are requirements, responsibilities, and preferred qualifications correctly bucketed?
- Company/title accuracy: correct extraction from noisy scraped text.

Evaluation approach: human-labeled golden set of job postings; LLM-as-judge for recall.

---

### Classification prompts

**`requirement_matching`**
- Score accuracy: does the STRONG/PARTIAL/NONE score match a human reviewer's judgment?
- Rationale quality: does the rationale cite specific evidence from the profile?
- Source attribution: are experience_sources correct?

Primary metric: classification accuracy against human-labeled pairs (candidate profile × job requirements → expected scores). Cohen's Kappa for inter-annotator agreement when building the golden set.

**`chunk_matching`** (the most complex prompt — most to gain)
- Score accuracy: same as requirement_matching, plus the -1 (non-evaluable) class for job board chrome.
- `should_render` accuracy: is boilerplate correctly suppressed?
- Advocacy blurb quality: is the blurb specific to the candidate? Does it respect the score (partial should sound partial)?
- No overclaiming on partials: a known failure mode — the model over-advocates when the evidence is thin.
- YOE threshold handling: does the model use COMPUTED SIGNALS rather than re-deriving from dates?

Primary metric: classification accuracy + advocacy quality rubric (5 dimensions, scored by Opus/GPT-4o).

---

### Generation prompts

These require LLM-as-judge because there is no "ground truth" — quality is about tone, specificity, and fidelity to the system prompt rules.

**`tailoring`**
Evaluation rubric (score each dimension 1–5):
1. **Sourcing**: every claim traces back to the candidate's profile. No fabricated details.
2. **Specificity**: concrete numbers/outcomes/technologies, not generic statements.
3. **Voice consistency**: third-person throughout; no "I" statements.
4. **Advocacy score**: headers reflect candidate strengths, not job requirements verbatim.
5. **Gap handling**: partial matches are framed constructively; genuine gaps are omitted.
6. **No repetition**: closing does not echo specific phrases from body sections.
7. **Section count**: 3–5 advocacy statements (not fewer, not more).

LLM-as-judge prompt: give the judge the system prompt rules, the candidate profile, the job, and the generated tailoring. Ask it to score each dimension and explain failures.

**`gap_analysis`**
Evaluation rubric:
1. **Specificity**: question references the specific role/company, not a generic skill.
2. **Buildability**: for partial matches, question asks for a richer example, not "do you have experience with X?"
3. **Brevity**: one sentence preferred, two at most.
4. **Invitation tone**: question reads as collaborative, not interrogative.
5. **Context accuracy**: context explains why this matters for THIS role specifically.

---

## Part 2 — Tooling Landscape

### DSPy
**What it is:** A framework that treats prompts as programs with typed signatures. Optimizers (BootstrapFewShot, MIPRO, MIPROv2) search for better instruction text and/or few-shot examples given a golden dataset and a metric function.

**Best fit:** Structured extraction and classification prompts where the metric is objective (field coverage, classification accuracy). Works well for `profile_extraction`, `requirement_matching`, `chunk_matching`.

**How it works in practice:**
1. Define a DSPy `Signature` for each prompt (inputs → outputs).
2. Define a `metric(example, prediction)` function.
3. Run `MIPROv2(metric=metric).compile(module, trainset=golden_set)` — this calls a stronger model (Opus/GPT-4o) many times to find instruction variants that maximize your metric.
4. The result is an optimized prompt you can export as text and paste back into your prompt file.

**Tradeoffs:**
- Requires rewriting prompts as DSPy modules — moderate refactor.
- MIPRO is expensive to run (many teacher model calls).
- Output is a prompt string, not a diff — need tooling to track versions.
- Less natural for prose generation prompts where the metric is inherently subjective.

**Verdict:** Strong choice for our classification/extraction prompts. Worth integrating for `chunk_matching` in particular — it has the highest complexity and the most explicit scoring rules.

---

### Langfuse
**What it is:** Open-source LLM observability platform. Has prompt management, online evaluation, and dataset tooling on top of its trace/span model.

**Why it fits Tailord's stack:**
- Can run as a Docker container alongside our existing LGTM stack. One more service in docker-compose.
- Captures all LLM calls via SDK decorator or OTel integration — plugs directly into our existing `llm_utils.py` instrumentation.
- **Prompt management**: prompts are stored in Langfuse, versioned, and fetched at runtime. Replaces hardcoded Python string constants. Enables A/B routing, rollback, environment-specific variants.
- **Datasets**: production I/O pairs can be added to datasets directly from traces, with a UI for labeling.
- **Evaluators**: attach an LLM-as-judge evaluator to any trace — runs automatically, posts scores back as metrics.
- **Dashboards**: per-prompt quality trends over time. Queryable by prompt version, model, user segment.

**Tradeoffs:**
- Yet another service to self-host. The managed version (Langfuse Cloud) reduces ops burden.
- Adds a runtime dependency: prompts fetched from Langfuse must be cached for latency (they have a local cache SDK, so this is handled).
- Does not include an optimizer — it is an evaluation and management platform, not a self-improving system.

**Verdict:** The most practical first step. The prompt management + dataset + evaluation story is exactly what we need before we can run any optimization loop. Think of it as the data layer that makes optimization possible.

---

### Promptfoo
**What it is:** CLI tool for prompt testing and comparison. Config-driven (YAML): define prompts, test cases, providers, and evaluators.

**Strengths:**
- Zero code changes to the app. Standalone evaluation harness.
- Very fast for A/B comparisons: "does prompt v2 score better than v1 on these 50 test cases?"
- Supports LLM-as-judge evaluators out of the box.
- Great for one-off prompt experiments before committing to a new version.

**Limitations:**
- Not self-improving — it evaluates but does not optimize.
- No online evaluation (production traffic integration requires custom glue).
- No built-in prompt versioning or dataset management.

**Verdict:** A useful tactical tool for quick prompt experiments. Complement to Langfuse, not a replacement.

---

### Braintrust
**What it is:** Hosted eval platform. Strong UI for reviewing outputs, comparing experiments, and building datasets.

**Strengths:**
- Best-in-class DX for manual review of LLM outputs.
- Native support for scoring functions and LLM-as-judge.
- Good SDK for logging evals from CI.

**Limitations:**
- SaaS/hosted — data leaves our infrastructure. Matters because our inputs include resume text and job applications (PII-adjacent).
- Cost at scale.

**Verdict:** Good if we want to move fast without self-hosting. But Langfuse is the better fit given our existing infrastructure and data sensitivity.

---

### OpenAI Evals / Anthropic Model Evals
Both offer frameworks for running structured evals against their models. Primarily useful for understanding how model updates affect our outputs, not for optimizing our prompts. Worth running when we upgrade model versions.

---

### Custom critique loop
A lightweight alternative to DSPy for prose prompts. The core idea:

```
1. Run current prompt on N examples → outputs
2. Run judge prompt (Opus/GPT-4o) → scores + failure reasons per example
3. Aggregate failure reasons → common failure patterns
4. Run "prompt engineer" prompt (Opus):
   input: [current system prompt] + [failure patterns] + [examples of bad outputs]
   output: [revised system prompt with targeted fixes]
5. Run revised prompt on same examples → new outputs
6. Run judge again → compare scores
7. If score improvement > threshold, flag as candidate
```

This is essentially a manual DSPy loop, but with full control over each step. Better suited to `tailoring` and `gap_analysis` where the optimization signal is qualitative.

---

## Part 3 — The Architecture We Should Build

### Recommended stack

| Layer | Tool | Why |
|-------|------|-----|
| Prompt versioning + management | Langfuse (self-hosted) | Replaces hardcoded Python strings; versioned, rollback-able, environment-aware |
| Dataset management | Langfuse datasets | Captures production I/O; UI for labeling; integrates with eval runs |
| Online evaluation | Langfuse evaluators + our OTel traces | Real-traffic quality signal, no golden set required for Loop 1 |
| Offline evaluation (CI) | Promptfoo or custom pytest harness | Fast regression check on every prompt change |
| Automated optimization | DSPy (structured prompts) + custom critique loop (prose prompts) | Best tool for each prompt class |
| A/B routing | Langfuse prompt variants + feature flag | Route X% of traffic to candidate prompt version |

---

### Data flow

```
Production traffic
       │
       ▼
llm_utils.py (already instruments spans)
       │
       ▼
Langfuse trace (via SDK or OTel bridge)
       │
       ├─── Online evaluator runs automatically ──► quality scores per call
       │         (LLM-as-judge, rule-based checks)
       │
       ▼
Langfuse dataset (curated + labeled I/O pairs)
       │
       ▼
Optimization loop (nightly or on-demand)
  ├─ DSPy MIPROv2 (structured/classification prompts)
  └─ Custom critique loop (prose prompts)
       │
       ▼
Candidate prompt version
       │
       ▼
Offline evaluation against golden set
       │
  passes? ──no──► discard, log failure
       │
      yes
       │
       ▼
A/B test on staging → promote to production
```

---

### Per-prompt optimization priority

Not all prompts are equal. Where to start:

**High priority — highest impact / easiest to evaluate:**
1. `chunk_matching` — runs ~20–100x per tailoring (batched), quality determines what the tailoring LLM sees. Scoring accuracy directly affects the tailoring output. Has objective labels (score 0/1/2/-1) and advocacy quality dimensions.
2. `requirement_matching` — also feeds directly into the tailoring. Classification accuracy is easy to measure.
3. `tailoring` — the primary user-visible output. Quality degradation is felt immediately.

**Medium priority:**
4. `profile_extraction` — if we're losing bullets or misclassifying skills, all downstream prompts suffer. But the prompt already works well.
5. `gap_analysis` — high-leverage UX moment but lower traffic volume (runs once per tailoring, not per chunk).

**Lower priority (currently solid):**
6. `job_extraction` — works reliably, input is varied but structured.
7. `github_enrichment` — good quality, low volume.
8. `user_input_parse` — very simple task, rarely fails.

---

### The unsupervised improvement loop (ideal-world version)

This is the fully automated vision. Runs on a schedule (nightly or weekly):

```python
# Pseudocode for the optimization runner
for prompt_type in PROMPT_REGISTRY:
    golden_set = load_golden_dataset(prompt_type)          # curated examples
    current_prompt = langfuse.get_prompt(prompt_type, version="production")

    # Evaluate current baseline
    baseline_scores = evaluate(current_prompt, golden_set, metric=METRICS[prompt_type])

    # Structured prompts: DSPy
    if prompt_type in STRUCTURED_PROMPTS:
        candidate = dspy_mipro_optimize(current_prompt, golden_set, METRICS[prompt_type])

    # Prose prompts: critique loop
    else:
        failures = identify_failures(baseline_scores, golden_set)
        critique = run_critique_llm(current_prompt, failures)  # Opus
        candidate = run_rewrite_llm(current_prompt, critique)  # Opus

    # Evaluate candidate
    candidate_scores = evaluate(candidate, golden_set, metric=METRICS[prompt_type])

    # Promote if strictly better
    improvement = candidate_scores.mean - baseline_scores.mean
    regressions = count_regressions(baseline_scores, candidate_scores)

    if improvement > IMPROVEMENT_THRESHOLD and regressions == 0:
        langfuse.create_prompt(prompt_type, candidate, labels=["candidate"])
        notify_slack(f"{prompt_type} candidate ready: +{improvement:.1%} on golden set")
        # Human sign-off → promote to staging A/B
    else:
        log_failed_optimization(prompt_type, improvement, regressions)
```

Human review before production promotion is intentional. The loop finds the improvements; humans decide whether they make sense before they touch real users.

---

## Part 4 — Prompt Versioning: Replacing Hardcoded Strings

Currently all prompts are Python constants in `backend/app/prompts/*.py`. This is fine for now but creates friction:
- Changing a prompt requires a code deploy.
- There is no history of what changed and why.
- You cannot roll back a prompt without reverting a commit.
- A/B testing requires code-level feature flags.

With Langfuse prompt management:

```python
# Before (current)
from app.prompts import tailoring
system_prompt = tailoring.SYSTEM

# After (Langfuse-managed)
from langfuse import Langfuse
lf = Langfuse()
prompt = lf.get_prompt("tailoring-system", version="production")  # cached locally
system_prompt = prompt.compile()  # returns the string
```

Each `get_prompt` call:
- Hits the Langfuse API (with a local TTL cache, ~1s latency on cache miss, 0ms on hit).
- Returns the version labeled "production" (or "staging", or a specific version number).
- Is traced automatically — every LLM call records which prompt version was used.

This means you can push a prompt change without a code deploy, roll back in seconds, and query "which prompt version caused this quality regression?" in the Langfuse UI.

**Migration path:** Keep the existing `prompts/*.py` files as the source of truth for now. Add Langfuse as a layer on top — on startup, seed prompts from the Python constants if they're not already in Langfuse. This avoids a hard dependency on Langfuse being available for the backend to start.

---

## Part 5 — Golden Dataset Strategy

A golden dataset for each prompt type. How to build them without spending weeks on labeling:

### Bootstrap from production (the pragmatic path)
1. Enable Langfuse trace capture in production (or staging).
2. For each prompt type, sample 30–50 recent I/O pairs from Langfuse traces.
3. Run an LLM-as-judge pass over the sampled outputs — this gives a first-pass label at near-zero human cost.
4. Do a quick human spot-check on judge outputs to calibrate — fix any systematic errors in the judge.
5. You now have ~30–50 labeled examples per prompt type in a few hours of work.

For classification prompts (`chunk_matching`, `requirement_matching`): human spot-check is important because the judge can share failure modes with the model being evaluated.

For generation prompts (`tailoring`, `gap_analysis`): judge-only labeling is more reliable because the judge is a stronger model evaluating a weaker one's output.

### Growing the dataset over time
- **Manual additions:** when a production output catches your attention (good or bad), add it to the dataset with a label directly from the Langfuse UI.
- **Failure injection:** deliberately create hard cases — edge case resumes, job postings with tricky formatting, candidates with genuine gaps — and label them.
- **Adversarial cases for known failure modes:** e.g., for `chunk_matching`, add cases with years-of-experience thresholds that are clearly not met, since that is a documented failure mode.

Target dataset sizes per prompt type:
- Extraction prompts: 30–50 examples
- Classification prompts: 50–100 examples (need coverage of all score classes)
- Generation prompts: 20–30 examples with rubric scores per dimension

---

## Part 6 — Online Evaluation in Production

Once Langfuse is ingesting traces, attach auto-evaluators:

```python
# Example: automatic quality check on every tailoring generation
# Attached in Langfuse UI or via SDK

judge_prompt = """
You are evaluating a generated Tailoring document against a rubric.

CANDIDATE PROFILE:
{profile}

JOB POSTING:
{job}

GENERATED TAILORING:
{tailoring_output}

Score each dimension 1–5:
1. sourcing (every claim has evidence in the profile)
2. specificity (concrete details, not generic statements)
3. voice (third person, advocacy tone, no "I")
4. gap_handling (partial matches framed well, gaps omitted)
5. no_repetition (closing does not echo body sections)

Return JSON: {"sourcing": N, "specificity": N, "voice": N, "gap_handling": N, "no_repetition": N, "comments": "..."}
"""
```

These scores flow into Grafana as metrics (Langfuse exports Prometheus metrics). You can alert on quality degradation just like you alert on latency or error rate.

This is what makes Loop 1 (online evaluation) work without any golden dataset — real outputs are scored in production, giving a continuous quality signal.

---

## Part 7 — A/B Testing Prompt Versions

Once a candidate prompt passes offline evaluation:

1. In Langfuse: create a new version, label it "staging".
2. In the backend: add a routing layer (thin wrapper around the Langfuse `get_prompt` call):
   ```python
   def get_prompt_version(prompt_name: str, user_id: str) -> str:
       if is_in_experiment_group(user_id, "chunk_matching_v2"):
           return langfuse.get_prompt(prompt_name, version="staging")
       return langfuse.get_prompt(prompt_name, version="production")
   ```
3. Run for 1–2 weeks with 10–20% traffic.
4. Compare online evaluator scores between groups in Grafana/Langfuse.
5. Promote staging → production if winner; discard if not.

No feature flags library needed — `is_in_experiment_group` can be a deterministic hash of `user_id + experiment_name`.

---

## Part 8 — Connection to the Observability Stack

Layer 4 (OTel tracing) already captures `llm.call` spans with `llm.prompt_type`, `llm.model`, `llm.input_tokens`, `llm.output_tokens`, `llm.latency_ms`. The Langfuse SDK can be configured as an OTel exporter, meaning traces flow through one path.

**Alternative integration:** Langfuse has a `@observe` decorator and an `openai` wrapper. Since we already have OTel spans, the simplest bridge is to write a `BatchSpanProcessor` that forwards `llm.call` spans to Langfuse, injecting the prompt version from span attributes.

This means:
- In Tempo: you see the full trace with latency waterfall.
- In Langfuse: you see the same calls with input/output, prompt version, and quality scores.
- In Grafana: quality score trends as a metric alongside latency and error rate.

---

## Part 9 — What NOT to Do

**Don't optimize all prompts simultaneously.** Start with `chunk_matching` — it runs the most, affects the most, and has objective scoring criteria. Get the evaluation loop working there, then extend.

**Don't make the golden dataset too small.** 10 examples is not enough to detect regressions reliably. 30+ per class is the minimum.

**Don't use the same model as judge and model being optimized.** If the model scoring our outputs is the same model generating them, you get in-group bias. Use Opus or GPT-4o as judge even when the production model is a smaller/faster model.

**Don't automate promotion to production without human sign-off initially.** Build trust in the loop first — run it for a few cycles and manually review whether its candidate prompts are actually better before enabling auto-promotion.

**Don't confuse latency optimization with quality optimization.** This document is about quality. Latency improvements (shorter prompts, fewer tokens) are a separate concern and should only happen after quality is benchmarked.

---

## Part 10 — Implementation Phases

### Phase 0 — Instrument (1–2 days)
- Add Langfuse to docker-compose (self-hosted, fits alongside LGTM stack).
- Add `langfuse` SDK to `backend/pyproject.toml`.
- Wrap `llm_utils.py` to forward all calls to Langfuse (input, output, prompt_type, model, latency).
- Verify traces appear in Langfuse UI before proceeding.

### Phase 1 — Evaluate (3–5 days)
- Write LLM-as-judge prompts for each of the 8 prompt types.
- Build golden datasets: sample ~40 production examples per prompt type from Langfuse traces; spot-check with judge.
- Run offline evaluation baseline: score current prompts against golden sets.
- This gives you a numeric baseline to improve against.

### Phase 2 — Version + Manage (1–2 days)
- Seed Langfuse with current prompt text from `prompts/*.py`.
- Update `llm_utils.py` to fetch from Langfuse (with fallback to Python constants if unavailable).
- Enable online evaluators in Langfuse on the tailoring and chunk_matching traces.

### Phase 3 — First optimization run (2–3 days)
- Pick `chunk_matching` as the first target.
- Run DSPy MIPROv2 on the golden set with classification accuracy as metric.
- Or run the custom critique loop manually (Opus reviews failures, rewrites prompt, evaluate).
- Compare candidate vs. baseline on golden set.
- If improvement: A/B test on staging.

### Phase 4 — Automate (3–5 days)
- Build the optimization runner (nightly cron or triggered by CI on prompt file changes).
- Integrate with GitHub: failing offline eval on a prompt change blocks the PR.
- Wire Prometheus metrics from Langfuse into Grafana: quality score trends as a panel.

---

## Open Questions

1. **Judge model selection**: Opus 4.6 or GPT-4o as judge? Opus has the advantage of knowing our system prompt philosophy (candidate advocacy, specificity, sourcing). Worth testing both and checking agreement rates.

2. **Prompt storage format**: store prompts in Langfuse as flat strings, or structured with system/user as separate fields? The latter is cleaner for the A/B comparison but requires more tooling.

3. **Few-shot examples in prompts**: `chunk_matching` already has explicit examples hardcoded in the system prompt. DSPy's BootstrapFewShot optimizer would generate and select these automatically — but then the few-shot examples live outside the prompt string, which complicates Langfuse prompt management. Worth deciding before committing to DSPy.

4. **Feedback loop from users**: right now the only quality signal is automatic (LLM-as-judge). Do we want a mechanism for users to flag a bad tailoring? That labeled data would be the highest-quality signal in the dataset.

5. **Privacy**: golden datasets contain resume text and job posting data. Both are potentially sensitive. If using Langfuse Cloud rather than self-hosted, data leaves our infrastructure. Self-hosted preferred.

6. **Model upgrade testing**: when we switch the production model (e.g., Haiku 3.5 → Haiku 4), the offline evaluation suite should run automatically to detect regressions before the new model reaches users.

---

## TL;DR for a First Sprint

If we had one sprint to spend here, this is the order:

1. Add Langfuse (self-hosted Docker) — get all LLM I/O visible in one place.
2. Write LLM-as-judge evaluators for `chunk_matching` and `tailoring`.
3. Build golden datasets from production traces (sample + judge + spot-check).
4. Run one manual critique loop on `chunk_matching` — Opus reviews failures, proposes improved prompt, we evaluate the candidate.
5. If the candidate beats the baseline, A/B test it on staging.

That loop, done once, validates whether the infrastructure is worth automating. If it produces a measurably better `chunk_matching` prompt in a sprint, automate it. If not, debug the evaluation approach first.

---

## Part 11 — User Flagging and the Feedback Queue

### The idea

The automated evaluation loop (LLM-as-judge + golden datasets) catches known failure modes. But the most valuable signal comes from a user who just generated a tailoring against a job posting we have never seen, where something went wrong in a new way we did not anticipate.

The feature: a "flag this tailoring" mechanism, admin-only initially, potentially open to all users later. When triggered, it captures the failure context and routes it into a review queue — and ultimately into the golden dataset.

### What gets captured on flag submission

When a user flags a tailoring, the system should save:

- `tailoring_id` — links to the full generation context already in the DB (profile snapshot, job URL, model, generation timestamps, OTel trace ID)
- `job_url` — already on the `Job` row, but important to re-fetch since the posting may change
- `job_html_snapshot` — fetch and store the raw HTML of the job posting at flag time. Job postings go stale (links break, postings close). The HTML snapshot is the ground truth for diagnosing what Playwright and the LLM actually received.
- `failure_category` — selected from a predefined list (see below)
- `user_notes` — optional free text, "the sections are all wrong" or "it included the entire company boilerplate as requirements"
- `flagged_by` — user ID
- `flagged_at` — timestamp
- `review_status` — `pending` / `reviewed` / `added_to_dataset` / `resolved`

### Failure categories (predefined options)

Users should not have to write a bug report — give them labels to pick from:

| Category | Description |
|----------|-------------|
| `boilerplate_noise` | Non-requirements (EEO statements, perks, about-us) appear as scored requirements |
| `incorrect_sections` | Job sections are misidentified or collapsed (e.g., responsibilities merged with qualifications) |
| `missing_requirements` | Requirements visible in the job posting are absent from the analysis |
| `wrong_scores` | Requirements are scored incorrectly (STRONG when clearly a gap, or PARTIAL when clearly STRONG) |
| `fabricated_claims` | Tailoring contains claims not grounded in the candidate's profile |
| `parse_failure` | Job posting failed to load or extracted content is clearly wrong/empty |
| `advocacy_quality` | Generated tailoring is generic, imprecise, or misrepresents the candidate |
| `other` | Anything that doesn't fit the above (requires user_notes) |

### UI placement

A "Flag this tailoring" option on the `TailoringDetail` page. For admins: always visible. For general users: could be a subtle "something wrong?" link in a footer-level position to avoid cluttering the main UI.

The flagging flow:
1. Click "Flag this tailoring"
2. Select one or more failure categories
3. Optional: add a note
4. Submit → system saves the flag, triggers an async job to fetch and snapshot the job HTML

### The review queue (admin panel)

A new section in the admin panel listing pending flags, sortable by failure category and date. Each flag expands to show:
- The tailoring output
- The job HTML snapshot
- The profile snapshot (already saved on `Tailoring.profile_snapshot`)
- The OTel trace ID (links to Tempo for the full generation waterfall)
- The failure category and user notes
- Actions: "Add to golden dataset", "Resolved — already fixed", "Won't fix — out of scope"

### Connection to the optimization pipeline

Flagged tailorings are the highest-signal examples for the golden dataset — a real user found a real failure on a real job posting. They should be prioritized over random production samples:

1. Admin reviews the flag, confirms the failure, and marks `review_status = "added_to_dataset"`.
2. The flag is linked to a Langfuse dataset entry: the job HTML + profile → expected output (or expected score for classification prompts) is labeled by the admin.
3. The golden dataset grows with battle-tested edge cases rather than just randomly sampled traffic.

This closes the feedback loop: user flags a broken case → system learns from it → the same case gets tested on every future prompt version → we never regress on it again.

### What this is NOT

This is not a user-facing "rate your tailoring" feature. We are not asking users to score quality on a 1–5 scale. Likert-scale ratings without context are noisy and hard to act on. The flag is a deliberate gesture: "this broke in a specific way" — and the failure category forces enough structure to make it useful without requiring users to write bug reports.

---

## Part 12 — Multi-Strategy Job Posting Parsing and Agents

### Do we currently use agents?

No. Our current system is a linear pipeline of structured LLM calls. Each call has a defined input, a Pydantic output schema, and a retry strategy. The developer controls the flow entirely — the LLM never decides what happens next.

The term "agent" in the contemporary sense means: an LLM that can call tools, observe results, and decide what to do next, in a loop, until a goal is reached. The LLM drives the control flow; the developer defines the tools and the stopping condition. Our system does not do this.

The question is whether the job posting parsing problem benefits from agent-style orchestration, and whether tools like Pydantic AI are a natural fit for our stack.

### The current parsing approach and its failure modes

**Current:** Playwright fetches the page (JavaScript-rendered), BeautifulSoup/readability converts the DOM to markdown text, `job_extraction.py` LLM call structures it into `ExtractedJob`.

Known failure modes:
- **Markdown conversion loses structure**: heading levels, nested lists, and visual hierarchy get flattened. A `<h2>Requirements</h2>` and a `<h3>Nice to have</h3>` may become the same indentation level in markdown.
- **Boilerplate bleed**: readability keeps paragraphs it considers "content," which on job sites often includes EEO statements, company values essays, and cookie notices — all of which end up in the LLM context and increase the chance of scoring them as requirements.
- **JavaScript-heavy SPAs**: some job boards (Greenhouse, Lever, Ashby) render sections via React with dynamically injected content. Playwright handles this, but timing is fragile.
- **Modal/banner obstruction**: cookie banners, "sign in to apply" overlays, and "create job alert" popups are in the DOM and sometimes end up in the extracted text.
- **Structured data ignored**: most job boards emit `application/ld+json` schema markup (JobPosting schema) with machine-readable title, description, requirements, and salary. We do not currently use this at all.

### Three complementary strategies

**Strategy 1 — HTML → Markdown → LLM (current)**
Readability + markdown gives the LLM clean prose. Cheap and fast. Works well for most sites. Fails when visual/semantic structure is important.

**Strategy 2 — HTML → LLM directly (no markdown conversion)**
Skip the markdown step entirely. Feed the cleaned HTML (or a sensibly pruned version of it — remove `<script>`, `<style>`, SVG, data attributes) straight to the LLM. Modern LLMs can reason about HTML structure: they understand `<h2>`, `<ul>/<li>`, `<section aria-label="requirements">`, and semantic markup that markdown conversion discards. GPT-4o and Claude Sonnet have context windows large enough to hold most job postings as HTML. This captures what markdown misses without needing a vision model.

Cost implication: a cleaned job HTML is typically 10–40k tokens vs. 2–8k tokens for the markdown version. Roughly 3–5x more expensive per call. Worth it as a fallback, not as the default path.

**Strategy 3 — Screenshot → Vision model**
Playwright dismisses banners (already partially handled), scrolls to capture the full page, takes a screenshot. Feed the screenshot to a vision-capable model (GPT-4o Vision, Claude Sonnet). The model reads the page as a human would: it sees visual hierarchy (large bold text = section header), layout (two-column "required" vs. "nice to have"), and is immune to DOM complexity entirely.

This is the highest-fidelity approach for visually complex job boards and the one most resistant to DOM obfuscation. It is also the most expensive and slowest.

**Bonus: Strategy 0 — Structured data extraction (free signal)**
Before any LLM call, check for `<script type="application/ld+json">` in the page and parse any `JobPosting` schema. Many job boards (LinkedIn, Indeed, Greenhouse) emit machine-readable title, description, requirements, and salary range this way. This is zero-cost, deterministic, and should always be attempted first — it will not cover everything but gives reliable metadata.

### Combining strategies: parallel with merge

The right architecture is not a cascade (try 1, fail, try 2) but parallel execution with a merge step:

```
Job URL
  │
  ├─── Strategy 0: extract JSON-LD schema (deterministic, ~0ms)
  ├─── Strategy 1: HTML → markdown → LLM         (cheap, ~2s)
  ├─── Strategy 2: HTML → LLM directly           (medium, ~5s)
  └─── Strategy 3: screenshot → vision LLM       (expensive, ~10s)
              │
              ▼
    Merge: reconcile 2–4 extractions
    (or quality-gate: if strategy 1 meets threshold, skip 2 and 3)
```

The merge step for `ExtractedJob` is straightforward — take the union across `requirements` lists (deduplicated by semantic similarity), use the highest-confidence value for scalar fields (title, company). A small reconciliation LLM call works well here: "given these 3 extractions of the same job posting, return the most complete and accurate synthesis."

For most job postings, strategy 1 + strategy 0 (JSON-LD) will be good enough and we never call 2 or 3. The flagging system from Part 11 tells us which job boards are consistently failing strategy 1 — those are the ones to prioritize for strategy 2/3 investment.

### Where Pydantic AI fits

Pydantic AI is a framework for building agents with Pydantic-typed tool calls and result types. It is relevant here because:

- Our stack is already Pydantic-heavy (all LLM outputs are Pydantic models validated by `llm_parse_with_retry`).
- The job parsing use case is a genuine agent problem: the parser should be able to try a strategy, assess its quality, and decide whether to try another — without the developer hardcoding that decision tree.

A job parsing agent with Pydantic AI:

```python
from pydantic_ai import Agent, RunContext

job_parser = Agent(
    model='gpt-4o',
    result_type=ExtractedJob,
    system_prompt="Parse job postings using the best available strategy. "
                  "Prefer markdown for speed; fall back to HTML if the markdown "
                  "extraction looks incomplete; use screenshot only if both fail."
)

@job_parser.tool
async def get_jsonld(ctx: RunContext[JobParseContext]) -> dict | None:
    """Extract JSON-LD JobPosting schema from the page, if present."""
    ...

@job_parser.tool
async def get_markdown(ctx: RunContext[JobParseContext]) -> str:
    """Fetch the page and convert to markdown via readability."""
    ...

@job_parser.tool
async def get_html(ctx: RunContext[JobParseContext]) -> str:
    """Fetch the page and return cleaned HTML (no scripts/styles)."""
    ...

@job_parser.tool
async def check_quality(ctx: RunContext[JobParseContext], extraction: ExtractedJob) -> str:
    """Return a quality assessment: 'good', 'partial', or 'poor'."""
    ...

@job_parser.tool
async def take_screenshot(ctx: RunContext[JobParseContext]) -> bytes:
    """Take a full-page screenshot after dismissing overlays."""
    ...
```

The agent would reason about which tools to call, observe quality, and stop when it has a good enough extraction. This is more adaptive than a hardcoded strategy waterfall.

**Tradeoffs of the agent approach:**
- More latency variance — the agent may call tools serially rather than in parallel.
- Harder to predict cost — the agent decides how many tool calls to make.
- Harder to test — the control flow is not deterministic.
- But: genuinely handles novel failure modes without code changes. The agent adapts; a fixed waterfall does not.

Pydantic AI also ships Logfire integration for tracing agent runs (tool calls, token costs, decisions). This complements our existing OTel/Langfuse stack rather than replacing it.

### Practical recommendation

This is staged work; the value increases at each stage:

**Stage 1 (quick win, 1–2 days):** Add JSON-LD extraction as a pre-LLM step. For postings that emit `JobPosting` schema, we get title/company/salary for free and the LLM has better context. No architecture change.

**Stage 2 (medium effort, 3–5 days):** Add HTML-direct as a fallback path. If strategy 1 produces fewer than N requirements or fields below a quality threshold, re-run with raw HTML. Controlled by a quality check function, not an agent. Covers 80% of the new failure cases.

**Stage 3 (higher effort, 1–2 weeks):** Add vision fallback for identified "hard" job boards — those that consistently fail strategy 1/2 based on the flagging queue from Part 11. Screenshot + vision LLM added as a third path.

**Stage 4 (architectural change):** Migrate to a Pydantic AI agent that orchestrates all strategies adaptively. Worthwhile once we have stage 1–3 working and understand the real failure distribution from production flags. The agent replaces the hardcoded quality-check logic with LLM reasoning about which strategy to try next.

The flagging system is the prerequisite for stages 2–4: without knowing which job boards fail and why, we are optimizing in the dark. Build the flag queue first, collect 4–6 weeks of failure data, then invest in the multi-strategy architecture targeting the actual failure modes we have observed.

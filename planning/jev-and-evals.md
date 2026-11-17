# Jev + LLM Evals + Per-Task Model Routing

Status: planning (started 2026-11-17)

Three linked goals:

1. Integrate **Jev** (TypeSafe AI's System One model) where its capabilities fit.
2. Build a **model-agnostic eval pipeline** to compare any number of LLMs on Tailord's tasks (quality, cost, latency, reliability).
3. Support **mixed models per task** with a global default and per-task overrides.

Order of work matters: routing → eval harness → Jev adapter in the harness → (later, separate discussion) Jev in production, gated on eval results.

---

## Context

### What Jev is (from public docs; verify against live API)

A "System One" model: it does not generate text. You send a `state` (text, JSON, or images) plus typed `questions`; it returns structured answers with calibrated probabilities. Questions are evaluated independently and in parallel, so extra questions add little latency.

- Endpoint: `POST https://api.typesafe.ai/v1/systemone`; `GET /v1/models` lists model ids.
- Auth: `Authorization: Bearer <TYPESAFE_API_KEY>`.
- Models: `jev-1.14.0`, `jev-1.13.0`; aliases `jev-latest` / `jev-preview` can move. **Always pin a versioned id** for evals so results stay comparable.
- Request: `{model, state, questions: {name: {type, instructions, criteria}}}`.
  - `choice`: `criteria` is `{option_name: description}` (1–255 options). Always picks one option; pair with a `noul` question if options might not cover the input.
  - `score`: `criteria` is an ordered list of level descriptions (1–10); index = score.
  - `noul`: yes/no probability. `box`: bounding box (1.14 only, image use; irrelevant here).
- Response: `{model, answers: {name: ...}, usage: {input_tokens, output_tokens}}`.
  - choice → `choice`, `confidence`, `probabilities`
  - score → `score` (probability-weighted, can be fractional), `confidence`, `legend`, `probabilities`
  - noul → `noul` (0–1)
- Context: 64k tokens per request, 32k per question (state + one question). Long-context header exists but is slower and less accurate.
- Rate limits per org (tokens/s, requests/s); 429 on exceed with `retry-after`.
- Pricing (company-reported, Sept 2026): input ≈ $0.042 / 1M tokens, output currently free. **Confirm in the console before trusting cost numbers.**
- Docs: https://docs.typesafe.ai/introduction, `/models`, `/api`, `/primitives`, `/cookbooks` (see "Classification using confidence": one Choice question, threshold on `confidence` to fall back to a coarser label).

### Caveats

- Performance claims are company-reported on company-built benchmarks. The point of the eval is independent numbers on Tailord's own tasks.
- Jev is not OpenAI-compatible → needs its own adapter. Prefer plain `httpx` over adding the vendor SDK (project rule: no new packages without necessity). Confirm `httpx` is already a transitive dependency before using it directly.
- Classification only: Jev cannot produce letters, blurbs, rationales, or free-form extraction.

### Where Jev fits in Tailord

| Task | Today | Jev fit |
|------|-------|---------|
| Chunk `semantic_type` (8-way: job_requirement, role_description, company_description, compensation, location, application_info, legal, other) | Part of the combined `chunk_matching` LLM call | **Strong** — one Choice question |
| Match score 0/1/2 (none/partial/strong) | Part of the same call | **Strong** — Score or Choice, plus calibrated confidence |
| Job content bounds (`job_bounds_detector`) | LLM returns bounds | **Plausible** — per-line keep/drop classification |
| Claim type / confidence / group type | LLM extraction | **Plausible**, lower priority |
| Gap-analysis yes/no decisions, claim dedup | LLM | **Plausible** |
| Letter generation, `advocacy_blurb`, `rationale` | LLM | **No** — generative |
| Profile / job / resume extraction, resume polish | LLM | **No** — generative |

Implication: `chunk_matching` currently returns score + rationale + blurb + semantic_type in one call. Using Jev means splitting it: cheap classification/score first, generative blurb only for chunks that need one. The eval should measure the split as well as the models.

---

## Decisions made

- **Job posting data**: do not depend on live postings. Build a **frozen fixture corpus** checked into the repo (see Day 2). Generated mock postings and snapshots of real ones are both fine; snapshots must be scrubbed of anything identifying. Public planning files must not contain real company names tied to real feedback, emails, or internal URLs.
- **Labeling**: no hand labeling for now. Labels come from (a) a Sonnet **silver** pass and (b) a stronger non-Sonnet Claude model pass. Results are always tagged with their label source. Hand labels remain an option later and would be the "gold" tier.
- **Division of labor**: Sonnet does all scaffolding/busy work (harness, adapters, dataset format, label-request files, report generation). The label files are structured so a stronger model can be prompted to fill them in with minimal extra context.
- **Models to benchmark**: Azure AI Foundry deployments, not local models. Local model only as a smoke-test adapter ("go through the motions"). Candidate list (final selection after cost review):
  - Currently deployed: `gpt-5.4`, `gpt-5.4-mini`
  - Newer GPT family (to deploy): gpt-5.6 through gpt-6.2 in terra / luna / sol / astra flavors
  - Claude on Foundry (to deploy): fable, sonnet, opus, haiku
  - Jev: `jev-1.14.0` (and `jev-1.13.0` if useful as a version comparison)
  - High-tier models are benchmark-only (never production candidates). Spend is opt-in: every run prints an estimate first and only spends when the user re-runs with an explicit `--max-spend` cap (see Day 3).
  - Harness is vetted on the cheap pair (`gpt-5.4-mini`, `jev-1.14.0`) before any premium model is run.
- **Milestone for today**: benchmarks running end to end. Production Jev integration is a separate follow-up discussion.

---

## Day 1 — Per-task model routing (no behavior change)

Prerequisite for both evals and Jev. Today every call site does `get_llm_client()` + `settings.llm_model` (single global endpoint/model).

- [ ] Define a `TaskName` enum covering every LLM call site (profile_extraction, profile_identity, job_extraction, job_bounds, chunk_matching, gap_analysis, letter_generation, github_enrichment, github_pr_extraction, resume_polish, user_input_parse, …)
- [ ] Define a model registry: named entries with `provider`/adapter type, `base_url`, model id, auth mode (API key vs Managed Identity), price per 1M input/output tokens. Format: YAML or JSON in-repo; secrets via env, never in the file.
- [ ] `resolve_model(task) -> ResolvedModel`: per-task override (env/config) → falls back to global default (`LLM_MODEL` etc.). Unknown task or entry fails loudly at startup, not mid-request.
- [ ] Refactor call sites to take a resolved config; `llm_parse_with_retry` / `llm_parse` keep their signatures where possible; metrics labels already carry `model` and `prompt_type`
- [ ] Extend `tailoring.models` (already `{"letter": model}`) to record the model that ran each task
- [ ] Keep Azure Managed Identity path in `llm_client.py` working per registry entry
- [ ] Tests: resolution order, override precedence, fallback, bad config
- [ ] Update `CLAUDE.md` / `.claude/rules/backend.md` with the routing convention

Constraint: all LLM calls still go through `llm_client.py` and `llm_parse_with_retry(..., response_model=...)`; no inline `OpenAI(...)`.

## Day 2 — Datasets

- [ ] Create `backend/evals/` (separate from `app/`, not run in CI by default)
- [ ] Fixture corpus: `backend/evals/data/postings/` — frozen markdown/text per posting with a stable id. Mix: generated mock postings (varied seniority, domain, structure, messiness) + scrubbed snapshots. Target 30–50 postings to start.
- [ ] Run existing `extract_chunks` over the corpus to produce the chunk-level dataset (chunk id, text, position, posting id)
- [ ] Candidate profile fixtures (2–3 synthetic profiles of different shapes) for match-score tasks
- [ ] Dataset schema: versioned JSONL, one record per item, with `label`, `label_source` (`silver:sonnet` | `silver:<stronger-model>` | `gold:human`), `labeled_at`
- [ ] Label request generator: emits self-contained prompt files (task definition, label options with descriptions, items) that a stronger Claude model can fill in with no repo context
- [ ] Sonnet silver labeling pass for `semantic_type` and match score
- [ ] Stronger-model labeling pass (user-prompted), imported through the same schema
- [ ] Agreement report between the two label sources (Cohen's kappa + disagreement list). Disagreements are the interesting items to review later.

## Day 3 — Eval harness

- [ ] Task registry: each task = input builder, output schema, scorer, and (for classification) label set with descriptions
- [ ] Adapter interface: `run(task, item) -> {prediction, confidence?, probabilities?, tokens_in, tokens_out, latency_ms, error?}`
  - `openai_compat` adapter (Foundry GPT/Claude, local smoke test) using the registry from Day 1, reusing `llm_parse_with_retry` so production parsing behavior is what gets measured
  - `jev` adapter: builds `choice`/`score` questions from the task's label set, posts to `/v1/systemone`, maps `answers` → common result shape; pinned model id; honors `retry-after` on 429
- [ ] Runner: task × model × N repeats, bounded concurrency, resumable (results cached per task/model/item/run so a crash or rate limit doesn't redo paid calls)
- [ ] Cost: computed from registry prices × token usage
- [ ] **Spend is opt-in.** `run` without `--max-spend` is a dry run: prints estimated cost per model/task and a ready-to-paste command containing a suggested cap. Only a run with `--max-spend <usd>` makes paid calls.
  - Input tokens counted exactly from fixtures; output tokens estimated from a small calibration sample or per-task defaults (Jev output is currently free)
  - Suggested cap = estimate × 1.5 (covers schema-retry calls that resend the prompt, and estimation error)
- [ ] **Cap enforcement**: when spend reaches the cap, stop dispatching new calls, drain in-flight calls (overshoot is bounded and reported), then act per `--on-cap`:
  - `pause` (default on a TTY): print progress (items done / total, % complete), spend so far, estimated vs actual cost so far, and a **projected total** (spend ÷ progress). Then suggest a top-up sized to the remainder: `projected_total − spend`, × 1.2 padding. E.g. at 90% complete the suggestion is a small fraction of the original cap, not a full one. Prompt: `continue` (accept the suggested top-up), a custom new cap value, or `quit`.
  - Hitting the cap means the estimate was off; print the estimate-vs-actual ratio so the 1.5× padding can be tuned
  - Projection caveat: early progress can mislead (items/models are not uniform in cost), so progress is weighted by estimated cost per item, not item count
  - `abort` (default when non-interactive, so background runs never hang): stop cleanly
  - Either way, partial results are written and the exact resume command is printed (results are cached per task/model/item/run, so no paid call is repeated)
- [ ] **Model selection**: a suites file maps each task to its model list; CLI `--models` / `--exclude` override it. Registry entries carry a `tier` (`cheap` | `premium`); premium models never run unless named explicitly (no wildcard can trigger them).
- [ ] Metrics:
  - Quality: accuracy, macro-F1, per-class precision/recall, confusion matrix — reported **separately against each label source**
  - Calibration: ECE / reliability buckets, accuracy at confidence thresholds (key for Jev; for others use logprobs or self-reported confidence where available, else mark N/A)
  - Latency: p50 / p95 / max
  - Cost: per 1k items and total
  - Reliability: schema-failure rate, retry rate, error rate
  - Consistency: agreement across N repeats of the same item
- [ ] Output: JSON results + generated Markdown comparison table (quality vs cost vs latency); results dir gitignored, summary tables optionally committed
- [ ] CLI: `uv run python -m evals run --task chunk_semantic_type --models gpt-5.4,gpt-5.4-mini,jev-1.14.0 ...` and `... report`
- [ ] Smoke test with a local model adapter end to end

## Day 4 — First benchmarks

- [ ] Collect candidate model list with prices (Foundry price sheet, Jev console); fill the registry
- [ ] **Vet harness first on the cheap pair** (`gpt-5.4-mini`, `jev-1.14.0`): dry-run estimate, capped run, deliberately low cap to exercise pause/abort/resume, compare actual vs estimated cost to tune the 1.5× padding
- [ ] Deploy chosen Foundry models; record deployment names and `tier` in the registry
- [ ] Second run adds larger/premium models: dry-run estimate → user approves the printed command with its cap
- [ ] Run: `semantic_type` classification, match score, job bounds (if time)
- [ ] Write up results vs both silver label sets; call out where label sources disagree
- [ ] Evaluate the split-call design (Jev classify + generative blurb) vs the current single call on quality and cost

## Later — Jev in production (separate discussion)

- [ ] Decide per task based on eval results; ship behind per-task routing so rollback is a config change
- [ ] Use Jev confidence for "uncertain match" handling (fallback to a stronger model below a threshold)
- [ ] Split `chunk_matching` into classify/score + conditional blurb generation
- [ ] Re-run evals on model version bumps (pinned ids, never aliases)
- [ ] Optional: hand-labeled gold set; LLM-as-judge for generative tasks (letter, blurb)

---

## Open questions

- [~] Exact Jev rate limits for our org — check developer console before the first large run
- [ ] Is `httpx` already available as a direct dependency, or only transitively via `openai`?
- [ ] Does Foundry expose logprobs for the GPT/Claude deployments (affects calibration metrics for non-Jev models)?
- [ ] Scrubbing policy for snapshot postings (company names, recruiter contacts)
- [x] Cap scope: total cap per run only. Inputs are versioned, so a user can run one model at a time for per-model budgeting. Revisit only if needed.
- [x] `continue` at the cap prompt: suggests a progress-based top-up (remaining fraction of projected total + 20% padding), not the original amount; custom value also accepted

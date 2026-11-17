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

- [x] Define a `TaskName` enum covering every LLM call site (profile_extraction, profile_identity, job_extraction, job_bounds, chunk_matching, gap_analysis, letter_generation, github_enrichment, github_pr_extraction, resume_polish, user_input_parse, …)
- [x] Define a `TaskKind`: `system_one` (classification/scoring: output is a choice among known options) vs `generative` (free text / structured extraction). Each `TaskName` declares its kind. Today every call site is `generative`; `system_one` tasks arrive as tasks are split (e.g. chunk classification).
- [x] Define a model registry as a single JSON file (`backend/llm_models.json`, no secrets): `models` (named entries: `adapter`, deployment/model id, `base_url`, `api_key_env` or managed identity, optional `pricing`), `defaults` (one model per kind: `generative`, `system_one`), and `tasks` (optional per-task overrides). No `tier` field: cost classification of models is an eval-run concern, not a property of a model.
- [x] Adapters declare which kinds they support (`openai_compat`: both, via structured output; `jev`: `system_one` only — only `openai_compat` is registered so far, the `jev` adapter lands in Day 3). Assigning a model to a task of an unsupported kind fails validation.
- [x] `resolve_llm(task) -> ResolvedLLM`: per-task override → kind default → global default derived from existing env (`LLM_MODEL`, `LLM_BASE_URL`, …). With no file present, behavior is identical to today (no infra change). Unknown task/entry/unsupported kind fails loudly at startup, not mid-request.
- [x] Clients cached per model spec (thread-safe, stateless per call, connection pooling, managed-identity token caching); cache clearable for tests
- [x] **Pricing is expected for every model that runs.** `pricing` is optional in the schema (not always known up front) but: startup validation fails in staging/production if any routed model lacks pricing (warns locally); `compute_cost_usd` logs a warning once per unpriced model instead of silently returning `None`; the existing `llm_pricing.py` table is the built-in catalog and a spec's `pricing` overrides it. Cost visibility to users is a core product feature.
- [x] Refactor call sites to take a resolved config; `llm_parse_with_retry` / `llm_parse` keep their signatures where possible; metrics labels already carry `model` and `prompt_type`
- [x] Extend `tailoring.models` (already `{"letter": model}`) to record the model that ran each task
- [x] Keep Azure Managed Identity path in `llm_client.py` working per registry entry
- [x] Tests: resolution order, override precedence, fallback, bad config
- [x] Update `CLAUDE.md` / `.claude/rules/backend.md` with the routing convention

Constraint: all LLM calls still go through `llm_client.py` and `llm_parse_with_retry(..., response_model=...)`; no inline `OpenAI(...)`.

Implementation notes (done 2026-11-17):
- `app/core/llm_tasks.py` (TaskName/TaskKind), `app/clients/llm_registry.py` (file schema, loading, validation, resolution), `app/clients/llm_client.py` (`resolve_llm`, clients cached per connection, `reset_llm_caches`), `backend/llm_models.json` (staging/production config) and `backend/llm_models.dev.json` (local dev config).
- **A registry file is required.** `ENVIRONMENT=local` loads `llm_models.dev.json`; staging/production load `llm_models.json` (only this one is copied into the image, and the `COPY` fails the build without it). `LLM_REGISTRY_PATH` overrides explicitly (tests, evals). Missing/invalid file stops startup; startup logs the active path. No env fallback: `settings.llm_model` was removed (`LLM_MODEL`/`LLM_API_VERSION` are parsed only to emit an "ignored" warning). `get_llm_client()` was removed.
- **Providers vs models.** A provider is a connection (adapter, `base_url` or `base_url_env`, `auth`, `api_key_env`); a model is an id + pricing on one provider. Endpoints and keys are referenced by env var name (process env first, then local `.env`), so one committed file works in every environment. `auth: auto` = API key if present, else Managed Identity in staging/production, else keyless local.
- Committed defaults: prod file `gpt-5.4` (production's current model, so prod behavior is unchanged); dev file `gpt-5.4-mini` plus local LM Studio models. Shared providers/models must stay identical in both files (enforced by a test); dev only adds local providers/models and its own defaults.
- **Local-only env overrides** (process env or gitignored `.env`): `LLM_DEFAULT_<KIND>=<model>` and `LLM_TASK_<TASK>=<model>`. Precedence: `LLM_TASK_*` > file `tasks` > `LLM_DEFAULT_*` > file `defaults`. Unknown names are startup errors (no silent typos); ignored with a warning when `ENVIRONMENT` is staging/production; applied overrides are logged at startup.
- `Settings` now ignores unknown `.env` keys (`extra = "ignore"`), required so `.env` can hold provider keys named by `api_key_env` (e.g. `TYPESAFE_API_KEY`) and the overrides above. Side effect: a typo in a declared setting's name in `.env` is no longer rejected.
- Tests run against `tests/llm_models.test.json` (set in `tests/conftest.py`), never the developer's file.
- `tailoring.models` is now `{letter, job_extraction, job_bounds, chunk_matching}` (JSONB, no migration). Debug-log field `llm_model` became `llm_models`.
- `tests/eval/eval_runner.py` and `scripts/test_foundry.py` now resolve the `chunk_matching` model through the registry.
- Pre-existing: `make check-backend` fails under `/bin/sh` (`PIPESTATUS` in the bandit recipe); runs with `make SHELL=/bin/bash check-backend`.
- `pricing` accepts an optional `per_tokens` (default 1,000,000) so a provider's price sheet can be copied verbatim (e.g. per-1K); rates are normalized to per-1M at load. Not yet modeled: cache-write rates (add with Claude on Foundry), tiered long-context pricing.
- Follow-up (infra, not done): Terraform still sets `LLM_MODEL` / `LLM_API_VERSION`; they are now inert and can be removed from `infra/providers/azure/main.tf` and `variables.tf`. Production reads `LLM_BASE_URL` (already set) and uses Managed Identity (no `LLM_API_KEY`).

Design choices made for later extension (not implemented yet):
- **Other clouds** (AWS Bedrock, Google Vertex): a new provider entry with a new `adapter` and `auth` value (e.g. `aws_iam`, `gcp_adc`); model entries are unchanged. Adapters declare the task kinds they can serve.
- **Bring-your-own LLM:** `Registry` is built from a plain structure and `resolve_llm(task, registry=...)` accepts any registry, so a per-user registry (stored in the DB, credentials encrypted like `UserIntegration`) can be layered over the global one. Clients are cached by connection (endpoint + auth + key), not model name, so per-user connections cannot collide. Needs before shipping: SSRF protection for user-supplied `base_url`s, spend/rate limits, and cost reporting for unpriced user models.

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
- [ ] **Model selection**: a suites file maps each task to an explicit model list (no wildcards); CLI `--models` / `--exclude` override it. Which models count as "cheap" for the harness-vetting phase is just the suite contents, not model metadata.
- [ ] **Unpriced models**: the dry run flags any model lacking pricing, shows its cost as unknown (excluded from totals), and warns that the spend cap cannot cover it. Running it requires an explicit `--allow-unpriced` opt-in.
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
- [ ] Deploy chosen Foundry models; record deployment names and pricing in the registry
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

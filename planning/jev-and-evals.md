# Jev + LLM Evals + Per-Task Model Routing

Status: phase complete 2026-11-20 (started 2026-11-17); open work in "Carry forward" at the end

Three linked goals:

1. Integrate **Jev** (TypeSafe AI's System One model) where its capabilities fit.
2. Build a **model-agnostic eval pipeline** to compare any number of LLMs on Tailord's tasks (quality, cost, latency, reliability).
3. Support **mixed models per task** with a global default and per-task overrides.

Order of work matters: routing → eval harness → Jev adapter in the harness → (later, separate discussion) Jev in production, gated on eval results.

---

## Status (2026-11-20): this phase is complete; open work is in "Carry forward"

| Goal | Outcome |
|---|---|
| 1. Integrate Jev where its capabilities fit | **Groundwork done, production routing deferred by design.** `typesafe` provider and `jev-1.14.0` in the registry, one shared client (`app/clients/jev_client.py`) used by the app and the harness, the `system_one` task kind and the `jev` adapter rules. The evals say Jev belongs: about 10x cheaper and faster than `gpt-5.4-mini` on chunk classification with no significant accuracy difference, calibrated confidence, and it flags section labels that slip through as paragraphs. Routing a task to it is the separate design discussion (Carry forward, P2). |
| 2. Model-agnostic eval pipeline | **Done for classification tasks.** `backend/evals/` (see its README): runner with an opt-in spend cap, resumable per-item results, rate-limit handling, metrics, comparison report, label tooling, a frozen 30-posting corpus and a real-postings probe. First benchmark: `semantic_type`, 478 items, in `planning/results/`. |
| 3. Mixed models per task | **Done (Day 1).** Required registry files, per-task overrides, per-kind defaults, local `.env` overrides, a per-user registry seam. |

By-products: the harness exposed two production bugs, both fixed (Greenhouse job content reached the chunker as literal HTML; markdown headings deeper than `###` leaked through as paragraphs). The premium comparison (`gpt-5.4`) is done and changes nothing: it is no better than `gpt-5.4-mini` on classification.

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
  - Jev: `jev-1.14.0` (`jev-1.13.0` dropped: same price, no reason to use it)
  - High-tier models are benchmark-only (never production candidates). Spend is opt-in: every run prints an estimate first and only spends when the user re-runs with an explicit `--max-spend` cap (see Day 3).
  - Harness is vetted on the cheap pair (`gpt-5.4-mini`, `jev-1.14.0`) before any premium model is run.
- **Milestone for today**: benchmarks running end to end. Production Jev integration is a separate follow-up discussion. **Met for `semantic_type` on the cheap pair** (full 478-item run, see Day 4 and the takeaways at the end); the remaining tasks and models are tracked in Day 4.

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

Principles:
- **Each task is benchmarked in isolation on frozen input artifacts.** The harness never chains tasks with one model. Every artifact records provenance: producing task, model (or code git sha), upstream artifact content hash, parameters.
- **Workflow:** benchmark a task, choose a standard model, `promote` its output as the next task's input, benchmark the next task. Any task that uses an LLM is benchmarkable; the artifact framework is generic and Day 2 builds the job-side chain first.
- **Provisional upstream artifacts** (agreed): until a standard is chosen, each upstream artifact is derived from agreed silver labels (the stronger model's label wins on disagreement) and marked `provisional`. `promote` replaces it later with provenance; nothing downstream is restructured.
- **Items are keyed by (chunk id, profile id)** so more profiles can be added later without changing layout. One profile for now: reuse `alex-chen-backend-engineer` (schema in `tests/eval/profile_schema.py`).

Chain:

```
HTML posting -> markdown (code) -> [job_bounds] -> chunks (code) -> [semantic_type]
profile claims -> embeddings -> retrieval (frozen once, k=8) -> [match_score]
```

- `job_bounds`: label = start/end line of the core job content (more robust than anchor strings). Scored by line overlap and boundary exactness; the production fallback (null anchors, use everything) counts as its own outcome. A System One per-line keep/drop reformulation may be added so Jev can compete.
- `semantic_type`: the 8-way chunk classification.
- `match_score`: -1/0/1/2 scoring using the production retrieval path. The retrieval artifact stores the production prompt inputs verbatim (candidate header, requirement, grouped context) plus embedding model, k and profile id, so every model sees byte-identical input. Retrieval is computed once (embedding cost estimate shown and approved first) using in-memory cosine like `tests/eval`.

Postings (persisted HTML repository, `backend/evals/data/`):
- Board templates captured from live Greenhouse / Lever / Ashby / Workday / company career pages (DOM skeleton and chrome: nav, cookie banners, EEO footer, apply buttons, JSON-LD) into `templates/`.
- Posting content is hand-written by Claude (not script-generated), modeled on the style of well-known postings, under **tongue-in-cheek mock company names** (e.g. "Googleo", "Notiono", "Microsofto") so size tier is obvious and nothing is misattributed. Big tech, mid-size, and startup tiers.
- Corpus 30 postings (phase A: 12 across all boards and sizes, then phase B: 18), about 1,000 chunks and about 400 scored pairs. Boards: Greenhouse 8, Lever 6, Ashby 6, Workday 3, company sites 4, aggregator-style 3. About 24 engineering-adjacent roles, 6 non-engineering. `manifest.jsonl` records board, company tier, role family, seniority.

Labeling: three rounds in order (job_bounds, semantic_type, match_score). Each has a Sonnet silver pass and a stronger non-Sonnet Claude pass; sources are free-form strings (`silver:sonnet-5-5`, `silver:<model>`, `gold:human`). Label-request files contain no predictions (avoid anchoring). Agreement via Cohen's kappa plus a disagreement list. After each round the next stage's inputs are rebuilt from the agreed labels.

Steps:
- [x] 1. Scaffold `backend/evals/` (separate from `app/` and from `tests/eval`, not run in CI): artifact + provenance schemas, item ids, label files, label definitions in `tasks/*.py`
- [x] 2. Captured board templates from live pages (7 templates in `backend/evals/data/templates/`, scrubbed, with slots; see its README)
- [x] 3a. Wrote phase A postings (12): sources in `backend/evals/data/postings/src/*.md`, rendered to board-style HTML by `python -m evals.render_postings` (`html/`, `manifest.jsonl`); about 400 chunks
- [x] 3b. Wrote phase B postings (18): 30 postings total, 916 chunks; deliberately messy cases included (single unbroken paragraph, all-caps headings, very short posting, heavy legal boilerplate, aggregator chrome)
- [x] 4. Code stages (`backend/evals/stages.py`): HTML to markdown via the production extractor; line-range bounds application and chunking via production `extract_chunks`; artifacts in `data/artifacts/` with git-sha provenance. Chunks are provisional (no bounds applied yet = production fallback, 916 core chunks); rebuilt with agreed bounds after label round 1. Bounds lines are 1-indexed inclusive. Regenerate artifacts after committing so the recorded sha is clean (it shows `+dirty` otherwise)
- [x] 5. Frozen retrieval artifact for match_score (`backend/evals/retrieval.py`): 619 items (provisional until bounds), production two-pass retrieval (top-8 substantive + top-6 skills), production prompt template; embedded once with text-embedding-3-small for $0.00034 (estimate matched actual). Vectors cached in gitignored `data/cache/`; retrieval.jsonl is 3.7MB (full prompts), regenerate after label round 1
- [x] 6. Label rounds 1 to 3 (tooling in `backend/evals/labeling.py`: request files, validated import, kappa/IoU agreement, agreed labels, chunk rebuild). Silver sources: `silver:sonnet-5-5` and `silver:opus-5-5` (Opus primary on disagreement). Round 1 job_bounds (30): exact 93%, mean IoU 0.975, line kappa 0.992. Round 2 semantic_type (478): exact 99.0%, kappa 0.985. Round 3 match_score (478): exact 83.7%, kappa 0.781 (quadratic-weighted 0.874 on the 335 both-scorable items); 78 disagreements, 49 are adjacent levels (0/1/2) and 27 are scorable-vs-not, mostly Sonnet marking role-intro paragraphs -1 where Opus scored them. Opus is itself inconsistent on domain-specific year thresholds (lever-01:15 and gh-07:14 scored by total YOE, site-01:16 not), so some match_score label noise is expected; report quality against each source and the agreed set separately. Sonnet's match_score pass used a compact requirement view, not the per-item contexts
- [x] 7. Unit tests written alongside each step (store, templates, postings, stages, retrieval, labeling; 83 tests, no live LLM calls)

## Day 3 — Eval harness


Scaffolding done (before the harness): `typesafe` provider (`adapter: jev`, `base_url: https://api.typesafe.ai`, key from `TYPESAFE_API_KEY`) and model `jev-1.14.0` (pinned version, no `latest`; `jev-1.13.0` is priced the same, so there is no reason to benchmark it) in both registry files. `jev` serves only `system_one` tasks, so routing a generative task to it fails validation; `resolve_llm` dispatches by adapter to one shared client per provider connection: `openai_compat` gives an OpenAI client, `jev` gives `app/clients/jev_client.py`'s `JevClient` (used by both the app and the eval harness; client logic is never duplicated in `evals/`). `resolve_model(name)` resolves a registry model outside any task, for benchmarks. Staging/production do not require the key until a task is routed to a Jev model. Pricing `input: 0.042` per 1M tokens, `output: 0.0` (verified in the TypeSafe console).

- [~] Task registry: `evals/tasks/` has `ClassificationTask` (labels with descriptions, instructions, state renderer) and the `semantic_type` task with items loaded from the frozen chunks plus every label source. `match_score` (ordinal) and `job_bounds` (span) task types still to add; scorer/metrics come with the runner
- [x] Adapter interface (`evals/adapters/base.py`: `Adapter` protocol, `CallResult`): `run(task, item) -> {prediction, confidence?, probabilities?, tokens_in, tokens_out, latency_ms, error?}`
  - `openai_compat` adapter (Foundry GPT/Claude, local smoke test) using the registry from Day 1, reusing `llm_parse_with_retry` so production parsing behavior is what gets measured
    - DONE (`evals/adapters/openai_compat.py`; live-tested on `gpt-5.4-mini`: a 3-item smoke test, then the full run): resolves the model via `resolve_model`, builds a standalone classification prompt from the task's labels, and calls the production `llm_parse_with_retry` with a closed `Literal` response model, so structured-output mode and self-correcting retries match production. To get tokens, retry counts and latency from that path, `llm_parse` / `llm_parse_with_retry` gained an optional, backward-compatible `stats_sink` (one `LLMCallStats` per call, including calls whose output failed validation since they are billed). Known gap: the OpenAI SDK's own transport retries are invisible to the harness. `CallResult.latency_ms` is wall clock per item for both adapters, retries and backoff included
  - `jev` adapter: DONE for `choice` (`evals/adapters/jev.py`). All transport logic is the shared `app/clients/jev_client.py` (auth, retries with exponential backoff on 429/529/5xx/timeouts, `Retry-After` honoured if present since the docs do not mention it, typed errors, response validation); the adapter only maps task items to questions and answers to the common `CallResult`. Live-tested on `jev-1.14.0`: a 3-item smoke test, then the full run (about 520 calls, no 429s seen at concurrency 8)
- [x] Runner: task × model × N repeats, bounded concurrency, resumable (results cached per task/model/item/run so a crash or rate limit doesn't redo paid calls) — `evals/runner.py` + `python -m evals run`; results append to gitignored `evals/results/<task>/<model>.jsonl`, each record carrying an `input_hash` of the task definition plus that item's input (and the adapters' `PROMPT_VERSION`), so partial runs and added items reuse every still-valid result and a changed input or prompt re-runs only what it touches; transient errors (rate limit, connection) are not model answers: the runner halves concurrency, backs off exponentially and requeues them up to 3 times, anything still failing is reported as unresolved (exit code 4) and retried by re-running, and the report excludes them from every score and flags the run INCOMPLETE, while model errors (invalid label, schema failure) are kept as outcomes and count as wrong; items are interleaved across models so a stopped run has comparable coverage
- [x] Cost: computed from registry prices × token usage — per call from registry/catalog pricing; failed calls count what they cost
- [x] **Spend is opt-in.** `run` without `--max-spend` is a dry run: prints estimated cost per model/task and a ready-to-paste command containing a suggested cap. Only a run with `--max-spend <usd>` makes paid calls. — dry run prints per-model estimate (local tiktoken count + calibrated per-adapter overhead, recalibrated from observed calls once 20 exist) and a paste-ready command with cap = estimate x 1.5
  - Input tokens counted exactly from fixtures; output tokens estimated from a small calibration sample or per-task defaults (Jev output is currently free)
  - Suggested cap = estimate × 1.5 (covers schema-retry calls that resend the prompt, and estimation error)
- [x] **Cap enforcement**: when spend reaches the cap, stop dispatching new calls, drain in-flight calls (overshoot is bounded and reported), then act per `--on-cap`: — stops dispatching at the cap, drains in-flight (overshoot bounded by concurrency), then `--on-cap pause` (interactive: progress weighted by estimated cost, estimate-vs-actual ratio, projected total, suggested top-up x1.2; `continue`, a new cap, or `quit`) or `abort` (default without a TTY; prints the resume command)
  - `pause` (default on a TTY): print progress (items done / total, % complete), spend so far, estimated vs actual cost so far, and a **projected total** (spend ÷ progress). Then suggest a top-up sized to the remainder: `projected_total − spend`, × 1.2 padding. E.g. at 90% complete the suggestion is a small fraction of the original cap, not a full one. Prompt: `continue` (accept the suggested top-up), a custom new cap value, or `quit`.
  - Hitting the cap means the estimate was off; print the estimate-vs-actual ratio so the 1.5× padding can be tuned
  - Projection caveat: early progress can mislead (items/models are not uniform in cost), so progress is weighted by estimated cost per item, not item count
  - `abort` (default when non-interactive, so background runs never hang): stop cleanly
  - Either way, partial results are written and the exact resume command is printed (results are cached per task/model/item/run, so no paid call is repeated)
- [x] **Model selection**: a suites file maps each task to an explicit model list (no wildcards); CLI `--models` / `--exclude` override it. Which models count as "cheap" for the harness-vetting phase is just the suite contents, not model metadata. — `evals/suites.json` (suite `vet` = gpt-5.4-mini + jev-1.14.0 on semantic_type), `--task/--models/--exclude/--limit` overrides
- [x] **Unpriced models**: the dry run flags any model lacking pricing, shows its cost as unknown (excluded from totals), and warns that the spend cap cannot cover it. Running it requires an explicit `--allow-unpriced` opt-in. — flagged in the dry run, refused without `--allow-unpriced`
- [x] Metrics:  (`evals/metrics.py`, classification tasks; ordinal `match_score` and span `job_bounds` metrics come with those tasks). Also: 95% Wilson intervals on accuracy, accuracy on items all label sources agree on vs contested, exact McNemar between model pairs on the agreed labels. Calibration uses the top-class probability; N/A for models without probabilities
  - Quality: accuracy, macro-F1, per-class precision/recall, confusion matrix — reported **separately against each label source**
  - Calibration: ECE / reliability buckets, accuracy at confidence thresholds (key for Jev; for others use logprobs or self-reported confidence where available, else mark N/A)
  - Latency: p50 / p95 / max
  - Cost: per 1k items and total
  - Reliability: schema-failure rate, retry rate, error rate
  - Consistency: agreement across N repeats of the same item
- [x] Output: JSON results + generated Markdown comparison table (quality vs cost vs latency); results dir gitignored, summary tables optionally committed — `python -m evals report --task T` writes `report.json` and `report.md` into the results directory and prints the markdown; `--out` copies it (e.g. under planning/). Quality, calibration and significance use each item's first run only (repeats feed consistency and a per-run accuracy line, and never inflate n); by default the report scopes to items that have a result, `--all-items` shows true coverage. Vetted on a 40-item slice of the cheap pair (estimate $0.0099, actual $0.0099)
- [x] CLI: `uv run python -m evals run --task semantic_type --models gpt-5.4-mini,jev-1.14.0 ...` and `... report` — `run` and `report` subcommands (`evals/__main__.py`)
- [~] Smoke test with a local model adapter end to end: deferred. Live smoke tests ran against `gpt-5.4-mini` and `jev-1.14.0` instead, and the runner and adapters are exercised offline with fakes (see `tests/unit/test_evals_*.py`). Run one against an LM Studio model only if wanted

## Day 4 — First benchmarks

Done for `semantic_type` on three models (cheap pair plus `gpt-5.4`); everything else is under "Carry forward".

- [x] Candidate prices: `gpt-5.4`, `gpt-5.4-mini` and `jev-1.14.0` are registered and priced (Jev pricing verified in the TypeSafe console). More models: Carry forward
- [x] **Vet harness first on the cheap pair** (`gpt-5.4-mini`, `jev-1.14.0`): dry-run estimate, capped run, deliberately low cap to exercise pause/abort/resume, compare actual vs estimated cost to tune the 1.5× padding. Done on a 40-item slice (abort at a low cap, resume, interactive pause with a custom cap and `continue`, repeats); estimates matched actual spend to the cent (1.00x), so the 1.5x padding stays as a safety margin. Vetting found and fixed: cap overshoot from concurrent calls (now reserves in-flight cost), whole-set fingerprint keys (now per-item hashes), repeats inflating confidence intervals (first run only), and a wrong resume command. The full run then found Azure rate limiting at concurrency 8 (164 failed calls), now handled by backoff, requeue and an INCOMPLETE report banner
- [x] Second run adds a larger model: `gpt-5.4` on all 478 items for $0.3553 (estimate $0.3556), no errors; no better than `gpt-5.4-mini`, not significantly different from either model. Full report: `planning/results/semantic_type.md`
- [~] Run `semantic_type`, match score, job bounds: `semantic_type` done on the cheap pair (`gpt-5.4-mini` 98.5% vs `jev-1.14.0` 96.9% on the agreed labels, 96.9% vs 98.1% on the adjudicated; no significant difference; Jev about 10x cheaper and faster). `match_score` and `job_bounds` need new task types: Carry forward
- [x] Write up results vs both silver label sets; call out where label sources disagree. Done: `planning/results/semantic_type.md` (generated report plus a header on how to read it). Earlier note: The report scores every label source separately and splits unanimous from contested items, but only 5 of 478 items are contested for `semantic_type`, so the sources barely differ there. The real finding is label error (8 heading-like chunks, see the TODOs). A committed summary table is pending the label adjudication
- [~] Evaluate the split-call design (Jev classify + generative blurb) against the current single call: Carry forward

---

## Open questions

- [x] `httpx` is a direct dependency (`httpx>=0.28.0` in pyproject); `JevClient` uses it
- [x] Cap scope: total cap per run only. Inputs are versioned, so a user can run one model at a time for per-model budgeting. Revisit only if needed.
- [x] `continue` at the cap prompt: suggests a progress-based top-up (remaining fraction of projected total + 20% padding), not the original amount; custom value also accepted
- [x] Jev price: $0.042 per 1M input tokens, $0 output, verified in the TypeSafe console (2026-11-20)
- [~] Jev rate limits for our org: no 429s in about 1,500 Jev calls at concurrency 8, so the limit is above that; not probed higher
- [~] Foundry logprobs, and the scrubbing policy for real-posting snapshots: Carry forward

---

## Takeaways

Captured after the first full `semantic_type` benchmark on the cheap pair (478 items, frozen inputs; "agreed" = Opus's label where the two silver labelers disagree).

### Where we landed

| | gpt-5.4 | gpt-5.4-mini | jev-1.14.0 |
|---|---|---|---|
| Accuracy vs agreed labels | 98.3% (96.7-99.1) | 98.5% (97.0-99.3) | 96.9% (94.9-98.1) |
| Accuracy vs adjudicated labels (8 heading-like chunks corrected to `other`) | 97.5% (95.7-98.6) | 96.9% (94.9-98.1) | 98.1% (96.5-99.0) |
| Macro-F1 (adjudicated) | 0.859 | 0.822 | 0.945 |
| Section labels and banners found (of 10 `other`) | 4 | 0 | 8 |
| Significance (exact McNemar, all pairs) | none significant on either label set (smallest p = 0.077) | | |
| Median latency | 928 ms | 778 ms | 80 ms |
| Cost per 1k items | about $0.74 | about $0.22 | about $0.023 |
| Calibration | none reported | none reported | ECE 0.021; every error has confidence < 0.7; >= 0.7 answers 96% of items at 100% accuracy |

- **Jev has a place in Tailord.** About 10x cheaper and faster than `gpt-5.4-mini` (30x cheaper than `gpt-5.4`) on classification, with accuracy statistically indistinguishable and confidence we can route on. The premium model buys nothing detectable here: `gpt-5.4` is no better than `gpt-5.4-mini` on either label set. The ranking shifts with a handful of label decisions, so do not claim an accuracy winner from n = 478.
- **Confidence is usable but a bigger fallback model is not a free win.** All 9 of Jev's errors are below 0.7 confidence, so answers at >= 0.7 are 100% accurate on 95.8% of items. Escalating the low-confidence rest to `gpt-5.4` gives 98.1%, the same as Jev alone (it fixes 6 of Jev's 9 errors and breaks as many correct low-confidence answers), at 14x lower cost than `gpt-5.4` everywhere. Hard items here are label-boundary cases, so confidence is better used to flag or review than to escalate. In-sample threshold; re-check on a larger set.
- **Jev caught section headers that slipped through as paragraphs.** Lines such as "Required Qualifications:", "Minimum Qualifications:", "Your responsibilities" and "We're looking for someone who has:" are chunked as `paragraph` (only `##` headings become skipped `header` chunks) and reach the scoring LLM in production. Jev called all but one of these `other`; both silver labelers, and `gpt-5.4-mini` on the two it answered, labeled them by the section they introduce. This looks like an existing bug with postings in the wild, and Jev could be the fix.
- **The harness paid for itself.** It surfaced the label problem above, a rate-limit failure mode (Azure throttled `gpt-5.4-mini` at concurrency 8, 164 failed calls, now handled by backoff, requeue and an INCOMPLETE report banner), overshoot of the spend cap, and inflated confidence intervals from repeats. Estimates matched actual spend to the cent.

### Real-postings probe (2026-11-20)

24 real postings (12 Greenhouse, 12 Lever) fetched through the production ATS paths into a gitignored local folder (`backend/evals/data/local/`, never committed), chunked with the production chunker, then run through Jev. Probe code: `backend/evals/probes/section_labels.py`; tasks `real_section_label` (section label vs content) and `real_semantic_type`.

- As the app behaves today (Greenhouse content escaped): 895 chunks, 802 reach an LLM. Jev flagged 89 (11%) as section labels at P >= 0.5, in 17 of 24 postings; 81 of the 89 are HTML-wrapped headings from the Greenhouse bug above, 8 are plain text on Lever (e.g. "Core Responsibilities", "SWE principles include:", a bold-only bullet). Probe cost $0.036 for 1,604 calls.
- With the Greenhouse content unescaped (the fix, now in `ats_client.py`): 932 chunks, 772 reach an LLM, with 160 header chunks instead of 93. Jev flagged **22 chunks (2.8%) as section labels at P >= 0.5, in 11 of 24 postings** (14 chunks, 1.8%, in 7 postings at P >= 0.9; 6 at >= 0.99). Probe cost $0.021 for 952 calls ($0.056 for the whole probe).
- My single-reviewer read of the 22 flags (a rough estimate, not a gold label): about 15 are true section labels or lead-ins ("Core Responsibilities", "SWE principles include:", "Examples of accommodations include but are not limited to:", "The base salary range for this position is:", a bold-only bullet), 2 are ambiguous ("More about X: <url>"), and 5 are false positives, all short Title Case benefit bullets ("Mental Health & Coaching Benefits", "Paid vacations and holidays"). At P >= 0.9 about 12 of 14 are correct. Misses seen: bold-only bullets such as `**AI**` / `**Robotics**` (P about 0.16) and a tagline heading that scored 0.35-0.54 depending on context. Rough recall on the label-like lines I could find is about 70-75%.
- Both defects found here are fixed: Greenhouse content is now unescaped (`ats_client.py`), and `#{1,6}` headings are recognized (`chunk_extractor.py`; the real sample goes from 160 to 166 headers and 772 to 766 chunks reaching an LLM; the frozen eval corpus is unchanged).
- **Roughly 4 in 10 postings still send at least one section label to the scoring LLM as an ordinary paragraph after the escaping fix**, but it is about 2% of chunks, so the escaping bug (98% of Greenhouse chunks) was the much bigger problem. Six of the 22 flags are markdown `####` headings: the chunker's header pattern is `^#{1,3}\s+`, so level-4 and deeper headings become paragraph chunks (checked directly). A one-line regex change fixes those without a model; the remaining plain-text labels (about 10) are where a classifier adds value.

---

## Carry forward (prioritized)

Everything still open from this plan lives here.

### P0: production correctness found along the way

- [x] Greenhouse job content was reaching the chunker and the LLM as literal HTML (the API returns it entity-escaped; `ats_client._greenhouse_to_markdown` now unescapes it, with tests). Expect Greenhouse tailorings to chunk and score differently after this
- [x] Markdown headings deeper than `###` leaked through as paragraph chunks (`chunk_extractor._HEADER_RE` is now `#{1,6}`, with tests)

### P1: finish the evidence

- [x] **Run `gpt-5.4` on `semantic_type`** (done 2026-11-20; see Takeaways and `planning/results/semantic_type.md`)
- [ ] **Benchmark `match_score` and `job_bounds`.** The harness has only classification tasks. `match_score` is ordinal (Jev `score` question vs a 4-way `choice`); `job_bounds` is a span (Jev per-line keep/drop). This is where the generative models should earn their cost
- [ ] **Review the classification scheme end to end.** The label set has no section-header class and `other` is a catch-all. Decide between keeping `other`, an explicit rule for section labels, lead-ins and banners, or a `section_header` class; then run the clarified wording as its own experiment (a task-text change invalidates results and costs about $0.13 on the cheap pair)
- [ ] **Review remaining label disagreements:** the 12 items only `gpt-5.4-mini` got right, the 4 only Jev got right, the 3 both missed (`site-03:22`, `wd-01:5`, `wwr-02:4`), role vs company for team descriptions, and the "AI Auto-Apply / Save job" chrome lines (`other` vs `application_info`)
- [ ] **Audit `match_score` agreed labels** for non-requirement chunks (consider making `semantic_type` imply -1 for `other`, `legal`, `compensation`, `location`, `application_info`)
- [ ] **Real postings with gold labels.** The 30-posting corpus was written by Claude and labeled by the same model family. Label a scrubbed real sample so precision and recall of the section-label detector are measured, not eyeballed, and decide the scrubbing policy (company names, recruiter contacts) before any snapshot is committed
- [ ] **More models:** larger Foundry GPT and Claude deployments (registry entries, prices, cache-write pricing for Claude); check whether Foundry exposes logprobs, for a calibration comparison with non-Jev models

### P2: production integration (the separate design discussion)

- [ ] **Header-in-paragraph detection with Jev.** After both fixes, about 2% of chunks and about 4 in 10 postings still send a section label to the scoring LLM as a paragraph; Jev's section-label question was roughly 85-90% precise at P >= 0.9 on a small single-reviewer read and missed bold-only bullets. Pick a threshold and a fallback for uncertain chunks; beware false positives on short Title Case benefit bullets (a rule such as "paragraph chunk, no sentence punctuation, P >= 0.9" is the likely start)
- [ ] **Classify before scoring.** A `system_one` task for chunk semantic type routed through the registry (`defaults.system_one`), skipping generative scoring for chunks that are not requirements or responsibilities (106 of 478, 22%, in the mock corpus: a hypothesis to quantify on real postings)
- [ ] **Confidence routing:** on this data, confidence >= 0.7 is 100% accurate on 96% of items, but escalating the rest to `gpt-5.4` did not beat Jev alone (98.1% both), so decide what low-confidence chunks should do (keep, flag, skip scoring, or review) rather than assuming a stronger model fixes them; choose the threshold on a larger, real-posting calibration set
- [ ] **Split `chunk_matching`** into classify/score plus conditional blurb generation, and compare it with the single call on quality, cost and latency
- [ ] **Production client work:** a registry `system_one` default, alerting on `TYPESAFE_API_KEY`, rollback as a config change, and re-running the evals on model version bumps (pinned ids, never aliases)

### P3: housekeeping

- [ ] Remove the inert `LLM_MODEL` / `LLM_API_VERSION` from Terraform (Day 1 follow-up)
- [ ] Per-model concurrency overrides in `suites.json` if Foundry throttling keeps recurring
- [ ] Decide whether to keep our `JevClient` (httpx) or adopt TypeSafe's official Python SDK, which has its own retries
- [ ] Probe Jev rate limits above concurrency 8 before a much larger run
- [ ] Optional: a hand-labeled gold set; LLM-as-judge for generative tasks (letter, blurb)

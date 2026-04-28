# Eval Ops Guide

Operational reference for the chunk-matching eval system: CI gate, live shadow run,
fixture management, and guidance for common scenarios.

---

## What this system protects

The chunk-matching step scores each job requirement against a candidate's experience
(STRONG / PARTIAL / GAP / N/A). It is the highest-leverage LLM call in the pipeline —
errors here flow directly into the tailoring output and the gap question list.

The eval system answers: **does the matching pipeline still behave correctly after a code
change?** It does this without re-running a live LLM on every PR.

---

## Architecture: two tracks

```
Track 1 — CI gate (blocking)
  ┌────────────────────────────────────────────────────────────┐
  │  On every PR: compare cache/scores.json against            │
  │  fixture expected_scores. No API calls. Exits 1 if         │
  │  vector agreement < 70%. Gate is on production mode only.  │
  └────────────────────────────────────────────────────────────┘

Track 2 — Live shadow run (non-blocking)
  ┌────────────────────────────────────────────────────────────┐
  │  Weekly (Mondays 9am UTC) + manual trigger:                │
  │  run both modes against real Foundry API. Upload           │
  │  RESULTS.md as 90-day artifact. Never blocks deploys.      │
  └────────────────────────────────────────────────────────────┘
```

**Why not live API calls in the gate?**
The gate tests *code logic* — retrieval, prompt construction, response parsing — not model
behaviour. Embeddings and LLM responses are non-deterministic (and costly). Cached scores
let the gate run in under 5 seconds with zero API cost.

**Why not LLM-as-a-Judge?**
Our output is a structured enum: STRONG, PARTIAL, GAP, N/A. Agreement rate against labeled
fixtures is the correct metric. A teacher model evaluating prose quality adds cost and a new
non-determinism source for a task that doesn't need it.

---

## Quick reference

```bash
make eval-offline   # CI gate locally: check cache against expected (no API calls)
make eval-record    # Live run + write new scores to cache (update the gate baseline)
make eval-live      # Live run only, no cache write (spot-check without committing)
```

Full options:

```bash
# From backend/
uv run python tests/eval/eval_runner.py --offline --mode vector --threshold 0.70
uv run python tests/eval/eval_runner.py --offline --mode both   --threshold 0.70
uv run python tests/eval/eval_runner.py --record  --mode both
uv run python tests/eval/eval_runner.py --mode vector           # live, no cache write
```

`--mode` accepts `both` (default), `vector`, or `llm`.
`--threshold` is only used in `--offline` mode. Default 0.70.

---

## File structure

```
tests/eval/
├── OPS.md                          — this file
├── README.md                       — brief intro (now outdated; OPS.md supersedes)
├── eval_runner.py                  — runner: offline gate + live + record modes
├── RESULTS.md                      — output of the last full both-mode live run
├── profile_schema.py               — EvalCandidateProfile Pydantic model
├── profiles/
│   └── alex-chen-backend-engineer.json
├── fixtures/
│   ├── 01-strong-yoe-match.json
│   ├── 02-partial-skill-match.json
│   ├── 03-clear-gap.json
│   ├── 04-non-evaluable.json
│   └── 05-multi-source.json
└── cache/
    └── scores.json                 — committed baseline; updated by --record
```

### cache/scores.json

The committed gate baseline. Format:

```json
{
  "version": 1,
  "recorded_at": "YYYY-MM-DD",
  "llm_model": "gpt-5.4-mini",
  "embedding_model": "text-embedding-3-small",
  "k": 8,
  "scores": {
    "<fixture-id>": {
      "llm": [2, 2, 2],
      "vector": [2, 2, 2]
    }
  }
}
```

The `scores` dict maps fixture IDs to recorded score lists. The gate compares these against
`expected_scores` in each fixture JSON and computes an agreement rate. A cache miss for any
fixture causes an immediate exit 1.

---

## CI jobs

### `eval-offline` (ci.yml)

- Triggered on every PR and push to `main`
- Needs the `backend` job to pass first
- No services, no API keys — just Python + committed files
- Runs `--offline --mode vector --threshold 0.70`
- Exits 1 if vector agreement < 70% or any fixture has a cache miss

### `eval-live` (eval-live.yml)

- Runs on schedule: Mondays at 09:00 UTC
- Also triggerable manually via GitHub Actions → `workflow_dispatch`
- Reads secrets: `EVAL_LLM_BASE_URL`, `EVAL_LLM_API_KEY`, `EVAL_LLM_MODEL`,
  `EVAL_EMBEDDING_BASE_URL`, `EVAL_EMBEDDING_API_KEY`
- Uploads `RESULTS.md` as artifact `eval-results-{run_id}`, 90-day retention
- Does NOT block any deployment

To trigger manually: GitHub Actions → "Eval (live shadow)" → "Run workflow"

---

## Current baseline (2026-04-28, gpt-5.4-mini, text-embedding-3-small, K=8)

| Fixture | Expected | LLM | Vector | Notes |
|---------|----------|-----|--------|-------|
| 01-strong-yoe-match | STRONG×3 | ✓ | ✓ | |
| 02-partial-skill-match | PARTIAL×2 | ✗ GAP×2 | ✗ GAP×2 | See calibration note below |
| 03-clear-gap | GAP×2 | ✓ | ✓ | |
| 04-non-evaluable | N/A×4 | ✓ | ✗ chunk 1→GAP | See edge case below |
| 05-multi-source | STRONG×2 | ✓ | ✓ | |

**LLM mode: 11/13 (85%) · Vector mode: 10/13 (77%)**

### Calibration note — fixture 02
Both modes score Kubernetes/Terraform as GAP, not PARTIAL. The system prompt rule —
"do not infer the presence of a specific tool from experience with a related tool" — is
being applied correctly: Docker ≠ Kubernetes; the profile has no Terraform mentions.
The PARTIAL expectation assumes a human evaluator would credit adjacent infrastructure
experience. **This is a fixture label issue, not a model regression.** Expected scores for
fixture 02 may need updating to `[0, 0]` once the model behaviour is confirmed stable.

### Edge case — fixture 04, vector mode, chunk 1
The work-authorization paragraph ("Must be authorized to work in the United States…")
is correctly scored N/A in LLM mode (full profile context signals boilerplate) but GAP
in vector mode (top-8 experience chunks include US job locations, giving the LLM just
enough context to treat it as an addressable requirement).

**Production impact is low**: the gap analyzer filters by `should_render=True`, and legal
boilerplate should already be filtered there. However, the SYSTEM prompt in
`backend/app/prompts/chunk_matching.py` does not explicitly list work-authorization
statements as `should_render=false` — this is a latent risk worth addressing.

---

## Pipeline hash — automatic staleness detection

The gate automatically detects when the cache needs updating. At record time, a
`pipeline_hash` is computed and stored in `scores.json`. At gate time, the hash is
recomputed and compared. A mismatch causes an immediate exit 1:

```
✗ Pipeline inputs have changed since cache was recorded.
  Cached hash : fdb8ef6d2a9a156f
  Current hash: a3c7b12e99f04d21

  The cached scores may no longer reflect current pipeline behaviour.
  Run: make eval-record  to update the cache, then re-run this gate.
```

**What is hashed:**
- `app/prompts/chunk_matching.py` — prompt templates and temperature
- `vector_top_k` — retrieval config (K affects which chunks the LLM sees)
- Each fixture's `id`, `section`, `profile` reference, and chunk `content`/`chunk_type`
- All candidate profile files

**What is NOT hashed:**
- `expected_scores` — calibration label changes do not require a new live run
- `description` fields — documentation only

This means: change a prompt, change K, change fixture inputs, or change a profile → gate
fails with a clear message. Change only expected_scores (recalibration) → gate continues.

## Workflow: after a prompt change

1. Make your prompt change
2. Run `make eval-record` — calls real API, updates `scores.json` and `RESULTS.md`
3. Review the diffs in both files before committing — confirm the score changes make sense
4. Commit `scores.json` and `RESULTS.md` alongside your prompt change
5. CI gate recomputes the hash, finds it matches the new cache, proceeds to agreement check

---

## Workflow: after changing retrieval or context-building logic

Changes to `_retrieve_top_k_experience_chunks`, `_build_grouped_context`, or K affect
what context the LLM receives → may change scores even with the same prompt.

Changing `VECTOR_TOP_K` in config or `.env` changes the pipeline hash → gate fails
automatically. Changes to Python retrieval logic (which don't change K) are not
detected by the hash — those require a `make eval-record` run to validate, which is
also the moment you'd want to confirm the logic change had the intended effect anyway.

---

## Workflow: after adding a fixture

1. Add the fixture JSON to `fixtures/` with a new ID (next sequential number)
2. Run `make eval-live` to see scores (live, no cache write) — this tells you whether
   your `expected_scores` are achievable
3. If expected scores are met, run `make eval-record` to fold the new fixture into the cache
4. Commit both the fixture file and the updated `cache/scores.json`

CI will now gate on the new fixture. Its miss counts against the 70% threshold.

---

## Workflow: after switching models

The cached scores were recorded against `gpt-5.4-mini`. If you switch `LLM_MODEL` or
`EMBEDDING_MODEL`:

1. Run `make eval-live` first to see the new model's performance without committing
2. If performance is acceptable (≥ 70% vector), run `make eval-record`
3. The new `scores.json` will capture the new model name in `llm_model` / `embedding_model`
4. Commit. CI will gate against the new baseline.

If the new model performs below 70%, either tune the prompt before recording or lower
the threshold deliberately (update `eval-offline` in both `Makefile` and `ci.yml`).

---

## Workflow: gate is failing in CI

1. Look at the CI output — which fixture(s) are failing and what scores were expected vs cached
2. If a fixture ID has a **cache miss**: the fixture was added but `--record` was never run.
   Run `make eval-record` locally and commit `scores.json`.
3. If agreement is **below threshold**: the cached scores no longer pass 70%. This shouldn't
   happen without a deliberate code change + `--record`. Investigate git history for what
   changed between the last passing run and now.
4. Do not artificially edit `scores.json` by hand to make CI pass — the cache is the source
   of truth for "what the pipeline actually produced". If the scores changed, understand why.

---

## Adding a new profile

Profiles live in `profiles/`. Each is a JSON object conforming to `EvalCandidateProfile`:

```json
{
  "candidate_name": "...",
  "pronouns": "...",
  "description": "One-line summary of background and notable gaps",
  "extracted_profile": {
    "resume": { ... },
    "github": { "repos": [ ... ] }
  }
}
```

The `extracted_profile` format mirrors the internal `extracted_profile` JSON field on the
`Experience` model. Keep profiles synthetic (no real names, companies, or contact info).
Use the description field to document what the profile is and is NOT good for — this makes
fixture authoring easier.

---

## Scaling the corpus

The current 5 fixtures cover: STRONG match, PARTIAL match, clear GAP, non-evaluable
boilerplate, and multi-source evidence. Gaps in coverage:

- Multi-requirement bullets ("3+ years Python or Go")
- Preferred vs required distinction
- Implicit YOE from project context alone
- Non-technical roles (product, design, operations)
- Profiles with only GitHub (no resume)

**Strategy for adding fixtures without burning out:**
Once `TailoringDebugLog` has enough data (event_type=`generation_complete`), real production
inputs can be mined for interesting edge cases. The intended process:
1. Query `tailoring_debug_logs` for tailorings with unusual chunk_batch_count or high
   error_count (signals the matcher struggled)
2. Retrieve the `profile_snapshot` and `extracted_job` from the parent `tailoring`
3. Identify a specific requirement chunk + profile combination worth testing
4. Write the fixture JSON with your expert-labelled `expected_scores`
5. Run `make eval-record` to fold it in

Do not use automated LLM labeling for `expected_scores` — the label is the ground truth;
it must reflect human judgement about what the correct score is.

---

## TailoringDebugLog

Every successful tailoring generation writes one row to `tailoring_debug_logs`:

| Field | Value |
|-------|-------|
| `event_type` | `"generation_complete"` |
| `payload.matching_mode` | `"vector"` or `"llm"` |
| `payload.embedding_model` | e.g. `"text-embedding-3-small"` |
| `payload.llm_model` | e.g. `"gpt-5.4-mini"` |
| `payload.generation_duration_ms` | wall-clock ms for the full pipeline |

The write is non-fatal — a failure logs a warning and does not affect the tailoring.

**Querying:**
```sql
-- Mode distribution across recent tailorings
SELECT payload->>'matching_mode' AS mode, COUNT(*) AS n
FROM tailoring_debug_logs
WHERE event_type = 'generation_complete'
  AND created_at > NOW() - INTERVAL '7 days'
GROUP BY mode;

-- Average generation duration by mode
SELECT
  payload->>'matching_mode' AS mode,
  AVG((payload->>'generation_duration_ms')::int) AS avg_ms
FROM tailoring_debug_logs
WHERE event_type = 'generation_complete'
GROUP BY mode;
```

**Planned next:** admin "Matching Quality" card in the dashboard that surfaces mode
distribution and average duration without requiring a DB query (Day 16+).

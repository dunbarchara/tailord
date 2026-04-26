# Eval Pipeline

Measures LLM chunk-matching accuracy against known fixtures. The goal is a
**baseline number to defend** before making prompt or model changes.

## What it tests

The chunk-matching step scores job requirement chunks against a candidate
profile (STRONG=2, PARTIAL=1, GAP=0, N/A=-1). This is the highest-leverage
LLM call in the pipeline — errors here flow directly into the tailoring output
and the gap analysis. The eval runner measures whether the LLM scores a set of
known inputs the way we expect.

## Running

```bash
# From backend/
uv run python tests/eval/eval_runner.py
```

Requires the local LLM to be running (LM Studio / Ollama at `LLM_BASE_URL`).
Not in CI — run manually before and after prompt changes.

## Structure

```
eval/
├── README.md               — this file
├── eval_runner.py          — loads fixtures, calls LLM, prints results
├── profiles/               — reusable candidate profiles (checked in)
│   └── alex-chen-backend-engineer.json
└── fixtures/               — scoring test cases
    ├── 01-strong-yoe-match.json
    ├── 02-partial-skill-match.json
    ├── 03-clear-gap.json
    ├── 04-non-evaluable.json
    └── 05-multi-source.json
```

## Profiles

Profiles live in `profiles/` and are referenced by fixtures. Each profile is a
JSON object with `candidate_name`, `pronouns`, `description`, and
`extracted_profile` (the same format the backend uses internally). Adding a new
profile type (e.g. a data scientist, a product manager) is a matter of adding a
new JSON file here.

Current profiles:
- `alex-chen-backend-engineer` — senior Python/FastAPI engineer, 7 years YOE,
  strong in databases and cloud infrastructure, no Kubernetes or CRM background

## Fixtures

Each fixture tests a specific scoring pattern:

| Fixture | Pattern | Expected |
|---|---|---|
| `01-strong-yoe-match` | Requirements clearly met (YOE, core stack) | all 2 |
| `02-partial-skill-match` | Adjacent experience (Docker → K8s, no Terraform) | all 1 |
| `03-clear-gap` | Genuine gaps (Salesforce, ML/PyTorch) | all 0 |
| `04-non-evaluable` | Legal boilerplate, perks, compensation | all -1 |
| `05-multi-source` | Evidence spans resume + GitHub | all 2 |

## Interpreting results

Local models (LM Studio, Ollama) are expected to underperform on some fixtures —
particularly `02-partial-skill-match` (partial scoring requires nuance) and
`04-non-evaluable` (requires recognising boilerplate vs requirements). This is
fine: the runner surfaces those weaknesses so we know where prompt work is needed.

The agreement rate from a local model run is not meaningful as a quality bar.
It becomes meaningful when comparing:
- the same model before and after a prompt change
- a hosted model (GPT-4o, Claude) vs the local baseline

## Future work

- Add profiles for: data scientist, product designer, non-technical roles
- Add fixtures for edge cases: multi-requirement bullets, preferred vs required,
  implicit YOE from project context
- CI gate (staging → prod only): once we have confidence in the eval and are
  targeting a specific hosted model, gate deploys on agreement rate ≥ threshold

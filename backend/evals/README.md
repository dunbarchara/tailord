# Eval harness

Compares LLMs on Tailord tasks side by side: quality, calibration, latency, cost and
reliability, per label source. Separate from `app/` (the service never imports it) and from
`tests/eval/` (the CI chunk-matching gate). Background and decisions: `planning/jev-and-evals.md`.
Results of the first benchmark: `planning/results/`.

All commands run from `backend/`.

## Run a benchmark

```
uv run python -m evals run --suite vet            # dry run: prints an estimate, calls nothing
uv run python -m evals run --suite vet --max-spend 0.20     # paid run under a cap
uv run python -m evals report --task semantic_type --all-items
```

- **Spend is opt-in.** Without `--max-spend` nothing paid is called; the dry run prints a
  per-model estimate and a paste-ready command with a suggested cap (estimate x 1.5).
- **The cap holds.** Calls already in flight are reserved against it. At the cap the run pauses
  (`--on-cap pause`, interactive: shows progress, estimate vs actual, a suggested top-up) or
  aborts (`--on-cap abort`, the default without a terminal) and prints the resume command.
- **Resumable.** Results append to `evals/results/<task>/<model>.jsonl` (gitignored), each
  keyed by a hash of the task definition plus that item's input. Re-running does only what is
  missing or stale; adding items or models never repeats a paid call.
- **Rate limits are not answers.** The runner backs off, halves concurrency and requeues. Calls
  that still fail are reported as unresolved (exit code 4) and are excluded from every score;
  the report shows an INCOMPLETE banner. Re-run the same command to retry only those.
- Useful flags: `--concurrency N` (default 8; use 4 on Foundry if it throttles), `--limit N`
  (first N items), `--repeats N` (consistency), `--task T --models a,b`, `--exclude m`,
  `--allow-unpriced` (a model with no pricing is refused otherwise).
- Suites live in `evals/suites.json`: `vet` (cheap pair), `compare` (adds `gpt-5.4`),
  `real-probe` (real postings, no labels).

## Reading a report

Quality is shown against each label source separately, never a blend: the two silver passes
(`silver:sonnet-5-5`, `silver:opus-5-5`), `agreed` (Opus's label where they disagree) and
`adjudicated` (agreed plus reviewed corrections, the reference when present). It scores each
item's first run only, so repeats cannot inflate the sample size. Accuracy carries a 95% Wilson
interval, models are compared with an exact McNemar test, and calibration uses the top-class
probability (n/a for models that report none). A model's failed or invalid answer counts as
wrong; a rate-limited call is "no answer" and excluded.

## Add things

- **A model**: add it to `llm_models.dev.json` and `llm_models.json` (provider, id, pricing; a
  test keeps shared entries identical), then put it in a suite. The adapter is chosen by the
  provider's adapter kind (`openai_compat` or `jev`). Never put a key in the file: providers
  name an env var (`api_key_env`).
- **A task** (classification today): define a `ClassificationTask` in `evals/tasks/`
  (labels with descriptions, instructions, how to render an item), register it in
  `evals/tasks/__init__.py` and `LOADERS` in `evals/__main__.py`, and bump
  `PROMPT_VERSION` in `evals/adapters/base.py` if you change how an adapter builds its prompt.
- **A label source**: `evals/labeling.py` generates self-contained request files for a model to
  fill in (`request`), validates and imports answers (`import`), reports agreement (`report`),
  and builds agreed/adjudicated sets (`agree`, `adjudicate`). Corrections go in
  `evals/data/labels/adjudications.json` with a reason each; silver files are never edited.

## Data (all committed except where noted)

```
evals/data/templates/   board DOM skeletons captured from real pages, scrubbed, with slots
evals/data/postings/    30 hand-written mock postings (src/*.md) rendered to board-style HTML
evals/data/artifacts/   frozen inputs with provenance: markdown, chunks, retrieval
evals/data/labels/      silver, agreed and adjudicated labels
evals/data/local/       real postings for probes (gitignored: never commit real posting text)
evals/results/          run results and generated reports (gitignored)
```

Regenerate frozen artifacts with `python -m evals.stages`, then `python -m evals.labeling
rebuild-chunks`, then `python -m evals.retrieval` (embeds only new text; shows an estimate first).

## One client per API

The harness holds no transport logic. Models are called through the same clients the app uses:
`app/clients/llm_client.py` (`resolve_model`, `llm_parse_with_retry`) and, for Jev,
`app/clients/jev_client.py`. Pin versioned Jev model ids (`jev-1.14.0`), never `jev-latest`.

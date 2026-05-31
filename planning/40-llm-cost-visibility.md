# LLM Cost Visibility

## Context

We have good per-call observability for LLM calls (Loki + Prometheus) but two significant gaps:

1. **Embeddings are a blind spot** — `embed_text` has zero observability. Token counts are never
   read from `response.usage`. There are three call sites: experience claim embedding
   (`experience_embedder.py`), job chunk embedding during vector scoring (`chunk_matcher.py`),
   and one-off calls in the eval runner. All are invisible.

2. **Cached tokens are not captured** — OpenAI returns `usage.prompt_tokens_details.cached_tokens`
   but we throw it away. For `gpt-5.4-mini` cached input is $0.08/1M vs $0.75/1M — a ~10x
   difference. Our chunk scoring calls reuse the same formatted-profile system prompt across
   many calls per tailoring, so cache hit rates should be high. Cost estimates without this
   are materially overstated.

`LlmUsageLog` already exists with `model`, `input_tokens`, `output_tokens`, `cost_usd` columns
(all currently null — forward-declared for this work). That table tracks at the **pipeline
trigger level** (one row per tailoring/process run), not per LLM call. A separate per-call log
table is the right home for prompt-level attribution.

---

## Pricing reference

| Model | Input | Cached input | Output |
|-------|-------|-------------|--------|
| `gpt-5.4-mini` | $0.75/1M | $0.08/1M | $4.50/1M |
| `gpt-5.4` | $2.50/1M | $0.25/1M | $15.00/1M |
| `text-embedding-3-small` | $0.025/1M | — | — |

Cost is computed at query time from raw token counts (never stored as USD) — prices change and
recomputation from stored counts is always accurate.

---

## Prompt inventory

All current LLM call surfaces and their `prompt_name` labels:

| prompt_name | caller | approx calls/tailoring |
|---|---|---|
| `job_extraction` | `job_extractor.py` | 1 |
| `job_bounds` | `job_bounds_detector.py` | 1 |
| `chunk_match_batch` / `chunk_match_single` | `chunk_matcher.py` (llm mode) | 7–15 batches |
| `chunk_match_vector_batch` / `chunk_match_vector_single` | `chunk_matcher.py` (vector mode) | 25–30 single calls |
| `tailoring_generation` | `letter_generator.py` | 1 |
| `gap_question` | `gap_analyzer.py` | 1 |
| `partial_match_question` | `gap_analyzer.py` | 1 |
| `resume_structure_extraction` | `profile_extractor.py` | 1 (experience process) |
| `profile_prose_generation` | `profile_extractor.py` | 1 (experience process) |
| `resume_bullet_polish` | `resume_polisher.py` | per-bullet |
| `github_repo_enrichment` | `github_enricher.py` | per-repo |
| `user_input_parsing` | `experience.py` | per submission |

Embedding call surfaces (`embed_text`):

| embed_context | caller | volume |
|---|---|---|
| `experience_claim_embed` | `experience_embedder.py` | 50–100 per user |
| `job_chunk_embed` | `chunk_matcher.py` (vector mode) | 1 per scored chunk (25–30/tailoring) |

---

## Layers

### Layer 1 — Embedding observability (`embedding_client.py`)

`embed_text` currently returns the embedding vector and discards `response.usage`. Fix:

- Add `embed_context: str = "embed"` parameter (mirrors `prompt_name` on LLM calls)
- Read `response.usage.prompt_tokens` and `response.usage.total_tokens`
- Emit `embedding_call_complete` structured log with `embed_context`, `model`,
  `input_tokens`, `total_tokens`, `latency_ms`
- Add `EMBEDDING_TOKENS_TOTAL` Prometheus counter (labels: `model`, `embed_context`) to
  `metrics.py`
- Add `EMBEDDING_CALL_DURATION_MS` histogram to `metrics.py`
- Update call sites in `experience_embedder.py` and `chunk_matcher.py` to pass `embed_context`

This gives Loki and Prometheus the same visibility for embeddings as for LLM calls.

### Layer 2 — Cached token capture (`llm_utils.py`)

In both `llm_parse` and `llm_generate`:

- Read `usage.prompt_tokens_details.cached_tokens` (present on OpenAI responses; may be `None`
  for other providers — treat as 0 in that case)
- Add `cached_tokens` field to `llm_call_complete` log
- Add `LLM_CACHED_TOKENS_TOTAL` Prometheus counter (same labels as `LLM_TOKENS_TOTAL`,
  direction `cached_input`) to `metrics.py`

### Layer 3 — Per-call DB table

New table `llm_call_logs` (separate from `LlmUsageLog` which is pipeline-trigger scoped):

```
id            UUID PK
user_id       UUID FK → users (SET NULL on delete), nullable — read from structlog context vars
model         VARCHAR(100)
prompt_name   VARCHAR(100)
input_tokens  INTEGER
cached_tokens INTEGER default 0
output_tokens INTEGER
latency_ms    INTEGER
created_at    TIMESTAMPTZ server_default now()
```

Written from `llm_parse`, `llm_generate`, and `embed_text` after every successful call.
`user_id` is populated by reading from structlog context vars (already bound in background
tasks via `bind_contextvars`). Nullable — unauthenticated or system calls leave it null.

Index: `(created_at DESC)` for time-range queries; `(prompt_name, model)` for aggregation.

Migration: new Alembic revision after `b2d3e4f5a6b7`.

**Note on `LlmUsageLog`**: The existing `input_tokens`, `output_tokens`, `cost_usd` columns on
`LlmUsageLog` were forward-declared for this work. With `llm_call_logs` providing per-call
granularity, those columns on `LlmUsageLog` can remain null — `LlmUsageLog` stays focused on
rate limiting and quota enforcement. Do not remove the columns (they may be useful for a
pipeline-level cost rollup later).

### Layer 4 — Grafana dashboard

Two sub-layers: Loki log-based panels (fast, no DB required) and Postgres SQL panels (richer
aggregation, per-user attribution). Both use Grafana data sources already available in the stack.

#### 4a — Loki panels (LogQL)

**Panel 1: LLM call table**
- Filter: `{service="tailord"} |= "llm_call_complete" | json`
- Aggregate `sum by (prompt_name, model)` for call count, input tokens, output tokens, cached tokens
- Add Grafana transformation to compute estimated cost using multiply + add on token fields
- Table visualization with column sorting/filtering
- Time range picker from dashboard controls

**Panel 2: Embedding call table**
- Same approach on `embedding_call_complete` log entries
- After Layer 1 ships, this gets the same visibility as LLM calls

**Panel 3: Cost over time** (line chart)
- Daily estimated cost by prompt_name × model — shows trends, detects regressions

Loki panels are the fast operational view and can ship immediately after Layers 1–2 without
waiting for the DB table.

#### 4b — Postgres panels (SQL via Grafana PostgreSQL data source)

After Layer 3 ships, add panels that query `llm_call_logs` directly. Grafana's PostgreSQL data
source supports `$__timeFrom()` / `$__timeTo()` macros for dashboard time range integration.

**Panel 4: Cost by prompt × model (SQL)**
```sql
SELECT
  prompt_name,
  model,
  COUNT(*)                        AS call_count,
  SUM(input_tokens)               AS input_tokens,
  SUM(cached_tokens)              AS cached_tokens,
  SUM(output_tokens)              AS output_tokens,
  MIN(input_tokens)               AS input_min,
  AVG(input_tokens)::int          AS input_avg,
  MAX(input_tokens)               AS input_max,
  MIN(output_tokens)              AS output_min,
  AVG(output_tokens)::int         AS output_avg,
  MAX(output_tokens)              AS output_max
FROM llm_call_logs
WHERE created_at BETWEEN $__timeFrom() AND $__timeTo()
GROUP BY prompt_name, model
ORDER BY SUM(input_tokens) DESC;
```

**Panel 5: Cost by user (SQL)**
```sql
SELECT
  u.email,
  l.model,
  COUNT(*)           AS call_count,
  SUM(l.input_tokens) AS input_tokens,
  SUM(l.cached_tokens) AS cached_tokens,
  SUM(l.output_tokens) AS output_tokens
FROM llm_call_logs l
LEFT JOIN users u ON u.id = l.user_id
WHERE l.created_at BETWEEN $__timeFrom() AND $__timeTo()
GROUP BY u.email, l.model
ORDER BY SUM(l.input_tokens) DESC;
```

Cost computation from token sums uses Grafana transformations (Field override multiply) — no
custom API needed. Pricing config is maintained as a comment in the dashboard JSON for reference.

This replaces any need for a custom admin API endpoint or in-app admin panel for cost visibility.

---

## Implementation order

1. **Layer 1** — embedding observability (closes the blind spot; unblocks Grafana Panel 2)
2. **Layer 2** — cached token capture (improves cost accuracy; 5-line change)
3. **Layer 4a** — Grafana Loki panels (can ship immediately after Layers 1–2; no DB required)
4. **Layer 3** — `llm_call_logs` DB table + migration + write in `llm_utils.py` + `embed_text`
5. **Layer 4b** — Grafana Postgres panels (depends on Layer 3; adds per-user attribution + min/avg/max)

Layers 1 and 2 are small, isolated, and high-value — do them first. The Loki dashboard (4a) can
ship immediately after — no DB work needed. Layer 3 + 4b add per-user attribution and richer
aggregation via direct SQL. No custom admin API or in-app admin panel is needed — Grafana's
PostgreSQL data source handles everything.

---

## Design decisions

- **90-day retention**: `llm_call_logs` rows are pruned at 90 days — same policy as
  `tailoring_debug_logs` and `llm_usage_logs`. LLM versions iterate fast enough that data older
  than 90 days is not comparable to current anyway. Amortized cleanup runs in `_finalize_tailoring`
  via `cleanup_old_llm_call_logs()` in `llm_call_logger.py`.
- **Grafana SQL panels run automatically**: The `$__timeFrom()` / `$__timeTo()` macros map to the
  dashboard time picker. Panels rerun on load and on any time range change — no manual queries needed.
- **Embeddings in the same table**: `call_type` discriminator (`llm` | `embedding`) in
  `llm_call_logs`. Keeps aggregation queries in one place; model name distinguishes embedding
  model from LLM model in practice.

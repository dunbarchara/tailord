# Observability Walkthrough — Reflections

This document captures questions, answers, exercises, and notes from working through
`planning/26-observability-walkthrough.md`. The goal is to build genuine understanding
of how the platform is observed in production — not just that the tooling exists, but
why each piece is there and how to use it under pressure.

---

## Purpose of this directory

`reflections/` is a space to document understanding, not just decisions. Code and
features are often built by agents — this is where we make sure the human in the loop
stays current on what was built, why, and what it takes to operate it. Expect: learning
notes, answered questions, hands-on exercise results, and gaps flagged for follow-up.

---

## The Mental Model

Three signal types, each answering a different question:

| Signal | Question | Local tool | Azure equivalent |
|--------|----------|------------|-----------------|
| Logs | What happened, and when? | Loki + Grafana | Log Analytics |
| Metrics | How much / how fast / how often? | Prometheus + Grafana | Azure Managed Prometheus |
| Traces | Which operations caused which others? | Tempo + Grafana | Application Insights |

### Technology quick-reference

**Loki** — Log aggregation. Indexes only labels (metadata), not full text — cheap to
run. Logs are queried with LogQL. Locally via Docker; replaced by Log Analytics in Azure.

**Grafana** — Visualization UI. Connects to Prometheus, Loki, Tempo, PostgreSQL and
renders dashboards. Locally in Docker; Azure has a managed equivalent.

**Log Analytics** — Azure's managed log store. Container Apps auto-ship stdout here —
no Promtail needed. Queried with KQL instead of LogQL.

**Prometheus** — Metrics collection. Scrapes `/metrics` every 15s, stores numeric
time-series. Queried with PromQL. Locally in Docker.

**Azure Managed Prometheus** — Hosted Prometheus. Same PromQL queries, Microsoft manages
the infrastructure.

**Tempo** — Distributed tracing backend. Receives spans via OTLP, stores them, lets
you view trace waterfalls in Grafana Explore. No direct UI — local only.

**Application Insights** — Azure's tracing (and more) service. Receives OTel spans via
`AzureMonitorTraceExporter`. Provides transaction search, waterfall views, live metrics.
Replaces Tempo in production.

**structlog** — Python structured logging library. Produces dicts of key/value pairs
serialised to JSON instead of flat text strings. Makes logs machine-queryable and
filterable without regex.

**Histogram** — A metric type tracking the distribution of a value (e.g. latency) by
counting observations into predefined buckets. Lets you compute P95, P99 at query time.

**LGTM** — Acronym for the local stack: Loki + Grafana + Tempo + (managed) Prometheus.

**OTel (OpenTelemetry)** — Vendor-neutral standard for instrumentation. Defines a common
API and wire format (OTLP) for traces, metrics, and logs. Code instruments against the
OTel API; the exporter (Tempo locally, App Insights in Azure) is swapped without touching
instrumentation code.

**OTLP (OpenTelemetry Protocol)** — The wire format OTel uses to send telemetry between
systems. Supports gRPC (port 4317, used locally to Tempo) and HTTP/protobuf (port 4318).
The key idea: instrumentation code is decoupled from the backend — swap the exporter, not
the instrumentation.

---

## Section 1 — Logs

### How Loki works

Loki only indexes labels (metadata like `job="tailord-backend"`). Log content is stored
compressed and unindexed. This makes storage cheap but full-text search requires scanning
compressed chunks. The common case — you know which stream you want, then filter within
it — is fast.

Local flow:
1. Python writes JSON lines to `logs/app.jsonl`
2. Promtail tails the file and ships lines to Loki with labels attached
3. Loki stores lines indexed by labels only
4. Grafana queries with LogQL: label selector first (`{job="tailord-backend"}`), then
   optional pipeline filters (`| json | level = "error"`)

The `| json` step is key: it parses each line as JSON at query time, making any field
(like `tailoring_id`) filterable without pre-indexing it.

---

### Section 1 observability tasks

These are hands-on exercises using a real tailoring created during this walkthrough
session. Tailoring ID: `19a64901-7d97-4507-8a54-c6d6f95e8c07`

All tasks use **Grafana → Explore → Loki → Code mode** at `http://localhost:3001`.
Substitute your own tailoring ID when repeating these.

---

#### Task 1 — Pull every log line for a tailoring

**Goal:** confirm `tailoring_id` propagates through the background task.

```logql
{job="tailord-backend"} | json | tailoring_id = "19a64901-7d97-4507-8a54-c6d6f95e8c07"
```

Expect hundreds of lines — mostly SQLAlchemy and httpcore debug noise. What matters is
that every line carries `tailoring_id`, which proves the background task re-bound context
correctly at the top of `_finalize_tailoring`.

---

#### Task 2 — Get the phase breakdown

**Goal:** see all five pipeline phases and their individual durations (1 pre-phase + 4 background).

```logql
{job="tailord-backend"} | json | tailoring_id = "19a64901-7d97-4507-8a54-c6d6f95e8c07" | event = "phase_complete"
```

Expand each result to see the `phase` and `duration_ms` parsed fields.

Results from this session (tailoring `19a64901`):
```
validate_job_posting      →     82ms   (pre-phase, logged from HTTP handler)
extract_job               →  2,194ms
enrich_job_chunks         →  6,690ms
generate_advocacy_letter  →  4,419ms  ┐ parallel — wall-clock contribution
gap_analysis              → 12,295ms  ┘ is max(4419, 12295) = 12,295ms
```

Note: `validate_job_posting` is the pre-phase and carries `tailoring_id` but not yet
`correlation_id` (it fires before the background task binds context). The other four
phases all carry both fields.

---

#### Task 3 — Get the total generation time in one line

**Goal:** read the `generation_complete` summary event.

```logql
{job="tailord-backend"} | json | tailoring_id = "19a64901-7d97-4507-8a54-c6d6f95e8c07" | event = "generation_complete"
```

Expand the single result — `total_duration_ms` and a nested `phase_durations` object are
both present. This session: `total_duration_ms = 13,353`.

Note: `generation_complete` fires after all 4 background phases complete (including
`gap_analysis`, which runs in parallel with `generate_advocacy_letter`). The
`phase_durations` object contains all 4 phases. `total_duration_ms` reflects wall-clock
time, so the parallel block contributes `max(letter, gap)`, not their sum.

---

#### Task 4 — Inspect individual LLM calls

**Goal:** see every LLM call attributed to this tailoring with token counts and latency.

```logql
{job="tailord-backend"} | json | tailoring_id = "19a64901-7d97-4507-8a54-c6d6f95e8c07" | event = "llm_call_complete"
```

Expand any line — `schema`, `input_tokens`, `output_tokens`, `latency_ms` are all
present. Schemas visible here: `TailoringContent` (main generation call) and `GapQuestion`
(one per gap question).

The `enrich_job_chunks` LLM calls (`ChunkMatchBatch`) will not appear — see the gap note
below.

---

#### Task 5 — Find the slowest LLM call in the session

**Goal:** practice LogQL filtering across all requests.

```logql
{job="tailord-backend"} | json | event = "llm_call_complete"
```

In the results panel, use the Fields sidebar to sort by `latency_ms` descending. The
slowest call in this session was a `TailoringContent` schema call at ~4,407ms.

---

### ~~Gap~~ Fixed — enrich_chunks LLM calls now carry tailoring_id

`chunk_matcher.py` now captures `structlog.contextvars.get_contextvars()` before
dispatching to each `ThreadPoolExecutor`, and re-binds the context at the top of every
worker function. All `llm_call_complete` events inside the parallel scoring threads now
carry `tailoring_id` and `correlation_id`. Applied to all four dispatch sites: enrich
vector, enrich LLM, refresh vector, refresh LLM.

### ~~Gap~~ Fixed — positional log args converted to structured fields

All `logger.info("msg %s", val)` patterns in `chunk_matcher.py` and `gap_analyzer.py`
converted to `logger.info("event_name", field=val)`. Values are now queryable as
structured fields in Loki.

---

## Tailoring generation — pipeline reference

See `reflections/platform-flows.md` for the full canonical reference with line art
diagram, [SEQ]/[PAR] tags, phase failure modes, and observability queries.

Summary: 5 phases total — 1 pre-phase in the HTTP handler (`validate_job_posting`), 4 in
the background task (`extract_job`, `enrich_job_chunks`, `generate_advocacy_letter`,
`gap_analysis`). Phases 3 and 4 run in parallel via `ThreadPoolExecutor`. `generation_complete`
fires after all 4 background phases and includes `phase_durations` for all of them.

### Logging coverage (current state)

| Step | Logged? | Notes |
|------|---------|-------|
| Pre-phase validate_job_posting | `phase_complete` ✓ | carries `tailoring_id` + `correlation_id` |
| Phase 1 extract_job | `phase_complete` ✓ | |
| Phase 2 enrich_job_chunks | `phase_complete` ✓ | |
| Chunk parsing (inside phase 2) | `chunks_extracted` ✓ | `chunk_count`, `duration_ms` |
| Chunk scoring LLM calls | `llm_call_complete` ✓ | ThreadPoolExecutor context propagated |
| Chunk embedding step | `chunks_embeddings_complete` ✓ | |
| Phase 3 generate_advocacy_letter | `phase_complete` ✓ | runs in parallel with gap_analysis |
| generate_advocacy_letter LLM call | `llm_call_complete` ✓ | |
| Phase 4 gap_analysis | `phase_complete` ✓ | runs in parallel with generate_advocacy_letter |
| Gap/partial question LLM calls | `llm_call_complete` ✓ | sequential, context preserved |
| End-to-end summary | `generation_complete` ✓ | all 4 background phases in `phase_durations` |
| All phase errors | `phase_error` ✓ | |

---

## Questions from the walkthrough doc

These are questions posed in `planning/26-observability-walkthrough.md` as checkpoints.
Answers to be filled in as we work through each section.

### Section 1 — Logs

- Why do we clear contextvars at the start of each request rather than just overwriting?
- What happens to logs from a third-party library that uses `logging.getLogger` rather
  than `structlog.get_logger`? (Hint: look at `foreign_pre_chain` in `logging.py`.)
- Why does the background task need to re-bind context explicitly?

### Section 2 — Metrics

- What does the `_bucket`, `_count`, and `_sum` suffix mean on a histogram metric?
- Why does Prometheus pull metrics rather than having the app push them?
- Why do we use `rate()` rather than the raw counter value in dashboards?

### Section 3 — The Local LGTM Stack

- What is Promtail doing exactly? Trace the path from a `logger.info(...)` call in
  Python to a log line appearing in Loki.
- What would break if you changed the Grafana container name in docker-compose?

### Section 4 — Grafana Dashboards

- What is LogQL? How does `{job="tailord-backend"} | json | tailoring_id = "abc"` work?
- Why does Dashboard 05 use a PostgreSQL datasource instead of Prometheus or Loki?

### Section 5 — Distributed Tracing

- What is the W3C `traceparent` header format?
- What happens to the span tree if `carrier` is an empty dict (no parent context)?
- Why does `tailoring.phase.extract_job` appear as a child of the root background task
  span but not as a child of `POST /tailorings`?

### Section 7 — Alerting

- Why is `no-healthy-replicas` severity 0 but `container-restart` is severity 1?
  Shouldn't a restart be worse?
- What is the difference between evaluation frequency (`PT5M`) and window duration
  (`PT15M`)?

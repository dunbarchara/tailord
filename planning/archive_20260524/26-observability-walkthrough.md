# Observability Walkthrough — Tailord Platform

A guided tour of what we built, why each piece exists, and how to operate it.
Use this as a checklist: work through each section, then bring questions here.

**Goal by the end:** you can observe any tailoring generation end-to-end — from the HTTP
request that triggered it, through every LLM call, to the final result — using logs, metrics,
and a trace waterfall, both locally and in Azure.

---

## Before You Start: The Mental Model

Three kinds of **signals** are being collected. Each answers a different question:

| Signal | Question | Tool (local) | Tool (Azure) |
|--------|----------|--------------|--------------|
| **Logs** | *What happened, and when?* | Loki + Grafana | Log Analytics |
| **Metrics** | *How much / how fast / how often?* | Prometheus + Grafana | Azure Managed Prometheus |
| **Traces** | *Which operations caused which others?* | Tempo + Grafana | Application Insights |

The four implementation layers map roughly to this:

```
Layer 1 → Logs (structlog, correlation IDs)
Layer 2 → Metrics (Prometheus counters/histograms, /metrics endpoint)
Layer 3 → Local LGTM stack + dashboards + Azure alerting
Layer 4 → Distributed tracing (OTel → Tempo / Application Insights)
```

Locally, everything flows through **one Docker Compose stack** (`backend/docker-compose.yml`).
In Azure, the same signals go to managed equivalents — but the code doesn't change.

---

## Section 1 — Logs

> **Files:** `backend/app/logging.py`, `backend/app/middleware/correlation.py`

### 1.1 What structlog does and why we use it

Python's built-in `logging` module produces flat text strings.
`structlog` produces **structured log records** — every log call is a dict of key/value pairs
that gets serialised to JSON. That makes logs machine-queryable: you can filter on
`event == "llm_call_complete"` or `latency_ms > 5000` without regex.

Compare:
```
# stdlib logging (text)
INFO:app.tailorings:llm call complete in 1243ms model=gpt-4o

# structlog (JSON in prod)
{"level":"info","event":"llm_call_complete","model":"gpt-4o","latency_ms":1243,
 "input_tokens":812,"output_tokens":341,"correlation_id":"a3f…","trace_id":"00c4…"}
```

In local dev, structlog renders coloured human-readable output instead of JSON
(`ConsoleRenderer` when `ENVIRONMENT=local`, `JSONRenderer` otherwise — see `logging.py`).

### 1.2 Correlation IDs

`CorrelationIdMiddleware` (`middleware/correlation.py`) runs on every HTTP request:

1. Reads `X-Correlation-Id` from the incoming request headers, or generates a UUID4.
2. Calls `structlog.contextvars.clear_contextvars()` — clears any leaked context from the
   previous request on this async worker.
3. Calls `structlog.contextvars.bind_contextvars(correlation_id=...)` — from this point,
   **every** log record in this request's async scope automatically carries `correlation_id`,
   even in code that doesn't know the ID exists.
4. Echoes the ID back in the `X-Correlation-Id` response header.

This means you can grep all logs for a single request across dozens of log lines with one filter.

### 1.3 Trace ID injection (Layer 1 + Layer 4 integration point)

Later in the same middleware, after OTel has set the current span:

```python
span = otel_trace.get_current_span()
ctx = span.get_span_context()
if ctx.is_valid:
    structlog.contextvars.bind_contextvars(
        trace_id=format(ctx.trace_id, "032x"),
        span_id=format(ctx.span_id, "016x"),
    )
```

This ties logs and traces together: every log line carries both IDs, so you can jump from
a Loki log entry directly to the matching Tempo trace waterfall.

### 1.4 Background task continuity

`_finalize_tailoring` runs as a FastAPI `BackgroundTask` — outside the request's async scope.
At the top of that function, correlation context is manually re-established:

```python
structlog.contextvars.clear_contextvars()
structlog.contextvars.bind_contextvars(
    correlation_id=correlation_id,
    tailoring_id=tailoring_id,
)
```

Without this, all log lines from the background task would have no `correlation_id` and you
couldn't correlate them with the HTTP request that triggered the generation.

### 1.5 The JSON sidecar file (`logs/app.jsonl`)

`logging.py` configures a second log handler that writes every record as a JSON line to
`logs/app.jsonl`. Native Alloy (`alloy-native.config`, running on macOS outside Docker) tails
this file and ships it to Loki. Timestamps are emitted in UTC (`utc=True` on `TimeStamper`)
so Loki's `creation_grace_period` window handles any clock skew without rejecting lines.

### 1.6 What to verify ✓

- [ ] Run the backend and create a tailoring. Look at the terminal output — you should see
      coloured structlog lines with `correlation_id` and `tailoring_id` on every record.
- [ ] Find the `generation_started` log and note the `correlation_id`.
- [ ] Grep `logs/app.jsonl` for that ID and confirm all phase logs carry it.
- [ ] Check the HTTP response headers — is `X-Correlation-Id` present?

### Questions and answers

**Q: Why do we clear contextvars at the start of each request rather than just overwriting?**

`structlog.contextvars` stores all bound keys in a single `ContextVar` dict.
If you only overwrote `correlation_id`, any other keys bound earlier on the same async
context would survive into the new request. For example: a background task running on
the same event loop might have previously bound `tailoring_id`. If the next inbound
request only overwrites `correlation_id`, that stale `tailoring_id` would appear on every
log line for the new request. `clear_contextvars()` wipes the entire dict first, so the
new request starts with a known-empty slate before binding its own keys.

---

**Q: What happens to logs from a third-party library that uses `logging.getLogger` rather than `structlog.get_logger`?**

Third-party libraries (uvicorn, SQLAlchemy, the OpenAI SDK, etc.) emit stdlib `LogRecord`
objects that propagate up to the root logger. The root logger's handler is a
`ProcessorFormatter`. When `ProcessorFormatter.format()` receives a record, it checks
whether it was produced by structlog (it carries a special internal marker from
`wrap_for_formatter`) or is "foreign" (everything else). For foreign records it runs
`foreign_pre_chain` — which is the same `_shared_processors` list used in the structlog
pipeline, including `merge_contextvars`. That means a third-party log line emitted during
a request automatically picks up the current `correlation_id`, gets a timestamp, and is
rendered in the same JSON format as first-party structlog lines. The silenced loggers in
`logging.py` (`httpx`, `sqlalchemy.engine.Engine`, etc.) are set to WARNING not because
the bridge doesn't work but because their INFO/DEBUG output is too noisy or contains PII.

---

**Q: Why does the background task need to re-bind context explicitly?**

FastAPI's `BackgroundTasks` runs each task after the response has been sent, in the same
event loop. When the middleware coroutine that bound `correlation_id` finishes sending the
response, its contextvar scope ends — mutations made inside that coroutine are not
automatically visible to code running in a different async scope afterward. The background
task starts with a fresh (or parent-inherited) context that doesn't include the keys the
middleware bound. Re-binding at the top of `_finalize_tailoring` — with both
`correlation_id` and `tailoring_id` — ensures every log line from the background work
carries both IDs and can be correlated back to the originating HTTP request.

---

**Q: Why can't thread pool workers just inherit context automatically?**

They do inherit it — once. When `executor.submit(fn)` is called, Python copies the
current context into the new thread. The problem is that thread pools *reuse* threads.
After a worker thread finishes task A (which may have bound extra keys like `tailoring_id`
from a previous submit), the thread's contextvars from that task persist in memory.
When the pool reuses that same thread for task B (a different tailoring, different
request), it would start with task A's stale context still in place.

The pattern in `chunk_matcher.py` handles this explicitly:

```python
_log_ctx = structlog.contextvars.get_contextvars()   # capture caller's context once

def _score_one_vector(chunk):
    structlog.contextvars.clear_contextvars()         # wipe whatever leaked from the thread's last task
    structlog.contextvars.bind_contextvars(**_log_ctx) # re-apply the correct caller context
    ...
```

`_log_ctx` is captured in the submitting thread before any futures are submitted, so it
holds the right `correlation_id` and `tailoring_id` for this tailoring. Each worker then
clears and re-applies it fresh, regardless of what that thread was doing previously.

---

**Q: What is the practical difference between Loki labels and JSON fields, and what would break if you made `correlation_id` a label?**

Loki's storage model is stream-based. Every unique combination of label values defines a
**stream**, and all log lines for that stream are stored together in sequence on disk.
Labels like `{job="tailord-backend", level="ERROR"}` let Loki look up the exact stream
without touching any log content — that's fast.

`correlation_id` is high-cardinality: every HTTP request gets a unique value. Promoting
it to a label would create a new stream per request. With thousands of requests, Loki
would maintain thousands of streams in memory, blow up its index, and degrade ingestion
throughput. This is called label cardinality explosion and is the most common way to
misuse Loki.

Instead, `correlation_id` lives as a JSON field, queried with a content filter:
`{job="tailord-backend"} | json | correlation_id = "abc123"`. Loki fetches the relevant
streams by label (just `job`), then scans the content within those streams and filters.
It is a full scan within the stream, but at this scale the streams stay small enough that
this is fast in practice.

Rule of thumb: labels for things you always filter by (job, level, logger — a handful of
values), JSON fields for things that identify specific events (correlation_id, tailoring_id,
prompt_name — unbounded values).

---

**Q: Why does log shipping run as a native process instead of inside Docker?**

On macOS, Docker Desktop mounts project directories into containers via VirtioFS. The Linux
`inotify` API — which Promtail and Docker-based Alloy use to watch files — does not receive
events for writes made to VirtioFS bind mounts from the host side. The log file (`logs/app.jsonl`)
is written by the backend process running natively on macOS; Docker containers bind-mounting
that directory never see the kernel-level `IN_MODIFY` events.

The fix: run Alloy natively on macOS (`alloy-native.config`), where it uses `FSEvents`/`kqueue`
and receives file-change notifications correctly. The Docker-based `alloy` service handles
metrics and traces (which are pushed over TCP and don't rely on filesystem watching); native
Alloy handles only log shipping.

**Q: What did the `app.jsonl*` glob in Promtail cause on each rotation?** (historical)

Before the switch to native Alloy, Promtail ran in Docker with a glob pattern.
`RotatingFileHandler` works by renaming: when `app.jsonl` hits 5 MB, Python renames it to
`app.jsonl.1`, then opens a fresh `app.jsonl`. Promtail tracked positions by file path, so
finding no entry for `app.jsonl.1` it treated the renamed backup as a new file and re-shipped
everything from position 0. This caused duplicate log lines in Loki on every rotation. The
immediate fix was removing the glob (watch only `app.jsonl`); the permanent fix was moving to
native Alloy which avoids the inotify issue entirely.

---

## Section 2 — Metrics

> **Files:** `backend/app/metrics.py`, `backend/app/main.py` (`/metrics` mount)

### 2.1 What Prometheus metrics are

Metrics are **numeric time-series**. Unlike logs (one event per line), a metric is a counter
or histogram that gets *scraped* by Prometheus on a schedule. You don't push; Prometheus
pulls `/metrics` every 15 seconds and stores what it finds.

Four metric types matter here:

| Type | Use case | Example |
|------|----------|---------|
| `Counter` | Monotonically increasing count | total HTTP requests |
| `Gauge` | Value that goes up and down | active generations right now |
| `Histogram` | Distribution of values with buckets | request latency |
| `Summary` | Like histogram but pre-computed quantiles | (we don't use this) |

### 2.2 Our metric inventory

**HTTP layer** (recorded in `_RequestLoggingMiddleware`):
- `http_requests_total` — counter, labels: `method`, `endpoint`, `status_code`
- `http_request_duration_ms` — histogram, labels: `method`, `endpoint`

**LLM layer** (recorded in `llm_utils.py`):
- `llm_call_duration_ms` — histogram, labels: `model`, `prompt_type`
- `llm_tokens_total` — counter, labels: `model`, `prompt_type`, `direction` (input/output)
- `llm_retries_total` — counter, labels: `model`, `prompt_type`
- `llm_errors_total` — counter, labels: `model`, `prompt_type`, `error_type`

**Tailoring pipeline** (recorded in `_finalize_tailoring`):
- `tailoring_generations_total` — counter, labels: `status`, `matching_mode`
- `tailoring_generation_duration_ms` — histogram (end-to-end wall time)
- `tailoring_phase_duration_ms` — histogram, label: `phase`
- `tailoring_active_generations` — gauge (concurrent background tasks right now)

### 2.3 Labels and cardinality

Labels let you slice metrics. `http_requests_total{status_code="500"}` gives you just 5xx
counts. But labels create separate time-series for every unique combination — don't use
high-cardinality values like `user_id` or `tailoring_id` as labels, or Prometheus runs out
of memory. That's why `endpoint` is normalised (UUIDs replaced with `{id}`) in
`_normalize_path`.

### 2.4 Querying with PromQL

PromQL is Prometheus's query language. Key patterns:

```promql
# Rate of requests per second over last 5m
rate(http_requests_total[5m])

# P95 LLM call latency
histogram_quantile(0.95, rate(llm_call_duration_ms_bucket[5m]))

# Active generations right now
tailoring_active_generations

# Error rate percentage
100 * rate(http_requests_total{status_code=~"5.."}[5m])
  / rate(http_requests_total[5m])
```

### 2.5 What to verify ✓

- [ ] Start docker-compose (`cd backend && docker compose up -d`).
- [ ] Start the backend (`uv run uvicorn app.main:app --reload`).
- [ ] Hit `http://localhost:8000/metrics` — you should see Prometheus exposition format output.
- [ ] Open Prometheus at `http://localhost:9090`.
- [ ] Query `http_requests_total` — it should show zero until you make requests.
- [ ] Create a tailoring. Re-query — counters should have incremented.
- [ ] Query `tailoring_active_generations` during generation — should be 1.

### Questions to bring
- What does the `_bucket`, `_count`, and `_sum` suffix mean on a histogram metric?
- Why does Prometheus *pull* metrics rather than having the app *push* them?
- Why do we use `rate()` rather than the raw counter value in dashboards?

---

## Section 3 — The Local LGTM Stack

> **Files:** `backend/docker-compose.yml`, `observability/provisioning/`

### 3.1 What LGTM stands for

**L**oki + **G**rafana + **T**empo + (Managed) **P**rometheus → LGTM.
Together they form a complete local observability platform. All four run via Docker Compose.

### 3.2 Service map

```
┌─────────────────────────────────────────────────────────────────┐
│  docker-compose.yml                                              │
│                                                                  │
│  postgres    :5432           ← app database                      │
│  azurite     :10000          ← blob storage (local Azure)        │
│  prometheus  :9090           ← remote_write receiver + storage   │
│  loki        :3100           ← log aggregation                   │
│  alloy       :12345/:4317/:4318                                  │
│                ← scrapes /metrics → Prometheus (remote_write)    │
│                ← receives OTLP traces → Tempo                    │
│  tempo       :3200           ← trace storage + query             │
│  grafana     :3001           ← UI for all four signals           │
└─────────────────────────────────────────────────────────────────┘

Native Alloy (macOS host, alloy-native.config):
  tails logs/app.jsonl → Loki
  (runs outside Docker because inotify doesn't fire on macOS bind mounts)
```

### 3.3 Provisioning-as-code

Grafana is configured entirely through files in `observability/provisioning/` — no manual
UI setup required after `docker compose up`. On startup, Grafana reads:

- `datasources/local.yaml` — connects to Prometheus, Loki, Tempo, PostgreSQL
- `dashboards/provider.yaml` — tells Grafana where to find dashboard JSON files
- `observability/dashboards/local/*.json` — the 5 dashboards, loaded automatically

If you delete the Grafana container and recreate it, everything comes back exactly as it was.
This is the right way to manage Grafana: dashboards live in git, not in a database.

**Dashboard JSON is generated, not hand-edited.** The source of truth is
`observability/dashboards/generate.py`. To change a dashboard, edit the generator and run:

```bash
make generate-dashboards   # regenerates both local/ and prod/ JSON
make check-dashboards      # CI also runs this to catch stale artifacts
```

The generator handles the local/prod split natively: local files use Loki + LogQL, prod files
use Azure Monitor + KQL. No `__prod_*` metadata fields or two-pass transforms needed.

### 3.4 Starting the full stack

```bash
cd backend

# Start everything (first time: downloads images, ~2 min)
docker compose up -d

# Check all services are healthy
docker compose ps

# Start the backend (separate terminal)
uv run uvicorn app.main:app --reload

# Start native Alloy for log shipping (separate terminal, from backend/)
# Install once: brew install grafana/grafana/alloy
alloy run alloy-native.config --storage.path=/tmp/alloy-native-data
```

Ports:
- `http://localhost:3001` — Grafana (no login needed locally)
- `http://localhost:9090` — Prometheus
- `http://localhost:3100` — Loki (API only, use via Grafana)
- `http://localhost:12345` — Alloy UI (pipeline graph for metrics + traces)
- Tempo — no UI, accessed only through Grafana's Tempo datasource

### 3.5 What to verify ✓

- [ ] `docker compose ps` — all services show `Up` or `running`.
- [ ] Open Grafana → Home → Dashboards. You should see 5 dashboards without having
      configured anything.
- [ ] Open Grafana → Explore → select the Prometheus datasource → query
      `up` — all scraped targets should return `1`.
- [ ] Open Grafana → Explore → select the Loki datasource → query `{job="tailord-backend"}`
      — log lines should appear after you make requests.

### Questions to bring
- Trace the path from a `logger.info(...)` call in Python to a log line appearing in Loki.
  Which process ships the line? Why does it run outside Docker?
- What would break if you changed the Grafana container name in docker-compose?

---

## Section 4 — Grafana Dashboards

> **Files:** `observability/dashboards/generate.py`, `observability/dashboards/local/*.json`

### 4.1 The five dashboards

**01 — Platform Health**
The first thing to open when something feels wrong. Shows:
- Request rate and error rate side by side (are errors spiking?)
- P95 request latency (is the app slow?)
- Active generation gauge (is there a stuck background task?)
- Container CPU and memory (is the process healthy?)

**02 — LLM Observability**
For understanding LLM cost and reliability:
- Call rate by `prompt_type` (which LLM calls are happening most?)
- Token consumption over time (how much are we spending?)
- Retry rate (is the LLM misbehaving?)
- Error counts (how often are LLM calls failing completely?)

**03 — Tailoring Pipeline**
End-to-end pipeline health:
- Tailoring creation rate and success/error breakdown
- Phase duration stacked bar — which phase takes the most time?
- Matching mode distribution (vector vs. LLM)
- Active generations (concurrent background tasks)

**04 — Per-Tailoring Debug**
Takes a `tailoring_id` as an input variable. Shows:
- All log lines for that specific tailoring (Loki query filtered by `tailoring_id`)
- Phase durations from TailoringDebugLog (PostgreSQL datasource)
- LLM calls for that tailoring from TailoringDebugLog

Use this dashboard when a user reports a specific tailoring is wrong or slow.

**05 — User Activity** (admin-level)
Business metrics from the database directly:
- Tailorings created per day
- Active users
- Resume uploads over time

### 4.2 How to read a Grafana panel

Each panel has a query behind it. You can click the panel title → Edit to see the PromQL,
LogQL, or SQL query. This is the fastest way to understand what a panel actually measures.

Key UI controls:
- **Time range** (top-right) — all panels update together when you change this.
- **Refresh** (top-right) — useful to set to auto-refresh during an active incident.
- **Variables** — if a dashboard has dropdowns at the top (like `tailoring_id` in Dashboard 04),
  changing them re-runs all queries with the new value.

### 4.3 What to verify ✓

- [ ] Create a tailoring while watching Dashboard 01 — active generations gauge should
      increment then return to zero.
- [ ] Open Dashboard 03 after the tailoring completes. Can you see the phase durations?
- [ ] Copy the tailoring ID from the URL. Open Dashboard 04 and paste it in the variable.
      Can you see the log timeline for that specific tailoring?
- [ ] Open any panel in edit mode and read the underlying query.

### Questions to bring
- What's LogQL? How does `{job="tailord-backend"} | json | tailoring_id = "abc"` work?
- Why does Dashboard 05 use a PostgreSQL datasource instead of Prometheus or Loki?

---

## Section 5 — Distributed Tracing

> **Files:** `backend/app/telemetry.py`, `backend/app/api/tailorings.py`,
> `backend/app/core/llm_utils.py`, `frontend/src/instrumentation.ts`

### 5.1 Why tracing exists (the problem it solves)

Logs tell you *what* happened. Metrics tell you *how often*. Neither tells you *why one
operation caused another*, or how long each step of a multi-step process actually waited.

The tailoring pipeline is a perfect illustration:
- An HTTP request arrives and returns a `ready` event in ~2 seconds.
- A background task then runs for 30–120 seconds making 10–50 LLM calls.
- Logs are chronological but not causal — you can't easily see which LLM calls belong to
  which phase, or why the `enrich_chunks` phase took 40s on this run but 12s on the last.

A trace is a **tree of spans** that preserves causality:

```
POST /tailorings  (HTTP span, ~2s, created by FastAPI auto-instrumentation)
  └── background_task.tailoring.generate  (~85s, started in _finalize_tailoring)
        ├── tailoring.phase.extract_job  (~3s)
        │     └── llm.call  (prompt_type="ExtractedJob", 2.8s, 1200 input tokens)
        ├── tailoring.phase.enrich_chunks  (~40s)
        │     ├── llm.call  (prompt_type="ChunkScore", 1.1s)
        │     ├── llm.call  ...
        │     └── llm.call  (×N — one per job chunk)
        ├── tailoring.phase.generate_tailoring  (~35s)
        │     └── llm.call  (prompt_type="generate", 34s, 4200 input tokens)
        └── tailoring.phase.gap_analysis  (~6s)
              └── llm.call  (prompt_type="GapAnalysis", 5.8s)
```

In Tempo's UI this renders as a **flame graph** / **waterfall** — you can see exactly
where time went.

### 5.2 How the background task gets parented to the HTTP request

This is the trickiest part, because the background task runs in a different thread/context
from the HTTP handler that created it.

In `_stream_tailoring` (the HTTP handler), just before scheduling the background task:

```python
from opentelemetry import propagate as _otel_propagate
_otel_carrier: dict = {}
_otel_propagate.inject(_otel_carrier)
# _otel_carrier now contains e.g. {"traceparent": "00-abc123...-def456...-01"}
```

`propagate.inject` serialises the current span context (trace ID + span ID) into a dict
using the W3C TraceContext format. This dict is passed as `carrier` to `_finalize_tailoring`.

At the top of `_finalize_tailoring`:

```python
_parent_ctx = _otel_propagate.extract(carrier or {})
with _tracer.start_as_current_span(
    "background_task.tailoring.generate",
    context=_parent_ctx,   # ← this is the key line
    ...
):
```

`propagate.extract` deserialises the carrier back into a context object. Passing that
context as `context=` to `start_as_current_span` makes the new span a **child** of the
HTTP handler's span, even though they run in different threads. Same trace ID, different
span IDs.

### 5.3 Exporter selection

`backend/app/telemetry.py` switches based on `settings.environment`:

```
local       → OTLP gRPC  → Tempo (:4317)   (docker-compose)
staging/prod → AzureMonitorTraceExporter    (APPLICATIONINSIGHTS_CONNECTION_STRING)
else        → no-op (tracing disabled, app still runs fine)
```

No inline exporter code anywhere else in the codebase — everything goes through
`get_tracer("tailord.tailoring")` which returns a no-op tracer if nothing is configured.

### 5.4 LLM call spans

Every call to `llm_parse()` or `llm_generate()` in `llm_utils.py` creates a `llm.call`
span with these attributes:

- `llm.model` — the model name
- `llm.prompt_type` — the Pydantic response model name or label string
- `llm.input_tokens` / `llm.output_tokens` — from the API response
- `llm.finish_reason` — `stop`, `length`, etc.
- `llm.latency_ms`

These are child spans of whatever phase span is currently active, so they appear nested
correctly in the waterfall.

### 5.5 Frontend tracing

`frontend/src/instrumentation.ts` sets up a `NodeTracerProvider` that sends traces from
Next.js API routes to the same OTLP endpoint. Service name: `tailord-frontend`. This means
you can see Next.js API route spans in Tempo alongside the backend spans — useful for
measuring the full round-trip including proxy overhead.

### 5.6 What to verify ✓

- [ ] With docker-compose running, create a tailoring.
- [ ] Open Grafana → Explore → select the **Tempo** datasource.
- [ ] Click "Search" → Service Name: `tailord-backend` → Run Query.
- [ ] Find the trace for the tailoring you just created. Click it.
- [ ] Verify the waterfall shows: `POST /tailorings` → `background_task.tailoring.generate`
      → 4 phase spans → `llm.call` children.
- [ ] Click a `llm.call` span — check the attributes panel on the right for token counts.
- [ ] In Loki, query `{job="tailord-backend"} | json | trace_id = "<your_trace_id>"` —
      all log lines for that trace should be returned.

### Questions to bring
- What is the W3C `traceparent` header format?
- What happens to the span tree if `carrier` is an empty dict (no parent context)?
- Why does `tailoring.phase.extract_job` appear as a child of the root background task
  span but not as a child of `POST /tailorings`?

---

## Section 6 — Log-Metric-Trace Correlation

This is where the three signals become more than the sum of their parts.

### 6.1 From a log line to a trace

Every request log line carries `trace_id` and `span_id`. If you see an error in Loki:

```
{job="tailord-backend"} | json | event = "phase_error"
```

Click a result → expand → copy the `trace_id` value → go to Tempo → search by trace ID.
You get the full waterfall showing exactly what state the system was in when the error
occurred: which phase, which LLM call, how long everything had been running.

### 6.2 From a metric alert to a log investigation

An alert fires: `generation_failure_spike` (>5 errors in 30 min).

1. Open Dashboard 01 — confirm error rate spike, note the time window.
2. Open Dashboard 03 — see which phase is failing (phase duration bars will be truncated for failures).
3. Open Loki Explore — query for errors in that window:
   ```
   {job="tailord-backend"} | json | level = "error" | event = "phase_error"
   ```
4. Find a `tailoring_id` in the results. Open Dashboard 04 with that ID.
5. If you want the trace: copy `trace_id` from the log line → Tempo search.

### 6.3 From a trace to logs

In Tempo's UI, when viewing a trace, you can click "Logs for this span" if the Tempo and
Loki datasources are configured with trace-to-logs correlation (which they are via the
Grafana datasource provisioning). This jumps directly to Loki filtered by `trace_id`.

### 6.4 What to verify ✓

- [ ] Trigger a tailoring that you know will fail (e.g., bad LLM config). Find the error
      in Loki. Follow it to Tempo. Confirm the waterfall shows where it died.
- [ ] In Tempo, view a trace and use the "Logs" button to jump to Loki.

---

## Section 7 — Alerting

> **File:** `infra/providers/azure/monitoring.tf`

### 7.1 Alert types

We have two types of Azure Monitor alerts:

**Metric alerts** — react to numeric thresholds in near real-time:
- `container-restart` — any container restart (severity 1, 5m eval)
- `memory-pressure` — backend memory > 860 MiB (severity 2, 5m eval)
- `no-healthy-replicas` — zero running replicas (severity 0, 1m eval)

**Log search alerts** — run KQL queries against Log Analytics on a schedule:
- `backend-error-rate` — 5xx rate > 5% over ≥10 requests (15m window)
- `llm-timeout-spike` — >3 LLM errors in 15 minutes
- `generation-failure-spike` — >5 `phase_error` or `generation_error` events in 30m
- `p95-latency-degradation` — P95 request latency > 5000ms
- `log-analytics-quota` — daily ingestion quota reached

All alerts send to the `ops_email` action group (email address set via `alert_email` variable).

### 7.2 Severity levels

Azure Monitor uses 0–4 (0 = critical, 4 = informational). Our three metric alerts cover:
- Severity 0: zero replicas (the app is completely down)
- Severity 1: container restart (the app is crashing and restarting)
- Severity 2: memory pressure (it might crash soon)

### 7.3 KQL vs LogQL

In Azure, logs are queried with **KQL** (Kusto Query Language), not LogQL.
The queries in `monitoring.tf` are KQL — they parse the JSON log lines from container stdout:

```kql
ContainerAppConsoleLogs_CL
| where ContainerAppName_s contains "backend-prod"
| extend p = parse_json(Log_s)
| where tostring(p.event) == "request_complete"
| summarize total = count(), errors = countif(toint(p.status_code) >= 500)
```

Locally you use LogQL in Loki. In Azure you use KQL in Log Analytics. Same underlying data
(our structured JSON logs), different query language.

### 7.4 What to verify ✓

- [ ] Read through each alert rule in `monitoring.tf` — make sure you understand what
      condition triggers each one and why those thresholds make sense.
- [ ] For the log search alerts: trace the path from a Python `logger.error(...)` call to
      the log line appearing in Log Analytics and triggering the alert query.

### Questions to bring
- Why is `no-healthy-replicas` severity 0 but `container-restart` is severity 1? Shouldn't
  a restart be worse?
- What's the difference between evaluation frequency (`PT5M`) and window duration (`PT15M`)?

---

## Section 8 — Azure Production

> **File:** `infra/providers/azure/monitoring.tf`, `infra/providers/azure/main.tf`

### 8.1 How the local stack maps to Azure

| Local | Azure |
|-------|-------|
| Prometheus `:9090` | Azure Managed Prometheus (in `azurerm_monitor_workspace`) |
| Grafana `:3001` | Azure Managed Grafana (in `azurerm_dashboard_grafana`) |
| Loki `:3100` | Log Analytics Workspace (container stdout auto-collected) |
| Tempo `:4317` | Application Insights (OTel via `AzureMonitorTraceExporter`) |

### 8.2 How the backend connects to Application Insights

`setup_telemetry()` reads `settings.applicationinsights_connection_string`. In production,
this is injected from Key Vault via a Container App secret (`appinsights-connection-string`).
The connection string is output by `azurerm_application_insights.tailord.connection_string`
in Terraform.

When `settings.environment` is `staging` or `production` and the connection string is set,
`AzureMonitorTraceExporter` sends traces directly to Application Insights.
In Application Insights, you get:
- **Transaction search** — find traces by operation ID (= OTel trace ID)
- **Application map** — shows relationships between frontend and backend services
- **Performance** → **End-to-end transaction details** — equivalent to Tempo's waterfall
- **Live Metrics** — real-time request/failure/latency, visible within seconds of deploy

### 8.3 Log shipping in Azure

Azure Container Apps automatically ship container stdout to a Log Analytics Workspace —
no Promtail needed. Our structured JSON goes to the `ContainerAppConsoleLogs_CL` table.
The KQL queries in our alert rules parse this table.

### 8.4 What to verify (after a deploy) ✓

- [ ] After a deploy, open Application Insights → Live Metrics.
      Make a request. Does it appear within ~5 seconds?
- [ ] Create a tailoring in staging. In Application Insights → Transaction Search,
      find the trace. Is the full waterfall visible including the background task phases?
- [ ] Open Log Analytics → Logs. Run the error rate KQL query from `monitoring.tf`.
      Does it return results for recent requests?

---

## Section 9 — Operational Runbooks

Common scenarios and how to work through them.

### Runbook A: "A user says their tailoring failed"

1. Ask for (or find) the tailoring ID from the URL or database.
2. **Local**: Open Grafana → Dashboard 04 → enter `tailoring_id`. Check log timeline.
   **Azure**: Log Analytics → `ContainerAppConsoleLogs_CL | where Log_s contains "<tailoring_id>"`
3. Find the `phase_error` or `generation_error` event. Note `trace_id`.
4. Open Tempo (local) or Application Insights → Transaction Search (Azure) with that trace ID.
5. The waterfall shows which phase failed and how far it got.
6. Common causes:
   - `extract_job` failed → Playwright couldn't scrape the URL, or LLM returned bad JSON
   - `enrich_chunks` failed → embedding or LLM scorer timed out
   - `generate_tailoring` failed → LLM timeout (check `llm_call_duration_ms` in Dashboard 02)

### Runbook B: "LLM calls seem slow"

1. Open Dashboard 02 → LLM Call Duration histogram.
2. If P95 has spiked: check `llm_errors_total` for timeouts.
3. Check if it's one `prompt_type` or all of them (one = model-specific issue, all = endpoint issue).
4. In Tempo: find a slow trace and look at which `llm.call` span is slow — check `llm.input_tokens`.
   Very high input tokens often explains slow calls.
5. If the LLM endpoint is completely unreachable: `tailoring_active_generations` gauge will be
   stuck > 0 for an unusually long time.

### Runbook C: "The app seems down / no responses"

1. **Azure**: Check `no-healthy-replicas` alert — has it fired?
2. Open Dashboard 01 → container CPU/memory panels.
3. `container-restart` metric alert fires on any restart — check email.
4. Azure Portal → Container App → Revision → Logs → look at system events.
5. If memory: the tailoring pipeline holds large profile strings in memory during generation.
   Check if `tailoring_active_generations` was > 1 before the crash (memory exhaustion from
   concurrent tasks).

### Runbook D: "The daily Log Analytics quota alert fired"

The workspace has a 0.5 GB/day cap (cost control). If it fires:
1. Log Analytics → Usage and estimated costs → check which table is consuming the quota.
2. Usually `ContainerAppConsoleLogs_CL` from verbose logging.
3. Check if `LOG_LEVEL` was accidentally set to DEBUG in production (extremely verbose).
4. Temporary fix: filter low-value log events at the structlog level (raise the log level
   threshold for noisy loggers in `logging.py`). In Azure, log shipping is handled by the
   Container Apps platform — there is no Alloy/Promtail scrape interval to adjust.

---

## Summary: Key Files Reference

| What | Where |
|------|-------|
| Logging setup | `backend/app/logging.py` |
| Correlation ID middleware | `backend/app/middleware/correlation.py` |
| Prometheus metrics definitions | `backend/app/metrics.py` |
| OTel tracer setup | `backend/app/telemetry.py` |
| Phase spans + carrier injection | `backend/app/api/tailorings.py` |
| LLM call spans | `backend/app/core/llm_utils.py` |
| Frontend tracing | `frontend/src/instrumentation.ts` |
| Docker Compose stack | `backend/docker-compose.yml` |
| Docker Alloy config (metrics + traces) | `backend/alloy.config` |
| Native Alloy config (log shipping) | `backend/alloy-native.config` |
| Loki config | `backend/loki.yml` |
| Grafana provisioning | `observability/provisioning/` |
| Dashboard generator (source of truth) | `observability/dashboards/generate.py` |
| Azure alerts + Application Insights | `infra/providers/azure/monitoring.tf` |

## Summary: Key URLs (local)

| What | URL |
|------|-----|
| Grafana (all dashboards) | http://localhost:3001 |
| Prometheus (raw metrics) | http://localhost:9090 |
| Backend metrics endpoint | http://localhost:8000/metrics |
| Alloy UI (pipeline graph) | http://localhost:12345 |
| Loki API (via Grafana Explore) | http://localhost:3001/explore |
| Tempo (via Grafana Explore) | http://localhost:3001/explore |

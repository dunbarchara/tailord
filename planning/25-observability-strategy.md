# Observability Strategy — Tailord Platform

**Status**: All 4 layers complete
**Scope**: Backend (FastAPI), Frontend (Next.js), Infrastructure (Azure Container Apps + PostgreSQL)
**Last updated**: 2026-05-13 (Day 23)

## Implementation Status

| Layer | Description | Status |
|-------|-------------|--------|
| 1 | Structured JSON logging, correlation IDs, TailoringDebugLog | **Done** (Day 23) |
| 2 | Prometheus metrics, `/metrics` endpoint, Azure Managed Grafana | **Done** (Day 23) |
| 3 | Dashboards (5), alert rules in Terraform | **Done** (Day 23) |
| 4 | OpenTelemetry distributed tracing → Application Insights | **Done** (Day 23) |

## Pending

- [ ] Add `azurerm_monitor_scheduled_query_rules_alert_v2` in `monitoring.tf` for job scrape failure spikes. All three failure events (`playwright_scrape_failed`, `playwright_timeout`, `job_content_invalid`) are already logged with `url` — the alert just needs a KQL query over `ContainerAppConsoleLogs_CL` counting these events in a 15-minute window, firing when count exceeds a threshold (suggested: 5). A spike here likely means a major job board has started blocking the scraper and warrants investigation of the URLs in the logs.

### Layer 1 — What was built (Day 23)

- **`backend/app/middleware/correlation.py`** — Pure-ASGI `CorrelationIdMiddleware`. Reads or generates `X-Correlation-Id` per request, calls `structlog.contextvars.clear_contextvars()` + `bind_contextvars(correlation_id=...)`, echoes header in response. Safe for SSE streaming.
- **`backend/app/logging.py`** — `structlog` configured with `ProcessorFormatter`. Native `structlog.get_logger()` loggers use keyword args (`logger.info("event_key", model=model, latency_ms=ms)`). Stdlib `logging.getLogger()` loggers in unmodified files also emit JSON via `foreign_pre_chain`. `merge_contextvars` injects `correlation_id` (and any other bound context) into every log record automatically. Renderer is environment-aware: `ConsoleRenderer` (colored, human-readable) for `local`, `JSONRenderer` for staging/prod.
- **`backend/app/main.py`** — `CorrelationIdMiddleware` registered as outermost layer; `_RequestLoggingMiddleware` logs `request_start` and `request_complete` events with method, path, status_code, duration_ms.
- **`backend/app/core/llm_utils.py`** — All log calls use structured `extra={}`: `event`, `model`, `schema`/`label`, `input_tokens`, `output_tokens`, `latency_ms`, `finish_reason`. Retries emit `event="llm_retry"`, exhaustion emits `event="llm_error"`.
- **`backend/app/api/tailorings.py`** — `_finalize_tailoring` accepts `correlation_id: str = ""`, re-sets ContextVar at task entry. `_write_debug_log()` helper (non-fatal, own session). Per-phase wall-clock timing. `TailoringDebugLog` fully populated: `generation_started`, `phase_complete`/`phase_error` for all 5 phases, `generation_complete`/`generation_error`.
- **`frontend/src/lib/proxy.ts`** — All 3 proxy functions generate a UUID, send `X-Correlation-Id` to backend, include `correlation_id` in log calls, echo in response headers.

---

---

## Current State (Audit)

### What Exists

- **Backend logging**: Python `logging` module, unstructured string format (`"%(asctime)s | %(levelname)s | %(name)s | %(message)s"`), stdout in prod (collected by Log Analytics Workspace)
- **LLM instrumentation** (`llm_utils.py`): best-instrumented layer — `time.perf_counter()` per call, token counts (prompt/completion/total), finish reason, retry attempts, all logged at INFO
- **DB telemetry columns**: `generation_duration_ms`, `chunk_batch_count`, `chunk_error_count`, `generation_stage`, `generation_started_at`, `generated_at`, `matching_mode` on `Tailoring`
- **`TailoringDebugLog` table**: scaffolded, one event type written (`generation_complete`) but writes silently and non-fatally — effectively unused
- **`LlmTriggerLog`**: rate-limit event tracking per user
- **Frontend logger** (`frontend/src/lib/logger.ts`): JSON to console/stderr, no APM integration
- **Log Analytics Workspace** (`infra/providers/azure/monitoring.tf`): provisioned, connected to both Container App Environments (auto-ingests stdout/stderr), 30-day retention, 0.5 GB/day quota
- **Health endpoint**: `GET /health` returns `{"status": "ok"}`

### What Is Missing

- No correlation IDs — cannot trace a user action end-to-end
- No structured JSON logging — logs are not machine-queryable by field
- No request/response middleware — no per-request latency tracking
- No metrics pipeline — no Prometheus, no OpenTelemetry metrics
- No distributed tracing — no spans
- No Application Insights integration
- No Grafana or dashboards
- No alert rules
- No per-phase timing within `_finalize_tailoring()` (only wall-clock total)
- No frontend error tracking or client-side observability

---

## Section 1: Guiding Principles

### Three Pillars

**Logs** answer "what happened?" — event-level narrative with context.
**Metrics** answer "how is the system performing?" — quantitative, time-series, aggregatable.
**Traces** answer "where did the time go?" — causal chains across service boundaries.

All three are necessary. For this project at current scale, logs and metrics deliver the most value. Tracing is valuable but optional in the first iteration.

### Correlation: One ID to Rule Them All

Every user-initiated action (HTTP request, SSE stream, background task) carries a single `correlation_id` from entry to completion. This ID appears in every log line, every metric label, and every trace span. Without it, debugging requires guessing which log lines belong to which request.

### Structured Everything

Logs are JSON. Every field is a named key with a consistent type. This is the minimum requirement for Log Analytics KQL queries to work without `parse_json()` on every line. The switch from string format to JSON is the single highest-ROI change in this strategy.

### Opinionated Defaults

- Default log level: INFO
- Log at entry and exit of every HTTP request
- Log at entry and exit of every LLM call
- Log at entry and exit of every tailoring phase
- Never log PII (email, full name) in log payloads — use UUIDs or hashed IDs

---

## Section 2: Tech Stack

### Instrumentation

**OpenTelemetry SDK** (Python + Next.js) for traces. OTel is the vendor-agnostic standard — it works with Application Insights, Grafana Tempo, Jaeger, and any other backend without code changes.

For metrics: `prometheus_client` Python library directly. Simpler than OTel metrics for this scale, widely understood, and natively supported by Azure Managed Prometheus.

For logs: **`structlog`** — the closest thing to an industry standard for structured logging in Python. Configured with `structlog.stdlib.ProcessorFormatter` so both native structlog loggers and existing stdlib `logging.getLogger()` loggers emit JSON through the same pipeline. `structlog.contextvars` handles correlation ID propagation automatically — no per-callsite plumbing.

### Logs

**stdout → Log Analytics Workspace** (already wired). Switching to JSON format makes existing Log Analytics infrastructure immediately useful for structured queries. No new infra required for Layer 1.

### Traces

**OpenTelemetry → Application Insights** (Azure native). Application Insights is generous on the free tier (5 GB/month ingestion), auto-correlates with Log Analytics via Operation ID, and has a good end-to-end transaction view. Provision via Terraform (`azurerm_application_insights`).

### Metrics

**Prometheus → Azure Managed Grafana**.

Two options:
- **Production**: Azure Monitor managed Prometheus scrapes backend `/metrics`; Azure Managed Grafana queries it alongside Log Analytics
- **Local dev**: `docker-compose` Prometheus + Grafana sidecar, same scrape config

These complement each other: Log Analytics handles log-derived queries (rates, errors by text pattern); Prometheus handles time-series metrics (histograms, gauges, counters).

### Visualization

**Azure Managed Grafana** as the single pane of glass. Data sources:
- Log Analytics (KQL)
- Azure Monitor managed Prometheus (PromQL)
- Application Insights (via Azure Monitor data source)
- PostgreSQL (direct, read-only, for TailoringDebugLog queries)

Grafana is preferred over Azure Monitor Workbooks: better UX, multi-source querying, dashboard-as-code (JSON provisioning), and team familiarity.

### Alerting

**Azure Monitor Alert Rules** (Terraform-managed). Two types:
- `azurerm_monitor_metric_alert` — for container/infra metrics
- `azurerm_monitor_scheduled_query_rules_alert` — for log-based conditions (KQL)

---

## Section 3: Logging Conventions

### Structured JSON Format

Switch backend from string format to JSON using `structlog`. Configure with `ProcessorFormatter` so stdlib loggers also emit JSON through the same pipeline.

Every log line is a JSON object with these mandatory fields:

```json
{
  "timestamp": "2026-05-13T14:23:01.234Z",
  "level": "INFO",
  "logger": "app.api.tailorings",
  "message": "Tailoring generation complete",
  "correlation_id": "a3f7c2e1-9b4d-4f8a-bc12-3e7a5f9d2c08",
  "tailoring_id": "7f3a2b1c-...",
  "user_id": "d9e4f2a1-...",
  "event": "generation_complete"
}
```

Optional contextual fields (include when relevant):
- `phase` — tailoring pipeline phase name
- `duration_ms` — elapsed time for the logged operation
- `model` — LLM model name
- `prompt_type` — LLM call category
- `input_tokens`, `output_tokens` — LLM token counts
- `finish_reason` — LLM finish reason
- `attempt` — retry attempt number
- `status_code` — HTTP response status
- `method`, `path` — HTTP request metadata
- `error` — error type/class name
- `error_message` — error description (no stack traces at INFO/WARN)

Frontend JSON fields should use the same names. Field name parity means KQL queries work the same way across both log streams.

### What to Log and Where

| Layer | What | Level |
|-------|------|-------|
| Request entry | method, path, correlation_id | INFO |
| Request exit | status_code, duration_ms | INFO |
| LLM call | model, prompt_type, input_tokens, output_tokens, latency_ms, finish_reason | INFO |
| LLM retry | attempt, prompt_type, reason | WARN |
| LLM failure | prompt_type, all attempts exhausted | ERROR |
| Phase start | tailoring_id, phase, correlation_id | INFO |
| Phase complete | tailoring_id, phase, duration_ms | INFO |
| Phase error | tailoring_id, phase, error, error_message | ERROR |
| Background task start | task_name, tailoring_id, correlation_id | INFO |
| Rate limit hit | user_id, count, limit | WARN |
| Slow DB query | query_label, duration_ms (threshold: 500ms) | WARN |
| Experience processing | user_id, status, duration_ms | INFO |

### Log Levels Policy

- **DEBUG**: LLM prompt/response content, full request/response payloads. Never enabled in prod. Useful locally when debugging extraction quality.
- **INFO**: Normal operation events, timing, counts. The default level in all environments.
- **WARN**: Rate limits hit, LLM retries, non-fatal degradation, slow queries, quota approaching.
- **ERROR**: Failures that affect user outcome, unhandled exceptions, background task failures.

### Log Volume Estimate

Current Log Analytics quota: 0.5 GB/day. At typical usage:
- ~50 tailoring generations/day × ~30 log lines/generation × ~500 bytes/line = ~0.75 MB/day for tailoring pipeline
- HTTP request logging at ~100 req/day × 2 lines × 300 bytes = ~60 KB/day
- LLM call logging at ~500 calls/day × 300 bytes = ~150 KB/day

Total well under quota. Alert at 80% (400 MB/day) regardless.

---

## Section 4: Correlation IDs

### Design

- **Format**: UUID4 (e.g., `a3f7c2e1-9b4d-4f8a-bc12-3e7a5f9d2c08`)
- **Header name**: `X-Correlation-Id`
- **Source of truth**: FastAPI middleware generates a new UUID if the header is absent; accepts and forwards if present

### Flow

```
Browser
  → Next.js API route: generate correlation_id, set X-Correlation-Id header, log it
  → FastAPI middleware: read or generate correlation_id, set ContextVar
  → Every log record: formatter reads ContextVar, injects correlation_id
  → Background task (_finalize_tailoring): receives correlation_id as param, re-sets ContextVar at entry
  → Response: X-Correlation-Id echoed back in response headers
```

The response header echo means correlation_id is visible in browser DevTools Network tab — essential for support and debugging.

### Python Propagation

```python
# backend/app/middleware/correlation.py
import uuid
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        correlation_id = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
        correlation_id_var.set(correlation_id)
        response = await call_next(request)
        response.headers["X-Correlation-Id"] = correlation_id
        return response
```

```python
# backend/app/logging.py — JSON formatter
class CorrelationIdFilter(logging.Filter):
    def filter(self, record):
        record.correlation_id = correlation_id_var.get("")
        return True
```

### Background Task Propagation

Background tasks run outside the request context — the ContextVar is not automatically inherited. Pass correlation_id explicitly:

```python
# In tailorings.py
background_tasks.add_task(
    _finalize_tailoring,
    tailoring_id=tailoring.id,
    correlation_id=correlation_id_var.get(""),
    ...
)

# In _finalize_tailoring()
async def _finalize_tailoring(tailoring_id, correlation_id, ...):
    correlation_id_var.set(correlation_id)
    ...
```

### Tailoring-Specific Correlation

`tailoring_id` and `correlation_id` serve different purposes:
- `correlation_id` — HTTP-level: traces one request/response cycle
- `tailoring_id` — business-level: traces the full lifecycle of one tailoring (may span multiple HTTP requests for polling, regeneration, etc.)

Both appear in all relevant log lines. For debugging a specific tailoring, filter by `tailoring_id`. For debugging a specific request, filter by `correlation_id`.

### Frontend

In `proxy.ts`:

```typescript
import { v4 as uuidv4 } from 'uuid';

// proxyToBackendWithUser and proxyToBackend both:
const correlationId = req.headers.get('x-correlation-id') ?? uuidv4();
// Forward to backend, log it, echo in response headers
```

---

## Section 5: Metrics Conventions

### HTTP Layer

| Metric | Type | Labels |
|--------|------|--------|
| `http_requests_total` | Counter | `method`, `endpoint`, `status_code` |
| `http_request_duration_ms` | Histogram | `method`, `endpoint`, `status_code` |

Derived: request rate, error rate (5xx %), p50/p95/p99 latency per endpoint.

Histogram buckets for `http_request_duration_ms`: `[50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000]` ms. The upper buckets matter because SSE streams run for 30–120 seconds.

### LLM Layer

| Metric | Type | Labels |
|--------|------|--------|
| `llm_call_duration_ms` | Histogram | `model`, `prompt_type` |
| `llm_tokens_total` | Counter | `model`, `prompt_type`, `direction` (`input`/`output`) |
| `llm_errors_total` | Counter | `model`, `prompt_type`, `error_type` |
| `llm_retries_total` | Counter | `model`, `prompt_type` |

`prompt_type` values: `job_extraction`, `chunk_matching`, `tailoring`, `gap_analysis`, `profile_extraction`

`error_type` values: `refusal`, `truncation`, `validation`, `timeout`, `rate_limit`

### Tailoring Pipeline

| Metric | Type | Labels |
|--------|------|--------|
| `tailoring_generations_total` | Counter | `status` (`success`/`error`), `matching_mode` |
| `tailoring_generation_duration_ms` | Histogram | `matching_mode` |
| `tailoring_active_generations` | Gauge | — |
| `tailoring_phase_duration_ms` | Histogram | `phase` |
| `chunk_batch_duration_ms` | Histogram | `mode` (`llm`/`vector`) |
| `chunk_errors_total` | Counter | — |

`phase` values: `extract_job`, `enrich_chunks`, `generate_tailoring`, `gap_analysis`

### Experience Processing

| Metric | Type | Labels |
|--------|------|--------|
| `experience_processing_total` | Counter | `status` (`success`/`error`) |
| `experience_processing_duration_ms` | Histogram | `status` |

### System

CPU, memory, container restarts come from Azure Monitor Container Apps metrics (automatic, no instrumentation needed). DB connection pool utilization via SQLAlchemy event hooks if needed.

### How to Emit

Use `prometheus_client` Python library:

```python
from prometheus_client import Counter, Histogram, Gauge, make_asgi_app

llm_call_duration = Histogram(
    "llm_call_duration_ms",
    "LLM call duration in milliseconds",
    ["model", "prompt_type"],
    buckets=[100, 500, 1000, 2000, 5000, 10000, 30000],
)

# Expose /metrics endpoint (mount in main.py, internal only)
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
```

The `/metrics` endpoint must not be publicly accessible. In production, configure Azure Managed Prometheus to scrape it on the internal Container App ingress. In local dev, expose it to `localhost` only.

### Frontend Metrics

Web Vitals (LCP, FID, CLS) via Next.js built-in `instrumentation.ts` with OTel SDK. API route latency: log it; derive P50/P95 from logs in Grafana rather than emitting dedicated metrics. The log volume is low enough that log-derived metrics are practical.

---

## Section 6: Distributed Tracing

Tracing is valuable for this architecture because a single user action (create tailoring) results in:
- One HTTP POST to Next.js
- One HTTP POST proxy to FastAPI
- One FastAPI handler that returns quickly
- One long-running background task (30–120s) that makes 10–50 LLM calls

Without tracing, correlating these is manual. With tracing, the Application Insights end-to-end transaction view shows the full causal chain.

### Approach

1. Add `opentelemetry-sdk` + `opentelemetry-instrumentation-fastapi` + `opentelemetry-instrumentation-sqlalchemy`
2. Add `azure-monitor-opentelemetry-exporter` — exports traces to Application Insights
3. Add Next.js `instrumentation.ts` with OTel SDK + Application Insights exporter

### Key Spans

Auto-instrumented (no code changes):
- FastAPI request spans
- SQLAlchemy query spans

Manual spans:
- `_finalize_tailoring()` root span (background task — must be started manually, not auto-instrumented)
- Per-phase spans: `extract_job`, `enrich_chunks`, `generate_tailoring`, `gap_analysis`
- Per-LLM-call spans in `llm_utils.py`

### Span Attributes

```python
span.set_attribute("tailoring.id", str(tailoring_id))
span.set_attribute("tailoring.matching_mode", matching_mode)
span.set_attribute("tailoring.phase", phase_name)
span.set_attribute("llm.model", model)
span.set_attribute("llm.prompt_type", prompt_type)
span.set_attribute("llm.input_tokens", input_tokens)
span.set_attribute("llm.output_tokens", output_tokens)
span.set_attribute("llm.latency_ms", latency_ms)
span.set_attribute("user.id", str(user_id))  # UUID only, no PII
```

### Infrastructure

Provision `azurerm_application_insights` in `infra/providers/azure/monitoring.tf`. Connect it to the existing Log Analytics Workspace (`workspace_id`). Application Insights and Log Analytics share the same workspace, enabling cross-query between traces and logs.

---

## Section 7: TailoringDebugLog — Full Population

The `TailoringDebugLog` table is already scaffolded and is the right place for structured per-tailoring telemetry that doesn't fit in the primary `Tailoring` row. Currently only `generation_complete` is written (and even that write fails silently). This table should become the source of truth for "what happened with tailoring X?" — queryable from the admin panel and mineable for eval corpus building.

### Events to Write

| event_type | When | Payload fields |
|------------|------|----------------|
| `generation_started` | `_finalize_tailoring()` entry | `correlation_id`, `matching_mode`, `profile_snapshot_hash` |
| `phase_complete` | After each phase finishes | `phase`, `duration_ms`, `ok: true` |
| `phase_error` | On phase failure | `phase`, `error_type`, `error_message` |
| `llm_call` | After each LLM call | `prompt_type`, `model`, `input_tokens`, `output_tokens`, `latency_ms`, `finish_reason`, `attempt` |
| `chunk_batch_complete` | After each scoring batch | `batch_index`, `chunk_count`, `scores_distribution`, `duration_ms` |
| `generation_complete` | Final success | `total_duration_ms`, `phase_durations` (map), `total_llm_calls`, `total_tokens` |
| `generation_error` | Final failure | `phase`, `error_message` |

### Write Pattern

Writes must be non-fatal. A failure to write a debug log must never surface to the user or affect the tailoring result:

```python
async def _write_debug_log(db, tailoring_id, event_type, payload):
    try:
        log = TailoringDebugLog(
            tailoring_id=tailoring_id,
            event_type=event_type,
            payload=payload,
            created_at=datetime.utcnow(),
        )
        db.add(log)
        await db.commit()
    except Exception:
        logger.warning("Failed to write TailoringDebugLog", extra={
            "tailoring_id": str(tailoring_id),
            "event_type": event_type,
        })
```

### Admin Panel Integration

The per-tailoring debug view (Dashboard 4, below) queries this table via Grafana's PostgreSQL data source. For admin panel use, a lightweight API endpoint (`GET /admin/tailorings/{id}/debug-log`) can return the rows as JSON.

---

## Section 8: Dashboards

All dashboards are provisioned in Azure Managed Grafana as JSON definition files, stored in `infra/providers/azure/grafana/dashboards/`.

### Dashboard 1: Platform Health

**Purpose**: Is the system up and working?
**Data sources**: Log Analytics + Azure Monitor (Container Apps metrics)
**Refresh**: 30s

Panels:
- **Request rate** — RPS over time (HTTP requests total / 60s, by endpoint)
- **HTTP error rate** — 5xx and 4xx as % of total requests over time
- **P50/P95/P99 request latency** — histogram quantiles by endpoint
- **Active tailoring generations** — gauge (`tailoring_active_generations`)
- **Container CPU utilization** — frontend + backend side by side
- **Container memory utilization** — frontend + backend
- **Container restart count** — alert threshold line overlay
- **Log Analytics ingestion** — daily GB ingested vs 0.5 GB quota

### Dashboard 2: LLM Observability

**Purpose**: How are LLM calls performing and what do they cost?
**Data sources**: Prometheus (metrics) + Log Analytics (structured logs)
**Refresh**: 1m

Panels:
- **LLM call rate** — calls/minute by `prompt_type`
- **P50/P95/P99 latency** — histogram quantiles per `prompt_type`
- **Token consumption** — input vs output tokens over time, by `prompt_type`
- **Estimated token cost** — configurable $/1k tokens dashboard variable, computed from `llm_tokens_total`
- **Error rate** — `llm_errors_total` by `error_type` over time
- **Retry rate** — `llm_retries_total` by `prompt_type`
- **Model distribution** — pie chart of calls by `model` label

### Dashboard 3: Tailoring Pipeline

**Purpose**: How are tailorings performing end-to-end?
**Data sources**: Prometheus + Log Analytics
**Refresh**: 1m

Panels:
- **Tailorings created** — per hour and per day
- **Success rate** — `ready` vs `error` status over time
- **Generation duration distribution** — histogram of `tailoring_generation_duration_ms`
- **Phase duration breakdown** — stacked bar: `extract_job`, `enrich_chunks`, `generate_tailoring`, `gap_analysis` average durations
- **Matching mode distribution** — `llm` vs `vector` pie chart
- **Chunk error rate** — `chunk_errors_total` over time
- **Gap analysis completion rate** — % of tailorings with gap analysis complete
- **Rate limit events** — frequency over time, by user bucket

### Dashboard 4: Per-Tailoring Debug View

**Purpose**: Answer "what happened with tailoring X?"
**Data sources**: Log Analytics (KQL) + PostgreSQL (TailoringDebugLog)
**Access**: Drilldown from Dashboard 3 (link with `tailoring_id` variable), or direct URL

Dashboard variable: `tailoring_id` (text input)

Panels:
- **Event timeline** — all log lines for this `tailoring_id`, ordered by time (Logs panel, KQL)
- **Phase Gantt** — start/end times of each phase, derived from `phase_complete` events in TailoringDebugLog (Bar chart with per-phase bars)
- **LLM calls table** — all `llm_call` events: prompt_type, model, tokens, latency_ms, attempt count (Table panel, PostgreSQL)
- **Chunk scoring summary** — score distribution histogram, error count per batch (from `chunk_batch_complete` events)
- **Error panel** — `phase_error` and `generation_error` events with full payload (Table panel)
- **Correlation ID** — display for copy-paste into Log Analytics Explore

### Dashboard 5: User Activity (Admin)

**Purpose**: Usage patterns — admin-facing only
**Data sources**: PostgreSQL (read-only) + Log Analytics
**Refresh**: 5m

Panels:
- **Tailorings created per day** — time series from `tailorings` table
- **Active users** — unique `user_id` values with tailoring activity per week
- **Experience uploads over time** — from `experiences` table `uploaded_at`
- **Rate limit events per user** — from `LlmTriggerLog`, by user UUID bucket (no names/emails displayed in panels)

---

## Section 9: Alerting

All alert rules defined in Terraform. Notification channels: email (immediate for P1/P2), Slack webhook (optional for P2/P3 to reduce noise).

### Alert Rules

| Alert | Condition | Severity | Window |
|-------|-----------|----------|--------|
| Backend error rate | HTTP 5xx > 5% of requests | P1 | 5 min |
| Health check failure | `GET /health` non-200 | P1 | 2 min |
| LLM timeout spike | `llm_errors_total{error_type="timeout"}` > 10 | P2 | 5 min |
| Generation failure spike | `tailoring_generations_total{status="error"}` > 5 | P2 | 10 min |
| P95 latency degradation | P95 non-SSE request latency > 10s | P2 | 5 min |
| Log Analytics quota | Daily ingestion > 80% of 0.5 GB (400 MB) | P3 | 1 hour |
| Container memory pressure | Memory > 90% for 5 min | P2 | 5 min |
| Container restart | Any container restart event | P2 | immediate |

### Terraform Resources

```hcl
# infra/providers/azure/monitoring.tf

resource "azurerm_monitor_metric_alert" "backend_container_restart" {
  name                = "tailord-backend-container-restart"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_container_app.backend.id]
  description         = "Alert when backend container restarts"
  severity            = 2

  criteria {
    metric_namespace = "Microsoft.App/containerApps"
    metric_name      = "RestartCount"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = 0
  }

  action {
    action_group_id = azurerm_monitor_action_group.notify.id
  }
}

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "backend_error_rate" {
  name                = "tailord-backend-error-rate"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  evaluation_frequency = "PT5M"
  window_duration      = "PT5M"
  scopes               = [azurerm_log_analytics_workspace.main.id]
  severity             = 1

  criteria {
    query = <<-QUERY
      ContainerAppConsoleLogs_CL
      | extend log = parse_json(Log_s)
      | where log.status_code >= 500
      | summarize errors = count() by bin(TimeGenerated, 5m)
      | where errors > 10
    QUERY
    time_aggregation_method = "Count"
    threshold               = 0
    operator                = "GreaterThan"
  }
}
```

---

## Section 10: Querying Logs (KQL Reference)

Log Analytics uses KQL. With structured JSON logs, fields are queryable after `parse_json()`. Once the backend switches to JSON format and Log Analytics is parsing the JSON field, these queries work as-is.

### Common Queries

```kql
// All logs for a specific tailoring (most common debugging query)
ContainerAppConsoleLogs_CL
| where TimeGenerated > ago(24h)
| extend log = parse_json(Log_s)
| where log.tailoring_id == "TAILORING_ID_HERE"
| project TimeGenerated, level=log.level, event=log.event, message=log.message,
          phase=log.phase, duration_ms=log.duration_ms
| order by TimeGenerated asc

// All logs for a correlation ID (single HTTP request trace)
ContainerAppConsoleLogs_CL
| extend log = parse_json(Log_s)
| where log.correlation_id == "CORRELATION_ID_HERE"
| project TimeGenerated, level=log.level, logger=log.logger, message=log.message
| order by TimeGenerated asc

// Error rate over time
ContainerAppConsoleLogs_CL
| extend log = parse_json(Log_s)
| where log.level == "ERROR"
| summarize errors = count() by bin(TimeGenerated, 5m)
| render timechart

// LLM call latency distribution by prompt type
ContainerAppConsoleLogs_CL
| extend log = parse_json(Log_s)
| where log.event == "llm_call_complete"
| extend prompt_type = tostring(log.prompt_type), latency_ms = toint(log.latency_ms)
| summarize percentiles(latency_ms, 50, 95, 99) by prompt_type
| order by percentile_latency_ms_95 desc

// Token consumption over time
ContainerAppConsoleLogs_CL
| extend log = parse_json(Log_s)
| where log.event == "llm_call_complete"
| extend total_tokens = toint(log.output_tokens) + toint(log.input_tokens)
| summarize total = sum(total_tokens) by bin(TimeGenerated, 1h)
| render timechart

// LLM retries (identify problematic prompt types)
ContainerAppConsoleLogs_CL
| extend log = parse_json(Log_s)
| where log.level == "WARN" and log.event == "llm_retry"
| summarize retry_count = count() by tostring(log.prompt_type), bin(TimeGenerated, 1h)
| order by retry_count desc

// Tailoring phase duration summary (last 24h)
ContainerAppConsoleLogs_CL
| where TimeGenerated > ago(24h)
| extend log = parse_json(Log_s)
| where log.event == "phase_complete"
| extend phase = tostring(log.phase), duration_ms = toint(log.duration_ms)
| summarize avg_ms = avg(duration_ms), p95_ms = percentile(duration_ms, 95),
            count = count() by phase
| order by avg_ms desc

// Rate limit hits
ContainerAppConsoleLogs_CL
| extend log = parse_json(Log_s)
| where log.event == "rate_limit_hit"
| summarize hits = count() by tostring(log.user_id), bin(TimeGenerated, 1h)
| order by hits desc
```

### Grafana + Log Analytics

Azure Managed Grafana supports Log Analytics as a built-in data source. Use the Explore panel to iterate on KQL queries, then pin panels to dashboards. The Logs panel type displays raw log lines with the KQL result; the Time series panel accepts `| render timechart` equivalents.

---

## Section 11: Implementation Layers

### Layer 1: Foundations (Highest Value, No New Infrastructure)

These changes require no new Azure resources, no new dependencies, and deliver immediate value against the existing Log Analytics Workspace.

1. Rewrite `backend/app/logging.py` — custom `JsonFormatter` (stdlib only) reads `correlation_id_var` ContextVar and injects it into every record
3. Create `backend/app/middleware/correlation.py` — `CorrelationIdMiddleware` (generate/accept `X-Correlation-Id`, set ContextVar, echo in response)
4. Register middleware in `backend/app/main.py` (before other middleware)
5. Add request/response logging middleware in `main.py` — log entry and exit for every request
6. Update `llm_utils.py` — add `event="llm_call_complete"` structured field, retry `event="llm_retry"` field
7. Update `_finalize_tailoring()` in `tailorings.py` — accept `correlation_id` param, set ContextVar at task entry, log phase start/complete/error with `event` field
8. Fully populate `TailoringDebugLog` — implement `_write_debug_log()` helper, emit all 7 event types
9. Update `frontend/src/lib/proxy.ts` — generate/forward `X-Correlation-Id`, log it
10. Standardize `frontend/src/lib/logger.ts` field names to match backend (`correlation_id`, `tailoring_id`, `event`, etc.)

**Verification**: Start backend locally, make a request, parse stdout as JSON — every line must be valid JSON with `correlation_id`. Create a tailoring, query `TailoringDebugLog` — all 7 event types present.

### Layer 2: Metrics

Requires Prometheus infrastructure (local: Docker sidecar; production: Azure Managed Prometheus).

1. Add `prometheus_client` to `backend/pyproject.toml`
2. Define metric objects in `backend/app/metrics.py` (all counters, histograms, gauges)
3. Instrument HTTP layer — add metric emissions to request/response middleware
4. Instrument LLM calls — add metric emissions in `llm_utils.py` alongside existing logging
5. Instrument tailoring pipeline phases — emit `tailoring_phase_duration_ms` and `tailoring_active_generations`
6. Expose `/metrics` endpoint in `main.py` (mount `make_asgi_app()`, internal only)
7. Add Prometheus + Grafana to `backend/docker-compose.yml` for local dev
8. Provision Azure Managed Prometheus + Azure Managed Grafana in `infra/providers/azure/monitoring.tf`
9. Configure Prometheus scrape target for backend `/metrics`
10. Build Platform Health dashboard (JSON, stored in `infra/providers/azure/grafana/dashboards/`)
11. Build LLM Observability dashboard

**Verification**: Hit `/metrics` — Prometheus format output with correct metric names and labels. In Grafana: LLM dashboard shows data after creating a tailoring.

### Layer 3: Dashboards and Alerting

Builds on Layer 1 (logs) and Layer 2 (metrics). Build and validate locally first, then port JSON to Azure.

**Local LGTM stack first:**
1. Extend `docker-compose.yml` with Loki + Promtail (log aggregation) and Tempo (traces)
2. Add Grafana provisioning config — datasources + dashboard JSON loaded at startup, no manual UI config
3. Build all dashboards locally against the LGTM stack (Prometheus, Loki, Tempo, PostgreSQL)

**Dashboards (5):**
4. Platform Health — request rate, error rate, P95 latency, active generations, container metrics
5. LLM Observability — call rate, token consumption, cost estimate, error/retry rates
6. Tailoring Pipeline — generation rate, success/error breakdown, phase duration stacked bar
7. Per-Tailoring Debug — log timeline, phase Gantt, LLM calls table (PostgreSQL → TailoringDebugLog)
8. User Activity (admin) — tailorings per day, active users, uploads (PostgreSQL direct)

**Alerting (Azure Monitor native — no Grafana Standard tier needed):**
9. `azurerm_monitor_action_group` with email notification
10. Define all 8 alert rules in Terraform (see Section 9)
11. Test each alert by triggering the condition manually in staging

### Layer 4: Distributed Tracing

Optional. Highest implementation complexity but provides the best end-to-end visibility for the background task flow.

1. Add `opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-sqlalchemy`, `azure-monitor-opentelemetry-exporter` to `backend/pyproject.toml`
2. Initialize OTel in `main.py` — configure FastAPI auto-instrumentation, SQLAlchemy auto-instrumentation
3. Add manual span instrumentation in `_finalize_tailoring()` — root span + per-phase child spans
4. Add LLM call spans in `llm_utils.py`
5. Provision `azurerm_application_insights` in Terraform, connect to existing Log Analytics Workspace
6. Add `instrumentation.ts` to Next.js frontend with OTel SDK + Application Insights exporter
7. Verify end-to-end trace in Application Insights transaction view — Next.js → FastAPI → background task → LLM calls visible as one trace

---

## Critical Files to Modify

| File | Change |
|------|--------|
| `backend/app/logging.py` | `structlog` configuration — `ProcessorFormatter` for stdlib + native loggers, `merge_contextvars` for automatic correlation_id injection |
| `backend/app/main.py` | Register `CorrelationIdMiddleware`, request/response logging middleware, `/metrics` mount |
| `backend/app/middleware/correlation.py` | New — `CorrelationIdMiddleware`, `correlation_id_var` ContextVar |
| `backend/app/metrics.py` | New — all Prometheus metric objects |
| `backend/app/core/llm_utils.py` | Add `event` structured field, Prometheus emissions |
| `backend/app/api/tailorings.py` | Pass correlation_id to background task, per-phase TailoringDebugLog writes |
| `backend/app/services/chunk_matcher.py` | Emit `chunk_batch_complete` TailoringDebugLog events |
| `backend/pyproject.toml` | Add `prometheus_client` (Layer 2) |
| `frontend/src/lib/proxy.ts` | Generate/forward `X-Correlation-Id`, log it |
| `frontend/src/lib/logger.ts` | Standardize field names to match backend |
| `infra/providers/azure/monitoring.tf` | Add Application Insights, Managed Grafana, Managed Prometheus, alert rules |
| `backend/docker-compose.yml` | Add Prometheus + Grafana services for local dev |
| `infra/providers/azure/grafana/dashboards/` | New directory — dashboard JSON definitions |

---

## Verification Checklist

- [ ] Start backend locally, make a request, verify every stdout line is valid JSON with `correlation_id`
- [ ] Create a tailoring end-to-end, query `TailoringDebugLog` — all 7 event types present in order
- [ ] Filter local logs by `correlation_id` — all relevant lines (request entry, LLM calls, phases) appear
- [ ] Filter local logs by `tailoring_id` — all pipeline phases visible with durations
- [ ] Hit `/metrics` — Prometheus text format output, correct metric names and labels present
- [ ] Grafana (after Terraform apply): Log Analytics data source connects, KQL query returns results
- [ ] LLM dashboard: create one tailoring, verify `llm_call_duration_ms` histogram populates
- [ ] Tailoring Pipeline dashboard: `tailoring_generations_total` increments on generation
- [ ] Per-Tailoring Debug view: enter a tailoring_id, phase Gantt and LLM table populate
- [ ] Trigger health check failure — P1 alert fires within window
- [ ] Frontend: create a tailoring, inspect Network tab — `X-Correlation-Id` header present on API response

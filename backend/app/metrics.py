from opentelemetry import metrics as otel_metrics

from app.config import settings

# Meter is retrieved from the global MeterProvider.
# setup_telemetry() in telemetry.py must be called before this module is imported
# so that the real provider (PrometheusMetricReader for local, OTLP for prod) is set.
_meter = otel_metrics.get_meter("tailord.backend", version="1.0")


class _BoundMetric:
    """Metric with pre-bound attributes (environment + any extra labels)."""

    def __init__(self, instrument, attrs: dict) -> None:
        self._instrument = instrument
        self._attrs = attrs

    def inc(self, amount=1) -> None:
        self._instrument.add(amount, self._attrs)

    def dec(self, amount=1) -> None:
        # Only valid for UpDownCounter instruments (Gauges); Counter instruments
        # must never be decremented per the OTel monotonic-counter invariant.
        self._instrument.add(-amount, self._attrs)

    def observe(self, amount) -> None:
        self._instrument.record(amount, self._attrs)


class _EnvMetric:
    """Wraps an OTel metric instrument to inject environment label automatically.

    Callsites are identical to the previous prometheus_client wrapper:
        METRIC.inc() / .dec() / .observe()
        METRIC.labels(method="GET", status_code=200).inc()
    """

    def __init__(self, instrument) -> None:
        self._instrument = instrument

    def _bound(self) -> _BoundMetric:
        return _BoundMetric(self._instrument, {"environment": settings.environment})

    def labels(self, **kwargs) -> _BoundMetric:
        return _BoundMetric(self._instrument, {"environment": settings.environment, **kwargs})

    def inc(self, amount=1) -> None:
        self._bound().inc(amount)

    def dec(self, amount=1) -> None:
        self._bound().dec(amount)

    def observe(self, amount) -> None:
        self._bound().observe(amount)


# --- HTTP ---
HTTP_REQUESTS_TOTAL = _EnvMetric(
    _meter.create_counter(
        "http_requests_total",
        description="Total HTTP requests",
    )
)
HTTP_REQUEST_DURATION_MS = _EnvMetric(
    _meter.create_histogram(
        "http_request_duration_ms",
        description="HTTP request duration in milliseconds",
        unit="ms",
    )
)

# --- LLM ---
LLM_CALL_DURATION_MS = _EnvMetric(
    _meter.create_histogram(
        "llm_call_duration_ms",
        description="LLM call duration in milliseconds",
        unit="ms",
    )
)
LLM_TOKENS_TOTAL = _EnvMetric(
    _meter.create_counter(
        "llm_tokens_total",
        description="LLM tokens consumed",
    )
)
LLM_ERRORS_TOTAL = _EnvMetric(
    _meter.create_counter(
        "llm_errors_total",
        description="LLM call failures",
    )
)
LLM_RETRIES_TOTAL = _EnvMetric(
    _meter.create_counter(
        "llm_retries_total",
        description="LLM retry attempts",
    )
)
LLM_CACHED_TOKENS_TOTAL = _EnvMetric(
    _meter.create_counter(
        "llm_cached_tokens_total",
        description="LLM prompt tokens served from cache",
    )
)

# --- Embeddings ---
EMBEDDING_CALL_DURATION_MS = _EnvMetric(
    _meter.create_histogram(
        "embedding_call_duration_ms",
        description="Embedding API call duration in milliseconds",
        unit="ms",
    )
)
EMBEDDING_TOKENS_TOTAL = _EnvMetric(
    _meter.create_counter(
        "embedding_tokens_total",
        description="Embedding tokens consumed",
    )
)

# --- Tailoring pipeline ---
TAILORING_GENERATIONS_TOTAL = _EnvMetric(
    _meter.create_counter(
        "tailoring_generations_total",
        description="Tailoring generation completions",
    )
)
TAILORING_ACTIVE_GENERATIONS = _EnvMetric(
    _meter.create_up_down_counter(
        "tailoring_active_generations",
        description="Currently running tailoring generation tasks",
    )
)
TAILORING_GENERATION_DURATION_MS = _EnvMetric(
    _meter.create_histogram(
        "tailoring_generation_duration_ms",
        description="Total tailoring generation duration in milliseconds",
        unit="ms",
    )
)
TAILORING_PHASE_DURATION_MS = _EnvMetric(
    _meter.create_histogram(
        "tailoring_phase_duration_ms",
        description="Duration of each tailoring pipeline phase in milliseconds",
        unit="ms",
    )
)

# --- Experience processing ---
EXPERIENCE_PROCESSING_TOTAL = _EnvMetric(
    _meter.create_counter(
        "experience_processing_total",
        description="Experience processing completions",
    )
)
EXPERIENCE_PROCESSING_DURATION_MS = _EnvMetric(
    _meter.create_histogram(
        "experience_processing_duration_ms",
        description="Experience processing duration in milliseconds",
        unit="ms",
    )
)

# --- Experience processing — phase-level ---
EXPERIENCE_PHASE_DURATION_MS = _EnvMetric(
    _meter.create_histogram(
        "experience_phase_duration_ms",
        description="Duration of each experience processing phase in milliseconds",
        unit="ms",
    )
)

# --- GitHub enrichment ---
GITHUB_ENRICHMENT_TOTAL = _EnvMetric(
    _meter.create_counter(
        "github_enrichment_total",
        description="GitHub enrichment completions",
    )
)
GITHUB_ENRICHMENT_DURATION_MS = _EnvMetric(
    _meter.create_histogram(
        "github_enrichment_duration_ms",
        description="Total GitHub enrichment duration in milliseconds",
        unit="ms",
    )
)

# --- Job scraping ---
JOB_SCRAPE_TOTAL = _EnvMetric(
    _meter.create_counter(
        "job_scrape_total",
        description="Job URL scrape attempts by method and outcome",
    )
)

# --- Gap response ---
GAP_RESPONSE_DURATION_MS = _EnvMetric(
    _meter.create_histogram(
        "gap_response_duration_ms",
        description="Gap response + re-scoring duration in milliseconds",
        unit="ms",
    )
)

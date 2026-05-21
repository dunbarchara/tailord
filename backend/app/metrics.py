from prometheus_client import Counter, Gauge, Histogram

from app.config import settings


class _EnvMetric:
    """Wraps a prometheus_client metric to inject a constant environment label.

    Callsites do not need to change — .labels(**kwargs) injects environment
    automatically, and bare .inc()/.dec()/.observe() calls are routed through
    the pre-bound label child.
    """

    def __init__(self, metric):
        self._m = metric

    def _bound(self):
        return self._m.labels(environment=settings.environment)

    def labels(self, **kwargs):
        return self._m.labels(environment=settings.environment, **kwargs)

    def inc(self, amount=1):
        self._bound().inc(amount)

    def dec(self, amount=1):
        self._bound().dec(amount)

    def observe(self, amount):
        self._bound().observe(amount)


# --- HTTP ---
HTTP_REQUESTS_TOTAL = _EnvMetric(
    Counter(
        "http_requests_total",
        "Total HTTP requests",
        ["environment", "method", "endpoint", "status_code"],
    )
)
HTTP_REQUEST_DURATION_MS = _EnvMetric(
    Histogram(
        "http_request_duration_ms",
        "HTTP request duration in milliseconds",
        ["environment", "method", "endpoint"],
        buckets=[10, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000],
    )
)

# --- LLM ---
LLM_CALL_DURATION_MS = _EnvMetric(
    Histogram(
        "llm_call_duration_ms",
        "LLM call duration in milliseconds",
        ["environment", "model", "prompt_type"],
        buckets=[100, 250, 500, 1000, 2000, 5000, 10000, 30000, 60000],
    )
)
LLM_TOKENS_TOTAL = _EnvMetric(
    Counter(
        "llm_tokens_total",
        "LLM tokens consumed",
        ["environment", "model", "prompt_type", "direction"],  # direction: input | output
    )
)
LLM_ERRORS_TOTAL = _EnvMetric(
    Counter(
        "llm_errors_total",
        "LLM call failures",
        [
            "environment",
            "model",
            "prompt_type",
            "error_type",
        ],  # error_type: validation | timeout | unknown
    )
)
LLM_RETRIES_TOTAL = _EnvMetric(
    Counter(
        "llm_retries_total",
        "LLM retry attempts",
        ["environment", "model", "prompt_type"],
    )
)

# --- Tailoring pipeline ---
TAILORING_GENERATIONS_TOTAL = _EnvMetric(
    Counter(
        "tailoring_generations_total",
        "Tailoring generation completions",
        ["environment", "status", "matching_mode"],  # status: success | error
    )
)
TAILORING_ACTIVE_GENERATIONS = _EnvMetric(
    Gauge(
        "tailoring_active_generations",
        "Currently running tailoring generation tasks",
        ["environment"],
    )
)
TAILORING_GENERATION_DURATION_MS = _EnvMetric(
    Histogram(
        "tailoring_generation_duration_ms",
        "Total tailoring generation duration in milliseconds",
        ["environment"],
        buckets=[1000, 5000, 10000, 30000, 60000, 120000, 300000],
    )
)
TAILORING_PHASE_DURATION_MS = _EnvMetric(
    Histogram(
        "tailoring_phase_duration_ms",
        "Duration of each tailoring pipeline phase in milliseconds",
        ["environment", "phase"],  # extract_job | enrich_chunks | generate_tailoring | gap_analysis
        buckets=[100, 500, 1000, 5000, 10000, 30000, 60000],
    )
)

# --- Experience processing ---
EXPERIENCE_PROCESSING_TOTAL = _EnvMetric(
    Counter(
        "experience_processing_total",
        "Experience processing completions",
        ["environment", "status"],  # success | error
    )
)
EXPERIENCE_PROCESSING_DURATION_MS = _EnvMetric(
    Histogram(
        "experience_processing_duration_ms",
        "Experience processing duration in milliseconds",
        ["environment"],
        buckets=[500, 1000, 5000, 10000, 30000, 60000],
    )
)

# --- Experience processing — phase-level ---
EXPERIENCE_PHASE_DURATION_MS = _EnvMetric(
    Histogram(
        "experience_phase_duration_ms",
        "Duration of each experience processing phase in milliseconds",
        ["environment", "phase"],  # extracting | analyzing | chunking
        buckets=[100, 500, 1000, 5000, 10000, 30000, 60000],
    )
)

# --- GitHub enrichment ---
GITHUB_ENRICHMENT_TOTAL = _EnvMetric(
    Counter(
        "github_enrichment_total",
        "GitHub enrichment completions",
        ["environment", "status"],  # success | error | partial
    )
)
GITHUB_ENRICHMENT_DURATION_MS = _EnvMetric(
    Histogram(
        "github_enrichment_duration_ms",
        "Total GitHub enrichment duration in milliseconds",
        ["environment"],
        buckets=[1000, 5000, 10000, 30000, 60000, 120000],
    )
)

# --- Gap response ---
GAP_RESPONSE_DURATION_MS = _EnvMetric(
    Histogram(
        "gap_response_duration_ms",
        "Gap response + re-scoring duration in milliseconds",
        ["environment"],
        buckets=[500, 1000, 2000, 5000, 10000],
    )
)

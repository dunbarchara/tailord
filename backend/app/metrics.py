from prometheus_client import Counter, Gauge, Histogram

# --- HTTP ---
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)
HTTP_REQUEST_DURATION_MS = Histogram(
    "http_request_duration_ms",
    "HTTP request duration in milliseconds",
    ["method", "endpoint"],
    buckets=[10, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000],
)

# --- LLM ---
LLM_CALL_DURATION_MS = Histogram(
    "llm_call_duration_ms",
    "LLM call duration in milliseconds",
    ["model", "prompt_type"],
    buckets=[100, 250, 500, 1000, 2000, 5000, 10000, 30000, 60000],
)
LLM_TOKENS_TOTAL = Counter(
    "llm_tokens_total",
    "LLM tokens consumed",
    ["model", "prompt_type", "direction"],  # direction: input | output
)
LLM_ERRORS_TOTAL = Counter(
    "llm_errors_total",
    "LLM call failures",
    ["model", "prompt_type", "error_type"],  # error_type: validation | timeout | unknown
)
LLM_RETRIES_TOTAL = Counter(
    "llm_retries_total",
    "LLM retry attempts",
    ["model", "prompt_type"],
)

# --- Tailoring pipeline ---
TAILORING_GENERATIONS_TOTAL = Counter(
    "tailoring_generations_total",
    "Tailoring generation completions",
    ["status", "matching_mode"],  # status: success | error
)
TAILORING_ACTIVE_GENERATIONS = Gauge(
    "tailoring_active_generations",
    "Currently running tailoring generation tasks",
)
TAILORING_GENERATION_DURATION_MS = Histogram(
    "tailoring_generation_duration_ms",
    "Total tailoring generation duration in milliseconds",
    buckets=[1000, 5000, 10000, 30000, 60000, 120000, 300000],
)
TAILORING_PHASE_DURATION_MS = Histogram(
    "tailoring_phase_duration_ms",
    "Duration of each tailoring pipeline phase in milliseconds",
    ["phase"],  # extract_job | enrich_chunks | generate_tailoring | gap_analysis
    buckets=[100, 500, 1000, 5000, 10000, 30000, 60000],
)

# --- Experience processing ---
EXPERIENCE_PROCESSING_TOTAL = Counter(
    "experience_processing_total",
    "Experience processing completions",
    ["status"],  # success | error
)
EXPERIENCE_PROCESSING_DURATION_MS = Histogram(
    "experience_processing_duration_ms",
    "Experience processing duration in milliseconds",
    buckets=[500, 1000, 5000, 10000, 30000, 60000],
)

# --- Experience processing — phase-level ---
EXPERIENCE_PHASE_DURATION_MS = Histogram(
    "experience_phase_duration_ms",
    "Duration of each experience processing phase in milliseconds",
    ["phase"],  # extracting | analyzing | chunking
    buckets=[100, 500, 1000, 5000, 10000, 30000, 60000],
)

# --- GitHub enrichment ---
GITHUB_ENRICHMENT_TOTAL = Counter(
    "github_enrichment_total",
    "GitHub enrichment completions",
    ["status"],  # success | error | partial
)
GITHUB_ENRICHMENT_DURATION_MS = Histogram(
    "github_enrichment_duration_ms",
    "Total GitHub enrichment duration in milliseconds",
    buckets=[1000, 5000, 10000, 30000, 60000, 120000],
)

# --- Gap response ---
GAP_RESPONSE_DURATION_MS = Histogram(
    "gap_response_duration_ms",
    "Gap response + re-scoring duration in milliseconds",
    buckets=[500, 1000, 2000, 5000, 10000],
)

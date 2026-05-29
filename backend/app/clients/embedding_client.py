"""
embedding_client.py — OpenAI-compatible embedding client.

Mirrors llm_client.py in structure:
  - No global state — new client constructed per call
  - get_embedding_client() exposed for testability / mocking
  - embed_text() is the primary call site

Configuration:
  EMBEDDING_MODEL    — model name (default: text-embedding-3-small)
  EMBEDDING_BASE_URL — override endpoint; falls back to LLM_BASE_URL if unset
  EMBEDDING_API_KEY  — API key for the embedding endpoint. Intentionally NOT
                       falling back to LLM_API_KEY — keeping these separate
                       ensures the LLM key is never sent to the embedding
                       endpoint or vice versa.

Local dev: set EMBEDDING_API_KEY to a personal OpenAI key (platform.openai.com).
Leave LLM_API_KEY unset — LM Studio does not need a real key. This way your
Azure Foundry / production key never leaves its intended endpoint.
"""

import time

import structlog
from openai import OpenAI

from app.config import settings, use_managed_identity

logger = structlog.get_logger(__name__)

EMBEDDING_TIMEOUT_SECONDS = 30


def get_embedding_client() -> OpenAI:
    """
    Returns an OpenAI-compatible client for embedding calls.

    Base URL resolution:
      1. EMBEDDING_BASE_URL explicitly set → use it
      2. EMBEDDING_API_KEY set, no EMBEDDING_BASE_URL → use None (OpenAI default)
         A separate key implies a separate endpoint; do NOT fall back to LLM_BASE_URL
         (which may point to LM Studio locally and would receive the wrong key).
      3. Neither set → fall back to LLM_BASE_URL (same Azure AI Foundry endpoint
         as the chat model; managed identity handles auth in staging/production).
    """
    if settings.embedding_base_url:
        base_url = settings.embedding_base_url
    elif settings.embedding_api_key:
        base_url = None  # separate key → OpenAI default endpoint
    else:
        base_url = settings.llm_base_url  # same endpoint as LLM (Azure AI Foundry)

    if use_managed_identity():
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider

        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(),
            "https://ai.azure.com/.default",
        )
        return OpenAI(
            api_key=token_provider,
            base_url=base_url,
            timeout=EMBEDDING_TIMEOUT_SECONDS,
        )

    return OpenAI(
        api_key=settings.embedding_api_key or "local-dev",
        base_url=base_url or None,
        timeout=EMBEDDING_TIMEOUT_SECONDS,
    )


def embed_text(text: str, embed_context: str = "embed") -> list[float]:
    """
    Embed a single string. Returns a list of floats.

    Raises ValueError on empty input.
    Raises on API failure — callers decide whether to suppress (embedding failures
    are non-fatal throughout the pipeline; callers log and continue).
    """
    text = text.strip()
    if not text:
        raise ValueError("Cannot embed empty text")

    client = get_embedding_client()
    start = time.perf_counter()
    response = client.embeddings.create(
        model=settings.embedding_model,
        input=text,
    )
    elapsed = time.perf_counter() - start
    latency_ms = int(elapsed * 1000)

    usage = response.usage
    input_tokens = usage.prompt_tokens
    total_tokens = usage.total_tokens

    from app.core.llm_pricing import compute_cost_usd

    logger.info(
        "embedding_call_complete",
        embed_context=embed_context,
        model=settings.embedding_model,
        input_tokens=input_tokens,
        total_tokens=total_tokens,
        cost_usd=compute_cost_usd(model=settings.embedding_model, input_tokens=input_tokens),
        latency_ms=latency_ms,
    )

    from app.metrics import EMBEDDING_CALL_DURATION_MS, EMBEDDING_TOKENS_TOTAL

    EMBEDDING_CALL_DURATION_MS.labels(
        model=settings.embedding_model, embed_context=embed_context
    ).observe(latency_ms)
    EMBEDDING_TOKENS_TOTAL.labels(model=settings.embedding_model, embed_context=embed_context).inc(
        input_tokens
    )

    from app.core.llm_call_logger import log_llm_call

    log_llm_call(
        call_type="embedding",
        model=settings.embedding_model,
        prompt_name=embed_context,
        input_tokens=input_tokens,
        latency_ms=latency_ms,
    )

    return response.data[0].embedding

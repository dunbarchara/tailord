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

import logging

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_TIMEOUT_SECONDS = 30


def _use_managed_identity() -> bool:
    """True in staging/production when no explicit API key is configured."""
    return settings.environment in ("staging", "production") and not settings.llm_api_key


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

    if _use_managed_identity():
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


def embed_text(text: str) -> list[float]:
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
    response = client.embeddings.create(
        model=settings.embedding_model,
        input=text,
    )
    return response.data[0].embedding

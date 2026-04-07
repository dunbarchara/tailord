import logging

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)

# Hard ceiling on any single LLM call. Background tasks run in a thread with no
# external cancellation mechanism, so without this they can hang indefinitely if
# the endpoint is slow or unreachable.
LLM_TIMEOUT_SECONDS = 120


def validate_llm_config() -> None:
    if not settings.llm_api_key and not settings.llm_base_url:
        raise RuntimeError(
            "LLM not configured: set LLM_API_KEY (for OpenAI or Azure AI Foundry) "
            "or LLM_BASE_URL (for a local endpoint)"
        )


def get_llm_client() -> OpenAI:
    """
    Returns an OpenAI-compatible client.
    Works with OpenAI, Azure AI Foundry, Ollama, LM Studio, etc.
    Set LLM_BASE_URL to point at any OpenAI-compatible endpoint.
    """
    logger.debug(
        "get_llm_client: base_url=%s model=%s api_version=%s timeout=%ss",
        settings.llm_base_url or "(openai default)",
        settings.llm_model,
        settings.llm_api_version or "(none)",
        LLM_TIMEOUT_SECONDS,
    )
    return OpenAI(
        api_key=settings.llm_api_key or "local-dev",
        base_url=settings.llm_base_url or None,
        timeout=LLM_TIMEOUT_SECONDS,
        default_query={"api-version": settings.llm_api_version} if settings.llm_api_version else {},
    )

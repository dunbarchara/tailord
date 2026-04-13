import logging

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)

# Hard ceiling on any single LLM call. Background tasks run in a thread with no
# external cancellation mechanism, so without this they can hang indefinitely if
# the endpoint is slow or unreachable.
LLM_TIMEOUT_SECONDS = 120


def _use_managed_identity() -> bool:
    """True in staging/production when no explicit API key is set.
    Local dev always uses the direct path (local model or OpenAI key).
    An explicit LLM_API_KEY always overrides managed identity regardless of environment."""
    return settings.environment in ("staging", "production") and not settings.llm_api_key


def validate_llm_config() -> None:
    if settings.environment in ("staging", "production"):
        if not settings.llm_base_url:
            raise RuntimeError(
                "LLM_BASE_URL must be set in staging and production (injected by Terraform)"
            )
    elif not settings.llm_api_key and not settings.llm_base_url:
        raise RuntimeError(
            "LLM not configured: set LLM_BASE_URL (for a local endpoint) "
            "or LLM_API_KEY (for OpenAI direct)"
        )


def get_llm_client() -> OpenAI:
    """
    Returns an OpenAI-compatible client. Three modes:

    1. Azure AI Foundry + Managed Identity (no API key):
       LLM_BASE_URL + LLM_API_VERSION set, LLM_API_KEY absent.
       Uses DefaultAzureCredential — token rotated automatically by the SDK.

    2. OpenAI / Azure AI Foundry with explicit key:
       LLM_API_KEY set. Standard OpenAI client with configurable base_url.

    3. Local model (Ollama, LM Studio, etc.):
       LLM_BASE_URL set to a local endpoint. LLM_API_KEY omitted or set to a
       placeholder. Uses the generic OpenAI client.
    """
    if _use_managed_identity():
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
        from openai import AzureOpenAI

        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(),
            "https://cognitiveservices.azure.com/.default",
        )
        logger.debug(
            "get_llm_client: Azure AI Foundry + Managed Identity base_url=%s model=%s api_version=%s timeout=%ss",
            settings.llm_base_url,
            settings.llm_model,
            settings.llm_api_version,
            LLM_TIMEOUT_SECONDS,
        )
        return AzureOpenAI(
            azure_endpoint=settings.llm_base_url,
            azure_ad_token_provider=token_provider,
            api_version=settings.llm_api_version or None,
            timeout=LLM_TIMEOUT_SECONDS,
        )

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

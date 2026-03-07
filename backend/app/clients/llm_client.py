from openai import OpenAI
from app.config import settings


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
    return OpenAI(
        api_key=settings.llm_api_key or "local-dev",
        base_url=settings.llm_base_url or None,
    )
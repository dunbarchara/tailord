from openai import OpenAI
from app.config import settings

def validate_llm_config() -> None:
    if settings.llm_provider == "openai":
        if not settings.llm_api_key:
            raise RuntimeError(
                "LLM_PROVIDER=openai requires LLM_API_KEY to be set"
            )

    elif settings.llm_provider == "local":
        if not settings.llm_base_url:
            raise RuntimeError(
                "LLM_PROVIDER=local requires LLM_BASE_URL to be set"
            )

    else:
        raise RuntimeError(
            f"Unknown LLM_PROVIDER: {settings.llm_provider}"
        )

def get_llm_client() -> OpenAI:
    """
    Returns an OpenAI-compatible client.
    Works for OpenAI, Ollama, LM Studio, LocalAI, etc.
    """
    return OpenAI(
        api_key=settings.llm_api_key or "local-dev",
        base_url=settings.llm_base_url,
    )
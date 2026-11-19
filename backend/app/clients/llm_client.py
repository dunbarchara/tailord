import threading
from dataclasses import dataclass

import structlog
from openai import OpenAI

from app.clients.llm_registry import (
    ModelSpec,
    Registry,
    get_registry,
    reset_registry,
    resolve_spec,
    validate_registry,
)
from app.config import settings
from app.core.llm_tasks import TaskName

logger = structlog.get_logger(__name__)

# Hard ceiling on any single LLM call. Background tasks run in a thread with no
# external cancellation mechanism, so without this they can hang indefinitely if
# the endpoint is slow or unreachable.
LLM_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class ResolvedLLM:
    """The client and model id to use for one task, plus the spec it came from."""

    client: OpenAI
    model: str
    spec: ModelSpec
    task: TaskName | None = None


def validate_llm_config() -> None:
    """Fail startup unless llm_models.json is present, valid, and fully routable."""
    if settings.llm_model_deprecated or settings.llm_api_version_deprecated:
        logger.warning(
            "llm_legacy_env_ignored",
            detail="LLM_MODEL / LLM_API_VERSION are no longer read; "
            "configure models and providers in llm_models.json",
        )
    errors, warnings = validate_registry(get_registry())
    for warning in warnings:
        logger.warning("llm_registry_warning", detail=warning)
    if errors:
        raise RuntimeError("Invalid LLM model configuration:\n  - " + "\n  - ".join(errors))


def _build_client(spec: ModelSpec) -> OpenAI:
    """
    Build an OpenAI-compatible client for a model spec. Three modes:

    1. Azure AI Foundry + Managed Identity (auth="managed_identity"):
       Uses DefaultAzureCredential with the ai.azure.com scope — no api_version needed.

    2. OpenAI / Azure AI Foundry with explicit key (auth="api_key"):
       Standard OpenAI client with configurable base_url.

    3. Local model (Ollama, LM Studio, etc.):
       base_url set to a local endpoint, API key omitted or a placeholder.
    """
    if spec.auth == "managed_identity":
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider

        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(),
            "https://ai.azure.com/.default",
        )
        logger.debug(
            "llm_client_built",
            mode="managed_identity",
            model_name=spec.name,
            base_url=spec.base_url,
            model=spec.model,
            timeout=LLM_TIMEOUT_SECONDS,
        )
        return OpenAI(
            api_key=token_provider,
            base_url=spec.base_url,
            timeout=LLM_TIMEOUT_SECONDS,
        )

    logger.debug(
        "llm_client_built",
        mode="api_key",
        model_name=spec.name,
        base_url=spec.base_url or "(openai default)",
        model=spec.model,
        api_version=spec.api_version or "(none)",
        timeout=LLM_TIMEOUT_SECONDS,
    )
    return OpenAI(
        api_key=spec.api_key or "local-dev",
        base_url=spec.base_url or None,
        timeout=LLM_TIMEOUT_SECONDS,
        default_query={"api-version": spec.api_version} if spec.api_version else {},
    )


# One client per distinct connection (adapter + endpoint + auth + key), shared across
# threads and across models served by the same provider. OpenAI clients are thread-safe
# and stateless per call (every request carries its full message list), and sharing one
# reuses the HTTP connection pool and, under managed identity, the cached bearer token.
# Keying on the connection (not the model name) also keeps per-user registries, if they
# are ever added, from colliding. Rotating a key requires a process restart.
_clients: dict[tuple, OpenAI] = {}
_clients_lock = threading.Lock()


def _client_for(spec: ModelSpec) -> OpenAI:
    key = spec.connection_key()
    client = _clients.get(key)
    if client is None:
        with _clients_lock:
            client = _clients.get(key)
            if client is None:
                client = _build_client(spec)
                _clients[key] = client
    return client


def resolve_llm(task: TaskName, registry: Registry | None = None) -> ResolvedLLM:
    """Resolve the client and model id for a task via llm_models.json."""
    spec = resolve_spec(task, registry)
    if spec.adapter != "openai_compat":
        # Only the OpenAI-compatible client exists in the app today. The eval harness
        # builds its own clients for other adapters (e.g. jev). Production integration of
        # a System One adapter is a later step and needs its own client here.
        raise NotImplementedError(
            f"task '{task}' is routed to model '{spec.name}' (adapter '{spec.adapter}'), "
            "which the app cannot call yet; only 'openai_compat' models are supported"
        )
    return ResolvedLLM(client=_client_for(spec), model=spec.model, spec=spec, task=task)


def reset_llm_caches() -> None:
    """Drop cached registry and clients (tests, or after changing settings)."""
    with _clients_lock:
        _clients.clear()
    reset_registry()

"""Model adapters for the eval harness.

An adapter maps a task item to one model call and normalizes the result. It holds no
transport logic: HTTP, auth and retries live in app/clients (the same clients the platform
uses), so the harness measures what production would run.
"""

from evals.adapters.base import Adapter


def adapter_for(model_name: str) -> Adapter:
    """The adapter for a registry model, chosen by its provider's adapter kind."""
    from app.clients.llm_registry import get_registry

    spec = get_registry().models.get(model_name)
    if spec is None:
        raise LookupError(f"model '{model_name}' is not in the registry")
    if spec.adapter == "jev":
        from evals.adapters.jev import JevAdapter

        return JevAdapter(model_name)
    if spec.adapter == "openai_compat":
        from evals.adapters.openai_compat import OpenAICompatAdapter

        return OpenAICompatAdapter(model_name)
    raise NotImplementedError(f"no eval adapter for '{spec.adapter}' (model '{model_name}')")

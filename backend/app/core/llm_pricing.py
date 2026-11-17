"""
LLM and embedding pricing constants (USD per 1M tokens).

Source: https://platform.openai.com/docs/pricing (last updated 2026-05-29)
Update this file when pricing changes. The same constants are mirrored as a SQL
CASE expression in observability/dashboards/generate.py — update both together.
"""

import threading

import structlog

logger = structlog.get_logger(__name__)

# USD per 1M tokens
PRICING: dict[str, dict[str, float]] = {
    "gpt-5.4-mini": {
        "input": 0.75,
        "cached": 0.08,
        "output": 4.50,
    },
    "gpt-5.4": {
        "input": 2.50,
        "cached": 0.25,
        "output": 15.00,
    },
    "text-embedding-3-small": {
        "input": 0.025,
        "cached": 0.0,
        "output": 0.0,
    },
}


# Per-model overrides supplied by the model registry (llm_models.json). Take precedence
# over PRICING so models not in the built-in catalog can still be priced.
_OVERRIDES: dict[str, dict[str, float]] = {}
_warned_unpriced: set[str] = set()
_warn_lock = threading.Lock()


def set_pricing_overrides(overrides: dict[str, dict[str, float]]) -> None:
    """Replace registry-supplied pricing overrides (keyed by model id)."""
    _OVERRIDES.clear()
    _OVERRIDES.update(overrides)
    with _warn_lock:
        _warned_unpriced.clear()


def get_pricing(model: str) -> dict[str, float] | None:
    """Pricing for a model id (registry override first, then built-in catalog), or None."""
    return _OVERRIDES.get(model) or PRICING.get(model)


def compute_cost_usd(
    *,
    model: str,
    input_tokens: int,
    cached_tokens: int = 0,
    output_tokens: int = 0,
) -> float | None:
    """
    Return estimated cost in USD, or None if no pricing is known for the model.

    Cached tokens are billed at the cheaper cached rate; the remainder at the full
    input rate. Output tokens are billed separately. Embeddings have no output cost.

    A missing price is logged once per model: real cost visibility is a product
    feature, so an unpriced model must never go unnoticed.
    """
    p = get_pricing(model)
    if p is None:
        with _warn_lock:
            first = model not in _warned_unpriced
            _warned_unpriced.add(model)
        if first:
            logger.warning("llm_pricing_missing", model=model)
        return None
    non_cached = max(0, input_tokens - cached_tokens)
    return (
        non_cached * p["input"] + cached_tokens * p["cached"] + output_tokens * p["output"]
    ) / 1_000_000

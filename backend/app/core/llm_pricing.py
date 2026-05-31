"""
LLM and embedding pricing constants (USD per 1M tokens).

Source: https://platform.openai.com/docs/pricing (last updated 2026-05-29)
Update this file when pricing changes. The same constants are mirrored as a SQL
CASE expression in observability/dashboards/generate.py — update both together.
"""

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


def compute_cost_usd(
    *,
    model: str,
    input_tokens: int,
    cached_tokens: int = 0,
    output_tokens: int = 0,
) -> float | None:
    """
    Return estimated cost in USD, or None if the model is not in the pricing table.

    Cached tokens are billed at the cheaper cached rate; the remainder at the full
    input rate. Output tokens are billed separately. Embeddings have no output cost.
    """
    p = PRICING.get(model)
    if p is None:
        return None
    non_cached = max(0, input_tokens - cached_tokens)
    return (
        non_cached * p["input"] + cached_tokens * p["cached"] + output_tokens * p["output"]
    ) / 1_000_000

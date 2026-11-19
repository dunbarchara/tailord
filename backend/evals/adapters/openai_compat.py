"""OpenAI-compatible adapter (Foundry GPT deployments, local servers): classification via
structured output.

Reuses the production call path: the shared client from llm_client.resolve_model and
llm_parse_with_retry, so structured-output mode, schema validation and self-correcting retries
are exactly what Tailord runs. Token and latency numbers come from the stats_sink hook on
that path, not a separate client.
"""

import time
from functools import lru_cache
from typing import Literal

import openai
import pydantic
from pydantic import BaseModel, create_model

from app.clients.llm_client import resolve_model
from app.core.llm_utils import (
    LLMCallStats,
    LLMRefusalError,
    LLMTruncationError,
    llm_parse_with_retry,
)
from evals.adapters.base import CallResult
from evals.tasks.base import ClassificationTask, EvalItem

TEMPERATURE = 0.0  # classification should not be creative; supports_temperature is honoured

# Errors that are an outcome to record for this item (and count against reliability), as
# opposed to bugs, which should surface.
_EXPECTED_ERRORS = (
    pydantic.ValidationError,
    ValueError,
    LLMRefusalError,
    LLMTruncationError,
    openai.APIError,
)


@lru_cache(maxsize=None)
def _response_model(labels: tuple[str, ...]) -> type[BaseModel]:
    """`{"label": <one of labels>}`, closed so structured-output modes can enforce it."""
    return create_model("Classification", label=(Literal[labels], ...))  # type: ignore[valid-type]


def system_prompt(task: ClassificationTask) -> str:
    categories = "\n".join(f"- {name}: {desc}" for name, desc in task.labels.items())
    return (
        f"{task.instructions}\n\nCategories:\n{categories}\n\n"
        'Respond with a JSON object: {"label": "<exactly one category name>"}. No other text.'
    )


class OpenAICompatAdapter:
    def __init__(self, model_name: str) -> None:
        """`model_name` is a registry name (e.g. "gpt-5.4-mini")."""
        resolved = resolve_model(model_name)
        if not isinstance(resolved.client, openai.OpenAI):
            raise TypeError(f"model '{model_name}' is not served by the openai_compat adapter")
        self.model = model_name
        self._client = resolved.client
        self._api_model = resolved.model

    def run(self, task: ClassificationTask, item: EvalItem) -> CallResult:
        messages = [
            {"role": "system", "content": system_prompt(task)},
            {"role": "user", "content": task.render_state(item.input)},
        ]
        sink: list[LLMCallStats] = []
        started = time.perf_counter()
        try:
            parsed = llm_parse_with_retry(
                self._client,
                self._api_model,
                messages,
                response_model=_response_model(tuple(task.labels)),
                temperature=TEMPERATURE,
                prompt_name=f"eval_{task.name}",
                stats_sink=sink,
            )
            error, prediction = None, parsed.label
        except _EXPECTED_ERRORS as exc:
            error, prediction = type(exc).__name__, None
            detail = {"msg": str(exc)[:300]}
        else:
            detail = {}
        return CallResult(
            prediction=prediction,
            tokens_in=sum(c.input_tokens for c in sink),
            tokens_out=sum(c.output_tokens for c in sink),
            latency_ms=int((time.perf_counter() - started) * 1000),
            attempts=max(len(sink), 1),
            error=error,
            detail=detail,
        )

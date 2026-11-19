"""Jev (System One) adapter: asks one `choice` question over the task's label set.

All HTTP, auth, retry and parsing logic is app.clients.jev_client, shared with the platform.
"""

import time

from app.clients.jev_client import JevClient, JevError, choice_question
from app.clients.llm_client import resolve_model
from evals.adapters.base import CallResult
from evals.tasks.base import ClassificationTask, EvalItem


class JevAdapter:
    def __init__(self, model_name: str, client: JevClient | None = None) -> None:
        """`model_name` is a registry name (e.g. "jev-1.14.0"). `client` is injectable for
        tests; by default the registry's shared JevClient for that model is used."""
        self.model = model_name
        if client is None:
            resolved = resolve_model(model_name)
            client, self._api_model = resolved.client, resolved.model
        else:
            self._api_model = model_name
        if not isinstance(client, JevClient):
            raise TypeError(f"model '{model_name}' is not served by the jev adapter")
        self._client = client

    def run(self, task: ClassificationTask, item: EvalItem) -> CallResult:
        questions = choice_question(task.instructions, task.labels)
        started = time.perf_counter()
        try:
            response = self._client.system_one(
                self._api_model, task.render_state(item.input), questions
            )
        except JevError as exc:
            return CallResult(
                error=type(exc).__name__,
                attempts=exc.attempts,
                latency_ms=int((time.perf_counter() - started) * 1000),
                detail={"msg": str(exc)},
            )
        wall_ms = int((time.perf_counter() - started) * 1000)
        answer = response.answers["q"]
        usage = {
            "tokens_in": response.usage.input_tokens,
            "tokens_out": response.usage.output_tokens,
            "latency_ms": wall_ms,
            "attempts": response.attempts,
        }
        if answer.choice not in task.labels:  # model answered outside the closed set
            return CallResult(error="InvalidLabel", detail={"choice": answer.choice}, **usage)
        return CallResult(
            prediction=answer.choice,
            confidence=answer.confidence,
            probabilities=answer.probabilities or None,
            detail={"answered_by": response.model},
            **usage,
        )

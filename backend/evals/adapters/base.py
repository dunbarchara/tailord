"""Common shapes every adapter returns, whatever the model or API behind it."""

from dataclasses import dataclass, field
from typing import Any, Protocol

from evals.tasks.base import ClassificationTask, EvalItem


@dataclass
class CallResult:
    """One model call on one item. Exactly one of `prediction` and `error` is set."""

    prediction: Any | None = None
    # Models that report calibrated probabilities (Jev) fill these; others leave them None.
    confidence: float | None = None
    probabilities: dict[str, float] | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0  # wall clock for the whole item, retries and backoff included
    attempts: int = 1  # >1 means the call was retried (rate limits, timeouts, schema retries)
    error: str | None = None  # short machine-readable reason, e.g. "JevRateLimitedError"
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None


class Adapter(Protocol):
    model: str  # registry name, e.g. "jev-1.14.0"

    def run(self, task: ClassificationTask, item: EvalItem) -> CallResult: ...

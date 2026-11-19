"""
jev_client.py — client for TypeSafe's System One API (Jev models).

The one place Tailord talks to the System One endpoint: the app resolves it through
llm_client.resolve_llm (adapter "jev"), and the eval harness uses the same client, so
auth, retries and response parsing exist exactly once.

System One takes a `state` plus named, typed questions and returns an answer per
question with calibrated probabilities. It generates no text. Two question types are
supported here, the ones classification and scoring need:

  choice  pick one of 1-255 named options        -> choice, confidence, probabilities
  score   rate on an ordered rubric of 1-10 levels -> score, confidence, probabilities, legend

API: POST {base_url}/v1/systemone with `Authorization: Bearer <key>`. 429 and 529 mean
back off and retry; Retry-After is not documented, so it is honoured only if present.
Output tokens are currently free, input tokens are billed.
"""

import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any, Literal

import httpx
import structlog
from pydantic import BaseModel, Field, ValidationError

logger = structlog.get_logger(__name__)

DEFAULT_BASE_URL = "https://api.typesafe.ai"
MAX_CHOICES = 255
MAX_SCORE_LEVELS = 10

# Transient: the server asked us to slow down, or had a bad moment. Everything else (400,
# 401, 413, 415, 422) is our request's fault and retrying cannot fix it.
RETRYABLE_STATUS = frozenset({429, 502, 503, 504, 529})


# ── Errors ────────────────────────────────────────────────────────────────────


class JevError(Exception):
    """Base class for everything this client raises."""

    attempts: int = 1


class JevHTTPError(JevError):
    def __init__(self, status_code: int, detail: Any, attempts: int = 1) -> None:
        super().__init__(f"Jev API returned {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail
        self.attempts = attempts


class JevRateLimitedError(JevHTTPError):
    """429 or 529 that did not clear within the retry budget."""


class JevConnectionError(JevError):
    """Timeout or network failure that persisted through the retry budget."""

    def __init__(self, message: str, attempts: int = 1) -> None:
        super().__init__(message)
        self.attempts = attempts


class JevResponseError(JevError):
    """The API answered 200 but the body was not what the request implies."""


# ── Questions ─────────────────────────────────────────────────────────────────


def choice_question(
    instructions: str, criteria: dict[str, str | None], *, question_id: str = "q"
) -> dict[str, dict]:
    """A choice question. `criteria` maps each option name to a description (None if the
    name alone is clear). Returns the `questions` mapping with a single entry."""
    if not 1 <= len(criteria) <= MAX_CHOICES:
        raise ValueError(f"choice questions take 1-{MAX_CHOICES} options, got {len(criteria)}")
    return {
        question_id: {"type": "choice", "instructions": instructions, "criteria": dict(criteria)}
    }


def score_question(
    instructions: str, levels: list[str], *, question_id: str = "q"
) -> dict[str, dict]:
    """A score question. Level i (0-based, by position) is the score i."""
    if not 1 <= len(levels) <= MAX_SCORE_LEVELS:
        raise ValueError(f"score questions take 1-{MAX_SCORE_LEVELS} levels, got {len(levels)}")
    return {question_id: {"type": "score", "instructions": instructions, "criteria": list(levels)}}


# ── Response ──────────────────────────────────────────────────────────────────


class ChoiceAnswer(BaseModel):
    type: Literal["choice"]
    choice: str
    confidence: float | None = None
    probabilities: dict[str, float] = {}


class ScoreAnswer(BaseModel):
    type: Literal["score"]
    score: float  # probability-weighted average of the levels, so it can fall between them
    confidence: float | None = None
    probabilities: dict[str, float] = {}
    legend: dict[str, str] = {}


Answer = Annotated[ChoiceAnswer | ScoreAnswer, Field(discriminator="type")]


class Usage(BaseModel):
    input_tokens: int
    output_tokens: int = 0


class _Body(BaseModel):
    model: str
    answers: dict[str, Answer]
    usage: Usage


@dataclass(frozen=True)
class JevResponse:
    model: str  # the version that answered (may differ from an alias that was requested)
    answers: dict[str, ChoiceAnswer | ScoreAnswer]
    usage: Usage
    latency_ms: int  # the successful attempt only
    attempts: int  # 1 = first try; more means retried 429s / timeouts


# ── Client ────────────────────────────────────────────────────────────────────


class JevClient:
    """Thread-safe: one instance can serve concurrent requests."""

    def __init__(
        self,
        api_key: str | None,
        base_url: str | None = None,
        *,
        timeout: float = 120.0,
        max_retries: int = 4,
        backoff_base: float = 1.0,
        backoff_cap: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        jitter: bool = True,
    ) -> None:
        if not api_key:
            raise ValueError("a Jev API key is required")
        self._http = httpx.Client(
            base_url=(base_url or DEFAULT_BASE_URL).rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
            transport=transport,
        )
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._backoff_cap = backoff_cap
        self._sleep = sleep
        self._jitter = jitter

    def close(self) -> None:
        self._http.close()

    def _delay(self, attempt: int, retry_after: str | None) -> float:
        if retry_after:
            try:
                return min(float(retry_after), self._backoff_cap)
            except ValueError:
                pass  # an HTTP-date form; fall through to exponential backoff
        delay = min(self._backoff_base * 2**attempt, self._backoff_cap)
        return delay * (1 + 0.25 * random.random()) if self._jitter else delay

    def system_one(
        self,
        model: str,
        state: str | dict | list,
        questions: dict[str, dict],
        *,
        long_context: bool = False,
    ) -> JevResponse:
        """Ask `questions` about `state`. Pin a versioned model id (e.g. jev-1.14.0); the
        jev-latest alias moves under you. Set long_context for requests above 32k tokens
        per question (the API requires an opt-in header)."""
        if not questions:
            raise ValueError("at least one question is required")
        headers = {"TypeSafe-Danger-Zone-Long-Context": "true"} if long_context else {}
        payload = {"model": model, "state": state, "questions": questions}

        attempts = 0
        while True:
            attempts += 1
            started = time.perf_counter()
            try:
                response = self._http.post("/v1/systemone", json=payload, headers=headers)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempts > self._max_retries:
                    raise JevConnectionError(
                        f"{type(exc).__name__} after {attempts} attempts", attempts
                    ) from exc
                self._wait(attempts, None, f"{type(exc).__name__}")
                continue

            if response.status_code == 200:
                latency_ms = int((time.perf_counter() - started) * 1000)
                return self._parse(response, questions, latency_ms, attempts)

            if response.status_code in RETRYABLE_STATUS and attempts <= self._max_retries:
                self._wait(attempts, response.headers.get("retry-after"), response.status_code)
                continue

            detail = _error_detail(response)
            error_class = (
                JevRateLimitedError if response.status_code in (429, 529) else JevHTTPError
            )
            raise error_class(response.status_code, detail, attempts)

    def _wait(self, attempts: int, retry_after: str | None, reason: Any) -> None:
        delay = self._delay(attempts - 1, retry_after)
        logger.warning("jev_retry", reason=reason, attempt=attempts, wait_s=round(delay, 2))
        self._sleep(delay)

    @staticmethod
    def _parse(
        response: httpx.Response, questions: dict[str, dict], latency_ms: int, attempts: int
    ) -> JevResponse:
        try:
            body = _Body.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise JevResponseError(f"unparseable System One response: {exc}") from exc
        if set(body.answers) != set(questions):
            raise JevResponseError(
                f"answers {sorted(body.answers)} do not match questions {sorted(questions)}"
            )
        for name, answer in body.answers.items():
            if answer.type != questions[name]["type"]:
                raise JevResponseError(
                    f"question '{name}' is {questions[name]['type']} but the answer is "
                    f"{answer.type}"
                )
        return JevResponse(
            model=body.model,
            answers=body.answers,
            usage=body.usage,
            latency_ms=latency_ms,
            attempts=attempts,
        )


def _error_detail(response: httpx.Response) -> Any:
    try:
        body = response.json()
    except ValueError:
        return response.text[:500]
    return body.get("detail", body) if isinstance(body, dict) else body

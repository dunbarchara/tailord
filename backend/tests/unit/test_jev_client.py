import json

import httpx
import pytest

from app.clients.jev_client import (
    ChoiceAnswer,
    JevClient,
    JevConnectionError,
    JevHTTPError,
    JevRateLimitedError,
    JevResponseError,
    ScoreAnswer,
    choice_question,
    score_question,
)

CHOICE_OK = {
    "model": "jev-1.14.0",
    "answers": {
        "q": {
            "type": "choice",
            "choice": "calm",
            "confidence": 0.7,
            "probabilities": {"angry": 0.15, "calm": 0.8, "excited": 0.05},
        }
    },
    "usage": {"input_tokens": 120, "output_tokens": 12},
}
SCORE_OK = {
    "model": "jev-1.14.0",
    "answers": {
        "q": {
            "type": "score",
            "score": 1.7,
            "confidence": 0.55,
            "legend": {"0": "Can wait", "1": "This week", "2": "Today"},
            "probabilities": {"0": 0.1, "1": 0.1, "2": 0.8},
        }
    },
    "usage": {"input_tokens": 80, "output_tokens": 5},
}
CHOICE_Q = choice_question("Tone?", {"angry": "upset", "calm": "neutral"})


def client(handler, **kwargs) -> tuple[JevClient, list[float]]:
    sleeps: list[float] = []
    c = JevClient(
        "ts-secret",
        "https://jev.invalid/",
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
        jitter=False,
        **kwargs,
    )
    return c, sleeps


def test_choice_request_shape_and_parsing():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=CHOICE_OK)

    c, _ = client(handler)
    result = c.system_one("jev-1.14.0", "I hate this", CHOICE_Q)
    assert seen["url"] == "https://jev.invalid/v1/systemone"
    assert seen["auth"] == "Bearer ts-secret"
    assert seen["body"] == {
        "model": "jev-1.14.0",
        "state": "I hate this",
        "questions": {
            "q": {
                "type": "choice",
                "instructions": "Tone?",
                "criteria": {"angry": "upset", "calm": "neutral"},
            }
        },
    }
    answer = result.answers["q"]
    assert isinstance(answer, ChoiceAnswer) and answer.choice == "calm"
    assert answer.probabilities["calm"] == 0.8
    assert result.usage.input_tokens == 120 and result.attempts == 1


def test_score_answer_parsing():
    c, _ = client(lambda r: httpx.Response(200, json=SCORE_OK))
    result = c.system_one("jev-1.14.0", "urgent!", score_question("Urgency?", ["a", "b", "c"]))
    answer = result.answers["q"]
    assert isinstance(answer, ScoreAnswer) and answer.score == 1.7
    assert answer.legend["2"] == "Today"


def test_long_context_header_only_when_requested():
    headers = []

    def handler(request):
        headers.append(request.headers.get("typesafe-danger-zone-long-context"))
        return httpx.Response(200, json=CHOICE_OK)

    c, _ = client(handler)
    c.system_one("m", "s", CHOICE_Q)
    c.system_one("m", "s", CHOICE_Q, long_context=True)
    assert headers == [None, "true"]


def test_429_is_retried_with_backoff_then_succeeds():
    calls = iter([429, 529, 200])

    def handler(request):
        status = next(calls)
        return httpx.Response(status, json=CHOICE_OK if status == 200 else {"detail": "slow down"})

    c, sleeps = client(handler)
    result = c.system_one("m", "s", CHOICE_Q)
    assert result.attempts == 3
    assert sleeps == [1.0, 2.0]  # exponential, no jitter in this test


def test_retry_after_header_is_honoured_and_capped():
    calls = iter([429, 429, 200])

    def handler(request):
        status = next(calls)
        headers = {"retry-after": "5"} if status == 429 and not seen else {"retry-after": "999"}
        seen.append(1)
        return httpx.Response(status, json=CHOICE_OK if status == 200 else {}, headers=headers)

    seen: list[int] = []
    c, sleeps = client(handler, backoff_cap=30.0)
    c.system_one("m", "s", CHOICE_Q)
    assert sleeps == [5.0, 30.0]


def test_rate_limit_exhaustion_raises_with_attempt_count():
    c, sleeps = client(lambda r: httpx.Response(429, json={"detail": "no"}), max_retries=2)
    with pytest.raises(JevRateLimitedError) as exc:
        c.system_one("m", "s", CHOICE_Q)
    assert exc.value.attempts == 3 and exc.value.status_code == 429 and len(sleeps) == 2


@pytest.mark.parametrize("status", [400, 401, 413, 422])
def test_client_errors_are_not_retried(status):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(status, json={"detail": "bad request"})

    c, sleeps = client(handler)
    with pytest.raises(JevHTTPError) as exc:
        c.system_one("m", "s", CHOICE_Q)
    assert len(calls) == 1 and not sleeps
    assert exc.value.status_code == status and exc.value.detail == "bad request"
    assert not isinstance(exc.value, JevRateLimitedError)


def test_timeouts_retry_then_raise_connection_error():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    c, sleeps = client(handler, max_retries=1)
    with pytest.raises(JevConnectionError) as exc:
        c.system_one("m", "s", CHOICE_Q)
    assert exc.value.attempts == 2 and len(sleeps) == 1


def test_mismatched_answers_are_rejected():
    wrong_name = {**CHOICE_OK, "answers": {"other": CHOICE_OK["answers"]["q"]}}
    wrong_type = {**CHOICE_OK, "answers": {"q": SCORE_OK["answers"]["q"]}}
    for body in (wrong_name, wrong_type, {"model": "m"}):
        c, _ = client(lambda r, b=body: httpx.Response(200, json=b))
        with pytest.raises(JevResponseError):
            c.system_one("m", "s", CHOICE_Q)


def test_question_builders_enforce_api_limits():
    with pytest.raises(ValueError):
        choice_question("x", {})
    with pytest.raises(ValueError):
        choice_question("x", {str(i): None for i in range(256)})
    with pytest.raises(ValueError):
        score_question("x", [])
    with pytest.raises(ValueError):
        score_question("x", [str(i) for i in range(11)])
    assert choice_question("x", {"a": None}, question_id="z")["z"]["criteria"] == {"a": None}


def test_key_is_required_and_never_in_repr():
    with pytest.raises(ValueError, match="API key"):
        JevClient(None)
    c, _ = client(lambda r: httpx.Response(200, json=CHOICE_OK))
    assert "ts-secret" not in repr(c)

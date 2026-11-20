import json

import httpx
import pytest

from app.clients.jev_client import JevClient
from evals.adapters.jev import JevAdapter
from evals.tasks import TASKS
from evals.tasks.base import EvalItem
from evals.tasks.semantic_type import SEMANTIC_TYPE, load_items, render_state

ITEM = EvalItem(
    id="gh-04:9",
    input={"chunk_type": "bullet", "section": "Requirements", "content": "3+ years of Python"},
    labels={"agreed": "job_requirement"},
)


def adapter(handler):
    sleeps = []
    client = JevClient(
        "k",
        "https://jev.invalid",
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
        jitter=False,
        max_retries=1,
    )
    return JevAdapter("jev-1.14.0", client=client), sleeps


def ok(choice="job_requirement", probs=None):
    probs = probs or {"job_requirement": 0.9, "role_description": 0.1}
    return httpx.Response(
        200,
        json={
            "model": "jev-1.14.0-20260917",
            "answers": {
                "q": {"type": "choice", "choice": choice, "confidence": 0.8, "probabilities": probs}
            },
            "usage": {"input_tokens": 150, "output_tokens": 9},
        },
    )


def test_task_registry_and_state_rendering():
    assert TASKS["semantic_type"] is SEMANTIC_TYPE
    assert set(SEMANTIC_TYPE.labels) == {
        "job_requirement",
        "role_description",
        "company_description",
        "compensation",
        "location",
        "application_info",
        "legal",
        "other",
    }
    assert render_state(ITEM.input) == (
        "Section: Requirements\nChunk type: bullet\nChunk: 3+ years of Python"
    )
    assert render_state({**ITEM.input, "section": None}).startswith("Section: (none)")


def test_items_load_with_every_label_source():
    items = load_items()
    assert len(items) == 478
    assert all(
        set(i.labels) == {"silver:sonnet-5-5", "silver:opus-5-5", "agreed", "adjudicated"}
        for i in items
    )
    assert all(i.labels["agreed"] in SEMANTIC_TYPE.labels for i in items)
    assert len({i.id for i in items}) == 478


def test_jev_adapter_sends_the_task_labels_and_normalizes_the_answer():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return ok()

    a, _ = adapter(handler)
    result = a.run(SEMANTIC_TYPE, ITEM)
    body = seen["body"]
    assert body["model"] == "jev-1.14.0" and body["state"] == render_state(ITEM.input)
    question = body["questions"]["q"]
    assert question["type"] == "choice" and question["criteria"] == SEMANTIC_TYPE.labels
    assert result.ok and result.prediction == "job_requirement"
    assert result.confidence == 0.8 and result.probabilities["job_requirement"] == 0.9
    assert (result.tokens_in, result.tokens_out, result.attempts) == (150, 9, 1)
    assert result.detail["answered_by"] == "jev-1.14.0-20260917"


def test_jev_adapter_reports_errors_instead_of_raising():
    a, sleeps = adapter(lambda r: httpx.Response(429, json={"detail": "slow"}))
    result = a.run(SEMANTIC_TYPE, ITEM)
    assert not result.ok and result.prediction is None
    assert result.error == "JevRateLimitedError" and result.attempts == 2 and len(sleeps) == 1

    a, _ = adapter(lambda r: httpx.Response(422, json={"detail": [{"msg": "bad"}]}))
    assert a.run(SEMANTIC_TYPE, ITEM).error == "JevHTTPError"


def test_answer_outside_the_label_set_is_an_error_not_a_prediction():
    a, _ = adapter(lambda r: ok(choice="spam", probs={"spam": 1.0}))
    result = a.run(SEMANTIC_TYPE, ITEM)
    assert result.error == "InvalidLabel" and result.prediction is None
    assert result.tokens_in == 150  # the call was still billed


def test_adapter_rejects_a_non_jev_model(monkeypatch):
    from app.clients import llm_client
    from app.clients.llm_registry import ModelSpec

    class Fake:
        client, model = object(), "gpt"
        spec = ModelSpec(name="gpt", provider="p", adapter="openai_compat", model="gpt")

    monkeypatch.setattr("evals.adapters.jev.resolve_model", lambda name: Fake())
    with pytest.raises(TypeError, match="not served by the jev adapter"):
        JevAdapter("gpt")
    assert llm_client  # imported for monkeypatch target clarity


# ── openai_compat adapter ─────────────────────────────────────────────────────


class _Usage:
    def __init__(self, pt, ct):
        self.prompt_tokens, self.completion_tokens, self.total_tokens = pt, ct, pt + ct
        self.prompt_tokens_details = None


class _FakeOpenAI:
    """Stands in for the OpenAI client; replies come from a script, one per call."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        from types import SimpleNamespace as NS

        self.calls.append(kwargs)
        content = self.replies.pop(0)
        return NS(
            choices=[NS(finish_reason="stop", message=NS(content=content))],
            usage=_Usage(200, 10),
        )


@pytest.fixture
def openai_adapter(monkeypatch):
    import openai

    from evals.adapters import openai_compat

    def make(replies):
        client = _FakeOpenAI(replies)
        client.__class__ = type("FakeOpenAI", (_FakeOpenAI, openai.OpenAI), {})
        from types import SimpleNamespace as NS

        monkeypatch.setattr(
            openai_compat, "resolve_model", lambda name: NS(client=client, model="deploy-x")
        )
        return openai_compat.OpenAICompatAdapter("gpt-test"), client

    return make


def test_openai_adapter_prompt_carries_the_task_definition(openai_adapter):
    adapter, client = openai_adapter(['{"label": "job_requirement"}'])
    result = adapter.run(SEMANTIC_TYPE, ITEM)
    call = client.calls[0]
    system = call["messages"][0]["content"]
    assert call["model"] == "deploy-x" and call["temperature"] == 0.0
    assert SEMANTIC_TYPE.instructions in system
    assert all(f"- {name}: {desc}" in system for name, desc in SEMANTIC_TYPE.labels.items())
    assert call["messages"][1]["content"] == render_state(ITEM.input)
    assert result.ok and result.prediction == "job_requirement"
    assert (result.tokens_in, result.tokens_out, result.attempts) == (200, 10, 1)
    assert result.confidence is None and result.probabilities is None


def test_openai_adapter_uses_production_self_correcting_retries(openai_adapter):
    adapter, client = openai_adapter(['{"label": "spam"}', '{"label": "legal"}'])
    result = adapter.run(SEMANTIC_TYPE, ITEM)
    assert result.ok and result.prediction == "legal"
    assert result.attempts == 2 and result.tokens_in == 400  # both attempts are billed
    assert "previous response was invalid" in client.calls[1]["messages"][-1]["content"]


def test_openai_adapter_records_persistent_invalid_output_as_error(openai_adapter):
    adapter, _ = openai_adapter(['{"label": "x"}', "not json", '{"label": "y"}'])
    result = adapter.run(SEMANTIC_TYPE, ITEM)
    assert not result.ok and result.prediction is None
    assert result.error == "ValidationError" and result.attempts == 3
    assert result.tokens_in == 600


def test_openai_adapter_rejects_non_openai_model(monkeypatch):
    from types import SimpleNamespace as NS

    from evals.adapters import openai_compat

    monkeypatch.setattr(openai_compat, "resolve_model", lambda n: NS(client=object(), model="m"))
    with pytest.raises(TypeError, match="not served by the openai_compat adapter"):
        openai_compat.OpenAICompatAdapter("jev-1.14.0")

from types import SimpleNamespace as NS

import pytest
from pydantic import BaseModel

from app.core.llm_utils import LLMCallStats, llm_parse, llm_parse_with_retry


class Out(BaseModel):
    label: str


def _usage(pt=100, ct=7, cached=0):
    return NS(
        prompt_tokens=pt,
        completion_tokens=ct,
        total_tokens=pt + ct,
        prompt_tokens_details=NS(cached_tokens=cached),
    )


class JsonObjectClient:
    """create() path (models without strict schema support)."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.chat = NS(completions=self)

    def create(self, **kwargs):
        return NS(
            choices=[NS(finish_reason="stop", message=NS(content=self.replies.pop(0)))],
            usage=_usage(cached=40),
        )


class SchemaClient:
    """beta.chat.completions.parse() path (gpt-4o and newer)."""

    def __init__(self):
        self.beta = NS(chat=NS(completions=self))

    def parse(self, **kwargs):
        msg = NS(refusal=None, parsed=Out(label="a"), content='{"label": "a"}')
        return NS(choices=[NS(finish_reason="stop", message=msg)], usage=_usage())


def test_sink_records_each_call_including_failed_validations():
    sink: list[LLMCallStats] = []
    client = JsonObjectClient(["not json", '{"label": "ok"}'])
    result = llm_parse_with_retry(
        client, "some-model", [], Out, 0.0, stats_sink=sink, max_retries=1
    )
    assert result.label == "ok"
    assert len(sink) == 2  # the invalid first reply was billed too
    assert sink[0].input_tokens == 100 and sink[0].output_tokens == 7
    assert sink[0].cached_tokens == 40 and sink[0].finish_reason == "stop"


def test_sink_records_the_schema_path_too():
    sink: list[LLMCallStats] = []
    assert llm_parse(SchemaClient(), "gpt-4o", [], Out, 0.0, stats_sink=sink).label == "a"
    assert [s.input_tokens for s in sink] == [100] and sink[0].cached_tokens == 0


def test_sink_is_optional():
    assert llm_parse(JsonObjectClient(['{"label": "x"}']), "m", [], Out, 0.0).label == "x"


def test_exhausted_retries_still_raise_and_keep_stats():
    sink: list[LLMCallStats] = []
    client = JsonObjectClient(["bad", "bad", "bad"])
    with pytest.raises(ValueError):
        llm_parse_with_retry(client, "m", [], Out, 0.0, stats_sink=sink, max_retries=2)
    assert len(sink) == 3

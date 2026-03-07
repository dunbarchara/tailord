import logging
import time
from typing import TypeVar, Type

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMRefusalError(Exception):
    """Raised when the LLM refuses to answer due to a safety or policy violation."""
    pass


def strip_json_fences(text: str) -> str:
    """Remove markdown code fences that small LLMs emit despite instructions."""
    text = text.strip()
    if text.startswith("```"):
        text = text[text.index("\n") + 1:]
    if text.endswith("```"):
        text = text[: text.rfind("```")]
    return text.strip()


def _format_messages(messages: list[dict]) -> str:
    parts = []
    for m in messages:
        role = m.get("role", "?").upper()
        content = m.get("content", "")
        parts.append(f"[{role}]\n{content}")
    return "\n\n".join(parts)


def llm_parse(
    client,
    model: str,
    messages: list[dict],
    response_model: Type[T],
    temperature: float,
) -> T:
    """
    Call the LLM and return a validated Pydantic object.

    Selects the calling method based on model capabilities (see model_config.py):
    - JSON_SCHEMA → .parse() for strict structured output (OpenAI gpt-4o+, Azure AI)
    - JSON_OBJECT → .create() with json_object mode + model_validate_json()
    - NONE        → .create() with no format param + strip_json_fences + model_validate_json()

    Raises LLMRefusalError if the model refuses to answer (JSON_SCHEMA mode only).
    Raises pydantic.ValidationError if the response cannot be parsed into response_model.

    Logging:
    - INFO:  model, schema, mode, token usage, finish reason, latency (always visible)
    - DEBUG: full request messages and full response content (set LOG_LEVEL=DEBUG to enable)
    """
    from app.core.model_config import get_json_mode, JsonMode

    mode = get_json_mode(model)

    logger.debug(
        "llm_parse request | model=%s mode=%s schema=%s temperature=%s\n\n%s",
        model, mode.value, response_model.__name__, temperature,
        _format_messages(messages),
    )

    start = time.perf_counter()

    if mode == JsonMode.JSON_SCHEMA:
        completion = client.beta.chat.completions.parse(
            model=model,
            messages=messages,
            temperature=temperature,
            response_format=response_model,
        )
        elapsed = time.perf_counter() - start
        message = completion.choices[0].message
        usage = completion.usage
        finish_reason = completion.choices[0].finish_reason

        if message.refusal:
            logger.warning(
                "llm_parse refusal | model=%s schema=%s latency=%.2fs reason=%s",
                model, response_model.__name__, elapsed, message.refusal,
            )
            raise LLMRefusalError(message.refusal)

        result = message.parsed
        raw_content = message.content

    else:
        kwargs: dict = dict(model=model, messages=messages, temperature=temperature)
        if mode == JsonMode.JSON_OBJECT:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        elapsed = time.perf_counter() - start
        usage = resp.usage
        finish_reason = resp.choices[0].finish_reason
        raw_content = resp.choices[0].message.content
        result = response_model.model_validate_json(strip_json_fences(raw_content))

    logger.info(
        "llm_parse | model=%s schema=%s mode=%s tokens=%d+%d=%d finish=%s latency=%.2fs",
        model, response_model.__name__, mode.value,
        usage.prompt_tokens, usage.completion_tokens, usage.total_tokens,
        finish_reason, elapsed,
    )
    logger.debug("llm_parse response | raw content:\n%s", raw_content)

    return result


def llm_generate(
    client,
    model: str,
    messages: list[dict],
    temperature: float,
    label: str = "generate",
) -> str:
    """
    Call the LLM for a plain text response (Markdown, prose, etc.) with
    the same INFO/DEBUG logging as llm_parse().

    Use this for tasks that return unstructured text rather than JSON.
    """
    logger.debug(
        "llm_generate request | model=%s label=%s temperature=%s\n\n%s",
        model, label, temperature,
        _format_messages(messages),
    )

    start = time.perf_counter()
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )
    elapsed = time.perf_counter() - start

    usage = resp.usage
    finish_reason = resp.choices[0].finish_reason
    content = resp.choices[0].message.content

    logger.info(
        "llm_generate | model=%s label=%s tokens=%d+%d=%d finish=%s latency=%.2fs",
        model, label,
        usage.prompt_tokens, usage.completion_tokens, usage.total_tokens,
        finish_reason, elapsed,
    )
    logger.debug("llm_generate response | content:\n%s", content)

    return content

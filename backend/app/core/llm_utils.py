import time
from collections.abc import Callable
from typing import Type, TypeVar

import structlog
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMRefusalError(Exception):
    """Raised when the LLM refuses to answer due to a safety or policy violation."""

    pass


class LLMTruncationError(Exception):
    """Raised when the LLM response was cut off mid-output (finish_reason == 'length')."""

    pass


def strip_json_fences(text: str) -> str:
    """Remove markdown code fences that small LLMs emit despite instructions."""
    text = text.strip()
    if text.startswith("```"):
        text = text[text.index("\n") + 1 :]
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
    from app.core.model_config import JsonMode, get_capabilities

    caps = get_capabilities(model)
    mode = caps.json_mode

    logger.debug(
        "llm_parse_request",
        model=model,
        mode=mode.value,
        schema=response_model.__name__,
        temperature=temperature if caps.supports_temperature else "n/a",
        messages=_format_messages(messages),
    )

    start = time.perf_counter()

    if mode == JsonMode.JSON_SCHEMA:
        parse_kwargs: dict = dict(model=model, messages=messages, response_format=response_model)
        if caps.supports_temperature:
            parse_kwargs["temperature"] = temperature
        completion = client.beta.chat.completions.parse(**parse_kwargs)
        elapsed = time.perf_counter() - start
        message = completion.choices[0].message
        usage = completion.usage
        finish_reason = completion.choices[0].finish_reason

        if message.refusal:
            logger.warning(
                "llm_refusal",
                model=model,
                schema=response_model.__name__,
                latency_ms=int(elapsed * 1000),
                reason=message.refusal,
            )
            raise LLMRefusalError(message.refusal)

        result = message.parsed
        raw_content = message.content

    else:
        kwargs: dict = dict(model=model, messages=messages)
        if caps.supports_temperature:
            kwargs["temperature"] = temperature
        if mode == JsonMode.JSON_OBJECT:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        elapsed = time.perf_counter() - start
        usage = resp.usage
        finish_reason = resp.choices[0].finish_reason
        raw_content = resp.choices[0].message.content
        result = response_model.model_validate_json(strip_json_fences(raw_content))

    logger.info(
        "llm_call_complete",
        model=model,
        schema=response_model.__name__,
        mode=mode.value,
        input_tokens=usage.prompt_tokens,
        output_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        finish_reason=finish_reason,
        latency_ms=int(elapsed * 1000),
    )
    logger.debug("llm_parse_response", raw_content=raw_content)

    if finish_reason == "length":
        raise LLMTruncationError(
            f"LLM response truncated (finish_reason=length) for schema={response_model.__name__}, model={model}"
        )

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
    from app.core.model_config import get_capabilities

    caps = get_capabilities(model)

    logger.debug(
        "llm_generate_request",
        model=model,
        label=label,
        temperature=temperature if caps.supports_temperature else "n/a",
        messages=_format_messages(messages),
    )

    start = time.perf_counter()
    gen_kwargs: dict = dict(model=model, messages=messages)
    if caps.supports_temperature:
        gen_kwargs["temperature"] = temperature
    resp = client.chat.completions.create(**gen_kwargs)
    elapsed = time.perf_counter() - start

    usage = resp.usage
    finish_reason = resp.choices[0].finish_reason
    content = resp.choices[0].message.content

    logger.info(
        "llm_call_complete",
        model=model,
        label=label,
        input_tokens=usage.prompt_tokens,
        output_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        finish_reason=finish_reason,
        latency_ms=int(elapsed * 1000),
    )
    logger.debug("llm_generate_response", content=content)

    if finish_reason == "length":
        raise LLMTruncationError(
            f"LLM response truncated (finish_reason=length) for label={label}, model={model}"
        )

    return content


def llm_parse_with_retry(
    client,
    model: str,
    messages: list[dict],
    response_model: Type[T],
    temperature: float,
    validate_fn: Callable[[T], None] | None = None,
    max_retries: int = 2,
) -> T:
    """
    Like llm_parse(), but retries up to max_retries times when validate_fn raises
    ValueError or when Pydantic validation fails.

    On each failure, the error message is appended as a user turn so the LLM can
    self-correct. After max_retries exhausted, the last exception is re-raised.
    """
    import pydantic

    current_messages = list(messages)
    last_exc: Exception = RuntimeError("llm_parse_with_retry: no attempts made")

    for attempt in range(max_retries + 1):
        try:
            result = llm_parse(client, model, current_messages, response_model, temperature)
            if validate_fn is not None:
                validate_fn(result)
            return result
        except (pydantic.ValidationError, ValueError) as exc:
            last_exc = exc
            if attempt < max_retries:
                logger.warning(
                    "llm_retry",
                    attempt=attempt + 1,
                    max_attempts=max_retries + 1,
                    schema=response_model.__name__,
                    error=str(exc),
                )
                current_messages = current_messages + [
                    {
                        "role": "user",
                        "content": (
                            f"Your previous response was invalid: {exc}. "
                            "Please correct it and respond again."
                        ),
                    }
                ]
            else:
                logger.error(
                    "llm_error",
                    attempts=max_retries + 1,
                    schema=response_model.__name__,
                    error=str(last_exc),
                )

    raise last_exc

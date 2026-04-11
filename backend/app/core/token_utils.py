import logging

logger = logging.getLogger(__name__)

_CHARS_PER_TOKEN = 4  # conservative fallback estimate


def truncate_to_tokens(text: str, max_tokens: int, model: str = "gpt-4o") -> str:
    """
    Truncate text to at most max_tokens tokens using tiktoken.

    Falls back to a character-based estimate if tiktoken cannot load the
    encoding for the given model (e.g. local models with non-standard names).
    """
    try:
        import tiktoken

        try:
            enc = tiktoken.encoding_for_model(model)
        except KeyError:
            # o200k_base is the encoding for gpt-4o and all subsequent models.
            # Fall back to it when tiktoken doesn't recognise the model name
            # (e.g. newer releases or local model aliases).
            enc = tiktoken.get_encoding("o200k_base")

        tokens = enc.encode(text)
        if len(tokens) <= max_tokens:
            return text

        logger.warning(
            "truncate_to_tokens: %d tokens exceeds limit of %d — truncating (model=%s)",
            len(tokens),
            max_tokens,
            model,
        )
        return enc.decode(tokens[:max_tokens])

    except Exception:
        logger.warning("truncate_to_tokens: tiktoken unavailable, using char-based estimate")
        char_limit = max_tokens * _CHARS_PER_TOKEN
        if len(text) <= char_limit:
            return text
        logger.warning(
            "truncate_to_tokens: %d chars exceeds char limit of %d — truncating",
            len(text),
            char_limit,
        )
        return text[:char_limit]

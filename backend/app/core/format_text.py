import re


def reduce_newlines_to_two(text: str) -> str:
    """Collapse any sequence of newline/carriage-return characters to exactly two newlines.

    Used after markdownify conversion, which can produce runs of 3+ blank lines
    that inflate the markdown passed to the LLM.
    """
    cleaned_text = re.sub(r"[\r\n]+", "\n\n", text)
    return cleaned_text

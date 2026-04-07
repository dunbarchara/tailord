"""Unit tests for notion_export.py pure string functions."""

from types import SimpleNamespace

import pytest

from app.services.notion_export import (
    _escape,
    _strip_formatting,
    _strip_links,
    chunks_to_notion_markdown,
)

# ---------------------------------------------------------------------------
# _escape
# ---------------------------------------------------------------------------


def test_escape_leaves_plain_text():
    assert _escape("Hello world") == "Hello world"


def test_escape_special_chars():
    assert _escape("a~b`c[d]e<f>g{h}i|j^k") == r"a\~b\`c\[d\]e\<f\>g\{h\}i\|j\^k"


def test_escape_preserves_bold():
    # * is NOT in the escape set — bold/italic must survive
    assert _escape("**bold** and *italic*") == "**bold** and *italic*"


def test_escape_backslash():
    assert _escape(r"a\b") == r"a\\b"


# ---------------------------------------------------------------------------
# _strip_links
# ---------------------------------------------------------------------------


def test_strip_links_inline():
    assert _strip_links("[click here](https://example.com)") == "click here"


def test_strip_links_image():
    assert _strip_links("![alt text](https://example.com/img.png)") == "alt text"


def test_strip_links_preserves_plain_text():
    assert _strip_links("no links here") == "no links here"


def test_strip_links_multiple():
    result = _strip_links("[a](url1) and [b](url2)")
    assert result == "a and b"


# ---------------------------------------------------------------------------
# _strip_formatting
# ---------------------------------------------------------------------------


def test_strip_formatting_bold():
    assert _strip_formatting("**Section Title**") == "Section Title"


def test_strip_formatting_italic():
    assert _strip_formatting("*italic*") == "italic"


def test_strip_formatting_plain():
    assert _strip_formatting("plain text") == "plain text"


def test_strip_formatting_strips_whitespace():
    assert _strip_formatting("  text  ") == "text"


# ---------------------------------------------------------------------------
# chunks_to_notion_markdown
# ---------------------------------------------------------------------------


def _chunk(**kwargs):
    defaults = {
        "chunk_type": "bullet",
        "content": "Some requirement",
        "section": "Requirements",
        "match_score": 1,
        "advocacy_blurb": None,
        "experience_source": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_gap_chunks_omitted():
    chunks = [_chunk(match_score=0)]
    result = chunks_to_notion_markdown(chunks)
    assert result == ""


def test_header_chunks_skipped():
    chunks = [_chunk(chunk_type="header", section=None)]
    result = chunks_to_notion_markdown(chunks)
    assert result == ""


def test_no_section_skipped():
    chunks = [_chunk(section=None)]
    result = chunks_to_notion_markdown(chunks)
    assert result == ""


def test_strong_match_green_toggle():
    chunks = [_chunk(match_score=2, content="Led team of 5")]
    result = chunks_to_notion_markdown(chunks)
    assert '<details color="green_bg">' in result
    assert "<summary>Led team of 5</summary>" in result


def test_partial_match_yellow_toggle():
    chunks = [_chunk(match_score=1, content="Used Python")]
    result = chunks_to_notion_markdown(chunks)
    assert '<details color="yellow_bg">' in result


def test_na_chunk_bullet_plain():
    chunks = [_chunk(match_score=-1, chunk_type="bullet", content="Some skill")]
    result = chunks_to_notion_markdown(chunks)
    assert "- Some skill" in result
    assert "<details" not in result


def test_na_chunk_none_score_paragraph():
    chunks = [_chunk(match_score=None, chunk_type="paragraph", content="Intro text")]
    result = chunks_to_notion_markdown(chunks)
    assert "Intro text" in result
    assert "<details" not in result


def test_section_header_emitted():
    chunks = [_chunk(section="Requirements")]
    result = chunks_to_notion_markdown(chunks)
    assert "## Requirements" in result


def test_advocacy_blurb_in_callout():
    chunks = [
        _chunk(
            match_score=2,
            advocacy_blurb="Strong match because of X",
            experience_source="resume",
        )
    ]
    result = chunks_to_notion_markdown(chunks)
    assert "Strong match because of X" in result
    assert "Source: Resume" in result
    assert '<callout color="gray_bg">' in result


def test_section_change_adds_blank_line():
    chunks = [
        _chunk(section="Section A"),
        _chunk(section="Section B"),
    ]
    result = chunks_to_notion_markdown(chunks)
    assert "## Section A" in result
    assert "## Section B" in result
    # Blank line between sections
    assert "\n\n## Section B" in result


def test_content_links_stripped_in_toggle():
    chunks = [_chunk(match_score=2, content="[React](https://react.dev) experience")]
    result = chunks_to_notion_markdown(chunks)
    assert "<summary>React experience</summary>" in result


@pytest.mark.parametrize(
    "source,expected_label",
    [
        ("resume", "Resume"),
        ("github", "GitHub"),
        ("user_input", "Additional context"),
        ("unknown_source", "unknown_source"),  # falls back to raw value
    ],
)
def test_source_labels(source, expected_label):
    chunks = [_chunk(match_score=1, advocacy_blurb="blurb", experience_source=source)]
    result = chunks_to_notion_markdown(chunks)
    assert f"Source: {expected_label}" in result

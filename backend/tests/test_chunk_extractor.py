import pytest

from app.services.chunk_extractor import extract_chunks, normalize_markdown


def test_empty_bullet_does_not_hang():
    """Empty bullet lines (marker with no content) must not cause an infinite loop."""
    result = extract_chunks("- \n* \n+ \nReal content here yes\n")
    # Should return (only) the paragraph; empty bullets are silently skipped
    assert len(result) == 1
    assert result[0].chunk_type == "paragraph"
    assert "Real content here yes" in result[0].content


def test_numbered_empty_bullet_does_not_hang():
    """Numbered list with no content must not hang."""
    result = extract_chunks("1. \n2. \nActual paragraph content here\n")
    assert len(result) == 1
    assert result[0].chunk_type == "paragraph"


def test_normal_bullets_still_work():
    result = extract_chunks("- First item\n- Second item\n")
    assert len(result) == 2
    assert all(c.chunk_type == "bullet" for c in result)
    assert result[0].content == "First item"
    assert result[1].content == "Second item"


def test_section_tracking():
    md = "## Requirements\n- Must have Python\n- Must have SQL\n"
    result = extract_chunks(md)
    header = result[0]
    bullets = result[1:]
    assert header.chunk_type == "header"
    assert header.content == "Requirements"
    assert all(c.section == "Requirements" for c in bullets)


def test_bold_header_long_falls_through_to_paragraph():
    """Bold text > 80 chars should become a paragraph, not cause a hang."""
    long_bold = "**" + "x" * 90 + "**"
    result = extract_chunks(long_bold + "\n")
    assert len(result) == 1
    assert result[0].chunk_type == "paragraph"


def test_short_content_skipped():
    result = extract_chunks("Short\n\nThis is a proper paragraph that is long enough.\n")
    assert len(result) == 1
    assert result[0].chunk_type == "paragraph"


def test_normalize_asterisk_bullets():
    """* and + bullets normalize to -."""
    result = extract_chunks("* First requirement\n+ Second requirement\n")
    assert len(result) == 2
    assert all(c.chunk_type == "bullet" for c in result)
    assert result[0].content == "First requirement"


def test_normalize_numbered_list():
    """Numbered lists normalize to bullets."""
    result = extract_chunks("1. First requirement\n2. Second requirement\n")
    assert len(result) == 2
    assert all(c.chunk_type == "bullet" for c in result)


def test_normalize_unicode_glyph_bullets():
    """Unicode glyph line starters normalize to bullets."""
    result = extract_chunks("▸ Lead design decisions\n▪ Collaborate with teams\n")
    assert len(result) == 2
    assert all(c.chunk_type == "bullet" for c in result)
    assert result[0].content == "Lead design decisions"


def test_normalize_hash_variants():
    """# and ### normalize to ## — both tracked as section headers."""
    result = extract_chunks("# Top Level\n- bullet one here\n### Deep Level\n- bullet two here\n")
    assert result[0].chunk_type == "header"
    assert result[0].content == "Top Level"
    assert result[2].chunk_type == "header"
    assert result[2].content == "Deep Level"
    assert result[1].section == "Top Level"
    assert result[3].section == "Deep Level"


def test_deep_markdown_headings_are_headers_not_paragraphs():
    """h4-h6 headings (common in ATS job content) must not leak through as paragraph chunks
    that the scoring LLM would then score."""
    md = (
        "## About the role\n\n#### **Responsibilities**\n- Build the API surface\n\n"
        "###### Nice to have\n- Experience with Kafka\n"
    )
    result = extract_chunks(md)
    headers = [c for c in result if c.chunk_type == "header"]
    assert [h.content for h in headers] == [
        "About the role",
        "**Responsibilities**",
        "Nice to have",
    ]
    assert not [c for c in result if c.chunk_type == "paragraph"]
    bullets = {c.content: c.section for c in result if c.chunk_type == "bullet"}
    assert bullets == {
        "Build the API surface": "**Responsibilities**",
        "Experience with Kafka": "Nice to have",
    }


@pytest.mark.parametrize(
    "line", ["#hashtag stays text here", "####### seven hashes is not a header", "#### "]
)
def test_non_headings_with_hashes_are_not_headers(line):
    result = extract_chunks(line + "\n")
    assert not [c for c in result if c.chunk_type == "header"]


def test_normalize_empty_bullets_become_blank():
    """normalize_markdown turns empty bullets into blank lines."""
    normalized = normalize_markdown("- \n* \n+ \n1. \n")
    assert normalized.strip() == ""


def test_normalize_preserves_indented_continuations():
    """Indented continuation lines (leading whitespace) are left untouched."""
    normalized = normalize_markdown("- First item\n  continuation here\n")
    assert "  continuation here" in normalized

import json

import pytest

from app.core.extract import extract_markdown_content
from app.services.chunk_extractor import extract_chunks
from evals.render_postings import (
    BOARD_TEMPLATES,
    POSTINGS_DIR,
    REQUIRED_META,
    TIERS,
    parse_source,
    render,
)

SOURCES = sorted((POSTINGS_DIR / "src").glob("*.md"))


def test_parse_source_sections_and_bullets():
    text = (
        "---\n"
        + "\n".join(
            f"{k}: {'greenhouse' if k == 'board' else 'big' if k == 'tier' else 'x'}"
            for k in REQUIRED_META
        )
        + "\n---\nIntro line.\n\n## Duties\n- a\n- b\nTail.\n"
    )
    p = parse_source(text.replace("id: x", "id: t"))
    assert p.sections[0] == (None, [("p", "Intro line.")])
    assert p.sections[1] == ("Duties", [("ul", ["a", "b"]), ("p", "Tail.")])


def test_parse_source_rejects_bad_front_matter():
    with pytest.raises(ValueError, match="front matter"):
        parse_source("no front matter")
    with pytest.raises(ValueError, match="unknown board"):
        parse_source("---\n" + "\n".join(f"{k}: nope" for k in REQUIRED_META) + "\n---\nx")


@pytest.mark.parametrize("src", SOURCES, ids=lambda p: p.stem)
def test_committed_html_matches_source_and_is_extractable(src):
    posting = parse_source(src.read_text(encoding="utf-8"))
    assert posting.meta["id"] == src.stem
    html = (POSTINGS_DIR / "html" / f"{src.stem}.html").read_text(encoding="utf-8")
    assert html == render(posting), "stale HTML: run `uv run python -m evals.render_postings`"
    assert "{{" not in html
    first_bullet = next(
        (v[0] for _, bs in posting.sections for k, v in bs if k == "ul"),
        posting.sections[0][1][0][1][:60],
    )
    markdown = extract_markdown_content(html)
    assert first_bullet.split(",")[0][:40] in markdown
    # lever-03 is deliberately one unbroken paragraph (few chunks)
    assert len(extract_chunks(markdown)) >= 5


def test_manifest_matches_sources_and_values_are_valid():
    rows = [json.loads(line) for line in (POSTINGS_DIR / "manifest.jsonl").read_text().splitlines()]
    assert [r["id"] for r in rows] == [p.stem for p in SOURCES]
    assert all(r["board"] in BOARD_TEMPLATES and r["tier"] in TIERS for r in rows)


def test_corpus_covers_every_board_and_tier():
    rows = [json.loads(line) for line in (POSTINGS_DIR / "manifest.jsonl").read_text().splitlines()]
    assert {r["board"] for r in rows} == set(BOARD_TEMPLATES)
    assert {r["tier"] for r in rows} == TIERS

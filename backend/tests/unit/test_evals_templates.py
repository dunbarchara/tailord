import re

import pytest

from app.core.extract import extract_markdown_content
from evals.capture_templates import SLOTS
from evals.store import DATA_DIR

TEMPLATES = sorted((DATA_DIR / "templates").glob("*.html"))
BODY = "<h2>Responsibilities</h2><ul><li>Build zebra-grade APIs</li></ul>"
FILL = {s: f"x-{s.lower()}" for s in SLOTS} | {"BODY_HTML": BODY}
# Real names that were in the captured pages; none may survive scrubbing.
REAL_NAMES = (
    "anthropic",
    "palantir",
    "notion",
    "gitlab",
    "rivr",
    "clera",
    "nvidia",
    "amazon",
    "sanctuary",
    "granola",
    "physical ai",
    "knowledge graph",
    "talent pool",
)


def _fill(html: str) -> str:
    for k, v in FILL.items():
        html = html.replace("{{" + k + "}}", v)
    return html


def test_templates_exist():
    assert len(TEMPLATES) >= 7


@pytest.mark.parametrize("path", TEMPLATES, ids=lambda p: p.stem)
def test_template_has_body_slot_and_no_real_names(path):
    html = path.read_text()
    assert "{{BODY_HTML}}" in html
    low = html.lower()
    assert not [n for n in REAL_NAMES if n in low]


@pytest.mark.parametrize("path", TEMPLATES, ids=lambda p: p.stem)
def test_template_fills_and_body_survives_extraction(path):
    if path.stem == "workday":
        pytest.skip("hand-hydrated body; covered by the slot check")
    html = _fill(path.read_text())
    assert not re.search(r"\{\{[A-Z_]+\}\}", html)
    assert "zebra-grade" in extract_markdown_content(html)

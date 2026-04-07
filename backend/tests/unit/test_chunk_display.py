"""Unit tests for chunk_display.is_display_ready."""

from types import SimpleNamespace

import pytest

from app.services.chunk_display import is_display_ready


def _chunk(**kwargs):
    defaults = {"chunk_type": "bullet", "content": "Some requirement", "section": "Requirements"}
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_normal_bullet_is_ready():
    assert is_display_ready(_chunk()) is True


def test_normal_paragraph_is_ready():
    assert is_display_ready(_chunk(chunk_type="paragraph")) is True


def test_header_not_ready():
    assert is_display_ready(_chunk(chunk_type="header", section=None)) is False


def test_no_section_not_ready():
    assert is_display_ready(_chunk(section=None)) is False


@pytest.mark.parametrize(
    "content",
    [
        "[Apply here](https://example.com/apply)",
        "![Company logo](https://example.com/logo.png)",
    ],
)
def test_bare_link_not_ready(content):
    assert is_display_ready(_chunk(content=content)) is False


@pytest.mark.parametrize(
    "content",
    [
        "See [our website](https://example.com) for details",  # link not the whole content
        "Some requirement with details",
        "- Bullet point item",
    ],
)
def test_non_noise_content_ready(content):
    assert is_display_ready(_chunk(content=content)) is True


def test_whitespace_padded_link_not_ready():
    # The pattern matches after .strip(), so surrounding whitespace shouldn't rescue it
    content = "  [Apply here](https://example.com)  "
    assert is_display_ready(_chunk(content=content)) is False

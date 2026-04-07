"""Unit tests for pure utility functions in tailorings.py."""

import re

import pytest
from fastapi import HTTPException

from app.api.tailorings import _generate_slug, _validate_profile

# ---------------------------------------------------------------------------
# _validate_profile
# ---------------------------------------------------------------------------


def test_validate_profile_empty_raises():
    with pytest.raises(HTTPException) as exc_info:
        _validate_profile({})
    assert exc_info.value.status_code == 422


def test_validate_profile_resume_no_content_raises():
    with pytest.raises(HTTPException):
        _validate_profile({"resume": {}})


def test_validate_profile_work_experience_passes():
    _validate_profile({"resume": {"work_experience": [{"title": "Engineer"}]}})


def test_validate_profile_summary_passes():
    _validate_profile({"resume": {"summary": "Experienced engineer"}})


def test_validate_profile_blank_summary_raises():
    with pytest.raises(HTTPException):
        _validate_profile({"resume": {"summary": "   "}})


def test_validate_profile_github_repos_passes():
    _validate_profile({"github_repos": [{"name": "my-repo"}]})


def test_validate_profile_github_empty_list_raises():
    with pytest.raises(HTTPException):
        _validate_profile({"github_repos": []})


# ---------------------------------------------------------------------------
# _generate_slug
# ---------------------------------------------------------------------------

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]{1,4}$")


def test_generate_slug_basic_format():
    result = _generate_slug("Acme Corp", "Software Engineer")
    assert result.startswith("acme-corp-software-engineer-")
    suffix = result[len("acme-corp-software-engineer-") :]
    assert len(suffix) == 4
    assert suffix.isalnum()


def test_generate_slug_no_company():
    result = _generate_slug(None, "Engineer")
    assert result.startswith("engineer-")


def test_generate_slug_no_title():
    result = _generate_slug("Acme", None)
    assert result.startswith("acme-")


def test_generate_slug_both_none():
    result = _generate_slug(None, None)
    assert len(result) == 4
    assert result.isalnum()


def test_generate_slug_truncates_to_20():
    result = _generate_slug("A" * 30, "B" * 30)
    parts = result.split("-")
    # First part is 20 a's, second is 20 b's, last is 4-char suffix
    assert parts[0] == "a" * 20
    assert parts[1] == "b" * 20
    assert len(parts[2]) == 4


def test_generate_slug_special_chars_stripped():
    result = _generate_slug("Acme & Co.", "Sr. Engineer!")
    # Special chars are stripped, only alnum/hyphens remain
    assert _SLUG_RE.match(result)
    assert "&" not in result
    assert "." not in result
    assert "!" not in result


def test_generate_slug_is_different_each_call():
    # Random suffix means two calls should (almost always) differ
    results = {_generate_slug("Acme", "Eng") for _ in range(10)}
    assert len(results) > 1

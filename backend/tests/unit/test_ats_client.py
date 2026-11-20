"""Unit tests for ATS URL parsing and API fetching in ats_client.py."""

from unittest.mock import MagicMock, patch

import pytest

from app.core.ats_client import (
    _greenhouse_to_markdown,
    _parse_greenhouse_url,
    _parse_lever_url,
    _unescape_if_escaped,
    try_ats_fetch,
)

# ---------------------------------------------------------------------------
# _parse_greenhouse_url
# ---------------------------------------------------------------------------


def test_greenhouse_gh_jid_and_board_params():
    """CoreWeave-style: company site with gh_jid + board query params."""
    url = "https://coreweave.com/careers/job?gh_jid=4577764006&board=coreweave"
    result = _parse_greenhouse_url(url)
    assert result == ("coreweave", "4577764006")


def test_greenhouse_boards_domain():
    url = "https://boards.greenhouse.io/acme/jobs/12345"
    result = _parse_greenhouse_url(url)
    assert result == ("acme", "12345")


def test_greenhouse_job_boards_domain():
    url = "https://job-boards.greenhouse.io/acme/jobs/12345"
    result = _parse_greenhouse_url(url)
    assert result == ("acme", "12345")


def test_greenhouse_gh_jid_without_board_returns_none():
    url = "https://example.com/jobs?gh_jid=123"
    result = _parse_greenhouse_url(url)
    assert result is None


def test_greenhouse_board_without_gh_jid_returns_none():
    url = "https://example.com/jobs?board=acme"
    result = _parse_greenhouse_url(url)
    assert result is None


def test_greenhouse_random_url_returns_none():
    url = "https://example.com/careers"
    result = _parse_greenhouse_url(url)
    assert result is None


def test_greenhouse_lever_url_returns_none():
    url = "https://jobs.lever.co/notion/abc-123"
    result = _parse_greenhouse_url(url)
    assert result is None


# ---------------------------------------------------------------------------
# _parse_lever_url
# ---------------------------------------------------------------------------


def test_lever_standard_url():
    url = "https://jobs.lever.co/notion/abc-123-uuid"
    result = _parse_lever_url(url)
    assert result == ("notion", "abc-123-uuid")


def test_lever_url_with_trailing_slash():
    url = "https://jobs.lever.co/acme/some-uuid/"
    result = _parse_lever_url(url)
    assert result == ("acme", "some-uuid")


def test_lever_regular_company_website_returns_none():
    url = "https://acme.com/careers"
    result = _parse_lever_url(url)
    assert result is None


def test_lever_greenhouse_url_returns_none():
    url = "https://boards.greenhouse.io/acme/jobs/12345"
    result = _parse_lever_url(url)
    assert result is None


# ---------------------------------------------------------------------------
# try_ats_fetch — integration with mocked requests.get
# ---------------------------------------------------------------------------


def _make_response(status_code: int, json_data: dict) -> MagicMock:
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    return mock


@patch("app.core.ats_client.requests.get")
def test_try_ats_fetch_greenhouse_success(mock_get):
    mock_get.return_value = _make_response(
        200,
        {
            "title": "Senior Engineer",
            "location": {"name": "Remote"},
            "content": "<p>Requirements: 5+ years Python experience.</p>",
        },
    )
    url = "https://coreweave.com/careers/job?gh_jid=4577764006&board=coreweave"
    result = try_ats_fetch(url)
    assert result is not None
    assert "Senior Engineer" in result
    # Verify correct API URL was called
    called_url = mock_get.call_args[0][0]
    assert "boards-api.greenhouse.io/v1/boards/coreweave/jobs/4577764006" in called_url


# What the live Greenhouse API actually returns: the body is HTML-entity-escaped.
ESCAPED_CONTENT = (
    "&lt;div class=&quot;content-intro&quot;&gt;&lt;h3&gt;About Us&lt;/h3&gt;"
    "&lt;p&gt;We build things &amp;amp; ship them.&lt;/p&gt;&lt;/div&gt;"
    "&lt;p&gt;&lt;strong&gt;What you&#39;ll do&lt;/strong&gt;&lt;/p&gt;"
    "&lt;ul&gt;&lt;li&gt;Build APIs&lt;/li&gt;&lt;li&gt;Own on-call&lt;/li&gt;&lt;/ul&gt;"
)


def test_greenhouse_escaped_content_becomes_clean_markdown_not_literal_html():
    markdown = _greenhouse_to_markdown(
        {"title": "Backend Engineer", "location": {"name": "Remote"}, "content": ESCAPED_CONTENT}
    )
    assert "<" not in markdown and "&lt;" not in markdown and "class=" not in markdown
    assert "We build things & ship them." in markdown  # entities inside the text survive once
    assert "* Build APIs" in markdown and "* Own on-call" in markdown  # real list items
    assert "About Us" in markdown and "What you'll do" in markdown


def test_greenhouse_already_plain_html_is_left_alone():
    markdown = _greenhouse_to_markdown(
        {"title": "T", "content": "<p>Use &lt;b&gt; tags &amp; escape them.</p>"}
    )
    assert "Use <b> tags & escape them." in markdown  # entities in real text decode once


@pytest.mark.parametrize("content", ["", "no markup at all", "<p>plain</p>"])
def test_unescape_helper_ignores_content_that_is_not_escaped(content):
    assert _unescape_if_escaped(content) == content


def test_unescape_helper_unescapes_only_real_escaped_markup():
    assert _unescape_if_escaped("&lt;p&gt;a &amp;amp; b&lt;/p&gt;") == "<p>a &amp; b</p>"


@patch("app.core.ats_client.requests.get")
def test_try_ats_fetch_greenhouse_404_returns_none(mock_get):
    mock_get.return_value = _make_response(404, {"error": "not found"})
    url = "https://boards.greenhouse.io/acme/jobs/99999"
    result = try_ats_fetch(url)
    assert result is None


@patch("app.core.ats_client.requests.get")
def test_try_ats_fetch_lever_success(mock_get):
    mock_get.return_value = _make_response(
        200,
        {
            "text": "Product Manager",
            "categories": {"team": "Product", "location": "New York"},
            "descriptionPlain": "We are looking for a PM with 3+ years of experience.",
            "lists": [
                {
                    "text": "Qualifications",
                    "content": "<ul><li>3+ years product experience</li></ul>",
                }
            ],
        },
    )
    url = "https://jobs.lever.co/notion/abc-123-uuid"
    result = try_ats_fetch(url)
    assert result is not None
    assert "Product Manager" in result
    called_url = mock_get.call_args[0][0]
    assert "api.lever.co/v0/postings/notion/abc-123-uuid" in called_url


@patch("app.core.ats_client.requests.get")
def test_try_ats_fetch_network_error_returns_none(mock_get):
    mock_get.side_effect = Exception("Connection refused")
    url = "https://coreweave.com/careers/job?gh_jid=123&board=coreweave"
    result = try_ats_fetch(url)
    assert result is None


def test_try_ats_fetch_non_ats_url_returns_none():
    """A normal company URL with no ATS markers — no HTTP call made."""
    url = "https://acme.com/careers/open-positions"
    result = try_ats_fetch(url)
    assert result is None

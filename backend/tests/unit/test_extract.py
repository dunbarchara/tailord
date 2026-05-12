"""Unit tests for validate_job_content in extract.py."""

from app.core.extract import validate_job_content

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REAL_JOB_CONTENT = """
# Senior Software Engineer

## About the role
We're looking for a Senior Software Engineer to join our platform team.

## Responsibilities
- Design and build scalable backend services
- Collaborate with cross-functional teams

## Requirements
- 5+ years of experience with Python or Go
- Experience with distributed systems

## Nice to have
- Familiarity with Kubernetes
- Open source contributions
"""

_CHROME_ONLY_CONTENT = """
CoreWeave

Products
Cloud GPUs
Kubernetes
Networking

Solutions
AI/ML
VFX Rendering
Game Streaming

Company
About Us
Careers
Blog
Press

Contact us | Privacy Policy | Cookie Settings

© 2024 CoreWeave, Inc. All rights reserved.
This website uses cookies to enhance your browsing experience.
Accept all cookies | Manage preferences
"""

_BOT_DETECTION_CONTENT = (
    """
Enable JavaScript and cookies to continue

Checking your browser before accessing the page.
This process is automatic. Your browser will redirect to your requested content shortly.

Requirements: you must pass the bot check first.
"""
    + "A" * 300
)  # pad past min-length check

_LOGIN_WALL_CONTENT = (
    """
Sign in to view this job

Please log in to your LinkedIn account to see this posting.

Requirements: log in to view full requirements.
"""
    + "A" * 300
)  # pad past min-length check

_JOB_REMOVED_CONTENT = (
    """
This job is no longer available.

The position you are looking for has been filled.
"""
    + "A" * 300
)  # pad past min-length check


# ---------------------------------------------------------------------------
# Length check
# ---------------------------------------------------------------------------


def test_too_short_fails():
    valid, reason = validate_job_content("Hi there")
    assert not valid
    assert "enough content" in reason


# ---------------------------------------------------------------------------
# Job-removed check (runs before length and keyword checks)
# ---------------------------------------------------------------------------


def test_job_removed_fails():
    valid, reason = validate_job_content(_JOB_REMOVED_CONTENT)
    assert not valid
    assert "removed" in reason.lower() or "expired" in reason.lower()


# ---------------------------------------------------------------------------
# Keyword signal check
# ---------------------------------------------------------------------------


def test_chrome_only_fails_no_job_signals():
    """CoreWeave-style website shell — nav links, product names, no job content."""
    valid, reason = validate_job_content(_CHROME_ONLY_CONTENT)
    assert not valid
    assert "doesn't look like a specific job posting" in reason


def test_real_job_content_passes():
    valid, reason = validate_job_content(_REAL_JOB_CONTENT)
    assert valid
    assert reason == ""


def test_signal_in_content_passes():
    """Any single signal phrase is sufficient."""
    content = "A" * 200 + "\n\nYears of experience in software engineering required."
    valid, _ = validate_job_content(content)
    assert valid


def test_multiple_signals_passes():
    content = (
        "A" * 200 + "\n\nBasic qualifications: 3+ years.\n"
        "Preferred qualifications: leadership experience.\n"
        "Responsibilities include building services."
    )
    valid, _ = validate_job_content(content)
    assert valid


# ---------------------------------------------------------------------------
# Bot detection check (after keyword check)
# ---------------------------------------------------------------------------


def test_bot_detection_fails():
    valid, reason = validate_job_content(_BOT_DETECTION_CONTENT)
    assert not valid
    assert "bot detection" in reason.lower() or "cloudflare" in reason.lower()


# ---------------------------------------------------------------------------
# Login wall check
# ---------------------------------------------------------------------------


def test_login_wall_fails():
    valid, reason = validate_job_content(_LOGIN_WALL_CONTENT)
    assert not valid
    assert "login" in reason.lower() or "sign in" in reason.lower()


# ---------------------------------------------------------------------------
# html param: phrase check uses full HTML text
# ---------------------------------------------------------------------------


def test_job_removed_in_html_only_fails():
    """Job-removed phrase is in the HTML nav/header but not in the markdown."""
    html = "<nav>This job is no longer available</nav><main>" + ("A " * 200) + "</main>"
    valid, reason = validate_job_content("A " * 200, html=html)
    assert not valid
    assert "removed" in reason.lower() or "expired" in reason.lower()

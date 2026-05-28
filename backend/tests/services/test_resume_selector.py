"""Unit tests for resume_selector helpers (no DB required)."""

from unittest.mock import MagicMock

from app.services.resume_selector import (
    _classify_section,
    _is_yoe_only,
    check_resume_prerequisites,
)

# ---------------------------------------------------------------------------
# _classify_section
# ---------------------------------------------------------------------------


def test_classify_section_must_have():
    assert _classify_section("Requirements") == 2.0


def test_classify_section_must_have_case_insensitive():
    assert _classify_section("minimum qualifications") == 2.0


def test_classify_section_nice_to_have():
    assert _classify_section("Nice to Have") == 1.0


def test_classify_section_preferred():
    assert _classify_section("Preferred Qualifications") == 1.0


def test_classify_section_unclassified():
    assert _classify_section("About the Role") == 1.5


def test_classify_section_none():
    assert _classify_section(None) == 1.5


# ---------------------------------------------------------------------------
# _is_yoe_only
# ---------------------------------------------------------------------------


def test_is_yoe_only_true_simple():
    assert _is_yoe_only("5+ years of experience") is True


def test_is_yoe_only_true_years_only():
    assert _is_yoe_only("3 years") is True


def test_is_yoe_only_false_substantive():
    assert _is_yoe_only("5+ years building distributed systems at scale") is False


def test_is_yoe_only_false_no_years():
    assert _is_yoe_only("Led cross-functional team to deliver platform migration") is False


# ---------------------------------------------------------------------------
# check_resume_prerequisites
# ---------------------------------------------------------------------------


def test_check_prerequisites_no_claims():
    db = MagicMock()
    db.query.return_value.filter.return_value.count.return_value = 0
    result = check_resume_prerequisites(MagicMock(), db)
    assert result["can_generate"] is False
    assert "no_active_claims" in result["warnings"]


def test_check_prerequisites_no_resume_source():
    import uuid

    db = MagicMock()
    # Active claims exist
    db.query.return_value.filter.return_value.count.return_value = 5
    # No resume source
    db.query.return_value.filter.return_value.first.return_value = None
    result = check_resume_prerequisites(uuid.uuid4(), db)
    assert result["can_generate"] is True
    assert "no_resume_source" in result["warnings"]


def test_check_prerequisites_all_good():
    import uuid

    db = MagicMock()
    db.query.return_value.filter.return_value.count.return_value = 10
    db.query.return_value.filter.return_value.first.return_value = MagicMock()
    result = check_resume_prerequisites(uuid.uuid4(), db)
    assert result["can_generate"] is True
    assert result["warnings"] == []


# ---------------------------------------------------------------------------
# YOE deprioritization — integration of _is_yoe_only in selection logic
# ---------------------------------------------------------------------------


def test_yoe_only_claim_excluded_when_enough_good_bullets():
    """
    When a role has ≥ 3 substantive bullets, YOE-only claims should not appear.
    Tests the filtering logic that _is_yoe_only drives.
    """
    good_contents = [
        "Led migration of monolith to microservices, reducing deploy time by 40%.",
        "Designed event-driven pipeline processing 50k events/sec.",
        "Mentored team of 5 engineers through cloud-native adoption.",
        "Built observability stack with OTel, Grafana, and Tempo.",
    ]
    yoe_content = "7+ years of experience"

    good = [c for c in good_contents if not _is_yoe_only(c)]
    yoe = [yoe_content for c in [yoe_content] if _is_yoe_only(c)]

    # With 4 good bullets, cap is 5 — YOE not needed
    final = good[:5]
    if len(final) < 3:
        final += yoe[: 3 - len(final)]

    assert yoe_content not in final
    assert len(final) == 4

"""Unit tests for requirement_matcher.match_requirements.

No DB interaction — the function is a pure LLM call wrapper.
LLM and profile formatter are mocked to isolate the scoring/filtering logic.
"""

from unittest.mock import MagicMock, patch

from app.schemas.matching import RequirementMatch, RequirementMatchList
from app.services.requirement_matcher import match_requirements

PROFILE = {"resume": {"skills": ["Python", "Docker"]}}


def _llm_patch(return_value):
    return patch(
        "app.services.requirement_matcher.llm_parse_with_retry",
        return_value=return_value,
    )


def _client_patch():
    return patch("app.services.requirement_matcher.get_llm_client", return_value=MagicMock())


def _profile_patch():
    return patch(
        "app.services.requirement_matcher._format_sourced_profile",
        return_value="formatted profile",
    )


# ---------------------------------------------------------------------------
# Empty inputs — no LLM call
# ---------------------------------------------------------------------------


def test_no_requirements_key_returns_empty():
    result = match_requirements({}, PROFILE)
    assert result == []


def test_empty_required_and_preferred_returns_empty():
    result = match_requirements({"requirements": {"required": [], "preferred": []}}, PROFILE)
    assert result == []


# ---------------------------------------------------------------------------
# Score paths
# ---------------------------------------------------------------------------


def test_strong_match_passes_through():
    llm_result = RequirementMatchList(
        matches=[RequirementMatch(requirement="Python", score=2, rationale="Strong Python")]
    )
    with _llm_patch(llm_result), _client_patch(), _profile_patch():
        result = match_requirements({"requirements": {"required": ["Python"]}}, PROFILE)

    assert len(result) == 1
    assert result[0]["score"] == 2


def test_partial_match_passes_through():
    llm_result = RequirementMatchList(
        matches=[RequirementMatch(requirement="Docker", score=1, rationale="Some Docker")]
    )
    with _llm_patch(llm_result), _client_patch(), _profile_patch():
        result = match_requirements({"requirements": {"required": ["Docker"]}}, PROFILE)

    assert len(result) == 1
    assert result[0]["score"] == 1


def test_no_match_filtered_out():
    llm_result = RequirementMatchList(
        matches=[RequirementMatch(requirement="Kubernetes", score=0, rationale="Not found")]
    )
    with _llm_patch(llm_result), _client_patch(), _profile_patch():
        result = match_requirements({"requirements": {"required": ["Kubernetes"]}}, PROFILE)

    assert result == []


def test_mixed_results_sorted_by_score_desc():
    llm_result = RequirementMatchList(
        matches=[
            RequirementMatch(requirement="Docker", score=1, rationale="Some Docker"),
            RequirementMatch(requirement="Python", score=2, rationale="Strong Python"),
            RequirementMatch(requirement="K8s", score=0, rationale="No match"),
        ]
    )
    with _llm_patch(llm_result), _client_patch(), _profile_patch():
        result = match_requirements(
            {"requirements": {"required": ["Python", "Docker", "K8s"]}}, PROFILE
        )

    assert [m["score"] for m in result] == [2, 1]


def test_preferred_requirements_included():
    """Preferred requirements are also scored and returned if score >= 1."""
    llm_result = RequirementMatchList(
        matches=[
            RequirementMatch(requirement="Go", score=2, rationale="Strong Go", is_preferred=True)
        ]
    )
    with _llm_patch(llm_result), _client_patch(), _profile_patch():
        result = match_requirements(
            {"requirements": {"required": [], "preferred": ["Go"]}}, PROFILE
        )

    assert len(result) == 1
    assert result[0]["requirement"] == "Go"


# ---------------------------------------------------------------------------
# Profile key coverage
# ---------------------------------------------------------------------------


def test_experience_source_preserved():
    llm_result = RequirementMatchList(
        matches=[RequirementMatch(requirement="Python", score=2, experience_source="github")]
    )
    with _llm_patch(llm_result), _client_patch(), _profile_patch():
        result = match_requirements({"requirements": {"required": ["Python"]}}, PROFILE)

    assert result[0]["experience_source"] == "github"


def test_is_preferred_flag_preserved():
    llm_result = RequirementMatchList(
        matches=[RequirementMatch(requirement="Go", score=1, is_preferred=True)]
    )
    with _llm_patch(llm_result), _client_patch(), _profile_patch():
        result = match_requirements({"requirements": {"preferred": ["Go"]}}, PROFILE)

    assert result[0]["is_preferred"] is True

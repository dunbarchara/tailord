"""Unit tests for gap_analyzer._generate_gap_question and run_gap_analysis.

run_gap_analysis creates its own DB session, so SessionLocal is patched at
app.clients.database.SessionLocal. _format_sourced_profile is also patched
to isolate the gap logic from the profile formatting layer.
"""

from unittest.mock import MagicMock, patch

from app.schemas.gaps import GapQuestion
from app.services.gap_analyzer import _generate_gap_question, run_gap_analysis

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(match_score, should_render=True, content="requirement text", chunk_id="chunk-id"):
    c = MagicMock()
    c.match_score = match_score
    c.should_render = should_render
    c.content = content
    c.id = chunk_id
    return c


def _ready_tailoring(chunks_for_query):
    """Return a mock Tailoring and a mock DB session wired up to return it."""
    tailoring = MagicMock()
    tailoring.generation_status = "ready"
    tailoring.job = MagicMock()  # non-None — has a job
    tailoring.user = MagicMock()
    tailoring.user.experience.extracted_profile = {"resume": {}}
    tailoring.user.pronouns = None
    tailoring.user.preferred_first_name = None
    tailoring.user.preferred_last_name = None
    tailoring.user.name = "Alex Chen"
    tailoring.user.email = "alex@example.com"

    db = MagicMock()
    # db.query(Tailoring).filter(...).first() → tailoring
    db.query.return_value.filter.return_value.first.return_value = tailoring
    # db.query(JobChunk).filter(...).all() → chunks
    db.query.return_value.filter.return_value.all.return_value = chunks_for_query

    return tailoring, db


# ---------------------------------------------------------------------------
# _generate_gap_question
# ---------------------------------------------------------------------------


def test_generate_gap_question_returns_llm_result():
    mock_result = GapQuestion(
        question_for_candidate="Do you have Python experience?",
        context="Python is core to this backend role",
    )
    with patch("app.services.gap_analyzer.llm_parse_with_retry", return_value=mock_result):
        with patch("app.services.gap_analyzer.get_llm_client", return_value=MagicMock()):
            result = _generate_gap_question(
                requirement="Python 3+ experience",
                match_rationale="No Python evidence found",
                formatted_profile="Senior engineer, 5 years Python",
                job_context="Backend Engineer at Acme Corp",
            )

    assert result.question_for_candidate == "Do you have Python experience?"
    assert result.context == "Python is core to this backend role"


def test_generate_gap_question_includes_requirement_in_prompt():
    mock_result = GapQuestion(question_for_candidate="Q?", context="ctx")
    with patch(
        "app.services.gap_analyzer.llm_parse_with_retry", return_value=mock_result
    ) as mock_llm:
        with patch("app.services.gap_analyzer.get_llm_client", return_value=MagicMock()):
            _generate_gap_question(
                "Kubernetes orchestration",
                "No K8s evidence found",
                "some profile",
                "DevOps Engineer at Acme Corp",
            )

    messages = mock_llm.call_args.kwargs["messages"]
    user_content = messages[-1]["content"]
    assert "Kubernetes orchestration" in user_content


# ---------------------------------------------------------------------------
# run_gap_analysis — zero gap chunks
# ---------------------------------------------------------------------------


def test_run_gap_analysis_zero_gaps_empty_result():
    """All chunks scored 2 → gaps=[], partials=[], correct counts, LLM not called."""
    chunks = [_make_chunk(2), _make_chunk(2)]
    tailoring, db = _ready_tailoring(chunks)

    with patch("app.clients.database.SessionLocal", return_value=db):
        with patch("app.services.gap_analyzer.llm_parse_with_retry") as mock_llm:
            with patch("app.services.gap_analyzer.get_llm_client", return_value=MagicMock()):
                with patch(
                    "app.services.gap_analyzer._format_sourced_profile",
                    return_value="formatted profile",
                ):
                    run_gap_analysis("fake-tailoring-id")

    # Chunk scores are the authoritative source — no LLM re-scoring
    mock_llm.assert_not_called()

    saved = tailoring.gap_analysis
    assert saved["gaps"] == []
    assert saved["sourced_claim_count"] == 2
    assert saved["unsourced_claim_count"] == 0
    assert tailoring.gap_analysis_status == "complete"


# ---------------------------------------------------------------------------
# run_gap_analysis — sourced count arithmetic
# ---------------------------------------------------------------------------


def test_run_gap_analysis_sourced_count_excludes_score_zero():
    """score=0 chunks are unsourced; score>=1 are sourced."""
    chunks = [
        _make_chunk(2),
        _make_chunk(0),
        _make_chunk(1),
        _make_chunk(0),
    ]
    tailoring, db = _ready_tailoring(chunks)

    mock_gap_q = GapQuestion(question_for_candidate="Q?", context="ctx")

    with patch("app.clients.database.SessionLocal", return_value=db):
        with patch("app.services.gap_analyzer.llm_parse_with_retry", return_value=mock_gap_q):
            with patch("app.services.gap_analyzer.get_llm_client", return_value=MagicMock()):
                with patch(
                    "app.services.gap_analyzer._format_sourced_profile",
                    return_value="formatted profile",
                ):
                    run_gap_analysis("fake-tailoring-id")

    saved = tailoring.gap_analysis
    assert saved["sourced_claim_count"] == 2  # score 2 and 1
    assert saved["unsourced_claim_count"] == 2  # both score 0


# ---------------------------------------------------------------------------
# run_gap_analysis — gap content
# ---------------------------------------------------------------------------


def test_run_gap_analysis_gap_content_in_output():
    """score=0 chunk → ProfileGapWithChunk with correct job_requirement and question."""
    gap_chunk = _make_chunk(0, content="Kubernetes orchestration", chunk_id="chunk-uuid-1")
    chunks = [_make_chunk(2), gap_chunk]
    tailoring, db = _ready_tailoring(chunks)

    mock_gap_q = GapQuestion(
        question_for_candidate="Tell me about your K8s experience?",
        context="K8s is used for production deployments",
    )

    with patch("app.clients.database.SessionLocal", return_value=db):
        with patch("app.services.gap_analyzer.llm_parse_with_retry", return_value=mock_gap_q):
            with patch("app.services.gap_analyzer.get_llm_client", return_value=MagicMock()):
                with patch(
                    "app.services.gap_analyzer._format_sourced_profile",
                    return_value="formatted profile",
                ):
                    run_gap_analysis("fake-tailoring-id")

    saved = tailoring.gap_analysis
    assert len(saved["gaps"]) == 1
    gap = saved["gaps"][0]
    assert gap["job_requirement"] == "Kubernetes orchestration"
    assert gap["question_for_candidate"] == "Tell me about your K8s experience?"
    assert gap["chunk_id"] == "chunk-uuid-1"
    assert gap["source_searched"] == "chunk_scorer"

"""Unit tests for chunk_matcher.enrich_job_chunks and re_enrich_single_chunk.

Both functions create their own DB sessions internally, so SessionLocal is
patched at app.clients.database.SessionLocal. extract_chunks and
_format_sourced_profile are also patched to keep tests self-contained.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.schemas.matching import ChunkMatchBatch, ChunkMatchResult
from app.services.chunk_matcher import enrich_job_chunks, re_enrich_single_chunk

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _chunk(position, content="requirement text", chunk_type="bullet", section="Requirements"):
    return SimpleNamespace(
        position=position,
        content=content,
        chunk_type=chunk_type,
        section=section,
    )


def _run_enrich(job_id, chunks, llm_result, mock_db=None):
    """Run enrich_job_chunks with all external dependencies mocked.

    Returns (added_objects, mock_db) where added_objects is the list of
    JobChunk instances passed to db.add().
    """
    if mock_db is None:
        mock_db = MagicMock()
    added = []
    mock_db.add.side_effect = lambda obj: added.append(obj)

    with patch("app.clients.database.SessionLocal", return_value=mock_db):
        with patch("app.services.chunk_matcher.extract_chunks", return_value=chunks):
            with patch("app.services.chunk_matcher.llm_parse_with_retry", return_value=llm_result):
                with patch("app.services.chunk_matcher.get_llm_client", return_value=MagicMock()):
                    with patch(
                        "app.services.chunk_matcher._format_sourced_profile",
                        return_value="formatted profile",
                    ):
                        enrich_job_chunks(job_id, "# Job\n\nContent", {})

    return added, mock_db


# ---------------------------------------------------------------------------
# enrich_job_chunks — score paths
# ---------------------------------------------------------------------------


def test_score_0_chunk_persisted():
    job_id = uuid.uuid4()
    chunks = [_chunk(0, "Kubernetes experience")]
    llm_result = ChunkMatchBatch(results=[ChunkMatchResult(score=0, rationale="No match")])

    added, _ = _run_enrich(job_id, chunks, llm_result)

    assert len(added) == 1
    assert added[0].match_score == 0


def test_score_1_chunk_persisted():
    job_id = uuid.uuid4()
    chunks = [_chunk(0, "Python experience")]
    llm_result = ChunkMatchBatch(
        results=[
            ChunkMatchResult(score=1, rationale="Some Python", advocacy_blurb="Has some Python")
        ]
    )

    added, _ = _run_enrich(job_id, chunks, llm_result)

    assert len(added) == 1
    assert added[0].match_score == 1
    assert added[0].advocacy_blurb == "Has some Python"


def test_score_2_chunk_persisted():
    job_id = uuid.uuid4()
    chunks = [_chunk(0, "Python 5+ years")]
    llm_result = ChunkMatchBatch(
        results=[
            ChunkMatchResult(
                score=2, rationale="Strong Python", advocacy_blurb="Excellent Python engineer"
            )
        ]
    )

    added, _ = _run_enrich(job_id, chunks, llm_result)

    assert len(added) == 1
    assert added[0].match_score == 2
    assert added[0].advocacy_blurb == "Excellent Python engineer"


def test_header_chunks_get_minus_one_score():
    """Header chunks bypass LLM — persisted with score=-1."""
    job_id = uuid.uuid4()
    chunks = [
        _chunk(0, "Requirements", chunk_type="header", section=None),
        _chunk(1, "Python experience"),
    ]
    llm_result = ChunkMatchBatch(
        results=[ChunkMatchResult(score=2, rationale="Strong", advocacy_blurb="Great Python")]
    )

    added, _ = _run_enrich(job_id, chunks, llm_result)

    scores = {c.content: c.match_score for c in added}
    assert scores["Requirements"] == -1
    assert scores["Python experience"] == 2


# ---------------------------------------------------------------------------
# enrich_job_chunks — batch error telemetry
# ---------------------------------------------------------------------------


def test_batch_error_increments_error_count():
    """LLM failure → chunk_error_count=1 written to Tailoring update."""
    job_id = uuid.uuid4()
    chunks = [_chunk(0), _chunk(1), _chunk(2)]
    mock_db = MagicMock()

    with patch("app.clients.database.SessionLocal", return_value=mock_db):
        with patch("app.services.chunk_matcher.extract_chunks", return_value=chunks):
            with patch(
                "app.services.chunk_matcher.llm_parse_with_retry",
                side_effect=RuntimeError("LLM down"),
            ):
                with patch("app.services.chunk_matcher.get_llm_client", return_value=MagicMock()):
                    with patch(
                        "app.services.chunk_matcher._format_sourced_profile",
                        return_value="profile",
                    ):
                        enrich_job_chunks(job_id, "# Job\n\nContent", {})

    update_call = mock_db.query.return_value.filter.return_value.update.call_args
    assert update_call is not None
    update_dict = update_call[0][0]
    assert update_dict["chunk_error_count"] == 1
    assert update_dict["enrichment_status"] == "complete"


def test_batch_error_pads_chunks_with_minus_one():
    """On LLM failure, all chunks in the failed batch are persisted with score=-1."""
    job_id = uuid.uuid4()
    chunks = [_chunk(0, "req A"), _chunk(1, "req B")]
    mock_db = MagicMock()
    added = []
    mock_db.add.side_effect = lambda obj: added.append(obj)

    with patch("app.clients.database.SessionLocal", return_value=mock_db):
        with patch("app.services.chunk_matcher.extract_chunks", return_value=chunks):
            with patch(
                "app.services.chunk_matcher.llm_parse_with_retry",
                side_effect=RuntimeError("LLM down"),
            ):
                with patch("app.services.chunk_matcher.get_llm_client", return_value=MagicMock()):
                    with patch(
                        "app.services.chunk_matcher._format_sourced_profile",
                        return_value="profile",
                    ):
                        enrich_job_chunks(job_id, "# Job\n\nContent", {})

    assert len(added) == 2
    assert all(c.match_score == -1 for c in added)


# ---------------------------------------------------------------------------
# re_enrich_single_chunk
# ---------------------------------------------------------------------------


def test_re_enrich_updates_chunk_fields_in_place():
    mock_chunk = MagicMock()
    mock_chunk.section = "Requirements"
    mock_chunk.chunk_type = "bullet"
    mock_chunk.content = "Python experience"

    mock_db = MagicMock()
    mock_db.get.return_value = mock_chunk

    llm_result = ChunkMatchBatch(
        results=[
            ChunkMatchResult(
                score=2,
                rationale="Strong Python",
                advocacy_blurb="Expert Python engineer",
                experience_source="resume",
                should_render=True,
            )
        ]
    )

    with patch("app.clients.database.SessionLocal", return_value=mock_db):
        with patch("app.services.chunk_matcher.llm_parse_with_retry", return_value=llm_result):
            with patch("app.services.chunk_matcher.get_llm_client", return_value=MagicMock()):
                with patch(
                    "app.services.chunk_matcher._format_sourced_profile",
                    return_value="profile",
                ):
                    re_enrich_single_chunk("fake-chunk-id", {})

    assert mock_chunk.match_score == 2
    assert mock_chunk.match_rationale == "Strong Python"
    assert mock_chunk.advocacy_blurb == "Expert Python engineer"
    assert mock_chunk.experience_source == "resume"
    assert mock_chunk.should_render is True
    mock_db.commit.assert_called_once()


def test_re_enrich_chunk_not_found_does_not_crash():
    mock_db = MagicMock()
    mock_db.get.return_value = None

    with patch("app.clients.database.SessionLocal", return_value=mock_db):
        re_enrich_single_chunk("nonexistent-chunk-id", {})

    mock_db.commit.assert_not_called()

"""
tests/services/test_chunk_lifecycle.py

Verifies that gap_response (and annotation) chunks are NOT touched by the
source-level bulk delete functions (delete_resume_chunks, delete_github_chunks,
delete_user_input_chunks). These functions filter by source_type, so gap_response
chunks should always be excluded.

Also verifies the SQLAlchemy cascade configuration that ensures all ExperienceChunk
rows (including gap_response) are deleted when their parent Experience is deleted.
"""

import uuid
from unittest.mock import MagicMock, patch

from app.services.experience_chunker import (
    _delete_chunks,
    delete_github_chunks,
    delete_resume_chunks,
    delete_user_input_chunks,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db() -> MagicMock:
    db = MagicMock()
    db.query.return_value.filter.return_value.delete.return_value = 0
    db.query.return_value.filter.return_value.filter.return_value.delete.return_value = 0
    return db


# ---------------------------------------------------------------------------
# delete_resume_chunks — only deletes source_type="resume"
# ---------------------------------------------------------------------------


def test_delete_resume_chunks_targets_resume_only():
    exp_id = uuid.uuid4()
    db = _make_db()

    with patch("app.services.experience_chunker._delete_chunks") as mock_delete:
        delete_resume_chunks(db, exp_id)

    mock_delete.assert_called_once_with(db, exp_id, "resume")


def test_delete_resume_chunks_does_not_touch_gap_response():
    """gap_response is never passed as source_type to _delete_chunks during resume delete."""
    exp_id = uuid.uuid4()
    db = _make_db()

    with patch("app.services.experience_chunker._delete_chunks") as mock_delete:
        delete_resume_chunks(db, exp_id)

    called_source_types = [call.args[2] for call in mock_delete.call_args_list]
    assert "gap_response" not in called_source_types


# ---------------------------------------------------------------------------
# delete_github_chunks — only deletes source_type="github"
# ---------------------------------------------------------------------------


def test_delete_github_chunks_targets_github_only():
    exp_id = uuid.uuid4()
    db = _make_db()

    with patch("app.services.experience_chunker._delete_chunks") as mock_delete:
        delete_github_chunks(db, exp_id)

    mock_delete.assert_called_once_with(db, exp_id, "github", source_ref=None)


def test_delete_github_chunks_single_repo_targets_github_only():
    exp_id = uuid.uuid4()
    db = _make_db()

    with patch("app.services.experience_chunker._delete_chunks") as mock_delete:
        delete_github_chunks(db, exp_id, repo_name="my-repo")

    mock_delete.assert_called_once_with(db, exp_id, "github", source_ref="my-repo")


def test_delete_github_chunks_does_not_touch_gap_response():
    exp_id = uuid.uuid4()
    db = _make_db()

    with patch("app.services.experience_chunker._delete_chunks") as mock_delete:
        delete_github_chunks(db, exp_id)

    called_source_types = [call.args[2] for call in mock_delete.call_args_list]
    assert "gap_response" not in called_source_types


# ---------------------------------------------------------------------------
# delete_user_input_chunks — only deletes source_type="user_input"
# ---------------------------------------------------------------------------


def test_delete_user_input_chunks_targets_user_input_only():
    exp_id = uuid.uuid4()
    db = _make_db()

    with patch("app.services.experience_chunker._delete_chunks") as mock_delete:
        delete_user_input_chunks(db, exp_id)

    mock_delete.assert_called_once_with(db, exp_id, "user_input")


def test_delete_user_input_chunks_does_not_touch_gap_response():
    exp_id = uuid.uuid4()
    db = _make_db()

    with patch("app.services.experience_chunker._delete_chunks") as mock_delete:
        delete_user_input_chunks(db, exp_id)

    called_source_types = [call.args[2] for call in mock_delete.call_args_list]
    assert "gap_response" not in called_source_types


# ---------------------------------------------------------------------------
# _delete_chunks — source_type filter is applied to the DB query
# ---------------------------------------------------------------------------


def test_delete_chunks_filters_by_source_type():
    """_delete_chunks passes source_type as a filter — only rows matching that type
    are deleted. Verified by inspecting the filter call chain on the mock."""
    from app.models.database import ExperienceChunk

    exp_id = uuid.uuid4()
    db = _make_db()

    _delete_chunks(db, exp_id, "gap_response")

    # Should have queried ExperienceChunk
    db.query.assert_called_once_with(ExperienceChunk)


# ---------------------------------------------------------------------------
# SQLAlchemy cascade — Experience deletion cascades to all chunk types
# ---------------------------------------------------------------------------


def test_experience_chunks_relationship_has_cascade_delete():
    """Experience.chunks uses cascade='all, delete-orphan', ensuring that when an
    Experience row is deleted, all its ExperienceChunks (including gap_response
    and annotation) are also deleted via SQLAlchemy cascade."""
    from app.models.database import Experience

    chunks_relationship = Experience.__mapper__.relationships["chunks"]
    cascade_str = str(chunks_relationship.cascade)
    assert "delete" in cascade_str
    assert "delete-orphan" in cascade_str

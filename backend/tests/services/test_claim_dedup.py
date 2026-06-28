"""Unit tests for claim_dedup.py.

DB interactions are mocked. embed_text is patched throughout.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

USER_ID = uuid.uuid4()
FIXED_VECTOR = [0.1] * 1536


# ---------------------------------------------------------------------------
# is_duplicate_by_source_ref
# ---------------------------------------------------------------------------


def _make_exists_db(result: bool) -> MagicMock:
    db = MagicMock()
    db.query.return_value.scalar.return_value = result
    return db


def test_source_ref_match_returns_true():
    from app.services.claim_dedup import is_duplicate_by_source_ref

    db = _make_exists_db(True)
    assert is_duplicate_by_source_ref(USER_ID, "github", "my-repo", db) is True


def test_source_ref_no_match_returns_false():
    from app.services.claim_dedup import is_duplicate_by_source_ref

    db = _make_exists_db(False)
    assert is_duplicate_by_source_ref(USER_ID, "github", "new-repo", db) is False


# ---------------------------------------------------------------------------
# is_duplicate_claim
# ---------------------------------------------------------------------------


def _make_similarity_db(similarity: float | None) -> MagicMock:
    """Mock db whose query chain returns the given similarity scalar."""
    db = MagicMock()
    (
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.scalar.return_value
    ) = similarity
    return db


def test_similarity_at_threshold_is_duplicate():
    from app.services.claim_dedup import is_duplicate_claim

    threshold = 0.92
    db = _make_similarity_db(threshold)

    with patch("app.services.claim_dedup.embed_text", return_value=FIXED_VECTOR):
        result = is_duplicate_claim(
            USER_ID, "Led migration to microservices", db, threshold=threshold
        )

    assert result is True


def test_similarity_below_threshold_is_not_duplicate():
    from app.services.claim_dedup import is_duplicate_claim

    db = _make_similarity_db(0.91)

    with patch("app.services.claim_dedup.embed_text", return_value=FIXED_VECTOR):
        result = is_duplicate_claim(USER_ID, "Led migration to microservices", db, threshold=0.92)

    assert result is False


def test_no_existing_claims_is_not_duplicate():
    from app.services.claim_dedup import is_duplicate_claim

    db = _make_similarity_db(None)

    with patch("app.services.claim_dedup.embed_text", return_value=FIXED_VECTOR):
        result = is_duplicate_claim(USER_ID, "Built a feature end-to-end", db)

    assert result is False


def test_embed_text_raises_propagates():
    from app.services.claim_dedup import is_duplicate_claim

    db = MagicMock()

    with patch("app.services.claim_dedup.embed_text", side_effect=ValueError("API error")):
        with pytest.raises(ValueError, match="API error"):
            is_duplicate_claim(USER_ID, "Some content", db)


def test_embed_text_called_with_correct_context():
    from app.services.claim_dedup import is_duplicate_claim

    db = _make_similarity_db(0.5)

    with patch("app.services.claim_dedup.embed_text", return_value=FIXED_VECTOR) as mock_embed:
        is_duplicate_claim(USER_ID, "Built CI/CD pipeline", db)

    mock_embed.assert_called_once_with("Built CI/CD pipeline", embed_context="claim_dedup")

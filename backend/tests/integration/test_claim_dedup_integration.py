"""Integration tests for claim_dedup against a real PostgreSQL + pgvector database.

Requires TEST_DATABASE_URL pointing to a Postgres instance with pgvector enabled.
Uses the db and approved_user fixtures from tests/integration/conftest.py and
make_claim() from tests/conftest.py.
"""

from unittest.mock import patch

from tests.conftest import make_claim

NEAR_VECTOR = [0.1] * 1536
FAR_VECTOR = [0.9] + [0.0] * 1535


# ---------------------------------------------------------------------------
# is_duplicate_by_source_ref
# ---------------------------------------------------------------------------


def test_source_ref_duplicate_found(db, approved_user):
    from app.services.claim_dedup import is_duplicate_by_source_ref

    make_claim(db, approved_user, source_type="github", source_ref="my-repo")

    assert is_duplicate_by_source_ref(approved_user.id, "github", "my-repo", db) is True


def test_source_ref_no_match(db, approved_user):
    from app.services.claim_dedup import is_duplicate_by_source_ref

    assert is_duplicate_by_source_ref(approved_user.id, "github", "nonexistent-repo", db) is False


def test_source_ref_different_user_no_match(db, approved_user):
    from app.services.claim_dedup import is_duplicate_by_source_ref
    from tests.conftest import make_user

    other_user = make_user(db, google_sub="other-sub")
    make_claim(db, other_user, source_type="github", source_ref="shared-repo")

    # approved_user should NOT see other_user's claim
    assert is_duplicate_by_source_ref(approved_user.id, "github", "shared-repo", db) is False


# ---------------------------------------------------------------------------
# is_duplicate_claim (semantic)
# ---------------------------------------------------------------------------


def test_identical_embedding_is_duplicate(db, approved_user):
    from app.services.claim_dedup import is_duplicate_claim

    # Seed a claim with a known embedding
    claim = make_claim(db, approved_user, content="Led migration to microservices architecture")
    claim.embedding = NEAR_VECTOR
    db.commit()

    # Patch embed_text to return same vector — cosine distance = 0 → similarity = 1.0
    with patch("app.services.claim_dedup.embed_text", return_value=NEAR_VECTOR):
        result = is_duplicate_claim(
            approved_user.id, "Led migration to microservices architecture", db
        )

    assert result is not None
    assert result.id == claim.id


def test_unrelated_content_is_not_duplicate(db, approved_user):
    from app.services.claim_dedup import is_duplicate_claim

    claim = make_claim(db, approved_user, content="Led migration to microservices architecture")
    claim.embedding = NEAR_VECTOR
    db.commit()

    # FAR_VECTOR is orthogonal to NEAR_VECTOR — cosine distance ≈ 1 → similarity ≈ 0
    with patch("app.services.claim_dedup.embed_text", return_value=FAR_VECTOR):
        result = is_duplicate_claim(
            approved_user.id,
            "Managed budget spreadsheets for quarterly reviews",
            db,
            threshold=0.92,
        )

    assert result is None


def test_pending_claim_is_considered(db, approved_user):
    """Pending claims must be considered duplicates too, not just active ones.

    Without this, an incoming claim is only checked against claims the user has
    already reviewed and approved. In a passive-capture-then-review-later workflow,
    nothing is "active" yet at capture time, so this check would otherwise never
    catch duplicates piling up across unreviewed captures.
    """
    from app.models.database import ExperienceClaim
    from app.services.claim_dedup import is_duplicate_claim

    claim = make_claim(db, approved_user, content="Deployed Kubernetes clusters")
    db.query(ExperienceClaim).filter(ExperienceClaim.id == claim.id).update({"status": "pending"})
    claim.embedding = NEAR_VECTOR
    db.commit()

    with patch("app.services.claim_dedup.embed_text", return_value=NEAR_VECTOR):
        result = is_duplicate_claim(approved_user.id, "Deployed Kubernetes clusters", db)

    assert result is not None
    assert result.id == claim.id


def test_archived_claim_not_considered(db, approved_user):
    """Archived (rejected or superseded) claims must not be considered duplicates."""
    from app.models.database import ExperienceClaim
    from app.services.claim_dedup import is_duplicate_claim

    claim = make_claim(db, approved_user, content="Deployed Kubernetes clusters")
    db.query(ExperienceClaim).filter(ExperienceClaim.id == claim.id).update({"status": "archived"})
    claim.embedding = NEAR_VECTOR
    db.commit()

    with patch("app.services.claim_dedup.embed_text", return_value=NEAR_VECTOR):
        result = is_duplicate_claim(approved_user.id, "Deployed Kubernetes clusters", db)

    assert result is None


def test_no_claims_returns_none(db, approved_user):
    """Empty DB → not a duplicate."""
    from app.services.claim_dedup import is_duplicate_claim

    with patch("app.services.claim_dedup.embed_text", return_value=NEAR_VECTOR):
        result = is_duplicate_claim(approved_user.id, "Anything", db)

    assert result is None


def test_claim_without_embedding_skipped(db, approved_user):
    """Claims with null embedding must not be considered (filter: embedding.isnot(None))."""
    from app.services.claim_dedup import is_duplicate_claim

    make_claim(db, approved_user, content="Led migration to microservices architecture")
    # embedding left as None (default from make_claim)

    with patch("app.services.claim_dedup.embed_text", return_value=NEAR_VECTOR):
        result = is_duplicate_claim(
            approved_user.id, "Led migration to microservices architecture", db
        )

    assert result is None

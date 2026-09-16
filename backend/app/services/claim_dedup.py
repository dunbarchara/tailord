"""
claim_dedup.py — two-layer duplicate detection for incoming experience claims.

Layer 1 — Exact source_ref match (free): checks whether a claim with the same
(user_id, source_type, source_ref) already exists. Runs before any embedding call.

Layer 2 — Semantic similarity (embedding cosine distance): embeds the candidate
content and queries the nearest active claim. Returns True if similarity meets or
exceeds the configured threshold.

Both functions operate synchronously and do NOT commit — callers decide whether to
skip insertion or record a skip reason on the CaptureSignal row.
"""

import uuid

from sqlalchemy import exists
from sqlalchemy.orm import Session

from app.clients.embedding_client import embed_text
from app.config import settings
from app.models.database import ExperienceClaim


def is_duplicate_by_source_ref(
    user_id: uuid.UUID,
    source_type: str,
    source_ref: str,
    db: Session,
) -> bool:
    """Return True if an ExperienceClaim with the same (user_id, source_type, source_ref) exists.

    Used as a fast idempotency guard before the more expensive semantic check.
    """
    return db.query(
        exists().where(
            ExperienceClaim.user_id == user_id,
            ExperienceClaim.source_type == source_type,
            ExperienceClaim.source_ref == source_ref,
        )
    ).scalar()


def is_duplicate_claim(
    user_id: uuid.UUID,
    candidate_content: str,
    db: Session,
    threshold: float | None = None,
) -> ExperienceClaim | None:
    """Return the nearest existing claim if it's a semantic duplicate, else None.

    Embeds `candidate_content` and finds the nearest claim by cosine distance among
    claims with status "active" OR "pending" — pending is included so duplicates are
    caught across a capture-then-review cycle, not just against claims the user has
    already approved. Without this, a passive-capture workflow where review happens
    in occasional batches would never dedup two similar claims captured before either
    was reviewed, since neither would be "active" yet.

    Returns the matched ExperienceClaim when similarity >= threshold (default:
    settings.claim_dedup_threshold), else None. Callers that find a match are expected
    to roll the candidate up into it (e.g. append to `merged_from`) rather than discard
    it outright, so the signal that produced it is never silently lost.

    Raises if embed_text raises (e.g. empty content, API failure) — callers decide
    whether to suppress or propagate.
    """
    if threshold is None:
        threshold = settings.claim_dedup_threshold

    candidate_embedding = embed_text(candidate_content, embed_context="claim_dedup")

    row = (
        db.query(
            ExperienceClaim,
            (1 - ExperienceClaim.embedding.cosine_distance(candidate_embedding)).label("similarity"),
        )
        .filter(
            ExperienceClaim.user_id == user_id,
            ExperienceClaim.status.in_(("active", "pending")),
            ExperienceClaim.embedding.isnot(None),
        )
        .order_by(ExperienceClaim.embedding.cosine_distance(candidate_embedding))
        .limit(1)
        .first()
    )

    if row is None:
        return None

    claim, similarity = row
    return claim if similarity >= threshold else None

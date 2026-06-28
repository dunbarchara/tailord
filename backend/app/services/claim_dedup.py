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
) -> bool:
    """Return True if the candidate content is semantically similar to an existing active claim.

    Embeds `candidate_content` and queries the nearest active claim by cosine distance.
    Returns True when similarity >= threshold (default: settings.claim_dedup_threshold).

    Raises if embed_text raises (e.g. empty content, API failure) — callers decide
    whether to suppress or propagate.
    """
    if threshold is None:
        threshold = settings.claim_dedup_threshold

    candidate_embedding = embed_text(candidate_content, embed_context="claim_dedup")

    result = (
        db.query(
            (1 - ExperienceClaim.embedding.cosine_distance(candidate_embedding)).label("similarity")
        )
        .filter(
            ExperienceClaim.user_id == user_id,
            ExperienceClaim.status == "active",
            ExperienceClaim.embedding.isnot(None),
        )
        .order_by(ExperienceClaim.embedding.cosine_distance(candidate_embedding))
        .limit(1)
        .scalar()
    )

    return result is not None and result >= threshold

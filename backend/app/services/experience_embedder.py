"""
experience_embedder.py — embed ExperienceClaim and JobChunk rows after write.

Public functions
----------------
embed_experience_chunks(user_id, db)
    Embed all unembedded / stale ExperienceClaims. Uses provided session.
    Called inline from background tasks (SSE stream, github_enricher).

embed_experience_chunks_task(user_id)
    Background-task variant: creates its own DB session.
    Used from request handlers (set_user_input) where the request session
    must not be held open across async work.

embed_job_chunks(job_id, db)
    Embed all unembedded / stale JobChunks. Uses provided session.
    Called inline from chunk_matcher.enrich_job_chunks.

re_embed_chunk(chunk_id)
    Re-embed a single ExperienceClaim. Creates its own DB session.
    Used as a BackgroundTask from PATCH /experience/chunks/{id}.

All functions are non-fatal: per-chunk failures are logged as warnings and
skipped. The pipeline continues regardless of embedding errors.
"""

import re
import time as _time
import uuid

import structlog
import structlog.contextvars
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.clients.embedding_client import embed_text
from app.config import settings

logger = structlog.get_logger(__name__)

# Matches display prefixes added to gap/partial response claims, e.g.:
#   "[Gap answer — CI/CD pipeline experience]: "
#   "[Gap answer (partial): something]: "
# Stripping these before embedding ensures cosine distance reflects the
# actual answer content, not label noise.
_CLAIM_PREFIX_RE = re.compile(r"^\[[^\]]+\]:\s*")


def _embedding_text(claim) -> str:
    """Return the text to embed for a claim.

    For gap_response and partial_response claims the stored content includes a
    display prefix (e.g. '[Gap answer — ...]: ') that adds noise to the embedding
    and inflates cosine distance vs. job requirements. Strip it so the embedding
    represents the raw answer.
    """
    if claim.source_type in ("gap_response", "partial_response"):
        stripped = _CLAIM_PREFIX_RE.sub("", claim.content)
        return stripped if stripped else claim.content
    return claim.content


def embed_experience_chunks(user_id: uuid.UUID, db: Session) -> None:
    """
    Embed all ExperienceClaims for the user that are unembedded or were
    embedded with a different model than settings.embedding_model.

    Commits after processing. Non-fatal — per-chunk failures are logged and skipped.
    """
    from app.models.database import ExperienceClaim

    chunks = (
        db.query(ExperienceClaim)
        .filter(
            ExperienceClaim.user_id == user_id,
            or_(
                ExperienceClaim.embedding.is_(None),
                ExperienceClaim.embedding_model != settings.embedding_model,
            ),
        )
        .all()
    )

    if not chunks:
        return

    _start = _time.perf_counter()
    embedded = 0
    for chunk in chunks:
        try:
            chunk.embedding = embed_text(
                _embedding_text(chunk), embed_context="experience_claim_embed"
            )
            chunk.embedding_model = settings.embedding_model
            embedded += 1
        except Exception:
            logger.warning("embed_chunk_failed", chunk_id=str(chunk.id))

    if embedded:
        db.commit()

    duration_ms = int((_time.perf_counter() - _start) * 1000)
    logger.info(
        "embed_experience_chunks_complete",
        embedded=embedded,
        total=len(chunks),
        duration_ms=duration_ms,
    )


def embed_experience_chunks_task(
    user_id: uuid.UUID,
    correlation_id: str | None = None,
) -> None:
    """Background-task variant of embed_experience_chunks. Creates its own DB session."""
    from app.clients.database import SessionLocal

    structlog.contextvars.clear_contextvars()
    ctx: dict = {"user_id": str(user_id)}
    if correlation_id:
        ctx["correlation_id"] = correlation_id
    structlog.contextvars.bind_contextvars(**ctx)

    db = SessionLocal()
    try:
        embed_experience_chunks(user_id, db)
    except Exception:
        logger.exception("embed_experience_chunks_task_failed")
    finally:
        db.close()


def embed_job_chunks(job_id: uuid.UUID, db: Session) -> None:
    """
    Embed all JobChunks for the job that are unembedded or stale.
    Non-fatal — per-chunk failures are logged and skipped.
    """
    from app.models.database import JobChunk

    chunks = (
        db.query(JobChunk)
        .filter(
            JobChunk.job_id == job_id,
            or_(
                JobChunk.embedding.is_(None),
                JobChunk.embedding_model != settings.embedding_model,
            ),
        )
        .all()
    )

    if not chunks:
        return

    embedded = 0
    for chunk in chunks:
        try:
            chunk.embedding = embed_text(chunk.content, embed_context="job_chunk_embed")
            chunk.embedding_model = settings.embedding_model
            embedded += 1
        except Exception:
            logger.warning("embed_job_chunk_failed", chunk_id=str(chunk.id), job_id=str(job_id))

    if embedded:
        db.commit()

    logger.debug("embed_job_chunks_progress", embedded=embedded, total=len(chunks))


def re_embed_chunk(chunk_id: uuid.UUID) -> None:
    """
    Re-embed a single ExperienceClaim. Creates its own DB session.
    Called as a BackgroundTask when chunk content is updated via PATCH.
    """
    from app.clients.database import SessionLocal
    from app.models.database import ExperienceClaim

    db = SessionLocal()
    try:
        chunk = db.get(ExperienceClaim, chunk_id)
        if not chunk:
            logger.warning("re_embed_chunk_not_found", chunk_id=str(chunk_id))
            return

        chunk.embedding = embed_text(_embedding_text(chunk), embed_context="experience_claim_embed")
        chunk.embedding_model = settings.embedding_model
        db.commit()
        logger.debug("re_embed_chunk_complete", chunk_id=str(chunk_id))
    except Exception:
        logger.exception("re_embed_chunk_failed", chunk_id=str(chunk_id))
    finally:
        db.close()

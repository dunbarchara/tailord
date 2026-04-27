"""
experience_embedder.py — embed ExperienceChunk and JobChunk rows after write.

Public functions
----------------
embed_experience_chunks(experience_id, db)
    Embed all unembedded / stale ExperienceChunks. Uses provided session.
    Called inline from background tasks (SSE stream, github_enricher).

embed_experience_chunks_task(experience_id)
    Background-task variant: creates its own DB session.
    Used from request handlers (set_user_input) where the request session
    must not be held open across async work.

embed_job_chunks(job_id, db)
    Embed all unembedded / stale JobChunks. Uses provided session.
    Called inline from chunk_matcher.enrich_job_chunks.

re_embed_chunk(chunk_id)
    Re-embed a single ExperienceChunk. Creates its own DB session.
    Used as a BackgroundTask from PATCH /experience/chunks/{id}.

All functions are non-fatal: per-chunk failures are logged as warnings and
skipped. The pipeline continues regardless of embedding errors.
"""

import logging
import uuid

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.clients.embedding_client import embed_text
from app.config import settings

logger = logging.getLogger(__name__)


def embed_experience_chunks(experience_id: uuid.UUID, db: Session) -> None:
    """
    Embed all ExperienceChunks for the experience that are unembedded or were
    embedded with a different model than settings.embedding_model.

    Commits after processing. Non-fatal — per-chunk failures are logged and skipped.
    """
    from app.models.database import ExperienceChunk

    chunks = (
        db.query(ExperienceChunk)
        .filter(
            ExperienceChunk.experience_id == experience_id,
            or_(
                ExperienceChunk.embedding.is_(None),
                ExperienceChunk.embedding_model != settings.embedding_model,
            ),
        )
        .all()
    )

    if not chunks:
        return

    embedded = 0
    for chunk in chunks:
        try:
            chunk.embedding = embed_text(chunk.content)
            chunk.embedding_model = settings.embedding_model
            embedded += 1
        except Exception:
            logger.warning(
                "embed_experience_chunks: failed for chunk=%s experience=%s",
                chunk.id,
                experience_id,
            )

    if embedded:
        db.commit()

    logger.debug(
        "embed_experience_chunks: %d/%d embedded for experience=%s",
        embedded,
        len(chunks),
        experience_id,
    )


def embed_experience_chunks_task(experience_id: uuid.UUID) -> None:
    """Background-task variant of embed_experience_chunks. Creates its own DB session."""
    from app.clients.database import SessionLocal

    db = SessionLocal()
    try:
        embed_experience_chunks(experience_id, db)
    except Exception:
        logger.exception("embed_experience_chunks_task: failed for experience=%s", experience_id)
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
            chunk.embedding = embed_text(chunk.content)
            chunk.embedding_model = settings.embedding_model
            embedded += 1
        except Exception:
            logger.warning("embed_job_chunks: failed for chunk=%s job=%s", chunk.id, job_id)

    if embedded:
        db.commit()

    logger.debug("embed_job_chunks: %d/%d embedded for job=%s", embedded, len(chunks), job_id)


def re_embed_chunk(chunk_id: uuid.UUID) -> None:
    """
    Re-embed a single ExperienceChunk. Creates its own DB session.
    Called as a BackgroundTask when chunk content is updated via PATCH.
    """
    from app.clients.database import SessionLocal
    from app.models.database import ExperienceChunk

    db = SessionLocal()
    try:
        chunk = db.get(ExperienceChunk, chunk_id)
        if not chunk:
            logger.warning("re_embed_chunk: chunk %s not found", chunk_id)
            return

        chunk.embedding = embed_text(chunk.content)
        chunk.embedding_model = settings.embedding_model
        db.commit()
        logger.debug("re_embed_chunk: embedded chunk=%s", chunk_id)
    except Exception:
        logger.exception("re_embed_chunk: failed for chunk=%s", chunk_id)
    finally:
        db.close()

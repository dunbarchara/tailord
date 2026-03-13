import logging
import uuid
from datetime import datetime, timezone

from app.clients.llm_client import get_llm_client
from app.config import settings
from app.core.llm_utils import llm_parse
from app.prompts import chunk_matching as prompt
from app.schemas.matching import ChunkMatchBatch, ChunkMatchResult
from app.services.chunk_extractor import extract_chunks
from app.services.tailoring_generator import _format_sourced_profile

logger = logging.getLogger(__name__)

BATCH_SIZE = 5  # Smaller batches improve JSON completion reliability on local/smaller models


def enrich_job_chunks(job_id: uuid.UUID, job_markdown: str, extracted_profile: dict) -> None:
    """
    Background task: extract chunks from job markdown, match against candidate profile,
    and persist JobChunk rows to DB. Sets enrichment_status on related tailorings.

    Creates its own DB session — do not pass a session across thread boundaries.
    """
    from app.clients.database import SessionLocal
    from app.models.database import JobChunk, Tailoring

    logger.info("enrich_job_chunks start: job_id=%s", job_id)

    db = SessionLocal()
    try:
        # Delete existing chunks for idempotent re-enrichment
        db.query(JobChunk).filter(JobChunk.job_id == job_id).delete()
        db.commit()

        chunks = extract_chunks(job_markdown)
        if not chunks:
            logger.info("enrich_job_chunks: no chunks extracted for job_id=%s", job_id)
            _set_enrichment_status(db, Tailoring, job_id, "complete")
            db.commit()
            return

        formatted_profile = _format_sourced_profile(extracted_profile)

        # Group non-header chunks by section, preserving original order
        from collections import OrderedDict
        section_map: OrderedDict[str, list] = OrderedDict()
        for chunk in chunks:
            if chunk.chunk_type == "header":
                continue
            key = chunk.section or "General"
            section_map.setdefault(key, []).append(chunk)

        # Map chunk position → match result for final assembly
        result_map: dict[int, ChunkMatchResult] = {}

        for section, section_chunks in section_map.items():
            for batch_start in range(0, len(section_chunks), BATCH_SIZE):
                batch = section_chunks[batch_start: batch_start + BATCH_SIZE]

                chunks_block = "\n".join(
                    f"{idx}. [{c.chunk_type.upper()}] {c.content}"
                    for idx, c in enumerate(batch, start=1)
                )

                try:
                    result = llm_parse(
                        get_llm_client(),
                        model=settings.llm_model,
                        messages=[
                            {"role": "system", "content": prompt.SYSTEM},
                            {"role": "user", "content": prompt.USER_TEMPLATE.format(
                                extracted_profile=formatted_profile,
                                section=section,
                                chunks_block=chunks_block,
                            )},
                        ],
                        response_model=ChunkMatchBatch,
                        temperature=prompt.TEMPERATURE,
                    )
                    batch_results = result.results
                except Exception:
                    logger.exception(
                        "enrich_job_chunks: LLM batch failed for job_id=%s section=%r batch_start=%d",
                        job_id, section, batch_start,
                    )
                    batch_results = []

                # Pad results if LLM returned fewer than chunks sent
                while len(batch_results) < len(batch):
                    batch_results.append(ChunkMatchResult(score=0, rationale="Not evaluated (batch error)"))

                for chunk, match in zip(batch, batch_results):
                    result_map[chunk.position] = match

        # Build ordered results list (header chunks get a -1 placeholder)
        all_results: list[tuple] = []  # (chunk, match_result)
        for chunk in chunks:
            if chunk.chunk_type == "header":
                all_results.append((chunk, ChunkMatchResult(score=-1, rationale="Section header")))
            else:
                all_results.append((chunk, result_map.get(chunk.position, ChunkMatchResult(score=0, rationale="Not evaluated"))))

        # Persist JobChunk rows
        now = datetime.now(timezone.utc)
        for chunk, match in all_results:
            job_chunk = JobChunk(
                job_id=job_id,
                chunk_type=chunk.chunk_type,
                content=chunk.content,
                position=chunk.position,
                section=chunk.section,
                match_score=match.score,
                match_rationale=match.rationale,
                experience_source=match.experience_source,
                should_render=match.should_render,
                enriched_at=now,
            )
            db.add(job_chunk)

        _set_enrichment_status(db, Tailoring, job_id, "complete")
        db.commit()
        logger.info("enrich_job_chunks complete: job_id=%s chunks=%d", job_id, len(chunks))

    except Exception:
        logger.exception("enrich_job_chunks failed for job_id=%s", job_id)
        try:
            from app.models.database import Tailoring as _Tailoring
            _set_enrichment_status(db, _Tailoring, job_id, "error")
            db.commit()
        except Exception:
            logger.exception("enrich_job_chunks: failed to set error status for job_id=%s", job_id)
    finally:
        db.close()
        logger.debug("enrich_job_chunks: DB session closed for job_id=%s", job_id)


def _set_enrichment_status(db, tailoring_model, job_id: uuid.UUID, status: str) -> None:
    db.query(tailoring_model).filter(
        tailoring_model.job_id == job_id
    ).update({"enrichment_status": status})

import logging
import uuid
from collections import OrderedDict
from datetime import datetime, timezone

from app.clients.llm_client import get_llm_client
from app.config import settings
from app.core.llm_utils import llm_parse_with_retry
from app.prompts import chunk_matching as prompt
from app.schemas.matching import ChunkMatchBatch, ChunkMatchResult
from app.services.chunk_extractor import extract_chunks
from app.services.tailoring_generator import _format_sourced_profile

logger = logging.getLogger(__name__)

BATCH_SIZE = (
    3  # Smaller batches reduce output token count — advocacy_blurb roughly doubles output length
)

# ---------------------------------------------------------------------------
# Vector-path helpers
# ---------------------------------------------------------------------------


def _build_candidate_header(candidate_name: str | None, pronouns: str | None) -> str:
    """Build the [CANDIDATE] block for the vector scoring prompt."""
    lines = []
    if candidate_name:
        lines.append(f"Name: {candidate_name}")
    if pronouns:
        lines.append(
            f"Pronouns: {pronouns} — use these when referring to the candidate in third person."
        )
    if not lines:
        return ""
    return "[CANDIDATE]\n" + "\n".join(lines)


def _retrieve_top_k_experience_chunks(
    job_chunk_embedding: list[float],
    experience_id: uuid.UUID,
    db,
    k: int,
) -> list:
    """
    Return the top-K ExperienceChunk rows most similar to job_chunk_embedding,
    ordered by cosine similarity (closest first).

    Scoped to the given experience_id. Skips chunks with null embeddings.
    """
    from app.models.database import ExperienceChunk

    return (
        db.query(ExperienceChunk)
        .filter(
            ExperienceChunk.experience_id == experience_id,
            ExperienceChunk.embedding.isnot(None),
        )
        .order_by(ExperienceChunk.embedding.cosine_distance(job_chunk_embedding))
        .limit(k)
        .all()
    )


def _build_grouped_context(chunks: list) -> str:
    """
    Format a list of ExperienceChunk rows into a grouped, human-readable context block.

    Groups chunks by (group_key, date_range, source_type) so the LLM sees them as
    coherent work-experience entries / projects / GitHub repos, not isolated facts.
    Chunks without a group_key (typically skills / other) are rendered as flat bullets.
    """
    groups: OrderedDict[tuple, list] = OrderedDict()
    ungrouped: list = []

    for chunk in chunks:
        if chunk.group_key:
            key = (chunk.group_key, chunk.date_range or "", chunk.source_type)
            groups.setdefault(key, []).append(chunk)
        else:
            ungrouped.append(chunk)

    lines: list[str] = []

    for (group_key, date_range, source_type), group_chunks in groups.items():
        if source_type == "github":
            techs = group_chunks[0].technologies or []
            tech_str = f"  ({', '.join(techs)})" if techs else ""
            header = f"GitHub: {group_key}{tech_str}"
        else:
            header = group_key
            if date_range:
                header += f"  ({date_range})"
        lines.append(header)
        for c in group_chunks:
            lines.append(f"  • {c.content}")
        lines.append("")

    if ungrouped:
        candidate_notes = [
            c for c in ungrouped if c.source_type in ("gap_response", "additional_experience")
        ]
        other = [
            c for c in ungrouped if c.source_type not in ("gap_response", "additional_experience")
        ]
        if candidate_notes:
            lines.append("Candidate Notes")
            for c in candidate_notes:
                lines.append(f"  • {c.content}")
            lines.append("")
        for c in other:
            lines.append(f"  • {c.content}")

    return "\n".join(lines).strip()


def _score_chunk_vector(
    chunk_content: str,
    chunk_type: str,
    chunk_section: str | None,
    experience_id: uuid.UUID,
    db,
    candidate_header: str,
    k: int,
) -> tuple[ChunkMatchResult, list[float]]:
    """
    Score a single job chunk using vector pre-selection.

    Embeds chunk_content, retrieves the top-K most similar ExperienceChunks,
    builds a grouped context block, then calls the LLM for a single score + blurb.

    Returns (ChunkMatchResult, job_chunk_embedding). Raises on any failure —
    callers are responsible for exception handling and error counting.
    """
    from app.clients.embedding_client import embed_text

    job_chunk_embedding = embed_text(chunk_content)

    top_k_chunks = _retrieve_top_k_experience_chunks(job_chunk_embedding, experience_id, db, k)
    if not top_k_chunks:
        return (
            ChunkMatchResult(score=-1, rationale="No embedded experience chunks available"),
            job_chunk_embedding,
        )

    grouped_context = _build_grouped_context(top_k_chunks)

    def _validate_single(r: ChunkMatchBatch) -> None:
        if not r.results:
            raise ValueError("results list is empty — score the chunk")
        item = r.results[0]
        if item.score in (1, 2) and not (item.advocacy_blurb and item.advocacy_blurb.strip()):
            raise ValueError(
                f"score={item.score} but advocacy_blurb is empty"
                " — populate it with a 1–2 sentence third-person advocacy statement"
            )

    result = llm_parse_with_retry(
        get_llm_client(),
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": prompt.SYSTEM},
            {
                "role": "user",
                "content": prompt.USER_TEMPLATE_VECTOR.format(
                    candidate_header=candidate_header,
                    job_requirement=f"[{chunk_type.upper()}] {chunk_content}",
                    grouped_context=grouped_context,
                    k=len(top_k_chunks),
                ),
            },
        ],
        response_model=ChunkMatchBatch,
        temperature=prompt.TEMPERATURE,
        validate_fn=_validate_single,
    )

    raw = (
        result.results[0]
        if result.results
        else ChunkMatchResult(score=-1, rationale="Not evaluated")
    )
    annotated = ChunkMatchResult(
        score=raw.score,
        rationale=f"[vector top-{len(top_k_chunks)}] {raw.rationale}",
        advocacy_blurb=raw.advocacy_blurb,
        experience_sources=raw.experience_sources,
        should_render=raw.should_render,
    )
    return annotated, job_chunk_embedding


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def enrich_job_chunks(
    job_id: uuid.UUID,
    job_markdown: str,
    extracted_profile: dict,
    pronouns: str | None = None,
    experience_id: uuid.UUID | None = None,
    candidate_name: str | None = None,
) -> None:
    """
    Background task: extract chunks from job markdown, match against candidate profile,
    and persist JobChunk rows to DB. Sets enrichment_status on related tailorings.

    Dispatches based on settings.matching_mode:
      - "vector": cosine pre-selection → focused grouped context → one LLM call per chunk.
                  Requires experience_id; falls back to llm mode if missing.
      - "llm":    full formatted profile → batched LLM calls (default).

    Creates its own DB session — do not pass a session across thread boundaries.
    """
    from app.clients.database import SessionLocal
    from app.models.database import JobChunk, Tailoring

    logger.info("enrich_job_chunks start: job_id=%s mode=%s", job_id, settings.matching_mode)

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

        # Determine effective mode
        use_vector = settings.matching_mode == "vector" and experience_id is not None
        if settings.matching_mode == "vector" and experience_id is None:
            logger.warning(
                "enrich_job_chunks: MATCHING_MODE=vector but experience_id not provided"
                " — falling back to llm mode for job_id=%s",
                job_id,
            )

        result_map: dict[int, ChunkMatchResult] = {}
        embedding_map: dict[int, list[float]] = {}  # populated only in vector mode
        batch_count = 0
        error_count = 0

        if use_vector:
            candidate_header = _build_candidate_header(candidate_name, pronouns)
            k = settings.vector_top_k

            for chunk in chunks:
                if chunk.chunk_type == "header":
                    continue  # handled in "Build ordered results" below

                batch_count += 1
                try:
                    match, embedding = _score_chunk_vector(
                        chunk.content,
                        chunk.chunk_type,
                        chunk.section,
                        experience_id,
                        db,
                        candidate_header,
                        k,
                    )
                    result_map[chunk.position] = match
                    embedding_map[chunk.position] = embedding
                except Exception:
                    logger.exception(
                        "enrich_job_chunks: vector scoring failed job_id=%s position=%d",
                        job_id,
                        chunk.position,
                    )
                    error_count += 1
                    result_map[chunk.position] = ChunkMatchResult(
                        score=-1, rationale="Not evaluated (vector error)"
                    )

        else:
            # LLM path: full profile, batched per section
            formatted_profile = _format_sourced_profile(extracted_profile, pronouns=pronouns)

            section_map: OrderedDict[str, list] = OrderedDict()
            for chunk in chunks:
                if chunk.chunk_type == "header":
                    continue
                key = chunk.section or "General"
                section_map.setdefault(key, []).append(chunk)

            for section, section_chunks in section_map.items():
                last_paragraph: str | None = None

                for batch_start in range(0, len(section_chunks), BATCH_SIZE):
                    batch = section_chunks[batch_start : batch_start + BATCH_SIZE]
                    batch_count += 1

                    preceding = ""
                    if last_paragraph is not None:
                        preceding = (
                            f"PRECEDING CONTEXT (do not score):\n[PARAGRAPH] {last_paragraph}\n\n"
                        )

                    for c in batch:
                        if c.chunk_type == "paragraph":
                            last_paragraph = c.content

                    chunks_block = preceding + "\n".join(
                        f"{idx}. [{c.chunk_type.upper()}] {c.content}"
                        for idx, c in enumerate(batch, start=1)
                    )

                    def _validate_batch(r: ChunkMatchBatch) -> None:
                        for i, item in enumerate(r.results):
                            if item.score in (1, 2) and not (
                                item.advocacy_blurb and item.advocacy_blurb.strip()
                            ):
                                raise ValueError(
                                    f"result[{i}] has score={item.score} but advocacy_blurb is empty"
                                    " — populate it with a 1–2 sentence third-person advocacy statement"
                                )

                    try:
                        result = llm_parse_with_retry(
                            get_llm_client(),
                            model=settings.llm_model,
                            messages=[
                                {"role": "system", "content": prompt.SYSTEM},
                                {
                                    "role": "user",
                                    "content": prompt.USER_TEMPLATE.format(
                                        extracted_profile=formatted_profile,
                                        section=section,
                                        chunks_block=chunks_block,
                                    ),
                                },
                            ],
                            response_model=ChunkMatchBatch,
                            temperature=prompt.TEMPERATURE,
                            validate_fn=_validate_batch,
                        )
                        batch_results = result.results
                    except Exception:
                        logger.exception(
                            "enrich_job_chunks: LLM batch failed for job_id=%s section=%r batch_start=%d",
                            job_id,
                            section,
                            batch_start,
                        )
                        error_count += 1
                        batch_results = []

                    # Pad results if LLM returned fewer than chunks sent
                    while len(batch_results) < len(batch):
                        batch_results.append(
                            ChunkMatchResult(score=-1, rationale="Not evaluated (batch error)")
                        )

                    for chunk, match in zip(batch, batch_results):
                        result_map[chunk.position] = match

        # Build ordered results list (header chunks get a -1 placeholder)
        all_results: list[tuple] = []
        for chunk in chunks:
            if chunk.chunk_type == "header":
                all_results.append((chunk, ChunkMatchResult(score=-1, rationale="Section header")))
            else:
                all_results.append(
                    (
                        chunk,
                        result_map.get(
                            chunk.position, ChunkMatchResult(score=-1, rationale="Not evaluated")
                        ),
                    )
                )

        # Persist JobChunk rows. In vector mode, pre-populate embeddings so
        # embed_job_chunks at the end skips chunks already embedded.
        now = datetime.now(timezone.utc)
        for chunk, match in all_results:
            embedding = embedding_map.get(chunk.position) if use_vector else None
            job_chunk = JobChunk(
                job_id=job_id,
                chunk_type=chunk.chunk_type,
                content=chunk.content,
                position=chunk.position,
                section=chunk.section,
                match_score=match.score,
                match_rationale=match.rationale,
                advocacy_blurb=match.advocacy_blurb,
                experience_sources=match.experience_sources or [],
                should_render=match.should_render,
                enriched_at=now,
                embedding=embedding,
                embedding_model=settings.embedding_model if embedding is not None else None,
            )
            db.add(job_chunk)

        db.query(Tailoring).filter(Tailoring.job_id == job_id).update(
            {
                "enrichment_status": "complete",
                "chunk_batch_count": batch_count,
                "chunk_error_count": error_count,
            }
        )
        db.commit()

        from app.services.experience_embedder import embed_job_chunks

        embed_job_chunks(job_id, db)  # no-op for chunks already embedded in vector mode

        logger.info(
            "enrich_job_chunks complete: job_id=%s mode=%s chunks=%d batches=%d errors=%d",
            job_id,
            "vector" if use_vector else "llm",
            len(chunks),
            batch_count,
            error_count,
        )

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


def re_enrich_single_chunk(
    chunk_id: str,
    extracted_profile: dict,
    pronouns: str | None = None,
    experience_id: uuid.UUID | None = None,
    candidate_name: str | None = None,
) -> None:
    """
    Re-score one JobChunk against an updated profile.

    Used when a gap answer is submitted — avoids re-processing the entire job.
    Dispatches to vector or llm mode based on settings.matching_mode.
    Creates its own DB session — do not pass a session across thread boundaries.
    """
    from app.clients.database import SessionLocal
    from app.models.database import JobChunk

    logger.info(
        "re_enrich_single_chunk: start chunk_id=%s mode=%s", chunk_id, settings.matching_mode
    )

    db = SessionLocal()
    try:
        chunk = db.get(JobChunk, chunk_id)
        if not chunk:
            logger.warning("re_enrich_single_chunk: chunk %s not found", chunk_id)
            return

        use_vector = settings.matching_mode == "vector" and experience_id is not None

        if use_vector:
            candidate_header = _build_candidate_header(candidate_name, pronouns)
            k = settings.vector_top_k
            match, new_embedding = _score_chunk_vector(
                chunk.content,
                chunk.chunk_type,
                chunk.section,
                experience_id,
                db,
                candidate_header,
                k,
            )
            # Opportunistically update the chunk's embedding if it was missing
            if chunk.embedding is None and new_embedding is not None:
                chunk.embedding = new_embedding
                chunk.embedding_model = settings.embedding_model
        else:
            formatted_profile = _format_sourced_profile(extracted_profile, pronouns=pronouns)

            section = chunk.section or "General"
            chunks_block = f"1. [{chunk.chunk_type.upper()}] {chunk.content}"

            def _validate_single(r: ChunkMatchBatch) -> None:
                if not r.results:
                    raise ValueError("results list is empty — score the chunk")
                item = r.results[0]
                if item.score in (1, 2) and not (
                    item.advocacy_blurb and item.advocacy_blurb.strip()
                ):
                    raise ValueError(
                        f"score={item.score} but advocacy_blurb is empty"
                        " — populate it with a 1–2 sentence third-person advocacy statement"
                    )

            result = llm_parse_with_retry(
                get_llm_client(),
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": prompt.SYSTEM},
                    {
                        "role": "user",
                        "content": prompt.USER_TEMPLATE.format(
                            extracted_profile=formatted_profile,
                            section=section,
                            chunks_block=chunks_block,
                        ),
                    },
                ],
                response_model=ChunkMatchBatch,
                temperature=prompt.TEMPERATURE,
                validate_fn=_validate_single,
            )

            match = (
                result.results[0]
                if result.results
                else ChunkMatchResult(score=-1, rationale="Not evaluated (re-enrichment failed)")
            )

        now = datetime.now(timezone.utc)
        chunk.match_score = match.score
        chunk.match_rationale = match.rationale
        chunk.advocacy_blurb = match.advocacy_blurb
        chunk.experience_sources = match.experience_sources or []
        chunk.should_render = match.should_render
        chunk.enriched_at = now
        db.commit()

        logger.info(
            "re_enrich_single_chunk: complete chunk_id=%s new_score=%d",
            chunk_id,
            match.score,
        )

    except Exception:
        logger.exception("re_enrich_single_chunk failed for chunk_id=%s", chunk_id)
    finally:
        db.close()


def _set_enrichment_status(db, tailoring_model, job_id: uuid.UUID, status: str) -> None:
    db.query(tailoring_model).filter(tailoring_model.job_id == job_id).update(
        {"enrichment_status": status}
    )

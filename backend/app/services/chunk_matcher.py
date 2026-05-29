import time
import uuid
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timezone

import structlog
from sqlalchemy import text

from app.clients.llm_client import get_llm_client
from app.config import settings
from app.core.llm_utils import llm_parse_with_retry
from app.prompts import chunk_matching as prompt
from app.schemas.matching import ChunkMatchBatch, ChunkMatchResult
from app.services.chunk_display import is_display_ready
from app.services.chunk_extractor import extract_chunks
from app.services.job_bounds_detector import (
    JobContentBounds,
    apply_bounds,
    detect_job_content_bounds,
)
from app.services.profile_formatter import format_sourced_profile

logger = structlog.get_logger(__name__)

# (include_in_scoring, should_render) — None means "use LLM-returned value"
SEMANTIC_TYPE_RULES: dict[str, tuple[bool | None, bool | None]] = {
    "job_requirement": (True, True),
    "role_description": (True, True),
    "company_description": (None, False),  # LLM decides include_in_scoring; render always False
    "compensation": (False, False),
    "location": (False, False),
    "application_info": (False, False),
    "legal": (False, False),
    "other": (None, None),  # LLM decides both
}


def resolve_chunk_flags(result: ChunkMatchResult) -> ChunkMatchResult:
    """Apply SEMANTIC_TYPE_RULES to override include_in_scoring and should_render."""
    include_override, render_override = SEMANTIC_TYPE_RULES.get(
        result.semantic_type, SEMANTIC_TYPE_RULES["other"]
    )
    return ChunkMatchResult(
        score=result.score,
        rationale=result.rationale,
        advocacy_blurb=result.advocacy_blurb,
        experience_sources=result.experience_sources,
        should_render=render_override if render_override is not None else result.should_render,
        include_in_scoring=include_override
        if include_override is not None
        else result.include_in_scoring,
        semantic_type=result.semantic_type,
    )


def _derive_evaluation_status(match: ChunkMatchResult, chunk_type: str) -> str | None:
    if chunk_type == "header":
        return "skipped"
    if not match.include_in_scoring:
        return "skipped"
    if match.score in (0, 1, 2):
        return "scored"
    if match.score == -1 and "error" in (match.rationale or "").lower():
        return "error"
    if match.score == -1:
        return "skipped"
    return None


BATCH_SIZE = (
    3  # Smaller batches reduce output token count — advocacy_blurb roughly doubles output length
)

# Hard ceiling on the entire chunk-scoring phase. LLM calls use a per-request HTTP timeout
# (120 s) but streaming LLM servers can bypass it by trickling tokens. This wall-clock budget
# covers the full parallel batch regardless of LLM speed. Futures that have not completed when
# this expires are abandoned (executor.shutdown(wait=False)) — their threads drain in the
# background when the HTTP timeout eventually fires.
_CHUNK_SCORING_TIMEOUT_SECONDS = 300  # 5 minutes


# ---------------------------------------------------------------------------
# Module-level validators (replace identical inline closures)
# ---------------------------------------------------------------------------


def _validate_chunk_batch(r: ChunkMatchBatch) -> None:
    """Validate that all scored chunks with score>=1 have an advocacy_blurb."""
    for i, item in enumerate(r.results):
        if item.score in (1, 2) and not (item.advocacy_blurb and item.advocacy_blurb.strip()):
            raise ValueError(
                f"result[{i}] has score={item.score} but advocacy_blurb is empty"
                " — populate it with a 1–2 sentence third-person advocacy statement"
            )


def _validate_single_chunk(r: ChunkMatchBatch) -> None:
    """Validate a single-chunk batch result."""
    if not r.results:
        raise ValueError("results list is empty — score the chunk")
    item = r.results[0]
    if item.score in (1, 2) and not (item.advocacy_blurb and item.advocacy_blurb.strip()):
        raise ValueError(
            f"score={item.score} but advocacy_blurb is empty"
            " — populate it with a 1–2 sentence third-person advocacy statement"
        )


# ---------------------------------------------------------------------------
# Vector-path helpers
# ---------------------------------------------------------------------------


def _build_candidate_header(
    candidate_name: str | None,
    pronouns: str | None,
    signals: str | None = None,
) -> str:
    """Build the [CANDIDATE] + [COMPUTED SIGNALS] block for the vector scoring prompt.

    signals should be the output of compute_profile_signals() — total YOE and role
    list. Including it in the vector path ensures YOE threshold requirements are
    scored correctly without requiring the LLM to re-derive totals from partial
    context (the top-K claims alone don't cover all roles).
    """
    lines = []
    if candidate_name:
        lines.append(f"Name: {candidate_name}")
    if pronouns:
        lines.append(
            f"Pronouns: {pronouns} — use these when referring to the candidate in third person."
        )
    parts = []
    if lines:
        parts.append("[CANDIDATE]\n" + "\n".join(lines))
    if signals:
        parts.append(f"[COMPUTED SIGNALS — treat as ground truth]\n{signals}")
    return "\n\n".join(parts)


# Maximum matched skill claims to retrieve per chunk evaluation.
# Skills are aggregated into one line per source in the context, so this does not
# consume substantive claim slots — it is a separate, capped retrieval pass.
K_SKILLS = 6


def _retrieve_top_k_experience_chunks(
    job_chunk_embedding: list[float],
    user_id: uuid.UUID,
    db,
    k: int,
) -> list:
    """
    Return the top-K substantive ExperienceClaim rows most similar to
    job_chunk_embedding, plus up to K_SKILLS matched skill claims.

    Two separate queries are run so skill claims never displace substantive
    work-experience/project bullets in the top-K slots:
      1. Non-skill claims (work_experience, project, other): top-k by cosine distance
      2. Skill claims only: top-K_SKILLS by cosine distance

    Both result sets are returned combined. Skill claims are rendered as a single
    aggregated line in _build_grouped_context rather than as individual bullets.

    Scoped to the given user_id. Skips claims with null embeddings.
    Groups (and their parents) are eager-loaded so they remain accessible
    after the session is closed.
    """
    from sqlalchemy.orm import joinedload

    from app.models.database import ExperienceClaim, ExperienceGroup

    base_filters = [
        ExperienceClaim.user_id == user_id,
        ExperienceClaim.embedding.isnot(None),
        ExperienceClaim.status == "active",
    ]
    opts = joinedload(ExperienceClaim.group).joinedload(ExperienceGroup.parent)

    substantive = (
        db.query(ExperienceClaim)
        .options(opts)
        .filter(*base_filters, ExperienceClaim.claim_type != "skill")
        .order_by(ExperienceClaim.embedding.cosine_distance(job_chunk_embedding))
        .limit(k)
        .all()
    )

    skills = (
        db.query(ExperienceClaim)
        .options(opts)
        .filter(*base_filters, ExperienceClaim.claim_type == "skill")
        .order_by(ExperienceClaim.embedding.cosine_distance(job_chunk_embedding))
        .limit(K_SKILLS)
        .all()
    )

    return substantive + skills


def _source_label(chunk) -> str:
    """Return the inline source label for a claim, e.g. '[resume]' or '[github: tailord]'."""
    if chunk.source_type == "github":
        ref = getattr(chunk, "source_ref", None)
        group_obj = getattr(chunk, "group", None)
        ref = ref or (group_obj.name if group_obj else "github")
        return f"[github: {ref}]"
    return f"[{chunk.source_type}]"


def _format_skill_lines(skill_chunks: list, *, bullet: str = "  •") -> list[str]:
    """
    Aggregate skill claims into one line per source ref so they don't consume
    individual context slots.

    Default (ungrouped global section):
      • TypeScript, React, PostgreSQL  [resume]

    Inline within a role bucket (bullet="  Skills:"):
      Skills: TypeScript, React, PostgreSQL  [resume]
    """
    # Group by (source_type, source_ref) to keep source attribution accurate
    from collections import defaultdict

    buckets: dict = defaultdict(list)
    for c in skill_chunks:
        ref = getattr(c, "source_ref", None) or c.source_type
        key = (c.source_type, ref)
        buckets[key].append(c.content)

    lines = []
    for (source_type, ref), contents in buckets.items():
        joined = ", ".join(contents)
        if source_type == "github":
            label = f"  [github: {ref}]"
        else:
            label = f"  [{source_type}]"
        lines.append(f"{bullet} {joined}{label}")
    return lines


def _build_grouped_context(chunks: list) -> str:
    """
    Format a list of ExperienceClaim rows into a grouped, human-readable context block.

    Primary path: claims with group_id set are bucketed by their effective group.
    If a claim's group has parent_group_id, it is bucketed under the parent (role)
    group so linked resume + GitHub evidence is presented as a unified block.

    Legacy path: claims without group_id fall back to (group_key, date_range,
    source_type) tuple grouping (unchanged from before).

    Skill claims are aggregated into one line per source within each bucket rather
    than rendered individually — this prevents skills from displacing substantive
    work-experience bullets in the LLM's reasoning context.

    When a bucket contains non-skill claims from multiple source_types, inline
    source labels are appended so the LLM can distinguish resume bullets from
    GitHub evidence.
    """
    # Each bucket is either:
    #   FK-based:     {"fk": True, "group": ExperienceGroup, "claims": [...]}
    #   Legacy-based: {"fk": False, "group_key": str, "date_range": str, "source_type": str, "claims": [...]}
    bucket_order: list = []  # ordered list of keys
    buckets: OrderedDict = OrderedDict()
    ungrouped: list = []

    for chunk in chunks:
        group_id = getattr(chunk, "group_id", None)
        group_obj = getattr(chunk, "group", None)

        if group_id and group_obj:
            # Bucket under parent group if this group is a child
            parent = getattr(group_obj, "parent", None)
            effective = (
                parent if (getattr(group_obj, "parent_group_id", None) and parent) else group_obj
            )
            key = str(effective.id)
            if key not in buckets:
                bucket_order.append(key)
                buckets[key] = {"fk": True, "group": effective, "claims": []}
            buckets[key]["claims"].append(chunk)
        elif getattr(chunk, "group_key", None):
            key = (chunk.group_key, chunk.date_range or "", chunk.source_type)
            if key not in buckets:
                bucket_order.append(key)
                buckets[key] = {
                    "fk": False,
                    "group_key": chunk.group_key,
                    "date_range": chunk.date_range or "",
                    "source_type": chunk.source_type,
                    "claims": [],
                }
            buckets[key]["claims"].append(chunk)
        else:
            ungrouped.append(chunk)

    lines: list[str] = []

    for key in bucket_order:
        bucket = buckets[key]
        group_chunks = bucket["claims"]
        skill_chunks = [c for c in group_chunks if getattr(c, "claim_type", None) == "skill"]
        substantive_chunks = [c for c in group_chunks if getattr(c, "claim_type", None) != "skill"]

        if bucket["fk"]:
            g = bucket["group"]
            if g.source_type == "github":
                techs = group_chunks[0].keywords or [] if group_chunks else []
                tech_str = f"  ({', '.join(techs)})" if techs else ""
                header = f"GitHub: {g.name}{tech_str}"
            else:
                # Use date_range from claims (role groups may not store dates)
                date_ranges = [c.date_range for c in group_chunks if getattr(c, "date_range", None)]
                date_str = date_ranges[0] if date_ranges else None
                header = g.name
                if date_str:
                    header += f"  ({date_str})"
        else:
            group_key = bucket["group_key"]
            date_range = bucket["date_range"]
            source_type = bucket["source_type"]
            if source_type == "github":
                techs = group_chunks[0].keywords or [] if group_chunks else []
                tech_str = f"  ({', '.join(techs)})" if techs else ""
                header = f"GitHub: {group_key}{tech_str}"
            else:
                header = group_key
                if date_range:
                    header += f"  ({date_range})"

        lines.append(header)

        # Render substantive claims as individual bullets.
        # Add source label when multiple source_types are present in a FK bucket.
        has_mixed = bucket["fk"] and len({c.source_type for c in substantive_chunks}) > 1
        for c in substantive_chunks:
            if has_mixed:
                label = f"  {_source_label(c)}"
                lines.append(f"  • {c.content}{label}")
            else:
                lines.append(f"  • {c.content}")

        # Aggregate skill claims inline: "  Skills: TypeScript, React  [resume]"
        # Using bullet="  Skills:" merges the label onto the same line as the content.
        lines.extend(_format_skill_lines(skill_chunks, bullet="  Skills:"))

        lines.append("")

    if ungrouped:
        candidate_notes = [
            c for c in ungrouped if c.source_type in ("gap_response", "additional_experience")
        ]
        other_ungrouped = [
            c for c in ungrouped if c.source_type not in ("gap_response", "additional_experience")
        ]
        skill_ungrouped = [c for c in other_ungrouped if getattr(c, "claim_type", None) == "skill"]
        substantive_ungrouped = [
            c for c in other_ungrouped if getattr(c, "claim_type", None) != "skill"
        ]

        if candidate_notes:
            lines.append("Candidate Notes")
            for c in candidate_notes:
                lines.append(f"  • {c.content}")
            lines.append("")

        if skill_ungrouped:
            lines.append("Skills")
            lines.extend(_format_skill_lines(skill_ungrouped))
            lines.append("")

        if substantive_ungrouped:
            lines.append("Additional Context")
            for c in substantive_ungrouped:
                lines.append(f"  • {c.content}")
            lines.append("")

    return "\n".join(lines).strip()


def _append_pinned_claims(
    top_k: list,
    job_chunk_id: str,
    user_id: uuid.UUID,
    db,
) -> list:
    """Append active claims explicitly linked to job_chunk_id via provenance_metadata
    if they weren't already selected by cosine retrieval.

    Gap/partial response claims are written specifically to answer a requirement —
    they must always appear in that requirement's scoring context regardless of
    whether they win a natural cosine slot.
    """
    from sqlalchemy.orm import joinedload

    from app.models.database import ExperienceClaim, ExperienceGroup

    pinned = (
        db.query(ExperienceClaim)
        .options(joinedload(ExperienceClaim.group).joinedload(ExperienceGroup.parent))
        .filter(
            ExperienceClaim.user_id == user_id,
            ExperienceClaim.status == "active",
            ExperienceClaim.provenance_metadata["job_chunk_id"].astext == job_chunk_id,
        )
        .all()
    )
    if not pinned:
        return top_k
    existing_ids = {c.id for c in top_k}
    result = list(top_k)
    for claim in pinned:
        if claim.id not in existing_ids:
            result.append(claim)
            logger.debug(
                "pinned_claim_appended",
                claim_id=str(claim.id),
                job_chunk_id=job_chunk_id,
            )
    return result


def _score_chunk_vector(
    chunk_content: str,
    chunk_type: str,
    chunk_section: str | None,
    user_id: uuid.UUID,
    candidate_header: str,
    k: int,
    force_score: bool = False,
    prompt_name: str | None = None,
    pinned_job_chunk_id: str | None = None,
) -> tuple[ChunkMatchResult, list[float]]:
    """
    Score a single job chunk using vector pre-selection.

    Embeds chunk_content, retrieves the top-K most similar ExperienceClaims,
    builds a grouped context block, then calls the LLM for a single score + blurb.

    Creates its own DB session — safe to call from threads.

    Returns (ChunkMatchResult, job_chunk_embedding). Raises on any failure —
    callers are responsible for exception handling and error counting.
    """
    from app.clients.database import SessionLocal
    from app.clients.embedding_client import embed_text

    job_chunk_embedding = embed_text(chunk_content, embed_context="job_chunk_embed")

    db = SessionLocal()
    try:
        top_k_chunks = _retrieve_top_k_experience_chunks(job_chunk_embedding, user_id, db, k)
        if pinned_job_chunk_id:
            top_k_chunks = _append_pinned_claims(top_k_chunks, pinned_job_chunk_id, user_id, db)
    finally:
        db.close()

    if not top_k_chunks:
        return (
            ChunkMatchResult(score=-1, rationale="No embedded experience chunks available"),
            job_chunk_embedding,
        )

    grouped_context = _build_grouped_context(top_k_chunks)

    force_score_note = prompt.FORCE_SCORE_NOTE if force_score else ""
    result = llm_parse_with_retry(
        get_llm_client(),
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": prompt.SYSTEM},
            {
                "role": "user",
                "content": prompt.format_user_template_vector(
                    candidate_header=candidate_header,
                    job_requirement=f"[{chunk_type.upper()}] {chunk_content}",
                    grouped_context=grouped_context,
                    k=len(top_k_chunks),
                    force_score_note=force_score_note,
                ),
            },
        ],
        response_model=ChunkMatchBatch,
        temperature=prompt.TEMPERATURE,
        validate_fn=_validate_single_chunk,
        prompt_name=prompt_name or prompt.PROMPT_NAME_VECTOR_SINGLE,
    )

    raw = (
        result.results[0]
        if result.results
        else ChunkMatchResult(score=-1, rationale="Not evaluated")
    )
    logger.debug("top_k_chunks_retrieved", count=len(top_k_chunks))
    annotated = ChunkMatchResult(
        score=raw.score,
        rationale=raw.rationale,
        advocacy_blurb=raw.advocacy_blurb,
        experience_sources=raw.experience_sources,
        should_render=raw.should_render,
        include_in_scoring=raw.include_in_scoring,
        semantic_type=raw.semantic_type,
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
    user_id: uuid.UUID | None = None,
    candidate_name: str | None = None,
    precomputed_bounds: JobContentBounds | None = None,
) -> None:
    """
    Background task: extract chunks from job markdown, match against candidate profile,
    and persist JobChunk rows to DB.

    Dispatches based on settings.matching_mode:
      - "vector": cosine pre-selection → focused grouped context → one LLM call per chunk.
                  Requires user_id; falls back to llm mode if missing.
      - "llm":    full formatted profile → batched LLM calls (default).

    Creates its own DB session — do not pass a session across thread boundaries.
    """
    from app.clients.database import SessionLocal
    from app.models.database import JobChunk

    logger.info("enrich_job_chunks_start", job_id=str(job_id), mode=settings.matching_mode)

    db = SessionLocal()
    try:
        logger.debug("enrich_db_session_opened", job_id=str(job_id))
        db.execute(text("SET LOCAL statement_timeout = '30000'"))  # 30 s for this transaction
        # Delete existing chunks for idempotent re-enrichment
        db.query(JobChunk).filter(JobChunk.job_id == job_id).delete()
        db.commit()
        logger.debug("enrich_delete_committed", job_id=str(job_id))

        # Use pre-computed bounds if provided (set by _finalize_tailoring as a named stage);
        # otherwise detect bounds here (e.g. during refresh or standalone calls).
        bounds = (
            precomputed_bounds
            if precomputed_bounds is not None
            else detect_job_content_bounds(job_markdown)
        )
        pre_seg, core_seg, post_seg = apply_bounds(job_markdown, bounds)
        logger.info(
            "job_bounds_applied",
            job_id=str(job_id),
            has_pre=bool(pre_seg.strip()),
            has_post=bool(post_seg.strip()),
        )

        pre_raw = extract_chunks(pre_seg) if pre_seg.strip() else []
        post_raw = extract_chunks(post_seg) if post_seg.strip() else []

        t0 = time.perf_counter()
        chunks = extract_chunks(core_seg)
        logger.info(
            "chunks_extracted",
            job_id=str(job_id),
            chunk_count=len(chunks),
            excluded_pre=len(pre_raw),
            excluded_post=len(post_raw),
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )

        # Re-number positions sequentially: pre → core → post
        pos = 0
        for c in pre_raw:
            c.position = pos
            pos += 1
        for c in chunks:
            c.position = pos
            pos += 1
        for c in post_raw:
            c.position = pos
            pos += 1

        if not chunks:
            logger.info("enrich_no_chunks", job_id=str(job_id))
            db.commit()
            return

        # Determine effective mode
        use_vector = settings.matching_mode == "vector" and user_id is not None
        if settings.matching_mode == "vector" and user_id is None:
            logger.warning(
                "enrich_job_chunks: MATCHING_MODE=vector but user_id not provided"
                " — falling back to llm mode for job_id=%s",
                job_id,
            )

        result_map: dict[int, ChunkMatchResult] = {}
        embedding_map: dict[int, list[float]] = {}  # populated only in vector mode
        batch_count = 0
        error_count = 0

        # Pre-classify chunks that won't appear in the Posting view (sectionless metadata,
        # noise links). is_display_ready() is the single source of truth — if the frontend
        # won't render it, there is nothing to score against the candidate.
        _pre_classified: set[int] = set()
        for chunk in chunks:
            if chunk.chunk_type == "header":
                continue
            if not is_display_ready(chunk):
                result_map[chunk.position] = ChunkMatchResult(
                    score=-1,
                    rationale="Pre-section metadata — not a scorable requirement.",
                    semantic_type="other",
                    include_in_scoring=False,
                    should_render=False,
                )
                _pre_classified.add(chunk.position)

        if use_vector:
            from app.services.profile_formatter import compute_profile_signals

            signals = compute_profile_signals(extracted_profile) if extracted_profile else None
            candidate_header = _build_candidate_header(candidate_name, pronouns, signals=signals)
            k = settings.vector_top_k
            scoreable = [
                c for c in chunks if c.chunk_type != "header" and c.position not in _pre_classified
            ]
            batch_count += len(scoreable)

            _log_ctx = structlog.contextvars.get_contextvars()

            def _score_one_vector(chunk):
                structlog.contextvars.clear_contextvars()
                structlog.contextvars.bind_contextvars(**_log_ctx)
                return chunk, _score_chunk_vector(
                    chunk.content,
                    chunk.chunk_type,
                    chunk.section,
                    user_id,
                    candidate_header,
                    k,
                    prompt_name=prompt.PROMPT_NAME_VECTOR_BATCH,
                )

            executor = ThreadPoolExecutor(max_workers=settings.chunk_scorer_concurrency)
            futures_map = {executor.submit(_score_one_vector, c): c for c in scoreable}
            done, not_done = wait(list(futures_map.keys()), timeout=_CHUNK_SCORING_TIMEOUT_SECONDS)
            # Don't block on lingering threads — they will drain when the HTTP timeout fires.
            executor.shutdown(wait=False)

            for future in not_done:
                chunk = futures_map[future]
                logger.warning(
                    "chunk_scoring_timeout",
                    job_id=str(job_id),
                    position=chunk.position,
                    mode="vector",
                )
                error_count += 1
                result_map[chunk.position] = ChunkMatchResult(
                    score=-1, rationale="Not evaluated (scoring timeout)"
                )

            for future in done:
                chunk = futures_map[future]
                try:
                    _, (match, embedding) = future.result()
                    result_map[chunk.position] = match
                    embedding_map[chunk.position] = embedding
                except Exception:
                    logger.exception(
                        "chunk_scoring_failed",
                        job_id=str(job_id),
                        position=chunk.position,
                        mode="vector",
                    )
                    error_count += 1
                    result_map[chunk.position] = ChunkMatchResult(
                        score=-1, rationale="Not evaluated (vector error)"
                    )

        else:
            # LLM path: full profile, batched per section
            formatted_profile = format_sourced_profile(extracted_profile, pronouns=pronouns)

            section_map: OrderedDict[str, list] = OrderedDict()
            for chunk in chunks:
                if chunk.chunk_type == "header" or chunk.position in _pre_classified:
                    continue
                key = chunk.section or "General"
                section_map.setdefault(key, []).append(chunk)

            # Collect all (section, batch_start, batch, preceding_paragraph) units upfront
            # so we can submit them all in parallel.
            batch_units: list[tuple[str, int, list, str]] = []
            for section, section_chunks in section_map.items():
                last_paragraph: str | None = None
                for batch_start in range(0, len(section_chunks), BATCH_SIZE):
                    batch = section_chunks[batch_start : batch_start + BATCH_SIZE]
                    preceding = ""
                    if last_paragraph is not None:
                        preceding = (
                            f"PRECEDING CONTEXT (do not score):\n[PARAGRAPH] {last_paragraph}\n\n"
                        )
                    for c in batch:
                        if c.chunk_type == "paragraph":
                            last_paragraph = c.content
                    batch_units.append((section, batch_start, batch, preceding))

            batch_count += len(batch_units)

            _log_ctx = structlog.contextvars.get_contextvars()

            def _run_llm_batch(unit: tuple[str, int, list, str]) -> tuple[list, list]:
                structlog.contextvars.clear_contextvars()
                structlog.contextvars.bind_contextvars(**_log_ctx)
                section, batch_start, batch, preceding = unit
                chunks_block = preceding + "\n".join(
                    f"{idx}. [{c.chunk_type.upper()}] {c.content}"
                    for idx, c in enumerate(batch, start=1)
                )
                result = llm_parse_with_retry(
                    get_llm_client(),
                    model=settings.llm_model,
                    messages=[
                        {"role": "system", "content": prompt.SYSTEM},
                        {
                            "role": "user",
                            "content": prompt.format_user_template(
                                extracted_profile=formatted_profile,
                                section=section,
                                chunks_block=chunks_block,
                            ),
                        },
                    ],
                    response_model=ChunkMatchBatch,
                    temperature=prompt.TEMPERATURE,
                    validate_fn=_validate_chunk_batch,
                    prompt_name=prompt.PROMPT_NAME_BATCH,
                )
                return batch, result.results

            executor = ThreadPoolExecutor(max_workers=settings.chunk_scorer_concurrency)
            futures_map = {executor.submit(_run_llm_batch, unit): unit for unit in batch_units}
            done, not_done = wait(list(futures_map.keys()), timeout=_CHUNK_SCORING_TIMEOUT_SECONDS)
            executor.shutdown(wait=False)

            for future in not_done:
                unit = futures_map[future]
                section, batch_start, batch, _ = unit
                logger.warning(
                    "chunk_scoring_timeout",
                    job_id=str(job_id),
                    section=section,
                    batch_start=batch_start,
                    mode="llm",
                )
                error_count += 1
                for chunk in batch:
                    result_map[chunk.position] = ChunkMatchResult(
                        score=-1, rationale="Not evaluated (scoring timeout)"
                    )

            for future in done:
                unit = futures_map[future]
                section, batch_start, batch, _ = unit
                try:
                    batch, batch_results = future.result()
                except Exception:
                    logger.exception(
                        "chunk_scoring_failed",
                        job_id=str(job_id),
                        section=section,
                        batch_start=batch_start,
                        mode="llm",
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
            match = resolve_chunk_flags(match)
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
                include_in_scoring=match.include_in_scoring,
                semantic_type=match.semantic_type,
                evaluation_status=_derive_evaluation_status(match, chunk.chunk_type),
                enriched_at=now,
                scored_content=chunk.content,
                embedding=embedding,
                embedding_model=settings.embedding_model if embedding is not None else None,
            )
            db.add(job_chunk)

        # Persist pre/post-content chunks (excluded from scoring by bounds detection).
        for excluded_reason, excluded_chunks in [
            ("pre_content", pre_raw),
            ("post_content", post_raw),
        ]:
            for chunk in excluded_chunks:
                db.add(
                    JobChunk(
                        job_id=job_id,
                        chunk_type=chunk.chunk_type,
                        content=chunk.content,
                        position=chunk.position,
                        section=chunk.section,
                        match_score=None,
                        match_rationale=None,
                        advocacy_blurb=None,
                        experience_sources=[],
                        should_render=False,
                        include_in_scoring=False,
                        semantic_type="other",
                        evaluation_status="skipped",
                        excluded_reason=excluded_reason,
                        enriched_at=now,
                        scored_content=None,
                    )
                )

        # Merge batch telemetry into generation_telemetry JSONB (duration_ms / matching_mode
        # are written by _finalize_tailoring; we only add batch_count and batch_errors here).
        db.execute(
            text(
                """
                UPDATE tailorings
                SET generation_telemetry =
                    COALESCE(generation_telemetry, '{}'::jsonb)
                    || jsonb_build_object('batch_count', :batch_count, 'batch_errors', :error_count)
                WHERE job_id = :job_id
                """
            ),
            {"batch_count": batch_count, "error_count": error_count, "job_id": str(job_id)},
        )
        db.commit()

        from app.services.experience_embedder import embed_job_chunks

        t0 = time.perf_counter()
        embed_job_chunks(job_id, db)  # no-op for chunks already embedded in vector mode
        logger.info(
            "chunks_embeddings_complete",
            job_id=str(job_id),
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )

        logger.info(
            "enrich_job_chunks_complete",
            job_id=str(job_id),
            mode="vector" if use_vector else "llm",
            chunk_count=len(chunks),
            batch_count=batch_count,
            error_count=error_count,
        )

    except Exception:
        logger.exception("enrich_job_chunks_failed", job_id=str(job_id))
        try:
            db.rollback()  # required: session is in aborted-txn state after QueryCanceled
        except Exception:
            logger.exception("enrich_job_chunks_rollback_failed", job_id=str(job_id))
        raise
    finally:
        db.close()
        logger.debug("enrich_job_chunks_session_closed", job_id=str(job_id))


def re_enrich_single_chunk(
    chunk_id: str,
    extracted_profile: dict,
    pronouns: str | None = None,
    user_id: uuid.UUID | None = None,
    candidate_name: str | None = None,
    force_score: bool = False,
) -> None:
    """
    Re-score one JobChunk against an updated profile.

    Used when a gap answer is submitted — avoids re-processing the entire job.
    Dispatches to vector or llm mode based on settings.matching_mode.
    Creates its own DB session — do not pass a session across thread boundaries.
    """
    from app.clients.database import SessionLocal
    from app.models.database import JobChunk

    logger.info("re_enrich_single_chunk_start", chunk_id=chunk_id, mode=settings.matching_mode)

    db = SessionLocal()
    try:
        chunk = db.get(JobChunk, chunk_id)
        if not chunk:
            logger.warning("re_enrich_single_chunk_not_found", chunk_id=chunk_id)
            return

        use_vector = settings.matching_mode == "vector" and user_id is not None

        if use_vector:
            from app.services.profile_formatter import compute_profile_signals

            signals = compute_profile_signals(extracted_profile) if extracted_profile else None
            candidate_header = _build_candidate_header(candidate_name, pronouns, signals=signals)
            k = settings.vector_top_k
            match, new_embedding = _score_chunk_vector(
                chunk.content,
                chunk.chunk_type,
                chunk.section,
                user_id,
                candidate_header,
                k,
                force_score=force_score,
                prompt_name=prompt.PROMPT_NAME_VECTOR_SINGLE,
                pinned_job_chunk_id=chunk_id,
            )
            # Opportunistically update the chunk's embedding if it was missing
            if chunk.embedding is None and new_embedding is not None:
                chunk.embedding = new_embedding
                chunk.embedding_model = settings.embedding_model
        else:
            formatted_profile = format_sourced_profile(extracted_profile, pronouns=pronouns)

            section = chunk.section or "General"
            chunks_block = f"1. [{chunk.chunk_type.upper()}] {chunk.content}"
            force_score_note = prompt.FORCE_SCORE_NOTE if force_score else ""

            result = llm_parse_with_retry(
                get_llm_client(),
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": prompt.SYSTEM},
                    {
                        "role": "user",
                        "content": prompt.format_user_template(
                            extracted_profile=formatted_profile,
                            section=section,
                            chunks_block=chunks_block,
                            force_score_note=force_score_note,
                        ),
                    },
                ],
                response_model=ChunkMatchBatch,
                temperature=prompt.TEMPERATURE,
                validate_fn=_validate_single_chunk,
                prompt_name=prompt.PROMPT_NAME_SINGLE,
            )

            match = (
                result.results[0]
                if result.results
                else ChunkMatchResult(score=-1, rationale="Not evaluated (re-enrichment failed)")
            )

        now = datetime.now(timezone.utc)
        old_score = chunk.match_score
        chunk.match_score = match.score
        chunk.match_rationale = match.rationale
        chunk.advocacy_blurb = match.advocacy_blurb
        chunk.experience_sources = match.experience_sources or []
        chunk.should_render = match.should_render
        chunk.evaluation_status = "scored" if match.score in (0, 1, 2) else "error"
        chunk.enriched_at = now
        chunk.scored_content = chunk.content
        db.commit()

        logger.info(
            "re_enrich_single_chunk_complete",
            chunk_id=chunk_id,
            old_score=old_score,
            new_score=match.score,
        )

    except Exception:
        logger.exception("re_enrich_single_chunk_failed", chunk_id=chunk_id)
    finally:
        db.close()


def refresh_job_chunks(
    job_id: uuid.UUID,
    tailoring_id: str,
    extracted_profile: dict,
    pronouns: str | None = None,
    user_id: uuid.UUID | None = None,
    candidate_name: str | None = None,
) -> None:
    """
    Re-score existing JobChunk rows in-place without deleting them.

    Only chunks where include_in_scoring=True are re-scored; include_in_scoring=False chunks
    are left untouched. Sets enrichment_status on the specific tailoring.

    Creates its own DB session — do not pass a session across thread boundaries.
    """
    from app.clients.database import SessionLocal
    from app.models.database import JobChunk

    logger.info(
        "refresh_job_chunks_start",
        job_id=str(job_id),
        tailoring_id=tailoring_id,
        mode=settings.matching_mode,
    )

    db = SessionLocal()
    try:
        chunks = (
            db.query(JobChunk).filter(JobChunk.job_id == job_id).order_by(JobChunk.position).all()
        )
        scoreable = [c for c in chunks if c.include_in_scoring and c.chunk_type != "header"]

        if not scoreable:
            logger.info("refresh_job_chunks_no_scoreable", job_id=str(job_id))
            db.commit()
            return

        use_vector = settings.matching_mode == "vector" and user_id is not None

        result_map: dict[str, ChunkMatchResult] = {}
        error_count = 0

        if use_vector:
            from app.services.profile_formatter import compute_profile_signals

            signals = compute_profile_signals(extracted_profile) if extracted_profile else None
            candidate_header = _build_candidate_header(candidate_name, pronouns, signals=signals)
            k = settings.vector_top_k

            _log_ctx = structlog.contextvars.get_contextvars()

            def _score_one_vector(chunk):
                structlog.contextvars.clear_contextvars()
                structlog.contextvars.bind_contextvars(**_log_ctx)
                return chunk, _score_chunk_vector(
                    chunk.content,
                    chunk.chunk_type,
                    chunk.section,
                    user_id,
                    candidate_header,
                    k,
                    prompt_name=prompt.PROMPT_NAME_VECTOR_BATCH,
                )

            executor = ThreadPoolExecutor(max_workers=settings.chunk_scorer_concurrency)
            futures_map = {executor.submit(_score_one_vector, c): c for c in scoreable}
            done, not_done = wait(list(futures_map.keys()), timeout=_CHUNK_SCORING_TIMEOUT_SECONDS)
            executor.shutdown(wait=False)

            for future in not_done:
                chunk = futures_map[future]
                logger.warning(
                    "chunk_scoring_timeout",
                    job_id=str(job_id),
                    chunk_id=str(chunk.id),
                    mode="vector",
                )
                error_count += 1
                result_map[str(chunk.id)] = ChunkMatchResult(
                    score=-1, rationale="Not evaluated (scoring timeout)"
                )

            for future in done:
                chunk = futures_map[future]
                try:
                    _, (match, _embedding) = future.result()
                    result_map[str(chunk.id)] = match
                except Exception:
                    logger.exception(
                        "chunk_scoring_failed",
                        job_id=str(job_id),
                        chunk_id=str(chunk.id),
                        mode="vector",
                    )
                    error_count += 1
                    result_map[str(chunk.id)] = ChunkMatchResult(
                        score=-1, rationale="Not evaluated (vector error)"
                    )

        else:
            formatted_profile = format_sourced_profile(extracted_profile, pronouns=pronouns)

            section_map: dict[str, list] = {}
            for chunk in scoreable:
                key = chunk.section or "General"
                section_map.setdefault(key, []).append(chunk)

            batch_units: list[tuple[str, int, list, str]] = []
            for section, section_chunks in section_map.items():
                last_paragraph: str | None = None
                for batch_start in range(0, len(section_chunks), BATCH_SIZE):
                    batch = section_chunks[batch_start : batch_start + BATCH_SIZE]
                    preceding = ""
                    if last_paragraph is not None:
                        preceding = (
                            f"PRECEDING CONTEXT (do not score):\n[PARAGRAPH] {last_paragraph}\n\n"
                        )
                    for c in batch:
                        if c.chunk_type == "paragraph":
                            last_paragraph = c.content
                    batch_units.append((section, batch_start, batch, preceding))

            _log_ctx = structlog.contextvars.get_contextvars()

            def _run_llm_batch(unit: tuple[str, int, list, str]) -> tuple[list, list]:
                structlog.contextvars.clear_contextvars()
                structlog.contextvars.bind_contextvars(**_log_ctx)
                section, batch_start, batch, preceding = unit
                chunks_block = preceding + "\n".join(
                    f"{idx}. [{c.chunk_type.upper()}] {c.content}"
                    for idx, c in enumerate(batch, start=1)
                )
                result = llm_parse_with_retry(
                    get_llm_client(),
                    model=settings.llm_model,
                    messages=[
                        {"role": "system", "content": prompt.SYSTEM},
                        {
                            "role": "user",
                            "content": prompt.format_user_template(
                                extracted_profile=formatted_profile,
                                section=section,
                                chunks_block=chunks_block,
                            ),
                        },
                    ],
                    response_model=ChunkMatchBatch,
                    temperature=prompt.TEMPERATURE,
                    validate_fn=_validate_chunk_batch,
                    prompt_name=prompt.PROMPT_NAME_BATCH,
                )
                return batch, result.results

            executor = ThreadPoolExecutor(max_workers=settings.chunk_scorer_concurrency)
            futures_map = {executor.submit(_run_llm_batch, unit): unit for unit in batch_units}
            done, not_done = wait(list(futures_map.keys()), timeout=_CHUNK_SCORING_TIMEOUT_SECONDS)
            executor.shutdown(wait=False)

            for future in not_done:
                unit = futures_map[future]
                section, batch_start, batch, _ = unit
                logger.warning(
                    "chunk_scoring_timeout",
                    job_id=str(job_id),
                    section=section,
                    mode="llm",
                )
                error_count += 1
                for chunk in batch:
                    result_map[str(chunk.id)] = ChunkMatchResult(
                        score=-1, rationale="Not evaluated (scoring timeout)"
                    )

            for future in done:
                unit = futures_map[future]
                section, batch_start, batch, _ = unit
                try:
                    batch, batch_results = future.result()
                except Exception:
                    logger.exception(
                        "chunk_scoring_failed",
                        job_id=str(job_id),
                        section=section,
                        mode="llm",
                    )
                    error_count += 1
                    batch_results = []

                while len(batch_results) < len(batch):
                    batch_results.append(
                        ChunkMatchResult(score=-1, rationale="Not evaluated (batch error)")
                    )

                for chunk, match in zip(batch, batch_results):
                    result_map[str(chunk.id)] = match

        # Update chunks in-place (do NOT touch semantic_type or include_in_scoring — set at extraction)
        now = datetime.now(timezone.utc)
        for chunk in scoreable:
            match = result_map.get(str(chunk.id))
            if match is None:
                continue
            chunk.match_score = match.score
            chunk.match_rationale = match.rationale
            chunk.advocacy_blurb = match.advocacy_blurb
            chunk.experience_sources = match.experience_sources or []
            chunk.should_render = match.should_render
            chunk.evaluation_status = "scored" if match.score in (0, 1, 2) else "error"
            chunk.enriched_at = now
            chunk.scored_content = chunk.content

        db.commit()

        logger.info(
            "refresh_job_chunks_complete",
            job_id=str(job_id),
            chunk_count=len(scoreable),
            error_count=error_count,
        )

    except Exception:
        logger.exception("refresh_job_chunks_failed", job_id=str(job_id))
    finally:
        db.close()

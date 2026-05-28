from typing import Literal

import structlog

from app.clients.llm_client import get_llm_client
from app.config import settings
from app.core.llm_utils import llm_parse_with_retry
from app.prompts import gap_analysis as prompt
from app.schemas.gaps import GapAnalysis, GapQuestion, ProfileGapWithChunk
from app.services.profile_formatter import format_sourced_profile, sources_to_profile_dict

logger = structlog.get_logger(__name__)


def run_gap_analysis(tailoring_id: str) -> None:
    """
    Background task: run after enrich_job_chunks completes.

    Uses existing JobChunk.match_score values (set by the chunk matcher) as the
    authoritative source of gap identification — no re-scoring. For each confirmed
    gap chunk (match_score == 0, should_render == True), makes one focused LLM call
    to generate a targeted follow-up question.

    sourced_claim_count / unsourced_claim_count are derived arithmetically from
    chunk scores — no LLM involvement for counting.

    Creates its own DB session — do not pass a session across thread boundaries.
    """
    from app.clients.database import SessionLocal
    from app.models.database import JobChunk, Tailoring

    logger.info("run_gap_analysis_start", tailoring_id=tailoring_id)

    db = SessionLocal()
    try:
        tailoring = db.query(Tailoring).filter(Tailoring.id == tailoring_id).first()
        if not tailoring:
            logger.warning("run_gap_analysis_not_found", tailoring_id=tailoring_id)
            return

        job = tailoring.job
        if not job:
            logger.info("run_gap_analysis_no_job", tailoring_id=tailoring_id)
            tailoring.gap_analysis = []
            db.commit()
            return

        user = tailoring.user
        if not user or not user.experience_sources:
            logger.info("run_gap_analysis_no_experience", tailoring_id=tailoring_id)
            tailoring.gap_analysis = []
            db.commit()
            return

        extracted_profile = sources_to_profile_dict(user.experience_sources)
        if not extracted_profile:
            logger.info("run_gap_analysis_no_experience", tailoring_id=tailoring_id)
            tailoring.gap_analysis = []
            db.commit()
            return

        pronouns = user.profile.pronouns if user.profile else None
        candidate_name = user.candidate_name

        formatted_profile = format_sourced_profile(
            extracted_profile, candidate_name=candidate_name, pronouns=pronouns
        )

        extracted_job = job.extracted_job or {}
        job_context = _build_job_context(extracted_job)

        # Use chunk matcher scores as the authoritative source — no re-scoring.
        # Headers are excluded: they carry no scoreable requirement content.
        all_scored_chunks = (
            db.query(JobChunk)
            .filter(
                JobChunk.job_id == job.id,
                JobChunk.chunk_type != "header",
                JobChunk.match_score.isnot(None),
            )
            .all()
        )

        if not all_scored_chunks:
            logger.info(
                "run_gap_analysis_no_scored_chunks",
                tailoring_id=tailoring_id,
            )
            tailoring.gap_analysis = []
            db.commit()
            return

        # Counts derived from chunk scores — no LLM needed
        sourced_count = sum(1 for c in all_scored_chunks if (c.match_score or 0) >= 1)
        gap_chunks = [c for c in all_scored_chunks if c.match_score == 0 and c.should_render]
        partial_chunks = [c for c in all_scored_chunks if c.match_score == 1 and c.should_render]

        logger.info(
            "run_gap_analysis_scoring_summary",
            tailoring_id=tailoring_id,
            total_scored=len(all_scored_chunks),
            sourced_count=sourced_count,
            gap_count=len(gap_chunks),
            partial_count=len(partial_chunks),
        )

        # One focused LLM call per gap chunk — single responsibility: question generation only
        gaps_with_questions: list[ProfileGapWithChunk] = []
        for chunk in gap_chunks:
            try:
                result = _generate_question(
                    "gap",
                    requirement=chunk.content,
                    match_rationale=chunk.match_rationale or "",
                    formatted_profile=formatted_profile,
                    job_context=job_context,
                )
                gaps_with_questions.append(
                    ProfileGapWithChunk(
                        job_requirement=chunk.content,
                        question_for_candidate=result.question_for_candidate,
                        context=result.context,
                        source_searched="chunk_scorer",
                        chunk_id=str(chunk.id),
                    )
                )
            except Exception:
                logger.exception(
                    "run_gap_analysis_question_failed", chunk_id=str(chunk.id), mode="gap"
                )

        # One focused LLM call per partial chunk — path-to-strong question generation
        partials_with_questions: list[ProfileGapWithChunk] = []
        for chunk in partial_chunks:
            try:
                result = _generate_question(
                    "partial",
                    requirement=chunk.content,
                    match_rationale=chunk.match_rationale or "",
                    formatted_profile=formatted_profile,
                    job_context=job_context,
                )
                partials_with_questions.append(
                    ProfileGapWithChunk(
                        job_requirement=chunk.content,
                        question_for_candidate=result.question_for_candidate,
                        context=result.context,
                        source_searched="chunk_scorer",
                        chunk_id=str(chunk.id),
                    )
                )
            except Exception:
                logger.exception(
                    "run_gap_analysis_question_failed", chunk_id=str(chunk.id), mode="partial"
                )

        gap_analysis = GapAnalysis(
            gaps=gaps_with_questions,
            partials=partials_with_questions,
            sourced_claim_count=sourced_count,
            unsourced_claim_count=len(gap_chunks),
        )
        tailoring.gap_analysis = gap_analysis.model_dump()
        db.commit()

        logger.info(
            "run_gap_analysis_complete",
            tailoring_id=tailoring_id,
            gaps_with_questions=len(gaps_with_questions),
            partials_with_questions=len(partials_with_questions),
            sourced_count=sourced_count,
            unsourced_count=len(gap_chunks),
        )

    except Exception:
        logger.exception("run_gap_analysis_failed", tailoring_id=tailoring_id)
        try:
            tailoring = db.get(Tailoring, tailoring_id)
            if tailoring:
                tailoring.gap_analysis = []  # Signal completion so frontend stops polling
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def _build_job_context(extracted_job: dict) -> str:
    """Build a compact job context string for gap question prompts."""
    lines = []
    if title := extracted_job.get("title"):
        lines.append(f"Role: {title}")
    if company := extracted_job.get("company"):
        lines.append(f"Company: {company}")
    if desc := extracted_job.get("description"):
        lines.append(f"About the role: {desc[:400]}")
    if responsibilities := extracted_job.get("responsibilities"):
        top = responsibilities[:4]
        lines.append("Key responsibilities: " + "; ".join(top))
    return "\n".join(lines) if lines else "this role"


def _generate_question(
    mode: Literal["gap", "partial"],
    requirement: str,
    match_rationale: str,
    formatted_profile: str,
    job_context: str,
) -> GapQuestion:
    """
    Single-responsibility LLM call: generate a targeted follow-up question for one
    scored requirement.

    mode="gap"     — requirement scored 0; asks for gap-filling experience evidence.
    mode="partial" — requirement scored 1; asks for a path-to-strong clarification.

    The prompt templates differ between modes; everything else is identical.
    """
    sys_prompt = prompt.SYSTEM if mode == "gap" else prompt.PARTIAL_SYSTEM
    user_template = prompt.USER_TEMPLATE if mode == "gap" else prompt.PARTIAL_USER_TEMPLATE

    def _validate(r: GapQuestion) -> None:
        if not r.question_for_candidate.strip():
            raise ValueError("question_for_candidate is empty")

    return llm_parse_with_retry(
        get_llm_client(),
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": sys_prompt},
            {
                "role": "user",
                "content": user_template.format(
                    requirement=requirement,
                    match_rationale=match_rationale,
                    job_context=job_context,
                    formatted_profile=formatted_profile,
                ),
            },
        ],
        response_model=GapQuestion,
        temperature=prompt.TEMPERATURE,
        validate_fn=_validate,
        prompt_name=prompt.PROMPT_NAME if mode == "gap" else prompt.PARTIAL_PROMPT_NAME,
    )

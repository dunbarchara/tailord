import logging

from app.clients.llm_client import get_llm_client
from app.config import settings
from app.core.llm_utils import llm_parse_with_retry
from app.prompts import gap_analysis as prompt
from app.schemas.gaps import GapAnalysis, GapQuestion, ProfileGapWithChunk
from app.services.tailoring_generator import _format_sourced_profile

logger = logging.getLogger(__name__)


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

    logger.info("run_gap_analysis: start tailoring_id=%s", tailoring_id)

    db = SessionLocal()
    try:
        tailoring = db.query(Tailoring).filter(Tailoring.id == tailoring_id).first()
        if not tailoring:
            logger.warning("run_gap_analysis: tailoring %s not found", tailoring_id)
            return

        if tailoring.generation_status != "ready":
            logger.info(
                "run_gap_analysis: skipping tailoring %s (status=%s)",
                tailoring_id,
                tailoring.generation_status,
            )
            return

        job = tailoring.job
        if not job:
            logger.info("run_gap_analysis: no job for tailoring %s", tailoring_id)
            tailoring.gap_analysis_status = "complete"
            db.commit()
            return

        user = tailoring.user
        if not user or not user.experience or not user.experience.extracted_profile:
            logger.info("run_gap_analysis: no experience profile for tailoring %s", tailoring_id)
            tailoring.gap_analysis_status = "complete"
            db.commit()
            return

        extracted_profile = user.experience.extracted_profile
        pronouns = user.pronouns or None
        preferred = " ".join(
            filter(None, [user.preferred_first_name, user.preferred_last_name])
        ).strip()
        candidate_name = preferred or user.name or user.email

        formatted_profile = _format_sourced_profile(
            extracted_profile, candidate_name=candidate_name, pronouns=pronouns
        )

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
                "run_gap_analysis: no scored chunks for tailoring %s — enrichment may not have run yet",
                tailoring_id,
            )
            tailoring.gap_analysis_status = "complete"
            db.commit()
            return

        # Counts derived from chunk scores — no LLM needed
        sourced_count = sum(1 for c in all_scored_chunks if (c.match_score or 0) >= 1)
        gap_chunks = [c for c in all_scored_chunks if c.match_score == 0 and c.should_render]

        logger.info(
            "run_gap_analysis: tailoring=%s total_scored=%d sourced=%d gaps=%d",
            tailoring_id,
            len(all_scored_chunks),
            sourced_count,
            len(gap_chunks),
        )

        # One focused LLM call per gap chunk — single responsibility: question generation only
        gaps_with_questions: list[ProfileGapWithChunk] = []
        for chunk in gap_chunks:
            try:
                result = _generate_gap_question(
                    requirement=chunk.content,
                    formatted_profile=formatted_profile,
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
                    "run_gap_analysis: question generation failed for chunk %s — skipping",
                    chunk.id,
                )

        gap_analysis = GapAnalysis(
            gaps=gaps_with_questions,
            sourced_claim_count=sourced_count,
            unsourced_claim_count=len(gap_chunks),
        )
        tailoring.gap_analysis = gap_analysis.model_dump()
        tailoring.gap_analysis_status = "complete"
        db.commit()

        logger.info(
            "run_gap_analysis: complete tailoring=%s gaps_with_questions=%d sourced=%d unsourced=%d",
            tailoring_id,
            len(gaps_with_questions),
            sourced_count,
            len(gap_chunks),
        )

    except Exception:
        logger.exception("run_gap_analysis failed for tailoring %s", tailoring_id)
        try:
            tailoring = db.get(Tailoring, tailoring_id)
            if tailoring:
                tailoring.gap_analysis_status = "complete"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def _generate_gap_question(
    requirement: str,
    formatted_profile: str,
) -> GapQuestion:
    """
    Single-responsibility LLM call: given one confirmed gap requirement and the
    candidate's profile, generate a targeted follow-up question.

    The requirement has already been scored 0 by the chunk matcher — this function
    only generates the question; it does not re-score or validate the gap.
    """

    def _validate(r: GapQuestion) -> None:
        if not r.question_for_candidate.strip():
            raise ValueError("question_for_candidate is empty")

    return llm_parse_with_retry(
        get_llm_client(),
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": prompt.SYSTEM},
            {
                "role": "user",
                "content": prompt.USER_TEMPLATE.format(
                    requirement=requirement,
                    formatted_profile=formatted_profile,
                ),
            },
        ],
        response_model=GapQuestion,
        temperature=prompt.TEMPERATURE,
        validate_fn=_validate,
    )

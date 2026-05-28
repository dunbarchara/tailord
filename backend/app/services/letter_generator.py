import structlog

from app.clients.llm_client import get_llm_client
from app.config import settings
from app.core.llm_utils import llm_parse_with_retry
from app.prompts import tailoring as prompt
from app.schemas.llm_outputs import TailoringContent
from app.services.profile_formatter import format_sourced_profile

logger = structlog.get_logger(__name__)


def _format_ranked_matches(matches: list[dict]) -> str:
    """Format pre-scored requirement matches into a labeled block for the LLM."""
    if not matches:
        return "(No pre-scored matches available — write claims based on the candidate profile and job context.)"

    score_labels = {2: "STRONG", 1: "PARTIAL"}
    source_labels = {"resume": "Resume", "github": "GitHub", "user_input": "Direct Input"}

    lines = []
    for match in matches:
        score = match.get("score", 0)
        score_label = score_labels.get(score, "PARTIAL")
        req = match.get("requirement", "")
        is_preferred = match.get("is_preferred", False)
        req_label = "Preferred" if is_preferred else "Required"
        rationale = match.get("rationale", "")
        source_keys = match.get("experience_sources") or []
        source_parts = [source_labels.get(k, k) for k in source_keys if k]
        source_label = ", ".join(source_parts) if source_parts else None

        header = f'[{score_label}] {req_label}: "{req}"'
        if source_label and rationale:
            detail = f"  → {source_label} — {rationale}"
        elif rationale:
            detail = f"  → {rationale}"
        elif source_label:
            detail = f"  → {source_label}"
        else:
            detail = None

        lines.append(header)
        if detail:
            lines.append(detail)

    return "\n".join(lines)


def _render_tailoring(
    content: TailoringContent,
    candidate_name: str,
    candidate_email: str | None,
    candidate_linkedin: str | None,
    candidate_title: str | None,
    company: str,
    job_title: str,
    job_url: str | None = None,
) -> str:
    """Deterministically render a TailoringContent object into the final markdown document."""
    first_name = candidate_name.split()[0] if candidate_name else candidate_name
    job_title_md = f"[{job_title}]({job_url})" if job_url else job_title

    lines: list[str] = []

    # Greeting + opening sentence
    lines += [
        f"Hello **{company}**,",
        "",
        f"Given the requirements in your {job_title_md} job posting, here are some reasons **{candidate_name}** would be a strong fit for the role.",
        "",
        "---",
        "",
    ]

    # Advocacy sections
    logger.debug(
        "_render_tailoring: advocacy_statement_count", count=len(content.advocacy_statements)
    )
    for stmt in content.advocacy_statements:
        source_tag = " ".join(f"[{s}]" for s in stmt.sources) if stmt.sources else ""
        body = f"{stmt.body} *{source_tag}*".strip()
        lines += [f"**{stmt.header}**", "", body, ""]

    lines += ["---", ""]

    # Closing: LLM synthesis + deterministic contact line
    closing = content.closing.rstrip()
    if candidate_email:
        lines += [closing, ""]
        lines.append(
            f"If you're interested in continuing the conversation, {first_name} can be reached at [{candidate_email}](mailto:{candidate_email})."
        )
    else:
        lines.append(closing)

    lines += ["", "---", ""]

    # Candidate brief footer
    brief_parts = [candidate_name]
    if candidate_title:
        brief_parts.append(candidate_title)
    if candidate_email:
        brief_parts.append(f"[{candidate_email}](mailto:{candidate_email})")
    if candidate_linkedin:
        linkedin_url = (
            candidate_linkedin
            if candidate_linkedin.startswith("http")
            else f"https://{candidate_linkedin}"
        )
        brief_parts.append(f"[LinkedIn]({linkedin_url})")
    lines.append(f"*{' · '.join(brief_parts)}*")

    return "\n".join(lines)


def generate_letter(
    extracted_profile: dict,
    extracted_job: dict,
    candidate_name: str,
    ranked_matches: list[dict] | None = None,
    job_url: str | None = None,
    pronouns: str | None = None,
) -> tuple[str, dict]:
    company = extracted_job.get("company") or "the company"
    job_title = extracted_job.get("title") or "this role"
    logger.debug(
        "generate_letter: start",
        company=company,
        job_title=job_title,
        profile_sources=list(extracted_profile.keys()),
    )
    resume = extracted_profile.get("resume") or {}
    candidate_email: str | None = resume.get("email") or None
    candidate_linkedin: str | None = resume.get("linkedin") or None

    ranked_matches_block = _format_ranked_matches(
        ranked_matches if ranked_matches is not None else []
    )

    def _validate_tailoring(result: TailoringContent) -> None:
        total = sum(len(s.body) for s in result.advocacy_statements) + len(result.closing or "")
        if total < 200:
            raise ValueError(
                f"output is too short ({total} chars) — write more detailed advocacy statements"
            )

    content = llm_parse_with_retry(
        get_llm_client(),
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": prompt.SYSTEM},
            {
                "role": "user",
                "content": prompt.USER_TEMPLATE.format(
                    candidate_name=candidate_name,
                    job_title=job_title,
                    company=company,
                    ranked_matches_block=ranked_matches_block,
                    extracted_profile=format_sourced_profile(
                        extracted_profile, candidate_name=candidate_name, pronouns=pronouns
                    ),
                ),
            },
        ],
        response_model=TailoringContent,
        temperature=prompt.TEMPERATURE,
        validate_fn=_validate_tailoring,
        prompt_name=prompt.PROMPT_NAME,
    )

    rendered = _render_tailoring(
        content=content,
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        candidate_linkedin=candidate_linkedin,
        candidate_title=resume.get("title") or None,
        company=company,
        job_title=job_title,
        job_url=job_url,
    )
    return rendered, content.model_dump()

import re

from app.clients.llm_client import get_llm_client
from app.config import settings
from app.core.llm_utils import llm_parse_with_retry
from app.prompts import profile_extraction as extraction_prompt
from app.prompts import profile_identity as identity_prompt
from app.schemas.llm_outputs import ExtractedStructure, ProfileIdentity
from app.services.profile_formatter import (
    merge_intervals,
    parse_duration_date,
    parse_duration_years,
)

_LEADING_BULLET = re.compile(r"^[•\-\*·◦▸–—]\s*")
_DURATION_SPLIT = re.compile(r"\s*[-–—]\s*|\s+to\s+")


def _clean_profile(data: dict) -> dict:
    for job in data.get("work_experience", []):
        job["bullets"] = [_LEADING_BULLET.sub("", b) for b in job.get("bullets", [])]
    return data


def _validate_structure(result: ExtractedStructure) -> None:
    if not result.work_experience:
        raise ValueError("work_experience is empty — extract all roles from the resume")


def _validate_identity(result: ProfileIdentity) -> None:
    if not (result.summary and result.summary.strip()):
        raise ValueError("summary is empty — write a 2–3 sentence professional summary")


def _compute_yoe(structure: ExtractedStructure) -> float:
    intervals = []
    for role in structure.work_experience:
        if not role.duration:
            continue
        parts = _DURATION_SPLIT.split(role.duration.strip(), maxsplit=1)
        if len(parts) != 2:
            continue
        start = parse_duration_date(parts[0])
        end = parse_duration_date(parts[1])
        if start and end and end >= start:
            intervals.append((start, end))
    merged = merge_intervals(intervals)
    return round(sum((e - s).days / 365.25 for s, e in merged), 1)


def _format_yoe_label(yoe: float) -> str:
    if yoe < 1:
        months = round(yoe * 12)
        return f"{months} month{'s' if months != 1 else ''}"
    return f"{int(yoe)}+ years"


def _render_experience_summary(structure: ExtractedStructure) -> str:
    """Compact prose for Step 2 prompt — roles + skills + education only."""
    lines = []
    if structure.work_experience:
        lines.append("Work Experience:")
        for role in structure.work_experience:
            years = parse_duration_years(role.duration) if role.duration else 0.0
            label = f"  {role.title}"
            if role.company:
                label += f" @ {role.company}"
            if role.duration:
                label += f" ({role.duration})"
            if years:
                label += f" [{years:.1f} yrs]"
            lines.append(label)
    if structure.skills.technical:
        lines.append("Technical skills: " + ", ".join(structure.skills.technical))
    if structure.education:
        lines.append("Education:")
        for e in structure.education:
            lines.append("  " + ", ".join(p for p in [e.degree, e.institution, e.year] if p))
    return "\n".join(lines)


def extract_profile(text: str) -> dict:
    client = get_llm_client()

    # Step 1: structural extraction
    structure = llm_parse_with_retry(
        client,
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": extraction_prompt.SYSTEM},
            {"role": "user", "content": extraction_prompt.USER_TEMPLATE.format(resume_text=text)},
        ],
        response_model=ExtractedStructure,
        temperature=extraction_prompt.TEMPERATURE,
        validate_fn=_validate_structure,
        prompt_name=extraction_prompt.PROMPT_NAME,
    )

    # Compute YoE from extracted date intervals, pre-format for prose
    yoe = _compute_yoe(structure)
    yoe_label = _format_yoe_label(yoe)

    # Step 2: identity generation with computed YoE injected
    identity = llm_parse_with_retry(
        client,
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": identity_prompt.SYSTEM},
            {
                "role": "user",
                "content": identity_prompt.USER_TEMPLATE.format(
                    experience_summary=_render_experience_summary(structure),
                    yoe_label=yoe_label,
                ),
            },
        ],
        response_model=ProfileIdentity,
        temperature=identity_prompt.TEMPERATURE,
        validate_fn=_validate_identity,
        prompt_name=identity_prompt.PROMPT_NAME,
    )

    # Merge into ExtractedProfile-compatible dict (unchanged public contract)
    merged = {
        **structure.model_dump(),
        "title": identity.title,
        "headline": identity.headline,
        "summary": identity.summary,
    }
    return _clean_profile(merged)

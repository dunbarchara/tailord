import logging

from app.clients.llm_client import get_llm_client
from app.config import settings
from app.core.llm_utils import llm_parse
from app.prompts import requirement_matching as prompt
from app.schemas.matching import RequirementMatchList
from app.services.tailoring_generator import _format_sourced_profile

logger = logging.getLogger(__name__)


def match_requirements(extracted_job: dict, extracted_profile: dict) -> list[dict]:
    """
    Fast pipeline: single LLM call scoring all requirements against the candidate profile.
    Returns matches sorted by score desc, filtered to score >= 1.
    """
    required = extracted_job.get("requirements", {}).get("required", [])
    preferred = extracted_job.get("requirements", {}).get("preferred", [])

    if not required and not preferred:
        return []

    lines = []
    for req in required:
        lines.append(f"[REQUIRED] {req}")
    for req in preferred:
        lines.append(f"[PREFERRED] {req}")
    requirements_block = "\n".join(lines)

    formatted_profile = _format_sourced_profile(extracted_profile)

    result = llm_parse(
        get_llm_client(),
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": prompt.SYSTEM},
            {"role": "user", "content": prompt.USER_TEMPLATE.format(
                extracted_profile=formatted_profile,
                requirements_block=requirements_block,
            )},
        ],
        response_model=RequirementMatchList,
        temperature=prompt.TEMPERATURE,
    )

    matches = [m.model_dump() for m in result.matches if m.score >= 1]
    matches.sort(key=lambda m: m["score"], reverse=True)
    return matches

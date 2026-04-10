import re

from app.clients.llm_client import get_llm_client
from app.config import settings
from app.core.llm_utils import llm_parse_with_retry
from app.prompts import profile_extraction as prompt
from app.schemas.llm_outputs import ExtractedProfile

_LEADING_BULLET = re.compile(r"^[•\-\*·◦▸–—]\s*")


def _clean_profile(data: dict) -> dict:
    for job in data.get("work_experience", []):
        job["bullets"] = [_LEADING_BULLET.sub("", b) for b in job.get("bullets", [])]
    return data


def _validate_extracted_profile(result: ExtractedProfile) -> None:
    if not (result.summary and result.summary.strip()):
        raise ValueError("summary is empty — generate a 2–3 sentence professional summary")
    if not result.work_experience:
        raise ValueError("work_experience is empty — extract all roles from the resume")


def extract_profile(text: str) -> dict:
    client = get_llm_client()
    result = llm_parse_with_retry(
        client,
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": prompt.SYSTEM},
            {"role": "user", "content": prompt.USER_TEMPLATE.format(resume_text=text)},
        ],
        response_model=ExtractedProfile,
        temperature=prompt.TEMPERATURE,
        validate_fn=_validate_extracted_profile,
    )
    return _clean_profile(result.model_dump())

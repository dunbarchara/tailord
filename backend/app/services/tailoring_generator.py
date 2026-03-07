import json

from app.clients.llm_client import get_llm_client
from app.config import settings
from app.core.llm_utils import llm_generate
from app.prompts import tailoring as prompt


def _format_sourced_profile(sourced_profile: dict) -> str:
    """Format a source-keyed profile dict into labeled blocks for LLM context."""
    source_labels = {
        "resume": "Resume",
        "github": "GitHub",
        "user_input": "Direct Input",
    }
    sections = []
    for key, label in source_labels.items():
        if data := sourced_profile.get(key):
            sections.append(f"[Source: {label}]\n{json.dumps(data, indent=2)}")
    # Include any unknown keys without a label, so future sources aren't silently dropped
    for key, data in sourced_profile.items():
        if key not in source_labels:
            sections.append(f"[Source: {key}]\n{json.dumps(data, indent=2)}")
    return "\n\n".join(sections) if sections else json.dumps(sourced_profile, indent=2)


def generate_tailoring(extracted_profile: dict, extracted_job: dict, candidate_name: str) -> str:
    company = extracted_job.get("company") or "the company"
    job_title = extracted_job.get("title") or "this role"

    return llm_generate(
        get_llm_client(),
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": prompt.SYSTEM},
            {"role": "user", "content": prompt.USER_TEMPLATE.format(
                candidate_name=candidate_name,
                job_title=job_title,
                company=company,
                extracted_profile=_format_sourced_profile(extracted_profile),
                extracted_job=json.dumps(extracted_job, indent=2),
            )},
        ],
        temperature=prompt.TEMPERATURE,
        label="tailoring",
    )


def generate_match(profile: dict, job: dict) -> str:
    return llm_generate(
        get_llm_client(),
        model=settings.llm_model,
        messages=[
            {"role": "user", "content": prompt.MATCH_USER_TEMPLATE.format(
                profile=json.dumps(profile, indent=2),
                job=json.dumps(job, indent=2),
            )},
        ],
        temperature=prompt.MATCH_TEMPERATURE,
        label="match",
    )

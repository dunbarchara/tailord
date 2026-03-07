from app.clients.llm_client import get_llm_client
from app.config import settings
from app.core.llm_utils import llm_parse
from app.prompts import job_extraction as prompt
from app.schemas.llm_outputs import ExtractedJob


def extract_job(job_markdown: str) -> dict:
    client = get_llm_client()
    result = llm_parse(
        client,
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": prompt.SYSTEM},
            {"role": "user", "content": prompt.USER_TEMPLATE.format(job_markdown=job_markdown)},
        ],
        response_model=ExtractedJob,
        temperature=prompt.TEMPERATURE,
    )
    return result.model_dump()

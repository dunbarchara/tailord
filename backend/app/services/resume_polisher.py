from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel

from app.clients.llm_client import get_llm_client
from app.config import settings
from app.core.llm_utils import llm_parse_with_retry
from app.models.database import ExperienceClaim
from app.prompts import resume_polish as prompt
from app.schemas.resume import BulletPolishResponse, BulletPolishResult


class _BulletResult(BaseModel):
    rewritten: str
    unchanged: bool
    note: str


def polish_bullets(
    claim_ids: list[str],
    claims: list[ExperienceClaim],
    job_title: str,
    company: str,
) -> BulletPolishResponse:
    """
    Run Phase 2 LLM polish on requested claim IDs.
    One LLM call per bullet (stateless, parallel via ThreadPoolExecutor).
    Returns {claim_id: BulletPolishResult}.
    """
    client = get_llm_client()
    claim_map = {str(c.id): c for c in claims}
    results: dict[str, BulletPolishResult] = {}

    def _polish_one(cid: str) -> tuple[str, BulletPolishResult]:
        claim = claim_map[cid]
        messages = [
            {
                "role": "system",
                "content": prompt.SYSTEM.format(
                    job_title=job_title,
                    company=company,
                    original_content=claim.content,
                ),
            }
        ]
        result = llm_parse_with_retry(
            client=client,
            model=settings.llm_model,
            messages=messages,
            response_model=_BulletResult,
            temperature=prompt.TEMPERATURE,
            prompt_name=prompt.PROMPT_NAME,
        )
        return cid, BulletPolishResult(
            rewritten=result.rewritten,
            unchanged=result.unchanged,
            note=result.note,
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(_polish_one, cid): cid for cid in claim_ids}
        for future in futures:
            cid = futures[future]
            try:
                cid, result = future.result(timeout=60)
                results[cid] = result
            except Exception:
                claim = claim_map.get(cid)
                if claim:
                    results[cid] = BulletPolishResult(
                        rewritten=claim.content,
                        unchanged=True,
                        note="polish failed — original returned",
                    )

    return BulletPolishResponse(results=results)

from pydantic import BaseModel


class GapQuestion(BaseModel):
    """LLM output for a single gap chunk — question generation only, no re-scoring."""

    question_for_candidate: str
    context: str  # why this requirement matters for THIS specific role


class ProfileGapWithChunk(BaseModel):
    """A confirmed gap with its resolved chunk_id and generated question."""

    job_requirement: str
    question_for_candidate: str
    context: str
    source_searched: str
    chunk_id: str | None = None


class GapAnalysis(BaseModel):
    gaps: list[ProfileGapWithChunk]
    partials: list[ProfileGapWithChunk] = []
    sourced_claim_count: int
    unsourced_claim_count: int

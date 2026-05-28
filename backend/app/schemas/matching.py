from pydantic import BaseModel


class ChunkMatchResult(BaseModel):
    score: int = 0  # -1=non-evaluable, 0=gap, 1=partial, 2=strong
    rationale: str = ""
    advocacy_blurb: str | None = None  # personal advocacy statement; only for score >= 1
    experience_sources: list[str] = []
    should_render: bool = True
    include_in_scoring: bool = True
    semantic_type: str = "other"


class ChunkMatchBatch(BaseModel):
    results: list[ChunkMatchResult] = []

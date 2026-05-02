from pydantic import BaseModel


class RequirementMatch(BaseModel):
    requirement: str
    is_preferred: bool = False
    score: int  # 0=not met, 1=partial, 2=strong
    rationale: str = ""
    experience_sources: list[str] = []  # resume, github, user_input


class RequirementMatchList(BaseModel):
    matches: list[RequirementMatch] = []


class ChunkMatchResult(BaseModel):
    score: int = 0  # -1=non-evaluable, 0=gap, 1=partial, 2=strong
    rationale: str = ""
    advocacy_blurb: str | None = None  # personal advocacy statement; only for score >= 1
    experience_sources: list[str] = []
    should_render: bool = True


class ChunkMatchBatch(BaseModel):
    results: list[ChunkMatchResult] = []

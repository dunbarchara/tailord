from pydantic import BaseModel


class RequirementMatch(BaseModel):
    requirement: str
    is_preferred: bool = False
    score: int  # 0=not met, 1=partial, 2=strong
    rationale: str = ""
    experience_source: str | None = None  # resume, github, user_input


class RequirementMatchList(BaseModel):
    matches: list[RequirementMatch] = []


class ChunkMatchResult(BaseModel):
    score: int = 0  # 0=not relevant, 1=partial, 2=strong
    rationale: str | None = None
    experience_source: str | None = None


class ChunkMatchBatch(BaseModel):
    results: list[ChunkMatchResult] = []

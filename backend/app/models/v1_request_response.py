from pydantic import BaseModel, HttpUrl
from typing import List

class AnalyzeRequest(BaseModel):
    url: HttpUrl

class AnalyzeResponse(BaseModel):
    job_title: str
    seniority_level: str
    required_skills: List[str]
    preferred_skills: List[str]
    soft_skills: List[str]
    responsibilities: List[str]
    qualifications: List[str]

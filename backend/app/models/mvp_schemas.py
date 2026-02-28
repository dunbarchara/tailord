from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class ProfileInput(BaseModel):
    resume_text: str
    github_username: str

class JobInput(BaseModel):
    job_url: str

class GenerateInput(BaseModel):
    job_id: str

class GeneratedOutput(BaseModel):
    content: str


class TailoringCreate(BaseModel):
    job_url: str


class TailoringResponse(BaseModel):
    id: str
    title: Optional[str]
    company: Optional[str]
    job_url: str
    generated_output: str
    created_at: str


class TailoringListItem(BaseModel):
    id: str
    title: Optional[str]
    company: Optional[str]
    created_at: str

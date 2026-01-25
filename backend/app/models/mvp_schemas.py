from pydantic import BaseModel
from typing import List

class ProfileInput(BaseModel):
    resume_text: str
    github_username: str

class JobInput(BaseModel):
    job_url: str

class GeneratedOutput(BaseModel):
    content: str

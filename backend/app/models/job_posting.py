from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class Company(BaseModel):
    company_id: Optional[str] = None
    name: Optional[str] = None
    department: Optional[str] = None

class Employment(BaseModel):
    type: Optional[str] = None
    level: Optional[str] = None
    contract_length_months: Optional[int] = None

class Location(BaseModel):
    workplace_type: Optional[str] = None
    primary_location: Optional[str] = None
    eligible_regions: Optional[List[str]] = Field(default_factory=list)

class Compensation(BaseModel):
    currency: Optional[str] = None
    min: Optional[int] = None
    max: Optional[int] = None
    frequency: Optional[str] = None
    equity: Optional[bool] = None

class Requirements(BaseModel):
    required: List[str] = Field(default_factory=list)
    preferred: List[str] = Field(default_factory=list)

class Skills(BaseModel):
    technical: List[str] = Field(default_factory=list)
    soft: List[str] = Field(default_factory=list)

class Qualifications(BaseModel):
    education: Optional[str] = None
    certifications: Optional[List[str]] = Field(default_factory=list)

class Application(BaseModel):
    apply_url: Optional[str] = None
    deadline: Optional[str] = None

class JobPosting(BaseModel):
    job_id: str
    version: int
    status: str
    language: str

    title: Optional[str] = None
    summary: Optional[str] = None

    company: Optional[Company] = None
    employment: Optional[Employment] = None
    location: Optional[Location] = None
    compensation: Optional[Compensation] = None

    responsibilities: List[str] = Field(default_factory=list)
    requirements: Requirements
    skills: Skills
    qualifications: Qualifications
    benefits: List[str] = Field(default_factory=list)

    application: Application
    metadata: Dict[str, str] = Field(default_factory=dict)

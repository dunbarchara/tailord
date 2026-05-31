from typing import Literal

from pydantic import BaseModel, Field


class WorkExperience(BaseModel):
    title: str = ""
    company: str = ""
    location: str | None = None
    duration: str = ""
    start_date: str | None = None  # YYYY-MM, e.g. "2020-01"
    end_date: str | None = None  # YYYY-MM, or null if current/ongoing
    bullets: list[str] = []


class ProfileSkills(BaseModel):
    technical: list[str] = []
    soft: list[str] = []


class Education(BaseModel):
    degree: str = ""  # credential received (e.g. "B.S. Computer Science"); empty if none
    institution: str = ""
    location: str | None = None
    year: str = ""  # human-readable display string (e.g. "Graduated Dec 2017")
    enrollment_date: str | None = None  # YYYY-MM or YYYY — when studies began
    completion_date: str | None = (
        None  # YYYY-MM or YYYY — when attendance ended (neutral: graduation, transfer, or departure)
    )
    status: str | None = None  # graduated | pursuing | transferred | attended
    distinction: str | None = None


class Project(BaseModel):
    name: str = ""
    description: str = ""
    technologies: list[str] = []
    start_date: str | None = None  # YYYY-MM or YYYY
    end_date: str | None = None  # YYYY-MM or YYYY; null if ongoing


class ExtractedStructure(BaseModel):
    """Step 1 output — raw structured extraction, no prose generation."""

    email: str | None = None
    phone: str | None = None
    linkedin: str | None = None
    location: str | None = None
    work_experience: list[WorkExperience] = []
    skills: ProfileSkills = ProfileSkills()
    education: list[Education] = []
    projects: list[Project] = []
    certifications: list[str] = []


class ProfileIdentity(BaseModel):
    """Step 2 output — generated prose fields only."""

    title: str | None = None
    headline: str | None = None
    summary: str = ""


class ExtractedProfile(BaseModel):
    email: str | None = None
    phone: str | None = None
    linkedin: str | None = None
    location: str | None = None
    title: str | None = None
    headline: str | None = None
    summary: str = ""
    work_experience: list[WorkExperience] = []
    skills: ProfileSkills = ProfileSkills()
    education: list[Education] = []
    projects: list[Project] = []
    certifications: list[str] = []


class ParsedClaims(BaseModel):
    """LLM output for user_input_parse: atomic claims extracted from free-text input."""

    claims: list[str] = []


class GitHubRepoEnrichment(BaseModel):
    """LLM output for a single GitHub repo enrichment call (github_enricher.py)."""

    readme_summary: str = Field(default="", description="2–3 sentence project summary")
    detected_stack: list[str] = Field(
        default_factory=list, description="Specific frameworks, libraries, tools"
    )
    project_domain: str = Field(default="unknown", description="Concise domain phrase")
    confidence: Literal["high", "medium", "low"] = "low"
    experience_claims: list[str] = Field(
        default_factory=list,
        description="0–3 concrete, resume-style bullets about what was built or done",
    )


class JobRequirements(BaseModel):
    required: list[str] = []
    preferred: list[str] = []


class JobSkills(BaseModel):
    technical: list[str] = []
    soft: list[str] = []


class AdvocacyStatement(BaseModel):
    header: str
    body: str
    sources: list[Literal["Resume", "GitHub", "Direct Input"]] = []


class TailoringContent(BaseModel):
    advocacy_statements: list[AdvocacyStatement]
    closing: str


class ExtractedJob(BaseModel):
    company: str | None = None
    title: str | None = None
    responsibilities: list[str] = []
    requirements: JobRequirements = JobRequirements()
    skills: JobSkills = JobSkills()

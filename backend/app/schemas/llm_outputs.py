from typing import Literal

from pydantic import BaseModel


class WorkExperience(BaseModel):
    title: str = ""
    company: str = ""
    location: str | None = None
    duration: str = ""
    bullets: list[str] = []


class ProfileSkills(BaseModel):
    technical: list[str] = []
    soft: list[str] = []


class Education(BaseModel):
    degree: str = ""
    institution: str = ""
    location: str | None = None
    year: str = ""
    distinction: str | None = None


class Project(BaseModel):
    name: str = ""
    description: str = ""
    technologies: list[str] = []


class ExtractedProfile(BaseModel):
    email: str | None = None
    phone: str | None = None
    linkedin: str | None = None
    location: str | None = None
    headline: str | None = None
    summary: str = ""
    work_experience: list[WorkExperience] = []
    skills: ProfileSkills = ProfileSkills()
    education: list[Education] = []
    projects: list[Project] = []
    certifications: list[str] = []


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

from pydantic import BaseModel


class WorkExperience(BaseModel):
    title: str = ""
    company: str = ""
    duration: str = ""
    bullets: list[str] = []


class ProfileSkills(BaseModel):
    technical: list[str] = []
    soft: list[str] = []


class Education(BaseModel):
    degree: str = ""
    institution: str = ""
    year: str = ""


class Project(BaseModel):
    name: str = ""
    description: str = ""
    technologies: list[str] = []


class ExtractedProfile(BaseModel):
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


class ExtractedJob(BaseModel):
    company: str | None = None
    title: str | None = None
    responsibilities: list[str] = []
    requirements: JobRequirements = JobRequirements()
    skills: JobSkills = JobSkills()

from pydantic import BaseModel


class EducationEntry(BaseModel):
    """Embedded education metadata — self-contained so no DB lookup needed at render time."""

    name: str  # Institution name
    degree: str | None = None
    end_date: str | None = None
    location: str | None = None
    distinction: str | None = None  # e.g. "3.8 GPA · Magna Cum Laude"


class ResumeSection(BaseModel):
    group_id: str  # UUID string or synthetic key "ungrouped:<group_key>"
    group_type: str  # role | project | repository | education | custom
    # Group display metadata — embedded at generation time so rendering is self-contained
    group_name: str = ""
    group_start_date: str | None = None
    group_end_date: str | None = None
    group_location: str | None = None
    group_type_meta: dict | None = None
    included: bool = True
    claim_ids: list[str]  # ordered by relevance
    rewrites: dict[str, str] = {}  # {claim_id: accepted_rewrite_text}
    bullet_snapshots: dict[str, str] = {}  # {claim_id: content} — frozen at generation time


class ResumeContactOverride(BaseModel):
    linkedin_url: str | None = None
    location: str | None = None


class ResumeDraft(BaseModel):
    generated_at: str
    polished: bool = False
    contact_override: ResumeContactOverride = ResumeContactOverride()
    sections: list[ResumeSection]
    skills_claim_ids: list[str]
    skills_snapshots: dict[str, str] = {}  # {claim_id: content} — frozen at generation time
    education_data: list[EducationEntry] = []  # embedded at generation time — no DB lookup needed
    education_group_ids: list[str] = []  # legacy — kept for backward compat
    warnings: list[str] = []  # e.g. "no_resume_source" → triggers soft callout in UI
    experience_snapshot_at: str | None = (
        None  # max(ExperienceSource.last_synced_at) at generation time
    )


class ResumePatchRequest(BaseModel):
    sections: list[ResumeSection] | None = None
    skills_claim_ids: list[str] | None = None
    education_group_ids: list[str] | None = None
    contact_override: ResumeContactOverride | None = None
    rewrites: dict[str, str] | None = None  # {claim_id: rewrite} merged into matching section


class PolishRequest(BaseModel):
    claim_ids: list[str]


class BulletPolishResult(BaseModel):
    rewritten: str
    unchanged: bool
    note: str


class BulletPolishResponse(BaseModel):
    results: dict[str, BulletPolishResult]  # {claim_id: result}

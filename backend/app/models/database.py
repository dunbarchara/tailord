import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.clients.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    google_sub: Mapped[str] = mapped_column(String, unique=True, index=True)
    email: Mapped[str] = mapped_column(String)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    preferred_first_name: Mapped[str | None] = mapped_column(String, nullable=True)
    preferred_last_name: Mapped[str | None] = mapped_column(String, nullable=True)
    # Notion OAuth
    notion_access_token: Mapped[str | None] = mapped_column(String, nullable=True)
    notion_bot_id: Mapped[str | None] = mapped_column(String, nullable=True)
    notion_workspace_id: Mapped[str | None] = mapped_column(String, nullable=True)
    notion_workspace_name: Mapped[str | None] = mapped_column(String, nullable=True)
    notion_parent_page_id: Mapped[str | None] = mapped_column(String, nullable=True)
    pronouns: Mapped[str | None] = mapped_column(String, nullable=True)
    # Public profile
    username_slug: Mapped[str | None] = mapped_column(
        String, unique=True, nullable=True, index=True
    )
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
    profile_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # status: pending | approved
    status: Mapped[str] = mapped_column(String, default="pending", server_default="pending")
    is_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    experience: Mapped["Experience | None"] = relationship(
        "Experience", back_populates="user", uselist=False
    )
    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="user")
    tailorings: Mapped[list["Tailoring"]] = relationship("Tailoring", back_populates="user")


class Experience(Base):
    __tablename__ = "experiences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), unique=True
    )
    s3_key: Mapped[str | None] = mapped_column(String, nullable=True)
    filename: Mapped[str | None] = mapped_column(String, nullable=True)
    # status: pending | processing | ready | error
    status: Mapped[str] = mapped_column(String, default="pending")
    extracted_profile: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    raw_resume_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    github_username: Mapped[str | None] = mapped_column(String, nullable=True)
    github_repos: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Enriched per-repo signals from the GitHub App crawl (README, manifests, LLM summary).
    # Null until enrichment completes. Additive — does not replace github_repos.
    github_repo_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    user_input_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set at request time (before processing begins) — used for the 5-min cooldown check.
    # processed_at captures completion; this captures the trigger.
    last_process_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship("User", back_populates="experience")
    chunks: Mapped[list["ExperienceChunk"]] = relationship(
        "ExperienceChunk", back_populates="experience", cascade="all, delete-orphan"
    )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    job_url: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_job: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User | None"] = relationship("User", back_populates="jobs")
    tailorings: Mapped[list["Tailoring"]] = relationship("Tailoring", back_populates="job")
    chunks: Mapped[list["JobChunk"]] = relationship(
        "JobChunk", back_populates="job", cascade="all, delete-orphan"
    )


class Tailoring(Base):
    __tablename__ = "tailorings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id"))
    generated_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    # generation lifecycle: pending | generating | ready | error
    generation_status: Mapped[str] = mapped_column(String, default="ready", server_default="ready")
    generation_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    generation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    generation_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Set when generation completes (status → "ready"). Pairs with generation_started_at
    # to give wall-clock generation time without log parsing.
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set at the API boundary when a regen is triggered — UI "last refreshed" display field.
    last_regenerated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    enrichment_status: Mapped[str] = mapped_column(
        String, default="pending", server_default="pending"
    )
    # Matching mode used during chunk enrichment: "vector" | "llm" | null (pre-migration historical)
    matching_mode: Mapped[str | None] = mapped_column(String, nullable=True)
    # Generation telemetry — populated on completion, overwritten on regen
    generation_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_batch_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_error_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Profile snapshot — exact formatted_profile string passed to the LLM at generation time.
    # Populated on generation/regen; null for tailorings created before this column was added.
    profile_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Gap analysis — stored as JSON after generation completes. Null until gap analysis runs
    # or if gap analysis fails (non-fatal). Contains ProfileGapWithChunk[] with chunk_id refs.
    gap_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # gap_analysis_status: pending | complete
    # "complete" is set by run_gap_analysis regardless of success/failure — signals the
    # frontend that gap analysis has finished and the tailoring is fully ready to display.
    gap_analysis_status: Mapped[str] = mapped_column(
        String, default="pending", server_default="pending"
    )
    letter_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    posting_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    public_slug: Mapped[str | None] = mapped_column(String, nullable=True)
    notion_container_page_id: Mapped[str | None] = mapped_column(String, nullable=True)
    notion_page_id: Mapped[str | None] = mapped_column(String, nullable=True)
    notion_page_url: Mapped[str | None] = mapped_column(String, nullable=True)
    notion_posting_page_id: Mapped[str | None] = mapped_column(String, nullable=True)
    notion_posting_page_url: Mapped[str | None] = mapped_column(String, nullable=True)

    @hybrid_property
    def is_public(self) -> bool:
        return self.letter_public or self.posting_public

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "public_slug", name="uq_tailorings_user_public_slug"),
    )

    user: Mapped["User"] = relationship("User", back_populates="tailorings")
    job: Mapped["Job"] = relationship("Job", back_populates="tailorings")


class LlmTriggerLog(Base):
    """
    One row per LLM pipeline trigger. Used for sliding-window rate limiting.

    Storing triggers in a separate table (rather than updating a timestamp on the
    parent row) is necessary because a user can trigger the same Tailoring multiple
    times — last_regenerated_at would only record the most recent event, making 10
    rapid regens on one tailoring look like a single event in the last hour.

    event_type values: 'tailoring_create' | 'tailoring_regen' | 'experience_process'
    """

    __tablename__ = "llm_trigger_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TailoringDebugLog(Base):
    """
    One row per notable generation event. Level 3 scaffolding — table exists, nothing writes yet.

    Intended use: per-batch chunk matching results, token counts, latency per pipeline step,
    validation retry counts. Provides the raw signal the eval pipeline will aggregate.

    event_type values (planned): 'chunk_batch' | 'generation_complete' | 'validation_retry' | 'error'
    """

    __tablename__ = "tailoring_debug_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tailoring_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tailorings.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExperienceChunk(Base):
    """
    Atomic, source-traceable claim derived from extracted_profile.
    One row per bullet / skill / project / education entry.

    source_type values and lifecycle:
      resume      — parsed from uploaded resume; deleted when resume is removed
      github      — derived from GitHub repo enrichment; deleted when repo is disconnected
      user_input  — manually submitted by user; deleted per-chunk or all at once
      gap_response — user's answer to a gap question; NEVER deleted by source events,
                     only by Experience cascade (see 17-chunk-model.md)
      partial_response — user's answer to a path-to-strong question; same lifecycle as gap_response
      annotation  — (future) user-added claim on a position/project; same lifecycle as gap_response

    source_ref:  null for resume/user_input/gap_response; repo name for github
    claim_type:  work_experience | skill | project | education | other
    chunk_metadata: null for resume/github/user_input; JSON provenance for gap_response
                    and annotation — e.g. {question, job_chunk_id, tailoring_id}
    """

    __tablename__ = "experience_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experience_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("experiences.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    claim_type: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Grouping key for rendering hierarchy. Examples:
    #   work_experience → "ACME Corp | Software Engineer"
    #   project         → "MyApp"
    #   education       → "BSc Computer Science | MIT"
    #   github chunks   → repo name (mirrors source_ref)
    #   skill / other   → null (flat, no parent group)
    group_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_range: Mapped[str | None] = mapped_column(String(100), nullable=True)
    technologies: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Provenance metadata for gap_response and annotation chunks.
    # gap_response: {question: str, job_chunk_id: str, tailoring_id: str}
    # annotation:   {parent_chunk_id: str}  (future)
    # Null for resume, github, user_input.
    chunk_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    # Populated by experience_embedder.py after chunking. Null until first embed run.
    # Not exposed in API responses — internal to the matching pipeline.
    embedding = mapped_column(Vector(1536), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    experience: Mapped["Experience"] = relationship("Experience", back_populates="chunks")


class JobChunk(Base):
    __tablename__ = "job_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    chunk_type: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str | None] = mapped_column(String(255), nullable=True)
    match_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    match_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    advocacy_blurb: Mapped[str | None] = mapped_column(Text, nullable=True)
    experience_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    experience_sources: Mapped[list | None] = mapped_column(
        JSON, nullable=True
    )  # list[str]: resume, github, user_input, gap_response, additional_experience
    should_render: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    is_requirement: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scored_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Populated by experience_embedder.py after job chunk extraction.
    embedding = mapped_column(Vector(1536), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)

    job: Mapped["Job"] = relationship("Job", back_populates="chunks")

import uuid
from datetime import datetime
from sqlalchemy import String, Text, JSON, DateTime, Boolean, Integer, func, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.clients.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
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
    # Public profile
    username_slug: Mapped[str | None] = mapped_column(String, unique=True, nullable=True, index=True)
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
    profile_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    # status: pending | approved
    status: Mapped[str] = mapped_column(String, default="pending", server_default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    experience: Mapped["Experience | None"] = relationship(
        "Experience", back_populates="user", uselist=False
    )
    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="user")
    tailorings: Mapped[list["Tailoring"]] = relationship(
        "Tailoring", back_populates="user"
    )


class Experience(Base):
    __tablename__ = "experiences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
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
    user_input_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship("User", back_populates="experience")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    job_url: Mapped[str] = mapped_column(String)
    extracted_job: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User | None"] = relationship("User", back_populates="jobs")
    tailorings: Mapped[list["Tailoring"]] = relationship(
        "Tailoring", back_populates="job"
    )
    chunks: Mapped[list["JobChunk"]] = relationship(
        "JobChunk", back_populates="job", cascade="all, delete-orphan"
    )


class Tailoring(Base):
    __tablename__ = "tailorings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id")
    )
    generated_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    # generation lifecycle: pending | generating | ready | error
    generation_status: Mapped[str] = mapped_column(String, default="ready", server_default="ready")
    generation_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    generation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    generation_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    enrichment_status: Mapped[str] = mapped_column(String, default="pending", server_default="pending")
    letter_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    posting_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    public_slug: Mapped[str | None] = mapped_column(String, nullable=True)
    notion_container_page_id: Mapped[str | None] = mapped_column(String, nullable=True)
    notion_page_id: Mapped[str | None] = mapped_column(String, nullable=True)
    notion_page_url: Mapped[str | None] = mapped_column(String, nullable=True)
    notion_posting_page_id: Mapped[str | None] = mapped_column(String, nullable=True)
    notion_posting_page_url: Mapped[str | None] = mapped_column(String, nullable=True)

    @hybrid_property
    def is_public(self) -> bool:
        return self.letter_public or self.posting_public

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint('user_id', 'public_slug', name='uq_tailorings_user_public_slug'),
    )

    user: Mapped["User"] = relationship("User", back_populates="tailorings")
    job: Mapped["Job"] = relationship("Job", back_populates="tailorings")


class JobChunk(Base):
    __tablename__ = "job_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    chunk_type: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str | None] = mapped_column(String(255), nullable=True)
    match_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    match_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    experience_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    should_render: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    job: Mapped["Job"] = relationship("Job", back_populates="chunks")

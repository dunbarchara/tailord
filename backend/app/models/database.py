import uuid
from datetime import datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.clients.database import Base
from app.core.crypto import EncryptedJSON


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    # status: pending | approved
    status: Mapped[str] = mapped_column(String, default="pending", server_default="pending")
    is_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True
    )
    # Soft-delete tombstone: set on account deletion; PII (email, name) cleared at same time.
    # The row is kept indefinitely for platform metrics (account lifetime, churn cohorts).
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def candidate_name(self) -> str:
        """Resolved display name for LLM prompts. Always returns a non-empty string.
        Delegates to profile.candidate_name if profile exists."""
        if self.profile:
            preferred = " ".join(
                filter(None, [self.profile.preferred_first_name, self.profile.preferred_last_name])
            ).strip()
            if preferred:
                return preferred
        return self.name or self.email or ""

    # profile is always needed — selectin-load batches it with User queries
    profile: Mapped["UserProfile | None"] = relationship(
        "UserProfile", back_populates="user", uselist=False, lazy="selectin"
    )
    auth_identities: Mapped[list["AuthIdentity"]] = relationship(
        "AuthIdentity", back_populates="user", cascade="all, delete-orphan"
    )
    integrations: Mapped[list["UserIntegration"]] = relationship(
        "UserIntegration", back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    experience_sources: Mapped[list["ExperienceSource"]] = relationship(
        "ExperienceSource", back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="user")
    tailorings: Mapped[list["Tailoring"]] = relationship("Tailoring", back_populates="user")
    claims: Mapped[list["ExperienceClaim"]] = relationship(
        "ExperienceClaim", back_populates="user", cascade="all, delete-orphan"
    )
    groups: Mapped[list["ExperienceGroup"]] = relationship(
        "ExperienceGroup", back_populates="user", cascade="all, delete-orphan"
    )


class AuthIdentity(Base):
    """
    Provider-neutral OAuth subject. One row per (provider, subject) pair.
    Replaces users.google_sub with a normalized, extensible identity table.

    provider values: "google" (current); future: "linkedin", "magic_link"
    subject: google_sub for google; email for magic_link
    """

    __tablename__ = "auth_identities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    subject: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("provider", "subject", name="uq_auth_identities_provider_subject"),
    )

    user: Mapped["User"] = relationship("User", back_populates="auth_identities")


class UserProfile(Base):
    """
    Display preferences and public profile settings for a user (1:1 with users).
    Extracted from users to isolate profile concerns from identity/auth concerns.

    username_slug: URL-safe handle for public profile (/u/{slug}). UNIQUE, nullable
                   (unset until user chooses one or one is auto-generated at signup).
    communication_email: future use — digest/notification emails distinct from auth email.
    """

    __tablename__ = "user_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    preferred_first_name: Mapped[str | None] = mapped_column(String, nullable=True)
    preferred_last_name: Mapped[str | None] = mapped_column(String, nullable=True)
    pronouns: Mapped[str | None] = mapped_column(String, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
    username_slug: Mapped[str | None] = mapped_column(
        String, unique=True, nullable=True, index=True
    )
    profile_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # Deferred: will be used for digest/notification email routing
    communication_email: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="profile")


class UserIntegration(Base):
    """
    Per-user OAuth tokens and metadata for external service integrations.
    One row per (user_id, provider) pair.

    provider values: "notion" (current); future: "github" (per-user OAuth), "jira"
    credentials: {access_token, refresh_token?, expires_at?} — never exposed in API responses.
                 Encrypted at rest via EncryptedJSON (Fernet). Set FIELD_ENCRYPTION_KEY in env.
    provider_metadata: provider-specific non-secret data
      notion: {bot_id, workspace_id, workspace_name, parent_page_id}
      github (future): {installation_id, login}
    """

    __tablename__ = "user_integrations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    credentials: Mapped[dict | None] = mapped_column(EncryptedJSON, nullable=True)
    # Named provider_metadata in Python to avoid shadowing SQLAlchemy's Base.metadata
    provider_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True, name="metadata")
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_user_integrations_user_provider"),
    )

    user: Mapped["User"] = relationship("User", back_populates="integrations")


class ExperienceSource(Base):
    """
    One row per (user_id, source_type) pair. Replaces the monolithic Experience table.

    source_type values: "resume" | "github" | (future: "linear", "messenger", ...)
    connection_status: connected | disconnected | error
    sync_status: idle | syncing | error

    config shapes:
      resume:  {"storage_key": "users/123/abc.pdf", "filename": "resume.pdf"}
      github:  {"username": "dunbarchara"}

    source_data shapes:
      resume:  {"extracted": {...profile...}, "raw_text": "...", "corrections": {...}}
      github:  {"extracted": {...}, "repos": [...], "repo_details": {...}}
    """

    __tablename__ = "experience_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # connection_status: connected | disconnected | error
    connection_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="connected", server_default="connected"
    )
    # sync_status: idle | syncing | error
    sync_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="idle", server_default="idle"
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Cooldown anchor (was last_process_requested_at on Experience)
    last_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    # Surface connection config (non-secret)
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Pipeline artifacts + extracted content
    source_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True, name="source_data")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "source_type", name="uq_experience_sources_user_source"),
    )

    user: Mapped["User"] = relationship("User", back_populates="experience_sources")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    job_url: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_job: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # source_type: "url" | "manual"
    source_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="url", server_default="url"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="jobs")
    tailorings: Mapped[list["Tailoring"]] = relationship("Tailoring", back_populates="job")
    chunks: Mapped[list["JobChunk"]] = relationship(
        "JobChunk", back_populates="job", cascade="all, delete-orphan"
    )


class Tailoring(Base):
    __tablename__ = "tailorings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id"))
    # Deprecated: rendered markdown kept for backward compat with pre-letter_content rows.
    # New generations continue writing this as a derived artifact alongside letter_content.
    generated_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Structured letter content (JSONB). Null for rows created before this column was added.
    letter_content: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # generation lifecycle: pending | generating | ready | error
    generation_status: Mapped[str] = mapped_column(String, default="ready", server_default="ready")
    generation_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    generation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    generation_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Set when generation completes (status → "ready"). Pairs with generation_started_at.
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set at the API boundary when a regen is triggered — UI "last refreshed" display field.
    last_regenerated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Profile snapshot — exact formatted_profile string passed to the LLM at generation time.
    profile_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Gap analysis — stored as JSON after generation completes. Null until gap analysis runs.
    # Set to [] on early exits or errors so frontend polling stops on gap_analysis !== null.
    gap_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    letter_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    posting_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    public_slug: Mapped[str | None] = mapped_column(String, nullable=True)
    # Generation telemetry JSONB. Keys: duration_ms, matching_mode, batch_count, batch_errors.
    generation_telemetry: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Notion export JSONB. Keys: container_page_id, page_id, page_url, posting_page_id, posting_page_url.
    notion_export: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # LLM models used. Keys: letter (scoring model planned).
    models: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Resume draft JSONB. Populated by POST /tailorings/{id}/resume/generate.
    # Shape: ResumeDraft — sections, skills_claim_ids, education_group_ids, contact_override, warnings.
    resume_draft: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    @hybrid_property
    def is_public(self) -> bool:
        return self.letter_public or self.posting_public

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("user_id", "public_slug", name="uq_tailorings_user_public_slug"),
    )

    user: Mapped["User"] = relationship("User", back_populates="tailorings")
    job: Mapped["Job"] = relationship("Job", back_populates="tailorings")


class LlmUsageLog(Base):
    """
    One row per LLM pipeline trigger. Serves two purposes:
    1. Rate limiting — hourly burst limit (sliding window count)
    2. Billing usage — monthly tailoring count for quota enforcement
    3. Cost tracking — token counts and cost_usd for analytics (populated when
       LLM call instrumentation ships; nullable until then)

    event_type values:
      'tailoring_create'  — full tailoring pipeline (counts toward monthly quota)
      'tailoring_regen'   — full regen (counts toward monthly quota)
      'letter_regen'      — letter-only regen; counts toward hourly burst but NOT monthly quota
      'resume_process'    — LLM resume profile extraction (renamed from experience_process)
      'github_enrich'     — LLM GitHub repo enrichment (tracked, not yet rate-limited)
      'gap_analysis'      — gap question generation (tracked when run independently)
    """

    __tablename__ = "llm_usage_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TailoringDebugLog(Base):
    """
    One row per notable generation event. Written via _write_debug_log() in tailorings.py.

    Intended use: per-batch chunk matching results, token counts, latency per pipeline step,
    validation retry counts. Provides the raw signal the eval pipeline will aggregate.

    event_type values: 'generation_complete' | (planned) 'chunk_batch' | 'validation_retry' | 'error'

    user_id: nullable FK (SET NULL on delete) — populated at write time for per-user analytics.
    payload: JSONB for operator support and GIN indexing.
    Index: ix_tailoring_debug_logs_event_time on (event_type, created_at) for eval-mining queries.
    Retention: 90 days (amortized cleanup in _finalize_tailoring).
    """

    __tablename__ = "tailoring_debug_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tailoring_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tailorings.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExperienceGroup(Base):
    """
    Parent container for grouped ExperienceClaims (roles, projects, repos, education).

    One level of nesting only: claims belong to a group, groups belong to an experience.
    Groups are context — they are not embedded. When an ExperienceClaim with a group_id
    is passed to the LLM, the group context is prepended by the retrieval layer.

    group_type values: role | project | repository | education | custom
    type_meta: JSONB with type-specific fields (see design doc — no migration needed
               for new group types, just a new Pydantic variant).
    """

    __tablename__ = "experience_groups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    group_type: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    end_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    type_meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Ordered position within user's group list (ascending). Null = unordered (pre-migration rows).
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provenance_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    provenance_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Group-level tags — propagate context to claims during retrieval (e.g. "fintech", "open_source")
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # Free-text description — used by 'custom' group type; name alone isn't enough LLM context
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="groups")
    claims: Mapped[list["ExperienceClaim"]] = relationship(
        "ExperienceClaim", back_populates="group"
    )


class ExperienceClaim(Base):
    """
    Atomic, source-traceable claim derived from extracted_profile.
    One row per bullet / skill / project / education entry.

    source_type values and lifecycle:
      resume      — parsed from uploaded resume; deleted when resume is removed
      github      — derived from GitHub repo enrichment; deleted when repo is disconnected
      user_input  — manually submitted by user; deleted per-claim or all at once
      gap_response — user's answer to a gap question; NEVER deleted by source events,
                     only by Experience cascade
      partial_response — user's answer to a path-to-strong question; same lifecycle as gap_response
      annotation  — (future) user-added claim on a position/project; same lifecycle as gap_response

    source_ref:  null for resume/user_input/gap_response; repo name for github
    claim_type:  work_experience | skill | project | education | other

    group_id: FK → experience_groups. Null = ungrouped/standalone. SET NULL on group delete.
    group_key: deprecated denormalized string (kept until group_id backfill is verified).

    confidence:  high   = user directly stated (gap_response, user_input, annotation)
                 medium = LLM-extracted from structure (resume, PR description)
                 low    = inferred by pipeline (GitHub stack detection)
    status:      pending | active | archived

    provenance_metadata: null for resume/github/user_input; JSONB provenance for gap_response
                         and annotation — e.g. {question, job_chunk_id, tailoring_id}

    original_content: set on first user edit (null = never edited); enables revert.
    merged_from: [{id, source_type, content_snapshot}] — set when claim is created by
                 dedup merge pipeline; null for all normal claims.
    """

    __tablename__ = "experience_claims"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("experience_groups.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    claim_type: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # group_key: deprecated — replaced by group_id → experience_groups.
    # Kept until backfill is verified; will be dropped in a future migration.
    group_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_range: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Formerly 'technologies' — renamed to 'keywords' for industry neutrality
    # (PostgreSQL, Watercolor, GAAP, and Ableton all belong here, not just tech stacks).
    keywords: Mapped[list | None] = mapped_column(JSON, nullable=True, name="keywords")
    confidence: Mapped[str] = mapped_column(
        String(20), nullable=False, default="medium", server_default="medium"
    )
    # pending | active | archived  ('pending' = silent-capture pipeline, not shown to user yet)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", server_default="active"
    )
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Consolidated provenance field. Replaces chunk_metadata (legacy), provenance_url, provenance_label.
    # gap_response/partial_response: {question: str, job_chunk_id: str, tailoring_id: str}
    # annotation (future):           {parent_claim_id: str}
    # With link:                     {..., url: str, label: str}
    # Null for resume, github, user_input.
    provenance_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Set on first user edit (null = never edited). Enables revert to original extracted content.
    original_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Set by dedup pipeline when this claim is created from merged duplicates.
    # Shape: [{id: str, source_type: str, content_snapshot: str}, ...]
    merged_from: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    # Populated by experience_embedder.py after chunking. Null until first embed run.
    # Not exposed in API responses — internal to the matching pipeline.
    embedding = mapped_column(Vector(1536), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="claims")
    group: Mapped["ExperienceGroup | None"] = relationship(
        "ExperienceGroup", back_populates="claims"
    )


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
    experience_sources: Mapped[list | None] = mapped_column(
        JSON, nullable=True
    )  # list[str]: resume, github, user_input, gap_response, additional_experience
    should_render: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    include_in_scoring: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    # semantic_type: set at initial extraction; never updated on refresh.
    # Values: job_requirement | role_description | company_description | compensation |
    #         location | application_info | legal | other
    semantic_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # evaluation_status: scored | skipped | error | null (pre-migration rows)
    evaluation_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    scored_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Populated by experience_embedder.py after job chunk extraction.
    embedding = mapped_column(Vector(1536), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)

    job: Mapped["Job"] = relationship("Job", back_populates="chunks")

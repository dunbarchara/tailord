"""replace_experiences_with_experience_sources

Replaces the monolithic `experiences` table (one row per user, conflating
pipeline state, resume data, GitHub data, and LLM artifacts) with
`experience_sources`: one row per (user_id, source_type) pair. Each source
has independent connection_status and sync_status fields, and surface-specific
data in config/source_data JSONB columns.

Column mapping from experiences → experience_sources:
  storage_key              → config["storage_key"]           (resume row)
  filename                 → config["filename"]              (resume row)
  raw_resume_text          → source_data["raw_text"]         (resume row)
  extracted_profile.resume → source_data["extracted"]        (resume row)
  extracted_profile.corrections → source_data["corrections"] (resume row)
  extracted_profile.github → source_data["extracted"]        (github row)
  github_username          → config["username"]              (github row)
  github_repos             → source_data["repos"]            (github row)
  github_repo_details      → source_data["repo_details"]     (github row)
  status                   → per-source connection_status + sync_status
  error_message            → per-source error_message
  uploaded_at              → created_at                      (resume row)
  processed_at             → last_synced_at                  (resume row)
  last_process_requested_at → last_requested_at              (resume row)
  user_input_text          → DROPPED (claims are source of truth)

Revision ID: b4d5e6f7a8b9
Revises: a7b8c9d0e1f2
Create Date: 2026-05-27 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Create experience_sources ──────────────────────────────────────────
    op.create_table(
        "experience_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(30), nullable=False),
        # connection_status: connected | disconnected | error
        sa.Column(
            "connection_status",
            sa.String(20),
            nullable=False,
            server_default="connected",
        ),
        # sync_status: idle | syncing | error
        sa.Column(
            "sync_status",
            sa.String(20),
            nullable=False,
            server_default="idle",
        ),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        # config: surface connection config (non-secret); resume: {storage_key, filename}; github: {username}
        sa.Column("config", postgresql.JSONB(), nullable=True),
        # source_data: pipeline artifacts + extracted content
        # resume: {extracted: {...}, raw_text: "...", corrections: {...}}
        # github: {extracted: {...}, repos: [...], repo_details: {...}}
        sa.Column("source_data", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
            name="fk_experience_sources_user_id_users",
        ),
        sa.UniqueConstraint("user_id", "source_type", name="uq_experience_sources_user_source"),
    )
    op.create_index("ix_experience_sources_user_id", "experience_sources", ["user_id"])

    # ── 2. Backfill resume rows from experiences ───────────────────────────────
    # Include any row that had a storage_key OR has extracted_profile['resume'].
    op.execute("""
        INSERT INTO experience_sources (
            id, user_id, source_type,
            connection_status, sync_status,
            last_synced_at, last_requested_at,
            error_message, config, source_data,
            created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            user_id,
            'resume',
            CASE status
                WHEN 'error' THEN 'error'
                WHEN 'pending' THEN 'disconnected'
                ELSE 'connected'
            END,
            CASE status
                WHEN 'processing' THEN 'syncing'
                WHEN 'error' THEN 'error'
                ELSE 'idle'
            END,
            processed_at,
            last_process_requested_at,
            CASE WHEN status = 'error' THEN error_message ELSE NULL END,
            jsonb_strip_nulls(jsonb_build_object(
                'storage_key', storage_key,
                'filename', filename
            )),
            jsonb_strip_nulls(jsonb_build_object(
                'extracted', (extracted_profile::jsonb)->'resume',
                'raw_text', to_jsonb(raw_resume_text),
                'corrections', (extracted_profile::jsonb)->'corrections'
            )),
            COALESCE(uploaded_at, NOW()),
            NOW()
        FROM experiences
        WHERE storage_key IS NOT NULL
           OR (extracted_profile IS NOT NULL AND extracted_profile::jsonb ? 'resume')
    """)

    # ── 3. Backfill github rows from experiences ───────────────────────────────
    op.execute("""
        INSERT INTO experience_sources (
            id, user_id, source_type,
            connection_status, sync_status,
            last_synced_at, last_requested_at,
            error_message, config, source_data,
            created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            user_id,
            'github',
            'connected',
            'idle',
            processed_at,
            NULL,
            NULL,
            jsonb_build_object('username', github_username),
            jsonb_strip_nulls(jsonb_build_object(
                'extracted', (extracted_profile::jsonb)->'github',
                'repos', to_jsonb(github_repos),
                'repo_details', to_jsonb(github_repo_details)
            )),
            NOW(),
            NOW()
        FROM experiences
        WHERE github_username IS NOT NULL
    """)

    # ── 4. Drop the experiences table ─────────────────────────────────────────
    op.drop_table("experiences")


def downgrade() -> None:
    # ── Recreate experiences ───────────────────────────────────────────────────
    op.create_table(
        "experiences",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("storage_key", sa.String(), nullable=True),
        sa.Column("filename", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("extracted_profile", sa.JSON(), nullable=True),
        sa.Column("raw_resume_text", sa.Text(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("github_username", sa.String(), nullable=True),
        sa.Column("github_repos", sa.JSON(), nullable=True),
        sa.Column("github_repo_details", sa.JSON(), nullable=True),
        sa.Column("user_input_text", sa.Text(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_process_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("user_id", name="uq_experiences_user_id"),
    )

    # Backfill resume data from experience_sources
    op.execute("""
        INSERT INTO experiences (
            id, user_id, storage_key, filename, status,
            extracted_profile, raw_resume_text, error_message,
            processed_at, last_process_requested_at, uploaded_at
        )
        SELECT
            gen_random_uuid(),
            user_id,
            config->>'storage_key',
            config->>'filename',
            CASE connection_status
                WHEN 'error' THEN 'error'
                WHEN 'disconnected' THEN 'pending'
                ELSE CASE sync_status WHEN 'syncing' THEN 'processing' ELSE 'ready' END
            END,
            jsonb_strip_nulls(jsonb_build_object(
                'resume', source_data->'extracted',
                'corrections', source_data->'corrections'
            ))::json,
            source_data->>'raw_text',
            error_message,
            last_synced_at,
            last_requested_at,
            created_at
        FROM experience_sources
        WHERE source_type = 'resume'
        ON CONFLICT (user_id) DO NOTHING
    """)

    # Merge github data into existing experience rows
    op.execute("""
        UPDATE experiences e
        SET
            github_username = gs.config->>'username',
            github_repos = (gs.source_data->'repos')::json,
            github_repo_details = (gs.source_data->'repo_details')::json,
            extracted_profile = (COALESCE(e.extracted_profile::jsonb, '{}'::jsonb)
                || jsonb_build_object('github', gs.source_data->'extracted'))::json
        FROM experience_sources gs
        WHERE gs.user_id = e.user_id
          AND gs.source_type = 'github'
    """)

    # Insert experience rows for users that only have github (no resume)
    op.execute("""
        INSERT INTO experiences (
            id, user_id, status, github_username, github_repos,
            github_repo_details, extracted_profile, processed_at
        )
        SELECT
            gen_random_uuid(),
            gs.user_id,
            'ready',
            gs.config->>'username',
            gs.source_data->'repos',
            gs.source_data->'repo_details',
            jsonb_build_object('github', gs.source_data->'extracted')::json,
            gs.last_synced_at
        FROM experience_sources gs
        WHERE gs.source_type = 'github'
          AND NOT EXISTS (
              SELECT 1 FROM experiences e WHERE e.user_id = gs.user_id
          )
        ON CONFLICT (user_id) DO NOTHING
    """)

    # ── Drop experience_sources ────────────────────────────────────────────────
    op.drop_index("ix_experience_sources_user_id", table_name="experience_sources")
    op.drop_table("experience_sources")

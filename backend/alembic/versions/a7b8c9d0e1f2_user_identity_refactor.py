"""user_identity_refactor

Splits the monolithic users table into three concern-separated tables:
- auth_identities: provider-neutral OAuth subjects (replaces google_sub)
- user_profiles: display preferences + public profile settings
- user_integrations: per-user OAuth tokens for external services (Notion, future GitHub)

Also adds updated_at + deleted_at to users for audit and soft-delete tombstone support,
and drops the migrated columns from users in the same transaction.

Revision ID: a7b8c9d0e1f2
Revises: f5a6b7c8d9e0
Create Date: 2026-05-27 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f5a6b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Create auth_identities ─────────────────────────────────────────────
    op.create_table(
        "auth_identities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column(
            "connected_at",
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("provider", "subject", name="uq_auth_identities_provider_subject"),
    )
    op.create_index("ix_auth_identities_user_id", "auth_identities", ["user_id"])

    # ── 2. Create user_profiles ───────────────────────────────────────────────
    op.create_table(
        "user_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("preferred_first_name", sa.String(), nullable=True),
        sa.Column("preferred_last_name", sa.String(), nullable=True),
        sa.Column("pronouns", sa.String(), nullable=True),
        sa.Column("avatar_url", sa.String(), nullable=True),
        sa.Column("username_slug", sa.String(), nullable=True),
        sa.Column(
            "profile_public",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("communication_email", sa.String(), nullable=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_user_profiles_user_id"),
        sa.UniqueConstraint("username_slug", name="uq_user_profiles_username_slug"),
    )
    op.create_index("ix_user_profiles_username_slug", "user_profiles", ["username_slug"])

    # ── 3. Create user_integrations ───────────────────────────────────────────
    op.create_table(
        "user_integrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("credentials", postgresql.JSONB(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "connected_at",
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "provider", name="uq_user_integrations_user_provider"),
    )
    op.create_index("ix_user_integrations_user_id", "user_integrations", ["user_id"])

    # ── 4. Add updated_at + deleted_at to users ───────────────────────────────
    op.add_column(
        "users",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── 5. Backfill auth_identities from users.google_sub ────────────────────
    op.execute("""
        INSERT INTO auth_identities (id, user_id, provider, subject, email, connected_at, updated_at)
        SELECT
            gen_random_uuid(),
            id,
            'google',
            google_sub,
            email,
            created_at,
            created_at
        FROM users
        WHERE google_sub IS NOT NULL
    """)

    # ── 6. Backfill user_profiles from users profile fields ──────────────────
    op.execute("""
        INSERT INTO user_profiles (
            id, user_id,
            preferred_first_name, preferred_last_name, pronouns, avatar_url,
            username_slug, profile_public,
            created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            id,
            preferred_first_name,
            preferred_last_name,
            pronouns,
            avatar_url,
            username_slug,
            profile_public,
            created_at,
            created_at
        FROM users
    """)

    # ── 7. Backfill user_integrations from users notion fields ───────────────
    op.execute("""
        INSERT INTO user_integrations (id, user_id, provider, credentials, metadata, connected_at, updated_at)
        SELECT
            gen_random_uuid(),
            id,
            'notion',
            jsonb_build_object('access_token', notion_access_token),
            jsonb_build_object(
                'bot_id', notion_bot_id,
                'workspace_id', notion_workspace_id,
                'workspace_name', notion_workspace_name,
                'parent_page_id', notion_parent_page_id
            ),
            created_at,
            created_at
        FROM users
        WHERE notion_access_token IS NOT NULL
    """)

    # ── 8. Drop migrated columns from users ───────────────────────────────────
    op.drop_index("ix_users_google_sub", table_name="users")
    op.drop_column("users", "google_sub")

    op.drop_column("users", "preferred_first_name")
    op.drop_column("users", "preferred_last_name")
    op.drop_column("users", "pronouns")
    op.drop_column("users", "avatar_url")

    op.drop_index("ix_users_username_slug", table_name="users")
    op.drop_column("users", "username_slug")
    op.drop_column("users", "profile_public")

    op.drop_column("users", "notion_access_token")
    op.drop_column("users", "notion_bot_id")
    op.drop_column("users", "notion_workspace_id")
    op.drop_column("users", "notion_workspace_name")
    op.drop_column("users", "notion_parent_page_id")


def downgrade() -> None:
    # ── Restore migrated columns on users ────────────────────────────────────
    op.add_column("users", sa.Column("notion_parent_page_id", sa.String(), nullable=True))
    op.add_column("users", sa.Column("notion_workspace_name", sa.String(), nullable=True))
    op.add_column("users", sa.Column("notion_workspace_id", sa.String(), nullable=True))
    op.add_column("users", sa.Column("notion_bot_id", sa.String(), nullable=True))
    op.add_column("users", sa.Column("notion_access_token", sa.String(), nullable=True))

    op.add_column(
        "users",
        sa.Column("profile_public", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("users", sa.Column("username_slug", sa.String(), nullable=True))
    op.create_index("ix_users_username_slug", "users", ["username_slug"], unique=True)
    op.add_column("users", sa.Column("avatar_url", sa.String(), nullable=True))
    op.add_column("users", sa.Column("pronouns", sa.String(), nullable=True))
    op.add_column("users", sa.Column("preferred_last_name", sa.String(), nullable=True))
    op.add_column("users", sa.Column("preferred_first_name", sa.String(), nullable=True))

    op.add_column("users", sa.Column("google_sub", sa.String(), nullable=True))
    op.create_index("ix_users_google_sub", "users", ["google_sub"], unique=True)

    # Backfill from new tables (best-effort)
    op.execute("""
        UPDATE users u
        SET google_sub = ai.subject
        FROM auth_identities ai
        WHERE ai.user_id = u.id AND ai.provider = 'google'
    """)

    op.execute("""
        UPDATE users u
        SET
            preferred_first_name = up.preferred_first_name,
            preferred_last_name = up.preferred_last_name,
            pronouns = up.pronouns,
            avatar_url = up.avatar_url,
            username_slug = up.username_slug,
            profile_public = up.profile_public
        FROM user_profiles up
        WHERE up.user_id = u.id
    """)

    op.execute("""
        UPDATE users u
        SET
            notion_access_token = (ui.credentials->>'access_token'),
            notion_bot_id = (ui.metadata->>'bot_id'),
            notion_workspace_id = (ui.metadata->>'workspace_id'),
            notion_workspace_name = (ui.metadata->>'workspace_name'),
            notion_parent_page_id = (ui.metadata->>'parent_page_id')
        FROM user_integrations ui
        WHERE ui.user_id = u.id AND ui.provider = 'notion'
    """)

    # ── Drop new tables ───────────────────────────────────────────────────────
    op.drop_table("user_integrations")
    op.drop_table("user_profiles")
    op.drop_table("auth_identities")

    # ── Remove added columns from users ──────────────────────────────────────
    op.drop_column("users", "deleted_at")
    op.drop_column("users", "updated_at")

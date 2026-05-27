"""replace_experience_id_with_user_id_on_claims_and_groups

ExperienceClaim and ExperienceGroup previously owned their parent reference
via experience_id (FK → experiences.id).  Since User ↔ Experience is a hard
1:1, experience_id and user_id are functionally identical for ownership scoping.
This migration replaces the redundant FK with a direct user_id FK on both tables,
eliminating the two-step ownership join.

Revision ID: f5a6b7c8d9e0
Revises: d2e3f4a5b6c7
Create Date: 2026-05-27 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f5a6b7c8d9e0"
down_revision: Union[str, Sequence[str], None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── experience_claims ────────────────────────────────────────────────────

    # 1. Add nullable user_id column
    op.add_column(
        "experience_claims",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # 2. Backfill from experiences
    op.execute("""
        UPDATE experience_claims ec
        SET user_id = e.user_id
        FROM experiences e
        WHERE ec.experience_id = e.id
    """)

    # 3. Make non-nullable and index
    op.alter_column("experience_claims", "user_id", nullable=False)
    op.create_foreign_key(
        "fk_experience_claims_user_id_users",
        "experience_claims",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_experience_claims_user_id", "experience_claims", ["user_id"])

    # 4. Drop old FK and index on experience_id
    op.drop_constraint(
        "experience_chunks_experience_id_fkey", "experience_claims", type_="foreignkey"
    )
    op.drop_index("ix_experience_claims_experience_id", table_name="experience_claims")
    op.drop_column("experience_claims", "experience_id")

    # ── experience_groups ─────────────────────────────────────────────────────

    # 1. Add nullable user_id column
    op.add_column(
        "experience_groups",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # 2. Backfill from experiences
    op.execute("""
        UPDATE experience_groups eg
        SET user_id = e.user_id
        FROM experiences e
        WHERE eg.experience_id = e.id
    """)

    # 3. Make non-nullable and index
    op.alter_column("experience_groups", "user_id", nullable=False)
    op.create_foreign_key(
        "fk_experience_groups_user_id_users",
        "experience_groups",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_experience_groups_user_id", "experience_groups", ["user_id"])

    # 4. Drop old FK and index on experience_id
    op.drop_constraint(
        "experience_groups_experience_id_fkey", "experience_groups", type_="foreignkey"
    )
    op.drop_index("ix_experience_groups_experience_id", table_name="experience_groups")
    op.drop_column("experience_groups", "experience_id")


def downgrade() -> None:
    # ── experience_groups ─────────────────────────────────────────────────────

    op.add_column(
        "experience_groups",
        sa.Column("experience_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute("""
        UPDATE experience_groups eg
        SET experience_id = e.id
        FROM experiences e
        WHERE eg.user_id = e.user_id
    """)
    op.alter_column("experience_groups", "experience_id", nullable=False)
    op.create_foreign_key(
        "experience_groups_experience_id_fkey",
        "experience_groups",
        "experiences",
        ["experience_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_experience_groups_experience_id", "experience_groups", ["experience_id"]
    )
    op.drop_constraint(
        "fk_experience_groups_user_id_users", "experience_groups", type_="foreignkey"
    )
    op.drop_index("ix_experience_groups_user_id", table_name="experience_groups")
    op.drop_column("experience_groups", "user_id")

    # ── experience_claims ────────────────────────────────────────────────────

    op.add_column(
        "experience_claims",
        sa.Column("experience_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute("""
        UPDATE experience_claims ec
        SET experience_id = e.id
        FROM experiences e
        WHERE ec.user_id = e.user_id
    """)
    op.alter_column("experience_claims", "experience_id", nullable=False)
    op.create_foreign_key(
        "experience_claims_experience_id_fkey",
        "experience_claims",
        "experiences",
        ["experience_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_experience_claims_experience_id", "experience_claims", ["experience_id"]
    )
    op.drop_constraint(
        "fk_experience_claims_user_id_users", "experience_claims", type_="foreignkey"
    )
    op.drop_index("ix_experience_claims_user_id", table_name="experience_claims")
    op.drop_column("experience_claims", "user_id")

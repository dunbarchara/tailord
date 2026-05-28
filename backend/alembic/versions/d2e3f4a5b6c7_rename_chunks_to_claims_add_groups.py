"""rename_experience_chunks_to_claims_and_add_groups

Adds the ExperienceGroup table and renames experience_chunks → experience_claims.
Adds new columns to experience_claims: group_id, confidence, status,
provenance_url, provenance_label, tags.

group_key is intentionally preserved (deprecated — drop after backfill confirmed).

Revision ID: d2e3f4a5b6c7
Revises: f9c5c4e0d3fd
Create Date: 2026-05-27 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, Sequence[str], None] = "f9c5c4e0d3fd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Rename experience_chunks → experience_claims ───────────────────────
    op.rename_table("experience_chunks", "experience_claims")
    op.drop_index("ix_experience_chunks_experience_id", table_name="experience_claims")
    op.create_index(
        "ix_experience_claims_experience_id", "experience_claims", ["experience_id"]
    )

    # ── 2. Create experience_groups ───────────────────────────────────────────
    op.create_table(
        "experience_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("experience_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("group_type", sa.String(30), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("start_date", sa.String(50), nullable=True),
        sa.Column("end_date", sa.String(50), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("type_meta", postgresql.JSONB(), nullable=True),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("source_ref", sa.String(255), nullable=True),
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
        sa.ForeignKeyConstraint(["experience_id"], ["experiences.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_experience_groups_experience_id", "experience_groups", ["experience_id"]
    )

    # ── 3. Add new columns to experience_claims ───────────────────────────────
    # group_id FK — nullable; SET NULL when group is deleted (claim becomes ungrouped)
    op.add_column(
        "experience_claims",
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        None,
        "experience_claims",
        "experience_groups",
        ["group_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "experience_claims",
        sa.Column(
            "confidence", sa.String(20), nullable=False, server_default="medium"
        ),
    )
    op.add_column(
        "experience_claims",
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
    )
    op.add_column(
        "experience_claims",
        sa.Column("provenance_url", sa.String(500), nullable=True),
    )
    op.add_column(
        "experience_claims",
        sa.Column("provenance_label", sa.String(255), nullable=True),
    )
    op.add_column(
        "experience_claims",
        sa.Column("tags", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    # Remove new columns
    op.drop_column("experience_claims", "tags")
    op.drop_column("experience_claims", "provenance_label")
    op.drop_column("experience_claims", "provenance_url")
    op.drop_column("experience_claims", "status")
    op.drop_column("experience_claims", "confidence")
    # Drop FK constraint before dropping column
    op.drop_constraint(
        op.f("fk_experience_claims_group_id_experience_groups"),
        "experience_claims",
        type_="foreignkey",
    )
    op.drop_column("experience_claims", "group_id")

    # Drop experience_groups
    op.drop_index("ix_experience_groups_experience_id", table_name="experience_groups")
    op.drop_table("experience_groups")

    # Rename index and table back
    op.drop_index("ix_experience_claims_experience_id", table_name="experience_claims")
    op.create_index(
        "ix_experience_chunks_experience_id", "experience_claims", ["experience_id"]
    )
    op.rename_table("experience_claims", "experience_chunks")

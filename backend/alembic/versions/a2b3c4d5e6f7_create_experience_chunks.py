"""create_experience_chunks

Revision ID: a2b3c4d5e6f7
Revises: f4a5b6c7d8e9
Create Date: 2026-04-26 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "a2b3c4d5e6f7"
down_revision = "f4a5b6c7d8e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "experience_chunks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("experience_id", sa.UUID(), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("source_ref", sa.String(length=255), nullable=True),
        sa.Column("claim_type", sa.String(length=30), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("date_range", sa.String(length=100), nullable=True),
        sa.Column("technologies", sa.JSON(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["experience_id"], ["experiences.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_experience_chunks_experience_id"),
        "experience_chunks",
        ["experience_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_experience_chunks_experience_id"), table_name="experience_chunks"
    )
    op.drop_table("experience_chunks")

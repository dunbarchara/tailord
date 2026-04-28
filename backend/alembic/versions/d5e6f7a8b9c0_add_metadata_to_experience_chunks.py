"""add_metadata_to_experience_chunks

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-04-28 00:00:00.000000

Adds a nullable JSON chunk_metadata column to experience_chunks.

Used by:
  - gap_response chunks: stores {question, job_chunk_id, tailoring_id}
  - annotation chunks (future): stores {parent_chunk_id}

Null for all existing chunk types (resume, github, user_input).
No FK constraints — provenance is stored as string IDs to keep
gap_response chunks independent of tailoring/job lifecycle.
"""

import sqlalchemy as sa
from alembic import op

revision = "d5e6f7a8b9c0"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "experience_chunks",
        sa.Column("chunk_metadata", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("experience_chunks", "chunk_metadata")

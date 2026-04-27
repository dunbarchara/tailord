"""add_embedding_columns

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-04-27 00:00:00.000000

Adds vector embedding columns to experience_chunks and job_chunks.
Enables the pgvector extension (idempotent — safe if already enabled by the
postgres-init SQL script that runs on first container start).

Dimensions: 1536 — matches text-embedding-3-small (OpenAI default).
Changing to a model with different dimensions requires a new migration.
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "c4d5e6f7a8b9"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column("experience_chunks", sa.Column("embedding", Vector(1536), nullable=True))
    op.add_column(
        "experience_chunks", sa.Column("embedding_model", sa.String(length=100), nullable=True)
    )
    op.add_column("job_chunks", sa.Column("embedding", Vector(1536), nullable=True))
    op.add_column(
        "job_chunks", sa.Column("embedding_model", sa.String(length=100), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("job_chunks", "embedding_model")
    op.drop_column("job_chunks", "embedding")
    op.drop_column("experience_chunks", "embedding_model")
    op.drop_column("experience_chunks", "embedding")

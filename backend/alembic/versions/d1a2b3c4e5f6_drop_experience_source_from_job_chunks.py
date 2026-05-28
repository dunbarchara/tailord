"""drop_experience_source_from_job_chunks

The experience_source (singular) column on job_chunks is superseded by
experience_sources (array). All code now reads from the array.

Revision ID: d1a2b3c4e5f6
Revises: c5d6e7f8a9b0
Create Date: 2026-05-28 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d1a2b3c4e5f6"
down_revision: Union[str, None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("job_chunks", "experience_source")


def downgrade() -> None:
    op.add_column(
        "job_chunks",
        sa.Column("experience_source", sa.String(50), nullable=True),
    )
    # Backfill from first element of the array
    op.execute(
        "UPDATE job_chunks SET experience_source = experience_sources->>0 "
        "WHERE experience_sources IS NOT NULL AND jsonb_array_length(experience_sources::jsonb) > 0"
    )

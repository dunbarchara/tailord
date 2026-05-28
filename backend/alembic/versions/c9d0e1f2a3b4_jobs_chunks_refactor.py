"""jobs_chunks_refactor

Revision ID: c9d0e1f2a3b4
Revises: a4b5c6d7e8f9
Create Date: 2026-05-28 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, None] = "a4b5c6d7e8f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # job_chunks: rename is_requirement → include_in_scoring
    op.alter_column(
        "job_chunks",
        "is_requirement",
        new_column_name="include_in_scoring",
        existing_type=sa.Boolean(),
        existing_nullable=False,
        existing_server_default="true",
    )

    op.add_column("job_chunks", sa.Column("semantic_type", sa.String(30), nullable=True))

    op.add_column(
        "job_chunks",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.add_column(
        "job_chunks",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.add_column("job_chunks", sa.Column("evaluation_status", sa.String(20), nullable=True))

    op.execute("""
        UPDATE job_chunks
        SET evaluation_status = CASE
            WHEN match_score IN (0, 1, 2) THEN 'scored'
            WHEN match_score = -1
                 AND match_rationale IS NOT NULL
                 AND LOWER(match_rationale) LIKE '%error%' THEN 'error'
            WHEN match_score = -1 THEN 'skipped'
        END
        WHERE match_score IS NOT NULL
    """)

    # jobs: add source_type
    op.add_column(
        "jobs",
        sa.Column(
            "source_type", sa.String(20), server_default="url", nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("jobs", "source_type")
    op.drop_column("job_chunks", "evaluation_status")
    op.drop_column("job_chunks", "updated_at")
    op.drop_column("job_chunks", "created_at")
    op.drop_column("job_chunks", "semantic_type")
    op.alter_column(
        "job_chunks",
        "include_in_scoring",
        new_column_name="is_requirement",
        existing_type=sa.Boolean(),
        existing_nullable=False,
        existing_server_default="true",
    )

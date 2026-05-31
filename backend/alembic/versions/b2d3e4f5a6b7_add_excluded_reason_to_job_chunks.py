"""add excluded_reason to job_chunks

Revision ID: b2d3e4f5a6b7
Revises: a0b1c2d3e4f5
Create Date: 2026-05-29 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2d3e4f5a6b7"
down_revision: Union[str, None] = "a0b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "job_chunks",
        sa.Column("excluded_reason", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("job_chunks", "excluded_reason")

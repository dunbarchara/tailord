"""make_job_extracted_job_nullable

Revision ID: bcfb04fef2f6
Revises: g1h2i3j4k5l6
Create Date: 2026-03-19 14:26:19.578584

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bcfb04fef2f6'
down_revision: Union[str, Sequence[str], None] = 'g1h2i3j4k5l6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('jobs', 'extracted_job', nullable=True)


def downgrade() -> None:
    op.alter_column('jobs', 'extracted_job', nullable=False)

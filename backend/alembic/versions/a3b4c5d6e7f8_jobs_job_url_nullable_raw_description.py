"""jobs_job_url_nullable_raw_description

Revision ID: a3b4c5d6e7f8
Revises: e85b470648f4
Create Date: 2026-05-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a3b4c5d6e7f8'
down_revision: Union[str, Sequence[str], None] = 'e85b470648f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('jobs', 'job_url', nullable=True)
    op.add_column('jobs', sa.Column('raw_description', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('jobs', 'raw_description')
    # Restore NOT NULL: requires existing rows have a value; acceptable for managed downgrade.
    op.alter_column('jobs', 'job_url', nullable=False)

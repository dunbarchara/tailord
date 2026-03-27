"""add_advocacy_blurb_to_job_chunks

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-03-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a3b4c5d6e7f8'
down_revision: Union[str, None] = 'f2a3b4c5d6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('job_chunks', sa.Column('advocacy_blurb', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('job_chunks', 'advocacy_blurb')

"""add_preferred_name_to_users

Revision ID: f3a1e2d4c5b6
Revises: e7f2a1b3c8d9
Create Date: 2026-03-07 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f3a1e2d4c5b6'
down_revision: Union[str, Sequence[str], None] = 'e7f2a1b3c8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('preferred_first_name', sa.String(), nullable=True))
    op.add_column('users', sa.Column('preferred_last_name', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'preferred_last_name')
    op.drop_column('users', 'preferred_first_name')

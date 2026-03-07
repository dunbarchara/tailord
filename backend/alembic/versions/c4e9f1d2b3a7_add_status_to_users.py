"""add_status_to_users

Revision ID: c4e9f1d2b3a7
Revises: 2696096fffe0
Create Date: 2026-03-06 00:00:00.000000

NOTE: After applying this migration all existing users will have status='pending'.
Approve active users before deploying the frontend access gate:
  UPDATE users SET status = 'approved' WHERE email IN ('your@email.com');
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4e9f1d2b3a7'
down_revision: Union[str, Sequence[str], None] = '2696096fffe0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('status', sa.String(), nullable=False, server_default='pending'))


def downgrade() -> None:
    op.drop_column('users', 'status')

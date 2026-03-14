"""add_per_view_public_sharing

Revision ID: b8c9d0e1f2a3
Revises: a1b2c3d4e5f6
Create Date: 2026-03-13 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, Sequence[str], None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tailorings', sa.Column('letter_public', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('tailorings', sa.Column('posting_public', sa.Boolean(), nullable=False, server_default='false'))
    op.execute("UPDATE tailorings SET letter_public = is_public")


def downgrade() -> None:
    op.drop_column('tailorings', 'posting_public')
    op.drop_column('tailorings', 'letter_public')

"""add_public_sharing_to_tailorings

Revision ID: a1b2c3d4e5f6
Revises: e7f2a1b3c8d9
Create Date: 2026-03-10 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f3a1e2d4c5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tailorings', sa.Column('is_public', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('tailorings', sa.Column('public_slug', sa.String(), nullable=True))
    op.create_unique_constraint('uq_tailorings_public_slug', 'tailorings', ['public_slug'])


def downgrade() -> None:
    op.drop_constraint('uq_tailorings_public_slug', 'tailorings', type_='unique')
    op.drop_column('tailorings', 'public_slug')
    op.drop_column('tailorings', 'is_public')

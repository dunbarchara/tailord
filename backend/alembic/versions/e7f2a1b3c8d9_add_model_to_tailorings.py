"""add_model_to_tailorings

Revision ID: e7f2a1b3c8d9
Revises: c4e9f1d2b3a7
Create Date: 2026-03-07 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e7f2a1b3c8d9'
down_revision: Union[str, Sequence[str], None] = 'c4e9f1d2b3a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tailorings', sa.Column('model', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('tailorings', 'model')

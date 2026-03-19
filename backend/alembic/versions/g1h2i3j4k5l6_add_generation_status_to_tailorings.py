"""add_generation_status_to_tailorings

Revision ID: g1h2i3j4k5l6
Revises: a7b8c9d0e1f2
Create Date: 2026-03-19 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'g1h2i3j4k5l6'
down_revision: Union[str, Sequence[str], None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make generated_output nullable (pre-generation tailoring records have no output yet)
    op.alter_column('tailorings', 'generated_output', nullable=True)

    # Generation lifecycle tracking
    op.add_column('tailorings', sa.Column(
        'generation_status', sa.String(), nullable=False, server_default='ready',
    ))
    op.add_column('tailorings', sa.Column(
        'generation_stage', sa.String(), nullable=True,
    ))
    op.add_column('tailorings', sa.Column(
        'generation_error', sa.Text(), nullable=True,
    ))
    op.add_column('tailorings', sa.Column(
        'generation_started_at', sa.DateTime(timezone=True), nullable=True,
    ))


def downgrade() -> None:
    op.drop_column('tailorings', 'generation_started_at')
    op.drop_column('tailorings', 'generation_error')
    op.drop_column('tailorings', 'generation_stage')
    op.drop_column('tailorings', 'generation_status')
    op.alter_column('tailorings', 'generated_output', nullable=False)

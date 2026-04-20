"""add_gap_analysis_to_tailorings

Revision ID: e3f4a5b6c7d8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-18 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = 'e3f4a5b6c7d8'
down_revision = 'd1e2f3a4b5c6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('tailorings', sa.Column('gap_analysis', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('tailorings', 'gap_analysis')

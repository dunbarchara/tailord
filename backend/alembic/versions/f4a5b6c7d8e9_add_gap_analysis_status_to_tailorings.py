"""add_gap_analysis_status_to_tailorings

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-04-20 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = 'f4a5b6c7d8e9'
down_revision = 'e3f4a5b6c7d8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'tailorings',
        sa.Column('gap_analysis_status', sa.String(), nullable=False, server_default='pending'),
    )
    # Mark all existing ready tailorings as complete — gap analysis for these
    # has already run (or won't run again), so they should not be held in pending.
    op.execute(
        "UPDATE tailorings SET gap_analysis_status = 'complete' WHERE generation_status = 'ready'"
    )


def downgrade() -> None:
    op.drop_column('tailorings', 'gap_analysis_status')

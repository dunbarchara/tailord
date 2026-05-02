"""add experience_sources to job_chunks

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-05-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f7a8b9c0d1e2'
down_revision = 'e6f7a8b9c0d1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('job_chunks', sa.Column('experience_sources', sa.JSON(), nullable=True))
    # Backfill: wrap existing experience_source into a single-element list
    op.execute(
        "UPDATE job_chunks SET experience_sources = json_build_array(experience_source) "
        "WHERE experience_source IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_column('job_chunks', 'experience_sources')

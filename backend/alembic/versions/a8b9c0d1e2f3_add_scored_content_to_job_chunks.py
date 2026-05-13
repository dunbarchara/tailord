"""add scored_content to job_chunks

Revision ID: a8b9c0d1e2f3
Revises: 9f8e7d6c5b4a
Create Date: 2026-05-12 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a8b9c0d1e2f3'
down_revision = '9f8e7d6c5b4a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('job_chunks', sa.Column('scored_content', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('job_chunks', 'scored_content')

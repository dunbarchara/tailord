"""add is_requirement to job_chunks

Revision ID: 9f8e7d6c5b4a
Revises: a3b4c5d6e7f8
Create Date: 2026-05-12 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9f8e7d6c5b4a'
down_revision = 'a3b4c5d6e7f8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('job_chunks', sa.Column(
        'is_requirement', sa.Boolean(), nullable=False, server_default='true'
    ))


def downgrade() -> None:
    op.drop_column('job_chunks', 'is_requirement')

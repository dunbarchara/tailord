"""add should_render to job_chunks

Revision ID: d1e2f3a4b5c6
Revises: b5d8e2f1a9c3
Create Date: 2026-03-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, None] = '43311df5f40b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('job_chunks', sa.Column('should_render', sa.Boolean(), nullable=False, server_default='true'))


def downgrade() -> None:
    op.drop_column('job_chunks', 'should_render')

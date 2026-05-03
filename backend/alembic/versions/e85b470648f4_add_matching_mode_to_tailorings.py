"""add matching_mode to tailorings

Revision ID: e85b470648f4
Revises: f7a8b9c0d1e2
Create Date: 2026-05-02 16:02:26.092871

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e85b470648f4'
down_revision: Union[str, Sequence[str], None] = 'f7a8b9c0d1e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tailorings', sa.Column('matching_mode', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('tailorings', 'matching_mode')

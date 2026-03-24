"""scope_tailoring_slug_per_user

Revision ID: e1f2a3b4c5d6
Revises: d7e8f9a0b1c2
Create Date: 2026-03-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, None] = 'd7e8f9a0b1c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('uq_tailorings_public_slug', 'tailorings', type_='unique')
    op.create_unique_constraint(
        'uq_tailorings_user_public_slug', 'tailorings', ['user_id', 'public_slug']
    )


def downgrade() -> None:
    op.drop_constraint('uq_tailorings_user_public_slug', 'tailorings', type_='unique')
    op.create_unique_constraint('uq_tailorings_public_slug', 'tailorings', ['public_slug'])

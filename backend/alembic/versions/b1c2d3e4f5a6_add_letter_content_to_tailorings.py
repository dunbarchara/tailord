"""add letter_content to tailorings

Revision ID: b1c2d3e4f5a6
Revises: a8b9c0d1e2f3
Create Date: 2026-05-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'b1c2d3e4f5a6'
down_revision = 'a8b9c0d1e2f3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('tailorings', sa.Column('letter_content', postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column('tailorings', 'letter_content')

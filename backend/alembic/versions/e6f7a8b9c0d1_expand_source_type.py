"""expand source_type varchar(20) to varchar(30)

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-05-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e6f7a8b9c0d1'
down_revision = 'd5e6f7a8b9c0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "experience_chunks",
        "source_type",
        type_=sa.String(30),
        existing_type=sa.String(20),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "experience_chunks",
        "source_type",
        type_=sa.String(20),
        existing_type=sa.String(30),
        nullable=False,
    )

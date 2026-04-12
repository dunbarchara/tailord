"""make_uploaded_at_nullable

Revision ID: a1b2c3d4e5f6
Revises: c9e1f2a3b4d5
Create Date: 2026-04-12 00:00:00.000000

"""
from alembic import op

revision = 'a1b2c3d4e5f6'
down_revision = 'c9e1f2a3b4d5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('experiences', 'uploaded_at', nullable=True, server_default=None)


def downgrade() -> None:
    # Re-fill any NULLs before restoring the NOT NULL constraint
    op.execute("UPDATE experiences SET uploaded_at = NOW() WHERE uploaded_at IS NULL")
    op.alter_column('experiences', 'uploaded_at', nullable=False)

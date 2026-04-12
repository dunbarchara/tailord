"""profile_snapshot_and_debug_logs

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-12 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('tailorings', sa.Column('profile_snapshot', sa.Text(), nullable=True))

    op.create_table(
        'tailoring_debug_logs',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tailoring_id', sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('tailorings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_tailoring_debug_logs_tailoring_id', 'tailoring_debug_logs', ['tailoring_id'])


def downgrade() -> None:
    op.drop_index('ix_tailoring_debug_logs_tailoring_id', table_name='tailoring_debug_logs')
    op.drop_table('tailoring_debug_logs')
    op.drop_column('tailorings', 'profile_snapshot')

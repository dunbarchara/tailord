"""add_llm_rate_limiting_fields

Adds the infrastructure for LLM pipeline rate limiting and generation timing:
  - llm_trigger_log table: one row per LLM pipeline trigger (create, regen, experience
    process). Used for sliding-window rate limit queries. last_regenerated_at on the
    Tailoring row is insufficient because it only records the most recent regen per row,
    so spamming regen on one tailoring would appear as a single event.
  - tailorings.last_regenerated_at: UI display field ("last refreshed X min ago").
  - tailorings.generated_at: wall-clock generation completion time; pairs with
    generation_started_at to give total generation duration without log parsing.
  - experiences.last_process_requested_at: set at request time (not completion) so the
    5-minute cooldown check fires at the API boundary.

Revision ID: a9b8c7d6e5f4
Revises: a3b4c5d6e7f8
Create Date: 2026-04-06 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'a9b8c7d6e5f4'
down_revision: Union[str, None] = 'a3b4c5d6e7f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'llm_trigger_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'user_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # Rate limit query: WHERE user_id = ? AND event_type IN (...) AND created_at >= ?
    op.create_index(
        'ix_llm_trigger_log_user_event_created',
        'llm_trigger_log',
        ['user_id', 'event_type', 'created_at'],
    )

    op.add_column(
        'tailorings',
        sa.Column('last_regenerated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'tailorings',
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        'experiences',
        sa.Column('last_process_requested_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('experiences', 'last_process_requested_at')
    op.drop_column('tailorings', 'generated_at')
    op.drop_column('tailorings', 'last_regenerated_at')
    op.drop_index('ix_llm_trigger_log_user_event_created', table_name='llm_trigger_log')
    op.drop_table('llm_trigger_log')

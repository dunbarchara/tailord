"""rename_llm_trigger_log_to_usage_logs

Revision ID: e0f1a2b3c4d5
Revises: d0e1f2a3b4c5
Create Date: 2026-05-28 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e0f1a2b3c4d5"
down_revision: Union[str, None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename table (PK index is renamed automatically by PostgreSQL)
    op.rename_table("llm_trigger_log", "llm_usage_logs")

    # Add cost/model tracking columns (nullable — populated when LLM instrumentation ships)
    op.add_column("llm_usage_logs", sa.Column("model", sa.String(100), nullable=True))
    op.add_column("llm_usage_logs", sa.Column("input_tokens", sa.Integer(), nullable=True))
    op.add_column("llm_usage_logs", sa.Column("output_tokens", sa.Integer(), nullable=True))
    op.add_column("llm_usage_logs", sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True))

    # Rename event type: experience_process → resume_process
    op.execute(
        "UPDATE llm_usage_logs SET event_type = 'resume_process' WHERE event_type = 'experience_process'"
    )

    # Composite index covers both hourly burst queries and calendar-month quota queries
    op.create_index(
        "ix_llm_usage_logs_user_event_time",
        "llm_usage_logs",
        ["user_id", "event_type", "created_at"],
    )

    # Rename FK constraint to match new table name.
    # PostgreSQL keeps the old constraint name after rename_table — drop and recreate.
    # Note: auto-generated constraint name may differ in prod; verify with \d llm_trigger_log first.
    op.drop_constraint("llm_trigger_log_user_id_fkey", "llm_usage_logs", type_="foreignkey")
    op.create_foreign_key(
        "llm_usage_logs_user_id_fkey",
        "llm_usage_logs",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_index("ix_llm_usage_logs_user_event_time", table_name="llm_usage_logs")

    op.drop_constraint("llm_usage_logs_user_id_fkey", "llm_usage_logs", type_="foreignkey")
    op.create_foreign_key(
        "llm_trigger_log_user_id_fkey",
        "llm_usage_logs",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.execute(
        "UPDATE llm_usage_logs SET event_type = 'experience_process' WHERE event_type = 'resume_process'"
    )

    op.drop_column("llm_usage_logs", "cost_usd")
    op.drop_column("llm_usage_logs", "output_tokens")
    op.drop_column("llm_usage_logs", "input_tokens")
    op.drop_column("llm_usage_logs", "model")

    op.rename_table("llm_usage_logs", "llm_trigger_log")

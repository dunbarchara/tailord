"""add llm_call_logs

Revision ID: c3d4e5f6a7b8
Revises: b2d3e4f5a6b7
Create Date: 2026-05-29 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "llm_call_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("call_type", sa.String(20), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("prompt_name", sa.String(100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("cached_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_llm_call_logs_user_id", "llm_call_logs", ["user_id"])
    op.create_index("ix_llm_call_logs_created_at", "llm_call_logs", ["created_at"])
    op.create_index(
        "ix_llm_call_logs_prompt_model", "llm_call_logs", ["prompt_name", "model"]
    )


def downgrade() -> None:
    op.drop_index("ix_llm_call_logs_prompt_model", table_name="llm_call_logs")
    op.drop_index("ix_llm_call_logs_created_at", table_name="llm_call_logs")
    op.drop_index("ix_llm_call_logs_user_id", table_name="llm_call_logs")
    op.drop_table("llm_call_logs")

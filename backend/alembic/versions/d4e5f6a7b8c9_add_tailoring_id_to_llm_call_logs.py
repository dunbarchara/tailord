"""add tailoring_id to llm_call_logs

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-29 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "llm_call_logs",
        sa.Column("tailoring_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_llm_call_logs_tailoring_id",
        "llm_call_logs",
        "tailorings",
        ["tailoring_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_llm_call_logs_tailoring_id", "llm_call_logs", ["tailoring_id"])


def downgrade() -> None:
    op.drop_index("ix_llm_call_logs_tailoring_id", table_name="llm_call_logs")
    op.drop_constraint("fk_llm_call_logs_tailoring_id", "llm_call_logs", type_="foreignkey")
    op.drop_column("llm_call_logs", "tailoring_id")

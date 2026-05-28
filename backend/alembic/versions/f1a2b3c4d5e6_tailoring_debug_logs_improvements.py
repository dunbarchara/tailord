"""tailoring_debug_logs_improvements

Revision ID: f1a2b3c4d5e6
Revises: e0f1a2b3c4d5
Create Date: 2026-05-28 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e0f1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Promote payload to JSONB (requires explicit USING cast)
    op.execute(
        "ALTER TABLE tailoring_debug_logs ALTER COLUMN payload TYPE JSONB USING payload::JSONB"
    )

    # 2. Add nullable user_id FK (SET NULL on user delete)
    op.add_column(
        "tailoring_debug_logs",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "tailoring_debug_logs_user_id_fkey",
        "tailoring_debug_logs",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 3. Backfill user_id from parent tailoring (best-effort; null for orphaned rows)
    op.execute("""
        UPDATE tailoring_debug_logs tdl
        SET user_id = t.user_id
        FROM tailorings t
        WHERE tdl.tailoring_id = t.id
    """)

    # 4. Composite index for eval-mining queries (event_type filter + recency range)
    op.create_index(
        "ix_tailoring_debug_logs_event_time",
        "tailoring_debug_logs",
        ["event_type", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_tailoring_debug_logs_event_time", table_name="tailoring_debug_logs")

    op.drop_constraint(
        "tailoring_debug_logs_user_id_fkey", "tailoring_debug_logs", type_="foreignkey"
    )
    op.drop_column("tailoring_debug_logs", "user_id")

    op.execute(
        "ALTER TABLE tailoring_debug_logs ALTER COLUMN payload TYPE JSON USING payload::JSON"
    )

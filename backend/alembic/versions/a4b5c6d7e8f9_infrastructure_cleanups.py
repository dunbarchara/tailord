"""infrastructure_cleanups

Infrastructure FK and constraint cleanup:
  - Make jobs.user_id non-nullable (was nullable for legacy compatibility; confirmed 0 null rows)
  - Add ON DELETE CASCADE to tailorings.user_id FK (closes gap; app code already deletes
    tailorings before user rows, so no runtime impact)

Revision ID: a4b5c6d7e8f9
Revises: f3c4d5e6a7b8
Create Date: 2026-05-28 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a4b5c6d7e8f9"
down_revision: Union[str, None] = "f3c4d5e6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Pre-check: this migration assumes no NULL user_id rows in jobs.
    # If this fails, audit NULL rows before proceeding.
    op.alter_column("jobs", "user_id", nullable=False, existing_type=postgresql.UUID(as_uuid=True))

    # Add ON DELETE CASCADE to tailorings.user_id FK.
    # PostgreSQL requires dropping and recreating the constraint.
    op.drop_constraint("tailorings_user_id_fkey", "tailorings", type_="foreignkey")
    op.create_foreign_key(
        "tailorings_user_id_fkey",
        "tailorings",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # Revert CASCADE → RESTRICT (PostgreSQL default)
    op.drop_constraint("tailorings_user_id_fkey", "tailorings", type_="foreignkey")
    op.create_foreign_key(
        "tailorings_user_id_fkey",
        "tailorings",
        "users",
        ["user_id"],
        ["id"],
    )

    op.alter_column("jobs", "user_id", nullable=True, existing_type=postgresql.UUID(as_uuid=True))

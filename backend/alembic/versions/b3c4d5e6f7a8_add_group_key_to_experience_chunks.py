"""add_group_key_to_experience_chunks

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-04-26 00:00:00.000000

group_key enables rendering hierarchy from flat chunk rows:
  work_experience → "ACME Corp | Software Engineer"
  project         → "MyApp"
  education       → "BSc Computer Science | MIT"
  github chunks   → repo name
  skill / other   → null
"""

import sqlalchemy as sa
from alembic import op

revision = "b3c4d5e6f7a8"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "experience_chunks",
        sa.Column("group_key", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("experience_chunks", "group_key")

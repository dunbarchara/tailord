"""experience_groups_enrichment

Enriches the experience_groups table:
  - Add position integer (drag-and-drop ordering foundation)
  - Add provenance_url, provenance_label (view-source link)
  - Add tags JSONB (group-level signal propagation)
  - Add description text (custom group type context)
  - Change type_meta from JSON → JSONB (enables operator queries)

Revision ID: f3c4d5e6a7b8
Revises: e2b3c4d5f6a7
Create Date: 2026-05-28 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f3c4d5e6a7b8"
down_revision: Union[str, None] = "e2b3c4d5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 3a — Add position, backfill from created_at order within each user
    op.add_column(
        "experience_groups",
        sa.Column("position", sa.Integer(), nullable=True),
    )
    op.execute(
        """
        UPDATE experience_groups eg
        SET position = ranked.rn
        FROM (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at) - 1 AS rn
            FROM experience_groups
        ) ranked
        WHERE eg.id = ranked.id
        """
    )

    # 3b — Add provenance link fields
    op.add_column(
        "experience_groups",
        sa.Column("provenance_url", sa.String(500), nullable=True),
    )
    op.add_column(
        "experience_groups",
        sa.Column("provenance_label", sa.String(255), nullable=True),
    )

    # 3c — Add tags JSONB
    op.add_column(
        "experience_groups",
        sa.Column("tags", postgresql.JSONB(), nullable=True),
    )

    # 3d — Add description text
    op.add_column(
        "experience_groups",
        sa.Column("description", sa.Text(), nullable=True),
    )

    # 3e — type_meta JSON → JSONB (lossless cast)
    op.execute(
        """
        ALTER TABLE experience_groups
        ALTER COLUMN type_meta TYPE jsonb USING type_meta::text::jsonb
        """
    )


def downgrade() -> None:
    # Revert type_meta JSONB → JSON
    op.execute(
        """
        ALTER TABLE experience_groups
        ALTER COLUMN type_meta TYPE json USING type_meta::text::json
        """
    )
    op.drop_column("experience_groups", "description")
    op.drop_column("experience_groups", "tags")
    op.drop_column("experience_groups", "provenance_label")
    op.drop_column("experience_groups", "provenance_url")
    op.drop_column("experience_groups", "position")

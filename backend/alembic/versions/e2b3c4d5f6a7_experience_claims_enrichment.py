"""experience_claims_enrichment

Enriches the experience_claims table:
  - Rename technologies → keywords (industry-neutral term)
  - Add provenance_metadata JSONB (consolidates chunk_metadata + provenance_url/label)
  - Add original_content text (enables revert on user-edited claims)
  - Add merged_from JSONB (dedup pipeline foundation)
  - Drop chunk_metadata, provenance_url, provenance_label
  - Expose status field (already present; no DDL change — docs-only)

Revision ID: e2b3c4d5f6a7
Revises: d1a2b3c4e5f6
Create Date: 2026-05-28 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e2b3c4d5f6a7"
down_revision: Union[str, None] = "d1a2b3c4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 2a — Rename technologies → keywords
    op.alter_column("experience_claims", "technologies", new_column_name="keywords")

    # 2b — Add merged_from JSONB
    op.add_column(
        "experience_claims",
        sa.Column("merged_from", postgresql.JSONB(), nullable=True),
    )

    # 2c — Add original_content text
    op.add_column(
        "experience_claims",
        sa.Column("original_content", sa.Text(), nullable=True),
    )

    # 2d — Collapse provenance fields into provenance_metadata
    op.add_column(
        "experience_claims",
        sa.Column("provenance_metadata", postgresql.JSONB(), nullable=True),
    )
    # Backfill from existing chunk_metadata
    op.execute(
        """
        UPDATE experience_claims
        SET provenance_metadata = chunk_metadata::jsonb
        WHERE chunk_metadata IS NOT NULL
        """
    )
    op.drop_column("experience_claims", "chunk_metadata")
    op.drop_column("experience_claims", "provenance_url")
    op.drop_column("experience_claims", "provenance_label")


def downgrade() -> None:
    # Restore chunk_metadata from provenance_metadata
    op.add_column(
        "experience_claims",
        sa.Column("chunk_metadata", sa.JSON(), nullable=True),
    )
    op.execute(
        "UPDATE experience_claims SET chunk_metadata = provenance_metadata WHERE provenance_metadata IS NOT NULL"
    )
    op.add_column(
        "experience_claims",
        sa.Column("provenance_url", sa.String(500), nullable=True),
    )
    op.add_column(
        "experience_claims",
        sa.Column("provenance_label", sa.String(255), nullable=True),
    )
    op.drop_column("experience_claims", "provenance_metadata")
    op.drop_column("experience_claims", "original_content")
    op.drop_column("experience_claims", "merged_from")
    op.alter_column("experience_claims", "keywords", new_column_name="technologies")

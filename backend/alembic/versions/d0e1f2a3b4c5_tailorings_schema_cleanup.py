"""tailorings_schema_cleanup

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-05-28 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new JSONB columns
    op.add_column(
        "tailorings",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )
    op.add_column(
        "tailorings",
        sa.Column("generation_telemetry", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "tailorings",
        sa.Column("notion_export", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "tailorings",
        sa.Column("models", postgresql.JSONB(), nullable=True),
    )

    # Data migrations: populate new JSONB columns from old flat columns
    op.execute(
        """
        UPDATE tailorings SET generation_telemetry = jsonb_strip_nulls(jsonb_build_object(
            'duration_ms', generation_duration_ms,
            'matching_mode', matching_mode,
            'batch_count', chunk_batch_count,
            'batch_errors', chunk_error_count
        )) WHERE generation_duration_ms IS NOT NULL
            OR matching_mode IS NOT NULL
            OR chunk_batch_count IS NOT NULL
            OR chunk_error_count IS NOT NULL
        """
    )

    op.execute(
        """
        UPDATE tailorings SET notion_export = jsonb_strip_nulls(jsonb_build_object(
            'container_page_id', notion_container_page_id,
            'page_id', notion_page_id,
            'page_url', notion_page_url,
            'posting_page_id', notion_posting_page_id,
            'posting_page_url', notion_posting_page_url
        )) WHERE notion_page_id IS NOT NULL OR notion_posting_page_id IS NOT NULL
        """
    )

    op.execute(
        """
        UPDATE tailorings SET models = jsonb_build_object('letter', model)
        WHERE model IS NOT NULL
        """
    )

    # Alter letter_content JSON → JSONB
    op.alter_column(
        "tailorings",
        "letter_content",
        type_=postgresql.JSONB(),
        postgresql_using="letter_content::jsonb",
        existing_nullable=True,
    )

    # Drop old flat columns
    op.drop_column("tailorings", "enrichment_status")
    op.drop_column("tailorings", "gap_analysis_status")
    op.drop_column("tailorings", "generation_duration_ms")
    op.drop_column("tailorings", "chunk_batch_count")
    op.drop_column("tailorings", "chunk_error_count")
    op.drop_column("tailorings", "matching_mode")
    op.drop_column("tailorings", "model")
    op.drop_column("tailorings", "notion_container_page_id")
    op.drop_column("tailorings", "notion_page_id")
    op.drop_column("tailorings", "notion_page_url")
    op.drop_column("tailorings", "notion_posting_page_id")
    op.drop_column("tailorings", "notion_posting_page_url")


def downgrade() -> None:
    # Re-add dropped columns (data not restored from JSONB)
    op.add_column(
        "tailorings", sa.Column("notion_posting_page_url", sa.String(), nullable=True)
    )
    op.add_column(
        "tailorings", sa.Column("notion_posting_page_id", sa.String(), nullable=True)
    )
    op.add_column(
        "tailorings", sa.Column("notion_page_url", sa.String(), nullable=True)
    )
    op.add_column(
        "tailorings", sa.Column("notion_page_id", sa.String(), nullable=True)
    )
    op.add_column(
        "tailorings",
        sa.Column("notion_container_page_id", sa.String(), nullable=True),
    )
    op.add_column("tailorings", sa.Column("model", sa.String(), nullable=True))
    op.add_column("tailorings", sa.Column("matching_mode", sa.String(), nullable=True))
    op.add_column(
        "tailorings", sa.Column("chunk_error_count", sa.Integer(), nullable=True)
    )
    op.add_column(
        "tailorings", sa.Column("chunk_batch_count", sa.Integer(), nullable=True)
    )
    op.add_column(
        "tailorings",
        sa.Column("generation_duration_ms", sa.Integer(), nullable=True),
    )
    op.add_column(
        "tailorings",
        sa.Column(
            "gap_analysis_status",
            sa.String(),
            server_default="pending",
            nullable=False,
        ),
    )
    op.add_column(
        "tailorings",
        sa.Column(
            "enrichment_status",
            sa.String(),
            server_default="pending",
            nullable=False,
        ),
    )

    # Revert letter_content JSONB → JSON (JSONB is a superset, no data loss)
    op.alter_column(
        "tailorings",
        "letter_content",
        type_=sa.JSON(),
        existing_nullable=True,
    )

    # Drop new columns
    op.drop_column("tailorings", "models")
    op.drop_column("tailorings", "notion_export")
    op.drop_column("tailorings", "generation_telemetry")
    op.drop_column("tailorings", "updated_at")

"""rename_resumes_to_experiences_add_github_fields

Revision ID: 967e51ce9415
Revises:
Create Date: 2026-02-28 10:41:50.026472

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '967e51ce9415'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename resumes → experiences (preserves all data and existing constraints)
    op.rename_table("resumes", "experiences")

    # Add GitHub fields
    op.add_column("experiences", sa.Column("github_username", sa.String(), nullable=True))
    op.add_column("experiences", sa.Column("github_repos", sa.JSON(), nullable=True))

    # Make s3_key and filename nullable (needed for GitHub-only experience records)
    op.alter_column("experiences", "s3_key", existing_type=sa.String(), nullable=True)
    op.alter_column("experiences", "filename", existing_type=sa.String(), nullable=True)

    # Drop legacy profiles table (no longer in the model)
    op.drop_table("profiles")


def downgrade() -> None:
    # Recreate legacy profiles table
    op.create_table(
        "profiles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("raw_profile", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Reverse column changes
    op.alter_column("experiences", "filename", existing_type=sa.String(), nullable=False)
    op.alter_column("experiences", "s3_key", existing_type=sa.String(), nullable=False)
    op.drop_column("experiences", "github_repos")
    op.drop_column("experiences", "github_username")

    # Rename back
    op.rename_table("experiences", "resumes")

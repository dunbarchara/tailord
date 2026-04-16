"""add_github_repo_details_to_experiences

Revision ID: d1e2f3a4b5c6
Revises: c9e1f2a3b4d5
Create Date: 2026-04-15 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "experiences",
        sa.Column("github_repo_details", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("experiences", "github_repo_details")

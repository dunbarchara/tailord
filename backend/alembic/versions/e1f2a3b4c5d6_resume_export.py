"""resume_export: add resume_draft JSONB to tailorings

Revision ID: e1f2a3b4c5d6
Revises: f9c5c4e0d3fd
Create Date: 2026-05-28 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tailorings",
        sa.Column("resume_draft", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tailorings", "resume_draft")

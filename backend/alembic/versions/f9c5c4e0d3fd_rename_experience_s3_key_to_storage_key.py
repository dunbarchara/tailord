"""rename_experience_s3_key_to_storage_key

Revision ID: f9c5c4e0d3fd
Revises: b1c2d3e4f5a6
Create Date: 2026-05-14 20:03:09.990185

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f9c5c4e0d3fd"
down_revision: Union[str, Sequence[str], None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("experiences", "s3_key", new_column_name="storage_key")


def downgrade() -> None:
    op.alter_column("experiences", "storage_key", new_column_name="s3_key")

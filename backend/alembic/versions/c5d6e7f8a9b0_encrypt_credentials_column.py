"""encrypt_credentials_column

Changes user_integrations.credentials from JSONB to Text to support
transparent Fernet encryption via the EncryptedJSON TypeDecorator.

PostgreSQL casts jsonb → text, preserving existing plaintext JSON values.
The EncryptedJSON TypeDecorator reads legacy plaintext rows transparently
via its plaintext fallback until they are overwritten with encrypted values.

Revision ID: c5d6e7f8a9b0
Revises: b4d5e6f7a8b9
Create Date: 2026-05-28 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, None] = "b4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Cast JSONB → Text, preserving existing plaintext JSON values verbatim.
    # EncryptedJSON will read them back via its plaintext fallback.
    op.alter_column(
        "user_integrations",
        "credentials",
        type_=sa.Text(),
        existing_type=postgresql.JSONB(),
        postgresql_using="credentials::text",
    )


def downgrade() -> None:
    # Cast Text → JSONB. Works for legacy plaintext rows only.
    # Encrypted rows (Fernet tokens) are NOT valid JSON — downgrade will fail
    # if any encrypted rows exist. Remove encrypted rows before downgrading.
    op.alter_column(
        "user_integrations",
        "credentials",
        type_=postgresql.JSONB(),
        existing_type=sa.Text(),
        postgresql_using="credentials::jsonb",
    )

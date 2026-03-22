"""add_username_slug_and_avatar_to_users

Revision ID: c913ef0df21a
Revises: bcfb04fef2f6
Create Date: 2026-03-20 14:21:48.240404

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c913ef0df21a'
down_revision: Union[str, Sequence[str], None] = 'bcfb04fef2f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('username_slug', sa.String(), nullable=True))
    op.add_column('users', sa.Column('avatar_url', sa.String(), nullable=True))
    op.create_unique_constraint('uq_users_username_slug', 'users', ['username_slug'])
    op.create_index('ix_users_username_slug', 'users', ['username_slug'])


def downgrade() -> None:
    op.drop_index('ix_users_username_slug', table_name='users')
    op.drop_constraint('uq_users_username_slug', 'users', type_='unique')
    op.drop_column('users', 'avatar_url')
    op.drop_column('users', 'username_slug')

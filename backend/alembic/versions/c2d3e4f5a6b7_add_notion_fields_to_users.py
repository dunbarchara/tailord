"""add_notion_fields_to_users

Revision ID: c2d3e4f5a6b7
Revises: b8c9d0e1f2a3
Create Date: 2026-03-14 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c2d3e4f5a6b7'
down_revision: Union[str, Sequence[str], None] = 'b8c9d0e1f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('notion_access_token', sa.String(), nullable=True))
    op.add_column('users', sa.Column('notion_bot_id', sa.String(), nullable=True))
    op.add_column('users', sa.Column('notion_workspace_id', sa.String(), nullable=True))
    op.add_column('users', sa.Column('notion_workspace_name', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'notion_workspace_name')
    op.drop_column('users', 'notion_workspace_id')
    op.drop_column('users', 'notion_bot_id')
    op.drop_column('users', 'notion_access_token')

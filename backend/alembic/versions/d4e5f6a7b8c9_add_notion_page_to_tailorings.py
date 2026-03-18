"""add_notion_page_to_tailorings

Revision ID: d4e5f6a7b8c9
Revises: c2d3e4f5a6b7
Create Date: 2026-03-18 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tailorings', sa.Column('notion_page_id', sa.String(), nullable=True))
    op.add_column('tailorings', sa.Column('notion_page_url', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('tailorings', 'notion_page_url')
    op.drop_column('tailorings', 'notion_page_id')

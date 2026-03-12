"""add_job_chunks_and_enrichment_status

Revision ID: b5d8e2f1a9c3
Revises: a1b2c3d4e5f6
Create Date: 2026-03-11 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'b5d8e2f1a9c3'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'tailorings',
        sa.Column('enrichment_status', sa.String(), nullable=False, server_default='pending'),
    )
    op.create_table(
        'job_chunks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('chunk_type', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('section', sa.String(255), nullable=True),
        sa.Column('match_score', sa.Integer(), nullable=True),
        sa.Column('match_rationale', sa.Text(), nullable=True),
        sa.Column('experience_source', sa.String(50), nullable=True),
        sa.Column('enriched_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_job_chunks_job_id', 'job_chunks', ['job_id'])


def downgrade() -> None:
    op.drop_index('ix_job_chunks_job_id', table_name='job_chunks')
    op.drop_table('job_chunks')
    op.drop_column('tailorings', 'enrichment_status')

"""activate_experience_groups: add parent_group_id, backfill ExperienceGroup rows from claims

Revision ID: a0b1c2d3e4f5
Revises: e1f2a3b4c5d6
Create Date: 2026-05-28 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a0b1c2d3e4f5"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add self-referential parent_group_id FK to experience_groups
    op.add_column(
        "experience_groups",
        sa.Column(
            "parent_group_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experience_groups.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_experience_groups_parent_id",
        "experience_groups",
        "experience_groups",
        ["parent_group_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_experience_groups_parent_group_id",
        "experience_groups",
        ["parent_group_id"],
    )

    # Backfill ExperienceGroup rows from existing resume claims grouped by group_key
    op.execute("""
        INSERT INTO experience_groups (id, user_id, group_type, name, source_type, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            user_id,
            CASE
                WHEN claim_type = 'work_experience' THEN 'role'
                WHEN claim_type = 'project' THEN 'project'
                WHEN claim_type = 'education' THEN 'education'
                ELSE 'custom'
            END,
            group_key,
            source_type,
            MIN(created_at),
            MAX(updated_at)
        FROM experience_claims
        WHERE group_key IS NOT NULL
          AND source_type = 'resume'
          AND claim_type IN ('work_experience', 'project', 'education')
        GROUP BY user_id, group_key, claim_type, source_type
        ON CONFLICT DO NOTHING
    """)

    # Backfill ExperienceGroup rows from GitHub repo claims (grouped by source_ref)
    op.execute("""
        INSERT INTO experience_groups (id, user_id, group_type, name, source_type, source_ref, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            user_id,
            'repository',
            source_ref,
            'github',
            source_ref,
            MIN(created_at),
            MAX(updated_at)
        FROM experience_claims
        WHERE source_type = 'github'
          AND source_ref IS NOT NULL
        GROUP BY user_id, source_ref
        ON CONFLICT DO NOTHING
    """)

    # Backfill group_id on existing resume claims from the new groups
    op.execute("""
        UPDATE experience_claims ec
        SET group_id = eg.id
        FROM (
            SELECT DISTINCT ON (user_id, source_type, name) id, user_id, source_type, name
            FROM experience_groups
            WHERE source_type = 'resume'
        ) eg
        WHERE ec.user_id = eg.user_id
          AND ec.source_type = 'resume'
          AND ec.group_key = eg.name
          AND ec.claim_type IN ('work_experience', 'project', 'education')
          AND ec.group_id IS NULL
    """)

    # Backfill group_id on existing github claims from the new groups
    op.execute("""
        UPDATE experience_claims ec
        SET group_id = eg.id
        FROM experience_groups eg
        WHERE ec.user_id = eg.user_id
          AND ec.source_type = 'github'
          AND ec.source_ref = eg.source_ref
          AND eg.source_type = 'github'
          AND ec.group_id IS NULL
    """)


def downgrade() -> None:
    op.execute("UPDATE experience_claims SET group_id = NULL")
    op.drop_constraint(
        "fk_experience_groups_parent_id", "experience_groups", type_="foreignkey"
    )
    op.drop_index("ix_experience_groups_parent_group_id", table_name="experience_groups")
    op.drop_column("experience_groups", "parent_group_id")
    op.execute("DELETE FROM experience_groups")

"""Cover listed world indicators for the cold country directory query.

Revision ID: 20260924_countries_idx
Revises: 20260920_subnational
"""

from alembic import op

revision = "20260924_countries_idx"
down_revision = "20260920_subnational"
branch_labels = None
depends_on = None

_INDEX_NAME = "ix_world_indicators_listed_signal"


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            f"""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS {_INDEX_NAME}
            ON world_indicators (country_id) INCLUDE (id, code, name_ru)
            WHERE is_listed
            """
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX_NAME}")

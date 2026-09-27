"""Index nonzero world points for cold country catalogue signal checks.

Revision ID: 20260927_world_nonzero_idx
Revises: 20260924_oauth_locale
"""

from alembic import op
import sqlalchemy as sa

revision = "20260927_world_nonzero_idx"
down_revision = "20260924_oauth_locale"
branch_labels = None
depends_on = None

_INDEX_NAME = "ix_world_data_points_nonzero_indicator"


def _index_flags() -> tuple[bool, bool] | None:
    """An interrupted concurrent build leaves a same-name INVALID index.

    ``IF NOT EXISTS`` alone would silently keep that index and stamp the
    migration, while PostgreSQL cannot use it for catalogue queries.
    """
    row = op.get_bind().execute(
        sa.text(
            """
            SELECT indisvalid, indisready
            FROM pg_catalog.pg_index
            WHERE indexrelid = to_regclass(:index_name)
            """
        ),
        {"index_name": _INDEX_NAME},
    ).one_or_none()
    return (bool(row[0]), bool(row[1])) if row is not None else None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        flags = _index_flags()
        if flags is not None and flags != (True, True):
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX_NAME}")
        op.execute(
            f"""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS {_INDEX_NAME}
            ON world_data_points (indicator_id)
            WHERE value <> 0
            """
        )
        if _index_flags() != (True, True):
            raise RuntimeError(
                f"{_INDEX_NAME} is missing or invalid after CREATE INDEX CONCURRENTLY"
            )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX_NAME}")

"""Cover narrow logical-session history without locking event ingestion.

Revision ID: 20261009c_session_perf
Revises: 20261009b_analytics_signups
"""
from alembic import op
import sqlalchemy as sa

revision = "20261009c_session_perf"
down_revision = "20261009b_analytics_signups"
branch_labels = None
depends_on = None
_INDEX_NAME = "ix_behavior_logical_session_cover"
_PORTRAIT_INDEX = "ix_behavior_sessions_visitor_started"


def _index_flags(name=_INDEX_NAME):
    row = op.get_bind().execute(sa.text(
        "SELECT indisvalid, indisready FROM pg_catalog.pg_index WHERE indexrelid = to_regclass(:name)"
    ), {"name": name}).one_or_none()
    return (bool(row[0]), bool(row[1])) if row is not None else None


def upgrade():
    with op.get_context().autocommit_block():
        if _index_flags() not in (None, (True, True)):
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX_NAME}")
        op.execute(f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {_INDEX_NAME} ON behavior_events "
                   "((coalesce(nullif(visitor_id_hash, ''), nullif(session_id_hash, ''))), occurred_at, id) "
                   "INCLUDE (event_type, session_id_hash, visitor_id_hash) "
                   "WHERE event_type IN ('pageview', 'dwell', 'click', 'move')")
        if _index_flags() != (True, True):
            raise RuntimeError(f"{_INDEX_NAME} is not valid after concurrent build")
        # A newly built expression index has no key distribution statistics.
        # Without this the planner assumes thousands of rows per visitor and
        # repeats bitmap heap scans. Refresh before the first scheduled run.
        op.execute("ANALYZE behavior_events")
        if _index_flags(_PORTRAIT_INDEX) not in (None, (True, True)):
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_PORTRAIT_INDEX}")
        op.execute(f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {_PORTRAIT_INDEX} "
                   "ON behavior_sessions (visitor_id_hash, started_at DESC, session_id_hash)")
        if _index_flags(_PORTRAIT_INDEX) != (True, True):
            raise RuntimeError(f"{_PORTRAIT_INDEX} is not valid after concurrent build")


def downgrade():
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX_NAME}")
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_PORTRAIT_INDEX}")

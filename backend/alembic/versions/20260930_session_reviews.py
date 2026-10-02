"""Own masked recordings and revisioned session evidence.

Revision ID: 20260930_session_reviews
Revises: 20260927_world_nonzero_idx
"""
from alembic import op
import sqlalchemy as sa

revision = "20260930_session_reviews"
down_revision = "20260927_world_nonzero_idx"
branch_labels = None
depends_on = None

_STREAM_INDEXES = (
    ("ix_behavior_session_event", "behavior_events", "session_id_hash, id"),
    ("ix_behavior_occurred", "behavior_events", "occurred_at"),
    ("ix_frontend_session_event", "frontend_events", "session_id_hash, id"),
    ("ix_frontend_occurred", "frontend_events", "occurred_at"),
)

def upgrade():
    # Existing event streams may be large. Interrupted concurrent builds are
    # repaired; IF NOT EXISTS must not silently keep an invalid index.
    with op.get_context().autocommit_block():
        for name, table, columns in _STREAM_INDEXES:
            valid = op.get_bind().execute(sa.text(
                "SELECT indisvalid AND indisready FROM pg_catalog.pg_index WHERE indexrelid = to_regclass(:name)"
            ), {"name": name}).scalar()
            if valid is False:
                op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
            op.execute(f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {name} ON {table} ({columns})")
            valid = op.get_bind().execute(sa.text(
                "SELECT indisvalid AND indisready FROM pg_catalog.pg_index WHERE indexrelid = to_regclass(:name)"
            ), {"name": name}).scalar()
            if valid is not True:
                raise RuntimeError(f"Invalid session index: {name}")
    op.create_table("session_analysis_reports",
        sa.Column("session_id_hash", sa.String(80), primary_key=True),
        sa.Column("schema_version", sa.String(20), nullable=False, server_default="1"),
        sa.Column("source_fingerprint", sa.String(64), nullable=False, server_default=""),
        sa.Column("latest_event_id", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("pending_event_id", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("report_json", sa.JSON()), sa.Column("visual_json", sa.JSON()),
        sa.Column("pending_at", sa.DateTime()), sa.Column("due_at", sa.DateTime()),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.String(300)), sa.Column("generated_at", sa.DateTime()))
    op.create_index("ix_session_analysis_due", "session_analysis_reports", ["status", "due_at"])
    op.create_table("session_replay_chunks",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("session_id_hash", sa.String(80), nullable=False),
        sa.Column("visitor_id_hash", sa.String(80), nullable=False),
        sa.Column("recording_id", sa.String(40), nullable=False),
        sa.Column("page", sa.String(500), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("part", sa.Integer(), nullable=False),
        sa.Column("parts", sa.Integer(), nullable=False),
        sa.Column("payload_gzip", sa.LargeBinary(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("raw_bytes", sa.Integer(), nullable=False),
        sa.Column("ended", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("recording_id", "sequence", "part", name="uq_session_replay_part"))
    for name, columns in (
        ("ix_session_replay_session", ["session_id_hash", "created_at"]),
        ("ix_session_replay_retention", ["created_at"]),
        ("ix_session_replay_visitor_hour", ["visitor_id_hash", "created_at"]),
        ("ix_session_replay_session_order", ["session_id_hash", "recording_id", "sequence", "part"]),
    ):
        op.create_index(name, "session_replay_chunks", columns)

def downgrade():
    with op.get_context().autocommit_block():
        for name, _table, _columns in reversed(_STREAM_INDEXES):
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
    op.drop_table("session_replay_chunks")
    op.drop_table("session_analysis_reports")

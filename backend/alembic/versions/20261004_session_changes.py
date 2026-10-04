"""Durable change journal of server_sessions for ClickHouse replication (F05b).

Revision ID: 20261004_session_changes
Revises: 20260930_session_reviews
"""
from alembic import op
import sqlalchemy as sa

revision = "20261004_session_changes"
down_revision = "20260930_session_reviews"
branch_labels = None
depends_on = None


def upgrade():
    # Новая пустая таблица: быстрый DDL без блокировок существующих данных.
    op.create_table(
        "server_session_changes",
        sa.Column("visitor_id_hash", sa.String(80), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("changed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("visitor_id_hash", "started_at"),
    )
    op.create_index("ix_server_session_changes_changed", "server_session_changes", ["changed_at"])


def downgrade():
    op.drop_index("ix_server_session_changes_changed", table_name="server_session_changes")
    op.drop_table("server_session_changes")

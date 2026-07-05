"""behavior_sessions — портрет сессии собственного счётчика (аудитория).

Revision ID: 20260705_behavior_sessions
Revises: 20260704_telegram_outbox
Create Date: 2026-07-05
"""
from alembic import op
import sqlalchemy as sa

revision = "20260705_behavior_sessions"
down_revision = "20260704_tg_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "behavior_sessions",
        sa.Column("session_id_hash", sa.String(length=80), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("authed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("entry_page", sa.String(length=500), nullable=True),
        sa.Column("referrer", sa.String(length=1000), nullable=True),
        sa.Column("referrer_host", sa.String(length=200), nullable=True),
        sa.Column("utm_source", sa.String(length=120), nullable=True),
        sa.Column("utm_medium", sa.String(length=120), nullable=True),
        sa.Column("utm_campaign", sa.String(length=200), nullable=True),
        sa.Column("ua_raw", sa.String(length=500), nullable=True),
        sa.Column("browser", sa.String(length=40), nullable=True),
        sa.Column("browser_version", sa.String(length=20), nullable=True),
        sa.Column("os", sa.String(length=30), nullable=True),
        sa.Column("os_version", sa.String(length=30), nullable=True),
        sa.Column("device_type", sa.String(length=12), nullable=True),
        sa.Column("screen_w", sa.Integer(), nullable=True),
        sa.Column("screen_h", sa.Integer(), nullable=True),
        sa.Column("viewport_w", sa.Integer(), nullable=True),
        sa.Column("viewport_h", sa.Integer(), nullable=True),
        sa.Column("dpr", sa.Numeric(4, 2), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("timezone", sa.String(length=60), nullable=True),
        sa.Column("touch", sa.Boolean(), nullable=True),
    )
    op.create_index("ix_behavior_sessions_started", "behavior_sessions", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_behavior_sessions_started", table_name="behavior_sessions")
    op.drop_table("behavior_sessions")

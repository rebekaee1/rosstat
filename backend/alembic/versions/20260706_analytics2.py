"""Аналитика 2.0: visitor_id, гео, каналы, identity_links, словарь целей,
серверные сессии, rollup-таблицы, каркас расходов Директа.

Всё аддитивно; ни одна существующая колонка не меняется.

Revision ID: 20260706_analytics2
Revises: 20260705_behavior_sessions
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa

revision = "20260706_analytics2"
down_revision = "20260705_behavior_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- visitor_id в потоках событий ---
    op.add_column("frontend_events", sa.Column("visitor_id_hash", sa.String(length=80), nullable=True))
    op.create_index("ix_frontend_events_visitor_id_hash", "frontend_events", ["visitor_id_hash"])
    op.add_column("behavior_events", sa.Column("visitor_id_hash", sa.String(length=80), nullable=True))
    op.create_index("ix_behavior_events_visitor_id_hash", "behavior_events", ["visitor_id_hash"])

    # --- расширение портрета сессии ---
    for col in (
        sa.Column("visitor_id_hash", sa.String(length=80), nullable=True),
        sa.Column("ym_client_id", sa.String(length=80), nullable=True),
        sa.Column("channel", sa.String(length=20), nullable=True),
        sa.Column("utm_term", sa.String(length=200), nullable=True),
        sa.Column("utm_content", sa.String(length=200), nullable=True),
        sa.Column("yclid", sa.String(length=64), nullable=True),
        sa.Column("country", sa.String(length=60), nullable=True),
        sa.Column("geo_region", sa.String(length=120), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("conn_type", sa.String(length=16), nullable=True),
        sa.Column("downlink", sa.Numeric(6, 2), nullable=True),
        sa.Column("device_memory", sa.Numeric(5, 1), nullable=True),
        sa.Column("cpu_cores", sa.Integer(), nullable=True),
        sa.Column("color_scheme", sa.String(length=10), nullable=True),
        sa.Column("orientation", sa.String(length=12), nullable=True),
        sa.Column("is_webdriver", sa.Boolean(), nullable=True),
    ):
        op.add_column("behavior_sessions", col)
    op.create_index("ix_behavior_sessions_visitor_id_hash", "behavior_sessions", ["visitor_id_hash"])

    # --- граф идентичности ---
    op.create_table(
        "identity_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("visitor_id_hash", sa.String(length=80), nullable=False),
        sa.Column("first_seen", sa.DateTime(), nullable=False),
        sa.Column("last_seen", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "visitor_id_hash", name="uq_identity_user_visitor"),
    )
    op.create_index("ix_identity_links_user_id", "identity_links", ["user_id"])
    op.create_index("ix_identity_visitor", "identity_links", ["visitor_id_hash"])

    # --- словарь целей Метрики ---
    op.create_table(
        "metrika_goals",
        sa.Column("goal_id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("name", sa.String(length=300), nullable=True),
        sa.Column("event_name", sa.String(length=120), nullable=True),
        sa.Column("tier", sa.String(length=20), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_metrika_goals_event_name", "metrika_goals", ["event_name"])

    # --- серверные сессии (вычислительный фундамент) ---
    op.create_table(
        "server_sessions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("visitor_id_hash", sa.String(length=80), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=False),
        sa.Column("duration_ms", sa.BigInteger(), nullable=True),
        sa.Column("active_ms", sa.BigInteger(), nullable=True),
        sa.Column("pageviews", sa.Integer(), nullable=True),
        sa.Column("clicks", sa.Integer(), nullable=True),
        sa.Column("max_scroll_pct", sa.Integer(), nullable=True),
        sa.Column("entry_page", sa.String(length=500), nullable=True),
        sa.Column("exit_page", sa.String(length=500), nullable=True),
        sa.Column("channel", sa.String(length=20), nullable=True),
        sa.Column("device", sa.String(length=20), nullable=True),
        sa.Column("is_new_visitor", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_engaged", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("micro_goals", sa.Integer(), nullable=True),
        sa.Column("macro_goals", sa.Integer(), nullable=True),
        sa.Column("is_bot", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("computed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("visitor_id_hash", "started_at", name="uq_server_session_visitor_start"),
    )
    op.create_index("ix_server_session_day", "server_sessions", ["day"])

    # --- дневные rollup'ы ---
    op.create_table(
        "daily_traffic",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("channel", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("device", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("is_new", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("visits", sa.Integer(), nullable=True),
        sa.Column("visitors", sa.Integer(), nullable=True),
        sa.Column("pageviews", sa.Integer(), nullable=True),
        sa.Column("goal_visits", sa.Integer(), nullable=True),
        sa.Column("total_duration_sec", sa.BigInteger(), nullable=True),
        sa.Column("bounces", sa.Integer(), nullable=True),
        sa.Column("computed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("day", "channel", "device", "is_new", name="uq_daily_traffic_key"),
    )
    op.create_index("ix_daily_traffic_day", "daily_traffic", ["day"])

    op.create_table(
        "daily_goals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("event_name", sa.String(length=120), nullable=False),
        sa.Column("tier", sa.String(length=20), nullable=False, server_default="engagement"),
        sa.Column("count", sa.Integer(), nullable=True),
        sa.Column("sessions", sa.Integer(), nullable=True),
        sa.Column("authed_count", sa.Integer(), nullable=True),
        sa.Column("computed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("day", "event_name", name="uq_daily_goal_key"),
    )
    op.create_index("ix_daily_goals_day", "daily_goals", ["day"])

    op.create_table(
        "daily_pages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("page", sa.String(length=500), nullable=False),
        sa.Column("views", sa.Integer(), nullable=True),
        sa.Column("visitors", sa.Integer(), nullable=True),
        sa.Column("total_dwell_ms", sa.BigInteger(), nullable=True),
        sa.Column("total_active_ms", sa.BigInteger(), nullable=True),
        sa.Column("avg_scroll_pct", sa.Numeric(5, 1), nullable=True),
        sa.Column("dead_clicks", sa.Integer(), nullable=True),
        sa.Column("computed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("day", "page", name="uq_daily_page_key"),
    )
    op.create_index("ix_daily_pages_day", "daily_pages", ["day"])

    # --- расходы Директа (каркас) ---
    op.create_table(
        "direct_costs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("campaign", sa.String(length=300), nullable=False),
        sa.Column("cost_rub", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("clicks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("synced_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("day", "campaign", name="uq_direct_cost_day_campaign"),
    )
    op.create_index("ix_direct_costs_day", "direct_costs", ["day"])


def downgrade() -> None:
    op.drop_table("direct_costs")
    op.drop_table("daily_pages")
    op.drop_table("daily_goals")
    op.drop_table("daily_traffic")
    op.drop_table("server_sessions")
    op.drop_table("metrika_goals")
    op.drop_table("identity_links")
    op.drop_index("ix_behavior_sessions_visitor_id_hash", table_name="behavior_sessions")
    for col in (
        "is_webdriver", "orientation", "color_scheme", "cpu_cores", "device_memory",
        "downlink", "conn_type", "city", "geo_region", "country", "yclid",
        "utm_content", "utm_term", "channel", "ym_client_id", "visitor_id_hash",
    ):
        op.drop_column("behavior_sessions", col)
    op.drop_index("ix_behavior_events_visitor_id_hash", table_name="behavior_events")
    op.drop_column("behavior_events", "visitor_id_hash")
    op.drop_index("ix_frontend_events_visitor_id_hash", table_name="frontend_events")
    op.drop_column("frontend_events", "visitor_id_hash")

"""Analytics: user_signups, daily_goal_dims, site_locale for sessions (round 11, zone H).

Revision ID: 20261009b_analytics_signups
Revises: 20261009_user_cabinet

Только добавления, ничего не переписывается и не блокируется надолго:
- `user_signups`: новая маленькая таблица (одна строка на аккаунт, FK на users с CASCADE);
- `daily_goal_dims`: новая таблица-роллап (пересобирается задачей);
- `behavior_sessions.site_locale`, `server_sessions.site_locale`: nullable без значения
  по умолчанию (PostgreSQL ≥ 11 добавляет такую колонку мгновенно, без переписывания таблицы).
Индексов на больших таблицах (`frontend_events`, `behavior_events`) нет. Старый код новых
колонок и таблиц не читает, откат кода безопасен.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261009b_analytics_signups"
down_revision = "20261009_user_cabinet"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_signups",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("method", sa.String(20), nullable=True),
        sa.Column("site_locale", sa.String(2), nullable=True),
        sa.Column("newsletter", sa.Boolean(), nullable=True),
        sa.Column("country", sa.String(60), nullable=True),
        sa.Column("country_code", sa.String(2), nullable=True),
        sa.Column("geo_region", sa.String(120), nullable=True),
        sa.Column("channel", sa.String(20), nullable=True),
        sa.Column("referrer_host", sa.String(200), nullable=True),
        sa.Column("utm_source", sa.String(120), nullable=True),
        sa.Column("utm_medium", sa.String(120), nullable=True),
        sa.Column("utm_campaign", sa.String(200), nullable=True),
        sa.Column("device_type", sa.String(12), nullable=True),
        sa.Column("browser", sa.String(40), nullable=True),
        sa.Column("os", sa.String(30), nullable=True),
        sa.Column("browser_lang", sa.String(16), nullable=True),
        sa.Column("landing_page", sa.String(500), nullable=True),
        sa.Column("trigger", sa.String(30), nullable=True),
        sa.Column("sessions_before", sa.Integer(), nullable=True),
        sa.Column("pageviews_before", sa.Integer(), nullable=True),
        sa.Column("days_to_signup", sa.Integer(), nullable=True),
        sa.Column("filled_at", sa.DateTime(), nullable=True),
        sa.Column("source", sa.String(20), nullable=True),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index("ix_user_signups_created", "user_signups", ["created_at"])

    op.create_table(
        "daily_goal_dims",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("event_name", sa.String(120), nullable=False),
        sa.Column("dim", sa.String(20), nullable=False),
        sa.Column("value", sa.String(120), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sessions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("day", "event_name", "dim", "value", name="uq_daily_goal_dim_key"),
    )
    op.create_index("ix_daily_goal_dims_day", "daily_goal_dims", ["day"])

    op.add_column("behavior_sessions", sa.Column("site_locale", sa.String(2), nullable=True))
    op.add_column("server_sessions", sa.Column("site_locale", sa.String(2), nullable=True))


def downgrade():
    op.drop_column("server_sessions", "site_locale")
    op.drop_column("behavior_sessions", "site_locale")
    op.drop_index("ix_daily_goal_dims_day", table_name="daily_goal_dims")
    op.drop_table("daily_goal_dims")
    op.drop_index("ix_user_signups_created", table_name="user_signups")
    op.drop_table("user_signups")

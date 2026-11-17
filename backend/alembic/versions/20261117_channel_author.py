"""Автор Telegram-канала: черновики, запуски модели, счётчик канала (17.11.2026, ADR-0035).

Revision ID: 20261117_channel_author
Revises: 20261116_mail_tracking

Только добавляющая миграция: пять новых таблиц, старые не тронуты. ПДн в них нет: тексты постов,
числа и адреса источников, число подписчиков и просмотров, расход на модель.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261117_channel_author"
down_revision = "20261116_mail_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "channel_posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("rubric", sa.String(20), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="draft"),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("chart_topic", sa.String(20), nullable=True),
        sa.Column("link_url", sa.String(500), nullable=True),
        sa.Column("silent", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("why", sa.String(600), nullable=True),
        sa.Column("planned_at", sa.DateTime(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("decided_by", sa.String(32), nullable=True),
        sa.Column("feedback", sa.String(600), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("telegram_message_id", sa.Integer(), nullable=True),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("run_id", sa.Integer(), nullable=True),
        sa.Column("blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("audit", sa.JSON(), nullable=True),
        sa.Column("review_messages", sa.JSON(), nullable=True),
        sa.Column("error", sa.String(300), nullable=True),
    )
    op.create_index("ix_channel_posts_status", "channel_posts", ["status", "planned_at"])
    op.create_index("ix_channel_posts_created", "channel_posts", ["created_at"])
    op.create_table(
        "channel_author_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("trigger", sa.String(300), nullable=True),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="ok"),
        sa.Column("decision", sa.String(20), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("steps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("web_searches", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(10, 5), nullable=False, server_default="0"),
        sa.Column("seconds", sa.Numeric(8, 1), nullable=True),
    )
    op.create_index("ix_channel_author_runs_started", "channel_author_runs", ["started_at"])
    op.create_table(
        "channel_stats_daily",
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("subscribers", sa.Integer(), nullable=False),
        sa.Column("taken_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "channel_post_views",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("views", sa.Integer(), nullable=False),
        sa.Column("posted_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("message_id", "day", name="uq_channel_post_views_msg_day"),
    )
    op.create_table(
        "channel_voice_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("text", sa.String(300), nullable=False),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_table("channel_voice_rules")
    op.drop_table("channel_post_views")
    op.drop_table("channel_stats_daily")
    op.drop_index("ix_channel_author_runs_started", table_name="channel_author_runs")
    op.drop_table("channel_author_runs")
    op.drop_index("ix_channel_posts_created", table_name="channel_posts")
    op.drop_index("ix_channel_posts_status", table_name="channel_posts")
    op.drop_table("channel_posts")

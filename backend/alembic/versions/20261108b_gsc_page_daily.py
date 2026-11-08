"""Ежедневный снимок Google Search Console по страницам (гигиена после падения Google, 08.11.2026).

Revision ID: 20261108b_gsc_page_daily
Revises: 20261108_public_bot

Только добавляющая миграция: новая таблица `gsc_page_daily`. `gsc_search_queries` хранит строки с видимым
запросом — это 3–6% показов; разрез «страница × день» без запроса отдаёт полные показы и клики страницы.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261108b_gsc_page_daily"
down_revision = "20261108_public_bot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gsc_page_daily",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("page", sa.String(1000), nullable=False),
        sa.Column("impressions", sa.Integer(), nullable=True),
        sa.Column("clicks", sa.Integer(), nullable=True),
        sa.Column("ctr", sa.Numeric(8, 4), nullable=True),
        sa.Column("position", sa.Numeric(8, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("date", "page", name="uq_gsc_page_daily"),
    )
    op.create_index("ix_gsc_page_daily_date", "gsc_page_daily", ["date"])


def downgrade() -> None:
    op.drop_index("ix_gsc_page_daily_date", table_name="gsc_page_daily")
    op.drop_table("gsc_page_daily")

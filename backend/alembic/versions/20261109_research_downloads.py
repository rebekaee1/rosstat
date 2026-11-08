"""Счётчик скачиваний отчётов раздела «Исследования» (09.11.2026).

Revision ID: 20261109_research_downloads
Revises: 20261108b_gsc_page_daily

Только добавляющая миграция: таблица `research_downloads` (отчёт × день → число скачиваний), без ПДн.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261109_research_downloads"
down_revision = "20261108b_gsc_page_daily"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_downloads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("slug", "date", name="uq_research_downloads_slug_date"),
    )


def downgrade() -> None:
    op.drop_table("research_downloads")

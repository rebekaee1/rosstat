"""Счётчик скачиваний отчётов раздела «Исследования» (09.11.2026).

Revision ID: 20261109_research_downloads
Revises: 20261109_public_bot_dialog

Только добавляющая миграция: таблица `research_downloads` (отчёт × день × источник → число скачиваний), без ПДн.
Источник (09.11.2026, до первого выпуска): site — переход со страницы сайта, bot / tg — помеченные ссылки бота и
канала, direct — без перехода с сайта и без метки (так ходит ферма); в публичный счёт direct не входит.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261109_research_downloads"
down_revision = "20261109_public_bot_dialog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_downloads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(16), nullable=False, server_default="site"),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("slug", "date", "source", name="uq_research_downloads_slug_date_src"),
    )


def downgrade() -> None:
    op.drop_table("research_downloads")

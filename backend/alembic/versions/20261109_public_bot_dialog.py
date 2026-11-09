"""Журнал переписки публичного бота: входящие сообщения с профилем и запросы к модели (решение владельца 09.11.2026).

Revision ID: 20261109_public_bot_dialog
Revises: 20261108b_gsc_page_daily

Только добавляющая миграция: одна новая таблица.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261109_public_bot_dialog"
down_revision = "20261108b_gsc_page_daily"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "public_bot_dialog",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("chat_id", sa.String(32)),
        sa.Column("user_id", sa.String(32)),
        sa.Column("username", sa.String(64)),
        sa.Column("first_name", sa.String(128)),
        sa.Column("last_name", sa.String(128)),
        sa.Column("language_code", sa.String(16)),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("text", sa.Text()),
        sa.Column("payload", sa.JSON()),
    )
    op.create_index("ix_public_bot_dialog_occurred_at", "public_bot_dialog", ["occurred_at"])
    op.create_index("ix_public_bot_dialog_chat_ts", "public_bot_dialog", ["chat_id", "occurred_at"])


def downgrade() -> None:
    op.drop_table("public_bot_dialog")

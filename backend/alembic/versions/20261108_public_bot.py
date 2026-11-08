"""Публичный Telegram-бот: чаты, события, подписки (решение владельца 08.11.2026).

Revision ID: 20261108_public_bot
Revises: 20261012_world_ingest_note

Только добавляющая миграция: три новые таблицы, существующие не меняются. Код работает с пустыми
таблицами; публичные ответы включает флаг RUSTATS_PUBLIC_BOT_ENABLED (по умолчанию выключен).
"""
from alembic import op
import sqlalchemy as sa

revision = "20261108_public_bot"
down_revision = "20261012_world_ingest_note"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "public_bot_chats",
        sa.Column("chat_id", sa.String(32), primary_key=True),
        sa.Column("chat_hash", sa.String(64), nullable=False),
        sa.Column("first_code", sa.String(64)),
        sa.Column("heard_from", sa.String(24)),
        sa.Column("asked_source_at", sa.DateTime()),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("blocked_at", sa.DateTime()),
    )
    op.create_index("ix_public_bot_chats_chat_hash", "public_bot_chats", ["chat_hash"])
    op.create_table(
        "public_bot_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("chat_hash", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("code", sa.String(64)),
        sa.Column("topic", sa.String(24)),
    )
    op.create_index("ix_public_bot_events_chat_hash", "public_bot_events", ["chat_hash"])
    op.create_index("ix_public_bot_events_kind_ts", "public_bot_events", ["kind", "occurred_at"])
    op.create_table(
        "public_bot_subscriptions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("chat_id", sa.String(32), sa.ForeignKey("public_bot_chats.chat_id", ondelete="CASCADE"), nullable=False),
        sa.Column("topic", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_point_date", sa.Date()),
        sa.Column("last_value", sa.Numeric(14, 4)),
        sa.Column("last_sent_at", sa.DateTime()),
        sa.UniqueConstraint("chat_id", "topic", name="uq_public_bot_sub_chat_topic"),
    )
    op.create_index("ix_public_bot_subscriptions_chat_id", "public_bot_subscriptions", ["chat_id"])


def downgrade() -> None:
    op.drop_table("public_bot_subscriptions")
    op.drop_table("public_bot_events")
    op.drop_table("public_bot_chats")

"""telegram_outbox — архив всех исходящих Telegram-отправок (глаза агента).

Revision ID: 20260704_tg_outbox
Revises: 20260703_hypotheses
Create Date: 2026-07-04
"""
from alembic import op
import sqlalchemy as sa


revision = "20260704_tg_outbox"
down_revision = "20260703_hypotheses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_outbox",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("sent_at", sa.DateTime(), nullable=False),
        sa.Column("chat_id", sa.String(length=32), nullable=False),
        sa.Column("method", sa.String(length=30), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False, server_default="generic"),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("file_name", sa.String(length=200), nullable=True),
        sa.Column("file_content", sa.LargeBinary(), nullable=True),
        sa.Column("ok", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=True),
        sa.Column("error", sa.String(length=300), nullable=True),
    )
    op.create_index("ix_tg_outbox_ts", "telegram_outbox", ["sent_at"])
    op.create_index("ix_tg_outbox_kind", "telegram_outbox", ["kind", "sent_at"])


def downgrade() -> None:
    op.drop_index("ix_tg_outbox_kind", table_name="telegram_outbox")
    op.drop_index("ix_tg_outbox_ts", table_name="telegram_outbox")
    op.drop_table("telegram_outbox")

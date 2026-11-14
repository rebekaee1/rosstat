"""Журнал писем mail_outbox (14.11.2026, ADR-0032).

Revision ID: 20261114_mail_outbox
Revises: 20261114_pulse_context

Только добавляющая миграция: новая таблица, существующие не меняются. Адрес получателя —
ПДн: строка удаляется вместе с аккаунтом (FK ON DELETE CASCADE + явное удаление в
DELETE /account). Тело письма не хранится.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261114_mail_outbox"
down_revision = "20261114_pulse_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mail_outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("campaign", sa.String(80), nullable=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("to_email", sa.String(320), nullable=False),
        sa.Column("locale", sa.String(5), nullable=False, server_default="ru"),
        sa.Column("subject", sa.String(300), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.String(200), nullable=True),
        sa.Column("message_id", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("campaign", "user_id", name="uq_mail_outbox_campaign_user"),
    )
    op.create_index("ix_mail_outbox_user", "mail_outbox", ["user_id"])
    op.create_index("ix_mail_outbox_status_created", "mail_outbox", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_mail_outbox_status_created", table_name="mail_outbox")
    op.drop_index("ix_mail_outbox_user", table_name="mail_outbox")
    op.drop_table("mail_outbox")

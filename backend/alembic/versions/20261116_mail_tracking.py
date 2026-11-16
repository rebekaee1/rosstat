"""Воронка письма: разрезы и итоги в mail_outbox, события mail_events (16.11.2026, ADR-0034).

Revision ID: 20261116_mail_tracking
Revises: 20261115_newsletter_personal

Только добавляющая миграция: новые необязательные столбцы журнала писем и новая таблица
событий. События письма — ПДн (действие человека): удаляются вместе с письмом и аккаунтом
(ON DELETE CASCADE). IP и строка User-Agent не хранятся.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261116_mail_tracking"
down_revision = "20261115_newsletter_personal"
branch_labels = None
depends_on = None

_COLUMNS = (
    sa.Column("variant", sa.String(12), nullable=True),
    sa.Column("addr_verified", sa.Boolean(), nullable=True),
    sa.Column("provider", sa.String(12), nullable=True),
    sa.Column("tracked", sa.Boolean(), nullable=True),
    sa.Column("opened_at", sa.DateTime(), nullable=True),
    sa.Column("opens", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("machine_opened_at", sa.DateTime(), nullable=True),
    sa.Column("open_client", sa.String(20), nullable=True),
    sa.Column("clicked_at", sa.DateTime(), nullable=True),
    sa.Column("clicks", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("bounced_at", sa.DateTime(), nullable=True),
)


def upgrade() -> None:
    for col in _COLUMNS:
        op.add_column("mail_outbox", col.copy())
    op.create_table(
        "mail_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mail_id", sa.Integer(), sa.ForeignKey("mail_outbox.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("campaign", sa.String(80), nullable=True),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("machine", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("client", sa.String(20), nullable=True),
        sa.Column("block", sa.String(40), nullable=True),
        sa.Column("session_id_hash", sa.String(80), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("kind", "session_id_hash", name="uq_mail_events_kind_session"),
    )
    op.create_index("ix_mail_events_mail", "mail_events", ["mail_id", "kind"])
    op.create_index("ix_mail_events_campaign", "mail_events", ["campaign", "kind", "occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_mail_events_campaign", table_name="mail_events")
    op.drop_index("ix_mail_events_mail", table_name="mail_events")
    op.drop_table("mail_events")
    for col in reversed(_COLUMNS):
        op.drop_column("mail_outbox", col.name)

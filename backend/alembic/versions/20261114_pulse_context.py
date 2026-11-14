"""Заметки владельца для аналитика Пульса (14.11.2026).

Revision ID: 20261114_pulse_context
Revises: 20261113_world_slice_idx

Только добавляющая миграция: таблица `pulse_context_notes` (текст до 600 знаков, срок показа, пометка удаления).
Пишет служебный бот по команде /context или тексту «контекст …» из чата владельца; читает Пульс в блок «Контекст
проекта». Почты и телефоны вычищаются до записи. Откат - удаление таблицы, данные заметок теряются.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261114_pulse_context"
down_revision = "20261113_world_slice_idx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pulse_context_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("text", sa.String(600), nullable=False),
        sa.Column("until", sa.Date(), nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_table("pulse_context_notes")

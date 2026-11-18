"""Человек подтверждён признаком живого посетителя: server_sessions.is_human (18.11.2026, ADR-0009).

Revision ID: 20261118_session_is_human
Revises: 20261117_channel_author

Одна колонка, допускающая NULL и без значения по умолчанию: на PostgreSQL это правка только описания
таблицы, строки не переписываются. NULL — сессия посчитана до правила; сессионизация заполняет
колонку при каждом пересчёте окна (последние двое суток — ежечасно).
"""
from alembic import op
import sqlalchemy as sa

revision = "20261118_session_is_human"
down_revision = "20261117_channel_author"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("server_sessions", sa.Column("is_human", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("server_sessions", "is_human")

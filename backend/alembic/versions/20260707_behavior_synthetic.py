"""behavior_sessions.is_synthetic: частичный портрет, собранный сервером
из батча событий (UA запроса + первый pageview), когда session_start потерян.

Волна 2 BI (2026-07-07, п. 1/4): портрет обязан существовать у КАЖДОЙ сессии —
иначе канал и срезы аудитории строятся только по доле трафика. Настоящий
session_start, дошедший позже, апгрейдит синтетическую строку полным портретом.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260707_beh_synth"
down_revision = "20260706_bi21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "behavior_sessions",
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("behavior_sessions", "is_synthetic")

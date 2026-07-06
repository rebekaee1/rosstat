"""BI 2.1: soft-delete словаря целей Метрики + bot_score/is_internal сессий.

Аддитивно: колонки с server_default, существующие данные не трогаются.

Revision ID: 20260706_bi21
Revises: 20260706_analytics2
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa

revision = "20260706_bi21"
down_revision = "20260706_analytics2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "metrika_goals",
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "server_sessions",
        sa.Column("bot_score", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "server_sessions",
        sa.Column("is_internal", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("server_sessions", "is_internal")
    op.drop_column("server_sessions", "bot_score")
    op.drop_column("metrika_goals", "deleted")

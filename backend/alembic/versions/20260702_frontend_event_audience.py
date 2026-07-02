"""frontend_events: атрибуция аудитории (user_id + authed)

Аддитивная миграция (ADR-0002 инвариант «миграции только добавляют»):
даёт разрез «гость vs зарегистрированный» в first-party аналитике («Пульс»).
Сервер резолвит сессию (кука fe_sess) на приёме события и проставляет флаги.

Revision ID: 20260702_fe_audience
Revises: 20260702_regional
Create Date: 2026-07-02
"""
from alembic import op
import sqlalchemy as sa

revision = "20260702_fe_audience"
down_revision = "20260702_regional"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "frontend_events",
        sa.Column("user_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "frontend_events",
        sa.Column(
            "authed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index(
        "ix_frontend_events_user_id", "frontend_events", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_frontend_events_user_id", table_name="frontend_events")
    op.drop_column("frontend_events", "authed")
    op.drop_column("frontend_events", "user_id")

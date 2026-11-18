"""Недельные цены на топливо по субъектам РФ: таблица region_weekly_data (18.11.2026, ADR-0008).

Revision ID: 20261118_region_weekly
Revises: 20261117_channel_author

Только добавляющая миграция: одна новая таблица, старые не тронуты. Неделя хранится датой
регистрации цен Росстатом (не номером недели): люди спрашивают цену «на 01.01.2026».
"""
from alembic import op
import sqlalchemy as sa

revision = "20261118_region_weekly"
down_revision = "20261117_channel_author"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "region_weekly_data",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "indicator_id", sa.Integer(),
            sa.ForeignKey("region_indicators.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "region_id", sa.Integer(),
            sa.ForeignKey("regions.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(18, 4), nullable=False),
        sa.UniqueConstraint("indicator_id", "region_id", "date", name="uq_region_weekly_point"),
    )
    op.create_index(
        "ix_region_weekly_region_indicator_date", "region_weekly_data",
        ["region_id", "indicator_id", "date"],
    )


def downgrade() -> None:
    op.drop_index("ix_region_weekly_region_indicator_date", table_name="region_weekly_data")
    op.drop_table("region_weekly_data")

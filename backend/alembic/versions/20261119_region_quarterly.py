"""Квартальный слой регионов: таблица region_quarterly_data (19.11.2026, ADR-0008).

Revision ID: 20261119_region_quarterly
Revises: 20261119_world_latest_points

Только добавляющая миграция: одна новая таблица, старые не тронуты. Квартал хранится как YYYYQ (20263 —
III квартал 2026). Первые ряды — цена 1 м² жилья и её индексы, цена 1 м² в центрах субъектов, доходы к
прожиточному минимуму (ЕМИСС 31452, 30925, 61781, 58537).

Уникальный ключ (indicator_id, region_id, quarter) сам служит индексом пары «показатель × регион»;
второй индекс (indicator_id, quarter) — для карты и рейтинга по последнему кварталу.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261119_region_quarterly"
down_revision = "20261119_world_latest_points"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "region_quarterly_data",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "indicator_id", sa.Integer(),
            sa.ForeignKey("region_indicators.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "region_id", sa.Integer(),
            sa.ForeignKey("regions.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("quarter", sa.Integer(), nullable=False),
        sa.Column("value", sa.Numeric(18, 4), nullable=False),
        sa.UniqueConstraint("indicator_id", "region_id", "quarter", name="uq_region_quarterly_point"),
    )
    op.create_index(
        "ix_region_quarterly_indicator_quarter", "region_quarterly_data",
        ["indicator_id", "quarter"],
    )


def downgrade() -> None:
    op.drop_index("ix_region_quarterly_indicator_quarter", table_name="region_quarterly_data")
    op.drop_table("region_quarterly_data")

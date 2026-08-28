"""Помесячный слой регионального bounded context (region_monthly_data).

Первая витрина — потребительские цены на бензин/дизель по субъектам РФ
(ЕМИСС, помесячно). Отдельная таблица вместо досеивания в годовую region_data:
смешение частот в одной таблице — задокументированный trap (CONTEXT.md,
annual-in-monthly mixing).

Revision ID: 20260827_region_monthly_points
Revises: 20260826_world_search_trgm
Create Date: 2026-08-27
"""
import sqlalchemy as sa
from alembic import op


revision = "20260827_region_monthly_points"
down_revision = "20260826_world_search_trgm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "region_monthly_data",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "indicator_id",
            sa.Integer(),
            sa.ForeignKey("region_indicators.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "region_id",
            sa.Integer(),
            sa.ForeignKey("regions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("value", sa.Numeric(18, 4), nullable=False),
        sa.UniqueConstraint("indicator_id", "region_id", "month", name="uq_region_monthly_point"),
    )
    op.create_index(
        "ix_region_monthly_indicator_month",
        "region_monthly_data",
        ["indicator_id", "month"],
    )
    op.create_index(
        "ix_region_monthly_region_indicator_month",
        "region_monthly_data",
        ["region_id", "indicator_id", "month"],
    )


def downgrade() -> None:
    op.drop_table("region_monthly_data")

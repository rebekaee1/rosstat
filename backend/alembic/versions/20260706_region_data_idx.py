"""Композитный индекс region_data (region_id, indicator_id, year DESC).

П-10 (CTO-аудит 2026-07-06): профиль региона и карточка «регион × показатель»
фильтруют по region_id и ранжируют по (indicator_id, year DESC) — одиночный
`ix_region_data_region` заставлял window-функцию сортировать все ~10k точек
региона. Композитный индекс отдаёт данные в готовом порядке.

Revision ID: 20260706_region_data_idx
"""
from alembic import op

revision = "20260706_region_data_idx"
down_revision = "20260706_etl_perf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_region_data_region_indicator_year",
        "region_data",
        ["region_id", "indicator_id", "year"],
        postgresql_using="btree",
    )


def downgrade() -> None:
    op.drop_index("ix_region_data_region_indicator_year", table_name="region_data")

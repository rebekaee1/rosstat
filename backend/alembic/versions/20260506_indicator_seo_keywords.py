"""indicator metadata: seo_keywords (per-page meta keywords)

Revision ID: 20260506_indicator_seo_kw
Revises: 20260505_indicator_seo
Create Date: 2026-05-06

Goal: убрать одинаковую meta-keywords строку, которая до сих пор хардкодилась
в `seo_renderer.py` для всех страниц. После этой миграции каждый индикатор
несёт свою keywords-строку, а на главной/категориях/прочих страницах
keywords задаются через PageSeo/CategorySeo dataclasses.

Migration is purely additive — only ADD COLUMN, no DROP. Backfill значений
делается идемпотентно в `seed_data.py` через `app/data/indicator_seo.py`.
"""
from alembic import op
import sqlalchemy as sa


revision = "20260506_indicator_seo_kw"
down_revision = "20260505_indicator_seo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "indicators",
        sa.Column("seo_keywords", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("indicators", "seo_keywords")

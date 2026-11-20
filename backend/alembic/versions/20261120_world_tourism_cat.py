"""Наборы туризма Евростата — в разделе «Туризм» стран мира (20.11.2026).

Revision ID: 20261120_world_tourism_cat
Revises: 20261119_world_latest_points

Только данные: у рядов Евростата из наборов `tour_*` поле `category_ru` меняется с «Общество» на «Туризм»
(та же тема, что у новых рядов МВФ, UN Tourism и ОЭСР — `world_tourism_sources`). Витрина уже показывает
новую тему через `listing_category_ru`; миграция выравнивает хранимое поле сразу, чтобы блок «Ещё в разделе»
(выборка по `category_ru`) не ждал переингеста каждого набора. Схема не меняется; откат возвращает «Общество».
"""
from alembic import op

revision = "20261120_world_tourism_cat"
down_revision = "20261119_world_latest_points"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE world_indicators SET category_ru = 'Туризм' "
        "WHERE provider = 'eurostat' AND dataset_id LIKE 'tour\\_%' AND category_ru = 'Общество'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE world_indicators SET category_ru = 'Общество' "
        "WHERE provider = 'eurostat' AND dataset_id LIKE 'tour\\_%' AND category_ru = 'Туризм'"
    )

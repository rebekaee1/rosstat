"""Индекс соседей мировой карточки: (country_id, provider, dataset_id pattern_ops).

Revision ID: 20260904_world_card_lookup_idx
Revises: 20260903_indexing_control
Create Date: 2026-09-04

Инцидент 2026-09-04. `world_card_siblings` (legacy_redirects.py) на каждой
мировой карточке ищет ряды той же карточки:

    country_id = ? AND provider = ? AND (dataset_id = stem OR dataset_id LIKE 'stem\\_%')

Планировщик брал uq-индекс (provider, country_id) и фильтровал dataset_id
уже по heap: ~5,7k строк на страну, а строка world_indicators широкая
(description/methodology/seo, ~2,3 КБ) — почти каждая на своей странице.
Итог: ~5,5k страниц (45 МБ) чтения диска на карточку; при 1,7 запросах/с от
поисковых ботов таблица за 4 часа прочитана с диска 136 млн блоков (терабайт),
кэш 41%. Любая дополнительная нагрузка (BI-сканы behavior_events) ставила
диск, и публичные API уходили в таймауты.

btree с varchar_pattern_ops обслуживает и равенство, и префиксный LIKE
независимо от collation базы: BitmapOr двух диапазонов → ~14 строк.
CONCURRENTLY — таблица под постоянным чтением, блокировать её нельзя;
для этого миграция выполняется вне транзакции (autocommit_block).
"""

from alembic import op

revision = "20260904_world_card_lookup_idx"
down_revision = "20260903_indexing_control"
branch_labels = None
depends_on = None

_INDEX_NAME = "ix_world_indicators_card_lookup"


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            f"""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS {_INDEX_NAME}
            ON world_indicators (country_id, provider, dataset_id varchar_pattern_ops)
            """
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX_NAME}")

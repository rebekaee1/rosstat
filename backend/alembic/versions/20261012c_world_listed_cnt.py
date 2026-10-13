"""Счётчик публичных рядов по странам: узкий индекс и материализованная таблица (круг 12, SPEED3).

Revision ID: 20261012c_world_listed_cnt
Revises: 20261012b_world_dset_lower_idx

Холодный рендер главной считал `count(*) ... WHERE is_listed GROUP BY country_id` по 90-мегабайтному покрывающему индексу
`ix_world_indicators_listed_signal`; на боевом под нагрузкой на диск это 15–30 с (таймаут запроса 30 с).
Только добавляющая миграция:
1. узкий partial-индекс `ix_world_indicators_listed_country (country_id) WHERE is_listed` (≈ 2 МБ), CONCURRENTLY;
2. таблица `world_country_listed_counts` (≈ 55 строк), её наполняет планировщик при включении флага
   `RUSTATS_WORLD_LISTED_COUNTS_ENABLED`; миграция её не заполняет (код работает и с пустой таблицей).
Порядок выкладки: индекс можно построить заранее на старом коде (`CREATE INDEX CONCURRENTLY IF NOT EXISTS …`), миграция
тогда ничего не делает.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261012c_world_listed_cnt"
down_revision = "20261012b_world_dset_lower_idx"
branch_labels = None
depends_on = None
_INDEX_NAME = "ix_world_indicators_listed_country"
_TABLE = "world_country_listed_counts"


def _index_flags(name=_INDEX_NAME):
    row = op.get_bind().execute(sa.text(
        "SELECT indisvalid, indisready FROM pg_catalog.pg_index WHERE indexrelid = to_regclass(:name)"
    ), {"name": name}).one_or_none()
    return (bool(row[0]), bool(row[1])) if row is not None else None


def upgrade():
    op.execute(
        f"CREATE TABLE IF NOT EXISTS {_TABLE} ("
        "country_id INTEGER NOT NULL PRIMARY KEY REFERENCES world_countries (id) ON DELETE CASCADE, "
        "listed_count INTEGER NOT NULL, "
        "computed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL)"
    )
    with op.get_context().autocommit_block():
        if _index_flags() not in (None, (True, True)):
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX_NAME}")
        op.execute(
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {_INDEX_NAME} "
            "ON world_indicators (country_id) WHERE is_listed"
        )
        if _index_flags() != (True, True):
            raise RuntimeError(f"{_INDEX_NAME} is not valid after concurrent build")


def downgrade():
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX_NAME}")
    op.execute(f"DROP TABLE IF EXISTS {_TABLE}")

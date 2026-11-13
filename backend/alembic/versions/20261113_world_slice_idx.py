"""Индекс срезов мирового каталога для поиска: условие «член оси» без чтения всей таблицы.

Revision ID: 20261113_world_slice_idx
Revises: 20261109_research_downloads

Поиск проверяет срез ряда Евростата условием «поставщик — Евростат, строковый член оси входит в набор»
(`search_dimensions.native_dimension_match_clause`, `dimension_constraints`). Условие вычисляется из JSON каждой
строки, ни один индекс ему не помогает, и запрос читал `world_indicators` целиком: 110 920 страниц (867 МБ) на
боевом 13.11.2026 в каждом поиске, где слово запроса совпадает с подписью члена среза («импорт», «население»,
«безработица», «кредит»).

Миграция только добавляет:
1. функцию `fe_world_slice_members(provider, slice)` — массив меток «ось=ЧЛЕН» строковых членов среза ряда
   Евростата (для остальных рядов пустой массив); нормализация та же, что в условии поиска (`upper(trim(…))`);
2. GIN-индекс `ix_world_indicators_slice_members` по этой функции (колонка среза приводится к jsonb: в базе она
   jsonb, в модели объявлена как JSON; явное приведение одинаково в индексе и в запросе при любом из двух типов). Индекс ведёт сама база при каждой записи
   строки: отдельного обновления нет и отстать он не может.

Индекс строится CONCURRENTLY, без блокировки записи и чтения: один проход по таблице. Код поиска работает и без
индекса (наличие проверяет `search._slice_index_available` раз в минуту), поэтому порядок «код раньше миграции»
и откат безопасны. Откат снимает сначала индекс, затем, после паузы дольше минуты проверки, функцию.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261113_world_slice_idx"
down_revision = "20261109_research_downloads"
branch_labels = None
depends_on = None

_INDEX_NAME = "ix_world_indicators_slice_members"
_FUNCTION = "fe_world_slice_members"
# Поиск перепроверяет наличие индекса раз в 60 с (`search._SLICE_INDEX_RECHECK_SECONDS`).
_RECHECK_PAUSE_SECONDS = 65

_CREATE_FUNCTION = f"""
CREATE OR REPLACE FUNCTION {_FUNCTION}(provider text, slice jsonb) RETURNS text[]
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $fe$
    SELECT CASE
        WHEN lower(trim(coalesce(provider, ''))) = 'eurostat' AND jsonb_typeof(slice) = 'object' THEN
            ARRAY(SELECT member.key || '=' || upper(trim(member.value #>> '{{}}'))
                  FROM jsonb_each(slice) AS member
                  WHERE jsonb_typeof(member.value) = 'string')
        ELSE '{{}}'::text[]
    END
$fe$
"""


def _index_flags(name=_INDEX_NAME):
    row = op.get_bind().execute(sa.text(
        "SELECT indisvalid, indisready FROM pg_catalog.pg_index WHERE indexrelid = to_regclass(:name)"
    ), {"name": name}).one_or_none()
    return (bool(row[0]), bool(row[1])) if row is not None else None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    with op.get_context().autocommit_block():
        op.execute(_CREATE_FUNCTION)
        if _index_flags() not in (None, (True, True)):
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX_NAME}")
        op.execute(
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {_INDEX_NAME} "
            f"ON world_indicators USING gin ({_FUNCTION}(provider, CAST(slice_json AS jsonb)))"
        )
        if _index_flags() != (True, True):
            raise RuntimeError(f"{_INDEX_NAME} is not valid after concurrent build")
        op.execute("ANALYZE world_indicators")


def downgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    with op.get_context().autocommit_block():
        had_index = _index_flags() is not None
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX_NAME}")
        if had_index:
            # Работающий поиск ещё до минуты считает индекс живым и вызывает функцию.
            op.execute(f"SELECT pg_sleep({_RECHECK_PAUSE_SECONDS})")
        op.execute(f"DROP FUNCTION IF EXISTS {_FUNCTION}(text, jsonb)")

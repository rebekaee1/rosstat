"""Индекс по lower(dataset_id) для мировых выборок «по набору данных» (круг 12, SPEED2).

Revision ID: 20261012b_world_dataset_lower_idx
Revises: 20261009c_session_perf

Запросы сравнения стран, рейтингов и карт отбирают ряды условием `lower(dataset_id) IN (...)`; индекс по самому
`dataset_id` для такого выражения не годится, и каждая холодная выборка читала всю таблицу `world_indicators`
(691 МБ, 355 тыс. строк: 0,5 с на стенде, 8 мс с индексом). Только добавляющая миграция: один функциональный индекс.
Строится CONCURRENTLY без блокировки записи (занимает ≈ 1 с на данных боевого размера); код работает и без него.
Порядок выкладки: можно построить заранее на старом коде той же командой (`CREATE INDEX CONCURRENTLY IF NOT EXISTS …`),
миграция тогда ничего не делает.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261012b_world_dataset_lower_idx"
down_revision = "20261009c_session_perf"
branch_labels = None
depends_on = None
_INDEX_NAME = "ix_world_indicators_dataset_lower"


def _index_flags(name=_INDEX_NAME):
    row = op.get_bind().execute(sa.text(
        "SELECT indisvalid, indisready FROM pg_catalog.pg_index WHERE indexrelid = to_regclass(:name)"
    ), {"name": name}).one_or_none()
    return (bool(row[0]), bool(row[1])) if row is not None else None


def upgrade():
    with op.get_context().autocommit_block():
        if _index_flags() not in (None, (True, True)):
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX_NAME}")
        op.execute(
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {_INDEX_NAME} "
            "ON world_indicators (lower(dataset_id)) INCLUDE (country_id)"
        )
        if _index_flags() != (True, True):
            raise RuntimeError(f"{_INDEX_NAME} is not valid after concurrent build")
        op.execute("ANALYZE world_indicators")


def downgrade():
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX_NAME}")

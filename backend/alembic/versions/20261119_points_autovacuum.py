"""Автоочистка таблиц точек мира и регионов мира по доле 1–2 %, а не 20 % (19.11.2026).

Revision ID: 20261119_points_autovacuum
Revises: 20261118_search_index

Боевой 19.11.2026: `world_data_points` — 16,55 млн живых строк, 1,61 млн мёртвых, последняя автоочистка
25.09, карта видимости 75 %. Ничто очистку не держало: долгих транзакций, подготовленных транзакций и слотов
репликации нет, отмен автоочистки в журнале нет. Порог по умолчанию — 50 + 20 % строк = 3,3 млн мёртвых
(и 3,3 млн вставок для очистки по вставкам, 1,65 млн изменений для сбора статистики); правки источников
дают ~38 тыс. изменённых строк в сутки, до порога — 2,5 месяца. Мёртвые версии сидят на последних точках
рядов (правят обычно свежие значения), то есть ровно там, что читает каталог страны.
`subnational_data_points` — то же: 4,55 млн строк, 0,65 млн мёртвых, очистка 24.09, карта видимости 9 %.

Миграция только меняет параметры хранения двух таблиц (ALTER TABLE … SET, блокировка
SHARE UPDATE EXCLUSIVE: чтение и запись идут, ждёт только идущую автоочистку этой таблицы):
- `autovacuum_vacuum_scale_factor=0.01`, `autovacuum_vacuum_threshold=10000` — очистка после ~1 % мёртвых
  строк (175 тыс. у точек мира: раз в 4–5 суток при нынешнем потоке правок);
- `autovacuum_vacuum_insert_scale_factor=0.02` — после загрузки новых рядов карта видимости обновляется
  через ~330 тыс. вставок, а не 3,3 млн;
- `autovacuum_analyze_scale_factor=0.05` — статистика раз в ~830 тыс. изменений: у `indicator_id` точек
  мира цель статистики 1000 (deploy/pg-world-catalog-maintenance.sql), один сбор читает почти всю таблицу;
- `log_autovacuum_min_duration=0` — каждый проход автоочистки этих таблиц пишется в журнал Postgres
  (глобально 10 мин), чтобы отставание было видно без запросов.
Темп очистки (`autovacuum_vacuum_cost_limit`) не трогаем: диск ВМ общий и медленный, частые небольшие
проходы с прежним темпом безопаснее редких быстрых.

Разовую очистку накопленного (`VACUUM (ANALYZE, VERBOSE)`) миграция не делает: внутри транзакции её нельзя,
а при старте бэкенда в выкладке она заняла бы минуты. Команда и окно — docs/workflow.md, шаг выпуска.
На SQLite ничего не делает. Откат возвращает параметры по умолчанию.
"""
from alembic import op

revision = "20261119_points_autovacuum"
down_revision = "20261118_search_index"
branch_labels = None
depends_on = None

TABLES = ("world_data_points", "subnational_data_points")
OPTIONS = {
    "autovacuum_vacuum_scale_factor": "0.01",
    "autovacuum_vacuum_threshold": "10000",
    "autovacuum_vacuum_insert_scale_factor": "0.02",
    "autovacuum_analyze_scale_factor": "0.05",
    "log_autovacuum_min_duration": "0",
}


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if not _is_postgres():
        return
    # SHARE UPDATE EXCLUSIVE: мешающую автоочистку Postgres отменяет сам (~1 с), ручной VACUUM — нет; за ним не
    # висим дольше 10 с: миграция падает, контейнер перезапускается и повторяет. Ручной VACUUM в выкладку не запускать.
    op.execute("SET LOCAL lock_timeout = '10s'")
    settings = ", ".join(f"{name} = {value}" for name, value in OPTIONS.items())
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} SET ({settings})")
    op.execute("SET LOCAL lock_timeout TO DEFAULT")


def downgrade() -> None:
    if not _is_postgres():
        return
    op.execute("SET LOCAL lock_timeout = '10s'")
    names = ", ".join(OPTIONS)
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} RESET ({names})")
    op.execute("SET LOCAL lock_timeout TO DEFAULT")

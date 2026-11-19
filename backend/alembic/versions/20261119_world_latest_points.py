"""Последние две точки мировых рядов — узкая копия для каталога страны (19.11.2026, ADR-0037).

Revision ID: 20261119_world_latest_points
Revises: 20261119_points_autovacuum

Только добавляющая миграция: две новые пустые таблицы, основные таблицы и загрузки не тронуты.
- `world_latest_points` — одна строка на мировой ряд: последняя и предпоследняя точка, «есть ненулевая точка»;
  индекс по стране покрывает все столбцы, которые читает каталог;
- `world_latest_points_state` — одна строка: копия заведена, заполнена, курсор обхода.

Таблицы наполняют обход планировщика и загрузчики (`app/services/world_latest_points.py`) после заведения копии;
каталог читает их только за флагом `RUSTATS_WORLD_LATEST_POINTS_ENABLED` и после первого полного прохода. Пока
строки состояния нет, никто в копию не пишет, поэтому порядок «код раньше миграции» и откат безопасны.

Строки копии часто переписываются на месте (новая точка ряда): запас места на странице (fillfactor 80) оставляет
такие правки на той же странице, частая автоочистка держит карту видимости свежей для чтения только из индекса.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261119_world_latest_points"
down_revision = "20261119_points_autovacuum"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "world_latest_points",
        sa.Column("indicator_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("country_id", sa.Integer(), nullable=False),
        sa.Column("last_date", sa.Date(), nullable=True),
        sa.Column("last_value", sa.Numeric(20, 6), nullable=True),
        sa.Column("prev_date", sa.Date(), nullable=True),
        sa.Column("prev_value", sa.Numeric(20, 6), nullable=True),
        sa.Column("has_nonzero", sa.Boolean(), nullable=False),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
    )
    if op.get_bind().dialect.name == "postgresql":
        # Таблица только что создана и пуста: параметры хранения ставятся мгновенно.
        op.execute("ALTER TABLE world_latest_points SET (fillfactor = 80, "
                   "autovacuum_vacuum_scale_factor = 0.02, autovacuum_analyze_scale_factor = 0.05)")
    op.create_index(
        "ix_world_latest_points_country", "world_latest_points", ["country_id"],
        postgresql_include=["indicator_id", "last_date", "last_value", "prev_date", "prev_value", "has_nonzero"],
    )
    op.create_table(
        "world_latest_points_state",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("maintained_since", sa.DateTime(), nullable=False),
        sa.Column("filled_at", sa.DateTime(), nullable=True),
        sa.Column("cursor_country_id", sa.Integer(), nullable=True),
        sa.Column("cursor_indicator_id", sa.Integer(), nullable=True),
        sa.Column("pass_started_at", sa.DateTime(), nullable=True),
        sa.Column("pass_completed_at", sa.DateTime(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("rows", sa.Integer(), nullable=True),
        sa.Column("rows_changed", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    # Каталог перестаёт читать копию, как только пропадает строка состояния (читатель смотрит её при каждом расчёте);
    # загрузчики — через минуту памяти процесса, ошибка записи в пропавшую таблицу их не роняет (savepoint).
    op.drop_table("world_latest_points_state")
    op.drop_index("ix_world_latest_points_country", table_name="world_latest_points")
    op.drop_table("world_latest_points")

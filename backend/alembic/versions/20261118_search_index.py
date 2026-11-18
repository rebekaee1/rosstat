"""Поисковый индекс: маленькие копии того, что поиск читает при каждом запросе (18.11.2026, ADR-0036).

Revision ID: 20261118_search_index
Revises: 20261118_region_weekly

Только добавляющая миграция: девять новых пустых таблиц, основные таблицы не тронуты. Таблицы наполняет задача
планировщика `search_index_refresh` (`app/services/search_index.py`); пока часть индекса не собрана, поиск читает
основные таблицы, как раньше. Поэтому порядок «код раньше миграции» и откат безопасны, а сама миграция идёт секунды.

- `search_index_state` — какая копия (`a`/`b`) каждой части действует и из какого состояния основных таблиц собрана;
- `search_world_a/b` — строки `world_indicators` без длинных текстов, с отметкой «есть ненулевой конечный факт»;
- `search_russia_a/b` — активные ряды `indicators` с отметкой «есть конечный факт»;
- `search_region_facts_a/b`, `search_subnational_facts_a/b` — пары «показатель × территория» с данными.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261118_search_index"
down_revision = "20261118_region_weekly"
branch_labels = None
depends_on = None

_COPIES = ("a", "b")


def _world(table: str, postgres: bool) -> None:
    op.create_table(
        table,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("country_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("code", sa.String(120), nullable=False),
        sa.Column("dataset_id", sa.String(160), nullable=False),
        sa.Column("slice_json", postgresql.JSONB() if postgres else sa.JSON(), nullable=True),
        sa.Column("slice_hash", sa.String(64), nullable=False),
        sa.Column("name_ru", sa.String(400), nullable=False),
        sa.Column("name_en", sa.String(400), nullable=True),
        sa.Column("unit", sa.String(80), nullable=False),
        sa.Column("unit_ru", sa.String(80), nullable=False),
        sa.Column("frequency", sa.String(20), nullable=False),
        sa.Column("category_ru", sa.String(80), nullable=False),
        sa.Column("seo_keywords", sa.Text(), nullable=True),
        sa.Column("is_listed", sa.Boolean(), nullable=False),
        sa.Column("points_count", sa.Integer(), nullable=False),
        sa.Column("history_end", sa.Date(), nullable=True),
        sa.Column("ord", sa.Integer(), nullable=False),
        sa.Column("country_ord", sa.Integer(), nullable=False),
        sa.Column("has_fact", sa.Boolean(), nullable=False),
    )
    op.create_index(f"ix_{table}_code", table, ["code"], unique=True)
    op.create_index(f"ix_{table}_ord", table, ["ord"], unique=True)
    op.create_index(f"ix_{table}_country_ord", table, ["country_id", "country_ord"], unique=True)
    op.create_index(f"ix_{table}_listed_fact_country", table, ["country_id"],
                    postgresql_where=sa.text("is_listed AND has_fact"))
    op.create_index(f"ix_{table}_card_lookup", table, ["country_id", "provider", "dataset_id"],
                    postgresql_ops={"dataset_id": "varchar_pattern_ops"})
    op.create_index(f"ix_{table}_search_text_trgm", table, ["code", "name_ru", "name_en", "seo_keywords"],
                    postgresql_using="gin",
                    postgresql_ops={"code": "gin_trgm_ops", "name_ru": "gin_trgm_ops", "name_en": "gin_trgm_ops",
                                    "seo_keywords": "gin_trgm_ops"})
    if postgres:
        # То же выражение, что у `ix_world_indicators_slice_members` и в условии поиска (`search_dimensions`).
        op.execute(f"CREATE INDEX ix_{table}_slice_members ON {table} "
                   f"USING gin (fe_world_slice_members(provider, CAST(slice_json AS jsonb)))")
        # Точное совпадение кода и названия с запросом (ранг 0–1 выдачи): `col ILIKE 'слово'` в базе UTF-8 — это
        # `lower(col) = lower('слово')`; триграммный индекс на таком условии перепроверяет тысячи строк с теми же буквами.
        for column in ("code", "name_ru", "name_en"):
            op.execute(f"CREATE INDEX ix_{table}_lower_{column} ON {table} (lower({column}))")


def upgrade() -> None:
    postgres = op.get_bind().dialect.name == "postgresql"
    op.create_table(
        "search_index_state",
        sa.Column("part", sa.String(16), primary_key=True),
        sa.Column("active", sa.String(1), nullable=True),
        sa.Column("built_at", sa.DateTime(), nullable=True),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column("rows", sa.Integer(), nullable=True),
        sa.Column("seconds", sa.Numeric(10, 2), nullable=True),
    )
    for copy in _COPIES:
        _world(f"search_world_{copy}", postgres)
        op.create_table(
            f"search_russia_{copy}",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
            sa.Column("code", sa.String(50), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("name_en", sa.String(200), nullable=True),
            sa.Column("unit", sa.String(20), nullable=False),
            sa.Column("frequency", sa.String(50), nullable=False),
            sa.Column("category", sa.String(100), nullable=True),
            sa.Column("seo_keywords", sa.Text(), nullable=True),
            sa.Column("is_listed", sa.Boolean(), nullable=False),
            sa.Column("has_fact", sa.Boolean(), nullable=False),
        )
        op.create_table(
            f"search_region_facts_{copy}",
            sa.Column("indicator_id", sa.Integer(), primary_key=True, autoincrement=False),
            sa.Column("region_id", sa.Integer(), primary_key=True, autoincrement=False),
            sa.Column("has_annual", sa.Boolean(), nullable=False),
            sa.Column("has_monthly", sa.Boolean(), nullable=False),
            sa.Column("last_year", sa.Integer(), nullable=True),
            sa.Column("last_year_value", sa.Numeric(18, 4), nullable=True),
            sa.Column("last_month", sa.Integer(), nullable=True),
            sa.Column("last_month_value", sa.Numeric(18, 4), nullable=True),
        )
        op.create_index(f"ix_search_region_facts_{copy}_region", f"search_region_facts_{copy}", ["region_id"])
        op.create_table(
            f"search_subnational_facts_{copy}",
            sa.Column("indicator_id", sa.Integer(), primary_key=True, autoincrement=False),
            sa.Column("region_id", sa.Integer(), primary_key=True, autoincrement=False),
        )
        op.create_index(f"ix_search_subnational_facts_{copy}_region", f"search_subnational_facts_{copy}", ["region_id"])


def downgrade() -> None:
    # Поиск перестаёт видеть индекс, как только пропадает `search_index_state` (проверка раз в 10 с на процесс)
    # и читает основные таблицы; копии удаляются после указателя и паузы дольше этой проверки.
    op.drop_table("search_index_state")
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute("SELECT pg_sleep(15)")
    for copy in _COPIES:
        op.drop_table(f"search_subnational_facts_{copy}")
        op.drop_table(f"search_region_facts_{copy}")
        op.drop_table(f"search_russia_{copy}")
        op.drop_table(f"search_world_{copy}")

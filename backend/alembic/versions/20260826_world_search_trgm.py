"""pg_trgm GIN индекс текстовых колонок мирового поиска.

Revision ID: 20260826_world_search_trgm
Revises: 20260806_world_forecasts
Create Date: 2026-08-27

/world/search фильтрует ILIKE '%q%' по code/name_ru/name_en/seo_keywords.
Без триграммного индекса это Seq Scan всей world_indicators (~1.1 с на 250k
строк); GIN gin_trgm_ops по этим четырём колонкам даёт BitmapOr-план (десятки
мс). Индекс живёт именно на сырых колонках: SQLAlchemy `ilike()` компилится в
`col ILIKE`, без lower() — выражение с lower() планировщик не подхватывает.
Межтабличный OR (ряды + поля страны) одним запросом planner всё равно уводит
в Seq Scan, поэтому сам запрос разбит на два (см. docstring search_world).
Индекс и расширение создаются IF NOT EXISTS — идемпотентно; расширение не
удаляем при откате, им могут пользоваться другие объекты БД.
"""

from alembic import op

revision = "20260826_world_search_trgm"
down_revision = "20260806_world_forecasts"
branch_labels = None
depends_on = None

_INDEX_NAME = "ix_world_indicators_search_text_trgm"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        f"""
        CREATE INDEX IF NOT EXISTS {_INDEX_NAME}
        ON world_indicators
        USING gin (
            code gin_trgm_ops,
            name_ru gin_trgm_ops,
            name_en gin_trgm_ops,
            seo_keywords gin_trgm_ops
        )
        """
    )


def downgrade() -> None:
    op.drop_index(_INDEX_NAME, table_name="world_indicators")

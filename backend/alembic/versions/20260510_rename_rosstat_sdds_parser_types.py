"""rename rosstat_sdds_* parser_types → rosstat_* (ADR-0004 cleanup)

Revision ID: 20260510_rename_sdds
Revises: 20260506_indicator_seo_kw
Create Date: 2026-05-10

Контекст: ADR-0004 завершил миграцию всех Росстат-индикаторов с SDDS-английского
зеркала (`eng.rosstat.gov.ru`) на canonical русские источники (`rosstat.gov.ru`).
SDDS-fetcher (`fetch_sdds_xlsx`, `DATASET_URLS`) и SDDS-ветка `parse_gdp_xlsx`
удалены из кода. Class-level `parser_type` ClassVar в 5 парсерах переименованы:

  rosstat_sdds_gdp      → rosstat_gdp
  rosstat_sdds_labor    → rosstat_labor
  rosstat_sdds_ipi      → rosstat_ipi
  rosstat_sdds_ppi      → rosstat_ppi
  rosstat_sdds_housing  → rosstat_housing

`seed_data.py` обновлён synchronously и при следующем upsert обновит
`indicators.parser_type` через `on_conflict_do_update`. Эта миграция —
defensive belt-and-braces: применяет тот же rename напрямую к таблице,
чтобы prod был корректным даже если seed_data по какой-то причине не
выполнится первым.

Идемпотентна (UPDATE ... WHERE parser_type = '<old>' — повторный запуск no-op).
"""
from alembic import op


revision = "20260510_rename_sdds"
down_revision = "20260506_indicator_seo_kw"
branch_labels = None
depends_on = None


_RENAMES = [
    ("rosstat_sdds_gdp", "rosstat_gdp"),
    ("rosstat_sdds_labor", "rosstat_labor"),
    ("rosstat_sdds_ipi", "rosstat_ipi"),
    ("rosstat_sdds_ppi", "rosstat_ppi"),
    ("rosstat_sdds_housing", "rosstat_housing"),
]


def upgrade() -> None:
    for old, new in _RENAMES:
        op.execute(
            f"UPDATE indicators SET parser_type = '{new}' "
            f"WHERE parser_type = '{old}'"
        )


def downgrade() -> None:
    for old, new in _RENAMES:
        op.execute(
            f"UPDATE indicators SET parser_type = '{old}' "
            f"WHERE parser_type = '{new}'"
        )

"""П-3 + П-7 (CTO-аудит 2026-07-06): наблюдаемость ревизий и индекс прогнозов.

- fetch_log.records_updated — ревизии источника (in-place value change) видны
  отдельно от добавлений; нужны для точного `updated_codes` (инкрементальный
  derived-пересчёт, П-2) и для диагностики «тихих ревизий» Росстата.
- ix_forecast_values_forecast_date — чтение прогноза карточкой идёт
  по (forecast_id, date); без индекса — seq scan по растущей таблице.
- seed_state — key-value для seed_schema_hash (П-12): entrypoint пропускает
  полный seed+CE-refresh+retrain, если desired-state payload не менялся
  (риск Р-3: хэшируется сам payload, не список файлов; FORCE_SEED=1 — обход).

Всё аддитивно.

Revision ID: 20260706_etl_perf
Revises: 20260706_analytics2
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa

revision = "20260706_etl_perf"
down_revision = "20260706_analytics2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "fetch_log",
        sa.Column("records_updated", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_forecast_values_forecast_date",
        "forecast_values",
        ["forecast_id", "date"],
    )
    op.create_table(
        "seed_state",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("seed_state")
    op.drop_index("ix_forecast_values_forecast_date", table_name="forecast_values")
    op.drop_column("fetch_log", "records_updated")

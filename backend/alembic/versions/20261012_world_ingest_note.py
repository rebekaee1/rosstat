"""Журнал загрузки Евростата: пояснение события набора (смена базы индекса).

Revision ID: 20261012_world_ingest_note
Revises: 20261012c_world_listed_cnt

Только добавляющая миграция: одна nullable-колонка. Старый код её не читает, новый
пишет в неё события вроде «смена базы индекса I15→I21: перенесено на месте 450».
"""
from alembic import op
import sqlalchemy as sa

revision = "20261012_world_ingest_note"
down_revision = "20261012c_world_listed_cnt"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE world_ingest_dataset_logs ADD COLUMN IF NOT EXISTS note TEXT"
    )


def downgrade():
    op.execute("ALTER TABLE world_ingest_dataset_logs DROP COLUMN IF EXISTS note")

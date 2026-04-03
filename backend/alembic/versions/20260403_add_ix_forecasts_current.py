"""add partial index on forecasts.is_current

Revision ID: a3f7c8d91e02
Revises: 20260320_add_ix_indicators_category
Create Date: 2026-04-03
"""
from alembic import op

revision = "a3f7c8d91e02"
down_revision = "b3c1d2e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_forecasts_indicator_current",
        "forecasts",
        ["indicator_id"],
        postgresql_where="is_current = true",
    )


def downgrade() -> None:
    op.drop_index("ix_forecasts_indicator_current", table_name="forecasts")

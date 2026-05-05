"""indicator metadata: seo_title, seo_description, seo_blocks, is_listed

Revision ID: 20260505_indicator_seo
Revises: 20260428_analytics_os
Create Date: 2026-05-05

Goal: consolidate indicator editorial content (SEO title/description, extra
SEO blocks, listing visibility) into the Indicator table, so any text edit
becomes a UPDATE statement instead of a multi-file code change.

This migration is purely additive — only ADD COLUMN, no DROP. Existing data
is untouched. Backfill of values from the historical SEO_MAP / INDICATOR_BLOCKS
/ HIDDEN_FROM_LISTING constants happens in `seed_data.py` (idempotent UPDATE).
"""
from alembic import op
import sqlalchemy as sa


revision = "20260505_indicator_seo"
down_revision = "20260428_analytics_os"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "indicators",
        sa.Column("seo_title", sa.String(300), nullable=True),
    )
    op.add_column(
        "indicators",
        sa.Column("seo_description", sa.Text(), nullable=True),
    )
    op.add_column(
        "indicators",
        sa.Column("seo_blocks", sa.JSON(), nullable=True),
    )
    op.add_column(
        "indicators",
        sa.Column(
            "is_listed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("indicators", "is_listed")
    op.drop_column("indicators", "seo_blocks")
    op.drop_column("indicators", "seo_description")
    op.drop_column("indicators", "seo_title")

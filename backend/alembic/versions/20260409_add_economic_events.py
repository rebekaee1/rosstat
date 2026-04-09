"""add economic_events table

Revision ID: 20260409_events
Revises: 20260403_add_ix_forecasts_current
Create Date: 2026-04-09
"""
from alembic import op
import sqlalchemy as sa

revision = "20260409_events"
down_revision = "a3f7c8d91e02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "economic_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("title_en", sa.String(300), nullable=True),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("indicator_id", sa.Integer(),
                  sa.ForeignKey("indicators.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column("scheduled_time", sa.String(5), nullable=True),
        sa.Column("is_estimated", sa.Boolean(), server_default="false"),
        sa.Column("actual_date", sa.Date(), nullable=True),
        sa.Column("reference_period", sa.String(80), nullable=True),
        sa.Column("importance", sa.Integer(), server_default="2"),
        sa.Column("previous_value", sa.String(50), nullable=True),
        sa.Column("forecast_value", sa.String(50), nullable=True),
        sa.Column("actual_value", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), server_default="scheduled"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("source", "event_type", "scheduled_date", "indicator_id",
                            name="uq_event_natural_key"),
    )
    op.create_index("ix_event_scheduled", "economic_events", ["scheduled_date"])
    op.create_index("ix_event_source", "economic_events", ["source"])
    op.create_index("ix_event_upcoming", "economic_events", ["scheduled_date", "importance"])


def downgrade() -> None:
    op.drop_index("ix_event_upcoming", table_name="economic_events")
    op.drop_index("ix_event_source", table_name="economic_events")
    op.drop_index("ix_event_scheduled", table_name="economic_events")
    op.drop_table("economic_events")

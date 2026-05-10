"""add official calendar provenance fields

Revision ID: 20260510_calendar_official
Revises: 20260510_rename_sdds
Create Date: 2026-05-10
"""
from alembic import op
import sqlalchemy as sa


revision = "20260510_calendar_official"
down_revision = "20260510_rename_sdds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("economic_events", sa.Column("event_key", sa.String(200), nullable=True))
    op.add_column(
        "economic_events",
        sa.Column("date_confidence", sa.String(30), nullable=False, server_default="estimated"),
    )
    op.add_column("economic_events", sa.Column("source_event_uid", sa.String(300), nullable=True))
    op.add_column("economic_events", sa.Column("source_hash", sa.String(64), nullable=True))
    op.add_column("economic_events", sa.Column("last_seen_at", sa.DateTime(), nullable=True))

    op.execute(
        """
        UPDATE economic_events
        SET date_confidence = CASE
            WHEN is_estimated IS TRUE THEN 'estimated'
            ELSE 'official_explicit'
        END
        WHERE date_confidence IS NULL OR date_confidence = 'estimated'
        """
    )
    op.create_unique_constraint(
        "uq_event_stable_key",
        "economic_events",
        ["source", "event_type", "event_key"],
    )
    op.create_index("ix_event_confidence", "economic_events", ["date_confidence"])


def downgrade() -> None:
    op.drop_index("ix_event_confidence", table_name="economic_events")
    op.drop_constraint("uq_event_stable_key", "economic_events", type_="unique")
    op.drop_column("economic_events", "last_seen_at")
    op.drop_column("economic_events", "source_hash")
    op.drop_column("economic_events", "source_event_uid")
    op.drop_column("economic_events", "date_confidence")
    op.drop_column("economic_events", "event_key")

"""behavior_events — сырой поведенческий поток (behavior.js autocapture).

Revision ID: 20260703_behavior
Revises: 20260702_fe_audience
Create Date: 2026-07-03
"""
from alembic import op
import sqlalchemy as sa

revision = "20260703_behavior"
down_revision = "20260702_fe_audience"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "behavior_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column("session_id_hash", sa.String(length=80), nullable=True),
        sa.Column("page_load_id", sa.String(length=40), nullable=True),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("authed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("page", sa.String(length=500), nullable=True),
        sa.Column("element_path", sa.String(length=400), nullable=True),
        sa.Column("element_text", sa.String(length=120), nullable=True),
        sa.Column("x", sa.Integer(), nullable=True),
        sa.Column("y", sa.Integer(), nullable=True),
        sa.Column("is_dead", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_rage", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("params_json", sa.JSON(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("ingested_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_behavior_type_time", "behavior_events", ["event_type", "occurred_at"])
    op.create_index("ix_behavior_page_time", "behavior_events", ["page", "occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_behavior_page_time", table_name="behavior_events")
    op.drop_index("ix_behavior_type_time", table_name="behavior_events")
    op.drop_table("behavior_events")

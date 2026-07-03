"""hypotheses — булев слой знаний поверх собранных данных (Пульс-LLM).

Revision ID: 20260703_hypotheses
Revises: 20260703_behavior
Create Date: 2026-07-03
"""
from alembic import op
import sqlalchemy as sa


revision = "20260703_hypotheses"
down_revision = "20260703_behavior"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hypotheses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("statement", sa.String(length=500), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("verdict", sa.Boolean(), nullable=True),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="pulse_llm"),
        sa.Column("evidence_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_hypothesis_verdict", "hypotheses", ["verdict", "updated_at"])


def downgrade() -> None:
    op.drop_index("ix_hypothesis_verdict", table_name="hypotheses")
    op.drop_table("hypotheses")

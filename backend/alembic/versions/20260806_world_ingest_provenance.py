"""World Eurostat delta ingest state and provenance.

Revision ID: 20260806_world_ingest
Revises: 20260727_world
Create Date: 2026-08-06

Eurostat is an isolated bounded context.  Its loader must not reuse FetchLog
or the Russian ETL lifecycle: TOC versions, quarantine and per-dataset
reconciliation belong to world_* tables.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260806_world_ingest"
down_revision = "20260727_world"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "world_dataset_state",
        sa.Column("dataset_id", sa.String(length=80), primary_key=True),
        sa.Column("last_update_of_data", sa.Date(), nullable=True),
        sa.Column("last_structure_change", sa.Date(), nullable=True),
        sa.Column("last_slice_hash", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ok"),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
    )
    op.create_table(
        "world_ingest_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="eurostat"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="running"),
        sa.Column("is_shadow", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("datasets_selected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("datasets_succeeded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("datasets_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_world_ingest_runs_started", "world_ingest_runs", ["started_at"])
    op.create_table(
        "world_ingest_dataset_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("world_ingest_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("dataset_id", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source_updated_at", sa.Date(), nullable=True),
        sa.Column("structure_changed_at", sa.Date(), nullable=True),
        sa.Column("slice_hash", sa.String(length=64), nullable=True),
        sa.Column("rows_fetched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_removed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.UniqueConstraint("run_id", "dataset_id", name="uq_world_ingest_run_dataset"),
    )
    op.create_index(
        "ix_world_ingest_dataset_log_dataset",
        "world_ingest_dataset_logs",
        ["dataset_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_world_ingest_dataset_log_dataset", table_name="world_ingest_dataset_logs")
    op.drop_table("world_ingest_dataset_logs")
    op.drop_index("ix_world_ingest_runs_started", table_name="world_ingest_runs")
    op.drop_table("world_ingest_runs")
    op.drop_table("world_dataset_state")

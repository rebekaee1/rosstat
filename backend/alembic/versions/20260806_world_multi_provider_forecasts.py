"""World multi-provider identity and quality-gated forecasts.

Revision ID: 20260806_world_forecasts
Revises: 20260806_world_ingest
Create Date: 2026-08-06
"""

from alembic import op
import sqlalchemy as sa


revision = "20260806_world_forecasts"
down_revision = "20260806_world_ingest"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "world_indicators",
        sa.Column(
            "provider",
            sa.String(length=50),
            nullable=False,
            server_default="eurostat",
        ),
    )
    op.alter_column(
        "world_indicators",
        "dataset_id",
        existing_type=sa.String(length=80),
        type_=sa.String(length=160),
        existing_nullable=False,
    )
    op.drop_constraint("uq_world_ind_slice", "world_indicators", type_="unique")
    op.create_unique_constraint(
        "uq_world_ind_provider_slice",
        "world_indicators",
        ["provider", "country_id", "dataset_id", "slice_hash"],
    )
    op.create_index(
        "ix_world_indicators_provider_dataset",
        "world_indicators",
        ["provider", "dataset_id"],
    )

    op.add_column(
        "world_dataset_state",
        sa.Column(
            "provider",
            sa.String(length=50),
            nullable=False,
            server_default="eurostat",
        ),
    )
    op.alter_column(
        "world_dataset_state",
        "dataset_id",
        existing_type=sa.String(length=80),
        type_=sa.String(length=160),
        existing_nullable=False,
    )
    op.drop_constraint("world_dataset_state_pkey", "world_dataset_state", type_="primary")
    op.create_primary_key(
        "pk_world_dataset_state",
        "world_dataset_state",
        ["provider", "dataset_id"],
    )

    op.add_column(
        "world_ingest_dataset_logs",
        sa.Column(
            "provider",
            sa.String(length=50),
            nullable=False,
            server_default="eurostat",
        ),
    )
    op.alter_column(
        "world_ingest_dataset_logs",
        "dataset_id",
        existing_type=sa.String(length=80),
        type_=sa.String(length=160),
        existing_nullable=False,
    )
    op.drop_constraint(
        "uq_world_ingest_run_dataset",
        "world_ingest_dataset_logs",
        type_="unique",
    )
    op.drop_index(
        "ix_world_ingest_dataset_log_dataset",
        table_name="world_ingest_dataset_logs",
    )
    op.create_unique_constraint(
        "uq_world_ingest_run_provider_dataset",
        "world_ingest_dataset_logs",
        ["run_id", "provider", "dataset_id"],
    )
    op.create_index(
        "ix_world_ingest_dataset_log_provider_dataset",
        "world_ingest_dataset_logs",
        ["provider", "dataset_id", "status"],
    )

    op.create_table(
        "world_forecasts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "world_indicator_id",
            sa.Integer(),
            sa.ForeignKey("world_indicators.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("strategy", sa.String(length=50), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("model_params", sa.JSON(), nullable=True),
        sa.Column("gate_status", sa.String(length=20), nullable=False),
        sa.Column("gate_reason", sa.String(length=300), nullable=True),
        sa.Column("mase", sa.Numeric(12, 6), nullable=True),
        sa.Column("baseline_mase", sa.Numeric(12, 6), nullable=True),
        sa.Column("origins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("horizon", sa.Integer(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_world_forecasts_indicator_current",
        "world_forecasts",
        ["world_indicator_id"],
        postgresql_where=sa.text("is_current = true"),
    )
    op.create_index(
        "ix_world_forecasts_gate_created",
        "world_forecasts",
        ["gate_status", "created_at"],
    )

    op.create_table(
        "world_forecast_values",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "forecast_id",
            sa.Integer(),
            sa.ForeignKey("world_forecasts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(20, 6), nullable=False),
        sa.Column("lower_bound", sa.Numeric(20, 6), nullable=True),
        sa.Column("upper_bound", sa.Numeric(20, 6), nullable=True),
        sa.UniqueConstraint("forecast_id", "date", name="uq_world_forecast_value"),
    )
    op.create_index(
        "ix_world_forecast_values_forecast_date",
        "world_forecast_values",
        ["forecast_id", "date"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_world_forecast_values_forecast_date",
        table_name="world_forecast_values",
    )
    op.drop_table("world_forecast_values")
    op.drop_index("ix_world_forecasts_gate_created", table_name="world_forecasts")
    op.drop_index(
        "ix_world_forecasts_indicator_current",
        table_name="world_forecasts",
    )
    op.drop_table("world_forecasts")

    op.drop_index(
        "ix_world_ingest_dataset_log_provider_dataset",
        table_name="world_ingest_dataset_logs",
    )
    op.drop_constraint(
        "uq_world_ingest_run_provider_dataset",
        "world_ingest_dataset_logs",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_world_ingest_run_dataset",
        "world_ingest_dataset_logs",
        ["run_id", "dataset_id"],
    )
    op.create_index(
        "ix_world_ingest_dataset_log_dataset",
        "world_ingest_dataset_logs",
        ["dataset_id", "status"],
    )
    op.drop_column("world_ingest_dataset_logs", "provider")
    op.alter_column(
        "world_ingest_dataset_logs",
        "dataset_id",
        existing_type=sa.String(length=160),
        type_=sa.String(length=80),
        existing_nullable=False,
    )

    op.drop_constraint("pk_world_dataset_state", "world_dataset_state", type_="primary")
    op.create_primary_key(
        "world_dataset_state_pkey",
        "world_dataset_state",
        ["dataset_id"],
    )
    op.drop_column("world_dataset_state", "provider")
    op.alter_column(
        "world_dataset_state",
        "dataset_id",
        existing_type=sa.String(length=160),
        type_=sa.String(length=80),
        existing_nullable=False,
    )

    op.drop_index(
        "ix_world_indicators_provider_dataset",
        table_name="world_indicators",
    )
    op.drop_constraint(
        "uq_world_ind_provider_slice",
        "world_indicators",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_world_ind_slice",
        "world_indicators",
        ["country_id", "dataset_id", "slice_hash"],
    )
    op.drop_column("world_indicators", "provider")
    op.alter_column(
        "world_indicators",
        "dataset_id",
        existing_type=sa.String(length=160),
        type_=sa.String(length=80),
        existing_nullable=False,
    )

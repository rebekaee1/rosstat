"""world bounded context: world_countries / world_indicators / world_data_points

Revision ID: 20260727_world
Revises: 20260713_partner_rev
Create Date: 2026-07-27

Мировой блок на данных Eurostat — отдельный bounded context по образцу ADR-0008.
Не пересекается с indicators / indicator_data / regions.
Прогнозы намеренно отсутствуют.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260727_world"
down_revision = "20260713_partner_rev"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "world_countries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=8), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name_ru", sa.String(length=150), nullable=False),
        sa.Column("name_en", sa.String(length=150), nullable=False),
        sa.Column("region_ru", sa.String(length=80), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_world_countries_code", "world_countries", ["code"], unique=True)
    op.create_index("ix_world_countries_slug", "world_countries", ["slug"], unique=True)

    op.create_table(
        "world_indicators",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "country_id",
            sa.Integer(),
            sa.ForeignKey("world_countries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("dataset_id", sa.String(length=80), nullable=False),
        sa.Column("slice_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("slice_hash", sa.String(length=64), nullable=False),
        sa.Column("name_ru", sa.String(length=400), nullable=False),
        sa.Column("name_en", sa.String(length=400), nullable=True),
        sa.Column("name_quality", sa.String(length=20), nullable=False, server_default="raw"),
        sa.Column("unit", sa.String(length=80), nullable=False),
        sa.Column("unit_ru", sa.String(length=80), nullable=False),
        sa.Column("frequency", sa.String(length=20), nullable=False),
        sa.Column("category_ru", sa.String(length=80), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("methodology", sa.Text(), nullable=True),
        sa.Column("history_start", sa.Date(), nullable=True),
        sa.Column("history_end", sa.Date(), nullable=True),
        sa.Column("points_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_listed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("seo_title", sa.String(length=300), nullable=True),
        sa.Column("seo_description", sa.Text(), nullable=True),
        sa.Column("seo_keywords", sa.Text(), nullable=True),
        sa.UniqueConstraint(
            "country_id", "dataset_id", "slice_hash", name="uq_world_ind_slice"
        ),
    )
    op.create_index("ix_world_indicators_code", "world_indicators", ["code"], unique=True)
    op.create_index("ix_world_indicators_dataset_id", "world_indicators", ["dataset_id"])
    op.create_index(
        "ix_world_indicators_country_category",
        "world_indicators",
        ["country_id", "category_ru"],
    )

    op.create_table(
        "world_data_points",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "indicator_id",
            sa.Integer(),
            sa.ForeignKey("world_indicators.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(20, 6), nullable=False),
        sa.UniqueConstraint("indicator_id", "date", name="uq_world_data_point"),
    )
    op.create_index(
        "ix_world_data_points_indicator_date",
        "world_data_points",
        ["indicator_id", "date"],
    )


def downgrade() -> None:
    op.drop_table("world_data_points")
    op.drop_table("world_indicators")
    op.drop_table("world_countries")

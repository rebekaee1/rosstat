"""Субнациональный bounded context: штаты / земли / провинции (ADR-0014).

Revision ID: 20260920_subnational
Revises: 20260904_world_card_lookup_idx
Create Date: 2026-09-20

Отдельные таблицы для любой страны кроме России. Российский региональный
контекст (ADR-0008) не расширяем: там годовой сборник, здесь — ряды
месячной / квартальной / годовой частоты с официальных первоисточников.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260920_subnational"
down_revision = "20260904_world_card_lookup_idx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subnational_regions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("country_code", sa.String(length=8), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name_en", sa.String(length=150), nullable=False),
        sa.Column("name_ru", sa.String(length=150), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("geo_code", sa.String(length=16), nullable=False),
        sa.Column("fips", sa.String(length=8), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.UniqueConstraint("country_code", "slug", name="uq_subnational_region_country_slug"),
    )
    op.create_index("ix_subnational_regions_country", "subnational_regions", ["country_code"])

    op.create_table(
        "subnational_indicators",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("country_code", sa.String(length=8), nullable=False),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("name_en", sa.String(length=400), nullable=False),
        sa.Column("name_ru", sa.String(length=400), nullable=False),
        sa.Column("unit", sa.String(length=80), nullable=False),
        sa.Column("unit_ru", sa.String(length=80), nullable=False),
        sa.Column("unit_en", sa.String(length=80), nullable=False),
        sa.Column("frequency", sa.String(length=20), nullable=False),
        sa.Column("section_en", sa.String(length=80), nullable=False),
        sa.Column("section_ru", sa.String(length=80), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("series_template", sa.String(length=160), nullable=False),
        sa.Column("aggregation", sa.String(length=20), nullable=False),
        sa.Column("description_en", sa.Text(), nullable=True),
        sa.Column("description_ru", sa.Text(), nullable=True),
        sa.Column("methodology_en", sa.Text(), nullable=True),
        sa.Column("methodology_ru", sa.Text(), nullable=True),
        sa.Column("source_en", sa.String(length=120), nullable=False),
        sa.Column("source_ru", sa.String(length=120), nullable=False),
        sa.Column("source_url_template", sa.String(length=500), nullable=True),
        sa.Column("is_listed", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("national_code", sa.String(length=120), nullable=True),
        sa.Column("better_is_low", sa.Boolean(), nullable=False, server_default="false"),
        sa.UniqueConstraint("country_code", "code", name="uq_subnational_indicator_country_code"),
    )
    op.create_index("ix_subnational_indicators_country", "subnational_indicators", ["country_code"])

    op.create_table(
        "subnational_data_points",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "indicator_id",
            sa.Integer(),
            sa.ForeignKey("subnational_indicators.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "region_id",
            sa.Integer(),
            sa.ForeignKey("subnational_regions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(20, 6), nullable=False),
        sa.UniqueConstraint(
            "indicator_id", "region_id", "period",
            name="uq_subnational_data_point",
        ),
    )
    op.create_index(
        "ix_subnational_data_indicator_period",
        "subnational_data_points",
        ["indicator_id", "period"],
    )
    op.create_index("ix_subnational_data_region", "subnational_data_points", ["region_id"])
    op.create_index(
        "ix_subnational_data_region_indicator_period",
        "subnational_data_points",
        ["region_id", "indicator_id", "period"],
    )


def downgrade() -> None:
    op.drop_table("subnational_data_points")
    op.drop_table("subnational_indicators")
    op.drop_table("subnational_regions")

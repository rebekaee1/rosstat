"""regional bounded context: regions / region_indicators / region_data (ADR-0008)

Revision ID: 20260702_regional
Revises: 20260619_oauth_phone
Create Date: 2026-07-02

Годовые ряды «Регионы России. Социально-экономические показатели» (Росстат):
96 территориальных строк (85 субъектов + РФ + 8 ФО + 2 статостатка),
~460 показателей, ~900 тыс. точек. Отдельные таблицы — не смешивать с
федеральной парой indicators/indicator_data.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260702_regional"
down_revision = "20260619_oauth_phone"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "regions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("district_slug", sa.String(length=80), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
    )
    op.create_index("ix_regions_slug", "regions", ["slug"], unique=True)
    op.create_index("ix_regions_district_slug", "regions", ["district_slug"])

    op.create_table(
        "region_indicators",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("table_code", sa.String(length=20), nullable=False),
        sa.Column("section_num", sa.Integer(), nullable=False),
        sa.Column("section_name", sa.String(length=150), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("unit", sa.String(length=120), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("source_note", sa.String(length=200), nullable=True),
        sa.Column("year_min", sa.Integer(), nullable=True),
        sa.Column("year_max", sa.Integer(), nullable=True),
        sa.Column("is_listed", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.create_index("ix_region_indicators_code", "region_indicators", ["code"], unique=True)
    op.create_index("ix_region_indicators_section_num", "region_indicators", ["section_num"])

    op.create_table(
        "region_data",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "indicator_id",
            sa.Integer(),
            sa.ForeignKey("region_indicators.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "region_id",
            sa.Integer(),
            sa.ForeignKey("regions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("value", sa.Numeric(18, 4), nullable=False),
        sa.UniqueConstraint("indicator_id", "region_id", "year", name="uq_region_data_point"),
    )
    op.create_index("ix_region_data_indicator_year", "region_data", ["indicator_id", "year"])
    op.create_index("ix_region_data_region", "region_data", ["region_id"])


def downgrade() -> None:
    op.drop_table("region_data")
    op.drop_table("region_indicators")
    op.drop_table("regions")

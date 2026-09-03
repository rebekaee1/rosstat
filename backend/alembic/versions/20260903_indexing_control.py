"""Ежедневный снимок индексации Вебмастера + GSC search queries.

Revision ID: 20260903_indexing_control
Revises: 20260827_region_monthly_points
Create Date: 2026-09-03
"""
import sqlalchemy as sa
from alembic import op


revision = "20260903_indexing_control"
down_revision = "20260827_region_monthly_points"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webmaster_indexing_daily",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("host", sa.String(300), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("in_search", sa.Integer(), nullable=True),
        sa.Column("crawled_2xx", sa.Integer(), nullable=True),
        sa.Column("crawled_3xx", sa.Integer(), nullable=True),
        sa.Column("crawled_4xx", sa.Integer(), nullable=True),
        sa.Column("crawled_5xx", sa.Integer(), nullable=True),
        sa.Column("appeared", sa.Integer(), nullable=True),
        sa.Column("excluded", sa.Integer(), nullable=True),
        sa.Column("sitemap_errors", sa.Integer(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("host", "day", name="uq_webmaster_indexing_daily"),
    )
    op.create_index(
        "ix_webmaster_indexing_daily_day",
        "webmaster_indexing_daily",
        ["day"],
    )
    op.create_table(
        "gsc_search_queries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("query", sa.String(500), nullable=False),
        sa.Column("page", sa.String(1000), nullable=True),
        sa.Column("impressions", sa.Integer(), nullable=True),
        sa.Column("clicks", sa.Integer(), nullable=True),
        sa.Column("ctr", sa.Numeric(8, 4), nullable=True),
        sa.Column("position", sa.Numeric(8, 2), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("date", "query", "page", name="uq_gsc_search_query"),
    )
    op.create_index("ix_gsc_query_date", "gsc_search_queries", ["date", "query"])


def downgrade() -> None:
    op.drop_index("ix_gsc_query_date", table_name="gsc_search_queries")
    op.drop_table("gsc_search_queries")
    op.drop_index(
        "ix_webmaster_indexing_daily_day", table_name="webmaster_indexing_daily"
    )
    op.drop_table("webmaster_indexing_daily")

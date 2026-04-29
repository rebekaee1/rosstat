"""add analytics os tables

Revision ID: 20260428_analytics_os
Revises: 20260409_events
Create Date: 2026-04-28
"""
from alembic import op
import sqlalchemy as sa


revision = "20260428_analytics_os"
down_revision = "20260409_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analytics_sync_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("job_type", sa.String(80), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=True),
        sa.Column("date_to", sa.Date(), nullable=True),
        sa.Column("request_hash", sa.String(80), nullable=True),
        sa.Column("records_processed", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_analytics_sync_runs_source", "analytics_sync_runs", ["source", "status"])
    op.create_index("ix_analytics_sync_runs_started", "analytics_sync_runs", ["started_at"])

    op.create_table(
        "analytics_watermarks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("resource_key", sa.String(150), nullable=False),
        sa.Column("last_success_date", sa.Date(), nullable=True),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("source", "resource_key", name="uq_analytics_watermark"),
    )

    op.create_table(
        "metrika_counter_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("counter_id", sa.String(30), nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("site", sa.String(300), nullable=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("permission", sa.String(50), nullable=True),
        sa.Column("webvisor_enabled", sa.Boolean(), nullable=True),
        sa.Column("ecommerce_enabled", sa.Boolean(), nullable=True),
        sa.Column("clickmap_enabled", sa.Boolean(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_metrika_counter_snapshots_counter", "metrika_counter_snapshots", ["counter_id", "captured_at"])

    op.create_table(
        "metrika_goal_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("counter_id", sa.String(30), nullable=False),
        sa.Column("goal_id", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("goal_type", sa.String(80), nullable=True),
        sa.Column("is_favorite", sa.Boolean(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("counter_id", "goal_id", "captured_at", name="uq_metrika_goal_snapshot"),
    )
    op.create_index("ix_metrika_goal_counter", "metrika_goal_snapshots", ["counter_id", "goal_id"])

    op.create_table(
        "metrika_report_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("counter_id", sa.String(30), nullable=False),
        sa.Column("report_type", sa.String(80), nullable=False),
        sa.Column("query_hash", sa.String(80), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=True),
        sa.Column("date_to", sa.Date(), nullable=True),
        sa.Column("sampled", sa.Boolean(), nullable=True),
        sa.Column("sample_share", sa.Numeric(10, 6), nullable=True),
        sa.Column("contains_sensitive_data", sa.Boolean(), nullable=True),
        sa.Column("query_json", sa.JSON(), nullable=True),
        sa.Column("response_json", sa.JSON(), nullable=True),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("counter_id", "report_type", "query_hash", "date_from", "date_to", name="uq_metrika_report_snapshot"),
    )
    op.create_index("ix_metrika_report_counter_dates", "metrika_report_snapshots", ["counter_id", "date_from", "date_to"])

    op.create_table(
        "metrika_daily_page_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("counter_id", sa.String(30), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("visits", sa.Integer(), nullable=False),
        sa.Column("users", sa.Integer(), nullable=False),
        sa.Column("pageviews", sa.Integer(), nullable=False),
        sa.Column("bounce_rate", sa.Numeric(8, 4), nullable=True),
        sa.Column("depth", sa.Numeric(8, 4), nullable=True),
        sa.Column("avg_duration_seconds", sa.Numeric(12, 2), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("counter_id", "date", "url", "source", name="uq_metrika_daily_page_metric"),
    )
    op.create_index("ix_metrika_daily_page_date", "metrika_daily_page_metrics", ["date", "url"])

    op.create_table(
        "metrika_search_phrases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("counter_id", sa.String(30), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("phrase", sa.String(500), nullable=False),
        sa.Column("landing_url", sa.String(1000), nullable=True),
        sa.Column("search_engine", sa.String(100), nullable=True),
        sa.Column("visits", sa.Integer(), nullable=False),
        sa.Column("users", sa.Integer(), nullable=False),
        sa.Column("bounce_rate", sa.Numeric(8, 4), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("counter_id", "date", "phrase", "landing_url", "search_engine", name="uq_metrika_search_phrase"),
    )
    op.create_index("ix_metrika_search_phrase_date", "metrika_search_phrases", ["date", "phrase"])

    op.create_table(
        "raw_metrika_visits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("counter_id", sa.String(30), nullable=False),
        sa.Column("visit_id", sa.String(100), nullable=False),
        sa.Column("client_id_hash", sa.String(80), nullable=True),
        sa.Column("visit_date", sa.Date(), nullable=True),
        sa.Column("start_time", sa.DateTime(), nullable=True),
        sa.Column("start_url", sa.String(1000), nullable=True),
        sa.Column("referer", sa.String(1000), nullable=True),
        sa.Column("traffic_source", sa.String(100), nullable=True),
        sa.Column("search_engine", sa.String(100), nullable=True),
        sa.Column("search_phrase", sa.String(500), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("goals_json", sa.JSON(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("row_hash", sa.String(80), nullable=False),
        sa.Column("ingested_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("counter_id", "visit_id", name="uq_raw_metrika_visit"),
    )
    op.create_index("ix_raw_metrika_visit_date", "raw_metrika_visits", ["visit_date"])
    op.create_index("ix_raw_metrika_visit_client", "raw_metrika_visits", ["client_id_hash"])

    op.create_table(
        "raw_metrika_hits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("counter_id", sa.String(30), nullable=False),
        sa.Column("hit_id", sa.String(100), nullable=True),
        sa.Column("visit_id", sa.String(100), nullable=True),
        sa.Column("page_view_id", sa.String(100), nullable=True),
        sa.Column("hit_date", sa.Date(), nullable=True),
        sa.Column("event_time", sa.DateTime(), nullable=True),
        sa.Column("url", sa.String(1000), nullable=True),
        sa.Column("referer", sa.String(1000), nullable=True),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("event_name", sa.String(150), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("row_hash", sa.String(80), nullable=False),
        sa.Column("ingested_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("counter_id", "hit_id", "row_hash", name="uq_raw_metrika_hit"),
    )
    op.create_index("ix_raw_metrika_hit_date", "raw_metrika_hits", ["hit_date"])
    op.create_index("ix_raw_metrika_hit_url", "raw_metrika_hits", ["url"])

    op.create_table(
        "webmaster_diagnostics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("host", sa.String(300), nullable=False),
        sa.Column("problem_code", sa.String(150), nullable=False),
        sa.Column("severity", sa.String(50), nullable=True),
        sa.Column("url", sa.String(1000), nullable=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("host", "problem_code", "url", "first_seen_at", name="uq_webmaster_diagnostic"),
    )
    op.create_index("ix_webmaster_diagnostic_host", "webmaster_diagnostics", ["host", "severity"])

    op.create_table(
        "webmaster_search_queries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("host", sa.String(300), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("query", sa.String(500), nullable=False),
        sa.Column("url", sa.String(1000), nullable=True),
        sa.Column("impressions", sa.Integer(), nullable=True),
        sa.Column("clicks", sa.Integer(), nullable=True),
        sa.Column("ctr", sa.Numeric(8, 4), nullable=True),
        sa.Column("position", sa.Numeric(8, 2), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("host", "date", "query", "url", name="uq_webmaster_search_query"),
    )
    op.create_index("ix_webmaster_query_date", "webmaster_search_queries", ["date", "query"])

    op.create_table(
        "seo_page_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("canonical", sa.String(1000), nullable=True),
        sa.Column("h1_count", sa.Integer(), nullable=True),
        sa.Column("json_ld_count", sa.Integer(), nullable=True),
        sa.Column("internal_links_count", sa.Integer(), nullable=True),
        sa.Column("content_hash", sa.String(80), nullable=False),
        sa.Column("facts_json", sa.JSON(), nullable=True),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("url", "content_hash", name="uq_seo_page_snapshot"),
    )
    op.create_index("ix_seo_page_snapshot_url", "seo_page_snapshots", ["url", "captured_at"])

    op.create_table(
        "agent_findings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("finding_type", sa.String(80), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("evidence_json", sa.JSON(), nullable=True),
        sa.Column("affected_urls_json", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_agent_finding_status", "agent_findings", ["status", "priority"])
    op.create_index("ix_agent_finding_created", "agent_findings", ["created_at"])

    op.create_table(
        "agent_action_audit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("action_type", sa.String(100), nullable=False),
        sa.Column("safety_class", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("target_json", sa.JSON(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("diff_json", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("approval_token_hash", sa.String(100), nullable=True),
        sa.Column("response_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("applied_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_agent_action_status", "agent_action_audit", ["status", "safety_class"])
    op.create_index("ix_agent_action_created", "agent_action_audit", ["created_at"])

    op.create_table(
        "frontend_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_name", sa.String(120), nullable=False),
        sa.Column("session_id_hash", sa.String(80), nullable=True),
        sa.Column("url", sa.String(1000), nullable=True),
        sa.Column("referrer", sa.String(1000), nullable=True),
        sa.Column("params_json", sa.JSON(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("ingested_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_frontend_event_name_time", "frontend_events", ["event_name", "occurred_at"])
    op.create_index("ix_frontend_event_url", "frontend_events", ["url"])

    op.create_table(
        "experiments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("variants_json", sa.JSON(), nullable=True),
        sa.Column("traffic_split_json", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("key", name="uq_experiment_key"),
    )


def downgrade() -> None:
    op.drop_table("experiments")
    op.drop_index("ix_frontend_event_url", table_name="frontend_events")
    op.drop_index("ix_frontend_event_name_time", table_name="frontend_events")
    op.drop_table("frontend_events")
    op.drop_index("ix_agent_action_created", table_name="agent_action_audit")
    op.drop_index("ix_agent_action_status", table_name="agent_action_audit")
    op.drop_table("agent_action_audit")
    op.drop_index("ix_agent_finding_created", table_name="agent_findings")
    op.drop_index("ix_agent_finding_status", table_name="agent_findings")
    op.drop_table("agent_findings")
    op.drop_index("ix_seo_page_snapshot_url", table_name="seo_page_snapshots")
    op.drop_table("seo_page_snapshots")
    op.drop_index("ix_webmaster_query_date", table_name="webmaster_search_queries")
    op.drop_table("webmaster_search_queries")
    op.drop_index("ix_webmaster_diagnostic_host", table_name="webmaster_diagnostics")
    op.drop_table("webmaster_diagnostics")
    op.drop_index("ix_raw_metrika_hit_url", table_name="raw_metrika_hits")
    op.drop_index("ix_raw_metrika_hit_date", table_name="raw_metrika_hits")
    op.drop_table("raw_metrika_hits")
    op.drop_index("ix_raw_metrika_visit_client", table_name="raw_metrika_visits")
    op.drop_index("ix_raw_metrika_visit_date", table_name="raw_metrika_visits")
    op.drop_table("raw_metrika_visits")
    op.drop_index("ix_metrika_search_phrase_date", table_name="metrika_search_phrases")
    op.drop_table("metrika_search_phrases")
    op.drop_index("ix_metrika_daily_page_date", table_name="metrika_daily_page_metrics")
    op.drop_table("metrika_daily_page_metrics")
    op.drop_index("ix_metrika_report_counter_dates", table_name="metrika_report_snapshots")
    op.drop_table("metrika_report_snapshots")
    op.drop_index("ix_metrika_goal_counter", table_name="metrika_goal_snapshots")
    op.drop_table("metrika_goal_snapshots")
    op.drop_index("ix_metrika_counter_snapshots_counter", table_name="metrika_counter_snapshots")
    op.drop_table("metrika_counter_snapshots")
    op.drop_table("analytics_watermarks")
    op.drop_index("ix_analytics_sync_runs_started", table_name="analytics_sync_runs")
    op.drop_index("ix_analytics_sync_runs_source", table_name="analytics_sync_runs")
    op.drop_table("analytics_sync_runs")

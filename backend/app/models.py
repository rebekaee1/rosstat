from datetime import date, datetime, timezone
from sqlalchemy import (
    String, Text, Boolean, Integer, Numeric, Date, DateTime,
    ForeignKey, UniqueConstraint, Index, JSON,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Indicator(Base):
    __tablename__ = "indicators"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(200))
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="%")
    frequency: Mapped[str] = mapped_column(String(50), nullable=False, default="monthly")
    source: Mapped[str] = mapped_column(String(100), nullable=False, default="Росстат")
    source_url: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    methodology: Mapped[str | None] = mapped_column(Text)
    parser_type: Mapped[str] = mapped_column(String(50), nullable=False, default="rosstat_cpi_xlsx")
    model_config_json: Mapped[dict | None] = mapped_column("model_config", JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    category: Mapped[str | None] = mapped_column(String(100))
    excel_sheet: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    data_points: Mapped[list["IndicatorData"]] = relationship(back_populates="indicator", cascade="all, delete-orphan")
    forecasts: Mapped[list["Forecast"]] = relationship(back_populates="indicator", cascade="all, delete-orphan")
    fetch_logs: Mapped[list["FetchLog"]] = relationship(back_populates="indicator", cascade="all, delete-orphan")


class IndicatorData(Base):
    __tablename__ = "indicator_data"
    __table_args__ = (
        UniqueConstraint("indicator_id", "date", name="uq_indicator_date"),
        Index("ix_indicator_data_lookup", "indicator_id", "date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    indicator_id: Mapped[int] = mapped_column(ForeignKey("indicators.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    indicator: Mapped["Indicator"] = relationship(back_populates="data_points")


class Forecast(Base):
    __tablename__ = "forecasts"

    id: Mapped[int] = mapped_column(primary_key=True)
    indicator_id: Mapped[int] = mapped_column(ForeignKey("indicators.id", ondelete="CASCADE"), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_params: Mapped[dict | None] = mapped_column(JSON)
    aic: Mapped[float | None] = mapped_column(Numeric(10, 2))
    bic: Mapped[float | None] = mapped_column(Numeric(10, 2))
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    indicator: Mapped["Indicator"] = relationship(back_populates="forecasts")
    values: Mapped[list["ForecastValue"]] = relationship(back_populates="forecast", cascade="all, delete-orphan")


class ForecastValue(Base):
    __tablename__ = "forecast_values"

    id: Mapped[int] = mapped_column(primary_key=True)
    forecast_id: Mapped[int] = mapped_column(ForeignKey("forecasts.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    lower_bound: Mapped[float | None] = mapped_column(Numeric(12, 4))
    upper_bound: Mapped[float | None] = mapped_column(Numeric(12, 4))

    forecast: Mapped["Forecast"] = relationship(back_populates="values")


class EconomicEvent(Base):
    __tablename__ = "economic_events"
    __table_args__ = (
        UniqueConstraint("source", "event_type", "scheduled_date", "indicator_id",
                         name="uq_event_natural_key"),
        Index("ix_event_scheduled", "scheduled_date"),
        Index("ix_event_source", "source"),
        Index("ix_event_upcoming", "scheduled_date", "importance"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    title_en: Mapped[str | None] = mapped_column(String(300))
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    indicator_id: Mapped[int | None] = mapped_column(
        ForeignKey("indicators.id", ondelete="SET NULL"), nullable=True
    )
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    scheduled_time: Mapped[str | None] = mapped_column(String(5))
    is_estimated: Mapped[bool] = mapped_column(Boolean, default=False)
    actual_date: Mapped[date | None] = mapped_column(Date)
    reference_period: Mapped[str | None] = mapped_column(String(80))
    importance: Mapped[int] = mapped_column(Integer, default=2)
    previous_value: Mapped[str | None] = mapped_column(String(50))
    forecast_value: Mapped[str | None] = mapped_column(String(50))
    actual_value: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    description: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(500))
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)

    indicator: Mapped["Indicator | None"] = relationship()


class FetchLog(Base):
    __tablename__ = "fetch_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    indicator_id: Mapped[int] = mapped_column(ForeignKey("indicators.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500))
    records_added: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    indicator: Mapped["Indicator"] = relationship(back_populates="fetch_logs")


class AnalyticsSyncRun(Base):
    __tablename__ = "analytics_sync_runs"
    __table_args__ = (
        Index("ix_analytics_sync_runs_source", "source", "status"),
        Index("ix_analytics_sync_runs_started", "started_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    job_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    date_from: Mapped[date | None] = mapped_column(Date)
    date_to: Mapped[date | None] = mapped_column(Date)
    request_hash: Mapped[str | None] = mapped_column(String(80))
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)


class AnalyticsWatermark(Base):
    __tablename__ = "analytics_watermarks"
    __table_args__ = (
        UniqueConstraint("source", "resource_key", name="uq_analytics_watermark"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_key: Mapped[str] = mapped_column(String(150), nullable=False)
    last_success_date: Mapped[date | None] = mapped_column(Date)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class MetrikaCounterSnapshot(Base):
    __tablename__ = "metrika_counter_snapshots"
    __table_args__ = (
        Index("ix_metrika_counter_snapshots_counter", "counter_id", "captured_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    counter_id: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str | None] = mapped_column(String(200))
    site: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str | None] = mapped_column(String(50))
    permission: Mapped[str | None] = mapped_column(String(50))
    webvisor_enabled: Mapped[bool | None] = mapped_column(Boolean)
    ecommerce_enabled: Mapped[bool | None] = mapped_column(Boolean)
    clickmap_enabled: Mapped[bool | None] = mapped_column(Boolean)
    raw_json: Mapped[dict | None] = mapped_column(JSON)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class MetrikaGoalSnapshot(Base):
    __tablename__ = "metrika_goal_snapshots"
    __table_args__ = (
        UniqueConstraint("counter_id", "goal_id", "captured_at", name="uq_metrika_goal_snapshot"),
        Index("ix_metrika_goal_counter", "counter_id", "goal_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    counter_id: Mapped[str] = mapped_column(String(30), nullable=False)
    goal_id: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str | None] = mapped_column(String(200))
    goal_type: Mapped[str | None] = mapped_column(String(80))
    is_favorite: Mapped[bool | None] = mapped_column(Boolean)
    raw_json: Mapped[dict | None] = mapped_column(JSON)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class MetrikaReportSnapshot(Base):
    __tablename__ = "metrika_report_snapshots"
    __table_args__ = (
        UniqueConstraint("counter_id", "report_type", "query_hash", "date_from", "date_to", name="uq_metrika_report_snapshot"),
        Index("ix_metrika_report_counter_dates", "counter_id", "date_from", "date_to"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    counter_id: Mapped[str] = mapped_column(String(30), nullable=False)
    report_type: Mapped[str] = mapped_column(String(80), nullable=False)
    query_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    date_from: Mapped[date | None] = mapped_column(Date)
    date_to: Mapped[date | None] = mapped_column(Date)
    sampled: Mapped[bool | None] = mapped_column(Boolean)
    sample_share: Mapped[float | None] = mapped_column(Numeric(10, 6))
    contains_sensitive_data: Mapped[bool | None] = mapped_column(Boolean)
    query_json: Mapped[dict | None] = mapped_column(JSON)
    response_json: Mapped[dict | None] = mapped_column(JSON)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class MetrikaDailyPageMetric(Base):
    __tablename__ = "metrika_daily_page_metrics"
    __table_args__ = (
        UniqueConstraint("counter_id", "date", "url", "source", name="uq_metrika_daily_page_metric"),
        Index("ix_metrika_daily_page_date", "date", "url"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    counter_id: Mapped[str] = mapped_column(String(30), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    source: Mapped[str | None] = mapped_column(String(100))
    visits: Mapped[int] = mapped_column(Integer, default=0)
    users: Mapped[int] = mapped_column(Integer, default=0)
    pageviews: Mapped[int] = mapped_column(Integer, default=0)
    bounce_rate: Mapped[float | None] = mapped_column(Numeric(8, 4))
    depth: Mapped[float | None] = mapped_column(Numeric(8, 4))
    avg_duration_seconds: Mapped[float | None] = mapped_column(Numeric(12, 2))
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class MetrikaSearchPhrase(Base):
    __tablename__ = "metrika_search_phrases"
    __table_args__ = (
        UniqueConstraint("counter_id", "date", "phrase", "landing_url", "search_engine", name="uq_metrika_search_phrase"),
        Index("ix_metrika_search_phrase_date", "date", "phrase"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    counter_id: Mapped[str] = mapped_column(String(30), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    phrase: Mapped[str] = mapped_column(String(500), nullable=False)
    landing_url: Mapped[str | None] = mapped_column(String(1000))
    search_engine: Mapped[str | None] = mapped_column(String(100))
    visits: Mapped[int] = mapped_column(Integer, default=0)
    users: Mapped[int] = mapped_column(Integer, default=0)
    bounce_rate: Mapped[float | None] = mapped_column(Numeric(8, 4))
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class RawMetrikaVisit(Base):
    __tablename__ = "raw_metrika_visits"
    __table_args__ = (
        UniqueConstraint("counter_id", "visit_id", name="uq_raw_metrika_visit"),
        Index("ix_raw_metrika_visit_date", "visit_date"),
        Index("ix_raw_metrika_visit_client", "client_id_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    counter_id: Mapped[str] = mapped_column(String(30), nullable=False)
    visit_id: Mapped[str] = mapped_column(String(100), nullable=False)
    client_id_hash: Mapped[str | None] = mapped_column(String(80))
    visit_date: Mapped[date | None] = mapped_column(Date)
    start_time: Mapped[datetime | None] = mapped_column(DateTime)
    start_url: Mapped[str | None] = mapped_column(String(1000))
    referer: Mapped[str | None] = mapped_column(String(1000))
    traffic_source: Mapped[str | None] = mapped_column(String(100))
    search_engine: Mapped[str | None] = mapped_column(String(100))
    search_phrase: Mapped[str | None] = mapped_column(String(500))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    goals_json: Mapped[dict | None] = mapped_column(JSON)
    raw_json: Mapped[dict | None] = mapped_column(JSON)
    row_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class RawMetrikaHit(Base):
    __tablename__ = "raw_metrika_hits"
    __table_args__ = (
        UniqueConstraint("counter_id", "hit_id", "row_hash", name="uq_raw_metrika_hit"),
        Index("ix_raw_metrika_hit_date", "hit_date"),
        Index("ix_raw_metrika_hit_url", "url"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    counter_id: Mapped[str] = mapped_column(String(30), nullable=False)
    hit_id: Mapped[str | None] = mapped_column(String(100))
    visit_id: Mapped[str | None] = mapped_column(String(100))
    page_view_id: Mapped[str | None] = mapped_column(String(100))
    hit_date: Mapped[date | None] = mapped_column(Date)
    event_time: Mapped[datetime | None] = mapped_column(DateTime)
    url: Mapped[str | None] = mapped_column(String(1000))
    referer: Mapped[str | None] = mapped_column(String(1000))
    title: Mapped[str | None] = mapped_column(String(500))
    event_name: Mapped[str | None] = mapped_column(String(150))
    raw_json: Mapped[dict | None] = mapped_column(JSON)
    row_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class WebmasterDiagnostic(Base):
    __tablename__ = "webmaster_diagnostics"
    __table_args__ = (
        UniqueConstraint("host", "problem_code", "url", "first_seen_at", name="uq_webmaster_diagnostic"),
        Index("ix_webmaster_diagnostic_host", "host", "severity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    host: Mapped[str] = mapped_column(String(300), nullable=False)
    problem_code: Mapped[str] = mapped_column(String(150), nullable=False)
    severity: Mapped[str | None] = mapped_column(String(50))
    url: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str | None] = mapped_column(String(50))
    raw_json: Mapped[dict | None] = mapped_column(JSON)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)


class WebmasterSearchQuery(Base):
    __tablename__ = "webmaster_search_queries"
    __table_args__ = (
        UniqueConstraint("host", "date", "query", "url", name="uq_webmaster_search_query"),
        Index("ix_webmaster_query_date", "date", "query"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    host: Mapped[str] = mapped_column(String(300), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    query: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str | None] = mapped_column(String(1000))
    impressions: Mapped[int | None] = mapped_column(Integer)
    clicks: Mapped[int | None] = mapped_column(Integer)
    ctr: Mapped[float | None] = mapped_column(Numeric(8, 4))
    position: Mapped[float | None] = mapped_column(Numeric(8, 2))
    raw_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class SeoPageSnapshot(Base):
    __tablename__ = "seo_page_snapshots"
    __table_args__ = (
        UniqueConstraint("url", "content_hash", name="uq_seo_page_snapshot"),
        Index("ix_seo_page_snapshot_url", "url", "captured_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    canonical: Mapped[str | None] = mapped_column(String(1000))
    h1_count: Mapped[int | None] = mapped_column(Integer)
    json_ld_count: Mapped[int | None] = mapped_column(Integer)
    internal_links_count: Mapped[int | None] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    facts_json: Mapped[dict | None] = mapped_column(JSON)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class AgentFinding(Base):
    __tablename__ = "agent_findings"
    __table_args__ = (
        Index("ix_agent_finding_status", "status", "priority"),
        Index("ix_agent_finding_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    finding_type: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    evidence_json: Mapped[dict | None] = mapped_column(JSON)
    affected_urls_json: Mapped[dict | None] = mapped_column(JSON)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    priority: Mapped[int] = mapped_column(Integer, default=3)
    status: Mapped[str] = mapped_column(String(30), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)


class AgentActionAudit(Base):
    __tablename__ = "agent_action_audit"
    __table_args__ = (
        Index("ix_agent_action_status", "status", "safety_class"),
        Index("ix_agent_action_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    safety_class: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="proposed")
    target_json: Mapped[dict | None] = mapped_column(JSON)
    payload_json: Mapped[dict | None] = mapped_column(JSON)
    diff_json: Mapped[dict | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(Text)
    approval_token_hash: Mapped[str | None] = mapped_column(String(100))
    response_json: Mapped[dict | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime)


class FrontendEvent(Base):
    __tablename__ = "frontend_events"
    __table_args__ = (
        Index("ix_frontend_event_name_time", "event_name", "occurred_at"),
        Index("ix_frontend_event_url", "url"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_name: Mapped[str] = mapped_column(String(120), nullable=False)
    session_id_hash: Mapped[str | None] = mapped_column(String(80))
    url: Mapped[str | None] = mapped_column(String(1000))
    referrer: Mapped[str | None] = mapped_column(String(1000))
    params_json: Mapped[dict | None] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class Experiment(Base):
    __tablename__ = "experiments"
    __table_args__ = (
        UniqueConstraint("key", name="uq_experiment_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    variants_json: Mapped[dict | None] = mapped_column(JSON)
    traffic_split_json: Mapped[dict | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

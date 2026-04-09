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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

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


class FetchLog(Base):
    __tablename__ = "fetch_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    indicator_id: Mapped[int] = mapped_column(ForeignKey("indicators.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500))
    records_added: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    indicator: Mapped["Indicator"] = relationship(back_populates="fetch_logs")

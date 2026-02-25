from datetime import date, datetime
from pydantic import BaseModel


# ── Indicators ───────────────────────────────────────────────────────

class IndicatorSummary(BaseModel):
    code: str
    name: str
    name_en: str | None = None
    unit: str
    category: str | None = None
    is_active: bool
    current_value: float | None = None
    current_date: date | None = None
    previous_value: float | None = None
    change: float | None = None

    model_config = {"from_attributes": True}


class IndicatorDetail(IndicatorSummary):
    frequency: str
    source: str
    source_url: str | None = None
    description: str | None = None
    methodology: str | None = None
    data_count: int = 0
    first_date: date | None = None
    last_date: date | None = None
    updated_at: datetime | None = None


class IndicatorStats(BaseModel):
    code: str
    highest: dict | None = None
    lowest: dict | None = None
    average: float | None = None
    std_dev: float | None = None
    data_count: int = 0


# ── Data Points ──────────────────────────────────────────────────────

class DataPointOut(BaseModel):
    date: date
    value: float

    model_config = {"from_attributes": True}


class DataResponse(BaseModel):
    indicator: str
    count: int
    data: list[DataPointOut]


# ── Forecasts ────────────────────────────────────────────────────────

class ForecastValueOut(BaseModel):
    date: date
    value: float
    lower_bound: float | None = None
    upper_bound: float | None = None

    model_config = {"from_attributes": True}


class ForecastOut(BaseModel):
    model_name: str
    aic: float | None = None
    bic: float | None = None
    created_at: datetime
    values: list[ForecastValueOut]


class ForecastResponse(BaseModel):
    indicator: str
    forecast: ForecastOut | None = None


# ── Inflation (cumulative 12-month) ──────────────────────────────

class InflationPoint(BaseModel):
    date: date
    value: float


class InflationForecastPoint(BaseModel):
    date: date
    value: float
    lower_bound: float | None = None
    upper_bound: float | None = None


class InflationResponse(BaseModel):
    indicator: str
    model_name: str | None = None
    actuals: list[InflationPoint]
    forecast: list[InflationForecastPoint]


# ── System ───────────────────────────────────────────────────────────

class SystemStatus(BaseModel):
    status: str = "ok"
    indicators_count: int = 0
    total_data_points: int = 0
    last_fetch: dict | None = None
    last_forecast: dict | None = None

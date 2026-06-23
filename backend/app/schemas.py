from datetime import date, datetime
from pydantic import BaseModel


# ── Indicators ───────────────────────────────────────────────────────

class IndicatorSummary(BaseModel):
    code: str
    name: str
    name_en: str | None = None
    unit: str
    category: str | None = None
    # Частота нужна listing-карточке для формата даты (квартальный ряд → «I кв.
    # 2026», годовой → «2026», а не всегда месяц).
    frequency: str | None = None
    is_active: bool
    is_listed: bool = True
    current_value: float | None = None
    current_date: date | None = None
    previous_value: float | None = None
    change: float | None = None
    # Hero block — то, что должно быть «первой цифрой» на карточке. Если у
    # индикатора `model_config_json.hero_view = "yoy_pct"`, бэк подставляет
    # сюда YoY% изменение (а не уровень). По умолчанию hero совпадает с
    # current_value и unit индикатора.
    hero_value: float | None = None
    hero_unit: str | None = None
    hero_label: str | None = None
    # Изменение hero-значения: для индекс-карточек (hero_view=yoy_pct) — ускорение
    # Г/г в п.п. (текущий YoY% минус предыдущий). Бейдж изменения на карточке.
    hero_change: float | None = None
    # seo_keywords здесь только для search-haystack (фронт ищет по нему).
    # Не для UI-отображения. Содержит синонимы/корни на русском и en.
    seo_keywords: str | None = None

    model_config = {"from_attributes": True}


class IndicatorDetail(IndicatorSummary):
    frequency: str
    source: str
    source_url: str | None = None
    description: str | None = None
    methodology: str | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    seo_blocks: list | None = None
    data_count: int = 0
    first_date: date | None = None
    last_date: date | None = None
    updated_at: datetime | None = None
    # Linkage на индикатор-counterpart другой частоты (T3 plan).
    # Пример: для `exports` (quarterly) → {"monthly": "exports-monthly"}.
    # Используется frontend frequency switcher на странице индикатора.
    alternate_frequencies: dict[str, str] | None = None
    # Обратная ссылка: monthly counterpart → primary quarterly. Для SSR canonical.
    primary_indicator_code: str | None = None


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


# ── Calendar Events ──────────────────────────────────────────────────

class CalendarEventOut(BaseModel):
    id: int
    title: str
    title_en: str | None = None
    event_type: str
    source: str
    scheduled_date: date
    scheduled_time: str | None = None
    is_estimated: bool = False
    date_confidence: str = "official_explicit"
    reference_period: str | None = None
    importance: int = 2
    status: str = "scheduled"
    previous_value: str | None = None
    forecast_value: str | None = None
    actual_value: str | None = None
    description: str | None = None
    source_url: str | None = None
    event_key: str | None = None
    source_event_uid: str | None = None
    source_hash: str | None = None
    indicator_code: str | None = None
    indicator_name: str | None = None

    model_config = {"from_attributes": True}


class CalendarResponse(BaseModel):
    events: list[CalendarEventOut]
    total: int


# ── System ───────────────────────────────────────────────────────────

class SystemStatus(BaseModel):
    status: str = "ok"
    indicators_count: int = 0
    total_data_points: int = 0
    last_fetch: dict | None = None
    last_forecast: dict | None = None

"""Публикационные константы и проверки мировых прогнозов без тяжёлых библиотек (круг 12, SPEED3).

Веб-процесс читает готовые прогнозы из базы и только решает, можно ли их показывать. Эти проверки жили в
`world_forecaster` / `world_forecast_pipeline`, которые на уровне модуля тянут pandas, scipy и statsmodels (≈ 85 МБ
оперативной памяти на каждый из трёх воркеров). Здесь они вынесены без этих зависимостей; прежние модули реэкспортируют
те же имена, поэтому старые импорты работают как раньше.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WorldDatasetState, WorldForecast, WorldIndicator

WORLD_FORECAST_METHOD_VERSION = 2
# Прошедшие проверку на прошлых данных (витрина прогнозов и подпись «проверен» — только они).
CHECKED_GATE_STATUSES: frozenset[str] = frozenset({"passed"})
# Круг 14 (решение владельца 15.10): прогноз нашей модели показывается у каждого ряда, где она смогла посчитать;
# не прошедший проверку («advisory») — с нейтральной подписью, пока включено ``world_forecast_publish_all``.
PUBLISHED_GATE_STATUSES: frozenset[str] = frozenset({"passed", "advisory"})


def publish_all_enabled() -> bool:
    from app.config import settings

    return bool(getattr(settings, "world_forecast_publish_all", False))


def publishable_world_forecast(forecast: object) -> bool:
    """Old gate versions did not backtest the full published horizon.

    ``advisory`` показывается только при ``world_forecast_publish_all``: выключение флага прячет такие прогнозы
    сразу, без пересчёта.
    """
    params = getattr(forecast, "model_params", None)
    status = getattr(forecast, "gate_status", None)
    if status not in CHECKED_GATE_STATUSES and not (status == "advisory" and publish_all_enabled()):
        return False
    return isinstance(params, dict) and params.get("method_version") == WORLD_FORECAST_METHOD_VERSION


def _as_naive(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


async def world_forecast_source_ready(
    db: AsyncSession,
    indicator: WorldIndicator,
    *,
    forecast: WorldForecast | None = None,
) -> bool:
    """Eurostat forecast requires a successfully applied source revision."""
    if (indicator.provider or "").lower() != "eurostat":
        return True
    state = await db.get(WorldDatasetState, ("eurostat", indicator.dataset_id))
    if state is None or state.status != "ok" or state.last_success_at is None:
        return False
    if forecast is not None and _as_naive(state.last_success_at) > _as_naive(forecast.created_at):
        return False
    return True

"""On-demand, quality-gated forecasts for available US state series.

The numerical models live in forecast_strategies/*.py and are evaluated by
world_forecaster.py against rolling historical origins and a seasonal-naive
benchmark. Ingest bumps the world cache namespace, so revised observations
cause the next request to recompute the forecast.
"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Sequence

from app.services.world_forecaster import train_quality_gated_world_forecast

FREQUENCIES = {
    "annual": (14, 2, 1, "annual_auto", 1400),
    "quarterly": (32, 4, 4, "quarterly_auto", 260),
    "monthly": (72, 12, 12, "monthly_auto", 150),
}


async def state_forecast(
    dates: Sequence[date], values: Sequence[float], *, frequency: str, unit: str,
    locale: str, today: date | None = None,
) -> dict:
    """Return a public forecast only after strict MASE and plausibility gates."""
    en = locale == "en"
    reason = None
    policy = FREQUENCIES.get(frequency)
    today = today or date.today()
    if policy is None:
        reason = "unsupported_frequency"
    elif len(dates) != len(values) or len(dates) < policy[0]:
        reason = "history_too_short"
    elif dates[-1] > today:
        reason = "future_observation"
    elif not dates or (today - dates[-1]).days > policy[4]:
        reason = "series_is_stale"
    if reason:
        return {"available": False, "reason": reason, "points": []}

    _, horizon, season, strategy, _max_age = policy
    gate = await asyncio.to_thread(
        train_quality_gated_world_forecast,
        dates, values, frequency=frequency, horizon=horizon, season=season,
        strategy=strategy, strict=True,
    )
    if gate.status != "passed" or gate.result is None:
        return {
            "available": False, "reason": gate.reason, "points": [],
            "quality": {"gate_status": gate.status, "mase": gate.mase,
                        "baseline_mase": gate.baseline_mase, "origins": gate.origins},
        }
    # Rates and percentages represent bounded quantities. An extrapolation
    # outside the published measure's possible range must never reach the UI.
    if "%" in unit and min(values) >= 0 and max(values) <= 100:
        if any(point.value < 0 or point.value > 100 for point in gate.result.points):
            return {"available": False, "reason": "out_of_range", "points": []}
    methodology = (
        "Our forecast uses a separate Python model for the series frequency. "
        "We test its full horizon on rolling historical windows against a seasonal-naive benchmark; "
        "only a model with MASE below 1 and at least 2% lower error is shown. "
        "The band is an indicative range derived from historical forecast errors, not a guarantee."
        if en else
        "Наш прогноз строит отдельная Python-модель для частоты ряда. "
        "Мы проверяем весь её горизонт на последовательных исторических отрезках и сравниваем "
        "с сезонной наивной моделью. Публикуем результат только при MASE ниже 1 "
        "и ошибке минимум на 2% меньше ориентира. Диапазон рассчитан по ошибкам "
        "исторической проверки и не гарантирует будущий результат."
    )
    return {
        "available": True,
        "model_name": gate.result.model_name,
        "strategy": gate.strategy,
        "methodology": methodology,
        "quality": {"gate_status": gate.status, "mase": gate.mase,
                    "baseline_mase": gate.baseline_mase, "origins": gate.origins},
        "points": [
            {"date": point.date.isoformat(), "year": point.date.year,
             "month": point.date.month, "quarter": (point.date.month - 1) // 3 + 1,
             "value": round(float(point.value), 4),
             "lower_bound": round(float(point.lower_bound), 4) if point.lower_bound is not None else None,
             "upper_bound": round(float(point.upper_bound), 4) if point.upper_bound is not None else None}
            for point in gate.result.points
        ],
    }

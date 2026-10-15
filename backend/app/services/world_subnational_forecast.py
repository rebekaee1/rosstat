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

from app.data.world_forecast_policy import FREQ_MIN_POINTS_PUBLISH_ALL
from app.services.world_forecast_gate import publish_all_enabled
from app.services.world_forecaster import train_quality_gated_world_forecast

FREQUENCIES = {
    "annual": (14, 1, 1, "annual_auto", 1400),
    "quarterly": (32, 4, 4, "quarterly_auto", 260),
    "monthly": (72, 12, 12, "monthly_auto", 150),
}


async def state_forecast(
    dates: Sequence[date], values: Sequence[float], *, frequency: str, unit: str,
    locale: str, today: date | None = None,
) -> dict:
    """Public forecast of a state series: checked, or (publish_all) our model without the check; plausibility gates kept."""
    reason = None
    policy = FREQUENCIES.get(frequency)
    today = today or date.today()
    # Круг 14: прогноз нашей модели и без подтверждения проверкой (как у рядов стран), см. world_forecaster.
    publish_all = publish_all_enabled()
    min_points = (FREQ_MIN_POINTS_PUBLISH_ALL.get(frequency, 0) if publish_all else policy[0]) if policy else 0
    if policy is None:
        reason = "unsupported_frequency"
    elif len(dates) != len(values) or len(dates) < min_points:
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
        strategy=strategy, strict=True, publish_all=publish_all,
    )
    if gate.status not in ({"passed", "advisory"} if publish_all else {"passed"}) or gate.result is None:
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
    # Круг 14 (решение владельца 15.10): о качестве и способе проверки прогноза на странице ничего не пишем.
    return {
        "available": True,
        "model_name": gate.result.model_name,
        "strategy": gate.strategy,
        "methodology": None,
        "quality": {"gate_status": gate.status, "mase": gate.mase,
                    "baseline_mase": gate.baseline_mase, "origins": gate.origins},
        "points": [
            {"date": point.date.isoformat(), "year": point.date.year,
             "month": point.date.month, "quarter": (point.date.month - 1) // 3 + 1,
             "value": round(float(point.value), 4)}
            for point in gate.result.points
        ],
    }

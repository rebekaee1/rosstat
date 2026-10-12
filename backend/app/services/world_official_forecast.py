"""Официальные прогнозы МВФ (WEO) как публичные прогнозы world-рядов.

Решение круга 12 (12.10.2026, владелец: «максимально увеличить охват»):
у стран без национальных рядов в каталоге (Китай, Япония, Индия, Бразилия,
Турция, США и др.) единственные макро-ряды — годовые оценки МВФ. Раньше
проекции фонда на разборе отбрасывались (чтобы карта и рейтинг не считали
горизонт 2031 «последним значением»), поэтому прогноза у них не было вообще.
Теперь ближайший проекционный год пишется в ``world_forecasts`` как
**официальный прогноз МВФ**, не пересчитанный платформой:

- ``strategy='imf_weo'``, ``model_name='IMF-WEO-official'``,
  ``gate_status='passed'``, ``gate_reason='official_imf_weo'``;
- MASE и baseline пусты: статистической проверки на истории тут нет, и
  интерфейс не показывает «проверено на прошлых данных» (см.
  ``official_forecast_info`` и API ``forecast.official``);
- вместо проверки на истории действует проверка согласованности
  (``check_official_projection``): тот же выпуск WEO, что и наша история
  (единицы совпадают по построению), примыкающий год, конечные значения,
  правдоподобие относительно истории, границы по смыслу ряда, возраст
  выпуска не более ``WEO_MAX_VINTAGE_AGE_DAYS``;
- публичная подпись: «Официальный прогноз МВФ, выпуск WEO от <дата>».

Запись идемпотентна: повтор с тем же выпуском и теми же значениями не
создаёт новую строку (ежедневный ingest не должен раздувать таблицу).
"""

from __future__ import annotations

import math
from datetime import date, datetime, timezone
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WorldForecast, WorldForecastValue
from app.services.imf_weo_adapter import (
    DATASET_ID,
    PROVIDER,
    WEO_LP,
    WEO_LUR,
    WEO_MAX_VINTAGE_AGE_DAYS,
    WEO_NGDPD,
    WEO_NGDPDPC,
    WeoProjection,
)
from app.services.world_forecaster import WORLD_FORECAST_METHOD_VERSION

OFFICIAL_STRATEGY = "imf_weo"
OFFICIAL_MODEL_NAME = "IMF-WEO-official"
OFFICIAL_GATE_REASON = "official_imf_weo"

# Ряды, значения которых по смыслу положительны / лежат в 0..100.
_POSITIVE_CODES = frozenset({WEO_NGDPD, WEO_NGDPDPC, WEO_LP})
_PERCENT_BOUND_CODES = frozenset({WEO_LUR})


def is_official_forecast(forecast: object) -> bool:
    return getattr(forecast, "strategy", None) == OFFICIAL_STRATEGY


def official_forecast_info(forecast: object) -> dict | None:
    """Публичные сведения об официальном прогнозе или None."""
    if not is_official_forecast(forecast):
        return None
    params = getattr(forecast, "model_params", None)
    official = params.get("official") if isinstance(params, dict) else None
    if not isinstance(official, dict):
        return None
    return {
        "provider": official.get("provider", PROVIDER),
        "publication": official.get("publication", "World Economic Outlook"),
        "vintage": official.get("vintage"),
    }


def check_official_projection(
    *,
    weo_code: str,
    history: Sequence[tuple[date, float]],
    projection: WeoProjection,
    today: date | None = None,
) -> tuple[list[tuple[date, float]] | None, str]:
    """Проверка согласованности проекции фонда с нашей историей.

    Возвращает (точки, "ok") или (None, причина). Ничего не «ослабляет»:
    это не статистический гейт, а условия, при которых чужой прогноз можно
    честно показать рядом с нашими данными.
    """
    today = today or date.today()
    if projection.vintage is not None and (today - projection.vintage).days > WEO_MAX_VINTAGE_AGE_DAYS:
        return None, "vintage_too_old"
    if len(history) < 3:
        return None, "history_too_short"
    last_date = history[-1][0]
    points = [(period, float(value)) for period, value in projection.points]
    if not points or points[0][0].year != last_date.year + 1:
        return None, "projection_not_adjacent"
    if any(not math.isfinite(value) for _, value in points):
        return None, "non_finite_projection"
    max_history = max(abs(float(value)) for _, value in history) or 1.0
    if any(abs(value) > max_history * 5 for _, value in points):
        return None, "implausible_projection"
    if weo_code in _POSITIVE_CODES and any(value <= 0 for _, value in points):
        return None, "out_of_range"
    if weo_code in _PERCENT_BOUND_CODES and any(not 0 <= value <= 100 for _, value in points):
        return None, "out_of_range"
    return points, "ok"


def _naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def store_official_forecast(
    db: AsyncSession,
    *,
    indicator_id: int,
    weo_code: str,
    points: list[tuple[date, float]] | None,
    vintage: date | None,
    history_end: date | None,
    points_count: int,
) -> str:
    """Записать (или снять) официальный прогноз ряда. Вернуть исход.

    ``created`` / ``unchanged`` / ``withdrawn`` / ``none``.
    """
    current = (
        await db.execute(
            select(WorldForecast).where(
                WorldForecast.world_indicator_id == indicator_id,
                WorldForecast.is_current,
            )
        )
    ).scalars().all()
    if not points:
        withdrawn = [row for row in current if is_official_forecast(row)]
        for row in withdrawn:
            row.is_current = False
        return "withdrawn" if withdrawn else "none"

    wanted = {period: round(float(value), 6) for period, value in points}
    for row in current:
        if not is_official_forecast(row):
            continue
        params = row.model_params if isinstance(row.model_params, dict) else {}
        same_vintage = (params.get("official") or {}).get("vintage") == (
            vintage.isoformat() if vintage else None
        )
        stored = {
            value.date: round(float(value.value), 6)
            for value in (
                await db.execute(
                    select(WorldForecastValue).where(WorldForecastValue.forecast_id == row.id)
                )
            ).scalars().all()
        }
        if same_vintage and stored == wanted and params.get("history_end") == (
            history_end.isoformat() if history_end else None
        ):
            return "unchanged"

    for row in current:
        row.is_current = False
    forecast = WorldForecast(
        world_indicator_id=indicator_id,
        strategy=OFFICIAL_STRATEGY,
        model_name=OFFICIAL_MODEL_NAME,
        model_params={
            # method_version нужен publishable_world_forecast; смысл другой:
            # это не наша модель, а выпуск WEO (поле official).
            "method_version": WORLD_FORECAST_METHOD_VERSION,
            "history_end": history_end.isoformat() if history_end else None,
            "points_count": int(points_count or 0),
            "source_ready": True,
            "annual_horizon": len(points),
            "official": {
                "provider": PROVIDER,
                "dataset": DATASET_ID,
                "weo_code": weo_code,
                "publication": "World Economic Outlook",
                "vintage": vintage.isoformat() if vintage else None,
                "kind": "projection",
            },
        },
        gate_status="passed",
        gate_reason=OFFICIAL_GATE_REASON,
        mase=None,
        baseline_mase=None,
        origins=0,
        horizon=len(points),
        is_current=True,
        created_at=_naive_now(),
    )
    db.add(forecast)
    await db.flush()
    for period, value in sorted(wanted.items()):
        db.add(WorldForecastValue(
            forecast_id=forecast.id,
            date=period,
            value=value,
            lower_bound=None,
            upper_bound=None,
        ))
    return "created"

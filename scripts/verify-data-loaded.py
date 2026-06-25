#!/usr/bin/env python3
"""Проверка «всё ли залито»: данные и прогнозы по всем активным индикаторам.

Зачем: после деплоя/сидинга нужно убедиться, что на проде НЕ осталось пустых
рядов или режимов без прогноза, который должен быть. На локалке всё может быть
залито, а на проде initial-ETL/retrain мог не отработать для части кодов.

Что проверяет:
- каждый active source/derived индикатор имеет ≥1 точку данных;
- каждый forecastable view-mode sibling (по конфигу view_model_families) имеет
  текущий прогноз (Forecast.is_current) с ≥1 значением;
- индикаторы из явных forecast-веток (monthly_auto / derived_from_source и т.п.)
  с forecast_steps>0 имеют прогноз.

Коды выхода: 0 — всё залито; 1 — есть пробелы (печатает список).

Запуск:
    docker compose exec backend python /app/scripts/verify-data-loaded.py
или локально из backend/:
    PYTHONPATH=. python ../scripts/verify-data-loaded.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _candidate in (_HERE.parent / "backend", Path("/app")):
    if (_candidate / "app" / "database.py").exists():
        if str(_candidate) not in sys.path:
            sys.path.insert(0, str(_candidate))
        break

from sqlalchemy import func, select  # noqa: E402

from app.database import async_session  # noqa: E402
from app.models import Forecast, Indicator, IndicatorData, ForecastValue  # noqa: E402
from app.data.view_model_families import iter_sibling_indicators  # noqa: E402


async def main() -> int:
    # forecastable sibling-коды по конфигу (что обязано иметь прогноз).
    forecastable_siblings = {
        s["code"] for s in iter_sibling_indicators() if s.get("forecastable")
    }

    empty_data: list[str] = []
    missing_forecast: list[str] = []

    async with async_session() as db:
        inds = (
            await db.execute(
                select(Indicator).where(Indicator.is_active.is_(True)).order_by(Indicator.code)
            )
        ).scalars().all()

        # Точки данных по индикатору.
        counts = dict(
            (
                await db.execute(
                    select(IndicatorData.indicator_id, func.count(IndicatorData.id))
                    .group_by(IndicatorData.indicator_id)
                )
            ).all()
        )

        # Индикаторы с текущим прогнозом (хотя бы 1 значение).
        fc_ids = set(
            (
                await db.execute(
                    select(Forecast.indicator_id)
                    .join(ForecastValue, ForecastValue.forecast_id == Forecast.id)
                    .where(Forecast.is_current.is_(True))
                    .group_by(Forecast.indicator_id)
                )
            ).scalars().all()
        )

        by_id = {ind.id: ind for ind in inds}
        for ind in inds:
            n = counts.get(ind.id, 0)
            if n == 0:
                empty_data.append(ind.code)

            cfg = ind.model_config_json or {}
            steps = int(cfg.get("forecast_steps", 0) or 0)
            wants_forecast = steps > 0 or ind.code in forecastable_siblings
            if wants_forecast and ind.id not in fc_ids and n > 0:
                missing_forecast.append(ind.code)

    print(f"Активных индикаторов: {len(by_id)}")
    print(f"Пустых рядов (0 точек): {len(empty_data)}")
    for c in empty_data:
        print(f"  EMPTY  {c}")
    print(f"Без прогноза (ожидался): {len(missing_forecast)}")
    for c in missing_forecast:
        print(f"  NOFC   {c}")

    if empty_data or missing_forecast:
        print("\nFAIL: есть пробелы — см. список выше.")
        return 1
    print("\nOK: все активные ряды залиты, прогнозы на месте.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

"""Т-8: генерация prod-fixture снапшотов forecast-стратегий.

Одноразовый (но воспроизводимый) генератор: берёт реальный ряд индикатора из
БД, прогоняет стратегию и пишет snapshot JSON в
`tests/forecast_strategies/snapshots/prod_<strategy>.json`:
    {strategy, code, cfg, frequency, series[], outputs[{model_name, points[]}]}

Тест `test_prod_strategy_snapshots.py` затем воспроизводит прогноз bit-exact —
обновление statsmodels/numpy, меняющее числа, станет красным тестом, а не
тихой сменой прогнозов на проде.

Запуск (локальная БД):
    RUSTATS_DATABASE_URL=... PYTHONPATH=. .venv/bin/python scripts/gen-forecast-snapshots.py
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.models import Indicator, IndicatorData
from app.services.forecast_strategies.base import StrategyContext
from app.services.forecast_strategies.registry import STRATEGIES

# strategy → канонический код-представитель (стабильный, длинная история)
TARGETS = {
    "ppi_monthly": "ppi",
    "gdp_nominal_quarterly": "gdp-nominal",
    "generic_quarterly": "exports",
    "signed_quarterly": "fdi-net",
    "generic_ols": "inflation-weekly",
}

OUT_DIR = Path(__file__).parent.parent / "tests" / "forecast_strategies" / "snapshots"


async def main() -> None:
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as db:
        for strategy_name, code in TARGETS.items():
            ind = (await db.execute(
                select(Indicator).where(Indicator.code == code)
            )).scalar_one_or_none()
            if ind is None:
                print(f"SKIP {strategy_name}: индикатор {code} не найден")
                continue
            rows = (await db.execute(
                select(IndicatorData)
                .where(IndicatorData.indicator_id == ind.id)
                .order_by(IndicatorData.date)
            )).scalars().all()
            if len(rows) < 12:
                print(f"SKIP {strategy_name}: {code} даёт лишь {len(rows)} точек")
                continue

            dates = [r.date for r in rows]
            values = [float(r.value) for r in rows]
            cfg = ind.model_config_json or {}
            ctx = StrategyContext(
                indicator_code=code,
                indicator_frequency=ind.frequency,
                forecast_steps=int(cfg.get("forecast_steps") or 4),
                cfg=cfg,
            )
            outputs = STRATEGIES[strategy_name](dates, values, ctx)

            snap = {
                "strategy": strategy_name,
                "code": code,
                "frequency": ind.frequency,
                "cfg": cfg,
                "series": [
                    {"date": d.isoformat(), "value": v}
                    for d, v in zip(dates, values)
                ],
                "outputs": [
                    {
                        "model_name": out.result.model_name,
                        "points": [
                            {
                                "date": p.date.isoformat(),
                                "value": round(float(p.value), 4),
                                "lower": (round(float(p.lower_bound), 4)
                                          if p.lower_bound is not None else None),
                                "upper": (round(float(p.upper_bound), 4)
                                          if p.upper_bound is not None else None),
                            }
                            for p in out.result.points
                        ],
                    }
                    for out in outputs
                ],
            }
            path = OUT_DIR / f"prod_{strategy_name}.json"
            path.write_text(
                json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8"
            )
            n_pts = sum(len(o["points"]) for o in snap["outputs"])
            print(f"OK {strategy_name}: {code}, {len(rows)} точек истории → "
                  f"{len(snap['outputs'])} моделей, {n_pts} прогнозных точек → {path.name}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

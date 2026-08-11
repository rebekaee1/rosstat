"""Изолированный pipeline quality-gated прогнозов world bounded context."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import bump_namespaces
from app.data.world_forecast_policy import forecast_eligibility_for
from app.database import async_session
from app.models import (
    WorldDataPoint,
    WorldForecast,
    WorldForecastValue,
    WorldIndicator,
)
from app.services.world_forecaster import train_quality_gated_world_forecast

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorldForecastRunSummary:
    selected: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0


async def _deactivate_current(
    db: AsyncSession,
    indicator_id: int,
) -> int:
    rows = (
        await db.execute(
            select(WorldForecast).where(
                WorldForecast.world_indicator_id == indicator_id,
                WorldForecast.is_current.is_(True),
            )
        )
    ).scalars().all()
    for row in rows:
        row.is_current = False
    return len(rows)


async def retrain_world_indicator_forecast(
    db: AsyncSession,
    indicator: WorldIndicator,
) -> str:
    eligibility, reason = forecast_eligibility_for(indicator)
    if eligibility is None:
        removed = await _deactivate_current(db, indicator.id)
        if removed:
            logger.info(
                "Disabled stale world forecast for %s: %s",
                indicator.code,
                reason,
            )
        return "skipped"

    points = (
        await db.execute(
            select(WorldDataPoint)
            .where(WorldDataPoint.indicator_id == indicator.id)
            .order_by(WorldDataPoint.date)
        )
    ).scalars().all()
    dates = [point.date for point in points]
    values = [float(point.value) for point in points]
    gate = await asyncio.to_thread(
        train_quality_gated_world_forecast,
        dates,
        values,
        frequency=eligibility.frequency,
        horizon=eligibility.horizon,
        season=eligibility.season,
        strategy=eligibility.strategy,
    )

    await _deactivate_current(db, indicator.id)
    forecast = WorldForecast(
        world_indicator_id=indicator.id,
        strategy=gate.strategy,
        model_name=(
            gate.result.model_name
            if gate.result is not None
            else f"World-{gate.strategy}-v1"
        ),
        model_params={
            "registry_key": list(eligibility.registry_key),
            "provider": eligibility.provider,
            "dataset_id": eligibility.dataset_id,
            "unit": eligibility.unit,
            "frequency": eligibility.frequency,
            "season": eligibility.season,
            "requested_strategy": eligibility.strategy,
            "resolved_strategy": gate.strategy,
            "methodology": "shared_multi_window",
            "gate": "rolling_origin_mase",
            "benchmark": "seasonal_naive",
        },
        gate_status=gate.status,
        gate_reason=gate.reason,
        mase=gate.mase,
        baseline_mase=gate.baseline_mase,
        origins=gate.origins,
        horizon=eligibility.horizon,
        is_current=gate.status == "passed",
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(forecast)
    await db.flush()
    if gate.result is not None:
        for point in gate.result.points:
            db.add(WorldForecastValue(
                forecast_id=forecast.id,
                date=point.date,
                value=point.value,
                lower_bound=point.lower_bound,
                upper_bound=point.upper_bound,
            ))
    return gate.status


async def world_forecast_job() -> WorldForecastRunSummary:
    """Пересчитать все публичные M/Q primary-series; ошибки изолированы по ряду."""
    async with async_session() as db:
        indicator_ids = list((
            await db.execute(
                select(WorldIndicator.id)
                .where(
                    WorldIndicator.is_listed.is_(True),
                    WorldIndicator.frequency.in_(("monthly", "quarterly")),
                )
                .order_by(WorldIndicator.id)
            )
        ).scalars().all())

    counts = {
        "selected": len(indicator_ids),
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "errors": 0,
    }
    changed = False
    for indicator_id in indicator_ids:
        try:
            async with async_session() as db:
                indicator = await db.get(WorldIndicator, indicator_id)
                if indicator is None:
                    counts["skipped"] += 1
                    continue
                status = await retrain_world_indicator_forecast(db, indicator)
                await db.commit()
                counts[status] += 1
                changed = changed or status in {"passed", "failed"}
        except Exception:  # noqa: BLE001 — один ряд не отменяет весь world run
            counts["errors"] += 1
            logger.exception("World forecast failed for indicator_id=%s", indicator_id)

    if changed:
        await bump_namespaces("world")
    summary = WorldForecastRunSummary(**counts)
    logger.info("World forecast run completed: %s", summary)
    return summary

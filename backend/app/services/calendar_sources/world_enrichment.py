"""Факт выхода мирового выпуска — по точке отчётного периода в мировом ряду сайта (14.11.2026).

У мировых рядов нет времени загрузки точки (``world_data_points`` без ``created_at``), поэтому
выход подтверждается так: дата выпуска наступила и точка периода уже есть в ряду. Работает для
выпусков с привязкой к ряду каталога (BEA: ВВП, индекс цен PCE, торговый баланс США). FOMC и
Eurostat без ряда остаются без цифры: «дата прошла».
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EconomicEvent, WorldDataPoint, WorldIndicator
from app.services.calendar_sources.enrichment import _format_actual, parse_reference_period_date

logger = logging.getLogger(__name__)

_QUARTER_RE = re.compile(r"Q([1-4])\s+(20\d{2})")


def world_period_date(reference_period: str | None, frequency: str | None) -> date | None:
    """Дата точки мирового ряда для периода: месяц — 1-е число; квартал — первый день квартала (FRED)."""
    if not reference_period:
        return None
    q = _QUARTER_RE.search(reference_period)
    if q:
        return date(int(q.group(2)), (int(q.group(1)) - 1) * 3 + 1, 1)
    return parse_reference_period_date(reference_period)


async def enrich_world_events(db: AsyncSession, *, today: date | None = None) -> int:
    from app.services.display import today_msk

    today = today or today_msk()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = (await db.execute(
        select(EconomicEvent).where(
            EconomicEvent.source.in_(("fed", "bea", "eurostat")),
            EconomicEvent.scheduled_date <= today,
            EconomicEvent.reference_period.is_not(None),
            or_(EconomicEvent.actual_value.is_(None), EconomicEvent.actual_value == ""),
        )
    )).scalars().all()
    indicators: dict[str, WorldIndicator | None] = {}
    updated = 0
    for ev in rows:
        details = ((ev.metadata_json or {}).get("provenance") or {}).get("details") or {}
        code = details.get("world_code")
        if not code:
            continue
        if code not in indicators:
            indicators[code] = (await db.execute(
                select(WorldIndicator).where(WorldIndicator.code == code)
            )).scalar_one_or_none()
        ind = indicators[code]
        if ind is None:
            continue
        point_date = world_period_date(ev.reference_period, ind.frequency)
        if point_date is None:
            continue
        value = (await db.execute(
            select(WorldDataPoint.value).where(WorldDataPoint.indicator_id == ind.id,
                                               WorldDataPoint.date == point_date)
        )).scalar()
        if value is None:
            continue
        previous = (await db.execute(
            select(WorldDataPoint.value)
            .where(WorldDataPoint.indicator_id == ind.id, WorldDataPoint.date < point_date)
            .order_by(WorldDataPoint.date.desc()).limit(1)
        )).scalar()
        ev.actual_value = _format_actual(float(value))
        if previous is not None and not ev.previous_value:
            ev.previous_value = _format_actual(float(previous))
        ev.status = "released"
        ev.actual_date = point_date
        meta = dict(ev.metadata_json or {})
        meta["release_fact"] = {"via": "world_reference_period", "point_date": point_date.isoformat()}
        ev.metadata_json = meta
        ev.updated_at = now
        updated += 1
    if updated:
        await db.commit()
        logger.info("Calendar: %d world events confirmed from world series", updated)
    return updated

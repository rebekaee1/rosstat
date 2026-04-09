from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import EconomicEvent, Indicator
from app.schemas import CalendarEventOut, CalendarResponse
from app.core.cache import cache_get, cache_set

router = APIRouter(prefix="/calendar", tags=["calendar"])

CACHE_TTL = 900  # 15 min


def _build_event_out(ev: EconomicEvent, indicator: Indicator | None) -> CalendarEventOut:
    return CalendarEventOut(
        id=ev.id,
        title=ev.title,
        title_en=ev.title_en,
        event_type=ev.event_type,
        source=ev.source,
        scheduled_date=ev.scheduled_date,
        scheduled_time=ev.scheduled_time,
        is_estimated=ev.is_estimated,
        reference_period=ev.reference_period,
        importance=ev.importance,
        status=ev.status,
        previous_value=ev.previous_value,
        forecast_value=ev.forecast_value,
        actual_value=ev.actual_value,
        description=ev.description,
        source_url=ev.source_url,
        indicator_code=indicator.code if indicator else None,
        indicator_name=indicator.name if indicator else None,
    )


@router.get("", response_model=CalendarResponse)
async def list_events(
    db: AsyncSession = Depends(get_db),
    from_date: Optional[date] = Query(None, alias="from", description="Start date (inclusive)"),
    to_date: Optional[date] = Query(None, alias="to", description="End date (inclusive)"),
    source: Optional[str] = Query(None, description="Comma-separated: cbr,rosstat,minfin"),
    importance: Optional[str] = Query(None, description="Comma-separated: 1,2,3"),
    event_type: Optional[str] = Query(None, description="Comma-separated event types"),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    if not from_date:
        from_date = date.today() - timedelta(days=7)
    if not to_date:
        to_date = from_date + timedelta(days=60)

    cache_key = f"fe:calendar:{from_date}:{to_date}:{source}:{importance}:{event_type}:{limit}:{offset}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    conditions = [
        EconomicEvent.scheduled_date >= from_date,
        EconomicEvent.scheduled_date <= to_date,
    ]
    if source:
        sources = [s.strip() for s in source.split(",")]
        conditions.append(EconomicEvent.source.in_(sources))
    if importance:
        levels = [int(x.strip()) for x in importance.split(",") if x.strip().isdigit()]
        if levels:
            conditions.append(EconomicEvent.importance.in_(levels))
    if event_type:
        types = [t.strip() for t in event_type.split(",")]
        conditions.append(EconomicEvent.event_type.in_(types))

    count_q = await db.execute(
        select(func.count(EconomicEvent.id)).where(and_(*conditions))
    )
    total = count_q.scalar() or 0

    stmt = (
        select(EconomicEvent, Indicator)
        .outerjoin(Indicator, EconomicEvent.indicator_id == Indicator.id)
        .where(and_(*conditions))
        .order_by(EconomicEvent.scheduled_date, EconomicEvent.importance.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()

    events = [_build_event_out(ev, ind) for ev, ind in rows]
    resp = CalendarResponse(events=events, total=total)
    serialized = resp.model_dump(mode="json")
    await cache_set(cache_key, serialized, CACHE_TTL)
    return resp


@router.get("/upcoming", response_model=CalendarResponse)
async def upcoming_events(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(10, ge=1, le=50),
    importance_min: int = Query(1, ge=1, le=3),
):
    cache_key = f"fe:calendar:upcoming:{limit}:{importance_min}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    today = date.today()
    stmt = (
        select(EconomicEvent, Indicator)
        .outerjoin(Indicator, EconomicEvent.indicator_id == Indicator.id)
        .where(
            EconomicEvent.scheduled_date >= today,
            EconomicEvent.importance >= importance_min,
        )
        .order_by(EconomicEvent.scheduled_date, EconomicEvent.importance.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    events = [_build_event_out(ev, ind) for ev, ind in rows]
    resp = CalendarResponse(events=events, total=len(events))
    await cache_set(cache_key, resp.model_dump(mode="json"), CACHE_TTL)
    return resp


@router.get("/{event_id}", response_model=CalendarEventOut)
async def get_event(event_id: int, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(EconomicEvent, Indicator)
        .outerjoin(Indicator, EconomicEvent.indicator_id == Indicator.id)
        .where(EconomicEvent.id == event_id)
    )
    row = (await db.execute(stmt)).first()
    if not row:
        raise HTTPException(status_code=404, detail="Event not found")
    ev, ind = row
    return _build_event_out(ev, ind)


ICAL_HEADER = (
    "BEGIN:VCALENDAR\r\n"
    "VERSION:2.0\r\n"
    "PRODID:-//Forecast Economy//Calendar//RU\r\n"
    "CALSCALE:GREGORIAN\r\n"
    "METHOD:PUBLISH\r\n"
    "X-WR-CALNAME:Forecast Economy — Экономический календарь\r\n"
    "X-WR-TIMEZONE:Europe/Moscow\r\n"
)


@router.get("/export/ical", response_class=PlainTextResponse)
async def export_ical(
    db: AsyncSession = Depends(get_db),
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    importance_min: int = Query(2, ge=1, le=3),
):
    if not from_date:
        from_date = date.today()
    if not to_date:
        to_date = from_date + timedelta(days=90)

    stmt = (
        select(EconomicEvent)
        .where(
            EconomicEvent.scheduled_date >= from_date,
            EconomicEvent.scheduled_date <= to_date,
            EconomicEvent.importance >= importance_min,
        )
        .order_by(EconomicEvent.scheduled_date)
        .limit(500)
    )
    events = (await db.execute(stmt)).scalars().all()

    lines = [ICAL_HEADER]
    for ev in events:
        dt_str = ev.scheduled_date.strftime("%Y%m%d")
        uid = f"fe-event-{ev.id}@forecasteconomy.com"
        summary = ev.title
        if ev.reference_period:
            summary += f" ({ev.reference_period})"
        desc_parts = [f"Источник: {ev.source.upper()}"]
        if ev.previous_value:
            desc_parts.append(f"Предыдущее: {ev.previous_value}")
        if ev.scheduled_time:
            desc_parts.append(f"Время: {ev.scheduled_time} МСК")
        desc = "\\n".join(desc_parts)

        lines.append("BEGIN:VEVENT\r\n")
        lines.append(f"UID:{uid}\r\n")
        lines.append(f"DTSTART;VALUE=DATE:{dt_str}\r\n")
        lines.append(f"SUMMARY:{summary}\r\n")
        lines.append(f"DESCRIPTION:{desc}\r\n")
        if ev.source_url:
            lines.append(f"URL:{ev.source_url}\r\n")
        lines.append("END:VEVENT\r\n")

    lines.append("END:VCALENDAR\r\n")

    return PlainTextResponse(
        content="".join(lines),
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=forecast-economy-calendar.ics"},
    )

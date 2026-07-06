import re
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Indicator, IndicatorData
from app.schemas import IndicatorSummary, IndicatorDetail, IndicatorStats, DataPointOut, DataResponse
from app.core.cache import cache_get, cache_set, versioned_key
from app.config import settings

router = APIRouter(prefix="/indicators", tags=["indicators"])


# Расчёт hero YoY% (только для индикаторов с `model_config_json.hero_view ==
# "yoy_pct"`). Точка «год назад» ищется ПО ДАТЕ, а не по позиции в ряду:
# позиционный сдвиг (rows[12] = «год назад») при дыре в ряду молча сравнивал
# с 13-месячной давностью, а weekly (52 шага) дрейфовал на 53-недельных годах.
# Для месячных/квартальных/годовых дата совпадает точно (точки — начала
# периодов); для weekly/daily даты публикаций плавают — ближайшая точка в
# допуске ±6 дней вокруг «минус 364/365 дней» (без допуска hero исчез бы у
# недельных карточек вовсе — регресс хуже дрейфа).
_YOY_TARGET = {
    "monthly": ("exact", None),
    "quarterly": ("exact", None),
    "annual": ("exact", None),
    "weekly": ("nearest", timedelta(days=364)),
    "daily": ("nearest", timedelta(days=365)),
}
_YOY_TOLERANCE = timedelta(days=6)


def _year_ago_target(d: date, frequency: str) -> date | None:
    mode = _YOY_TARGET.get(frequency)
    if mode is None:
        return None
    kind, delta = mode
    if kind == "nearest":
        return d - delta
    try:
        return d.replace(year=d.year - 1)
    except ValueError:  # 29 февраля
        return d.replace(year=d.year - 1, day=28)


def _lookup_year_ago(points: list[tuple[date, float]], d: date, frequency: str) -> float | None:
    """Значение «год назад» от даты d: точное совпадение или ближайшее в допуске."""
    target = _year_ago_target(d, frequency)
    if target is None:
        return None
    exact = frequency in ("monthly", "quarterly", "annual")
    best: tuple[int, float] | None = None
    for pd, pv in points:
        diff = abs((pd - target).days)
        if exact:
            if diff == 0:
                return pv
        elif diff <= _YOY_TOLERANCE.days and (best is None or diff < best[0]):
            best = (diff, pv)
    return best[1] if best else None


def _hero_window(current_date: date, frequency: str) -> tuple[date, date] | None:
    """Окно дат, в котором лежат кандидаты «год назад» для current и prev точек."""
    window_lo = _year_ago_target(current_date, frequency)
    if window_lo is None:
        return None
    return window_lo - timedelta(days=100), current_date - timedelta(days=300)


def _hero_yoy_from_points(
    frequency: str,
    current_val: float,
    rows: list[tuple[date, float]],
    candidates: list[tuple[date, float]],
):
    """Чистый расчёт hero YoY% по уже выбранным точкам.

    `rows` — последние точки ряда (новые первыми), `candidates` — точки в окне
    «год назад». Возвращает `(hero_value, hero_unit, hero_label, hero_change)`
    или `(None, …)`, если точки «год назад» нет (дыра в ряду) — честное «нет
    данных» вместо сравнения с чужим периодом. `hero_change` — ускорение/
    замедление в п.п.: разница между текущим YoY% и YoY% предыдущего периода
    (бейдж изменения на карточке-индексе, где «первая цифра» сама уже Г/г)."""
    if not rows:
        return None, None, None, None
    current_date = rows[0][0]
    year_ago = _lookup_year_ago(candidates, current_date, frequency)
    if not year_ago:
        return None, None, None, None
    pct = (current_val - year_ago) / year_ago * 100.0
    hero_change = None
    if len(rows) > 1:
        prev_date, prev_val = rows[1][0], float(rows[1][1])
        prev_year_ago = _lookup_year_ago(candidates, prev_date, frequency)
        if prev_year_ago:
            prev_pct = (prev_val - prev_year_ago) / prev_year_ago * 100.0
            hero_change = round(pct - prev_pct, 2)
    return round(pct, 2), "%", "Год к году", hero_change


async def _hero_yoy_pct(db: AsyncSession, ind_id: int, frequency: str, current_val: float | None):
    """Hero YoY% для одного индикатора (detail-endpoint): 2 точечных запроса."""
    if current_val is None or frequency not in _YOY_TARGET:
        return None, None, None, None
    rows = (await db.execute(
        select(IndicatorData.date, IndicatorData.value)
        .where(IndicatorData.indicator_id == ind_id)
        .order_by(desc(IndicatorData.date))
        .limit(3)
    )).all()
    if not rows:
        return None, None, None, None
    window = _hero_window(rows[0][0], frequency)
    if window is None:
        return None, None, None, None
    candidates = [
        (d, float(v)) for d, v in (await db.execute(
            select(IndicatorData.date, IndicatorData.value)
            .where(
                IndicatorData.indicator_id == ind_id,
                IndicatorData.date >= window[0],
                IndicatorData.date <= window[1],
            )
            .order_by(desc(IndicatorData.date))
        )).all()
    ]
    return _hero_yoy_from_points(
        frequency, float(current_val),
        [(d, float(v)) for d, v in rows], candidates,
    )


def _hero_view(indicator) -> str | None:
    mcfg = indicator.model_config_json or {}
    return mcfg.get("hero_view")


@router.get("", response_model=list[IndicatorSummary])
async def list_indicators(
    db: AsyncSession = Depends(get_db),
    category: Optional[str] = Query(None, description="Точное совпадение с полем category в БД"),
    include_inactive: bool = Query(False, description="Показать неактивные индикаторы"),
    include_unlisted: bool = Query(False, description="Показать индикаторы со is_listed=False (counterpart-карточки разных частот)"),
):
    cache_key = await versioned_key(
        "indicators",
        f"list:{category or 'all'}:"
        f"{'all' if include_inactive else 'active'}:"
        f"{'all' if include_unlisted else 'listed'}",
    )
    cached = await cache_get(cache_key)
    if cached:
        return cached

    stmt = select(Indicator).order_by(Indicator.code)
    if not include_inactive:
        stmt = stmt.where(Indicator.is_active.is_(True))
    if not include_unlisted:
        # A3: child-индикаторы (`exports-monthly`, `gdp-real-yoy`, etc.) видны
        # только через frequency/view switcher из primary-карточки, не дублируются в каталоге.
        stmt = stmt.where(Indicator.is_listed.is_(True))
    if category:
        stmt = stmt.where(Indicator.category == category)
    result = await db.execute(stmt)
    indicators = result.scalars().all()
    if not indicators:
        return []

    ind_ids = [ind.id for ind in indicators]

    ranked = (
        select(
            IndicatorData.indicator_id,
            IndicatorData.date,
            IndicatorData.value,
            func.row_number()
            .over(partition_by=IndicatorData.indicator_id, order_by=desc(IndicatorData.date))
            .label("rn"),
        )
        .where(IndicatorData.indicator_id.in_(ind_ids))
        .subquery()
    )
    latest_q = await db.execute(
        select(ranked.c.indicator_id, ranked.c.date, ranked.c.value, ranked.c.rn)
        .where(ranked.c.rn <= 2)
    )
    latest_rows = latest_q.all()

    by_ind: dict[int, list] = {}
    for row in latest_rows:
        by_ind.setdefault(row.indicator_id, []).append(row)
    for v in by_ind.values():
        v.sort(key=lambda r: r.rn)

    # П-8: hero YoY% для всех hero-индикаторов каталога — ОДНИМ запросом по
    # объединению их окон «год назад», вместо 2 запросов на каждый индикатор
    # в цикле (при ~8 hero-кодах это было 16 лишних round-trip'ов на cache miss).
    hero_data: dict[int, tuple] = {}
    hero_windows: dict[int, tuple[date, date]] = {}
    freq_by_id: dict[int, str] = {}
    for ind in indicators:
        if _hero_view(ind) != "yoy_pct" or ind.frequency not in _YOY_TARGET:
            continue
        rows = by_ind.get(ind.id)
        if not rows or rows[0].value is None:
            continue
        window = _hero_window(rows[0].date, ind.frequency)
        if window:
            hero_windows[ind.id] = window
            freq_by_id[ind.id] = ind.frequency
    if hero_windows:
        lo = min(w[0] for w in hero_windows.values())
        hi = max(w[1] for w in hero_windows.values())
        cand_rows = (await db.execute(
            select(IndicatorData.indicator_id, IndicatorData.date, IndicatorData.value)
            .where(
                IndicatorData.indicator_id.in_(hero_windows.keys()),
                IndicatorData.date >= lo,
                IndicatorData.date <= hi,
            )
        )).all()
        cand_by_ind: dict[int, list[tuple[date, float]]] = {}
        for iid, d, v in cand_rows:
            w = hero_windows[iid]
            if w[0] <= d <= w[1]:
                cand_by_ind.setdefault(iid, []).append((d, float(v)))
        for iid in hero_windows:
            ind_rows = [(r.date, float(r.value)) for r in by_ind[iid]]
            hero_data[iid] = _hero_yoy_from_points(
                freq_by_id[iid], ind_rows[0][1], ind_rows,
                cand_by_ind.get(iid, []),
            )

    out = []
    for ind in indicators:
        rows = by_ind.get(ind.id, [])
        current_val = rows[0].value if rows else None
        current_dt = rows[0].date if rows else None
        prev_val = rows[1].value if len(rows) > 1 else None
        change = round(float(current_val - prev_val), 4) if current_val is not None and prev_val is not None else None

        # Hero для listing-карточки: если у индекс-индикатора hero_view=yoy_pct,
        # «первая цифра» на карточке каталога = изменение г/г %, а не уровень
        # индекса (раньше карточка показывала 346, а страница по умолчанию — г/г,
        # что путало). Так карточка совпадает со значением при первом входе.
        hero_value = hero_unit = hero_label = hero_change = None
        if ind.id in hero_data:
            hero_value, hero_unit, hero_label, hero_change = hero_data[ind.id]

        out.append(IndicatorSummary(
            code=ind.code, name=ind.name, name_en=ind.name_en,
            unit=ind.unit, category=ind.category, frequency=ind.frequency,
            is_active=ind.is_active,
            is_listed=ind.is_listed,
            current_value=float(current_val) if current_val is not None else None,
            current_date=current_dt, previous_value=float(prev_val) if prev_val is not None else None,
            change=change,
            hero_value=hero_value, hero_unit=hero_unit, hero_label=hero_label,
            hero_change=hero_change,
            seo_keywords=ind.seo_keywords,
        ))

    serialized = [s.model_dump(mode="json") for s in out]
    await cache_set(cache_key, serialized, settings.cache_ttl_meta)
    return out


_CODE_RE = re.compile(r'^[a-z0-9-]+$')


def _validate_code(code: str) -> None:
    if not _CODE_RE.match(code):
        raise HTTPException(status_code=400, detail="Invalid indicator code format")


@router.get("/{code}", response_model=IndicatorDetail)
async def get_indicator(code: str, db: AsyncSession = Depends(get_db)):
    _validate_code(code)
    detail_key = await versioned_key(code, "detail")
    cached = await cache_get(detail_key)
    if cached:
        return cached

    ind = await db.execute(select(Indicator).where(Indicator.code == code))
    indicator = ind.scalar_one_or_none()
    if not indicator:
        raise HTTPException(status_code=404, detail=f"Indicator '{code}' not found")

    stats = await db.execute(
        select(
            func.count(IndicatorData.id),
            func.min(IndicatorData.date),
            func.max(IndicatorData.date),
        ).where(IndicatorData.indicator_id == indicator.id)
    )
    count, first_dt, last_dt = stats.one()

    latest = await db.execute(
        select(IndicatorData)
        .where(IndicatorData.indicator_id == indicator.id)
        .order_by(desc(IndicatorData.date))
        .limit(2)
    )
    recent = latest.scalars().all()
    current_val = recent[0].value if recent else None
    current_dt = recent[0].date if recent else None
    prev_val = recent[1].value if len(recent) > 1 else None
    change = round(float(current_val - prev_val), 4) if current_val is not None and prev_val is not None else None

    mcfg = indicator.model_config_json or {}
    alt_freq = mcfg.get("alternate_frequencies") or None
    primary_code = mcfg.get("primary_indicator_code") or None

    hero_value = hero_unit = hero_label = hero_change = None
    if mcfg.get("hero_view") == "yoy_pct":
        hero_value, hero_unit, hero_label, hero_change = await _hero_yoy_pct(
            db, indicator.id, indicator.frequency, current_val,
        )

    detail = IndicatorDetail(
        code=indicator.code, name=indicator.name, name_en=indicator.name_en,
        unit=indicator.unit, category=indicator.category, is_active=indicator.is_active,
        is_listed=indicator.is_listed,
        frequency=indicator.frequency, source=indicator.source,
        source_url=indicator.source_url, description=indicator.description,
        methodology=indicator.methodology,
        seo_title=indicator.seo_title,
        seo_description=indicator.seo_description,
        seo_blocks=indicator.seo_blocks,
        current_value=float(current_val) if current_val is not None else None,
        current_date=current_dt, previous_value=float(prev_val) if prev_val is not None else None,
        change=change, data_count=count, first_date=first_dt, last_date=last_dt,
        updated_at=indicator.updated_at,
        alternate_frequencies=alt_freq,
        primary_indicator_code=primary_code,
        hero_value=hero_value, hero_unit=hero_unit, hero_label=hero_label,
        hero_change=hero_change,
    )

    await cache_set(detail_key, detail.model_dump(mode="json"), settings.cache_ttl_meta)
    return detail


@router.get("/{code}/data", response_model=DataResponse)
async def get_indicator_data(
    code: str,
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    limit: int = Query(10000, ge=1, le=10000),
    db: AsyncSession = Depends(get_db),
):
    _validate_code(code)
    cache_key = await versioned_key(code, f"data:{from_date}:{to_date}:{limit}")
    cached = await cache_get(cache_key)
    if cached:
        return cached

    ind = await db.execute(select(Indicator).where(Indicator.code == code))
    indicator = ind.scalar_one_or_none()
    if not indicator:
        raise HTTPException(status_code=404, detail=f"Indicator '{code}' not found")

    stmt = (
        select(IndicatorData)
        .where(IndicatorData.indicator_id == indicator.id)
    )
    if from_date:
        stmt = stmt.where(IndicatorData.date >= from_date)
    if to_date:
        stmt = stmt.where(IndicatorData.date <= to_date)

    if not from_date and not to_date:
        stmt = stmt.order_by(desc(IndicatorData.date)).limit(limit)
        result = await db.execute(stmt)
        rows = list(reversed(result.scalars().all()))
    else:
        stmt = stmt.order_by(IndicatorData.date).limit(limit)
        result = await db.execute(stmt)
        rows = result.scalars().all()

    response = DataResponse(
        indicator=code,
        count=len(rows),
        data=[DataPointOut(date=r.date, value=float(r.value)) for r in rows],
    )

    await cache_set(cache_key, response.model_dump(mode="json"), settings.cache_ttl_data)
    return response


@router.get("/{code}/stats", response_model=IndicatorStats)
async def get_indicator_stats(code: str, db: AsyncSession = Depends(get_db)):
    _validate_code(code)
    ind = await db.execute(select(Indicator).where(Indicator.code == code))
    indicator = ind.scalar_one_or_none()
    if not indicator:
        raise HTTPException(status_code=404, detail=f"Indicator '{code}' not found")

    stats_q = await db.execute(
        select(
            func.count(IndicatorData.id),
            func.avg(IndicatorData.value),
            func.stddev(IndicatorData.value),
        ).where(IndicatorData.indicator_id == indicator.id)
    )
    count, avg_val, std_val = stats_q.one()

    highest_q = await db.execute(
        select(IndicatorData)
        .where(IndicatorData.indicator_id == indicator.id)
        .order_by(desc(IndicatorData.value))
        .limit(1)
    )
    highest = highest_q.scalar_one_or_none()

    lowest_q = await db.execute(
        select(IndicatorData)
        .where(IndicatorData.indicator_id == indicator.id)
        .order_by(IndicatorData.value)
        .limit(1)
    )
    lowest = lowest_q.scalar_one_or_none()

    return IndicatorStats(
        code=code,
        highest={"value": float(highest.value), "date": str(highest.date)} if highest else None,
        lowest={"value": float(lowest.value), "date": str(lowest.date)} if lowest else None,
        average=round(float(avg_val), 2) if avg_val is not None else None,
        std_dev=round(float(std_val), 2) if std_val is not None else None,
        data_count=count or 0,
    )

"""Данные сравнения двух регионов — общий слой для SSR и JSON API."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Region, RegionDataPoint, RegionIndicator
from app.services.seo_regional import MACRO_BY_TABLE, _fmt, _region

_KEY_TABLE_CODES = tuple(MACRO_BY_TABLE) + ("5.1",)


async def build_region_compare_payload(
    slug_a: str, slug_b: str, db: AsyncSession
) -> dict | None:
    if slug_a == slug_b:
        return None
    canon_a, canon_b = sorted((slug_a, slug_b))

    region_a = await _region(db, canon_a)
    region_b = await _region(db, canon_b)
    if not region_a or not region_b or region_a.kind != "region" or region_b.kind != "region":
        return None

    indicators = (await db.execute(
        select(RegionIndicator)
        .where(RegionIndicator.table_code.in_(_KEY_TABLE_CODES))
        .order_by(RegionIndicator.section_num)
    )).scalars().all()
    if not indicators:
        return None

    rows = []
    summary_bits = []
    for ind in indicators:
        common_year = (await db.execute(
            select(RegionDataPoint.year)
            .where(RegionDataPoint.indicator_id == ind.id,
                   RegionDataPoint.region_id.in_([region_a.id, region_b.id]))
            .group_by(RegionDataPoint.year)
            .having(func.count(func.distinct(RegionDataPoint.region_id)) == 2)
            .order_by(RegionDataPoint.year.desc())
            .limit(1)
        )).scalar_one_or_none()
        if common_year is None:
            continue
        vals = dict((await db.execute(
            select(RegionDataPoint.region_id, RegionDataPoint.value)
            .where(RegionDataPoint.indicator_id == ind.id,
                   RegionDataPoint.year == common_year,
                   RegionDataPoint.region_id.in_([region_a.id, region_b.id]))
        )).all())
        va, vb = vals.get(region_a.id), vals.get(region_b.id)
        if va is None or vb is None:
            continue
        va, vb = float(va), float(vb)
        unit = ind.unit or ""

        if abs(va - vb) < 1e-12:
            verdict = "значения совпадают"
            leader_slug = None
        else:
            leader = region_a if va > vb else region_b
            leader_slug = leader.slug
            hi, lo = max(va, vb), min(va, vb)
            diff_pct = (hi - lo) / abs(lo) * 100 if lo else None
            verdict = f"выше в регионе {leader.name}"
            if diff_pct is not None and diff_pct < 200:
                verdict += f" — на {_fmt(round(diff_pct, 1))}%"

        rows.append({
            "code": ind.code,
            "name": ind.name,
            "unit": unit,
            "year": int(common_year),
            "a": {"slug": canon_a, "name": region_a.name, "value": va},
            "b": {"slug": canon_b, "name": region_b.name, "value": vb},
            "verdict": verdict,
            "leader_slug": leader_slug,
        })
        summary_bits.append(f"{ind.name.lower()} — {verdict}")

    if not rows:
        return None

    return {
        "canonical_path": f"/region-vs/{canon_a}-vs-{canon_b}",
        "region_a": {"slug": canon_a, "name": region_a.name},
        "region_b": {"slug": canon_b, "name": region_b.name},
        "rows": rows,
        "summary_bits": summary_bits,
    }

"""Данные сравнения двух регионов — общий слой для SSR и JSON API."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import site_paths as paths
from app.models import Region, RegionDataPoint, RegionIndicator
from app.services.locale import get_locale
from app.services.seo_i18n import region_display_name, region_indicator_copy
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

    name_a = region_display_name(region_a.slug, region_a.name)
    name_b = region_display_name(region_b.slug, region_b.name)

    indicators = (await db.execute(
        select(RegionIndicator)
        .where(RegionIndicator.table_code.in_(_KEY_TABLE_CODES))
        .order_by(RegionIndicator.section_num)
    )).scalars().all()
    if not indicators:
        return None

    # П-21: все точки обоих регионов по всем ключевым показателям — одним
    # запросом (раньше 2 запроса на показатель в цикле: ~20 round-trip'ов
    # на каждую из 190 SSR-страниц пары при cache miss).
    points: dict[int, dict[int, dict[int, float]]] = {}
    all_rows = (await db.execute(
        select(RegionDataPoint.indicator_id, RegionDataPoint.region_id,
               RegionDataPoint.year, RegionDataPoint.value)
        .where(RegionDataPoint.indicator_id.in_([i.id for i in indicators]),
               RegionDataPoint.region_id.in_([region_a.id, region_b.id]))
    )).all()
    for iid, rid, year, value in all_rows:
        points.setdefault(iid, {}).setdefault(int(year), {})[rid] = float(value)

    rows = []
    summary_bits = []
    en = get_locale() == "en"
    for ind in indicators:
        by_year = points.get(ind.id, {})
        common_year = max(
            (y for y, vals in by_year.items()
             if region_a.id in vals and region_b.id in vals),
            default=None,
        )
        if common_year is None:
            continue
        vals = by_year[common_year]
        va, vb = vals.get(region_a.id), vals.get(region_b.id)
        if va is None or vb is None:
            continue
        va, vb = float(va), float(vb)
        copy = region_indicator_copy(
            ind.code,
            name_ru=ind.name,
            unit_ru=ind.unit or "",
            note_ru=ind.note,
            section_ru=ind.section_name,
        )
        unit = copy["unit"] or ""
        ind_name = copy["name"] or ind.name

        if abs(va - vb) < 1e-12:
            verdict = "values are equal" if en else "значения совпадают"
            leader_slug = None
        else:
            leader = region_a if va > vb else region_b
            leader_name = name_a if leader.slug == canon_a else name_b
            leader_slug = leader.slug
            hi, lo = max(va, vb), min(va, vb)
            diff_pct = (hi - lo) / abs(lo) * 100 if lo else None
            if en:
                verdict = f"higher in {leader_name}"
                if diff_pct is not None and diff_pct < 200:
                    verdict += f" — by {_fmt(round(diff_pct, 1))}%"
            else:
                verdict = f"выше в регионе {leader_name}"
                if diff_pct is not None and diff_pct < 200:
                    verdict += f" — на {_fmt(round(diff_pct, 1))}%"

        rows.append({
            "code": ind.code,
            "name": ind_name,
            "unit": unit,
            "year": int(common_year),
            "a": {"slug": canon_a, "name": name_a, "value": va},
            "b": {"slug": canon_b, "name": name_b, "value": vb},
            "verdict": verdict,
            "leader_slug": leader_slug,
        })
        summary_bits.append(
            f"{ind_name.lower()} — {verdict}" if not en
            else f"{ind_name} — {verdict}"
        )

    if not rows:
        return None

    return {
        "canonical_path": paths.region_vs(canon_a, canon_b),
        "region_a": {"slug": canon_a, "name": name_a},
        "region_b": {"slug": canon_b, "name": name_b},
        "rows": rows,
        "summary_bits": summary_bits,
    }

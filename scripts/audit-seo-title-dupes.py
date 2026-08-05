#!/usr/bin/env python3
"""Аудит полных дублей title/description по инвентарю публичных URL.

Детерминированно воспроизводит meta так же, как SSR-билдеры
(`seo_renderer` / `seo_regional` / `seo_today` / `seo_calendar` / `PAGE_META`),
по реестру `site_urls.collect_url_sections` (после фильтра 0be7a9c).

Не краулит HTTP. Нужна локальная Postgres с данными (docker :5434) или
тот же URL, что у backend.

Пример:
  cd backend && \\
  RUSTATS_DATABASE_URL=postgresql+asyncpg://rustats:rustats_dev@localhost:5434/rustats \\
  PYTHONPATH=. ../.venv/bin/python ../scripts/audit-seo-title-dupes.py

Опции:
  --sitemap-file /tmp/seo-dup-audit/all_urls.txt  сверка множества URL с prod sitemap
  --json out.json                                полный dump групп-дублей
  --top N                                        сколько top offenders (default 25)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

# backend/ на PYTHONPATH
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.view_model_families import FAMILY_BY_BASE
from app.database import async_session
from app.models import (
    Indicator,
    IndicatorData,
    Region,
    RegionDataPoint,
    RegionIndicator,
)
from app.services.display import today_msk
from app.services.seo_calendar import _MONTHS_NOM
from app.services.seo_content import CATEGORY_META, PAGE_META
from app.services.seo_regional import (
    _REGIONS_DESC,
    _REGIONS_TITLE,
    _fmt,
)
from app.data.indicator_seo import append_forecast_ssr_desc_tail
from app.services.seo_renderer import (
    _enrich_description,
    _forecast_ssr_enabled,
    clean_text,
)
from app.services.seo_today import (
    TODAY_SPECS,
    _change_phrase,
    _format_number as _today_fmt,
    _ru_date,
    is_stale,
)
from app.services.site_urls import collect_url_sections


@dataclass(frozen=True)
class Meta:
    path: str
    url_class: str
    title: str
    description: str


def classify_path(path: str) -> str:
    if path.startswith("/indicator/") and path.count("/") == 3:
        return "indicator_year"
    if path.startswith("/indicator/"):
        return "indicator"
    if path.startswith("/region-rating/"):
        return "region_rating"
    if path.startswith("/regions/map/"):
        return "regions_map"
    if path == "/regions/map" or path.startswith("/regions/map?"):
        return "regions_map_overview"
    if path.startswith("/region-vs/"):
        return "region_vs"
    if path.startswith("/region/") and path.count("/") >= 3:
        return "region_pair"
    if path.startswith("/region/"):
        return "region_hub"
    if path == "/regions":
        return "regions_home"
    if path.startswith("/today/"):
        return "today"
    if path == "/today":
        return "today_hub"
    if path.startswith("/category/"):
        return "category"
    if re.fullmatch(r"/calendar/\d{4}/\d{2}", path):
        return "calendar_month"
    if path == "/calendar":
        return "calendar"
    return "static"


def path_from_absolute(url: str) -> str:
    p = urlparse(url)
    return p.path or "/"


# ---------------------------------------------------------------------------
# Batch builders (mirror SSR formulas; no HTML)
# ---------------------------------------------------------------------------


async def _latest_by_indicator(
    db: AsyncSession, codes: list[str]
) -> dict[str, tuple[Indicator, IndicatorData | None]]:
    if not codes:
        return {}
    inds = (
        await db.execute(
            select(Indicator).where(Indicator.code.in_(codes), Indicator.is_active.is_(True))
        )
    ).scalars().all()
    by_code = {i.code: i for i in inds}
    ids = [i.id for i in inds]
    if not ids:
        return {c: (by_code[c], None) for c in codes if c in by_code}

    # DISTINCT ON (indicator_id) … ORDER BY date DESC — latest point
    sub = (
        select(
            IndicatorData.indicator_id,
            IndicatorData.date,
            IndicatorData.value,
            func.row_number()
            .over(
                partition_by=IndicatorData.indicator_id,
                order_by=IndicatorData.date.desc(),
            )
            .label("rn"),
        )
        .where(IndicatorData.indicator_id.in_(ids))
        .subquery()
    )
    latest_rows = (
        await db.execute(
            select(sub.c.indicator_id, sub.c.date, sub.c.value).where(sub.c.rn == 1)
        )
    ).all()
    latest_map = {iid: (d, v) for iid, d, v in latest_rows}

    out: dict[str, tuple[Indicator, object | None]] = {}
    for code, ind in by_code.items():
        lv = latest_map.get(ind.id)
        if lv is None:
            out[code] = (ind, None)
            continue

        class _Cur:
            __slots__ = ("date", "value")

            def __init__(self, d, v):
                self.date = d
                self.value = v

        out[code] = (ind, _Cur(*lv))
    return out


async def build_indicator_metas(
    db: AsyncSession, paths: list[str]
) -> list[Meta]:
    codes = [p.split("/", 2)[-1] for p in paths]
    packed = await _latest_by_indicator(db, codes)
    metas: list[Meta] = []
    for path, code in zip(paths, codes):
        pair = packed.get(code)
        if not pair:
            metas.append(Meta(path, "indicator", f"MISSING:{code}", ""))
            continue
        ind, current = pair
        title = ind.seo_title or f"{ind.name} — данные и график"
        desc = (
            ind.seo_description
            or clean_text(
                ind.description,
                f"{ind.name}: динамика, источник, методология и последние значения.",
            )
        )
        if _forecast_ssr_enabled(ind):
            desc = append_forecast_ssr_desc_tail(desc)
        desc = _enrich_description(
            desc, current, ind.unit or "",
            code=ind.code, frequency=ind.frequency,
        )
        metas.append(Meta(path, "indicator", title, desc))
    return metas


async def build_year_metas(db: AsyncSession, paths: list[str]) -> list[Meta]:
    # /indicator/{code}/{year}
    pairs = []
    for p in paths:
        parts = p.strip("/").split("/")
        pairs.append((p, parts[1], int(parts[2])))
    codes = sorted({c for _, c, _ in pairs})
    inds = {
        i.code: i
        for i in (
            await db.execute(
                select(Indicator).where(Indicator.code.in_(codes), Indicator.is_active.is_(True))
            )
        ).scalars().all()
    }
    today_y = today_msk().year
    metas: list[Meta] = []
    for path, code, year in pairs:
        ind = inds.get(code)
        if not ind:
            metas.append(Meta(path, "indicator_year", f"MISSING:{code}/{year}", ""))
            continue
        name = ind.name
        current_year = today_y == year
        title = (
            f"{name} в {year} году — данные с начала года"
            if current_year
            else f"{name} в {year} году — данные по месяцам и итоги"
        )
        # Description includes summary — approximate without per-year aggregates
        # for title-dupe focus; still unique enough via year+name for most cases.
        # Full desc needs row count + annual_summary; pull cheap stats.
        metas.append(Meta(path, "indicator_year", title, f"{name} в {year} году"))
    return metas


async def build_year_metas_full(db: AsyncSession, paths: list[str]) -> list[Meta]:
    """Year titles are template-stable; descriptions need per-year stats.

    For dupe detection on title we don't need desc; for title+desc we build
    a lightweight desc stub that still includes year+name (unique per pair).
    Collisions on title alone are the interesting signal for year pages.
    """
    return await build_year_metas(db, paths)


async def build_region_hub_metas(db: AsyncSession, paths: list[str]) -> list[Meta]:
    slugs = [p.split("/", 2)[-1] for p in paths]
    regions = {
        r.slug: r
        for r in (
            await db.execute(select(Region).where(Region.slug.in_(slugs)))
        ).scalars().all()
    }
    metas = []
    for path, slug in zip(paths, slugs):
        r = regions.get(slug)
        if not r:
            metas.append(Meta(path, "region_hub", f"MISSING:{slug}", ""))
            continue
        title = f"{r.name} — статистика региона: население, зарплата, ВРП, цены"
        desc = (
            f"Социально-экономические показатели региона {r.name}: население, "
            f"зарплата, ВРП, цены, инвестиции — данные Росстата."
        )
        metas.append(Meta(path, "region_hub", title, desc))
    return metas


async def build_region_pair_metas(db: AsyncSession, paths: list[str]) -> list[Meta]:
    """Largest class (~40k). Batch last value via DISTINCT ON."""
    parsed = []
    for p in paths:
        parts = p.strip("/").split("/")  # region, slug, code
        parsed.append((p, parts[1], parts[2]))

    slugs = sorted({s for _, s, _ in parsed})
    codes = sorted({c for _, _, c in parsed})

    regions = {
        r.slug: r
        for r in (
            await db.execute(select(Region).where(Region.slug.in_(slugs)))
        ).scalars().all()
    }
    inds = {
        i.code: i
        for i in (
            await db.execute(select(RegionIndicator).where(RegionIndicator.code.in_(codes)))
        ).scalars().all()
    }

    # last (year, value) per (region_id, indicator_id)
    region_ids = [r.id for r in regions.values()]
    ind_ids = [i.id for i in inds.values()]
    last_map: dict[tuple[int, int], tuple[int, float]] = {}
    if region_ids and ind_ids:
        sub = (
            select(
                RegionDataPoint.region_id,
                RegionDataPoint.indicator_id,
                RegionDataPoint.year,
                RegionDataPoint.value,
                func.row_number()
                .over(
                    partition_by=(RegionDataPoint.region_id, RegionDataPoint.indicator_id),
                    order_by=RegionDataPoint.year.desc(),
                )
                .label("rn"),
            )
            .where(
                RegionDataPoint.region_id.in_(region_ids),
                RegionDataPoint.indicator_id.in_(ind_ids),
            )
            .subquery()
        )
        rows = (
            await db.execute(
                select(
                    sub.c.region_id,
                    sub.c.indicator_id,
                    sub.c.year,
                    sub.c.value,
                ).where(sub.c.rn == 1)
            )
        ).all()
        last_map = {(rid, iid): (int(y), float(v)) for rid, iid, y, v in rows}

    # also need first_year for desc — optional; use last only for speed,
    # desc template still unique via region+indicator+value+year
    metas: list[Meta] = []
    for path, slug, code in parsed:
        r = regions.get(slug)
        ind = inds.get(code)
        if not r or not ind:
            metas.append(Meta(path, "region_pair", f"MISSING:{slug}/{code}", ""))
            continue
        lv = last_map.get((r.id, ind.id))
        if not lv:
            metas.append(Meta(path, "region_pair", f"EMPTY:{slug}/{code}", ""))
            continue
        last_year, last_value = lv
        unit = ind.unit or ""
        title = (
            f"{ind.name} — {r.name}: {_fmt(last_value)} {unit} ({last_year})"
        ).strip()
        desc = (
            f"{ind.name} в регионе {r.name}: {_fmt(last_value)} {unit} "
            f"в {last_year} году. Динамика, график по годам, таблица значений. "
            f"Данные Росстата."
        )
        metas.append(Meta(path, "region_pair", title, desc))
    return metas


async def _region_indicator_last_years(
    db: AsyncSession, codes: list[str]
) -> tuple[dict[str, RegionIndicator], dict[str, int]]:
    inds = {
        i.code: i
        for i in (
            await db.execute(select(RegionIndicator).where(RegionIndicator.code.in_(codes)))
        ).scalars().all()
    }
    if not inds:
        return inds, {}
    rows = (
        await db.execute(
            select(RegionIndicator.code, func.max(RegionDataPoint.year))
            .join(RegionDataPoint, RegionDataPoint.indicator_id == RegionIndicator.id)
            .join(Region, Region.id == RegionDataPoint.region_id)
            .where(
                RegionIndicator.code.in_(list(inds.keys())),
                Region.kind == "region",
            )
            .group_by(RegionIndicator.code)
        )
    ).all()
    return inds, {code: int(y) for code, y in rows}


async def build_rating_metas(db: AsyncSession, paths: list[str]) -> list[Meta]:
    codes = [p.rsplit("/", 1)[-1] for p in paths]
    inds, last_years = await _region_indicator_last_years(db, codes)
    metas = []
    for path, code in zip(paths, codes):
        ind = inds.get(code)
        y = last_years.get(code)
        if not ind or y is None:
            metas.append(Meta(path, "region_rating", f"MISSING:{code}", ""))
            continue
        title = f"Рейтинг регионов России: {ind.name} ({y})"
        desc = (
            f"Рейтинг субъектов РФ по показателю «{ind.name}» за {y} год. "
            f"Данные Росстата."
        )
        metas.append(Meta(path, "region_rating", title, desc))
    return metas


async def build_map_metas(db: AsyncSession, paths: list[str]) -> list[Meta]:
    codes = [p.rsplit("/", 1)[-1] for p in paths]
    inds, last_years = await _region_indicator_last_years(db, codes)
    metas = []
    for path, code in zip(paths, codes):
        ind = inds.get(code)
        y = last_years.get(code)
        if not ind or y is None:
            metas.append(Meta(path, "regions_map", f"MISSING:{code}", ""))
            continue
        title = f"Карта регионов России: {ind.name} ({y})"
        desc = (
            f"Карта субъектов РФ по показателю «{ind.name}» за {y} год. "
            f"Данные Росстата."
        )
        metas.append(Meta(path, "regions_map", title, desc))
    return metas


async def build_today_metas(db: AsyncSession, paths: list[str]) -> list[Meta]:
    metas = []
    today = today_msk()
    for path in paths:
        if path == "/today":
            title = (
                f"Экономика России сегодня, {_ru_date(today)}: "
                f"курсы, ставка, инфляция, цены"
            )
            desc = (
                "Ключевые экономические показатели России на сегодня: курс доллара, "
                "евро и юаня, ключевая ставка ЦБ, инфляция, цена золота и топлива, "
                "индекс МосБиржи. Официальные данные, обновление по мере публикации "
                "источников."
            )
            metas.append(Meta(path, "today_hub", title, desc))
            continue
        code = path.rsplit("/", 1)[-1]
        spec = TODAY_SPECS.get(code)
        if not spec:
            metas.append(Meta(path, "today", f"MISSING:{code}", ""))
            continue
        ind = (
            await db.execute(
                select(Indicator).where(
                    Indicator.code == spec.series_code, Indicator.is_active.is_(True)
                )
            )
        ).scalar_one_or_none()
        if not ind:
            metas.append(Meta(path, "today", f"MISSING:{code}", ""))
            continue
        rows = list(
            (
                await db.execute(
                    select(IndicatorData)
                    .where(IndicatorData.indicator_id == ind.id)
                    .order_by(IndicatorData.date.desc())
                    .limit(2)
                )
            ).scalars().all()
        )
        if len(rows) < 2:
            metas.append(Meta(path, "today", f"EMPTY:{code}", ""))
            continue
        last, prev = rows[0], rows[1]
        unit = (ind.unit or "").strip()
        value_text = f"{_today_fmt(last.value)} {unit}".strip()
        change = _change_phrase(float(last.value), float(prev.value), unit)
        stale = is_stale(ind.frequency, last.date, today)
        if stale:
            title = (
                f"{spec.query} — последнее значение на {_ru_date(last.date)}: "
                f"{value_text}"
            )
        else:
            title = f"{spec.query} сегодня, {_ru_date(today)} — {value_text}"
        fresh_frame = (
            f"последнее доступное значение на {_ru_date(last.date)}" if stale
            else f"данные на {_ru_date(last.date)}"
        )
        desc = (
            f"{spec.query}{' — последнее доступное значение' if stale else ' на сегодня'}: "
            f"{value_text} ({fresh_frame}, {change}). Источник — {ind.source}. "
            f"График, таблица последних значений и прогноз."
        )
        metas.append(Meta(path, "today", title, desc))
    return metas


async def build_region_vs_metas(db: AsyncSession, paths: list[str]) -> list[Meta]:
    # /region-vs/{a}-vs-{b}
    slugs_needed: set[str] = set()
    parsed = []
    for p in paths:
        token = p.rsplit("/", 1)[-1]
        if "-vs-" not in token:
            parsed.append((p, None, None))
            continue
        a, b = token.split("-vs-", 1)
        parsed.append((p, a, b))
        slugs_needed.add(a)
        slugs_needed.add(b)
    regions = {
        r.slug: r
        for r in (
            await db.execute(select(Region).where(Region.slug.in_(slugs_needed)))
        ).scalars().all()
    }
    metas = []
    for path, a, b in parsed:
        ra, rb = regions.get(a or ""), regions.get(b or "")
        if not ra or not rb:
            metas.append(Meta(path, "region_vs", f"MISSING:{path}", ""))
            continue
        title = (
            f"{ra.name} или {rb.name}: сравнение регионов — зарплата, население, цены"
        )
        desc = (
            f"Сравнение регионов {ra.name} и {rb.name}: зарплата, население, цены "
            f"и другие показатели Росстата."
        )
        metas.append(Meta(path, "region_vs", title, desc))
    return metas


def build_static_metas(paths: list[str]) -> list[Meta]:
    by_path = {p.path: p for p in PAGE_META.values()}
    # STATIC_PAGES may include paths not in PAGE_META keys by slug
    metas = []
    for path in paths:
        if path.startswith("/category/"):
            slug = path.rsplit("/", 1)[-1]
            cat = CATEGORY_META.get(slug)
            if cat:
                metas.append(Meta(path, "category", cat.title, cat.description))
            else:
                metas.append(Meta(path, "category", f"MISSING:{slug}", ""))
            continue
        page = by_path.get(path)
        if page:
            cls = "calendar" if path == "/calendar" else "static"
            metas.append(Meta(path, cls, page.title, page.description))
        elif path == "/regions":
            metas.append(Meta(path, "regions_home", _REGIONS_TITLE, _REGIONS_DESC))
        else:
            metas.append(Meta(path, "static", f"UNKNOWN:{path}", ""))
    return metas


def build_calendar_month_metas(paths: list[str]) -> list[Meta]:
    metas = []
    for path in paths:
        # /calendar/YYYY/MM
        parts = path.strip("/").split("/")
        year, month = int(parts[1]), int(parts[2])
        month_nom = _MONTHS_NOM[month - 1]
        title = (
            f"Календарь экономической статистики — {month_nom} {year}: даты публикаций"
        )
        desc = (
            f"Какие данные по экономике России выйдут/вышли в {month_nom} {year}: "
            f"публикации Росстата, Банка России и Минфина."
        )
        metas.append(Meta(path, "calendar_month", title, desc))
    return metas


# ---------------------------------------------------------------------------
# Mode estimate (live URLs not in sitemap)
# ---------------------------------------------------------------------------


def estimate_mode_title_dupes() -> dict:
    """Каждый non-default ?mode= на listed base с seo_title наследует тот же title.

    SSR: `title = indicator.seo_title or f"{display_name} — …"` — seo_title
    берётся раньше суффикса режима → все mode-URL карточки делят title с каноном.
    """
    # CPI / housing / ppi / unemployment / wages / gdp — bespoke; count via
    # frontend constants where cheap, else generic FAMILY_BY_BASE.
    from app.data.view_model_families import FAMILIES

    generic_extra = 0
    generic_bases = 0
    for fam in FAMILIES:
        non_default = [m for m in fam.modes if m.mode != fam.default_mode]
        if not non_default:
            continue
        generic_bases += 1
        generic_extra += len(non_default)

    # Bespoke families (approximate mode counts from known modules)
    # Bespoke (не в FAMILY_BY_BASE): non-default mode counts.
    # CPI: 10 modes на cpi; срезы без step-weekly → 9; минус default.
    bespoke = {
        "cpi": 9,
        "cpi-food": 8,
        "cpi-nonfood": 8,
        "cpi-services": 8,
        "housing-price-primary": 5,
        "housing-price-secondary": 5,
        "ppi": 8,
    }

    return {
        "generic_bases_with_modes": generic_bases,
        "generic_non_default_mode_urls": generic_extra,
        "bespoke_estimate_extra_urls": sum(bespoke.values()),
        "bespoke_detail": bespoke,
        "note": (
            "У карточек с заполненным seo_title все ?mode= наследуют тот же "
            "<title> (проверено SSR key-rate). Description часто отличается "
            "из-за enrichment по data-ряду режима. URL не в sitemap после "
            "0be7a9c, но живые и могут оставаться в индексе Вебмастера."
        ),
    }


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def summarize(metas: list[Meta], *, top_n: int = 25) -> dict:
    by_title: dict[str, list[Meta]] = defaultdict(list)
    by_both: dict[tuple[str, str], list[Meta]] = defaultdict(list)
    for m in metas:
        by_title[m.title].append(m)
        by_both[(m.title, m.description)].append(m)

    title_groups = {t: ms for t, ms in by_title.items() if len(ms) > 1}
    both_groups = {k: ms for k, ms in by_both.items() if len(ms) > 1}

    def extras(groups: dict) -> int:
        return sum(len(ms) - 1 for ms in groups.values())

    def class_breakdown(groups: dict) -> list[tuple[str, int, int]]:
        # per url_class: groups involving it, urls in dup groups, extras
        g_count: Counter[str] = Counter()
        u_count: Counter[str] = Counter()
        for ms in groups.values():
            classes = {m.url_class for m in ms}
            for c in classes:
                g_count[c] += 1
            for m in ms:
                u_count[m.url_class] += 1
        rows = []
        for c, n_urls in u_count.most_common():
            # extras attributed proportionally is messy; report urls in dup groups
            # and groups that touch the class
            rows.append((c, g_count[c], n_urls, n_urls - g_count[c]))  # rough extra
        return rows

    def top_offenders(groups: dict, key_fmt) -> list[dict]:
        ranked = sorted(groups.items(), key=lambda kv: len(kv[1]), reverse=True)
        out = []
        for key, ms in ranked[:top_n]:
            classes = Counter(m.url_class for m in ms)
            out.append({
                "key": key_fmt(key),
                "n": len(ms),
                "extra": len(ms) - 1,
                "classes": dict(classes),
                "sample_paths": [m.path for m in ms[:8]],
            })
        return out

    # Cross-class title collisions (most interesting)
    cross = []
    for t, ms in title_groups.items():
        classes = {m.url_class for m in ms}
        if len(classes) > 1:
            cross.append((t, ms))

    return {
        "total_urls": len(metas),
        "unique_titles": len(by_title),
        "title_dup_groups": len(title_groups),
        "title_urls_in_dup_groups": sum(len(ms) for ms in title_groups.values()),
        "title_extra": extras(title_groups),
        "both_dup_groups": len(both_groups),
        "both_urls_in_dup_groups": sum(len(ms) for ms in both_groups.values()),
        "both_extra": extras(both_groups),
        "title_class_touch": class_breakdown(title_groups),
        "both_class_touch": class_breakdown(both_groups),
        "top_title": top_offenders(title_groups, lambda k: k),
        "top_both": top_offenders(both_groups, lambda k: f"TITLE={k[0]} | DESC={k[1][:120]}…"),
        "cross_class_title_groups": len(cross),
        "cross_class_title_extra": sum(len(ms) - 1 for _, ms in cross),
        "cross_class_samples": [
            {
                "title": t,
                "n": len(ms),
                "classes": dict(Counter(m.url_class for m in ms)),
                "paths": [m.path for m in ms[:10]],
            }
            for t, ms in sorted(cross, key=lambda kv: len(kv[1]), reverse=True)[:15]
        ],
    }


async def collect_all_metas(db: AsyncSession) -> tuple[list[Meta], dict[str, int]]:
    sections = await collect_url_sections(db)
    counts = {k: len(v) for k, v in sections.items()}
    by_class: dict[str, list[str]] = defaultdict(list)
    for urls in sections.values():
        for u in urls:
            by_class[classify_path(u.path)].append(u.path)

    metas: list[Meta] = []
    builders = [
        ("indicator", True, build_indicator_metas),
        ("indicator_year", True, build_year_metas_full),
        ("region_hub", True, build_region_hub_metas),
        ("region_pair", True, build_region_pair_metas),
        ("region_rating", True, build_rating_metas),
        ("regions_map", True, build_map_metas),
        ("today", True, build_today_metas),
        ("today_hub", True, build_today_metas),
        ("region_vs", True, build_region_vs_metas),
        ("calendar_month", False, build_calendar_month_metas),
        ("static", False, build_static_metas),
        ("category", False, build_static_metas),
        ("calendar", False, build_static_metas),
        ("regions_home", False, build_static_metas),
    ]

    for cls, is_async, builder in builders:
        paths = by_class.get(cls, [])
        if not paths:
            continue
        print(f"  building {cls}: {len(paths)}…", flush=True)
        if is_async:
            part = await builder(db, paths)
        else:
            part = builder(paths)
        metas.extend(part)

    # leftover
    known = {m.path for m in metas}
    leftovers = []
    for urls in sections.values():
        for u in urls:
            if u.path not in known:
                leftovers.append(u.path)
    if leftovers:
        print(f"  leftovers: {len(leftovers)} → static builder", flush=True)
        metas.extend(build_static_metas(leftovers))

    return metas, counts


def compare_sitemap(sitemap_file: Path, local_paths: set[str]) -> dict:
    raw = sitemap_file.read_text().splitlines()
    prod = {path_from_absolute(u.strip()) for u in raw if u.strip()}
    return {
        "prod_count": len(prod),
        "local_count": len(local_paths),
        "only_prod": sorted(prod - local_paths)[:30],
        "only_local": sorted(local_paths - prod)[:30],
        "only_prod_n": len(prod - local_paths),
        "only_local_n": len(local_paths - prod),
    }


async def amain(args: argparse.Namespace) -> int:
    print("Collecting URL sections + building meta…", flush=True)
    async with async_session() as db:
        metas, section_counts = await collect_all_metas(db)
        local_paths = {m.path for m in metas}

        # listed indicators for mode estimate context
        listed_codes = (
            await db.execute(
                select(Indicator.code).where(
                    Indicator.is_active.is_(True), Indicator.is_listed.is_(True)
                )
            )
        ).scalars().all()
        listed_with_seo = (
            await db.execute(
                select(Indicator.code, Indicator.seo_title).where(
                    Indicator.is_active.is_(True),
                    Indicator.is_listed.is_(True),
                    Indicator.seo_title.isnot(None),
                    Indicator.seo_title != "",
                )
            )
        ).all()

    print("Summarizing…", flush=True)
    summary = summarize(metas, top_n=args.top)
    summary["section_counts"] = section_counts
    summary["listed_indicators"] = len(listed_codes)
    summary["listed_with_seo_title"] = len(listed_with_seo)
    summary["mode_estimate"] = estimate_mode_title_dupes()

    # Among listed with seo_title: how many are in a generic family
    fam_bases = set(FAMILY_BY_BASE)
    with_seo_in_family = sum(1 for c, _ in listed_with_seo if c in fam_bases)
    summary["listed_seo_title_in_generic_family"] = with_seo_in_family

    # Mode extra that truly share title: non-default modes of listed bases that have seo_title
    mode_share_extra = 0
    for code, _seo in listed_with_seo:
        fam = FAMILY_BY_BASE.get(code)
        if not fam:
            continue
        mode_share_extra += sum(1 for m in fam.modes if m.mode != fam.default_mode)
    summary["mode_estimate"]["listed_seo_title_generic_mode_extra"] = mode_share_extra

    if args.sitemap_file:
        summary["sitemap_compare"] = compare_sitemap(
            Path(args.sitemap_file), local_paths
        )

    # Print report
    print()
    print("=" * 72)
    print("SEO TITLE/DESCRIPTION DUPLICATE AUDIT")
    print("=" * 72)
    print(f"Inventory URLs: {summary['total_urls']}")
    print(f"Unique titles:  {summary['unique_titles']}")
    print()
    print("--- Identical TITLE ---")
    print(f"Dup groups:     {summary['title_dup_groups']}")
    print(f"URLs in groups: {summary['title_urls_in_dup_groups']}")
    print(f"Extra (n-1):    {summary['title_extra']}")
    print()
    print("--- Identical TITLE + DESCRIPTION ---")
    print(f"Dup groups:     {summary['both_dup_groups']}")
    print(f"URLs in groups: {summary['both_urls_in_dup_groups']}")
    print(f"Extra (n-1):    {summary['both_extra']}")
    print()
    print("--- Cross-class title collisions ---")
    print(f"Groups: {summary['cross_class_title_groups']}  "
          f"extra: {summary['cross_class_title_extra']}")
    print()
    print("Section counts:")
    for k, v in section_counts.items():
        print(f"  {k}: {v}")
    print()
    print("Title-dup URLs by class (groups touching / urls / rough extra):")
    print(f"  {'class':22} {'groups':>8} {'urls':>8} {'~extra':>8}")
    for c, g, u, e in summary["title_class_touch"]:
        print(f"  {c:22} {g:8} {u:8} {e:8}")
    print()
    print(f"Top {args.top} title offenders:")
    for i, row in enumerate(summary["top_title"], 1):
        print(f"  {i:2}. n={row['n']} extra={row['extra']}  {row['key'][:90]}")
        print(f"      classes={row['classes']}")
        print(f"      sample={row['sample_paths'][:4]}")
    print()
    if summary["cross_class_samples"]:
        print("Cross-class title samples:")
        for row in summary["cross_class_samples"][:8]:
            print(f"  n={row['n']} classes={row['classes']}")
            print(f"    title={row['title'][:100]}")
            print(f"    paths={row['paths'][:4]}")
    print()
    me = summary["mode_estimate"]
    print("--- ?mode= estimate (not in sitemap) ---")
    print(f"  generic non-default mode URLs: {me['generic_non_default_mode_urls']}")
    print(f"  of which listed+seo_title share title: "
          f"{me.get('listed_seo_title_generic_mode_extra')}")
    print(f"  bespoke estimate extra: {me['bespoke_estimate_extra_urls']} "
          f"({me['bespoke_detail']})")
    print(f"  note: {me['note']}")
    if "sitemap_compare" in summary:
        sc = summary["sitemap_compare"]
        print()
        print("--- Sitemap compare ---")
        print(f"  prod={sc['prod_count']} local={sc['local_count']} "
              f"only_prod={sc['only_prod_n']} only_local={sc['only_local_n']}")
        if sc["only_prod"]:
            print(f"  only_prod sample: {sc['only_prod'][:10]}")
        if sc["only_local"]:
            print(f"  only_local sample: {sc['only_local'][:10]}")

    if args.json:
        # compact: drop full metas, keep summary + small both top
        Path(args.json).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\nWrote {args.json}")

    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sitemap-file", type=str, default=None)
    ap.add_argument("--json", type=str, default=None)
    ap.add_argument("--top", type=int, default=25)
    args = ap.parse_args()
    return asyncio.run(amain(args))


if __name__ == "__main__":
    # Fix append_forecast import — resolve correctly
    sys.exit(main())

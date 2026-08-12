#!/usr/bin/env python3
"""Загрузчик мирового блока Eurostat → world_* таблицы.

Отбор наборов — ЗАПРОСОМ к research.source_catalog (одна точка истины).
Идемпотентный upsert точек (ADR-0002: ON CONFLICT DO UPDATE WHERE value IS
DISTINCT FROM excluded.value). Докачиваемый: повторный запуск дополняет.

Запуск (в контейнере backend или с хоста с RUSTATS_DATABASE_URL)::

    python /app/scripts/load-world-eurostat.py
    python /app/scripts/load-world-eurostat.py --freq M,Q
    python /app/scripts/load-world-eurostat.py --only prc_hicp_midx
    python /app/scripts/load-world-eurostat.py --dry-run --limit 5 --no-cache
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, "/app")

from app.database import async_session  # noqa: E402
from app.models import WorldCountry, WorldDataPoint, WorldIndicator  # noqa: E402
from app.data.eurostat_titles_ru import (  # noqa: E402
    build_public_name,
    category_for_dataset,
    country_prepositional,
    is_listed_for_quality,
    public_description,
    public_methodology,
    public_seo_title,
    resolve_dataset_title,
)
from app.data.eurostat_listing import (  # noqa: E402
    DEEP_DATASET_SLICES,
    meets_listing_depth,
)
from app.data.eurostat_units_ru import (  # noqa: E402
    is_sensitive_topic,
    resolve_public_unit,
    unit_is_listable,
)
from app.data.eurostat_country_visibility import (  # noqa: E402
    EUROSTAT_SUPPRESS_LISTED_CODES,
)
from app.services.eurostat_parser import (  # noqa: E402
    EXCLUDED_GEO_CODES,
    WORLD_COUNTRIES,
    DatasetParseResult,
    DEFAULT_WORKERS,
    fetch_and_parse_dataset,
    fetch_deep_slices,
    make_indicator_code,
)
from app.core.cache import bump_namespaces  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("load-world-eurostat")

DEFAULT_THEMES = (
    "ei_,sts_,prc_,namq_,nama_,une_,lfsi_,lfsq_,irt_,ert_,ext_,bop_,"
    "gov_,demo_,nrg_,road_,tour_,educ_,hlth_,ilc_,isoc_,sdg_,tec,tei,tin,tps"
)

# Приоритет префиксов при нехватке времени.
PRIORITY_PREFIXES = (
    "ei_", "sts_", "prc_", "namq_", "une_", "lfsq_", "irt_", "ert_",
    "ext_", "bop_", "gov_", "nama_",
)

_UPSERT_CHUNK = 3000


def _theme_sql(themes: list[str]) -> tuple[str, dict]:
    """Build OR of prefix matches for dataset_id."""
    clauses = []
    params: dict = {}
    for i, t in enumerate(themes):
        key = f"th{i}"
        params[key] = t.lower() + "%" if not t.endswith("_") and len(t) <= 4 and t.isalpha() else t.lower() + "%"
        # tec/tei/tin/tps — без подчёркивания; остальные как prefix
        if t.rstrip("_") in ("tec", "tei", "tin", "tps"):
            params[key] = t.rstrip("_").lower() + "%"
        else:
            params[key] = t.lower() + "%"
        clauses.append(f"lower(dataset_id) LIKE :{key}")
    return "(" + " OR ".join(clauses) + ")", params


def _priority_rank(dataset_id: str) -> int:
    ds = dataset_id.lower()
    for i, p in enumerate(PRIORITY_PREFIXES):
        if ds.startswith(p):
            return i
    return len(PRIORITY_PREFIXES)


async def select_datasets(
    themes: list[str],
    freqs: list[str],
    *,
    limit: int | None,
    only: str | None,
) -> list[dict]:
    theme_sql, theme_params = _theme_sql(themes)
    freq_params = {f"f{i}": f.upper() for i, f in enumerate(freqs)}
    freq_sql = ", ".join(f":f{i}" for i in range(len(freqs)))

    sql = f"""
        SELECT dataset_id, title, frequency, period_start, period_end, url
        FROM research.source_catalog
        WHERE source = 'eurostat'
          AND period_end IS NOT NULL
          AND period_end >= '2024'
          AND frequency IN ({freq_sql})
          AND {theme_sql}
    """
    params = {**theme_params, **freq_params}
    if only:
        sql += " AND dataset_id = :only"
        params["only"] = only

    async with async_session() as db:
        rows = (await db.execute(text(sql), params)).mappings().all()

    items = [dict(r) for r in rows]
    items.sort(key=lambda r: (_priority_rank(r["dataset_id"]), r["dataset_id"]))
    if limit:
        items = items[:limit]
    return items


async def ensure_countries(geos: set[str]) -> dict[str, int]:
    """Upsert countries; return code → id. Dedup by slug."""
    by_slug: dict[str, tuple[str, tuple]] = {}
    for geo in geos:
        if geo in EXCLUDED_GEO_CODES:
            continue
        meta = WORLD_COUNTRIES.get(geo)
        if not meta:
            continue
        slug = meta[0]
        # Prefer first-seen ISO code for shared slugs (EL over GR)
        if slug not in by_slug:
            by_slug[slug] = (geo, meta)

    async with async_session() as db:
        for slug, (geo, meta) in by_slug.items():
            _slug, name_ru, name_en, region_ru, sort_order = meta
            existing = (
                await db.execute(select(WorldCountry).where(WorldCountry.slug == slug))
            ).scalar_one_or_none()
            if existing:
                existing.name_ru = name_ru
                existing.name_en = name_en
                existing.region_ru = region_ru
                existing.sort_order = sort_order
                # is_active НЕ трогаем: витринный флаг ставит repair-world-listing
                # по порогу покрытия. Loader не должен реанимировать скрытых партнёров.
                if existing.code != geo and geo in ("EL", "UK"):
                    # keep existing code if already set
                    pass
            else:
                # also check by code
                by_code = (
                    await db.execute(select(WorldCountry).where(WorldCountry.code == geo))
                ).scalar_one_or_none()
                if by_code:
                    by_code.slug = slug
                    by_code.name_ru = name_ru
                    by_code.name_en = name_en
                    by_code.region_ru = region_ru
                    by_code.sort_order = sort_order
                else:
                    db.add(WorldCountry(
                        code=geo,
                        slug=slug,
                        name_ru=name_ru,
                        name_en=name_en,
                        region_ru=region_ru,
                        sort_order=sort_order,
                        is_active=True,
                    ))
        await db.commit()

        rows = (await db.execute(select(WorldCountry))).scalars().all()
        return {c.code: c.id for c in rows}


async def reconcile_points(
    db: AsyncSession,
    indicator_id: int,
    points: list[tuple[date, float]],
) -> tuple[int, int]:
    """Синхронизировать полный источник в текущей транзакции.

    Даты, исчезнувшие из успешно распарсенного source-ответа, удаляются только
    для конкретного indicator. Ошибка fetch/parse не вызывает эту функцию и не
    может стереть старый ряд.
    """
    if not points:
        return 0, 0
    touched = 0
    source_dates = [d for d, _ in points]
    for i in range(0, len(points), _UPSERT_CHUNK):
        chunk = points[i : i + _UPSERT_CHUNK]
        values = [
            {"indicator_id": indicator_id, "date": d, "value": v}
            for d, v in chunk
        ]
        stmt = pg_insert(WorldDataPoint).values(values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_world_data_point",
            set_={"value": stmt.excluded.value},
            where=(WorldDataPoint.__table__.c.value.is_distinct_from(stmt.excluded.value)),
        ).returning(WorldDataPoint.id)
        res = await db.execute(stmt)
        touched += len(res.fetchall())

    removed = await db.execute(
        WorldDataPoint.__table__.delete().where(
            WorldDataPoint.indicator_id == indicator_id,
            WorldDataPoint.date.not_in(source_dates),
        )
    )
    return touched, int(removed.rowcount or 0)


async def refresh_indicator_extent(db: AsyncSession, indicator_id: int) -> None:
    """Только фактическая БД определяет историю и count после reconciliation."""
    count, history_start, history_end = (
        await db.execute(
            select(
                func.count(WorldDataPoint.id),
                func.min(WorldDataPoint.date),
                func.max(WorldDataPoint.date),
            ).where(WorldDataPoint.indicator_id == indicator_id)
        )
    ).one()
    ind = await db.get(WorldIndicator, indicator_id)
    if ind is not None:
        ind.points_count = int(count or 0)
        ind.history_start = history_start
        ind.history_end = history_end


async def upsert_indicator_meta(
    db: AsyncSession,
    *,
    country_id: int,
    country_code: str,
    country_name_ru: str,
    result: DatasetParseResult,
    points: list[tuple[date, float]],
    country_slug: str | None = None,
) -> tuple[int, bool]:
    """Create/update WorldIndicator. Returns (id, created)."""
    code = make_indicator_code(country_code, result.dataset_id, result.slice_)
    title = resolve_dataset_title(result.dataset_id, result.title_en)
    unit_ru, _prov = resolve_public_unit(
        dataset_id=result.dataset_id,
        unit_code=result.unit,
        unit_label_en=getattr(result, "unit_label_en", "") or "",
        slice_json=result.slice_,
    )
    unit_ru = unit_ru or ""
    name_ru = build_public_name(
        title.name_ru,
        unit=result.unit,
        slice_json=result.slice_,
        frequency=result.frequency,
        dataset_id=result.dataset_id,
    )
    quality = title.quality
    listed = is_listed_for_quality(quality)
    if listed and (is_sensitive_topic(result.dataset_id) or not unit_is_listable(unit_ru)):
        listed = False
    if listed and not meets_listing_depth(result.frequency, len(points)):
        listed = False
    # National passport countries: eurostat stays in DB but off the vitrine.
    if listed and country_code.strip().upper() in EUROSTAT_SUPPRESS_LISTED_CODES:
        listed = False
    category = category_for_dataset(result.dataset_id)
    hs = points[0][0] if points else None
    he = points[-1][0] if points else None
    prep = country_prepositional(country_slug, country_name_ru)
    # Полный набор частот карточки досклеивается в repair-world-listing;
    # на этапе загрузки знаем только частоту текущего ряда.
    desc = public_description(
        name_ru,
        result.frequency,
        unit_ru,
        country_name_ru=country_name_ru,
        country_prep=prep,
        history_start=hs,
        history_end=he,
        available_frequencies=[result.frequency] if result.frequency else None,
        dataset_id=result.dataset_id or "",
    )
    meth = public_methodology(
        result.frequency,
        unit_ru,
        available_frequencies=[result.frequency] if result.frequency else None,
        dataset_id=result.dataset_id or "",
    )
    seo_title = public_seo_title(
        name_ru, country_prep=prep, country_name_ru=country_name_ru
    )
    seo_kw = (
        f"{name_ru}, {country_name_ru}, {name_ru} в {prep}, "
        f"{country_name_ru} статистика, график"
    )

    existing = (
        await db.execute(
            select(WorldIndicator).where(
                WorldIndicator.provider == "eurostat",
                WorldIndicator.country_id == country_id,
                WorldIndicator.dataset_id == result.dataset_id,
                WorldIndicator.slice_hash == result.slice_hash,
            )
        )
    ).scalar_one_or_none()
    created = False
    if existing is None:
        by_code = (
            await db.execute(select(WorldIndicator).where(WorldIndicator.code == code))
        ).scalar_one_or_none()
        if by_code is not None:
            existing = by_code
        else:
            ind = WorldIndicator(
                country_id=country_id,
                provider="eurostat",
                code=code,
                dataset_id=result.dataset_id,
                slice_json=result.slice_,
                slice_hash=result.slice_hash,
                name_ru=name_ru,
                name_en=result.title_en[:400] if result.title_en else None,
                name_quality=quality,
                unit=result.unit or unit_ru or "",
                unit_ru=unit_ru,
                frequency=result.frequency,
                category_ru=category,
                source="Евростат",
                source_url=result.source_url,
                description=desc,
                methodology=meth,
                history_start=hs,
                history_end=he,
                points_count=len(points),
                is_listed=listed,
                seo_title=seo_title,
                seo_description=desc,
                seo_keywords=seo_kw,
            )
            db.add(ind)
            await db.flush()
            return ind.id, True

    existing.code = code
    existing.provider = "eurostat"
    existing.slice_json = result.slice_
    existing.name_ru = name_ru
    existing.name_en = (result.title_en or "")[:400] or existing.name_en
    existing.name_quality = quality
    existing.unit = result.unit or existing.unit
    existing.unit_ru = unit_ru or existing.unit_ru
    existing.frequency = result.frequency
    existing.category_ru = category
    existing.source = "Евростат"
    existing.source_url = result.source_url
    existing.description = desc
    existing.methodology = meth
    existing.history_start = hs
    existing.history_end = he
    existing.points_count = len(points)
    existing.is_listed = listed
    existing.seo_title = seo_title
    existing.seo_description = desc
    existing.seo_keywords = seo_kw
    await db.flush()
    return existing.id, created


def _parse_one(
    dataset_id: str,
    catalog_freq: str | None,
    *,
    use_cache: bool,
) -> list[DatasetParseResult] | Exception:
    try:
        # Всегда через deep-expand: manual DEEP ∪ независимые разрезы ∪ headline.
        return fetch_deep_slices(dataset_id, use_cache=use_cache)
    except Exception as exc:  # noqa: BLE001
        return exc


async def persist_result(
    result: DatasetParseResult,
    country_ids: dict[str, int],
    country_names: dict[str, str],
) -> tuple[int, int]:
    """Persist one parsed slice atomically; returns (indicators, changed points)."""
    n_ind = 0
    n_pts = 0
    async with async_session() as db:
        async with db.begin():
            for geo, points in result.series_by_geo.items():
                cid = country_ids.get(geo)
                if cid is None:
                    meta = WORLD_COUNTRIES.get(geo)
                    if not meta:
                        continue
                    row = (
                        await db.execute(
                            select(WorldCountry).where(WorldCountry.slug == meta[0])
                        )
                    ).scalar_one_or_none()
                    if row is None:
                        continue
                    cid = row.id
                    country_names[geo] = row.name_ru

                name_ru = country_names.get(geo) or WORLD_COUNTRIES[geo][1]
                slug = (WORLD_COUNTRIES.get(geo) or (None,))[0]
                iid, _ = await upsert_indicator_meta(
                    db,
                    country_id=cid,
                    country_code=geo if geo in ("EL", "GR", "UK", "GB") else geo,
                    country_name_ru=name_ru,
                    country_slug=slug,
                    result=result,
                    points=points,
                )
                ind = await db.get(WorldIndicator, iid)
                if ind is not None:
                    country = await db.get(WorldCountry, ind.country_id)
                    if country is not None:
                        new_code = make_indicator_code(
                            country.code,
                            result.dataset_id,
                            result.slice_,
                        )
                        if ind.code != new_code:
                            clash = (
                                await db.execute(
                                    select(WorldIndicator).where(
                                        WorldIndicator.code == new_code,
                                        WorldIndicator.id != ind.id,
                                    )
                                )
                            ).scalar_one_or_none()
                            if clash is None:
                                ind.code = new_code
                touched, _removed = await reconcile_points(db, iid, points)
                await refresh_indicator_extent(db, iid)
                n_ind += 1
                n_pts += touched
    return n_ind, n_pts


async def run(args: argparse.Namespace) -> int:
    themes = [t.strip() for t in args.themes.split(",") if t.strip()]
    freqs = [f.strip().upper() for f in args.freq.split(",") if f.strip()]
    log.info("Selecting datasets themes=%s freq=%s limit=%s only=%s", themes, freqs, args.limit, args.only)
    datasets = await select_datasets(themes, freqs, limit=args.limit, only=args.only)
    log.info("Selected %d datasets", len(datasets))
    if args.dry_run:
        for d in datasets[:50]:
            log.info("  %s [%s] %s", d["dataset_id"], d["frequency"], (d["title"] or "")[:70])
        if len(datasets) > 50:
            log.info("  ... and %d more", len(datasets) - 50)
        return 0

    # Seed all known countries up front
    await ensure_countries(set(WORLD_COUNTRIES.keys()))
    async with async_session() as db:
        rows = (await db.execute(select(WorldCountry))).scalars().all()
        country_ids = {c.code: c.id for c in rows}
        country_names = {c.code: c.name_ru for c in rows}
        # slug aliases
        for geo, meta in WORLD_COUNTRIES.items():
            slug = meta[0]
            for c in rows:
                if c.slug == slug:
                    country_ids.setdefault(geo, c.id)
                    country_names.setdefault(geo, c.name_ru)

    stats = {
        "datasets_ok": 0,
        "datasets_err": 0,
        "indicators": 0,
        "points": 0,
        "errors": [],
    }
    t0 = time.time()
    workers = max(1, min(args.workers, DEFAULT_WORKERS))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {
            pool.submit(
                _parse_one,
                d["dataset_id"],
                d.get("frequency"),
                use_cache=not args.no_cache,
            ): d
            for d in datasets
        }
        done = 0
        for fut in as_completed(futs):
            meta = futs[fut]
            done += 1
            ds_id = meta["dataset_id"]
            result = fut.result()
            if isinstance(result, Exception):
                stats["datasets_err"] += 1
                stats["errors"].append(f"{ds_id}: {result}")
                log.error("[%d/%d] FAIL %s: %s", done, len(datasets), ds_id, result)
                continue
            results = result if isinstance(result, list) else [result]
            n_ind_total = 0
            n_pts_total = 0
            geos = 0
            for one in results:
                missing = set(one.series_by_geo) - set(country_ids)
                if missing:
                    extra = await ensure_countries(missing)
                    country_ids.update(extra)
                    for g, cid in extra.items():
                        country_names[g] = WORLD_COUNTRIES.get(g, ("", g, g, "", 0))[1]
                n_ind, n_pts = await persist_result(one, country_ids, country_names)
                n_ind_total += n_ind
                n_pts_total += n_pts
                geos = max(geos, len(one.series_by_geo))
            stats["datasets_ok"] += 1
            stats["indicators"] += n_ind_total
            stats["points"] += n_pts_total
            elapsed = time.time() - t0
            log.info(
                "[%d/%d] OK %s slices=%d geos=%d ind=%d pts=%d (%.0fs)",
                done, len(datasets), ds_id, len(results),
                geos, n_ind_total, n_pts_total, elapsed,
            )

    try:
        await bump_namespaces("world")
    except Exception as exc:  # noqa: BLE001
        log.warning("cache bump failed: %s", exc)

    # summary counts from DB
    async with async_session() as db:
        n_countries = (
            await db.execute(
                text("SELECT COUNT(*) FROM world_countries WHERE is_active")
            )
        ).scalar()
        n_indicators = (await db.execute(text("SELECT COUNT(*) FROM world_indicators"))).scalar()
        n_points = (await db.execute(text("SELECT COUNT(*) FROM world_data_points"))).scalar()

    log.info("=" * 60)
    log.info(
        "DONE in %.1f min | datasets ok=%d err=%d | indicators upserted=%d points touched=%d",
        (time.time() - t0) / 60,
        stats["datasets_ok"],
        stats["datasets_err"],
        stats["indicators"],
        stats["points"],
    )
    log.info(
        "DB totals: countries=%s indicators=%s points=%s",
        n_countries, n_indicators, n_points,
    )
    if stats["errors"]:
        log.info("Errors (%d):", len(stats["errors"]))
        for e in stats["errors"][:30]:
            log.info("  %s", e)
    return 0 if stats["datasets_ok"] else 1


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--themes", default=DEFAULT_THEMES, help="Comma-separated dataset_id prefixes")
    p.add_argument("--freq", default="M,Q,A", help="Frequencies: M,Q,A,W,D")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Parallel extraction workers; keep 1 for Eurostat fair use.",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--only", default=None, help="Single dataset_id")
    p.add_argument(
        "--no-cache",
        action="store_true",
        help="Bypass URL-only disk cache (required for changed TOC datasets).",
    )
    args = p.parse_args()
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()

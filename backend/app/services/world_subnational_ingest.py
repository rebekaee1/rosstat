"""Субнациональный ingest: полный ряд FRED + свежие данные BLS → subnational_*.

Отдельный bounded context (ADR-0014). Российский regional (ADR-0008) не трогаем.
Паспорт ``app/data/world_subnational/<cc>.yaml`` — config-driven: никакой
логики ``if country == 'us'``. Пропущенные серии (нет у штата/DC) не валят прогон.

Запуск: ``scripts/load-world-subnational.py --country us``.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import re
import time
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests
import yaml
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models import SubnationalDataPoint, SubnationalIndicator, SubnationalRegion
from app.services.world_adapters.fred_stlouis import (
    FRED_GRAPH_CSV,
    FredStLouisError,
    normalize_series_id,
    parse_fred_csv,
)

logger = logging.getLogger(__name__)

PASSPORT_DIR = Path(__file__).resolve().parents[1] / "data" / "world_subnational"
_HTTP_TIMEOUT = 90.0
_CONCURRENCY = 4
_RETRIES = 3
_BATCH = 2000
_REAL_INCOME_UNITS_RE = re.compile(r"<th[^>]*>Units</th>\s*<td[^>]*>(20\d{2}) C-CPI-U Dollars</td>", re.I)


def fetch_real_income_vintage_sync(series_id: str) -> int:
    """Read FRED's current real-dollar reference year; fail on unknown units."""
    response = requests.get(f"https://fred.stlouisfed.org/data/{series_id}", timeout=25)
    response.raise_for_status()
    match = _REAL_INCOME_UNITS_RE.search(response.text)
    if match is None:
        raise ValueError(f"FRED {series_id}: real income Units metadata missing or changed")
    return int(match.group(1))


def _with_real_income_vintage(passport: SubnationalPassport, vintage: int) -> SubnationalPassport:
    """Keep all 51 state labels aligned with the current FRED reference year."""
    updated = []
    for spec in passport.indicators:
        if spec.code != "median-household-income":
            updated.append(spec)
            continue
        old = re.search(r"USD_(20\d{2})", spec.unit)
        if old is None:
            raise ValueError("median-household-income passport has no real-dollar vintage")
        prior = old.group(1)
        now = str(vintage)
        updated.append(replace(
            spec, unit=f"USD_{now}", unit_en=f"{now} C-CPI-U dollars",
            unit_ru=f"долл. {now} г. (C-CPI-U)",
            description_en=spec.description_en.replace(prior, now),
            description_ru=spec.description_ru.replace(prior, now),
            methodology_en=spec.methodology_en.replace(prior, now),
            methodology_ru=spec.methodology_ru.replace(prior, now),
        ))
    return replace(passport, indicators=tuple(updated))


@dataclass(frozen=True)
class RegionSpec:
    slug: str
    name_en: str
    name_ru: str
    geo_code: str
    fips: str
    kind: str
    sort_order: int


@dataclass(frozen=True)
class IndicatorSpec:
    code: str
    name_en: str
    name_ru: str
    unit: str
    unit_en: str
    unit_ru: str
    frequency: str
    section_en: str
    section_ru: str
    provider: str
    series_template: str
    aggregation: str
    source_en: str
    source_ru: str
    source_url_template: str | None
    national_code: str | None
    value_scale: float
    bls_series_template: str | None
    better_is_low: bool
    is_listed: bool
    description_en: str
    description_ru: str
    methodology_en: str
    methodology_ru: str


@dataclass(frozen=True)
class SubnationalPassport:
    country_code: str
    country_slug: str
    region_kind_label_en: str
    region_kind_label_ru: str
    region_kind_label_en_plural: str
    region_kind_label_ru_plural: str
    default_indicator: str
    featured_indicators: tuple[str, ...]
    map_id: str
    regions: tuple[RegionSpec, ...]
    indicators: tuple[IndicatorSpec, ...]
    path: Path


def passport_path(country: str) -> Path:
    cc = (country or "").strip().lower()
    if not cc:
        raise ValueError("empty country code")
    return PASSPORT_DIR / f"{cc}.yaml"


def country_has_subnational(country_code: str) -> bool:
    """True, если для ISO-кода страны есть паспорт (файл на диске)."""
    cc = (country_code or "").strip().lower()
    if not cc:
        return False
    return passport_path(cc).is_file()


def list_subnational_countries() -> list[str]:
    return sorted(p.stem.upper() for p in PASSPORT_DIR.glob("*.yaml"))


def expand_series_template(
    template: str,
    *,
    geo: str,
    fips: str,
    series_id: str = "",
) -> str:
    """Подстановка плейсхолдеров паспорта. ``{geo}``/``{ST}`` — почтовый код."""
    return (template or "").format(
        geo=geo,
        ST=geo,
        fips=fips,
        series_id=series_id,
    )


def period_key(value: date, frequency: str) -> str:
    if frequency == "annual":
        return str(value.year)
    if frequency == "quarterly":
        return f"{value.year}-Q{(value.month - 1) // 3 + 1}"
    return f"{value.year}-{value.month:02d}"


def period_start(key: str, frequency: str) -> date | None:
    raw = (key or "").strip()
    if not raw:
        return None
    try:
        if frequency == "annual":
            return date(int(raw[:4]), 1, 1)
        if frequency == "quarterly":
            if "-Q" in raw.upper():
                year_s, _, q_s = raw.upper().partition("-Q")
                month = (int(q_s) - 1) * 3 + 1
                return date(int(year_s), month, 1)
            parsed = date.fromisoformat(raw[:10])
            month = ((parsed.month - 1) // 3) * 3 + 1
            return date(parsed.year, month, 1)
        if len(raw) == 7 and raw[4] == "-":
            return date(int(raw[:4]), int(raw[5:7]), 1)
        return date.fromisoformat(raw[:10]).replace(day=1)
    except (TypeError, ValueError):
        return None


def period_label(value: date, frequency: str, locale: str) -> str:
    from app.services.display import format_month_year

    if frequency == "annual":
        return str(value.year)
    if frequency == "quarterly":
        q = (value.month - 1) // 3 + 1
        return f"{value.year} Q{q}" if locale == "en" else f"{q} кв. {value.year}"
    return format_month_year(value, locale=locale)


Mappingish = dict[str, Any]


def _as_str(row: Mappingish, key: str, default: str = "") -> str:
    val = row.get(key, default)
    return "" if val is None else str(val).strip()


def _region_from_row(row: Mappingish, index: int) -> RegionSpec:
    slug = _as_str(row, "slug")
    geo = _as_str(row, "geo_code")
    fips = _as_str(row, "fips").zfill(2) if _as_str(row, "fips") else ""
    if not slug or not geo:
        raise ValueError(f"region[{index}]: slug and geo_code are required")
    kind = _as_str(row, "kind") or "state"
    if kind not in ("state", "district", "territory"):
        raise ValueError(f"region {slug}: unknown kind {kind!r}")
    return RegionSpec(
        slug=slug,
        name_en=_as_str(row, "name_en") or slug,
        name_ru=_as_str(row, "name_ru") or slug,
        geo_code=geo.upper(),
        fips=fips,
        kind=kind,
        sort_order=int(row.get("sort_order") or index),
    )


def _indicator_from_row(row: Mappingish, index: int) -> IndicatorSpec:
    code = _as_str(row, "code")
    template = _as_str(row, "series_template")
    if not code or not template:
        raise ValueError(f"indicator[{index}]: code and series_template required")
    freq = _as_str(row, "frequency") or "annual"
    if freq not in ("monthly", "quarterly", "annual"):
        raise ValueError(f"indicator {code}: bad frequency {freq!r}")
    agg = _as_str(row, "aggregation") or "last"
    if agg not in ("mean", "sum", "last"):
        raise ValueError(f"indicator {code}: bad aggregation {agg!r}")
    value_scale = float(row.get("value_scale", 1.0))
    if not math.isfinite(value_scale) or value_scale <= 0:
        raise ValueError(f"indicator {code}: value_scale must be finite and positive")
    return IndicatorSpec(
        code=code,
        name_en=_as_str(row, "name_en") or code,
        name_ru=_as_str(row, "name_ru") or code,
        unit=_as_str(row, "unit"),
        unit_en=_as_str(row, "unit_en"),
        unit_ru=_as_str(row, "unit_ru"),
        frequency=freq,
        section_en=_as_str(row, "section_en"),
        section_ru=_as_str(row, "section_ru"),
        provider=_as_str(row, "provider") or "fred",
        series_template=template,
        aggregation=agg,
        source_en=_as_str(row, "source_en"),
        source_ru=_as_str(row, "source_ru"),
        source_url_template=_as_str(row, "source_url_template") or None,
        national_code=_as_str(row, "national_code") or None,
        value_scale=value_scale,
        bls_series_template=_as_str(row, "bls_series_template") or None,
        better_is_low=bool(row.get("better_is_low", False)),
        is_listed=bool(row.get("is_listed", True)),
        description_en=_as_str(row, "description_en"),
        description_ru=_as_str(row, "description_ru"),
        methodology_en=_as_str(row, "methodology_en"),
        methodology_ru=_as_str(row, "methodology_ru"),
    )


def load_subnational_passport(country: str) -> SubnationalPassport:
    path = passport_path(country)
    if not path.is_file():
        raise FileNotFoundError(f"subnational passport not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: root must be a mapping")
    cc = _as_str(raw, "country_code").upper()
    if not cc:
        raise ValueError(f"{path}: country_code required")
    regions_raw = raw.get("regions") or []
    indicators_raw = raw.get("indicators") or []
    if not isinstance(regions_raw, list) or not regions_raw:
        raise ValueError(f"{path}: regions list required")
    if not isinstance(indicators_raw, list) or not indicators_raw:
        raise ValueError(f"{path}: indicators list required")
    regions = tuple(_region_from_row(r, i) for i, r in enumerate(regions_raw, 1))
    indicators = tuple(_indicator_from_row(r, i) for i, r in enumerate(indicators_raw, 1))
    slugs = [r.slug for r in regions]
    if len(slugs) != len(set(slugs)):
        raise ValueError(f"{path}: duplicate region slug")
    codes = [i.code for i in indicators]
    if len(codes) != len(set(codes)):
        raise ValueError(f"{path}: duplicate indicator code")
    default = _as_str(raw, "default_indicator") or indicators[0].code
    if default not in codes:
        raise ValueError(f"{path}: default_indicator {default!r} not in indicators")
    featured_raw = raw.get("featured_indicators") or []
    if not isinstance(featured_raw, list) or any(not isinstance(code, str) for code in featured_raw):
        raise ValueError(f"{path}: featured_indicators must be a list of codes")
    featured = tuple(featured_raw)
    if len(featured) != len(set(featured)) or any(code not in codes for code in featured):
        raise ValueError(f"{path}: featured_indicators must be distinct passport codes")
    return SubnationalPassport(
        country_code=cc,
        country_slug=_as_str(raw, "country_slug") or cc.lower(),
        region_kind_label_en=_as_str(raw, "region_kind_label_en") or "Region",
        region_kind_label_ru=_as_str(raw, "region_kind_label_ru") or "Регион",
        region_kind_label_en_plural=_as_str(raw, "region_kind_label_en_plural") or "Regions",
        region_kind_label_ru_plural=_as_str(raw, "region_kind_label_ru_plural") or "Регионы",
        default_indicator=default,
        featured_indicators=featured,
        map_id=_as_str(raw, "map_id") or f"{cc.lower()}-regions",
        regions=regions,
        indicators=indicators,
        path=path,
    )


def fetch_fred_csv_sync(series_id: str) -> list[tuple[date, float]] | None:
    """Скачать FRED graph CSV. None = серии нет (пропуск), [] = пустой ряд."""
    sid = normalize_series_id(series_id)
    last_exc: Exception | None = None
    for attempt in range(_RETRIES):
        try:
            response = requests.get(
                FRED_GRAPH_CSV,
                params={"id": sid},
                timeout=_HTTP_TIMEOUT,
                headers={"Accept": "text/csv,text/plain,*/*"},
            )
        except requests.RequestException as exc:
            last_exc = exc
            time.sleep(0.4 * (attempt + 1))
            continue
        if response.status_code in (400, 404):
            return None
        if response.status_code >= 400:
            last_exc = FredStLouisError(
                f"FRED GET {sid} HTTP {response.status_code}"
            )
            time.sleep(0.4 * (attempt + 1))
            continue
        observations = parse_fred_csv(response.text, series_id=sid)
        return [(item.period, float(item.value)) for item in observations]
    raise FredStLouisError(f"FRED fetch failed for {sid}: {last_exc}")


def fetch_bls_recent_sync(series_ids: list[str]) -> dict[str, list[tuple[date, float]]]:
    """Recent BLS observations; full historical backfill remains in FRED CSV."""
    from app.services.world_adapters.bls_api import BLS_V2_URL, parse_bls_period

    if not series_ids or len(series_ids) > 20:
        raise ValueError("BLS batch must contain 1–20 series")
    year = date.today().year
    request = {
        "seriesid": series_ids,
        "startyear": str(year - 5),
        "endyear": str(year),
    }
    key = os.environ.get("RUSTATS_BLS_API_KEY", "").strip()
    if key:
        request["registrationkey"] = key
    response = requests.post(BLS_V2_URL, json=request, timeout=_HTTP_TIMEOUT)
    response.raise_for_status()
    body = response.json()
    if body.get("status") != "REQUEST_SUCCEEDED":
        raise ValueError(f"BLS request failed: {body.get('status')}")
    rows = body.get("Results", {}).get("series")
    if not isinstance(rows, list):
        raise ValueError("BLS response has no series")
    result: dict[str, list[tuple[date, float]]] = {}
    for row in rows:
        sid = row.get("seriesID")
        if sid not in series_ids:
            raise ValueError(f"unexpected BLS series {sid!r}")
        points = []
        for item in row.get("data", []):
            try:
                period = parse_bls_period(item.get("year"), item.get("period"))
            except (TypeError, ValueError):
                continue
            if period is None or not str(item.get("period", "")).startswith("M"):
                continue
            try:
                value = float(str(item["value"]).replace(",", ""))
            except (KeyError, TypeError, ValueError):
                continue
            if math.isfinite(value):
                points.append((period, value))
        if not points:
            raise ValueError(f"BLS series {sid} has no numeric monthly data")
        result[sid] = sorted(points)
    if set(result) != set(series_ids):
        raise ValueError(f"BLS omitted {sorted(set(series_ids) - set(result))}")
    return result


def merge_and_scale_points(
    historical: list[tuple[date, float]],
    recent: list[tuple[date, float]] | None,
    scale: float,
) -> list[tuple[date, float]]:
    """Keep the historical floor, let the primary publisher revise recent dates."""
    merged = dict(historical)
    merged.update(recent or [])
    return [(period, value * scale) for period, value in sorted(merged.items())]


async def _upsert_regions(db: AsyncSession, passport: SubnationalPassport) -> dict[str, int]:
    ids: dict[str, int] = {}
    for spec in passport.regions:
        stmt = pg_insert(SubnationalRegion).values(
            country_code=passport.country_code,
            slug=spec.slug,
            name_en=spec.name_en,
            name_ru=spec.name_ru,
            kind=spec.kind,
            geo_code=spec.geo_code,
            fips=spec.fips or None,
            sort_order=spec.sort_order,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_subnational_region_country_slug",
            set_={
                "name_en": stmt.excluded.name_en,
                "name_ru": stmt.excluded.name_ru,
                "kind": stmt.excluded.kind,
                "geo_code": stmt.excluded.geo_code,
                "fips": stmt.excluded.fips,
                "sort_order": stmt.excluded.sort_order,
            },
        )
        await db.execute(stmt)
    await db.flush()
    rows = (
        await db.execute(
            select(SubnationalRegion).where(
                SubnationalRegion.country_code == passport.country_code
            )
        )
    ).scalars().all()
    for row in rows:
        ids[row.slug] = row.id
    return ids


async def _upsert_indicators(
    db: AsyncSession, passport: SubnationalPassport, only: str | None,
) -> dict[str, int]:
    specs = passport.indicators
    if only:
        needle = only.strip().lower()
        specs = tuple(s for s in specs if s.code == needle)
        if not specs:
            raise ValueError(f"no indicator with code={only!r}")
    for spec in specs:
        stmt = pg_insert(SubnationalIndicator).values(
            country_code=passport.country_code,
            code=spec.code,
            name_en=spec.name_en,
            name_ru=spec.name_ru,
            unit=spec.unit,
            unit_en=spec.unit_en,
            unit_ru=spec.unit_ru,
            frequency=spec.frequency,
            section_en=spec.section_en,
            section_ru=spec.section_ru,
            provider=spec.provider,
            series_template=spec.series_template,
            aggregation=spec.aggregation,
            description_en=spec.description_en or None,
            description_ru=spec.description_ru or None,
            methodology_en=spec.methodology_en or None,
            methodology_ru=spec.methodology_ru or None,
            source_en=spec.source_en,
            source_ru=spec.source_ru,
            source_url_template=spec.source_url_template,
            is_listed=spec.is_listed,
            national_code=spec.national_code,
            better_is_low=spec.better_is_low,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_subnational_indicator_country_code",
            set_={
                "name_en": stmt.excluded.name_en,
                "name_ru": stmt.excluded.name_ru,
                "unit": stmt.excluded.unit,
                "unit_en": stmt.excluded.unit_en,
                "unit_ru": stmt.excluded.unit_ru,
                "frequency": stmt.excluded.frequency,
                "section_en": stmt.excluded.section_en,
                "section_ru": stmt.excluded.section_ru,
                "provider": stmt.excluded.provider,
                "series_template": stmt.excluded.series_template,
                "aggregation": stmt.excluded.aggregation,
                "description_en": stmt.excluded.description_en,
                "description_ru": stmt.excluded.description_ru,
                "methodology_en": stmt.excluded.methodology_en,
                "methodology_ru": stmt.excluded.methodology_ru,
                "source_en": stmt.excluded.source_en,
                "source_ru": stmt.excluded.source_ru,
                "source_url_template": stmt.excluded.source_url_template,
                "is_listed": stmt.excluded.is_listed,
                "national_code": stmt.excluded.national_code,
                "better_is_low": stmt.excluded.better_is_low,
            },
        )
        await db.execute(stmt)
    await db.flush()
    rows = (
        await db.execute(
            select(SubnationalIndicator).where(
                SubnationalIndicator.country_code == passport.country_code
            )
        )
    ).scalars().all()
    return {row.code: row.id for row in rows}


async def _upsert_points(
    db: AsyncSession,
    indicator_id: int,
    region_id: int,
    points: list[tuple[date, float]],
) -> tuple[int, int]:
    if not points:
        return 0, 0
    added = 0
    updated = 0
    for offset in range(0, len(points), _BATCH):
        chunk = points[offset:offset + _BATCH]
        stmt = pg_insert(SubnationalDataPoint).values([
            {
                "indicator_id": indicator_id,
                "region_id": region_id,
                "period": period,
                "value": value,
            }
            for period, value in chunk
        ])
        stmt = stmt.on_conflict_do_update(
            constraint="uq_subnational_data_point",
            set_={"value": stmt.excluded.value},
            where=(SubnationalDataPoint.value != stmt.excluded.value),
        ).returning(SubnationalDataPoint.id, SubnationalDataPoint.period)
        result = await db.execute(stmt)
        rows = result.all()
        # RETURNING без xmax: считаем все затронутые как upserted.
        updated += len(rows)
    added = max(0, updated)  # отчётный счётчик «записано»
    return added, updated


@dataclass
class SeriesReport:
    indicator: str
    region: str
    series_id: str
    status: str  # loaded | skipped | error
    points: int = 0
    first: date | None = None
    last: date | None = None
    detail: str = ""


async def ingest_country(
    country: str,
    *,
    only: str | None = None,
    db: AsyncSession | None = None,
) -> list[SeriesReport]:
    passport = load_subnational_passport(country)
    if any(
        spec.code == "median-household-income"
        for spec in passport.indicators
    ) and (only is None or only.strip().lower() == "median-household-income"):
        vintage = await asyncio.to_thread(
            fetch_real_income_vintage_sync, "MEHOINUSCAA672N",
        )
        passport = _with_real_income_vintage(passport, vintage)
    own_session = db is None

    async def _run(session: AsyncSession) -> list[SeriesReport]:
        region_ids = await _upsert_regions(session, passport)
        indicator_ids = await _upsert_indicators(session, passport, only)
        await session.commit()
        specs = passport.indicators
        if only:
            needle = only.strip().lower()
            specs = tuple(s for s in specs if s.code == needle)

        jobs = [
            (ind, region, expand_series_template(
                ind.series_template, geo=region.geo_code, fips=region.fips,
            ))
            for ind in specs
            for region in passport.regions
        ]
        sem = asyncio.Semaphore(_CONCURRENCY)

        async def _fetch(series_id: str) -> list[tuple[date, float]] | None:
            async with sem:
                return await asyncio.to_thread(fetch_fred_csv_sync, series_id)

        logger.info("fetching %s FRED series (concurrency=%s)", len(jobs), _CONCURRENCY)
        fetched = await asyncio.gather(
            *(_fetch(series_id) for _, _, series_id in jobs),
            return_exceptions=True,
        )
        bls_by_fred_id: dict[str, list[tuple[date, float]]] = {}
        bls_errors: dict[str, str] = {}
        bls_ids = {
            series_id: expand_series_template(
                ind.bls_series_template,
                geo=region.geo_code,
                fips=region.fips,
            )
            for ind, region, series_id in jobs if ind.bls_series_template
        }
        recent_items = list(bls_ids.items())
        for offset in range(0, len(recent_items), 20):
            batch = recent_items[offset:offset + 20]
            try:
                current = await asyncio.to_thread(
                    fetch_bls_recent_sync, [sid for _, sid in batch]
                )
                for fred_id, bls_id in batch:
                    bls_by_fred_id[fred_id] = current[bls_id]
            except Exception as exc:
                logger.warning("BLS recent batch failed: %s", exc)
                for fred_id, _ in batch:
                    bls_errors[fred_id] = str(exc)[:300]
        out: list[SeriesReport] = []
        for i, ((ind, region, series_id), payload) in enumerate(zip(jobs, fetched), 1):
            if isinstance(payload, Exception):
                out.append(SeriesReport(
                    ind.code, region.slug, series_id, "error",
                    detail=str(payload)[:300],
                ))
                continue
            if payload is None:
                out.append(SeriesReport(
                    ind.code, region.slug, series_id, "skipped",
                    detail="series missing at source",
                ))
                continue
            if not payload:
                out.append(SeriesReport(
                    ind.code, region.slug, series_id, "skipped",
                    detail="empty series",
                ))
                continue
            iid = indicator_ids[ind.code]
            rid = region_ids[region.slug]
            scaled = merge_and_scale_points(
                payload, bls_by_fred_id.get(series_id), ind.value_scale,
            )
            n, _ = await _upsert_points(session, iid, rid, scaled)
            await session.commit()
            out.append(SeriesReport(
                ind.code, region.slug, series_id,
                "error" if series_id in bls_errors else "loaded",
                points=n, first=scaled[0][0], last=scaled[-1][0],
                detail=f"BLS recent overlay failed: {bls_errors[series_id]}" if series_id in bls_errors else "",
            ))
            if i % 10 == 0 or i == len(jobs):
                logger.info("upsert progress %s/%s", i, len(jobs))
        return out

    if own_session:
        async with async_session() as session:
            return await _run(session)
    assert db is not None
    return await _run(db)


async def world_subnational_ingest_job() -> None:
    """Ежедневное обновление всех паспортов в ``world_subnational/``."""
    started = datetime.now(timezone.utc)
    countries = list_subnational_countries()
    logger.info("world_subnational ingest start countries=%s", countries)
    touched = 0
    failures: list[str] = []
    checked = loaded_total = skipped_total = error_total = 0
    for cc in countries:
        try:
            reports = await ingest_country(cc.lower())
            loaded = sum(1 for r in reports if r.status == "loaded")
            skipped = sum(1 for r in reports if r.status == "skipped")
            errors = sum(1 for r in reports if r.status == "error")
            checked += len(reports)
            loaded_total += loaded
            skipped_total += skipped
            error_total += errors
            touched += sum(r.points for r in reports)
            logger.info(
                "world_subnational %s loaded=%s skipped=%s errors=%s",
                cc, loaded, skipped, errors,
            )
            if errors:
                logger.error("world_subnational %s had %s failed series", cc, errors)
                failures.append(f"{cc}:{errors}")
        except Exception:
            logger.exception("world_subnational ingest failed for %s", cc)
            failures.append(cc)
            error_total += 1
    # Passport metadata can change even when every numeric observation is stable.
    if countries:
        try:
            from app.core.cache import bump_namespaces

            await bump_namespaces("world", "ssr-world", "world-catalog")
        except Exception:
            logger.warning("world_subnational cache bump failed", exc_info=True)
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    logger.info("world_subnational ingest done in %.1fs points_touched=%s", elapsed, touched)
    from app.services.alerting import alert_world_ingest_summary

    await alert_world_ingest_summary(
        "США: штаты, FRED/BLS",
        status="partial" if failures else "ok",
        checked=checked, changed=touched, failed=error_total,
        checked_label="Проверено рядов",
        changed_label="Изменено точек",
        details=(
            f"Рядов загружено: {loaded_total}; пропущено: {skipped_total}; "
            f"изменённых точек: {touched}; время: {elapsed:.0f} с. "
            + (f"Ошибки: {', '.join(failures[:15])}" if failures else "")
        ).strip(),
    )
    if failures:
        raise RuntimeError(f"world_subnational ingest failures: {', '.join(failures)}")

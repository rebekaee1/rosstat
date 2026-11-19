"""Зарплата, пенсия и рождаемость по регионам помесячно (ЕМИСС 57824, 61699, 61698, 62852, 62853; 19.11.2026).

Реестр рядов — ``app.data.emiss_regional_social``. Пишет в ``region_monthly_data`` теми же средствами, что цены
ЕМИСС 31448 (``emiss_regional_parser``): транспорт ``_post_grid`` (прямой ход → HTTP-прокси → SOCKS; адресу прода
fedstat отвечает 403), запись ``_upsert_monthly_points`` (ON CONFLICT с guard ``value <> excluded.value``),
региональная advisory-блокировка и границы истории в той же транзакции, публикация кэша после commit.

Один запрос на ряд: строки — территория и год, столбцы — месяцы. Территории перечисляются явно (источник не
отдаёт «все»): oid берутся из ``regional/emiss_social_territories.json`` (снято со страниц показателей 08–09.11.2026).
В ответе территория приходит названием; название → slug — общий справочник ``emiss_dimnames.json`` плюс
``TERRITORY_ALIASES`` (межведомственный ОКАТО Соцфонда пишет названия иначе).

Россия у наборов Росстата (57824, 62852, 62853): до 2022 года — строка «Российская Федерация», с 2023 года — «без
учёта новых субъектов» (если строки нет, берётся другая). У наборов Соцфонда (61699, 61698) строка одна.

Первая загрузка ряда — вся история с первого года набора; дальше — год последней точки, предыдущий (ревизии) и
новые. Ячейка вне границ здравого смысла пропускается и считается в ``rejected``; незнакомое название территории
считается в ``unknown_territories`` — ряд от этого не падает. Ответ со строками, но без единой точки, — смена
формата: ``EmissFormatError``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import date
from math import isfinite
from pathlib import Path
from typing import Callable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import publish_committed_regional_changes
from app.data.emiss_regional_social import (
    DATASETS, RUSSIA, RUSSIA_WITHOUT_NEW, SERIES, TERRITORY_ALIASES, TERRITORY_SKIP, Dataset, SocialSeries,
)
from app.database import async_session
from app.models import Region, RegionIndicator, RegionMonthlyPoint
from app.services.emiss_regional_parser import (
    EmissFormatError, _post_grid, _upsert_monthly_points, load_dimnames, parse_ru_float,
)
from app.services.regional_storage import acquire_regional_write_lock, update_regional_year_bounds

logger = logging.getLogger(__name__)

_TERRITORIES_PATH = Path(__file__).resolve().parents[1] / "data" / "regional" / "emiss_social_territories.json"
_PAUSE_BETWEEN_REQUESTS = 0.4
_ALERT_MUTE_S = 3 * 24 * 3600


def load_territories(path: Path = _TERRITORIES_PATH) -> dict[str, list[str]]:
    """Набор → oid всех его территорий (ключ — номер набора строкой)."""
    return json.loads(path.read_text(encoding="utf-8"))


def territory_slugs(dimnames: dict[str, str] | None = None) -> dict[str, str]:
    """Название территории в ответе → slug сайта (Россия обрабатывается отдельно)."""
    out = dict(dimnames if dimnames is not None else load_dimnames())
    out.update(TERRITORY_ALIASES)
    return out


def build_params(dataset: Dataset, series: SocialSeries, territories: list[str], years: range) -> list[tuple[str, str]]:
    lines = [dataset.territory_dim] + ([dataset.series_dim] if dataset.series_dim else []) + ["3"]
    filters = [f"0_{dataset.id}", f"30611_{dataset.unit_oid}",
               *(f"{dataset.territory_dim}_{oid}" for oid in territories),
               *(f"3_{year}" for year in years), *(f"33560_{oid}" for oid in dataset.months),
               *(f"{dim}_{oid}" for dim, oid in dataset.fixed)]
    if dataset.series_dim and series.member:
        filters.append(f"{dataset.series_dim}_{series.member}")
    return [*(("lineObjectIds", dim) for dim in lines), ("columnObjectIds", "33560"),
            *(("selectedFilterIds", value) for value in filters)]


def _month(key: str, months: dict[str, int]) -> int | None:
    if not key.startswith("dim") or "_d" not in key:
        return None
    return months.get(key[3:].split("_", 1)[0])


def parse_payload(
    payload: dict, dataset: Dataset, slugs: dict[str, str],
) -> tuple[list[tuple[str, int, float]], dict[str, int]]:
    """Ответ dataGrid.do → [(slug, YYYYMM, value)] и счётчики пропусков."""
    rows = payload.get("results")
    if not isinstance(rows, list):
        raise ValueError(f"ЕМИСС {dataset.id}: нет массива результатов")
    points: dict[tuple[str, int], float] = {}
    russia: dict[int, dict[str, float]] = {}
    rejected = 0
    unknown: set[str] = set()
    for row in rows:
        name = str(row.get(f"dim{dataset.territory_dim}") or "").strip()
        year_text = str(row.get("dim3") or "").strip()
        if not year_text.isdigit():
            raise ValueError(f"ЕМИСС {dataset.id}: строка без года {row!r:.200}")
        if name in TERRITORY_SKIP:
            continue
        is_russia = name in (RUSSIA, RUSSIA_WITHOUT_NEW)
        slug = None if is_russia else slugs.get(name)
        if not is_russia and not slug:
            unknown.add(name)
            continue
        for key, raw in row.items():
            month = _month(key, dataset.months)
            if month is None or raw in (None, "", "-", "—"):
                continue
            value = parse_ru_float(raw)
            if value is None or not isfinite(value):
                rejected += 1
                continue
            value = round(value * dataset.scale, 3) if dataset.scale != 1.0 else value
            if not dataset.min_value <= value <= dataset.max_value:
                rejected += 1
                continue
            period = int(year_text) * 100 + month
            if is_russia:
                russia.setdefault(period, {})[name] = value
            else:
                points[(slug, period)] = value
    for period, values in russia.items():
        order = (RUSSIA_WITHOUT_NEW, RUSSIA) if period >= 202300 else (RUSSIA, RUSSIA_WITHOUT_NEW)
        points[("russia", period)] = next(values[n] for n in order if n in values)
    if rows and not points:
        raise EmissFormatError(f"ЕМИСС {dataset.id}: ответ содержит {len(rows)} строк, ни одна точка не разобрана")
    stats = {"rejected": rejected, "unknown_territories": len(unknown)}
    if unknown:
        logger.warning("emiss_social %s: незнакомые территории %s", dataset.id, sorted(unknown)[:5])
    return [(slug, period, value) for (slug, period), value in sorted(points.items())], stats


async def fetch_series(
    series: SocialSeries, years: range, *, territories: dict[str, list[str]], slugs: dict[str, str],
    post_grid: Callable | None = None,
) -> tuple[list[tuple[str, int, float]], dict[str, int]]:
    dataset = DATASETS[series.dataset]
    payload = await (post_grid or _post_grid)(
        dataset.id, build_params(dataset, series, territories[str(dataset.id)], years),
    )
    return parse_payload(payload, dataset, slugs)


async def run_emiss_social_update(
    db: AsyncSession, *, post_grid: Callable | None = None, today: date | None = None,
) -> dict[str, int]:
    today = today or date.today()
    territories = load_territories()
    slugs = territory_slugs()
    indicators = {
        ind.code: ind for ind in (await db.execute(
            select(RegionIndicator).where(RegionIndicator.code.in_([s.code for s in SERIES]))
        )).scalars()
    }
    regions = {slug: rid for slug, rid in (await db.execute(select(Region.slug, Region.id))).all()}
    stats = {"series": 0, "added": 0, "updated": 0, "rejected": 0, "unknown_territories": 0, "failed": 0}
    for series in SERIES:
        indicator = indicators.get(series.code)
        if indicator is None:
            # Метаданные приходят из indicators.json при старте (seed_regional): до него ряд пропускается.
            logger.warning("emiss_social: нет метаданных показателя %s, пропуск", series.code)
            continue
        dataset = DATASETS[series.dataset]
        latest = await db.scalar(
            select(func.max(RegionMonthlyPoint.month)).where(RegionMonthlyPoint.indicator_id == indicator.id)
        )
        first_year = max(dataset.first_year, int(latest) // 100 - 1) if latest else dataset.first_year
        try:
            points, part = await fetch_series(
                series, range(first_year, today.year + 1), territories=territories, slugs=slugs, post_grid=post_grid,
            )
        except EmissFormatError as exc:
            logger.warning("emiss_social: %s", exc)
            stats["failed"] += 1
            continue
        values = [(indicator.id, regions[slug], period, value) for slug, period, value in points if slug in regions]
        try:
            await acquire_regional_write_lock(db)
            added = updated = 0
            if values:
                added, updated = await _upsert_monthly_points(db, values)
            metadata_changed = await update_regional_year_bounds(db, {indicator.id})
            await db.commit()
        except BaseException:
            await db.rollback()
            raise
        if added or updated or metadata_changed:
            await publish_committed_regional_changes()
        stats["series"] += 1
        stats["added"] += added
        stats["updated"] += updated
        stats["rejected"] += part["rejected"]
        stats["unknown_territories"] = max(stats["unknown_territories"], part["unknown_territories"])
        logger.info("emiss_social: %s %d точек (added=%d updated=%d)", series.code, len(values), added, updated)
        await asyncio.sleep(_PAUSE_BETWEEN_REQUESTS)
    return stats


async def emiss_social_job() -> dict[str, int]:
    """Точка входа планировщика."""
    started = time.monotonic()
    try:
        async with async_session() as db:
            stats = await run_emiss_social_update(db)
        if stats["failed"] or stats["unknown_territories"]:
            from app.services.alerting import alert_muted, send_telegram

            if not await alert_muted("emiss_social:partial", _ALERT_MUTE_S):
                await send_telegram(
                    "🟡 <b>Зарплата, пенсии, рождаемость по регионам: обновлено не всё</b> — "
                    f"рядов без разбора: {stats['failed']}, незнакомых территорий: {stats['unknown_territories']}.",
                    kind="etl_alert",
                )
        logger.info("emiss_social_job done in %.1fs: %s", time.monotonic() - started, stats)
        return stats
    except Exception as exc:
        logger.exception("emiss_social_job failed")
        from html import escape

        from app.services.alerting import alert_muted, exception_reason, send_telegram

        try:
            if not await alert_muted("emiss_social:failed", _ALERT_MUTE_S):
                await send_telegram(
                    "🔴 <b>Парсер зарплат, пенсий и рождаемости по регионам упал</b>\n"
                    f"Причина: {escape(exception_reason(exc, 300))}",
                    kind="etl_alert",
                )
        except Exception:  # noqa: BLE001 — алерт не должен маскировать исключение
            pass
        raise

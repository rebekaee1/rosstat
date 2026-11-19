"""Помесячные региональные наборы ЕМИСС 57693, 34118, 57806, 31076 (реестр — ``app.data.emiss_regional_sets``).

Пишет в ``region_monthly_data`` — тот же слой, что цены 31448, и тем же способом: транспорт ``_post_grid``
(прямой ход → HTTP-прокси → SOCKS; адресу прода fedstat отвечает 403), upsert с guard ``value <> excluded.value``
(ADR-0002), advisory-блокировка регионального контура, границы истории в метаданных, публикация кэша после commit.

Один запрос — один год одного набора: строки — позиция × территория, столбцы — 12 месяцев (ключ ячейки несёт oid
месяца, поэтому месяцы в одном ответе не схлопываются). Территории — тот же справочник ОКАТО, что у 31448
(85 субъектов, округа и Россия); в ответе территория приходит названием.

Россия: до 2022 года — строка «Российская Федерация», с 2023 года — «без учета новых субъектов»; если за месяц
есть только одна из двух, берётся она (обе пишутся в slug ``russia``).

План: набор без единой точки (первый запуск после выпуска) грузится с первого года истории; дальше — год самой
ранней из последних точек рядов набора минус один (ревизии) и до текущего. Отсутствующий месяц не стирает
сохранённую историю. Значение вне границ набора пропускается и попадает в статистику ``rejected``.
"""

from __future__ import annotations

import asyncio
import html
import logging
import re
import time
from datetime import date
from math import isfinite
from typing import Callable, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import publish_committed_regional_changes
from app.data.emiss_regional_sets import SETS, TERRITORY_DIM, RegionalSet
from app.models import Region, RegionIndicator, RegionMonthlyPoint
from app.services.emiss_regional_parser import (
    _PAUSE_BETWEEN_REQUESTS, _RUSSIA_LEGACY, MONTH_OIDS, _post_grid, _upsert_monthly_points,
    load_dimnames, load_territory_ids, parse_ru_float,
)
from app.services.regional_storage import acquire_regional_write_lock, update_regional_year_bounds

logger = logging.getLogger(__name__)

_RUSSIA_LEGACY_NAME = "Российская Федерация"
# Краснодарский край с федеральной территорией «Сириус»: в части наборов с 2026 года месяцы идут этой строкой
# (ввод жилья 34118 с мая 2026), в части — обеими строками параллельно. Берётся только там, где обычной строки
# «Краснодарский край» за месяц нет, чтобы ряд не прыгал между двумя охватами.
_FALLBACK_TERRITORIES = {"1856621": "krasnodarskiy-kray"}
_FALLBACK_NAMES = {"краснодарский край (с учетом фт «сириус»)": "krasnodarskiy-kray"}
_SPACES = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _SPACES.sub(" ", html.unescape(str(text or "")).replace("\xa0", " ")).strip().casefold()


def _month(key: str) -> int | None:
    """Месяц из ключа ячейки ``dim<oid месяца>_d…_i…``; «январь–март», «I квартал» и т. п. — None."""
    if not key.startswith("dim") or "_d" not in key:
        return None
    return MONTH_OIDS.get(key[3:].split("_", 1)[0])


def build_params(rset: RegionalSet, year: int, territory_ids: Sequence[str]) -> list[tuple[str, str]]:
    params: list[tuple[str, str]] = [("lineObjectIds", rset.series_dim)]
    params += [("lineObjectIds", dim) for dim in rset.extra_lines]
    params += [("lineObjectIds", TERRITORY_DIM), ("columnObjectIds", "33560")]
    filters = [f"0_{rset.dataset}", f"3_{year}", *rset.filters]
    filters += [f"33560_{oid}" for oid in MONTH_OIDS]
    filters += [f"{rset.series_dim}_{oid}" for s in rset.series for oid in s.oids]
    filters += [f"{TERRITORY_DIM}_{oid}" for oid in territory_ids]
    filters += [f"{TERRITORY_DIM}_{oid}" for oid in _FALLBACK_TERRITORIES if oid not in territory_ids]
    if _RUSSIA_LEGACY not in territory_ids:
        filters.append(f"{TERRITORY_DIM}_{_RUSSIA_LEGACY}")
    params += [("selectedFilterIds", value) for value in filters]
    return params


def parse_year(
    rset: RegionalSet, payload: dict, year: int, dimnames: dict[str, str],
) -> tuple[list[tuple[str, str, int, float]], int]:
    """Ответ dataGrid.do за год → ([(code, slug, YYYYMM, value)], число отброшенных значений)."""
    rows = payload.get("results")
    if not isinstance(rows, list):
        raise ValueError(f"ЕМИСС {rset.dataset}: нет массива результатов")
    by_label = {_norm(s.label): s.code for s in rset.series}
    russia: dict[tuple[str, int], dict[bool, float]] = {}
    out: dict[tuple[str, str, int], float] = {}
    fallback: dict[tuple[str, str, int], float] = {}
    rejected = 0
    for row in rows:
        code = by_label.get(_norm(row.get(f"dim{rset.series_dim}")))
        territory = str(row.get(f"dim{TERRITORY_DIM}") or "").strip()
        slug = dimnames.get(territory)
        spare = slug is None and (slug := _FALLBACK_NAMES.get(_norm(territory))) is not None
        if code is None or slug is None:
            continue
        legacy = territory in (_RUSSIA_LEGACY, _RUSSIA_LEGACY_NAME)
        for key, raw in row.items():
            month = _month(key)
            if month is None or raw in (None, "", "-", "—"):
                continue
            value = parse_ru_float(raw)
            if value is None or not isfinite(value):
                rejected += 1
                continue
            if value == 0 and rset.min_value > 0:
                continue  # цена или индекс «0» — продаж за месяц не было, это пропуск, а не значение
            value *= rset.scale
            if not rset.min_value <= value <= rset.max_value:
                rejected += 1
                continue
            period = year * 100 + month
            if slug == "russia":
                russia.setdefault((code, period), {})[legacy] = value
            elif spare:
                fallback[(code, slug, period)] = value
            else:
                out[(code, slug, period)] = value
    for (code, period), values in russia.items():
        prefer_legacy = period // 100 < 2023
        value = values.get(prefer_legacy, values.get(not prefer_legacy))
        out[(code, "russia", period)] = value
    for key, value in fallback.items():
        out.setdefault(key, value)
    return [(code, slug, period, value) for (code, slug, period), value in out.items()], rejected


async def fetch_year(
    rset: RegionalSet, year: int, territory_ids: Sequence[str], dimnames: dict[str, str],
    *, post_grid: Callable | None = None,
) -> tuple[list[tuple[str, str, int, float]], int]:
    payload = await (post_grid or _post_grid)(rset.dataset, build_params(rset, year, territory_ids))
    return parse_year(rset, payload, year, dimnames)


def years_to_fetch(rset: RegionalSet, last_by_code: dict[str, int | None], today: date | None = None) -> range:
    """Годы запроса: вся история, если у какого-то ряда набора нет точек; иначе от самой ранней последней точки − 1."""
    today = today or date.today()
    lasts = [last_by_code.get(s.code) for s in rset.series]
    if any(last is None for last in lasts):
        start = rset.first_year
    else:
        start = max(rset.first_year, min(lasts) // 100 - 1)
    return range(start, today.year + 1)


async def run_set_update(
    db: AsyncSession, rset: RegionalSet, *, post_grid: Callable | None = None,
    territory_ids: Sequence[str] | None = None, dimnames: dict[str, str] | None = None,
    today: date | None = None,
) -> dict[str, int]:
    dimnames = dimnames if dimnames is not None else load_dimnames()
    territory_ids = territory_ids if territory_ids is not None else load_territory_ids()
    codes = [s.code for s in rset.series]
    indicators = {
        ind.code: ind for ind in (await db.execute(
            select(RegionIndicator).where(RegionIndicator.code.in_(codes))
        )).scalars()
    }
    if not indicators:
        raise RuntimeError(f"ЕМИСС {rset.dataset}: нет метаданных показателей (сид регионов не прошёл)")
    regions = {slug: rid for slug, rid in (await db.execute(select(Region.slug, Region.id))).all()}
    last_rows = (await db.execute(
        select(RegionMonthlyPoint.indicator_id, func.max(RegionMonthlyPoint.month))
        .where(RegionMonthlyPoint.indicator_id.in_([i.id for i in indicators.values()]))
        .group_by(RegionMonthlyPoint.indicator_id)
    )).all()
    by_id = {ind.id: code for code, ind in indicators.items()}
    last_by_code: dict[str, int | None] = {code: None for code in indicators}
    last_by_code.update({by_id[iid]: int(m) for iid, m in last_rows})

    added = updated = rejected = 0
    years = years_to_fetch(rset, last_by_code, today)
    for year in years:
        points, bad = await fetch_year(rset, year, territory_ids, dimnames, post_grid=post_grid)
        rejected += bad
        values = [
            (indicators[code].id, regions[slug], period, value)
            for code, slug, period, value in points
            if code in indicators and slug in regions
        ]
        year_added = year_updated = 0
        metadata_changed = 0
        try:
            await acquire_regional_write_lock(db)
            affected: set[int] = set()
            for start in range(0, len(values), 5_000):
                chunk = values[start:start + 5_000]
                a, u = await _upsert_monthly_points(db, chunk)
                year_added += a
                year_updated += u
                affected.update(v[0] for v in chunk)
            if affected:
                metadata_changed = await update_regional_year_bounds(db, affected)
            await db.commit()
        except BaseException:
            await db.rollback()
            raise
        added += year_added
        updated += year_updated
        if year_added or year_updated or metadata_changed:
            await publish_committed_regional_changes()
        logger.info("emiss_regional_sets %s: %d — %d точек (added=%d updated=%d)",
                    rset.dataset, year, len(points), year_added, year_updated)
        await asyncio.sleep(_PAUSE_BETWEEN_REQUESTS)
    return {"years": len(years), "added": added, "updated": updated, "rejected": rejected}


_ALERT_MUTE_S = 3 * 24 * 3600


async def emiss_regional_sets_job() -> dict[str, dict[str, int]]:
    """Точка входа планировщика: наборы обновляются по очереди, сбой одного не останавливает остальные."""
    from app.database import async_session

    started = time.monotonic()
    stats: dict[str, dict[str, int]] = {}
    failures: list[str] = []
    for rset in SETS:
        try:
            async with async_session() as db:
                stats[str(rset.dataset)] = await run_set_update(db, rset)
        except Exception as exc:  # noqa: BLE001 — один набор не должен ронять остальные
            logger.exception("emiss_regional_sets %s failed", rset.dataset)
            from app.services.alerting import exception_reason

            failures.append(f"{rset.dataset}: {exception_reason(exc, 160)}")
    logger.info("emiss_regional_sets_job done in %.1fs: %s", time.monotonic() - started, stats)
    if failures:
        from html import escape

        from app.services.alerting import alert_muted, send_telegram

        try:
            if not await alert_muted("emiss_regional_sets:failed", _ALERT_MUTE_S):
                await send_telegram(
                    "🔴 <b>Региональные ряды ЕМИСС (сельхозцены, жильё, промышленность, грузоперевозки) не обновились</b>\n"
                    + escape("; ".join(failures)),
                    kind="etl_alert",
                )
        except Exception:  # noqa: BLE001 — алерт не должен маскировать результат
            pass
    return stats

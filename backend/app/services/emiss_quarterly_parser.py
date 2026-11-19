"""Квартальные и годовые ряды ЕМИСС по регионам (реестр — ``app.data.emiss_quarterly``, 19.11.2026).

Цена 1 м² жилья и её индексы (31452, 30925), цена 1 м² в центрах субъектов (61781), доходы к прожиточному
минимуму (58537) пишутся в квартальный слой ``region_quarterly_data`` (YYYYQ); прожиточный минимум по группам
(30957) — в годовой ``region_data``: с 2021 года он устанавливается на год.

Зона F (19.11.2026): пенсии по видам Соцфонда (62164) — квартальный слой, значение «на 1 января / апреля / июля /
октября» = I–IV квартал (известно с первого дня квартала, поэтому текущий квартал не отрезается); территории —
межведомственный ОКАТО 30628 (oid и названия — как у пенсии 61699 в ``emiss_regional_social``). Итоги сезона в
сельском хозяйстве — годовой слой с одной датой из сезона: урожай на 1 ноября (34165), яровой сев на 1 июня
(34158); год без этой даты не пишется. Заглушки источника (1 000 000 тыс. га) отсекаются ``max_value``.

Транспорт — тот же ``_post_grid``, что у цен 31448 (прямой ход → HTTP-прокси → SOCKS; адресу прода fedstat
отвечает 403). Запрос: строки — территория, измерения ряда и год; столбец — период; территории перечислены явно
(«все территории» источник не отдаёт). Ключ ячейки ответа — ``dim<oid периода>_d…_i…``, год — в ``dim3`` строки
(проверено живым запросом с Mac 19.11.2026).

Россия: до 2022 года — строка «Российская Федерация», с 2023 — «без учета новых субъектов»; если одной строки нет,
берётся другая (до 2023 года это одна и та же страна). Плановые периоды (у 30957 есть 2027 год) и незакончившиеся
кварталы отрезаются. Отсутствующий в ответе период не стирает сохранённую историю (ADR-0002: только
INSERT … ON CONFLICT DO UPDATE с охраной «значение изменилось»).

План: первая загрузка набора — вся история с ``first_year`` кусками по шесть лет; дальше — год до последнего
сохранённого (ревизии) и новые годы. Новый ряд в наборе запускает полную догрузку набора (повторы идемпотентны).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import date
from math import isfinite
from typing import Callable

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import publish_committed_regional_changes
from app.data.emiss_quarterly import DATASETS, RUSSIA_LEGACY, RUSSIA_WITHOUT_NEW, Dataset, QSeries
from app.database import async_session
from app.models import Region, RegionDataPoint, RegionIndicator, RegionQuarterlyPoint
from app.services.emiss_regional_parser import (
    _DIMNAMES_PATH, _OKATO_PATH, _RUSSIA_LEGACY, _post_grid, literal_inserted, parse_ru_float,
)
from app.services.regional_storage import acquire_regional_write_lock, update_regional_year_bounds

logger = logging.getLogger(__name__)

CHUNK_YEARS = 6
_PAUSE_BETWEEN_REQUESTS = 0.6
_ALERT_MUTE_S = 3 * 24 * 3600

Point = tuple[str, str, int, float]  # (код ряда, slug, период YYYYQ или год, значение)


class EmissQuarterlyFormatError(RuntimeError):
    """Источник ответил строками, но ни одно значение не разобрано: вероятно, сменился формат ответа."""


def load_territories() -> tuple[list[str], dict[str, str]]:
    """OID территорий для запроса и карта «название или oid → slug» (общая со справочником цен 31448)."""
    okato = json.loads(_OKATO_PATH.read_text(encoding="utf-8"))
    names = json.loads(_DIMNAMES_PATH.read_text(encoding="utf-8"))
    dimnames = {str(oid): slug for slug, oid in okato.items()}
    dimnames.update(names)
    oids = sorted(set(okato.values()) | {_RUSSIA_LEGACY})
    return oids, dimnames


def dataset_territories(
    ds: Dataset, territory_oids: list[str], dimnames: dict[str, str],
) -> tuple[list[str], dict[str, str]]:
    """Территории запроса и «название → slug» набора: общий ОКАТО (57831) или межведомственный (30628, Соцфонд)."""
    if ds.territory_dim == "57831":
        return territory_oids, dimnames
    from app.services.emiss_regional_social import load_territories as social_territories, territory_slugs

    return social_territories()[ds.territories_key or str(ds.id)], territory_slugs(dimnames)


def current_quarter(today: date) -> int:
    return today.year * 10 + (today.month - 1) // 3 + 1


def _period_oid(key: str) -> str | None:
    if not key.startswith("dim") or "_d" not in key:
        return None
    return key[3:].split("_", 1)[0]


def parse_dataset_response(
    ds: Dataset, payload: dict, dimnames: dict[str, str], *, today: date,
) -> list[Point]:
    """Ответ dataGrid.do одного набора → точки рядов реестра. Неизвестные территории и ряды пропускаются."""
    rows = payload.get("results")
    if not isinstance(rows, list):
        raise EmissQuarterlyFormatError(f"ЕМИСС {ds.id}: нет массива результатов")
    by_key = {s.key: s for s in ds.series}
    alias = {name: slug for name, (_oid, slug) in ds.aliases.items()}
    alias.update({oid: slug for _name, (oid, slug) in ds.aliases.items()})
    series_dims = [d for d in ds.line_dims if d not in (ds.territory_dim, "3")]
    period_map = ds.period_map
    last_q = current_quarter(today)
    # (код, slug, период) → значение; Россия и подменные названия собираются отдельно и решаются ниже.
    main: dict[tuple[str, str, int], float] = {}
    russia: dict[tuple[str, int], dict[str, float]] = {}
    aliased: dict[tuple[str, str, int], float] = {}
    for row in rows:
        territory = str(row.get(f"dim{ds.territory_dim}") or "").strip()
        year_text = str(row.get("dim3") or "").strip()
        if not year_text.isdigit():
            continue
        year = int(year_text)
        series: QSeries | None = by_key.get(tuple(str(row.get(f"dim{d}") or "").strip() for d in series_dims))
        if series is None:
            continue
        for key, raw in row.items():
            oid = _period_oid(key)
            if oid is None or oid not in period_map:
                continue
            value = parse_ru_float(raw)
            if value is None or not isfinite(value) or value <= 0:
                continue
            if ds.max_value is not None and value > ds.max_value:
                continue  # заглушка источника (у 34158 бывает 1 000 000), не значение
            if ds.layer == "annual":
                period = year
                if year > today.year:  # плановые годы (прожиточный минимум на 2027 год)
                    continue
            else:
                period = year * 10 + period_map[oid]
                # Квартал ещё не закончился: значение может быть только плановым. Значение «на 1-е число»
                # квартала известно с его первого дня.
                if period > last_q or (period == last_q and not ds.at_quarter_start):
                    continue
            if series.min_year and year < series.min_year:
                continue
            if territory in (RUSSIA_LEGACY, RUSSIA_WITHOUT_NEW, _RUSSIA_LEGACY):
                russia.setdefault((series.code, period), {})[territory] = value
            elif territory in alias:
                aliased[(series.code, alias[territory], period)] = value
            elif dimnames.get(territory):
                main[(series.code, dimnames[territory], period)] = value
    for (code, period), values in russia.items():
        year = period if ds.layer == "annual" else period // 10
        order = (RUSSIA_WITHOUT_NEW, RUSSIA_LEGACY, _RUSSIA_LEGACY) if year >= 2023 else (
            RUSSIA_LEGACY, _RUSSIA_LEGACY, RUSSIA_WITHOUT_NEW)
        main[(code, "russia", period)] = next(values[t] for t in order if t in values)
    for key, value in aliased.items():
        main.setdefault(key, value)
    points = [(code, slug, period, value) for (code, slug, period), value in main.items()]
    if rows and not points:
        sample = str((rows[0] or {}).get("dim57831") or "")[:60]
        raise EmissQuarterlyFormatError(
            f"ЕМИСС {ds.id}: ответ содержит {len(rows)} строк, ни одно значение не разобрано (первая: {sample!r})"
        )
    return points


async def fetch_dataset(
    ds: Dataset, years: range, territory_oids: list[str], dimnames: dict[str, str], *,
    today: date, post_grid: Callable | None = None,
) -> list[Point]:
    post_grid = post_grid or _post_grid
    territory_oids, dimnames = dataset_territories(ds, territory_oids, dimnames)
    dim = ds.territory_dim
    filters = [
        f"0_{ds.id}", f"30611_{ds.unit_oid}", *(f"33560_{oid}" for oid in ds.period_oids), *ds.fixed_filters,
        *(f"{dim}_{oid}" for oid in territory_oids), *(f"{dim}_{oid}" for oid, _slug in ds.aliases.values()),
        *(f"3_{year}" for year in years),
    ]
    payload = await post_grid(ds.id, [
        *(("lineObjectIds", dim) for dim in ds.line_dims), ("columnObjectIds", "33560"),
        *(("selectedFilterIds", value) for value in filters),
    ])
    return parse_dataset_response(ds, payload, dimnames, today=today)


async def ensure_indicators(db: AsyncSession) -> dict[str, int]:
    """Метаданные своих рядов (загрузчик начинает с пустой базы) → {код: id} всех рядов реестра, что есть в базе."""
    for ds in DATASETS:
        for s in ds.series:
            if not s.own_metadata:
                continue
            values = dict(
                code=s.code, table_code=s.table_code, section_num=ds.section[0], section_name=ds.section[1],
                name=s.name_ru, unit=ds.unit_ru, note=ds.note_ru, source_note=f"ЕМИСС, {ds.id}",
            )
            stmt = pg_insert(RegionIndicator).values(**values)
            fields = {k: getattr(stmt.excluded, k) for k in values if k != "code"}
            await db.execute(stmt.on_conflict_do_update(
                index_elements=["code"], set_=fields,
                where=or_(*(getattr(RegionIndicator, k).is_distinct_from(v) for k, v in fields.items())),
            ))
    codes = [s.code for ds in DATASETS for s in ds.series]
    return dict((await db.execute(
        select(RegionIndicator.code, RegionIndicator.id).where(RegionIndicator.code.in_(codes))
    )).all())


async def _stored_last_year(db: AsyncSession, ds: Dataset, ids: dict[str, int]) -> int | None:
    """Последний сохранённый год самого короткого ряда набора (новый ряд → None → полная загрузка)."""
    lasts = []
    for s in ds.series:
        ind_id = ids.get(s.code)
        if ind_id is None:
            continue
        if ds.layer == "annual":
            q = select(func.max(RegionDataPoint.year)).where(RegionDataPoint.indicator_id == ind_id)
            last = await db.scalar(q)
        else:
            q = select(func.max(RegionQuarterlyPoint.quarter)).where(RegionQuarterlyPoint.indicator_id == ind_id)
            last = await db.scalar(q)
            last = last // 10 if last is not None else None
        if last is None or (s.min_year and last < s.min_year):
            return None
        lasts.append(int(last))
    return min(lasts) if lasts else None


def plan_years(ds: Dataset, last_year: int | None, today: date) -> list[range]:
    start = ds.first_year if last_year is None else max(ds.first_year, last_year - 1)
    end = today.year + (1 if ds.layer == "annual" else 0)  # годовой: видеть и отрезать плановый год
    return [range(y, min(y + CHUNK_YEARS, end + 1)) for y in range(start, end + 1, CHUNK_YEARS)]


async def _upsert(db: AsyncSession, layer: str, values: list[tuple[int, int, int, float]]) -> tuple[int, int]:
    model, column, constraint = (
        (RegionQuarterlyPoint, "quarter", "uq_region_quarterly_point") if layer == "quarterly"
        else (RegionDataPoint, "year", "uq_region_data_point")
    )
    added = updated = 0
    for start in range(0, len(values), 5000):
        stmt = pg_insert(model).values([
            {"indicator_id": i, "region_id": r, column: p, "value": v} for i, r, p, v in values[start:start + 5000]
        ])
        result = await db.execute(stmt.on_conflict_do_update(
            constraint=constraint, set_={"value": stmt.excluded.value},
            where=(model.__table__.c.value != stmt.excluded.value),
        ).returning(literal_inserted()))
        rows = result.fetchall()
        added += sum(1 for (ins,) in rows if ins)
        updated += sum(1 for (ins,) in rows if not ins)
    return added, updated


async def run_emiss_quarterly_update(
    db: AsyncSession, *, post_grid: Callable | None = None, today: date | None = None,
) -> dict[str, int]:
    """Fetch → SQL-транзакция на кусок лет → commit → публикация кэша регионов."""
    today = today or date.today()
    territory_oids, dimnames = load_territories()
    await acquire_regional_write_lock(db)
    ids = await ensure_indicators(db)
    await db.commit()
    regions = dict((await db.execute(select(Region.slug, Region.id))).all())
    stats = {"requests": 0, "added": 0, "updated": 0, "unparsed": 0}
    for ds in DATASETS:
        for years in plan_years(ds, await _stored_last_year(db, ds, ids), today):
            try:
                points = await fetch_dataset(ds, years, territory_oids, dimnames, today=today, post_grid=post_grid)
            except EmissQuarterlyFormatError as exc:
                logger.warning("emiss_quarterly: %s", exc)
                stats["unparsed"] += 1
                continue
            finally:
                stats["requests"] += 1
                await asyncio.sleep(_PAUSE_BETWEEN_REQUESTS if post_grid is None else 0)
            values = [
                (ids[code], regions[slug], period, value) for code, slug, period, value in points
                if code in ids and slug in regions
            ]
            if not values:
                continue
            try:
                await acquire_regional_write_lock(db)
                added, updated = await _upsert(db, ds.layer, values)
                changed_meta = await update_regional_year_bounds(db, {v[0] for v in values})
                await db.commit()
            except BaseException:
                await db.rollback()
                raise
            stats["added"] += added
            stats["updated"] += updated
            if added or updated or changed_meta:
                await publish_committed_regional_changes()
            logger.info("emiss_quarterly: %s %d–%d: %d точек (новых %d, ревизий %d)",
                        ds.id, years[0], years[-1], len(values), added, updated)
    return stats


async def emiss_quarterly_job() -> dict[str, int]:
    """Точка входа планировщика: квартальные ряды ЕМИСС по регионам."""
    started = time.monotonic()
    from app.services.alerting import alert_muted, exception_reason, send_telegram

    try:
        async with async_session() as db:
            stats = await run_emiss_quarterly_update(db)
    except Exception as exc:
        logger.exception("emiss_quarterly_job failed")
        try:
            if not await alert_muted("emiss_quarterly:failed", _ALERT_MUTE_S):
                from html import escape

                await send_telegram(
                    "🔴 <b>Квартальные ряды регионов (жильё, прожиточный минимум, пенсии по видам, итоги сева и уборки) не обновились</b>\n"
                    f"Причина: {escape(exception_reason(exc, 300))}",
                    kind="etl_alert",
                )
        except Exception:  # noqa: BLE001 — алерт не должен маскировать исключение
            pass
        raise
    if stats["unparsed"] and not await alert_muted("emiss_quarterly:unparsed", _ALERT_MUTE_S):
        await send_telegram(
            "🟡 <b>Квартальные ряды регионов: ответ получен, значения не разобраны</b> — "
            f"запросов без разбора: {stats['unparsed']}. Вероятно, источник сменил формат ответа.",
            kind="etl_alert",
        )
    logger.info("emiss_quarterly_job done in %.1fs: %s", time.monotonic() - started, stats)
    return stats

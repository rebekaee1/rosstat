"""Помесячные цены потребителей по регионам из ЕМИСС: ИПЦ 31074, стоимость наборов 31052 и 31481 (19.11.2026).

Справочник рядов — ``app.data.emiss_regional_cpi``. Пишет в ``region_monthly_data`` теми же механизмами, что
цены товаров 31448 (``emiss_regional_parser``): транспорт ``_post_grid`` через ETL-сессию (адрес прода fedstat
режет 403), справочник территорий ``emiss_okato_31448.json`` + ``emiss_dimnames.json``, upsert с guard'ом
``value <> excluded.value``, региональная блокировка записи и публикация кэша после commit.

Запрос — «год целиком»: строки — территория × (товар × вид индекса), столбцы — год × месяц; ключ ячейки
``dim{год}_{oid месяца}_d…`` несёт месяц, поэтому 12 месяцев приходят одним ответом (у 31448 месяц в ключе не
виден, там запрос «год × месяц»). Кварталы набора 31074 не запрашиваются.

Россия: до 2022 года — «Российская Федерация» (1688487), с 2023 — «без учёта новых субъектов» (1849012); обе
пишутся в slug ``russia``, при двух значениях за месяц побеждает вторая (так же у 31448). Новые субъекты в
справочнике территорий сайта отсутствуют и пропускаются.

План: пустая база или новый ряд — вся история с первого года набора (~25 запросов по 1–30 с); дальше — годы без
единой точки России (сбой прошлого прогона) и хвост от последнего загруженного года до текущего (если в нём только
январь — и прошлый год, на ревизии). Сбой сети на одном годе не отменяет остальные: год останется пустым, и
следующий прогон его повторит. Отсутствие значения в ответе ничего не удаляет.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import date
from typing import Callable, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import publish_committed_regional_changes
from app.data import emiss_regional_cpi as spec
from app.database import async_session
from app.models import Region, RegionIndicator, RegionMonthlyPoint
from app.services.emiss_regional_parser import (
    MONTH_OIDS,
    _RUSSIA_ID,
    _RUSSIA_LEGACY,
    _post_grid,
    _upsert_monthly_points,
    load_dimnames,
    load_territory_ids,
    parse_ru_float,
)
from app.services.regional_storage import acquire_regional_write_lock, update_regional_year_bounds

logger = logging.getLogger(__name__)

_PAUSE_BETWEEN_REQUESTS = 1.0
_KIND_LABELS = {
    "К предыдущему месяцу": spec.KIND_MONTH,
    "К декабрю предыдущего года": spec.KIND_DECEMBER,
    "К соответствующему периоду предыдущего года": spec.KIND_YEAR,
}
_RUSSIA_NEW = "Российская Федерация без учета новых субъектов (с 01.01.2023)"


@dataclass(frozen=True)
class GridRequest:
    """Один запрос dataGrid.do на год: набор, его ряды и выбор измерений."""
    name: str
    dataset: int
    unit: str                               # oid 30611
    first_year: int
    series: tuple[spec.RegionalSeries, ...]

    @property
    def items(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(s.item for s in self.series if s.item))

    @property
    def kinds(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(s.kind for s in self.series if s.kind))


def _by_dataset(dataset: int, kinds: frozenset[str] | None = None) -> tuple[spec.RegionalSeries, ...]:
    return tuple(s for s in spec.SERIES if s.dataset == dataset and (kinds is None or s.kind in kinds))


# Главные индексы — три вида; группы — только «за год». Два запроса, чтобы не тянуть лишние виды групп.
_HEADLINE_CODES = {spec.cpi_code(g, k) for g in spec.HEADLINE for k in spec.KIND_SUFFIX}
REQUESTS: tuple[GridRequest, ...] = (
    GridRequest("cpi-headline", spec.CPI_DATASET, spec.PERCENT, spec.FIRST_YEAR,
                tuple(s for s in _by_dataset(spec.CPI_DATASET) if s.code in _HEADLINE_CODES)),
    GridRequest("cpi-groups", spec.CPI_DATASET, spec.PERCENT, spec.FIRST_YEAR,
                tuple(s for s in _by_dataset(spec.CPI_DATASET) if s.code not in _HEADLINE_CODES)),
    GridRequest("fixed-set", spec.FIXED_SET_DATASET, spec.RUBLE, spec.FIRST_YEAR,
                _by_dataset(spec.FIXED_SET_DATASET)),
    GridRequest("food-set", spec.FOOD_SET_DATASET, spec.RUBLE, spec.FOOD_SET_FIRST_YEAR,
                _by_dataset(spec.FOOD_SET_DATASET)),
)


class EmissCpiFormatError(RuntimeError):
    """Ответ со строками, но без единого разобранного значения: вероятно, сменился формат."""


def build_params(req: GridRequest, year: int, territory_ids: Sequence[str]) -> list[tuple[str, str]]:
    lines = ["57831"] + (["58273", "57937"] if req.items else [])
    params: list[tuple[str, str]] = [("lineObjectIds", d) for d in lines]
    params += [("columnObjectIds", "3"), ("columnObjectIds", "33560")]
    params += [("selectedFilterIds", f"0_{req.dataset}"), ("selectedFilterIds", f"3_{year}"),
               ("selectedFilterIds", f"30611_{req.unit}")]
    params += [("selectedFilterIds", f"33560_{oid}") for oid in MONTH_OIDS]
    params += [("selectedFilterIds", f"58273_{oid}") for oid in req.items]
    params += [("selectedFilterIds", f"57937_{oid}") for oid in req.kinds]
    territories = [t for t in territory_ids if t != _RUSSIA_LEGACY]
    if year <= 2022:
        territories.append(_RUSSIA_LEGACY)
    params += [("selectedFilterIds", f"57831_{oid}") for oid in territories]
    return params


def _series_key(req: GridRequest) -> dict[tuple[str | None, str | None], str]:
    """(товар, вид) → код ряда; товар и вид узнаются и по oid, и по названию из ответа."""
    out: dict[tuple[str | None, str | None], str] = {}
    labels = {g.oid: g.label for g in (*spec.HEADLINE, *spec.GROUPS)}
    kind_labels = {oid: label for label, oid in _KIND_LABELS.items()}
    for s in req.series:
        for item in {s.item, labels.get(s.item or "")}:
            for kind in {s.kind, kind_labels.get(s.kind or "")}:
                out[(item, kind)] = s.code
    return out


def parse_year(payload: dict, req: GridRequest, year: int, dimnames: dict[str, str]) -> list[tuple[str, str, int, float]]:
    """Ответ dataGrid.do за год → [(код ряда, slug территории, YYYYMM, значение)]."""
    keys = _series_key(req)
    rows = payload.get("results")
    if not isinstance(rows, list):
        raise EmissCpiFormatError(f"{req.name} {year}: нет массива results")
    # «Без учёта новых субъектов» — последней: при двух значениях России за месяц побеждает она.
    rows = sorted(rows, key=lambda r: str(r.get("dim57831") or "").strip() in (_RUSSIA_ID, _RUSSIA_NEW))
    out: dict[tuple[str, str, int], float] = {}
    for row in rows:
        slug = dimnames.get(str(row.get("dim57831") or "").strip())
        if not slug:
            continue
        item = str(row["dim58273"]).strip() if "dim58273" in row else None
        kind = str(row["dim57937"]).strip() if "dim57937" in row else None
        code = keys.get((item, kind))
        if not code:
            continue
        for key, raw in row.items():
            parts = key.removeprefix("dim").split("_")
            if len(parts) < 3 or parts[0] != str(year) or not parts[2].startswith("d"):
                continue
            month = MONTH_OIDS.get(parts[1])
            value = parse_ru_float(raw)
            if month is None or value is None or value <= 0:
                continue
            out[(code, slug, year * 100 + month)] = value
    if rows and not out:
        raise EmissCpiFormatError(f"{req.name} {year}: {len(rows)} строк, ни одно значение не разобрано")
    return [(code, slug, period, value) for (code, slug, period), value in out.items()]


async def fetch_year(req: GridRequest, year: int, territory_ids: Sequence[str], dimnames: dict[str, str],
                     *, post_grid: Callable | None = None) -> list[tuple[str, str, int, float]]:
    payload = await (post_grid or _post_grid)(req.dataset, build_params(req, year, territory_ids))
    return parse_year(payload, req, year, dimnames)


def years_to_fetch(req: GridRequest, loaded: set[int] | None, *, today: date | None = None) -> list[int]:
    """Годы для запроса: недостающие (пустая база, новый ряд, сбой прошлого прогона) и хвост на ревизии.

    ``loaded`` — годы, где у России есть точки хотя бы одного ряда запроса; ``None`` или пусто — вся история.
    Хвост — от последнего загруженного года до текущего.
    """
    today = today or date.today()
    every = range(req.first_year, today.year + 1)
    if not loaded:
        return list(every)
    last = max(loaded)
    return sorted({y for y in every if y not in loaded or y >= last})


async def _loaded_years(db: AsyncSession, indicator_ids: list[int], russia_id: int | None) -> set[int] | None:
    """Годы с точками России у рядов запроса; None — если хоть у одного ряда точек нет (догрузить всё).

    Если в последнем году есть только январь, прошлый год тоже считается незагруженным: декабрь и ревизии
    прошлого года Росстат выкладывает вместе с январём.
    """
    if russia_id is None or not indicator_ids:
        return None
    rows = (await db.execute(
        select(RegionMonthlyPoint.indicator_id, RegionMonthlyPoint.month)
        .where(RegionMonthlyPoint.indicator_id.in_(indicator_ids), RegionMonthlyPoint.region_id == russia_id)
    )).all()
    if len({iid for iid, _m in rows}) < len(indicator_ids):
        return None
    years = {int(m) // 100 for _iid, m in rows}
    last = max(years)
    if {int(m) % 100 for _iid, m in rows if int(m) // 100 == last} == {1}:
        years.discard(last - 1)
    return years


async def run_emiss_regional_cpi_update(
    db: AsyncSession,
    *,
    post_grid: Callable | None = None,
    territory_ids: Sequence[str] | None = None,
    dimnames: dict[str, str] | None = None,
    today: date | None = None,
) -> dict[str, int]:
    """Все запросы по плану; каждый год — своя транзакция, кэш публикуется после commit изменившегося года."""
    dimnames = dimnames if dimnames is not None else load_dimnames()
    territory_ids = territory_ids if territory_ids is not None else load_territory_ids()
    codes = [s.code for s in spec.SERIES]
    indicators = {
        ind.code: ind for ind in (await db.execute(
            select(RegionIndicator).where(RegionIndicator.code.in_(codes))
        )).scalars()
    }
    regions = {slug: rid for slug, rid in (await db.execute(select(Region.slug, Region.id))).all()}
    stats = {"years": 0, "added": 0, "updated": 0, "unparsed": 0}
    failed: list[str] = []
    skipped = [c for c in codes if c not in indicators]
    if skipped:
        # Метаданные пишет seed_regional при старте; до него ряды ждут следующего прогона.
        logger.warning("emiss_regional_cpi: нет метаданных %d рядов, пропуск: %s", len(skipped), skipped[:5])
    for req in REQUESTS:
        ids = [indicators[s.code].id for s in req.series if s.code in indicators]
        if not ids:
            continue
        loaded = await _loaded_years(db, ids, regions.get("russia"))
        for year in years_to_fetch(req, loaded, today=today):
            try:
                points = await fetch_year(req, year, territory_ids, dimnames, post_grid=post_grid)
            except EmissCpiFormatError as exc:
                logger.warning("emiss_regional_cpi: %s", exc)
                stats["unparsed"] += 1
                continue
            except RuntimeError as exc:
                # Сбой сети или доступа на одном годе не отменяет остальные: пустой год следующий прогон
                # запросит снова (он не попадёт в loaded). В конце прогона — ошибка для алерта.
                logger.warning("emiss_regional_cpi: %s %d: %s", req.name, year, exc)
                failed.append(f"{req.name} {year}: {exc}")
                continue
            stats["years"] += 1
            by_code: dict[str, list[tuple[int, int, int, float]]] = {}
            for code, slug, period, value in points:
                if code in indicators and slug in regions:
                    by_code.setdefault(code, []).append((indicators[code].id, regions[slug], period, value))
            added = updated = 0
            try:
                await acquire_regional_write_lock(db)
                for values in by_code.values():
                    a, u = await _upsert_monthly_points(db, values)
                    added, updated = added + a, updated + u
                metadata_changed = await update_regional_year_bounds(db, {v[0][0] for v in by_code.values()})
                await db.commit()
            except BaseException:
                await db.rollback()
                raise
            stats["added"] += added
            stats["updated"] += updated
            if added or updated or metadata_changed:
                await publish_committed_regional_changes()
            logger.info("emiss_regional_cpi: %s %d — %d точек (новых %d, ревизий %d)",
                        req.name, year, len(points), added, updated)
            await asyncio.sleep(_PAUSE_BETWEEN_REQUESTS)
    if failed:
        raise RuntimeError(f"не загружено запросов: {len(failed)} (остальные сохранены); первый: {failed[0]}")
    return stats


_ALERT_MUTE_S = 3 * 24 * 3600


async def emiss_regional_cpi_job() -> dict[str, int]:
    """Точка входа планировщика: ИПЦ и стоимость наборов по регионам."""
    started = time.monotonic()
    try:
        async with async_session() as db:
            stats = await run_emiss_regional_cpi_update(db)
        logger.info("emiss_regional_cpi_job done in %.1fs: %s", time.monotonic() - started, stats)
        if stats["added"] or stats["updated"]:
            from app.services.alerting import send_telegram

            await send_telegram(
                "🧺 <b>Цены потребителей по регионам обновлены</b> (ИПЦ, стоимость наборов)\n"
                f"Лет запрошено: {stats['years']}, новых точек: {stats['added']}, ревизий: {stats['updated']}",
                kind="etl_summary",
            )
        if stats["unparsed"]:
            from app.services.alerting import alert_muted, send_telegram

            if not await alert_muted("emiss_regional_cpi:unparsed", _ALERT_MUTE_S):
                await send_telegram(
                    "🟡 <b>ИПЦ по регионам: ответ получен, значения не разобраны</b> — "
                    f"запросов без разбора: {stats['unparsed']}. Вероятно, источник сменил формат ответа.",
                    kind="etl_alert",
                )
        return stats
    except Exception as exc:
        logger.exception("emiss_regional_cpi_job failed")
        from html import escape

        from app.services.alerting import alert_muted, exception_reason, send_telegram

        try:
            if not await alert_muted("emiss_regional_cpi:failed", _ALERT_MUTE_S):
                await send_telegram(
                    "🔴 <b>Парсер ИПЦ по регионам упал</b>\n"
                    f"Причина: {escape(exception_reason(exc, 300))}",
                    kind="etl_alert",
                )
        except Exception:  # noqa: BLE001 — алерт не должен маскировать исключение
            pass
        raise

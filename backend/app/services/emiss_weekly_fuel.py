"""Недельные цены на топливо по субъектам РФ (ЕМИСС 37426) → ``region_weekly_data`` (18.11.2026).

Зачем. Из поиска за ценой топлива приходят с датой и городом: «ДТ в СПб на 01.01.2026»,
«стоимость дизтоплива в Вологде 10.01.2025». Месячный ряд (ЕМИСС 31448) отвечает только
месяцем, федеральный недельный (``fuel-ai92`` и др.) — только по России. Росстат публикует
и недельные средние цены по каждому субъекту: витрина ЕМИСС 37426 «Еженедельные средние
потребительские цены (тарифы) на отдельные товары и услуги», с 2008 года, обновление по
средам. Берём четыре позиции: АИ-92, АИ-95, АИ-98 и выше, дизельное топливо — они ложатся
на те же региональные показатели, что и месячные (``ceni-ai92`` …), и показываются на той
же странице «топливо × регион».

Механика dataGrid.do та же, что у 31448 (``emiss_regional_parser``): каждое измерение
должно иметь выбранное значение, территории перечисляются явно. Отличия (проверено живьём
18.11.2026 с Mac):

- период (измерение 33560) стоит в колонках вместе с годом, поэтому один запрос отдаёт все
  недели года сразу: ключ ячейки ``dim<год>_<oid недели>_d…_i…``;
- у недель с 2022 года подпись без даты: «1 неделя 2025», «51 неделя 2025». Oid новой
  недели появляется в справочнике витрины с её публикацией, поэтому список недель каждый
  прогон читается со страницы витрины (``/indicator/37426``), а не из снимка;
- дата недели — день регистрации цен Росстатом. Её даёт федеральный недельный ряд
  (``fuel-ai92``/``fuel-ai95``/``fuel-diesel``, файл ``nedel_sred_cen.xlsx``): строка
  России в 37426 совпадает с ним до копейки (2025: 55,46 / 55,49 / 55,55 … на 9, 13, 20
  января). Неделя k года получает дату k-й точки федерального ряда того же года, только
  если цены России по всем общим маркам совпали; несовпадение — неделя пропускается до
  следующего прогона (``undated``), дата не угадывается;
- строка России: до 2022 года «Российская Федерация» (1688487), с 2023 — «без учета новых
  субъектов» (1849012), как в федеральном ряду и в месячной витрине.

Глубина — с 2022 года: старые подписи недель несут дату текстом в разных видах, а спрос на
даты до 2022 года почти нулевой (90 дней фраз Яндекса на 18.11.2026: 5 заходов из 3 229).

Идемпотентность ADR-0002: ON CONFLICT DO UPDATE с guard ``value <> excluded.value``; год —
отдельная транзакция под общим региональным advisory lock; кэш публикуется после commit.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections import defaultdict
from datetime import date
from typing import Callable, Iterable, Sequence

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import publish_committed_regional_changes
from app.database import async_session
from app.models import Indicator, IndicatorData, Region, RegionIndicator, RegionWeeklyPoint
from app.services.emiss_regional_parser import (
    _RUSSIA_ID,
    _RUSSIA_LEGACY,
    EmissFormatError,
    _post_grid,
    literal_inserted,
    load_dimnames,
    load_territory_ids,
    parse_ru_float,
)
from app.services.http_client import create_session
from app.services.regional_storage import acquire_regional_write_lock

logger = logging.getLogger(__name__)

INDICATOR_ID = 37426
PAGE_URL = f"https://www.fedstat.ru/indicator/{INDICATOR_ID}"
FIRST_YEAR = 2022

# 58273 «Виды товаров и услуг» — те же oid, что в месячной витрине 31448.
WEEKLY_FUELS: dict[str, str] = {
    "1709730": "ceni-ai92",
    "1709750": "ceni-ai95",
    "1755184": "ceni-ai98",
    "1755196": "ceni-dt",
}
# Подписи позиций в ответе (``dim58273`` приходит названием, как и территория).
_FUEL_LABELS: dict[str, str] = {
    "Бензин автомобильный марки АИ-92, л": "ceni-ai92",
    "Бензин автомобильный марки АИ-95, л": "ceni-ai95",
    "Бензин автомобильный марки АИ-98 и выше, л": "ceni-ai98",
    "Дизельное топливо, л": "ceni-dt",
}
# Федеральный недельный ряд той же марки: календарь дат регистрации и сверка строки России.
NATIONAL_BY_REGIONAL: dict[str, str] = {
    "ceni-ai92": "fuel-ai92",
    "ceni-ai95": "fuel-ai95",
    "ceni-dt": "fuel-diesel",
}

_WEEK_TITLE = re.compile(r"^\s*(\d{1,2})\s+неделя\s+(\d{4})\s*$")
_FILTER_VALUE = re.compile(r"(\d+):\s*\{\s*title:\s*'([^']*)'")
_CELL_KEY = re.compile(r"^dim(\d{4})_(\d+)_")
_RU_NAMES = {"Российская Федерация": _RUSSIA_LEGACY,
             "Российская Федерация без учета новых субъектов (с 01.01.2023)": _RUSSIA_ID}
_MATCH_TOLERANCE = 0.006
_UPSERT_CHUNK = 2000


def _unescape(raw: str) -> str:
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), raw)


def parse_week_oids(page_html: str) -> dict[int, dict[int, str]]:
    """Страница витрины → {год: {номер недели: oid периода}} для подписей «N неделя YYYY»."""
    out: dict[int, dict[int, str]] = defaultdict(dict)
    for oid, raw_title in _FILTER_VALUE.findall(page_html):
        m = _WEEK_TITLE.match(_unescape(raw_title))
        if m:
            out[int(m.group(2))][int(m.group(1))] = oid
    return dict(out)


def parse_weekly_grid(
    payload: dict,
    *,
    year: int,
    week_by_oid: dict[str, int],
    dimnames: dict[str, str],
) -> tuple[dict[tuple[str, str], dict[int, float]], dict[str, dict[int, float]]]:
    """Ответ dataGrid.do за год → (точки субъектов, строка России).

    Точки: {(код показателя, slug): {неделя: цена}}. Строка России отдельно —
    {код: {неделя: цена}}, из «РФ» до 2022 года и «РФ без новых субъектов» с 2023-го; она
    же сверяется с федеральным рядом и пишется в slug ``russia``.
    """
    rf_oid = _RUSSIA_LEGACY if year <= 2022 else _RUSSIA_ID
    points: dict[tuple[str, str], dict[int, float]] = defaultdict(dict)
    russia: dict[str, dict[int, float]] = defaultdict(dict)
    for row in payload.get("results", []):
        territory = str(row.get("dim57831") or "").strip()
        fuel_raw = str(row.get("dim58273") or "").strip()
        code = _FUEL_LABELS.get(fuel_raw) or WEEKLY_FUELS.get(fuel_raw)
        if not code:
            continue
        ru_oid = _RU_NAMES.get(territory) or (territory if territory in (_RUSSIA_ID, _RUSSIA_LEGACY) else None)
        if ru_oid is not None:
            if ru_oid != rf_oid:
                continue
            slug = "russia"
        else:
            slug = dimnames.get(territory)
            if not slug or slug == "russia":
                continue
        for key, raw in row.items():
            m = _CELL_KEY.match(key)
            if not m or int(m.group(1)) != year:
                continue
            week = week_by_oid.get(m.group(2))
            value = parse_ru_float(raw)
            if week is None or value is None or value <= 0:
                continue
            if slug == "russia":
                russia[code][week] = value
            else:
                points[(code, slug)][week] = value
    return dict(points), dict(russia)


def resolve_week_dates(
    russia: dict[str, dict[int, float]],
    national: dict[str, list[tuple[date, float]]],
) -> dict[int, date]:
    """Неделя года → дата регистрации по федеральному недельному ряду того же года.

    Неделя k берёт k-ю дату ряда (с учётом найденного сдвига, если в ряду есть лишняя или
    пропущенная неделя) только при совпадении цен России по всем маркам, которые есть в обоих
    источниках (не меньше двух). Нет совпадения — нет даты: такую неделю не пишем.
    """
    calendar = sorted({d for series in national.values() for d, _v in series})
    if not calendar:
        return {}
    nat = {code: dict(series) for code, series in national.items()}
    weeks = sorted({w for by_week in russia.values() for w in by_week})
    out: dict[int, date] = {}
    offset = 0
    last_j = -1

    def matches(week: int, j: int) -> bool:
        compared = 0
        for code, by_week in russia.items():
            emiss = by_week.get(week)
            ref = nat.get(NATIONAL_BY_REGIONAL.get(code, ""), {}).get(calendar[j])
            if emiss is None or ref is None:
                continue
            if abs(emiss - float(ref)) > _MATCH_TOLERANCE:
                return False
            compared += 1
        return compared >= 2

    for week in weeks:
        expected = week - 1 + offset
        for j in (expected, expected + 1, expected - 1, expected + 2, expected - 2):
            if last_j < j < len(calendar) and matches(week, j):
                out[week] = calendar[j]
                offset = j - (week - 1)
                last_j = j
                break
    return out


async def fetch_week_oids(fetch_page: Callable[[], str] | None = None) -> dict[int, dict[int, str]]:
    """Справочник недель со страницы витрины (новые недели появляются в нём с публикацией)."""
    if fetch_page is None:
        fetch_page = _fetch_page_sync
    html = await asyncio.to_thread(fetch_page)
    weeks = parse_week_oids(html)
    if not weeks:
        raise EmissFormatError(f"{PAGE_URL}: на странице витрины не найдено ни одной недели «N неделя YYYY»")
    return weeks


def _fetch_page_sync() -> str:
    session = create_session(timeout=60)
    try:
        resp = session.get(PAGE_URL, timeout=60, headers={"User-Agent": "ForecastEconomy/1.0 (+https://forecasteconomy.com)"})
        resp.raise_for_status()
        return resp.text
    finally:
        session.close()


async def fetch_year(
    year: int,
    week_oids: dict[int, str],
    territory_ids: Sequence[str],
    dimnames: dict[str, str],
    *,
    post_grid: Callable | None = None,
) -> tuple[dict[tuple[str, str], dict[int, float]], dict[str, dict[int, float]]]:
    """Один запрос: все недели года × все территории × четыре марки."""
    if post_grid is None:
        post_grid = _post_grid
    params: list[tuple[str, str]] = [
        ("lineObjectIds", "57831"), ("lineObjectIds", "58273"),
        ("columnObjectIds", "3"), ("columnObjectIds", "33560"),
        ("selectedFilterIds", f"0_{INDICATOR_ID}"),
        ("selectedFilterIds", "30611_950351"),
        ("selectedFilterIds", f"3_{year}"),
    ]
    params += [("selectedFilterIds", f"58273_{oid}") for oid in WEEKLY_FUELS]
    territories = set(territory_ids) | {_RUSSIA_ID, _RUSSIA_LEGACY}
    params += [("selectedFilterIds", f"57831_{oid}") for oid in sorted(territories)]
    params += [("selectedFilterIds", f"33560_{oid}") for _w, oid in sorted(week_oids.items())]
    payload = await post_grid(INDICATOR_ID, params)
    week_by_oid = {oid: week for week, oid in week_oids.items()}
    points, russia = parse_weekly_grid(payload, year=year, week_by_oid=week_by_oid, dimnames=dimnames)
    rows = payload.get("results") or []
    if rows and not points and not russia:
        sample = str((rows[0] or {}).get("dim57831") or "")[:60]
        raise EmissFormatError(
            f"37426 {year}: ответ содержит {len(rows)} строк, ни одна цена не разобрана (первая территория: {sample!r})"
        )
    return points, russia


async def _national_series(db: AsyncSession, year: int) -> dict[str, list[tuple[date, float]]]:
    codes = list(NATIONAL_BY_REGIONAL.values())
    rows = (await db.execute(
        select(Indicator.code, IndicatorData.date, IndicatorData.value)
        .join(IndicatorData, IndicatorData.indicator_id == Indicator.id)
        .where(Indicator.code.in_(codes),
               IndicatorData.date >= date(year, 1, 1),
               IndicatorData.date <= date(year, 12, 31))
        .order_by(IndicatorData.date)
    )).all()
    out: dict[str, list[tuple[date, float]]] = defaultdict(list)
    for code, d, v in rows:
        out[code].append((d, float(v)))
    return dict(out)


def years_to_fetch(last_date: date | None, *, today: date | None = None) -> list[int]:
    """Пустая таблица — все годы с 2022; иначе год последней даты и все следующие до текущего."""
    today = today or date.today()
    start = FIRST_YEAR if last_date is None else max(FIRST_YEAR, last_date.year)
    return list(range(start, today.year + 1))


async def _upsert_weekly(db: AsyncSession, values: list[dict]) -> tuple[int, int]:
    added = updated = 0
    for i in range(0, len(values), _UPSERT_CHUNK):
        chunk = values[i:i + _UPSERT_CHUNK]
        stmt = pg_insert(RegionWeeklyPoint).values(chunk)
        result = await db.execute(
            stmt.on_conflict_do_update(
                constraint="uq_region_weekly_point",
                set_={"value": stmt.excluded.value},
                where=(RegionWeeklyPoint.__table__.c.value != stmt.excluded.value),
            ).returning(literal_inserted())
        )
        rows = result.fetchall()
        a = sum(1 for (ins,) in rows if ins)
        added += a
        updated += len(rows) - a
    return added, updated


async def run_weekly_fuel_update(
    db: AsyncSession,
    *,
    post_grid: Callable | None = None,
    fetch_page: Callable[[], str] | None = None,
    territory_ids: Sequence[str] | None = None,
    dimnames: dict[str, str] | None = None,
    years: Iterable[int] | None = None,
    today: date | None = None,
) -> dict[str, int]:
    """Справочник недель → запрос по году → даты по федеральному ряду → upsert → commit года."""
    if dimnames is None:
        dimnames = load_dimnames()
    if territory_ids is None:
        territory_ids = load_territory_ids()

    indicators = {
        ind.code: ind.id
        for ind in (await db.execute(
            select(RegionIndicator).where(RegionIndicator.code.in_(list(WEEKLY_FUELS.values())))
        )).scalars()
    }
    if not indicators:
        raise RuntimeError("region_weekly: нет метаданных топливных показателей (сид регионов ещё не прошёл)")
    regions = dict((await db.execute(select(Region.slug, Region.id))).all())

    if years is None:
        last = None
        if regions.get("russia") and indicators.get("ceni-dt"):
            last = (await db.execute(
                select(func.max(RegionWeeklyPoint.date))
                .where(RegionWeeklyPoint.region_id == regions["russia"],
                       RegionWeeklyPoint.indicator_id == indicators["ceni-dt"])
            )).scalar_one_or_none()
        years = years_to_fetch(last, today=today)
    years = list(years)
    # Сеть — вне транзакции: idle_in_transaction_session_timeout обрывает соединение, пока ждём источник.
    await db.commit()

    week_oids = await fetch_week_oids(fetch_page)
    stats = {"years": 0, "weeks": 0, "added": 0, "updated": 0, "undated": 0}
    unparsed: list[int] = []
    for year in years:
        if year not in week_oids:
            continue
        try:
            points, russia = await fetch_year(
                year, week_oids[year], territory_ids, dimnames, post_grid=post_grid,
            )
        except EmissFormatError as exc:
            logger.warning("emiss_weekly_fuel: %s", exc)
            unparsed.append(year)
            continue
        # Транзакция года начинается после ответа источника и заканчивается commit ниже.
        dates = resolve_week_dates(russia, await _national_series(db, year))
        all_weeks = {w for by_week in russia.values() for w in by_week}
        all_weeks |= {w for by_week in points.values() for w in by_week}
        stats["undated"] += len(all_weeks - set(dates))

        values: list[dict] = []
        for code, by_week in russia.items():
            if code in indicators and "russia" in regions:
                values += [
                    {"indicator_id": indicators[code], "region_id": regions["russia"], "date": dates[w], "value": v}
                    for w, v in by_week.items() if w in dates
                ]
        for (code, slug), by_week in points.items():
            if code in indicators and slug in regions:
                values += [
                    {"indicator_id": indicators[code], "region_id": regions[slug], "date": dates[w], "value": v}
                    for w, v in by_week.items() if w in dates
                ]
        try:
            await acquire_regional_write_lock(db)
            added, updated = await _upsert_weekly(db, values) if values else (0, 0)
            await db.commit()
        except BaseException:
            await db.rollback()
            raise
        stats["years"] += 1
        stats["weeks"] += len(dates)
        stats["added"] += added
        stats["updated"] += updated
        if added or updated:
            await publish_committed_regional_changes()
        logger.info(
            "emiss_weekly_fuel: %d — недель с датой %d, точек %d (added=%d updated=%d)",
            year, len(dates), len(values), added, updated,
        )
        await asyncio.sleep(0.4)
    if unparsed:
        stats["unparsed"] = len(unparsed)
    return stats


_ALERT_MUTE_S = 3 * 24 * 3600


async def emiss_weekly_fuel_job() -> dict[str, int]:
    """Точка входа планировщика: недельные цены на топливо по субъектам."""
    started = time.monotonic()
    try:
        async with async_session() as db:
            stats = await run_weekly_fuel_update(db)
        if stats.get("unparsed"):
            from app.services.alerting import alert_muted, send_telegram

            if not await alert_muted("emiss_weekly_fuel:unparsed", _ALERT_MUTE_S):
                await send_telegram(
                    "🟡 <b>Недельные цены на топливо по регионам: ответ получен, цены не разобраны</b> — "
                    f"лет без разбора: {stats['unparsed']}. Вероятно, источник сменил формат ответа.",
                    kind="etl_alert",
                )
        logger.info("emiss_weekly_fuel_job done in %.1fs: %s", time.monotonic() - started, stats)
        return stats
    except Exception as exc:
        logger.exception("emiss_weekly_fuel_job failed")
        from html import escape

        from app.services.alerting import alert_muted, exception_reason, send_telegram

        try:
            if not await alert_muted("emiss_weekly_fuel:failed", _ALERT_MUTE_S):
                await send_telegram(
                    "🔴 <b>Парсер недельных цен на топливо по регионам упал</b>\n"
                    f"Причина: {escape(exception_reason(exc, 300))}",
                    kind="etl_alert",
                )
        except Exception:  # noqa: BLE001 — алерт не должен маскировать исключение
            pass
        raise

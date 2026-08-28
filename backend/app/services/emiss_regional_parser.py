"""Помесячный парсер ЕМИСС (fedstat.ru) для регионального контура (ADR-0008).

Первая и пока единственная автоматическая витрина — потребительские цены на
автомобильное топливо по субъектам РФ (dataset 31448): АИ-92, АИ-95,
дизельное топливо, руб./л, месячная частота. Пишет в таблицу
``region_monthly_data`` — отдельную от годовой ``region_data`` (trap
annual-in-monthly mixing, CONTEXT.md).

Механика dataGrid.do (проверена живьём 2026-08-26/27, scripts/regional/fetch_emiss_fuel.py):

- все обязательные измерения должны иметь хотя бы одно выбранное значение,
  иначе источник отдаёт пустой ответ;
- территории (измерение 57831) перечисляются явно — «все территории» не
  отдаётся; список ОКАТО-кодов живёт в scripts/regional/emiss_okato_31448.json
  (переиспользуется — одна точка истины для маппинга территорий);
- РФ в витрине с 2023 года — значение «Российская Федерация без учета новых
  субъектов» (1849012): каноническое 1688487 с 2023 пусто; до 2022 наоборот,
  поэтому парсер грузит обе и пишет в один slug ``russia`` (на стыке
  методологически однородны — средние цены, состав субъектов на уровень не
  влияет заметно);
- месяцы не смешиваются в одном запросе: ключ ячейки не содержит период,
  значения схлопываются в последнюю выбранную ячейку — фетч идёт запросами
  «год × месяц», каждый отдаёт все территории и все три топлива (~0.8 с).

Инкрементальность: за прогон запрашиваются только месяцы, которых ещё нет в
БД для slug ``russia`` (РФ публикуется первой и полной), плюс текущий месяц
на случай ревизии. Отсутствие точек по региону за существующий месяц —
легитимно (источник иногда дозаливает задним числом): гэпы не вычищаем,
значения не удаляем — только добавляем/обновляем по фактическому payload.

Идемпотентность ADR-0002: ON CONFLICT DO UPDATE с guard'ом ``value <>
excluded.value`` — повторный прогон без изменений не пишет в БД и не
инвалидирует кэш.

Обновление: ежемесячный job ``emiss_regional_job`` (25-е число, 07:40 МСК —
после фактической публикации цен за отчётный месяц в середине следующего).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import date
from pathlib import Path
from typing import Callable, Sequence

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import bump_namespaces
from app.database import async_session
from app.models import Region, RegionIndicator, RegionMonthlyPoint

logger = logging.getLogger(__name__)

DATA_GRID_URL = "https://www.fedstat.ru/indicator/dataGrid.do"
_UA = "ForecastEconomy/1.0 (+https://forecasteconomy.com)"
_INDICATOR_ID = 31448
_RUSSIA_ID = "1849012"
_RUSSIA_LEGACY = "1688487"

# 58273 «Виды товаров и услуг» витрины 31448 → коды региональных показателей.
PRICE_FUELS = {
    "1709730": "ceni-ai92",
    "1709750": "ceni-ai95",
    "1755196": "ceni-dt",
}

# 33560 «Период»: месяц-в-году → порядковый номер месяца.
MONTH_OIDS = {
    "1540283": 1, "1540282": 2, "1540236": 3, "1540229": 4,
    "1540235": 5, "1540234": 6, "1540233": 7, "1540228": 8,
    "1540276": 9, "1540273": 10, "1540272": 11, "1540230": 12,
}

# Справочник «slug → ОКАТО-oid витрины 31448» лежит в артефактной папке
# регионального контекста: backend — отдельный build context Docker
# (docker-compose.yml), scripts/ в образ не попадает.
_OKATO_PATH = Path(__file__).resolve().parents[1] / "data" / "regional" / "emiss_okato_31448.json"

_FETCH_TIMEOUT = 60.0
_ATTEMPTS = 4
_PAUSE_BETWEEN_REQUESTS = 0.4


def load_territory_ids(path: Path = _OKATO_PATH) -> list[str]:
    """ОКАТО-коды территорий витрины 31448 из справочника (85 субъектов + РФ)."""
    mapping = json.loads(path.read_text(encoding="utf-8"))
    return sorted(set(mapping.values()) | {_RUSSIA_ID})


def parse_ru_float(raw) -> float | None:
    """«10,74» / «1 234,5» / «-» → float | None (источник отдаёт ru-локаль)."""
    if raw in (None, "", "-"):
        return None
    try:
        return float(str(raw).replace("\xa0", "").replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def key_fuel_oid(key: str, fuels: dict[str, str]) -> str | None:
    """Код товара из dim-ключа ячейки ``dim<товар>_d…_i…``."""
    for part in key[3:].split("_"):
        if part in fuels:
            return part
        if part.startswith("d") and part[1:].isdigit():
            break
    return None


def parse_grid_response(
    payload: dict,
    *,
    year: int,
    month: int,
    dimnames: dict[str, str],
    fuels: dict[str, str] = PRICE_FUELS,
) -> list[tuple[str, str, int, float]]:
    """JSON-ответ dataGrid.do → [(indicator_code, region_slug, YYYYMM, value)].

    Каноническая РФ-строка (1688487) схлопывается в slug ``russia`` — тот же,
    куда пишет витрина «без новых субъектов» с 2023 года.
    """
    points: list[tuple[str, str, int, float]] = []
    period = year * 100 + month
    for row in payload.get("results", []):
        okato = str(row.get("dim57831") or "")
        slug = dimnames.get(okato)
        if okato == _RUSSIA_LEGACY:
            slug = "russia"
        if not slug:
            continue
        for key, raw in row.items():
            if "_d" not in key:
                continue
            fuel_oid = key_fuel_oid(key, fuels)
            code = fuels.get(fuel_oid or "")
            if not code:
                continue
            value = parse_ru_float(raw)
            if value is None or value <= 0:
                continue
            points.append((code, slug, period, value))
    return points


async def fetch_month_points(
    year: int,
    month: int,
    territory_ids: Sequence[str],
    dimnames: dict[str, str],
    *,
    post_grid: Callable | None = None,
) -> list[tuple[str, str, int, float]]:
    """Точки одного месяца: запрос «год × месяц» → все территории × 3 топлива.

    ``post_grid`` инъекцией для тестов (сигнатура async (indicator_id, params) → dict).
    """
    if post_grid is None:
        post_grid = _post_grid
    month_oid = next(oid for oid, m in MONTH_OIDS.items() if m == month)
    params: list[tuple[str, str]] = [
        ("lineObjectIds", "57831"),
        ("columnObjectIds", "58273"),
        ("selectedFilterIds", f"0_{_INDICATOR_ID}"),
        ("selectedFilterIds", f"3_{year}"),
        ("selectedFilterIds", "30611_950351"),
        ("selectedFilterIds", f"33560_{month_oid}"),
    ]
    params += [("selectedFilterIds", f"58273_{f}") for f in PRICE_FUELS]
    params += [("selectedFilterIds", f"57831_{oid}") for oid in territory_ids]
    # Каноническая РФ пуста с 2023, но до 2022 — единственный источник ряда.
    if year <= 2022:
        params.append(("selectedFilterIds", f"57831_{_RUSSIA_LEGACY}"))
    payload = await post_grid(_INDICATOR_ID, params)
    return parse_grid_response(payload, year=year, month=month, dimnames=dimnames)


async def _post_grid(indicator_id: int, params: list[tuple[str, str]]) -> dict:
    """POST dataGrid.do с ретраями транзиентных сбоев (сетевой источник нестабилен)."""
    import urllib.parse

    encoded = urllib.parse.urlencode(params).encode()
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": _UA,
        "Referer": f"https://www.fedstat.ru/indicator/{indicator_id}",
    }
    last_err: Exception | None = None
    async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT, follow_redirects=True) as client:
        for attempt in range(_ATTEMPTS):
            try:
                resp = await client.post(
                    f"{DATA_GRID_URL}?id={indicator_id}",
                    content=encoded,
                    headers=headers,
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:  # noqa: BLE001 — ретрай транзиентных сбоев
                last_err = exc
                await asyncio.sleep(2 * (attempt + 1))
    raise RuntimeError(f"dataGrid.do?id={indicator_id}: {last_err}")


def months_to_fetch(
    existing: set[int],
    *,
    today: date | None = None,
    first_year: int = 2003,
) -> list[tuple[int, int]]:
    """Какие (year, month) запросить: новые месяцы сверх БД + хвост на ревизию.

    Опорная серия — slug ``russia``: публикуется первой и полной, по ней же
    в fetch-скрипте определялся пол витрины (до 2003 данных нет).
    """
    today = today or date.today()
    existing_months = sorted(m for m in existing)
    last = existing_months[-1] if existing_months else first_year * 100
    y, m = last // 100, last % 100
    out: list[tuple[int, int]] = []
    # Гарантированный хвост: два месяца от последнего в БД — ловит дозаливы
    # и ревизии значений задним числом, которые источник делает регулярно.
    for _ in range(2):
        m += 1
        if m > 12:
            m, y = 1, y + 1
        out.append((y, m))
    # Плюс все новые месяцы до текущего (после простоя парсера догонит серией).
    cur_y, cur_m = today.year, today.month
    while True:
        last_y, last_m = out[-1]
        if (last_y, last_m) >= (cur_y, cur_m):
            break
        m2 = last_m + 1
        y2 = last_y
        if m2 > 12:
            m2, y2 = 1, y2 + 1
        out.append((y2, m2))
    # Ревизия текущего и прошлого месяца — всегда (значения могут уточняться).
    if (cur_y, cur_m) not in out:
        out.append((cur_y, cur_m))
    return out


async def run_emiss_regional_update(
    db: AsyncSession,
    *,
    post_grid: Callable | None = None,
    territory_ids: Sequence[str] | None = None,
    dimnames: dict[str, str] | None = None,
) -> dict[str, int]:
    """Полный цикл обновления: fetch → upsert → invalidate. Возвращает счётчики.

    Идемпотентен (ADR-0002): guard ``value <> excluded.value`` — прогон без
    изменений возвращает added=updated=0 и не инвалидирует кэш.
    """
    if dimnames is None:
        # Справочник «ОКАТО-oid → slug»: и территориальные id, и сопоставление
        # slug'ов — из одного файла (одна точка истины, emiss_dimnames.json в
        # scripts/regional — dev-копия того же маппинга).
        dimnames = json.loads(_OKATO_PATH.read_text(encoding="utf-8"))
    if territory_ids is None:
        territory_ids = load_territory_ids()

    codes = list(PRICE_FUELS.values())
    indicators = {
        code: ind
        for code, ind in (
            await db.execute(
                select(RegionIndicator).where(RegionIndicator.code.in_(codes))
            )
        ).all()
        if ind
    }
    missing = [c for c in codes if c not in indicators]
    if missing:
        raise RuntimeError(f"region_monthly: нет метаданных показателей {missing}")

    regions = {
        slug: rid
        for slug, rid in (await db.execute(select(Region.slug, Region.id))).all()
    }

    # Опорная серия russia: какие месяцы уже есть — по ней строим план фетча.
    rf = await db.get(Region, regions.get("russia")) if regions.get("russia") else None
    existing: set[int] = set()
    if rf is not None:
        rf_code = next(iter(PRICE_FUELS.values()))
        existing = set((await db.execute(
            select(RegionMonthlyPoint.month)
            .where(RegionMonthlyPoint.indicator_id == indicators[rf_code].id,
                   RegionMonthlyPoint.region_id == rf.id)
        )).scalars().all())

    plan = months_to_fetch(existing)
    if not plan:
        return {"months": 0, "added": 0, "updated": 0}

    added = updated = 0
    for year, month in plan:
        points = await fetch_month_points(
            year, month, territory_ids, dimnames, post_grid=post_grid,
        )
        by_code: dict[str, list[tuple[str, int, float]]] = {}
        for code, slug, period, value in points:
            by_code.setdefault(code, []).append((slug, period, value))
        for code, rows in by_code.items():
            ind_id = indicators[code].id
            values = [
                (ind_id, regions[slug], period, value)
                for slug, period, value in rows
                if slug in regions
            ]
            if not values:
                continue
            a, u = await _upsert_monthly_points(db, values)
            added += a
            updated += u
        await db.commit()
        logger.info(
            "emiss_regional: %04d-%02d parsed %d points (added=%d updated=%d)",
            year, month, len(points), added, updated,
        )
        await asyncio.sleep(_PAUSE_BETWEEN_REQUESTS)

    if added or updated:
        await bump_namespaces("regions")
    return {"months": len(plan), "added": added, "updated": updated}


async def _upsert_monthly_points(
    db: AsyncSession,
    values: list[tuple[int, int, int, float]],
) -> tuple[int, int]:
    """INSERT … ON CONFLICT DO UPDATE (guard value) для region_monthly_data."""
    stmt = pg_insert(RegionMonthlyPoint).values([
        {
            "indicator_id": ind_id,
            "region_id": reg_id,
            "month": period,
            "value": value,
        }
        for ind_id, reg_id, period, value in values
    ])
    result = await db.execute(
        stmt.on_conflict_do_update(
            constraint="uq_region_monthly_point",
            set_={"value": stmt.excluded.value},
            where=(RegionMonthlyPoint.__table__.c.value != stmt.excluded.value),
        ).returning(literal_inserted())
    )
    rows = result.fetchall()
    added = sum(1 for (ins,) in rows if ins)
    updated = len(rows) - added
    await db.flush()
    return added, updated


def literal_inserted():
    from sqlalchemy import literal_column

    return literal_column("(xmax = 0)").label("inserted")


async def emiss_regional_job() -> dict[str, int]:
    """Точка входа планировщика: обновление региональных цен на топливо."""
    started = time.monotonic()
    try:
        async with async_session() as db:
            stats = await run_emiss_regional_update(db)
        if stats["added"] or stats["updated"]:
            from app.services.alerting import send_telegram

            await send_telegram(
                f"⛽ <b>Региональные цены на топливо обновлены</b>\n"
                f"Месяцев: {stats['months']}, новых точек: {stats['added']}, "
                f"ревизий: {stats['updated']}",
                kind="etl_summary",
            )
        logger.info(
            "emiss_regional_job done in %.1fs: %s", time.monotonic() - started, stats,
        )
        return stats
    except Exception:
        logger.exception("emiss_regional_job failed")
        from app.services.alerting import send_telegram

        try:
            await send_telegram(
                "🔴 <b>Парсер региональных цен на топливо упал</b> — смотри логи backend",
                kind="etl_alert",
            )
        except Exception:  # noqa: BLE001 — алерт не должен маскировать исключение
            pass
        raise

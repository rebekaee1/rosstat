"""Поисковый индекс: маленькие копии того, что поиск читает при каждом запросе (18.11.2026, ADR-0036).

Зачем. Поиск вызывается при наборе, после каждой паузы 300 мс. 18.11.2026 на боевом одно слово отвечало 1,8–30 с
(«уровень» 30,6 с). Почти всё это время — чтение с диска: база 13 ГБ при 0,9 ГБ памяти, а поиск в каждом запросе
читал широкие строки `world_indicators` (700 МБ: 2 КБ на строку, из них поиску нужно меньше трети), проверял
«есть ли факт» у сотен рядов в `world_data_points` (1,6 ГБ) и у пар «показатель × регион» в `region_monthly_data`
(13 млн строк). Каждое такое чтение — отдельная холодная страница.

Что здесь. Три части индекса, каждая — копия нужных поиску столбцов с готовой отметкой «есть данные»:

* `world` — `search_world_a/b`: строки мирового каталога без описаний и SEO-текстов страницы и с `has_fact`
  (есть ненулевой конечный факт, как `search._world_fact` без периода). Строки лежат в порядке выдачи
  (`ord`): широкое слово («уровень», «индекс») берёт первые строки подряд по индексу порядка, а не
  сортирует весь каталог;
* `russia` — `search_russia_a/b`: активные ряды России с `has_fact` (есть конечный факт);
* `territory` — `search_region_facts_a/b` (есть годовая / месячная конечная точка у пары «показатель × регион»)
  и `search_subnational_facts_a/b` (есть конечная точка у пары «показатель × штат»).

Выдача та же: индекс хранит ровно те значения, по которым поиск отбирал и сортировал, а условие «есть факт» — то же
условие, посчитанное заранее. Запрос с годом или месяцем («инфляция 2023») проверяет факт периода и читает основные
таблицы, как раньше. Если часть не собрана, выключена (`search_index_enabled`) или таблиц нет, поиск тоже читает
основные таблицы.

Свежесть. Задача планировщика `search_index_job` раз в `search_index_check_minutes` сверяет счётчики изменений
основных таблиц (`pg_stat_user_tables`) с теми, из которых собрана действующая копия, и пересобирает часть, если
они изменились и с прошлой сборки прошло не меньше `search_index_min_interval_minutes`. Новый ряд появляется в
поиске после ближайшей пересборки (обычно меньше часа после заливки); до неё поиск показывает каталог на момент сборки.

Две копии. Сборка пишет в недействующую копию (`TRUNCATE` + `INSERT … ORDER BY`), затем одной транзакцией
переключает `search_index_state.active`. Читатель берёт указатель (память процесса на `STATE_TTL_SECONDS`) и читает
целую копию; блокировок он не ждёт. Прежняя копия очищается после паузы дольше памяти процесса.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import Integer, Table, and_, exists, func, insert, literal, literal_column, select, text, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    Indicator, IndicatorData, RegionDataPoint, RegionMonthlyPoint, SearchIndexState, SearchRegionFactA,
    SearchRegionFactB, SearchRussiaRowA, SearchRussiaRowB, SearchSubnationalFactA, SearchSubnationalFactB,
    SearchWorldRowA, SearchWorldRowB, SubnationalDataPoint, WorldDataPoint, WorldIndicator,
)

logger = logging.getLogger(__name__)

PARTS = ("world", "russia", "territory")
COPIES = ("a", "b")
# Указатель действующей копии живёт в памяти процесса столько секунд; прежняя копия очищается не раньше чем через
# `_RELEASE_AFTER_SECONDS` после переключения, поэтому процесс с устаревшим указателем дочитывает целую копию.
STATE_TTL_SECONDS = 10.0
_RELEASE_AFTER_SECONDS = 90.0
# Сборка идёт в фоне: ей можно дольше, чем публичному запросу (30 с).
_BUILD_STATEMENT_TIMEOUT_MS = 30 * 60 * 1000
_ADVISORY_LOCK_KEY = 0x5EA2_C41D  # одна сборка за раз на всю базу

_TABLES: dict[str, dict[str, tuple[type, ...]]] = {
    "world": {"a": (SearchWorldRowA,), "b": (SearchWorldRowB,)},
    "russia": {"a": (SearchRussiaRowA,), "b": (SearchRussiaRowB,)},
    "territory": {"a": (SearchRegionFactA, SearchSubnationalFactA), "b": (SearchRegionFactB, SearchSubnationalFactB)},
}
# Основные таблицы, из которых собрана часть: их счётчики изменений — подпись копии.
_SOURCES = {
    "world": ("world_indicators", "world_data_points"),
    "russia": ("indicators", "indicator_data"),
    "territory": ("region_data", "region_monthly_data", "subnational_data_points"),
}


@dataclass(frozen=True)
class ActiveIndex:
    """Таблицы действующих копий; None — часть не собрана, поиск читает основные таблицы."""

    world: Table | None = None
    russia: Table | None = None
    region_facts: Table | None = None
    subnational_facts: Table | None = None


EMPTY = ActiveIndex()
_state_cache: dict[str, object] = {"checked": float("-inf"), "value": EMPTY}


def reset_cache() -> None:
    """Забыть указатель (тесты и сразу после сборки в том же процессе)."""
    _state_cache["checked"] = float("-inf")
    _state_cache["value"] = EMPTY


def _index_from_state(active: dict[str, str]) -> ActiveIndex:
    world = _TABLES["world"].get(active.get("world") or "")
    russia = _TABLES["russia"].get(active.get("russia") or "")
    territory = _TABLES["territory"].get(active.get("territory") or "")
    return ActiveIndex(
        world=world[0].__table__ if world else None,
        russia=russia[0].__table__ if russia else None,
        region_facts=territory[0].__table__ if territory else None,
        subnational_facts=territory[1].__table__ if territory else None,
    )


async def active_index(db: AsyncSession) -> ActiveIndex:
    """Действующие копии частей индекса. Сбой чтения указателя (таблицы ещё нет) — пустой индекс, без ошибки.

    Чтение идёт в savepoint: отсутствие таблицы (код раньше миграции) не портит транзакцию поиска.
    """
    if not settings.search_index_enabled:
        return EMPTY
    now = time.monotonic()
    if now - float(_state_cache["checked"]) < STATE_TTL_SECONDS:
        return _state_cache["value"]  # type: ignore[return-value]
    try:
        async with db.begin_nested():
            rows = (await db.execute(select(SearchIndexState.part, SearchIndexState.active))).all()
        value = _index_from_state({part: active for part, active in rows if active in COPIES})
    except Exception as exc:  # noqa: BLE001 — любой сбой чтения указателя = поиск по основным таблицам
        logger.warning("search index state unavailable: %s", type(exc).__name__)
        value = EMPTY
    _state_cache["checked"] = now
    _state_cache["value"] = value
    return value


def _finite(column):
    """Те же границы, что у условий факта поиска (`search._finite`): без NaN и бесконечностей PostgreSQL."""
    return and_(column.is_not(None), column > literal_column("-1e30"), column < literal_column("1e30"))


def _world_rows(target: Table):
    w = WorldIndicator
    # Ровно условие `search._world_fact` без периода: ненулевой конечный факт.
    fact = exists(select(1).where(WorldDataPoint.indicator_id == w.id, WorldDataPoint.value != literal_column("0"),
                                  _finite(WorldDataPoint.value)))
    columns = ("id", "country_id", "provider", "code", "dataset_id", "slice_json", "slice_hash", "name_ru", "name_en",
               "unit", "unit_ru", "frequency", "category_ru", "seo_keywords", "is_listed", "points_count", "history_end")
    order = (w.is_listed.desc(), w.code)
    source = select(*(getattr(w, name) for name in columns), func.row_number().over(order_by=order),
                    func.row_number().over(partition_by=w.country_id, order_by=order), fact.label("has_fact"))
    # Порядок вставки = порядок выдачи: страницы копии идут в том же порядке, что номера `ord`.
    source = source.order_by(*order)
    return [insert(target).from_select([*columns, "ord", "country_ord", "has_fact"], source)]


def _russia_rows(target: Table):
    i = Indicator
    # Ровно условие `search._russia` без периода: есть конечный факт.
    fact = exists(select(1).where(IndicatorData.indicator_id == i.id, _finite(IndicatorData.value)))
    columns = ("id", "code", "name", "name_en", "unit", "frequency", "category", "seo_keywords", "is_listed")
    source = select(*(getattr(i, name) for name in columns), fact.label("has_fact")).where(
        i.is_active.is_(True)).order_by(i.id)
    return [insert(target).from_select([*columns, "has_fact"], source)]


def _territory_rows(region_target: Table, subnational_target: Table):
    annual, monthly = RegionDataPoint, RegionMonthlyPoint
    # Последний период с конечной точкой у пары: год и месяц. Есть период — есть факт (условие `search._annual_fact`
    # и `_monthly_fact` без периода). Точка пары за период одна (уникальный ключ), её значение — последнее значение
    # пары, как в `search_regional_groups._latest_by_region`.
    last = union_all(
        select(annual.indicator_id.label("indicator_id"), annual.region_id.label("region_id"),
               func.max(annual.year).label("last_year"), literal(None, Integer).label("last_month")).where(
            _finite(annual.value)).group_by(annual.indicator_id, annual.region_id),
        select(monthly.indicator_id, monthly.region_id, literal(None, Integer), func.max(monthly.month)).where(
            _finite(monthly.value)).group_by(monthly.indicator_id, monthly.region_id),
    ).subquery()
    pairs = select(last.c.indicator_id, last.c.region_id, func.max(last.c.last_year).label("last_year"),
                   func.max(last.c.last_month).label("last_month")).group_by(last.c.indicator_id, last.c.region_id).subquery()
    year_value = select(annual.value).where(annual.indicator_id == pairs.c.indicator_id,
        annual.region_id == pairs.c.region_id, annual.year == pairs.c.last_year).scalar_subquery()
    month_value = select(monthly.value).where(monthly.indicator_id == pairs.c.indicator_id,
        monthly.region_id == pairs.c.region_id, monthly.month == pairs.c.last_month).scalar_subquery()
    regional = select(pairs.c.indicator_id, pairs.c.region_id, pairs.c.last_year.is_not(None),
                      pairs.c.last_month.is_not(None), pairs.c.last_year, year_value, pairs.c.last_month,
                      month_value).order_by(pairs.c.indicator_id, pairs.c.region_id)
    subnational = select(SubnationalDataPoint.indicator_id, SubnationalDataPoint.region_id).where(
        _finite(SubnationalDataPoint.value)).distinct().order_by(
        SubnationalDataPoint.indicator_id, SubnationalDataPoint.region_id)
    return [
        insert(region_target).from_select(["indicator_id", "region_id", "has_annual", "has_monthly", "last_year",
                                           "last_year_value", "last_month", "last_month_value"], regional),
        insert(subnational_target).from_select(["indicator_id", "region_id"], subnational),
    ]


async def _signature(db: AsyncSession, part: str) -> str | None:
    """Счётчики вставок, изменений и удалений основных таблиц части; None — база их не ведёт (SQLite)."""
    if db.get_bind().dialect.name != "postgresql":
        return None
    rows = (await db.execute(text(
        "SELECT relname, n_tup_ins, n_tup_upd, n_tup_del FROM pg_stat_user_tables "
        "WHERE relid = ANY(ARRAY(SELECT to_regclass(name) FROM unnest(CAST(:names AS text[])) AS name))"
    ), {"names": list(_SOURCES[part])})).all()
    return ";".join(f"{name}:{ins}/{upd}/{dele}" for name, ins, upd, dele in sorted(rows))


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _truncate(db: AsyncSession, tables: tuple[type, ...]) -> None:
    if db.get_bind().dialect.name == "postgresql":
        await db.execute(text("TRUNCATE " + ", ".join(model.__tablename__ for model in tables)))
    else:
        for model in tables:
            await db.execute(model.__table__.delete())


async def build_part(db: AsyncSession, part: str, *, force: bool = False) -> dict:
    """Собрать часть индекса в недействующую копию и переключить указатель. Одна транзакция.

    Без `force` сборка идёт, только если подпись основных таблиц изменилась и с прошлой сборки прошло не меньше
    `search_index_min_interval_minutes`. Возвращает отчёт: что сделано, какая копия, сколько строк и секунд.
    """
    if part not in PARTS:
        raise ValueError(f"unknown search index part {part!r}")
    postgres = db.get_bind().dialect.name == "postgresql"
    if postgres:
        await db.execute(text("SELECT set_config('statement_timeout', :v, true)"),
                         {"v": str(_BUILD_STATEMENT_TIMEOUT_MS)})
        await db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _ADVISORY_LOCK_KEY})
    state = await db.get(SearchIndexState, part)
    signature = await _signature(db, part)
    if not force and state is not None and state.active in COPIES:
        active = state.active
        if signature is not None and state.signature == signature:
            await db.rollback()
            return {"part": part, "status": "fresh", "active": active}
        min_age = timedelta(minutes=max(0, settings.search_index_min_interval_minutes))
        if state.built_at is not None and _utcnow_naive() - state.built_at < min_age:
            await db.rollback()
            return {"part": part, "status": "deferred", "active": active}
    previous = state.active if state is not None and state.active in COPIES else None
    target = "b" if previous == "a" else "a"
    models = _TABLES[part][target]
    started = time.monotonic()
    await _truncate(db, models)
    tables = tuple(model.__table__ for model in models)
    statements = (_world_rows(*tables) if part == "world" else _russia_rows(*tables) if part == "russia"
                  else _territory_rows(*tables))
    for statement in statements:
        await db.execute(statement)
    if postgres:
        for model in models:
            await db.execute(text(f"ANALYZE {model.__tablename__}"))
    rows = 0
    for model in models:
        rows += int((await db.execute(select(func.count()).select_from(model.__table__))).scalar() or 0)
    seconds = round(time.monotonic() - started, 2)
    if state is None:
        state = SearchIndexState(part=part)
        db.add(state)
    state.active, state.built_at, state.signature, state.rows, state.seconds = (
        target, _utcnow_naive(), signature, rows, seconds)
    await db.commit()
    reset_cache()
    logger.info("search index %s: built copy %s, %d rows, %.1f s", part, target, rows, seconds)
    return {"part": part, "status": "built", "active": target, "previous": previous, "rows": rows, "seconds": seconds}


async def release_copy(db: AsyncSession, part: str, copy: str) -> bool:
    """Очистить недействующую копию части (место на диске). Не ждёт читателей дольше 5 с; при отказе — False."""
    state = await db.get(SearchIndexState, part)
    if state is not None and state.active == copy:
        await db.rollback()
        return False
    models = _TABLES[part][copy]
    try:
        if db.get_bind().dialect.name == "postgresql":
            await db.execute(text("SET LOCAL lock_timeout = '5s'"))
        await _truncate(db, models)
        await db.commit()
        return True
    except Exception as exc:  # noqa: BLE001 — копию очистит следующая сборка
        await db.rollback()
        logger.info("search index %s: copy %s not released yet (%s)", part, copy, type(exc).__name__)
        return False


async def refresh(parts: tuple[str, ...] = PARTS, *, force: bool = False, session_maker=None,
                  release_after: float = _RELEASE_AFTER_SECONDS) -> list[dict]:
    """Проверить и при необходимости пересобрать части; после переключения очистить прежние копии."""
    if session_maker is None:
        from app.database import async_session as session_maker
    reports, released = [], []
    for part in parts:
        try:
            async with session_maker() as db:
                report = await build_part(db, part, force=force)
        except Exception:
            logger.exception("search index %s: build failed, search keeps the previous copy", part)
            report = {"part": part, "status": "failed"}
        reports.append(report)
        if report.get("status") == "built" and report.get("previous"):
            released.append((part, report["previous"]))
    if released:
        await asyncio.sleep(release_after)
        for part, copy in released:
            async with session_maker() as db:
                await release_copy(db, part, copy)
    return reports


async def search_index_job() -> None:
    """Задача планировщика: no-op, пока `search_index_enabled` выключен."""
    if not settings.search_index_enabled:
        return
    for report in await refresh():
        if report.get("status") == "built":
            logger.info("search index refresh: %s", report)

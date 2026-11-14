"""Основная версия для рядов стран мира, которые совпадают точно (14.11.2026).

Замер 14.11 (локальная копия каталога): после уточнения среза в названиях (`world_series_title`)
одинаковые названия остались у рядов, которые Евростат публикует в нескольких наборах — например,
«Уровень безработицы 15–74 лет» Дании в трёх наборах обследования рабочей силы (по образованию, по
гражданству, по стране рождения) с одними и теми же 111 точками. 4 278 таких групп; в них 7 434
неосновных карточки. Карточки не удаляются и не склеиваются, адреса не меняются: неосновная карточка
и её годовые страницы получают `rel=canonical` (и hreflang) на основную версию того же года и не
попадают в sitemap.

Группа — ряды одной страны с одинаковым публичным именем, одной частотой и одинаковым смысловым
срезом (без учёта «итого» и измерений, которых у набора нет), у которых данные совпадают точно
(отпечаток всех точек). Группы с частичным совпадением и разными данными не трогаются. Основная
версия — самая свежая последняя точка, затем самая длинная история, число точек, набор Евростата,
код (детерминированно). Неосновная, у которой карточка или годовые страницы имели показы в Search
Console, остаётся без canonical и в sitemap.

Список строится ночной сборкой sitemap и пишется в опубликованную генерацию
(`world-canonical.json`, вне каталогов хостов — наружу не отдаётся); серверная страница читает его.
Откат — `RUSTATS_WORLD_DUPLICATE_CANONICAL=false` (sitemap и canonical прежние).
"""
from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from typing import Any, Iterable

logger = logging.getLogger(__name__)

CANONICAL_FILE = "world-canonical.json"
_TECHNICAL = frozenset({"freq", "geo"})
_FREQ_RANK = {"monthly": 0, "m": 0, "quarterly": 1, "q": 1, "annual": 2, "a": 2}
_DIGEST_BATCH = 2000
_RECHECK_SECONDS = 300.0
_cache: dict[str, Any] = {"checked": None, "key": None, "map": None}


def _slice(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}


def slice_signature(slice_json: Any) -> frozenset[tuple[str, str]]:
    """Смысловой срез: значения не «итого», без частоты и географии (нет измерения = «итого»)."""
    from app.data.eurostat_dim_labels_ru import is_dim_totalish

    out = set()
    for axis, value in _slice(slice_json).items():
        if axis in _TECHNICAL or value is None:
            continue
        text = str(value).strip()
        if not text or is_dim_totalish(axis, text) or (axis == "age" and text.upper() == "Y15-74"):
            continue
        out.add((axis, text.upper()))
    return frozenset(out)


def primary_key(row: Any) -> tuple:
    """Порядок выбора основной версии: свежесть, частота, длина истории, точки, Евростат, код."""
    end = row.history_end.toordinal() if row.history_end else 0
    span = (row.history_end.year - row.history_start.year) if (row.history_end and row.history_start) else 0
    return (
        -end,
        _FREQ_RANK.get((row.frequency or "").lower(), 3),
        -span,
        -(row.points_count or 0),
        (row.provider or "") != "eurostat",
        row.code,
    )


def candidate_groups(rows: Iterable[Any]) -> list[list[Any]]:
    """Группы рядов одной страны с одинаковым публичным именем, частотой и смысловым срезом."""
    from app.services.world_series_title import _base_name

    groups: dict[tuple, list[Any]] = defaultdict(list)
    for row in rows:
        key = (
            row.country_id,
            _base_name(row, "ru"),
            (row.frequency or "").lower(),
            slice_signature(row.slice_json),
        )
        groups[key].append(row)
    return [members for members in groups.values() if len(members) > 1]


def resolve_map(
    groups: list[list[Any]], digests: dict[int, str], kept: set[tuple[str, str]],
) -> dict[str, dict[str, str]]:
    """slug страны → {код неосновной: код основной} для групп с точно совпадающими данными."""
    out: dict[str, dict[str, str]] = defaultdict(dict)
    for members in groups:
        fingerprints = {digests.get(row.id) for row in members}
        if len(fingerprints) != 1 or None in fingerprints:
            continue  # частичное совпадение или нет данных — не трогаем
        ordered = sorted(members, key=primary_key)
        primary = ordered[0]
        for row in ordered[1:]:
            if (row.slug, row.code) in kept:
                continue  # были показы в поиске — остаётся как есть
            out[row.slug][row.code] = primary.code
    return dict(out)


async def _load_rows(db) -> list[Any]:
    from sqlalchemy import select

    from app.models import WorldCountry, WorldIndicator

    rows = (await db.execute(
        select(
            WorldIndicator.id, WorldIndicator.country_id, WorldCountry.slug, WorldIndicator.code,
            WorldIndicator.name_ru, WorldIndicator.name_en, WorldIndicator.slice_json,
            WorldIndicator.provider, WorldIndicator.frequency, WorldIndicator.points_count,
            WorldIndicator.history_start, WorldIndicator.history_end,
        )
        .join(WorldCountry, WorldCountry.id == WorldIndicator.country_id)
        .where(WorldIndicator.is_listed.is_(True), WorldCountry.is_active.is_(True))
    )).all()
    return list(rows)


async def _digests(db, ids: list[int]) -> dict[int, str]:
    from sqlalchemy import text

    out: dict[int, str] = {}
    for start in range(0, len(ids), _DIGEST_BATCH):
        chunk = ids[start:start + _DIGEST_BATCH]
        rows = (await db.execute(text(
            "SELECT indicator_id, md5(string_agg(date::text || ':' || round(value::numeric, 6)::text, ',' "
            "ORDER BY date)) FROM world_data_points WHERE indicator_id = ANY(:ids) GROUP BY indicator_id"
        ), {"ids": chunk})).all()
        out.update({int(i): str(d) for i, d in rows})
    return out


async def _searched(db) -> set[tuple[str, str]]:
    """(страна, код) рядов, у которых карточка или годовая страница имела показы в Search Console."""
    from sqlalchemy import text

    rows = (await db.execute(text(
        "SELECT DISTINCT page FROM gsc_page_daily WHERE impressions > 0 "
        "UNION SELECT DISTINCT page FROM gsc_search_queries WHERE impressions > 0 "
        "AND date >= CURRENT_DATE - 120"
    ))).all()
    out: set[tuple[str, str]] = set()
    for (page,) in rows:
        path = "/" + str(page).split("://", 1)[-1].split("/", 1)[-1] if "://" in str(page) else str(page)
        parts = path.strip("/").split("/")
        if len(parts) >= 3 and parts[1] == "indicator":
            out.add((parts[0], parts[2]))
    return out


async def build_duplicate_map(db) -> dict[str, dict[str, str]]:
    """Список «неосновная → основная» для ночной сборки sitemap; ошибка — пустой список."""
    rows = await _load_rows(db)
    groups = candidate_groups(rows)
    ids = sorted({row.id for members in groups for row in members})
    digests = await _digests(db, ids)
    try:
        kept = await _searched(db)
    except Exception:  # noqa: BLE001 - без данных Search Console безопаснее не ставить canonical
        logger.warning("world canonical: Search Console pages unavailable — no canonical", exc_info=True)
        return {}
    return resolve_map(groups, digests, kept)


def excluded_pairs(mapping: dict[str, dict[str, str]]) -> set[tuple[str, str]]:
    return {(slug, code) for slug, codes in mapping.items() for code in codes}


def drop_from_sitemap(urls: list, excluded: set[tuple[str, str]]) -> list:
    """Убрать из шарда карточки неосновных рядов и их годовые страницы (адреса /{страна}/indicator/{код}[/…])."""
    if not excluded:
        return urls
    kept = []
    for url in urls:
        parts = url.path.strip("/").split("/")
        if len(parts) >= 3 and parts[1] == "indicator" and (parts[0], parts[2]) in excluded:
            continue
        kept.append(url)
    return kept


def write_map(generation, mapping: dict[str, dict[str, str]]) -> None:
    payload = {"pairs": sum(len(v) for v in mapping.values()), "map": mapping}
    (generation / CANONICAL_FILE).write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def enabled() -> bool:
    from app.config import settings

    return bool(settings.world_duplicate_canonical)


def published_map() -> dict[str, dict[str, str]]:
    """Список из опубликованной генерации sitemap (кэш процесса, проверка файла раз в 5 минут)."""
    from app.services.sitemap_static import _current_generation

    now = time.monotonic()
    if _cache["checked"] is not None and now - _cache["checked"] < _RECHECK_SECONDS:
        return _cache["map"] or {}
    _cache["checked"] = now
    try:
        generation = _current_generation()
        path = generation / CANONICAL_FILE if generation is not None else None
        if path is None or not path.is_file():
            _cache.update(key=None, map={})
            return {}
        key = (str(path), path.stat().st_mtime_ns)
        if key != _cache["key"]:
            _cache.update(key=key, map=json.loads(path.read_text(encoding="utf-8")).get("map", {}))
    except (OSError, ValueError):
        _cache.update(key=None, map={})
    return _cache["map"] or {}


def non_primary_codes(slug: str) -> frozenset[str]:
    """Коды неосновных версий страны — ссылки на них не ставятся (каталог, соседи, «в других странах»)."""
    if not enabled():
        return frozenset()
    return frozenset(published_map().get(slug, {}))


def primary_code(slug: str, code: str) -> str | None:
    """Код основной версии для неосновного ряда; None — ряд сам основной или правило выключено."""
    if not enabled():
        return None
    return published_map().get(slug, {}).get(code)



async def primary_has_year(db, country_id: int, code: str, year: int) -> bool:
    """У основной версии есть наблюдение в этом году (иначе годовой неосновной canonical не ставится)."""
    from datetime import date

    from sqlalchemy import select

    from app.models import WorldDataPoint, WorldIndicator

    found = (await db.execute(
        select(WorldDataPoint.id)
        .join(WorldIndicator, WorldIndicator.id == WorldDataPoint.indicator_id)
        .where(
            WorldIndicator.country_id == country_id,
            WorldIndicator.code == code,
            WorldIndicator.is_listed.is_(True),
            WorldDataPoint.date >= date(year, 1, 1),
            WorldDataPoint.date <= date(year, 12, 31),
        )
        .limit(1)
    )).first()
    return found is not None

"""Публичное название ряда страны мира с уточнением среза (14.11.2026).

Замер 14.11 (`scripts/world-title-duplicates.py`): 171 970 из 278 847 листинговых рядов на русском и
259 108 на английском делили название с другим рядом той же страны — «Автобусы и троллейбусы по
возрасту, штук» для пяти возрастов, «Валовая добавленная стоимость, % ВВП» для десяти отраслей.
Title и H1 таких страниц различались только числом, для поиска это почти копии.

Название = базовое имя ряда + короткое уточнение среза в скобках — только по тем измерениям, которыми
ряд отличается от других рядов той же страны с тем же именем (`differing_axes`); у ряда без «соседей»
по имени уточнения нет, название не раздувается. Подписи — без «итого» и без повторов имени. Подписи — официальные: английские из кодлистов Евростата
(`eurostat_dim_labels_en`, снимок `eurostat_codelists_en.json`), русские — словарь
`eurostat_dim_labels_ru` (перевод официального английского термина). Нет подписи — нет уточнения,
адрес страницы не меняется. Один источник для серверной страницы (`seo_world._display_name`) и
API карточки (`api/world._indicator_display_name`).
"""
from __future__ import annotations

import json
from contextvars import ContextVar
from typing import Any, Iterable

# (язык, страна, имя ряда в базе) → измерения, которыми различаются ряды с этим именем в стране. Заполняется
# обработчиком страницы или API на время запроса (`bind_title_axes` / `load_title_axes`); без карты —
# название без уточнения (как до 14.11.2026).
_TITLE_AXES: ContextVar[dict[tuple[str, int, str], frozenset[str]] | None] = ContextVar("fe_title_axes", default=None)

# Порядок слов в уточнении: сначала кто (пол, возраст, гражданство…), потом что (отрасль, продукт).
SLICE_AXES: tuple[str, ...] = (
    "sex", "age", "citizen", "c_birth", "wstatus", "isced11", "isced11f", "hhcomp", "rskpovth",
    "quant_inc", "deg_urb", "worktime", "duration", "mgstatus", "training", "marsta", "ord_brth",
    "nace_r2", "nace_r1", "coicop", "coicop18", "siec", "nrg_bal", "stk_flow", "partner", "sizeclas",
    "statinfo", "na_item", "indic_de", "indic_is", "indic_em", "indic_nrg", "indic", "month", "weight",
)


# Подписи, которые ничего не уточняют («Total» в кодлистах, где «итого» закодировано иначе).
_NOT_QUALIFIERS = frozenset({"total", "итого", "всего", "all", "все"})


def _slice(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}


def differing_axes(rows: Iterable[Any]) -> dict[tuple[str, int, str], frozenset[str]]:
    """Для групп рядов одной страны с одинаковым именем — измерения среза, значения которых в группе разные.

    Группы считаются отдельно по русскому (``name_ru``) и английскому (``name_en``) имени: английские
    имена Евростата часто общие на весь набор, русские — нет. Ключ — (язык, страна, имя в базе).
    ``rows`` — объекты с ``country_id``, ``name_ru``, ``name_en``, ``slice_json`` (листинговые ряды).
    """
    groups: dict[tuple[str, int, str], list[dict[str, Any]]] = {}
    for row in rows:
        slice_json = _slice(row.slice_json)
        groups.setdefault(("ru", row.country_id, row.name_ru or ""), []).append(slice_json)
        name_en = (getattr(row, "name_en", "") or "").strip()
        if name_en:
            groups.setdefault(("en", row.country_id, name_en), []).append(slice_json)
    out: dict[tuple[str, int, str], frozenset[str]] = {}
    for key, slices in groups.items():
        if len(slices) < 2:
            continue
        axes = frozenset(
            axis for axis in SLICE_AXES
            if len({str(item.get(axis)) for item in slices}) > 1
        )
        if axes:
            out[key] = axes
    return out


def bind_title_axes(mapping: dict[tuple[str, int, str], frozenset[str]]) -> None:
    """Добавить карту различающих измерений в контекст запроса (к уже загруженной)."""
    current = dict(_TITLE_AXES.get() or {})
    current.update(mapping)
    _TITLE_AXES.set(current)


async def load_title_axes(db, country_id: int) -> dict[tuple[str, int, str], frozenset[str]]:
    """Карта страны из кэша (на версию каталога) или из базы; кладётся в контекст запроса."""
    from sqlalchemy import select

    from app.core.cache import cache_get, cache_set, versioned_key
    from app.models import WorldIndicator

    key = None
    mapping: dict[tuple[str, int, str], frozenset[str]] | None = None
    try:
        key = await versioned_key("world", f"title-axes:v2:{country_id}")
        cached = await cache_get(key)
        if cached is not None:
            mapping = {(lang, country_id, name): frozenset(axes) for lang, name, axes in cached}
    except Exception:  # noqa: BLE001 - кэш не обязателен
        mapping = None
    if mapping is None:
        rows = (await db.execute(
            select(WorldIndicator.country_id, WorldIndicator.name_ru, WorldIndicator.name_en,
                   WorldIndicator.slice_json)
            .where(WorldIndicator.country_id == country_id, WorldIndicator.is_listed.is_(True))
        )).all()
        mapping = differing_axes(rows)
        if key is not None:
            try:
                await cache_set(key, [[lang, name, sorted(axes)] for (lang, _c, name), axes in mapping.items()],
                                ttl=6 * 3600)
            except Exception:  # noqa: BLE001
                pass
    bind_title_axes(mapping)
    return mapping


def slice_qualifiers(
    base: str, slice_json: dict[str, Any] | None, locale: str, axes: frozenset[str] | None = None,
) -> list[str]:
    """Подписи значений среза по измерениям ``axes`` на языке страницы, без «итого» и без повторов имени."""
    slice_json = _slice(slice_json)
    if not slice_json or not axes:
        return []
    from app.data.eurostat_dim_labels_ru import is_dim_totalish

    if locale == "en":
        from app.data.eurostat_dim_labels_en import label_for_dim_member
    else:
        from app.data.eurostat_dim_labels_ru import label_for_dim_member

    lowered = base.casefold()
    out: list[str] = []
    for axis in SLICE_AXES:
        if axis not in axes:
            continue
        raw = slice_json.get(axis)
        if raw is None:
            continue
        code = str(raw).strip()
        if not code or is_dim_totalish(axis, code):
            continue
        label = (label_for_dim_member(axis, code) or "").strip()
        if not label or label.casefold() in _NOT_QUALIFIERS or label.casefold() in lowered or label in out:
            continue
        out.append(label)
    return out


def with_slice(base: str, slice_json: dict[str, Any] | None, locale: str, axes: frozenset[str] | None) -> str:
    """«Автобусы и троллейбусы по возрасту, штук (младше 2 лет)»; без подписей — base как есть."""
    base = (base or "").strip()
    bits = slice_qualifiers(base, slice_json, locale, axes)
    return f"{base} ({', '.join(bits)})" if bits else base


def world_series_title(ind: Any, locale: str) -> str:
    """Название ряда страны мира для title, H1 и карточки API на языке страницы."""
    from app.data.world_indicator_titles_ru import public_indicator_name, title_override_en_for_code

    mapping = _TITLE_AXES.get() or {}
    country_id = getattr(ind, "country_id", None)

    if locale == "en" and (getattr(ind, "name_en", "") or "").strip():
        from app.data.eurostat_dim_labels_en import append_en_slice_to_title
        from app.data.legacy_redirects import strip_world_frequency_suffix

        override = title_override_en_for_code(ind.code)
        if override:
            return override
        base = strip_world_frequency_suffix(ind.name_en) or ind.name_en
        axes = mapping.get(("en", country_id, (ind.name_en or "").strip()))
        return with_slice(append_en_slice_to_title(base, ind.slice_json), ind.slice_json, "en", axes)
    base = public_indicator_name(ind.name_ru, ind.code) or ind.name_ru or ""
    axes = mapping.get(("ru", country_id, getattr(ind, "name_ru", "") or ""))
    return with_slice(base, ind.slice_json, "ru", axes)

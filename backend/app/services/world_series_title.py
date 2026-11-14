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
import re
from contextvars import ContextVar
from typing import Any, Iterable

# (язык, страна, имя ряда в базе) → измерения, которыми различаются ряды с этим именем в стране. Заполняется
# обработчиком страницы или API на время запроса (`bind_title_axes` / `load_title_axes`); без карты —
# название без уточнения (как до 14.11.2026).
_TITLE_AXES: ContextVar[dict[tuple[str, int, str], frozenset[str]] | None] = ContextVar("fe_title_axes", default=None)
# (язык, страна, имя) → минимум знаков уточнения в <title>, при котором названия группы ещё различаются.
_TITLE_BUDGETS: ContextVar[dict[tuple[str, int, str], int] | None] = ContextVar("fe_title_budgets", default=None)
# <title> не длиннее ~70 знаков (видимая часть в выдаче); уточнение режется по словам, но не до совпадения.
TITLE_TARGET = 70
# Уточнение короче этого не режется: «(младше…)» вместо «(младше 2 лет)» хуже длинного title.
QUALIFIER_MIN = 25

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


def _base_name(row: Any, lang: str) -> str:
    """Базовое публичное имя ряда (без уточнения) — ключ группы «одинаковых названий»."""
    from app.data.world_indicator_titles_ru import public_indicator_name, title_override_en_for_code

    if lang == "en":
        from app.data.eurostat_dim_labels_en import append_en_slice_to_title
        from app.data.legacy_redirects import strip_world_frequency_suffix

        override = title_override_en_for_code(getattr(row, "code", None))
        if override:
            return override
        name_en = (getattr(row, "name_en", "") or "").strip()
        return append_en_slice_to_title(strip_world_frequency_suffix(name_en) or name_en, _slice(row.slice_json)).strip()
    return (public_indicator_name(row.name_ru, getattr(row, "code", None)) or row.name_ru or "").strip()


def _lang_of(row: Any, locale: str) -> str:
    """Язык имени ряда: английский — только если у ряда есть name_en (иначе страница показывает русское)."""
    return "en" if locale == "en" and (getattr(row, "name_en", "") or "").strip() else "ru"


def differing_axes(rows: Iterable[Any]) -> dict[tuple[str, int, str], frozenset[str]]:
    """Для групп рядов одной страны с одинаковым базовым именем — измерения среза, значения которых в группе разные.

    Группы считаются отдельно по русскому и английскому публичному имени (без частотного хвоста):
    английские имена Евростата часто общие на весь набор, русские — нет. Ключ — (язык, страна, имя).
    ``rows`` — объекты с ``country_id``, ``code``, ``name_ru``, ``name_en``, ``slice_json``.
    """
    groups: dict[tuple[str, int, str], list[dict[str, Any]]] = {}
    for row in rows:
        slice_json = _slice(row.slice_json)
        groups.setdefault(("ru", row.country_id, _base_name(row, "ru")), []).append(slice_json)
        if (getattr(row, "name_en", "") or "").strip():
            groups.setdefault(("en", row.country_id, _base_name(row, "en")), []).append(slice_json)
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


def bind_title_axes(
    mapping: dict[tuple[str, int, str], frozenset[str]],
    budgets: dict[tuple[str, int, str], int] | None = None,
) -> None:
    """Добавить карту различающих измерений (и минимумы уточнения для <title>) в контекст запроса."""
    current = dict(_TITLE_AXES.get() or {})
    current.update(mapping)
    _TITLE_AXES.set(current)
    if budgets:
        merged = dict(_TITLE_BUDGETS.get() or {})
        merged.update(budgets)
        _TITLE_BUDGETS.set(merged)


def bind_rows(rows: Iterable[Any]) -> None:
    """Карта и минимумы из уже прочитанных листинговых рядов (каталог страны)."""
    rows = list(rows)
    mapping = differing_axes(rows)
    bind_title_axes(mapping, title_budgets(rows, mapping))


async def load_title_axes(db, country_id: int) -> dict[tuple[str, int, str], frozenset[str]]:
    """Карта страны из кэша (на версию каталога) или из базы; кладётся в контекст запроса."""
    from sqlalchemy import select

    from app.core.cache import cache_get, cache_set, versioned_key
    from app.models import WorldIndicator

    key = None
    mapping: dict[tuple[str, int, str], frozenset[str]] | None = None
    budgets: dict[tuple[str, int, str], int] = {}
    try:
        key = await versioned_key("world", f"title-axes:v4:{country_id}")
        cached = await cache_get(key)
        if cached is not None:
            mapping = {(lang, country_id, name): frozenset(axes) for lang, name, axes, _b in cached}
            budgets = {(lang, country_id, name): int(b) for lang, name, _axes, b in cached if b}
    except Exception:  # noqa: BLE001 - кэш не обязателен
        mapping = None
    if mapping is None:
        rows = (await db.execute(
            select(WorldIndicator.country_id, WorldIndicator.code, WorldIndicator.name_ru,
                   WorldIndicator.name_en, WorldIndicator.slice_json)
            .where(WorldIndicator.country_id == country_id, WorldIndicator.is_listed.is_(True))
        )).all()
        mapping = differing_axes(rows)
        budgets = title_budgets(rows, mapping)
        if key is not None:
            try:
                await cache_set(key, [[lang, name, sorted(axes), budgets.get((lang, c, name), 0)]
                                      for (lang, c, name), axes in mapping.items()], ttl=6 * 3600)
            except Exception:  # noqa: BLE001
                pass
    bind_title_axes(mapping, budgets)
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


def _base_and_bits(ind: Any, locale: str, mapping) -> tuple[str, list[str]]:
    """Базовое имя ряда и подписи уточнения (полные, официальные) на языке страницы."""
    from app.data.world_indicator_titles_ru import title_override_en_for_code

    lang = _lang_of(ind, locale)
    if lang == "en" and title_override_en_for_code(ind.code):
        return title_override_en_for_code(ind.code), []
    base = _base_name(ind, lang)
    axes = mapping.get((lang, getattr(ind, "country_id", None), base))
    return base, slice_qualifiers(base, ind.slice_json, lang, axes)


def world_series_title(ind: Any, locale: str) -> str:
    """Название ряда страны мира для H1, текста и карточки API: полная официальная подпись среза."""
    base, bits = _base_and_bits(ind, locale, _TITLE_AXES.get() or {})
    return f"{base} ({', '.join(bits)})" if bits else base


_WORD = re.compile(r"[\w%]+", re.UNICODE)


def title_qualifier(base: str, bits: list[str]) -> str:
    """Уточнение для <title>: без слов, которые уже есть в базовом имени («value added, gross» при
    «Gross value added …» уходит целиком)."""
    words = {w.casefold() for w in _WORD.findall(base)}
    kept: list[str] = []
    for bit in bits:
        own = [w for w in _WORD.findall(bit) if w.casefold() not in words]
        if not own:
            continue
        kept.append(bit)
    return ", ".join(kept)


def cut_words(text: str, limit: int) -> str:
    """Обрезка по целым словам с «…»; короче лимита — без изменений."""
    if limit <= 0 or len(text) <= limit:
        return text
    out = ""
    for word in text.split(" "):
        candidate = f"{out} {word}".strip()
        if len(candidate) + 1 > limit:
            break
        out = candidate
    if not out:
        # Ни одно слово целиком не помещается: слово не рвём — первое слово целиком.
        first = text.split(" ")[0]
        return text if first == text else first.rstrip(" ,;:—-") + "…"
    return out.rstrip(" ,;:—-") + "…"


def _cut_points(text: str) -> list[int]:
    """Длины, при которых cut_words даёт разные результаты (концы слов) + полная длина."""
    points, pos = [], 0
    for word in text.split(" "):
        pos += len(word) + (1 if pos else 0)
        points.append(pos + 1)  # +1 под «…»
    return sorted(set(points + [len(text)]))


def title_budgets(rows: Iterable[Any], mapping) -> dict[tuple[str, int, str], int]:
    """Для групп с уточнением — минимум знаков уточнения в <title>, при котором названия группы различны.

    Знак числа — режим: положительное — уточнение без слов базового имени (`title_qualifier`);
    отрицательное — в группе это склеило бы названия, уточнение берётся полностью.
    """
    groups: dict[tuple[str, int, str], list[tuple[str, str]]] = {}
    for row in rows:
        for locale in ("ru", "en"):
            if _lang_of(row, locale) != locale:
                continue
            base, bits = _base_and_bits(row, locale, mapping)
            key = (locale, row.country_id, base)
            if key not in mapping:
                continue
            groups.setdefault(key, []).append((title_qualifier(base, bits), ", ".join(bits)))
    out: dict[tuple[str, int, str], int] = {}
    for key, pairs in groups.items():
        full_distinct = len({full for _short, full in pairs})
        dedupe = len({short for short, _full in pairs}) == full_distinct
        quals = [short if dedupe else full for short, full in pairs]
        points = sorted({p for q in quals if q for p in _cut_points(q) if p >= 2})
        limit = max((len(q) for q in quals), default=0)
        # Наименьший предел, начиная с которого названия различны при любом большем пределе
        # (обрезка по словам не монотонна: «n.e.c.,» и «n.e.c. -» совпадают после снятия запятой).
        for candidate in reversed(points):
            if len({cut_words(q, candidate) for q in quals}) != full_distinct:
                break
            limit = candidate
        out[key] = max(limit, 1) if dedupe else -max(limit, 1)
    return out


def world_series_title_for_tag(ind: Any, locale: str, room: int) -> str:
    """Название ряда для <title>: уточнение без слов базового имени, при нехватке места — по словам с «…».

    ``room`` — сколько знаков названия помещается в <title> при цели ~70. Уточнение не режется короче
    минимума группы (`title_budgets`): название в <title> остаётся уникальным внутри страны.
    """
    mapping = _TITLE_AXES.get() or {}
    base, bits = _base_and_bits(ind, locale, mapping)
    if not bits:
        return base
    budget = (_TITLE_BUDGETS.get() or {}).get((_lang_of(ind, locale), getattr(ind, "country_id", None), base))
    if budget is None:
        # Нет минимума группы — уточнение целиком (уникальность важнее длины).
        return f"{base} ({', '.join(bits)})"
    qualifier = title_qualifier(base, bits) if budget > 0 else ", ".join(bits)
    if not qualifier:
        return base
    limit = max(room - len(base) - 3, abs(budget), QUALIFIER_MIN)
    return f"{base} ({cut_words(qualifier, limit)})"

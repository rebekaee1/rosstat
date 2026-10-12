"""Круг 12, BACK2 (U14, U15): дубли и одинаковые названия в выдаче поиска.

Две задачи над уже отсортированной выдачей:

1. `collapse_equivalent` — ряды одного экономического понятия реестра (`WORLD_CONCEPTS`) одной
   страны, частоты и единицы — это один показатель, поданный двумя наборами Евростата
   (например `prc_hicp_midx` и `prc_hicp_minr`). Остаётся первый по порядку выдачи (главный),
   остальные уходят в его поле `variants`; ничего не теряется, но в списке нет трёх одинаковых строк.
2. `disambiguate_titles` — разные ряды одной страны с одинаковым названием («Население, %» для
   разных возрастов, «Гармонизированный индекс ...» для месячного и годового) получают в
   скобках существенный признак: период, единицу или срез (возраст, пол). Название в базе не
   меняется, меняется только поле `name` ответа.

Обе функции чистые: работают над словарями выдачи и строками, которые поиск уже загрузил.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

from app.data.eurostat_dim_labels_en import label_for_dim_member as _label_en
from app.data.eurostat_dim_labels_ru import label_for_dim_member as _label_ru
from app.data.world_concepts import concept_for_indicator

_FREQUENCY_RU = {
    "annual": "годовой ряд", "yearly": "годовой ряд", "a": "годовой ряд",
    "quarterly": "квартальный ряд", "q": "квартальный ряд",
    "monthly": "месячный ряд", "m": "месячный ряд",
    "weekly": "недельный ряд", "daily": "дневной ряд",
}
_FREQUENCY_EN = {
    "annual": "annual", "yearly": "annual", "a": "annual", "quarterly": "quarterly", "q": "quarterly",
    "monthly": "monthly", "m": "monthly", "weekly": "weekly", "daily": "daily",
}
# Оси среза, которые меняют смысл ряда для человека; технические (единица, сезонность) подписываются
# отдельно или не показываются. Порядок задаёт порядок слов в скобках.
_SLICE_AXES = ("sex", "age", "citizen", "hhcomp", "quant_inc", "isced11", "wstatus", "nace_r2", "duration", "c_birth")


def _frequency_label(frequency: str | None, locale: str) -> str:
    key = str(frequency or "").strip().lower()
    table = _FREQUENCY_EN if locale == "en" else _FREQUENCY_RU
    return table.get(key, "")


def _slice_label(axis: str, member: Any, locale: str) -> str:
    if not isinstance(member, str) or not member.strip():
        return ""
    label = (_label_en if locale == "en" else _label_ru)(axis, member)
    return str(label or "").strip()


def collapse_equivalent(results: list[dict], world_rows: Mapping[tuple[str, str], Any]) -> list[dict]:
    """Схлопывает строки одного понятия/страны/частоты/единицы; остальные идут в `variants` первой."""
    primary_by_group: dict[tuple, dict] = {}
    out: list[dict] = []
    for item in results:
        group = _equivalence_key(item, world_rows)
        if group is None:
            out.append(item)
            continue
        primary = primary_by_group.get(group)
        if primary is None:
            primary_by_group[group] = item
            out.append(item)
            continue
        primary.setdefault("variants", []).append(
            {"key": item["key"], "code": item.get("code"), "path": item.get("path"), "navigation": item.get("navigation")})
    return out


def _equivalence_key(item: dict, world_rows: Mapping[tuple[str, str], Any]) -> tuple | None:
    if item.get("kind") != "world" or float(item.get("score") or 0) >= 900:
        return None  # точное совпадение кода или названия не прячем
    row = world_rows.get((item.get("country_slug"), item.get("code")))
    if row is None:
        return None
    try:
        concept = concept_for_indicator(row)
    except ValueError:
        return None
    if concept is None:
        return None
    return (item.get("country_slug"), concept.slug, str(item.get("frequency") or ""), str(item.get("unit") or ""))


def disambiguate_titles(results: Iterable[dict], world_rows: Mapping[tuple[str, str], Any], locale: str) -> None:
    """Добавляет в `name` признак, различающий ряды страны с одинаковым названием."""
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for item in results:
        if item.get("kind") == "world" and item.get("name"):
            groups[(str(item.get("country_slug")), str(item["name"]))].append(item)
    for members in groups.values():
        if len(members) < 2:
            continue
        parts = _distinguishing_parts(members, world_rows, locale)
        for item, labels in zip(members, parts):
            if labels:
                item["name"] = f"{item['name']} ({', '.join(labels)})"


def _distinguishing_parts(members: list[dict], world_rows: Mapping[tuple[str, str], Any], locale: str) -> list[list[str]]:
    """Для каждого ряда — слова только по тем признакам, которые различаются внутри группы."""
    columns: list[list[str]] = []
    frequencies = [_frequency_label(item.get("frequency"), locale) for item in members]
    if len(set(frequencies)) > 1:
        columns.append(frequencies)
    units = [str(item.get("unit") or "").strip() for item in members]
    if len(set(units)) > 1:
        columns.append(units)
    rows = [world_rows.get((item.get("country_slug"), item.get("code"))) for item in members]
    slices = [dict(getattr(row, "slice_json", None) or {}) if row is not None else {} for row in rows]
    for axis in _SLICE_AXES:
        values = [_slice_label(axis, one.get(axis), locale) for one in slices]
        if len(set(values)) > 1:
            columns.append(values)
    return [list(dict.fromkeys(column[index] for column in columns if column[index]))
        for index in range(len(members))]

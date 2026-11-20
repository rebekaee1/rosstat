"""Поиск из раздела «Туризм» и точное слово в названии (круг правок 20.11.2026, зона z6, правка 17).

1. Точное слово запроса в названии ряда («ночёвки» в «Ночёвки в санаториях») идёт выше похожих по написанию слов
   и синонимов («Ставка овернайт»): небольшая добавка к счёту, порядок только внутри уже подходящих строк.
2. Запрос из раздела «Туризм» (`section=tourism`), в котором названа только страна или регион («Турция»,
   «Краснодарский край»), ставит сразу после строки места туристские ряды этого места. Без `section` поведение прежнее.
"""
from __future__ import annotations

import re

from app.services.search_intent import normalize

SECTION_TOURISM = "tourism"
# Сколько туристских рядов места поднимается под строку самого места.
SECTION_LEAD_ROWS = 8
# Добавка за каждое точное слово запроса; потолок — чтобы длинный запрос не перевесил смысловой счёт.
EXACT_WORD_BONUS = 6
EXACT_WORD_CAP = 12
_MIN_WORD = 4
_WORD = re.compile(r"[a-zа-я0-9]+")

_PLACE_KINDS = frozenset(("country", "region", "subnational_region"))
_TOURISM_CATEGORIES = frozenset(("туризм", "tourism"))


def known_section(value: str | None) -> str | None:
    """Только известный раздел действует; всё остальное — как будто параметра нет."""
    # Прямой вызов обработчика без параметра приносит объект Query, а не строку.
    text = value.strip().lower() if isinstance(value, str) else ""
    return text if text == SECTION_TOURISM else None


def query_words(raw: str) -> tuple[str, ...]:
    """Слова запроса не короче четырёх букв: короткие («в», «по», «ВВП») совпадают слишком случайно."""
    return tuple(dict.fromkeys(word for word in _WORD.findall(normalize(raw)) if len(word) >= _MIN_WORD))


def exact_word_bonus(words: tuple[str, ...], names: tuple[str, ...]) -> int:
    """Добавка к счёту: слово запроса стоит в названии ряда целым словом, а не частью другого слова."""
    if not words:
        return 0
    title = set(_WORD.findall(normalize(" ".join(name or "" for name in names))))
    return min(sum(EXACT_WORD_BONUS for word in words if word in title), EXACT_WORD_CAP)


def is_tourism_row(item: dict) -> bool:
    """Строка выдачи из раздела «Туризм»: код `tour-…`, раздел «Туризм» или туристское название регионального ряда."""
    if item.get("kind") in _PLACE_KINDS:
        return False
    code = str(item.get("code") or "").lower()
    if code.startswith("tour") or "-tour-" in code:
        return True
    if str(item.get("category") or "").strip().lower() in _TOURISM_CATEGORIES:
        return True
    if item.get("kind") in ("region_indicator", "subnational_indicator"):
        from app.services.tourism_showcase import is_tourism_region_indicator

        return is_tourism_region_indicator(code, item.get("category"), item.get("name_ru") or item.get("name"))
    return False


def wants_tourism_lead(intent, section: str | None) -> bool:
    """Раздел «Туризм», названа страна или регион и нет других слов; Россия целиком уже ведёт `tourism_first`."""
    if section != SECTION_TOURISM or intent.terms:
        return False
    return bool(intent.regions) or bool(intent.countries - {"russia"})


def with_tourism_lead(rows: list[dict], tourism_rows: list[dict]) -> list[dict]:
    """Строки места, затем туристские ряды этого места (до SECTION_LEAD_ROWS), затем прежний порядок."""
    lead = []
    seen = set()
    for row in tourism_rows:
        if is_tourism_row(row) and row["key"] not in seen:
            lead.append(row)
            seen.add(row["key"])
        if len(lead) >= SECTION_LEAD_ROWS:
            break
    if not lead:
        return rows
    places = [row for row in rows if row["kind"] in _PLACE_KINDS]
    rest = [row for row in rows if row["kind"] not in _PLACE_KINDS and row["key"] not in seen]
    return places + lead + rest

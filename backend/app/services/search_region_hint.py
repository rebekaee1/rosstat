"""Регион в запросе по началу слова или названию города: «яйца нов», «хлеб новосибирск», «молоко тверь».

Обычные формы названий регионов (падежи, «край», «область») разбирает ``strip_geography``. Здесь —
только остаток: слово запроса, которое ничем не стало (не понятие, не страна, не регион), но является
началом слова из названия субъекта РФ. Короткое начало (3–4 буквы) принимается, лишь когда в запросе
есть товар из средних цен: так «рост ввп» не превращается в Ростовскую область.
"""

from __future__ import annotations

import re

_NAME_STOP = frozenset(("республика", "область", "край", "автономный", "автономная", "округ", "город", "федерального",
    "значения", "без", "учета", "учёта", "ао", "г", "обл", "респ"))
_MAX_REGIONS = 6
_WORD = re.compile(r"[a-zа-я0-9]+")


def _words(name: str) -> tuple[str, ...]:
    return tuple(word for word in _WORD.findall((name or "").casefold().replace("ё", "е")) if word not in _NAME_STOP and len(word) >= 3)


def _stems(token: str) -> tuple[str, ...]:
    """«тверь» → «твер», «пермь» → «перм»: город называют не так, как область."""
    stems = [token]
    if len(token) >= 5 and token[-1] in "ьйая":
        stems.append(token[:-1])
    return tuple(stems)


def region_prefix_keys(token: str, geometry: list[dict], *, goods: bool, minimum: int | None = None,
                       whole_word: bool = False) -> frozenset[str]:
    """Ключи субъектов РФ, в названии которых есть слово, начинающееся с ``token``; пусто, если неоднозначно.

    ``whole_word`` (второе чтение после пустой выдачи, 19.11.2026): целое слово названия важнее начала — «саха» —
    слово «Республики Саха (Якутия)», хотя с него же начинается «Сахалинская»; принимается от четырёх букв.
    ``minimum`` — наименьшая длина начала (второе чтение передаёт 3: «степень износа пен» → Пензенская область).
    Первое чтение вызывает без них и отвечает как раньше.
    """
    if minimum is None:
        minimum = 3 if goods else 5
    if not token or not _WORD.fullmatch(token):
        return frozenset()
    exact, keys = set(), set()
    stems = _stems(token)
    for item in geometry:
        if item.get("kind") != "region":
            continue
        words = _words(item.get("name_ru", "")) + _words(item.get("name_en", ""))
        if whole_word and len(token) >= 4 and token in words:
            exact.add(item["key"])
        if len(token) >= minimum and any(word.startswith(stem) for word in words for stem in stems):
            keys.add(item["key"])
    if exact:
        keys = exact
    return frozenset(keys) if 0 < len(keys) <= _MAX_REGIONS else frozenset()

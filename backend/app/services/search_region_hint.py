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


def region_prefix_keys(token: str, geometry: list[dict], *, goods: bool) -> frozenset[str]:
    """Ключи субъектов РФ, в названии которых есть слово, начинающееся с ``token``; пусто, если неоднозначно."""
    minimum = 3 if goods else 5
    if not token or len(token) < minimum or not _WORD.fullmatch(token):
        return frozenset()
    stems = _stems(token)
    keys = set()
    for item in geometry:
        if item.get("kind") != "region":
            continue
        words = _words(item.get("name_ru", "")) + _words(item.get("name_en", ""))
        if any(word.startswith(stem) for word in words for stem in stems):
            keys.add(item["key"])
    return frozenset(keys) if 0 < len(keys) <= _MAX_REGIONS else frozenset()

"""Смысл среза Eurostat ↔ имя карточки.

Слой 1: имя выводится из фактически закреплённого содержательного среза
(``na_item`` / ``indic*`` / …), а не только из заголовка набора.

Слой 2: если понятие в срезе противоречит понятию в имени — ряд нельзя
листить (дефект данных, не повод угадать).
"""

from __future__ import annotations

import re
from typing import Any

# Содержательные измерения SDMX, которые фиксируют «о чём ряд».
SUBSTANCE_DIMS: tuple[str, ...] = (
    "na_item",
    "indic_ppp",
    "indic_de",
    "indic",
    "indic_n",
    "indic_sb",
    "indic_bt",
)

# na_item → краткое русское подлежащее карточки.
NA_ITEM_SUBJECT_RU: dict[str, str] = {
    "B1GQ": "Валовой внутренний продукт",
    "B1G": "Валовая добавленная стоимость",
    "B9": "Дефицит или профицит бюджета",
    "B9_T3": "Дефицит или профицит бюджета",
    "B9F": "Дефицит или профицит бюджета",
    "NLG_B9": "Дефицит или профицит бюджета",
    "NET_LEND": "Дефицит или профицит бюджета",
    "P3": "Расходы на конечное потребление",
    "P31_S13": "Конечное потребление государственного управления",
    "P51G": "Валовое накопление основного капитала",
    "P52_P53": "Изменение запасов",
    "B11": "Внешнеторговое сальдо",
    "D41": "Проценты",
    "D41PAY": "Выплата процентов",
    "TE": "Расходы государственного управления",
    "TR": "Доходы государственного управления",
    "GD": "Государственный долг",
}

# indic* → подлежащее (когда код однозначно задаёт показатель).
INDIC_SUBJECT_RU: dict[str, str] = {
    "MF-DDI-RT": "Процентные ставки",
    "MF-LTGBY-RT": "Доходность долгосрочных гособлигаций",
    "MF-NBRATE-RT": "Ставка рефинансирования",
    "EXP_PPS_EU27_2020_HAB": "ВВП на душу населения по паритету покупательной способности",
    "EXP_PPS_HAB": "ВВП на душу населения по паритету покупательной способности",
}

# Имя заявляет понятие → допустимые коды измерения.
# Если измерение закреплено и код вне множества — unlist.
_NAME_CONCEPT_RULES: list[tuple[re.Pattern[str], str, frozenset[str]]] = [
    (
        re.compile(r"дефицит|профицит|чист(?:ое|ого)\s+кредитован", re.I),
        "na_item",
        frozenset({"B9", "B9_T3", "B9F", "NLG_B9", "NET_LEND"}),
    ),
    (
        re.compile(r"государственн\w*\s+долг|долг\s+сектора\s+государ", re.I),
        "na_item",
        frozenset({"GD", "F2", "F3", "F4", "GD_NACE"}),
    ),
]

# Срез закрепляет понятие → имя не должно заявлять чужое.
# «% ВВП» в единице — не заявление, что ряд сам есть ВВП.
_SLICE_CONCEPT_FORBIDDEN_NAME: list[tuple[str, frozenset[str], re.Pattern[str]]] = [
    (
        "na_item",
        frozenset({"B1GQ", "B1G"}),
        re.compile(r"дефицит|профицит|чист(?:ое|ого)\s+кредитован", re.I),
    ),
    (
        "na_item",
        frozenset({"B9", "B9_T3", "B9F", "NLG_B9", "NET_LEND"}),
        # подлежащее «ВВП…», но не хвост единицы «% ВВП»
        re.compile(
            r"(?:^|,\s*)(?:валовой внутренний продукт|(?<![%\w])ввп(?!\w))",
            re.I,
        ),
    ),
]


def substance_code(slice_json: dict[str, Any] | None) -> tuple[str, str] | None:
    """Вернуть (dim, CODE) первого содержательного пина или None."""
    sl = slice_json or {}
    for dim in SUBSTANCE_DIMS:
        raw = sl.get(dim)
        if raw is None:
            continue
        code = str(raw).strip().upper()
        if code and code not in {"TOTAL", "T", "ALL", "NSP"}:
            return dim, code
    return None


def substance_subject_ru(slice_json: dict[str, Any] | None) -> str | None:
    """Русское подлежащее из закреплённого среза, если код известен."""
    hit = substance_code(slice_json)
    if not hit:
        return None
    dim, code = hit
    if dim == "na_item":
        return NA_ITEM_SUBJECT_RU.get(code)
    return INDIC_SUBJECT_RU.get(code)


def apply_substance_to_subject(base_subject: str, slice_json: dict[str, Any] | None) -> str:
    """Слой 1: если срез известен — подлежащее обязано называть его.

    Кураторский заголовок набора сохраняется только когда он уже согласован
    со срезом; иначе заменяется именем из среза.
    """
    substance = substance_subject_ru(slice_json)
    subject = (base_subject or "").strip()
    if not substance:
        return subject
    if slice_concept_matches_name(subject, slice_json):
        # Кураторский заголовок согласован — оставляем (часто короче/лучше).
        return subject or substance
    return substance


def slice_concept_matches_name(
    name_ru: str | None,
    slice_json: dict[str, Any] | None,
) -> bool:
    """Слой 2: True, если имя и содержательный срез не противоречат друг другу."""
    name = name_ru or ""
    sl = slice_json or {}

    for pat, dim, allowed in _NAME_CONCEPT_RULES:
        if not pat.search(name):
            continue
        code = str(sl.get(dim) or "").strip().upper()
        if not code:
            # Имя заявляет понятие, а срез его не фиксирует — нельзя проверить.
            # Не unlist только из-за отсутствия пина: другие фильтры поймают.
            continue
        if code not in allowed:
            return False

    for dim, codes, forbidden_pat in _SLICE_CONCEPT_FORBIDDEN_NAME:
        code = str(sl.get(dim) or "").strip().upper()
        if code not in codes:
            continue
        if forbidden_pat.search(name):
            return False

    return True

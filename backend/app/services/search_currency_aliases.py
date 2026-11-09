"""Латиница и английские названия для курсов валют Банка России («uzbek», «dirham», «dram»).

Справочник ``app.data.cbr_currencies`` даёт русские псевдонимы и «uzs rub». Человек без русской
раскладки пишет «uzbek som», «dirham», «tenge», «hryvnia». Здесь псевдонимы выводятся из английского
названия валюты и ведут к тому же ряду, что и русские фразы.
"""

from __future__ import annotations

import re

from app.data.cbr_currencies import CBR_CURRENCIES

# Слова, которые у многих валют общие и однозначного ряда не задают.
_SHARED_LAST_WORDS = frozenset(("ruble", "dollar", "pound", "som", "manat", "leu", "dinar", "krone", "krona", "rial", "riyal",
    "peso", "rupee", "franc", "rights", "real"))
# Прилагательное страны → короткий корень («uzbekistani» → «uzbek»).
_ROOT_SUFFIXES = ("istani", "stani", "ian", "ish")
# Первое слово, которое не задаёт страну.
_GENERIC_FIRST = frozenset(("south", "new", "hong", "pound", "special", "uae", "japanese", "swiss"))


def _stem(currency) -> str:
    return currency.nom.split()[0].casefold()[:5]


def _roots(adjective: str) -> list[str]:
    for suffix in _ROOT_SUFFIXES:
        if adjective.endswith(suffix) and len(adjective) - len(suffix) >= 4:
            return [adjective, adjective[: -len(suffix)]]
    return [adjective]


def currency_latin_concepts() -> tuple[tuple[tuple[str, ...], tuple[str, ...]], ...]:
    words = [re.findall(r"[a-z]+", currency.en.casefold()) for currency in CBR_CURRENCIES]
    last_counts: dict[str, int] = {}
    for parts in words:
        if parts:
            last_counts[parts[-1]] = last_counts.get(parts[-1], 0) + 1
    out = []
    for currency, parts in zip(CBR_CURRENCIES, words):
        if len(parts) < 2 or currency.iso == "XDR":
            continue
        first, last = parts[0], parts[-1]
        aliases: list[str] = [currency.en.casefold(), f"курс {currency.en.casefold()}"]
        for root in ([] if first in _GENERIC_FIRST else _roots(first)):
            aliases.extend((root, f"{root} {last}", f"{root} {last} to rub", f"{root} rate"))
        if last not in _SHARED_LAST_WORDS and last_counts[last] == 1:
            aliases.extend((last, f"{last} rate", f"{last} to ruble", f"{last} rub"))
        if currency.iso == "GBP":
            aliases.extend(("pound", "sterling", "gbp"))
        if currency.iso == "AED":
            aliases.extend(("uae dirham", "emirates dirham"))
        unique = tuple(dict.fromkeys(alias for alias in aliases if alias))
        out.append((unique, (currency.code, f"{currency.iso.casefold()} rub", _stem(currency))))
    return tuple(out)

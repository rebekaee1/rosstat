"""Выверенные русские названия мировых рядов (национальные + чистка витрины).

Eurostat-заголовки собирает ``eurostat_titles_ru`` / curated JSON. Национальные
адаптеры иногда оставляют аббревиатуры ведомств (SHIBOR, IPCA, TIIE). Этот
модуль — единая точка правки публичного имени на витрине: код → имя, затем
замена латинского жаргона классификаторов. Ряд с латиницей после очистки
не должен попадать в видимый каталог страны.
"""

from __future__ import annotations

import re

from app.data.eurostat_titles_ru import has_latin, split_freq_suffix

# Точечные переопределения по коду ряда (национальные провайдеры).
TITLE_BY_CODE: dict[str, str] = {
    "br-cpi-ipca": "Индекс потребительских цен к предыдущему месяцу",
    "br-cpi-ipca-yoy": "Инфляция за 12 месяцев",
    "br-gdp-ibc-br": "Индекс экономической активности",
    "cn-shibor-1w": "Межбанковская ставка на одну неделю",
    "cn-shibor-on": "Межбанковская ставка овернайт",
    "cn-lpr-1y": "Базовая кредитная ставка на 1 год",
    "cn-lpr-5y": "Базовая кредитная ставка на 5 лет и более",
    "mx-tiie-28": "Межбанковская ставка на 28 дней",
    "mx-fx-usd-mxn": "Курс доллара США к мексиканскому песо",
    "ca-m2-plus": "Расширенный денежный агрегат",
    "jp-m2": "Денежный агрегат М2",
    "jp-m3": "Денежный агрегат М3",
}

# Латинский жаргон классификаторов → русская формулировка или удаление.
_LATIN_CLEANUPS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\be[\u2011\u2010\-]?commerce\b", re.I), "электронной торговли"),
    (re.compile(r"\bSTEM\b"), "естественно-научных и технических специальностей"),
    (re.compile(r"\bNEET\b"), "не занятой работой и учёбой"),
    (re.compile(r"\bNUTS\s*3\b", re.I), "уровень муниципалитетов"),
    (re.compile(r"\bNUTS\s*2\b", re.I), "уровень регионов"),
    (re.compile(r"\bNUTS\b", re.I), "регионы"),
    (re.compile(r"\s*\(\s*COICOP[^)]*\)", re.I), ""),
    (re.compile(r"\bCOICOP\b", re.I), ""),
    (re.compile(r"\s*\(\s*G[\u2013\-–]N,?\s*STS\s*\)", re.I), " в рыночных услугах"),
    (re.compile(r"\bSTS\b"), ""),
    (re.compile(r"\bSHIBOR\b", re.I), "межбанковская"),
    (re.compile(r"\bIPCA\b"), ""),
    (re.compile(r"\bIBC[\u2010\-]?Br\b", re.I), ""),
    (re.compile(r"\bTIIE\b"), ""),
    (re.compile(r"\bLPR\b"), ""),
    (re.compile(r"\bFIX\b"), ""),
    (re.compile(r"\bM2\+\b"), "расширенный денежный агрегат"),
    (re.compile(r"\bM2\b"), "М2"),
    (re.compile(r"\bM3\b"), "М3"),
]


def _apply_latin_cleanups(name: str) -> str:
    out = name
    for pat, repl in _LATIN_CLEANUPS:
        out = pat.sub(repl, out)
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+,", ",", out)
    out = re.sub(r",\s*,+", ",", out)
    return out.strip(" ,;—–-")


def public_indicator_name(name_ru: str | None, code: str | None = None) -> str:
    """Публичное имя карточки: override → чистка → без частотного хвоста."""
    code_key = (code or "").strip().lower()
    if code_key and code_key in TITLE_BY_CODE:
        base = TITLE_BY_CODE[code_key]
    else:
        base = name_ru or ""
    cleaned = _apply_latin_cleanups(base)
    subject, _ = split_freq_suffix(cleaned)
    return subject or cleaned or (name_ru or "")


def is_public_catalog_name(name: str | None) -> bool:
    """Имя пригодно для видимого каталога: есть кириллица, нет латиницы."""
    text = (name or "").strip()
    if not text:
        return False
    if has_latin(text):
        return False
    return bool(re.search(r"[А-Яа-яЁё]", text))

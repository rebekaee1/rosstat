"""Выверенные русские названия мировых рядов (национальные + чистка витрины).

Eurostat-заголовки собирает ``eurostat_titles_ru`` / curated JSON. Национальные
адаптеры иногда оставляют аббревиатуры ведомств (SHIBOR, IPCA, TIIE). Этот
модуль — единая точка правки публичного имени на витрине: код → имя, затем
замена латинского жаргона классификаторов. Ряд с латиницей после очистки
не должен попадать в видимый каталог страны.
"""

from __future__ import annotations

import re
from functools import lru_cache

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

# Переопределения по фрагменту кода (один и тот же ряд у разных стран): код страны стоит
# в начале, поэтому ищем «-фрагмент» внутри кода. Для названий, которые у разных рядов
# одного набора слипаются в одно слово (две карточки «Процентные ставки, %» у Турции) или
# называют не то, что показывают (годовая оценка МВФ подписана как изменение за год).
# Смысл рядов сверен по значениям: MF-DDI-RT совпадает со ставкой на один день набора
# irt_st_m (irt-dtd) в каждой точке; MF-3MI-RT — трёхмесячная ставка денежного рынка.
TITLE_BY_CODE_FRAGMENT: tuple[tuple[str, str], ...] = (
    ("-ei_mfir_m-mf-ddi-rt-", "Ставка денежного рынка на один день, %"),
    ("-ei_mfir_m-mf-3mi-rt-", "Ставка денежного рынка на три месяца, %"),
    ("-weo-pcpipch", "Инфляция в среднем за год, оценка МВФ"),
    # U15: веса и первые публикации HICP носили то же название, что сам индекс («Гармонизированный
    # индекс потребительских цен» ×9 у одной страны). Смысл — по набору Евростата: веса стран
    # (cw, cow), веса товаров и услуг (iw, inw), первые публикации индекса (fpd).
    ("-prc_hicp_cw-", "Веса стран в гармонизированном индексе потребительских цен"),
    ("-prc_hicp_cow-", "Веса стран в гармонизированном индексе потребительских цен"),
    ("-prc_hicp_iw-", "Веса товаров и услуг в гармонизированном индексе потребительских цен"),
    ("-prc_hicp_inw-", "Веса товаров и услуг в гармонизированном индексе потребительских цен"),
    ("-prc_hicp_fpd-", "Гармонизированный индекс потребительских цен, первые публикации"),
    # Круг 13: ИПЦ при постоянных налоговых ставках (ct) носил то же имя, что основной индекс
    # (minr): две одинаковые плитки у страны. Различает смысл, адрес не меняется.
    ("-prc_hicp_ct-", "Гармонизированный индекс потребительских цен при постоянных налоговых ставках"),
    # Среднегодовой ГИПЦ: у прежнего набора (aind) база 2015=100, у нового (ainr, ECOICOP ver.2)
    # 2025=100 — по данным 34 и 36 стран. Название у обоих было одно и то же.
    ("-prc_hicp_aind-", "Гармонизированный индекс потребительских цен, среднегодовой (2015 = 100)"),
    ("-prc_hicp_ainr-total-inx-", "Гармонизированный индекс потребительских цен, среднегодовой (2025 = 100)"),
)

# Английские пары к тем же рядам: сырые названия Евростата ("... ECOICOP ver.2 - indices and rates
# of change at constant tax rates, monthly data") длинны и не совпадают с русской подписью.
TITLE_EN_BY_CODE_FRAGMENT: tuple[tuple[str, str], ...] = (
    ("-prc_hicp_fpd-", "Harmonised index of consumer prices, first releases"),
    ("-prc_hicp_ct-", "Harmonised index of consumer prices at constant tax rates"),
    ("-prc_hicp_aind-", "Harmonised index of consumer prices, annual average (2015 = 100)"),
    ("-prc_hicp_ainr-total-inx-", "Harmonised index of consumer prices, annual average (2025 = 100)"),
)


def title_override_en_for_code(code: str | None) -> str | None:
    """Английское имя по фрагменту кода (см. TITLE_EN_BY_CODE_FRAGMENT) или None."""
    code_key = (code or "").strip().lower()
    if not code_key:
        return None
    for fragment, title in TITLE_EN_BY_CODE_FRAGMENT:
        if fragment in code_key:
            return title
    return None


def title_override_for_code(code: str | None) -> str | None:
    """Русское имя по фрагменту кода (см. TITLE_BY_CODE_FRAGMENT) или None."""
    code_key = (code or "").strip().lower()
    if not code_key:
        return None
    for fragment, title in TITLE_BY_CODE_FRAGMENT:
        if fragment in code_key:
            return title
    return None


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


@lru_cache(maxsize=8192)
def _apply_latin_cleanups(name: str) -> str:
    """Pure cleanup shared by repeated country titles; bounded per process."""
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
    elif title_override_for_code(code_key):
        base = title_override_for_code(code_key) or ""
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

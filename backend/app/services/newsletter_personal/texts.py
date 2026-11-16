"""Тексты персонального выпуска (ADR-0033): шаблоны ru/en, строка «почему вам это», типографика.

Правила редакции (концепция рассылки, раздел 6): число с источником и датой; без слов проекта и
техники (ряд-код, API, YoY, м/м); точные глаголы, без восклицаний; прогноз — одно число, «модельный
прогноз по официальному ряду, а не обещание». Тексты собираются только из полей факта — своих чисел
шаблоны не добавляют.
"""
from __future__ import annotations

import re

NBSP = " "

STR = {
    "ru": {
        "kicker.for_you": "Для вас",
        "kicker.watch": "Вы следите",
        "kicker.favorite": "Избранное",
        "kicker.download": "Вы скачивали",
        "kicker.search": "Вы искали",
        "kicker.view": "Ваши темы",
        "kicker.region": "Регион",
        "kicker.country": "Страна",
        "kicker.related": "Рядом с вашими темами",
        "kicker.forecast": "Прогноз",
        "kicker.check": "Сверка",
        "kicker.now": "Теперь есть на сайте",
        "kicker.since": "Пока вас не было",
        "kicker.table": "Ваши показатели",
        "why.watch": "Вы следите за этим показателем.",
        "why.favorite": "Этот показатель у вас в избранном.",
        "why.download": "Вы скачивали этот ряд.",
        "why.search": "Вы искали это на сайте.",
        "why.view": "Вы смотрели этот показатель.",
        "why.forecast": "Вы смотрели этот прогноз.",
        "why.region": "Вы смотрели данные этого региона.",
        "why.country": "Вы смотрели данные этой страны.",
        "why.related": "Его часто смотрят вместе с вашими показателями.",
        "why.topic": "По вашей теме: {topic}.",
        "why.mail_click": "Вы открывали его из прошлого письма.",
        "why.check": "Этот прогноз был в вашем письме.",
        "why.now": "Раньше ваш запрос на сайте ничего не находил.",
        "why.since": "Вы давно не заходили, а значение изменилось.",
        "forecast.note": "Модельный прогноз по официальному ряду, а не обещание.",
        "source.word": "Источник",
        "table.title": "Ваши показатели за неделю",
        "table.cols": ["Показатель", "Значение", "Изменение"],
        "section.title": "Для вас",
        "section.text": "Подборка по тому, что вы смотрели, искали и скачивали на сайте.",
        "intro.more": "{n} по вашим темам: {topics}.",
        "intro.since": "С вашего последнего визита {date} кое-что изменилось — ниже главное по вашим темам.",
        "note": ("Подборку «Для вас» мы составили по вашим действиям на сайте: что вы смотрели, искали "
                 "и скачивали. Отключить её можно по ссылке ниже — письмо останется, но без подборки."),
        "check.text": "В письме от {sent} наш прогноз на {period} был {forecast}. Официальное значение — {actual}.",
        "download.text": "{period_cap}. Вышло после вашего скачивания {day}.",
        "since.text": "{then_period} было {then}, сейчас {now} ({period}).",
        "compare.text": "По России — {value}.",
        "now.text": "Нашли ряд, который чаще всего выбирают по такому запросу.",
        "number.one": "число", "number.few": "числа", "number.many": "чисел",
    },
    "en": {
        "kicker.for_you": "For you",
        "kicker.watch": "You follow",
        "kicker.favorite": "Favourites",
        "kicker.download": "You downloaded",
        "kicker.search": "You searched",
        "kicker.view": "Your topics",
        "kicker.region": "Region",
        "kicker.country": "Country",
        "kicker.related": "Close to your topics",
        "kicker.forecast": "Forecast",
        "kicker.check": "Forecast check",
        "kicker.now": "Now on the site",
        "kicker.since": "While you were away",
        "kicker.table": "Your indicators",
        "why.watch": "You follow this indicator.",
        "why.favorite": "It is in your favourites.",
        "why.download": "You downloaded this series.",
        "why.search": "You searched for this on the site.",
        "why.view": "You viewed this indicator.",
        "why.forecast": "You viewed this forecast.",
        "why.region": "You looked at this region's data.",
        "why.country": "You looked at this country's data.",
        "why.related": "Readers often view it together with your indicators.",
        "why.topic": "On your topic: {topic}.",
        "why.mail_click": "You opened it from a previous email.",
        "why.check": "This forecast was in your email.",
        "why.now": "Your search on the site used to find nothing.",
        "why.since": "You have not visited for a while, and the value has changed.",
        "forecast.note": "A model forecast based on the official series, not a promise.",
        "source.word": "Source",
        "table.title": "Your indicators this week",
        "table.cols": ["Indicator", "Value", "Change"],
        "section.title": "For you",
        "section.text": "Picked from what you viewed, searched for and downloaded on the site.",
        "intro.more": "{n} on your topics: {topics}.",
        "intro.since": "Some things have changed since your last visit on {date}; below is the main news on your topics.",
        "note": ("We picked the “For you” section from what you did on the site: what you viewed, searched "
                 "for and downloaded. You can switch it off with the link below; the email stays, without the section."),
        "check.text": "In our email of {sent}, our forecast for {period} was {forecast}. The official figure is {actual}.",
        "download.text": "{period_cap}. Released after your download on {day}.",
        "since.text": "{then_period}: {then}; now {now} ({period}).",
        "compare.text": "Russia as a whole: {value}.",
        "now.text": "This is the series people most often pick for that search.",
        "number.one": "figure", "number.few": "figures", "number.many": "figures",
    },
}


def t(locale: str, key: str, **kw) -> str | list:
    value = STR["en" if locale == "en" else "ru"][key]
    return value.format(**kw) if kw and isinstance(value, str) else value


def plural(n: int, locale: str) -> str:
    if locale == "en":
        return f"{n} more {t(locale, 'number.one') if n == 1 else t(locale, 'number.many')}"
    if n % 10 == 1 and n % 100 != 11:
        word = t(locale, "number.one")
    elif 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        word = t(locale, "number.few")
    else:
        word = t(locale, "number.many")
    return f"{n}{NBSP}{word}"


def cap(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def sentence(*parts: str) -> str:
    """Части через точку: «На 9 ноября 2026. За неделю −0,70 ₽.»"""
    out = []
    for p in parts:
        p = (p or "").strip()
        if not p:
            continue
        p = cap(p)
        if not p.endswith((".", "?", "!")):
            p += "."
        out.append(p)
    return " ".join(out)


# Слова проекта и техники, которых не должно быть в письме (правило редакции 4).
_JARGON = (
    (re.compile(r"\bг/г\b"), "за год"), (re.compile(r"\bм/м\b"), "за месяц"), (re.compile(r"\bкв/кв\b"), "за квартал"),
    (re.compile(r"\bYoY\b"), "year on year"), (re.compile(r"\bMoM\b"), "month on month"),
    (re.compile(r"\bQoQ\b"), "quarter on quarter"),
)
FORBIDDEN_WORDS = re.compile(
    r"\b(API|ADR|парсер|parser|диапазон|коридор|интервал|range|interval)\b|(?<!\w)от\s[\d−-][^.]{0,40}\sдо\s[\d−-]",
    re.IGNORECASE,
)


def clean_title(title: str, limit: int = 110) -> str:
    out = title.strip()
    for pattern, repl in _JARGON:
        out = pattern.sub(repl, out)
    out = re.sub(r"\s+", " ", out)
    if len(out) > limit:
        cut = out[:limit].rsplit(" ", 1)[0].rstrip(",;:—- ")
        out = cut + "…"
    return out


def typo(s: str, locale: str) -> str:
    """Неразрывные пробелы как у сборщика редакции: число и единица, тысячи, короткие предлоги."""
    if not s:
        return s
    s = re.sub(r"(\d) (%|₽|\$|п\. п\.|руб\.|мск|MSK)", rf"\1{NBSP}\2", s)
    s = s.replace(" — ", NBSP + "— ")
    if locale != "en":
        s = re.sub(r"(?<=\s)(в|и|с|к|о|у|а|на|до|по|от|за|из|не) ", rf"\1{NBSP}", s)
        s = re.sub(r"^(В|И|С|К|О|У|А|На|До|По|От|За|Из|Не) ", rf"\1{NBSP}", s)
    return s

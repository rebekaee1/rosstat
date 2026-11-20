"""Строка «Как цитировать» на странице показателя (совет 19.11.2026, раздел 7.2 общей стратегии).

ИИ-помощники (ChatGPT, Алиса, Perplexity — около 100 входов в неделю, рост ×5 с августа) и люди,
которые пишут отчёты, берут у нас одно число. Строка даёт готовую ссылку: кто опубликовал
исходные данные, на какую дату значение, адрес страницы. Одинакова для человека и робота:
на годовой странице это чистый SSR, на карточке — тот же текст в SSR и в приложении
(`frontend/src/lib/citeLine.js`).
"""
from __future__ import annotations

from datetime import date
from html import escape

from app.services.display import format_date_locale

LABEL = {"ru": "Как цитировать", "en": "How to cite"}


_RU_MONTHS_NOM = ("январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь")
_EN_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
_ROMAN = ("I", "II", "III", "IV")


def _period_phrase(as_of: date, frequency: str | None, en: bool) -> str | None:
    """Период данных словами, как на клиенте (`citeLine.js`): «за II кв. 2026», «за 2025 год», «за июль 2026».
    Без известной частоты период не угадываем: None (строка уйдёт в прежнюю форму «на {дата}»)."""
    if frequency == "annual":
        return f"for {as_of.year}" if en else f"за {as_of.year} год"
    if frequency == "quarterly":
        q = (as_of.month - 1) // 3
        return f"for Q{q + 1} {as_of.year}" if en else f"за {_ROMAN[q]} кв. {as_of.year}"
    if frequency == "monthly":
        return f"for {_EN_MONTHS[as_of.month - 1]} {as_of.year}" if en else f"за {_RU_MONTHS_NOM[as_of.month - 1]} {as_of.year}"
    return None


def cite_text(*, name: str, source: str | None, url: str, as_of: date | None, locale: str,
              frequency: str | None = None, accessed: date | None = None) -> str:
    """«Forecast Economy. {Название}: источник данных — {источник}, данные за {период}, дата обращения {ДД.ММ.ГГГГ}. {адрес}».

    Круг наблюдателей 20.11.2026, №2: код периода из базы (`current_date` = 1 июня для II квартала) датой не пишем.
    Известна частота — период словами и дата обращения (сегодня); неизвестна — прежняя форма «на {дата}».
    """
    en = locale == "en"
    # Название с точкой на конце не даёт двух точек подряд (19.11.2026, рецензия №6).
    parts = [f"Forecast Economy. {name.strip().rstrip('.')}"]
    tail = []
    if source:
        tail.append(f"data from {source}" if en else f"источник данных — {source}")
    period = _period_phrase(as_of, frequency, en) if as_of is not None else None
    if period:
        tail.append(f"data {period}" if en else f"данные {period}")
        day = accessed or date.today()
        tail.append(f"accessed {day:%d.%m.%Y}" if en else f"дата обращения {day:%d.%m.%Y}")
    elif as_of is not None:
        tail.append(f"as of {format_date_locale(as_of)}" if en else f"на {format_date_locale(as_of)}")
    head = parts[0] + (": " + ", ".join(tail) if tail else "")
    return f"{head}. {url}"


def cite_html(*, name: str, source: str | None, url: str, as_of: date | None, locale: str,
              frequency: str | None = None, accessed: date | None = None) -> str:
    label = LABEL["en" if locale == "en" else "ru"]
    text = cite_text(name=name, source=source, url=url, as_of=as_of, locale=locale, frequency=frequency, accessed=accessed)
    return f'<p class="seo-cite"><span class="seo-cite__label">{escape(label)}:</span> {escape(text)}</p>\n'

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


def cite_text(*, name: str, source: str | None, url: str, as_of: date | None, locale: str) -> str:
    """«Forecast Economy. {Название}: источник данных — {источник}, на {дата}. {адрес}»."""
    en = locale == "en"
    # Название с точкой на конце не даёт двух точек подряд (19.11.2026, рецензия №6).
    parts = [f"Forecast Economy. {name.strip().rstrip('.')}"]
    tail = []
    if source:
        tail.append(f"data from {source}" if en else f"источник данных — {source}")
    if as_of is not None:
        tail.append(f"as of {format_date_locale(as_of)}" if en else f"на {format_date_locale(as_of)}")
    head = parts[0] + (": " + ", ".join(tail) if tail else "")
    return f"{head}. {url}"


def cite_html(*, name: str, source: str | None, url: str, as_of: date | None, locale: str) -> str:
    label = LABEL["en" if locale == "en" else "ru"]
    text = cite_text(name=name, source=source, url=url, as_of=as_of, locale=locale)
    return f'<p class="seo-cite"><span class="seo-cite__label">{escape(label)}:</span> {escape(text)}</p>\n'

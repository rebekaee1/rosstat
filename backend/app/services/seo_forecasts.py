"""Серверный HTML страницы «Прогнозы» (ADR-0003: тот же текст видят роботы и первый кадр человека).

Таблица строится из той же витрины, что отдаёт `/api/v1/forecasts/showcase`:
только прогнозы платформы, без пересказа проекций МВФ и без выдуманных рядов.
"""

from __future__ import annotations

import logging
from datetime import date
from html import escape

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import site_paths as paths
from app.services.display import format_month_year, format_number_ru
from app.services.forecast_showcase import change_phrase
from app.services.locale import get_locale
from app.services.seo_i18n import get_page_seo
from app.services.seo_renderer import (
    _breadcrumbs,
    _page_body,
    _page_trail,
    _site_json_ld,
    build_document,
    render_page_html,
)

logger = logging.getLogger(__name__)

_COPY = {
    "ru": {
        "name": "Показатель",
        "now": "Сейчас",
        "year": "Через год",
        "change": "Изменение",
        "range": "Коридор",
        "caption": "Прогноз на год вперёд, {theme}",
        "model": "Считает платформа по официальным данным.",
        "checked": "Для стран мира прогноз сначала проверен на прошлых данных.",
        "source": "Источник данных: {source}.",
        "updated": "Прогноз от {date}.",
    },
    "en": {
        "name": "Indicator",
        "now": "Now",
        "year": "In a year",
        "change": "Change",
        "range": "Range",
        "caption": "One-year-ahead forecast, {theme}",
        "model": "Built by the platform from official data.",
        "checked": "For countries outside Russia the forecast is first tested on past data.",
        "source": "Data source: {source}.",
        "updated": "Forecast of {date}.",
    },
}


def _value_text(value: float, unit: str, locale: str) -> str:
    rounded = round(float(value), 2 if abs(value) < 1000 else 0)
    number = format_number_ru(rounded, locale=locale)
    return f"{number} {unit}" if unit else number


def _item_row(item: dict, locale: str) -> str:
    copy = _COPY[locale]
    last = item["last_actual"]
    end = item["forecast_end"]
    unit = item.get("unit") or ""
    now_day = date.fromisoformat(last["date"])
    end_day = date.fromisoformat(end["date"])
    low, high = end.get("lower"), end.get("upper")
    corridor = ""
    if low is not None and high is not None:
        corridor = f"{format_number_ru(round(float(low), 2), locale=locale)} – {format_number_ru(round(float(high), 2), locale=locale)}"
    return (
        f'<tr><th scope="row"><a href="{escape(item["path"])}">{escape(item["title"])}</a></th>'
        f'<td>{escape(_value_text(last["value"], unit, locale))}<br>'
        f'<small>{escape(format_month_year(now_day, locale))}</small></td>'
        f'<td>{escape(_value_text(end["value"], unit, locale))}<br>'
        f'<small>{escape(format_month_year(end_day, locale))}</small></td>'
        f'<td>{escape(change_phrase(item["change"], locale))}'
        + (f'<br><small>{escape(copy["range"])}: {escape(corridor)}</small>' if corridor else "")
        + "</td></tr>"
    )


def _sections(payload: dict, locale: str) -> str:
    copy = _COPY[locale]
    themes = {t["id"]: t["name"] for t in payload.get("themes") or []}
    out = []
    for theme_id, theme_name in themes.items():
        items = [it for it in payload["items"] if it["theme"] == theme_id]
        if not items:
            continue
        head = (
            f'<tr><th>{escape(copy["name"])}</th><th>{escape(copy["now"])}</th>'
            f'<th>{escape(copy["year"])}</th><th>{escape(copy["change"])}</th></tr>'
        )
        rows = "".join(_item_row(item, locale) for item in items)
        out.append(
            f'<section><h2>{escape(theme_name)}</h2>'
            f'<table><caption>{escape(copy["caption"].format(theme=theme_name.lower()))}</caption>'
            f"<thead>{head}</thead><tbody>{rows}</tbody></table></section>"
        )
    if not out:
        return ""
    foot = f'<p class="seo-note">{escape(copy["model"])} {escape(copy["checked"])}</p>'
    return "".join(out) + foot


async def render_forecasts_html(db: AsyncSession) -> tuple[int, str]:
    from app.api.forecast_showcase import showcase_payload

    locale = "en" if get_locale() == "en" else "ru"
    try:
        payload = await showcase_payload(db, locale)
    except Exception:  # noqa: BLE001 — витрина не должна ронять страницу
        logger.warning("forecasts SSR: showcase unavailable, rendering the text-only page", exc_info=True)
        return await render_page_html("forecasts")
    section = _sections(payload, locale)
    if not section:
        return await render_page_html("forecasts")
    page = get_page_seo("forecasts")
    trail = _page_trail("forecasts", page)
    lead = f"<p>{escape(page.intro)}</p>"
    # Таблица стоит сразу после лида, до блоков «Как читать» и «Чего здесь нет».
    body = _page_body(page, trail).replace(lead, f"{lead}\n{section}", 1)
    return 200, await build_document(
        title=page.title,
        description=page.description,
        canonical_path=page.path,
        body=body,
        json_ld=[_site_json_ld(), _breadcrumbs(trail)],
        keywords=page.keywords,
    )

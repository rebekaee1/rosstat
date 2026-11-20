"""Серверная копия этажей «Регионы России» и «Мир» страницы «Туризм» (`/russia/category/tourism`).

Тот же набор, что видит посетитель (app/services/tourism_showcase.py): ссылки на рейтинги регионов,
на группы региональных рядов, рейтинги стран, список «Куда ездят россияне» и ссылку «все страны». Пустой этаж не выводится.
"""

from __future__ import annotations

from html import escape

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.locale import get_locale
from app.services.tourism_showcase import tourism_overview

_COPY = {
    "ru": {
        "regions": "Туризм по регионам России",
        "world": "Туризм в странах мира",
        "ratings": "Рейтинги стран",
        "outbound": "Куда ездят россияне",
        "all_countries": "Все страны ({n})",
        "all_countries_ex": "{n} {word} (Россия — в своём разделе)",
        "groups": {"flows": "Турпоток и гости", "stay": "Гостиницы и санатории", "money": "Доходы, траты и налоги",
                   "prices": "Цены", "transport": "Транспорт", "business": "Турфирмы и общепит"},
    },
    "en": {
        "regions": "Tourism across Russia's regions",
        "world": "Tourism in countries worldwide",
        "ratings": "Country rankings",
        "outbound": "Where Russians travel",
        "all_countries": "All countries ({n})",
        "all_countries_ex": "{n} countries (Russia has its own section)",
        "groups": {"flows": "Tourist flows and guests", "stay": "Hotels and health resorts",
                   "money": "Revenue, spending and taxes", "prices": "Prices", "transport": "Transport",
                   "business": "Tour operators and catering"},
    },
}


def _ru_countries_word(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return "страна"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "страны"
    return "стран"


def countries_label(world: dict, en: bool) -> str:
    """Подпись ссылки «все страны»: число — из `countries_count`, иначе длина списка (прежний путь)."""
    copy = _COPY["en" if en else "ru"]
    n = world.get("countries_count")
    if n is None:
        n = len(world.get("countries") or [])
    if world.get("russia_included") is False:
        return copy["all_countries_ex"].format(n=n, word=_ru_countries_word(int(n)))
    return copy["all_countries"].format(n=n)


def _number(value: float, en: bool) -> str:
    text = f"{value:,.0f}"
    return text if en else text.replace(",", "\u00a0")


def _a(path: str, label: str) -> str:
    return f'<a href="{escape(path)}">{escape(label)}</a>'


async def tourism_sections(db: AsyncSession) -> tuple[str, list[dict]]:
    """HTML двух этажей и элементы `mainEntity` для CollectionPage."""
    from app.services import site_paths as paths
    from app.services.seo_renderer import _absolute

    en = get_locale() == "en"
    copy = _COPY["en" if en else "ru"]
    data = await tourism_overview(db)
    parts: list[str] = []
    entities: list[dict] = []

    regions = data.get("regions", {}).get("items") or []
    if regions:
        groups_html = []
        for key in data["regions"].get("groups") or []:
            rows = [r for r in regions if r.get("group") == key]
            if not rows:
                continue
            items = []
            for row in rows:
                items.append(f'<li>{_a(row["path"], row["name"])}</li>')
                entities.append({"@type": "Dataset", "name": row["name"], "url": _absolute(row["path"])})
            groups_html.append(f'<h3>{escape(copy["groups"].get(key, key))}</h3><ul>{"".join(items)}</ul>')
        parts.append(f'<section><h2>{escape(copy["regions"])}</h2>{"".join(groups_html)}</section>')

    world = data.get("world", {})
    countries = world.get("countries") or []
    concepts = world.get("concepts") or []
    outbound = (world.get("outbound") or {}).get("items") or []
    if countries or concepts or outbound:
        body = ""
        if concepts:
            body += (f'<h3>{escape(copy["ratings"])}</h3><ul>'
                     + "".join(f'<li>{_a(c["path"], c["name"])}</li>' for c in concepts) + "</ul>")
        if outbound:
            unit = (world.get("outbound") or {}).get("unit") or ""
            lines = "".join(
                f'<li>{_a(r["path"], r["name"])} — {_number(r["value"], en)} {escape(unit)}, {escape(str(r["period"]))}</li>'
                for r in outbound
            )
            body += f'<h3>{escape(copy["outbound"])}</h3><ol>{lines}</ol>'
            for r in outbound:
                entities.append({"@type": "Dataset", "name": r["name"], "url": _absolute(r["path"])})
        if countries:
            body += f'<p>{_a(paths.home(), countries_label(world, en))}</p>'
        parts.append(f'<section><h2>{escape(copy["world"])}</h2>{body}</section>')
    return ("\n".join(parts) + "\n") if parts else "", entities[:40]

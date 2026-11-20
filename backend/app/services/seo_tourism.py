"""Серверная копия этажей «Регионы России» и «Мир» страницы «Туризм» (`/russia/category/tourism`).

Тот же набор, что видит посетитель (app/services/tourism_showcase.py): ссылки на рейтинги регионов,
на карточки регионов-лидеров, на ряды стран мира и рейтинги стран. Пустой этаж не выводится.
"""

from __future__ import annotations

from html import escape

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.locale import get_locale
from app.services.tourism_showcase import tourism_overview

_COPY = {
    "ru": {
        "regions": "Туризм по регионам России",
        "regions_lead": "Рейтинги субъектов: где больше гостиниц, туристов и поездок. Три лидера — по последнему году.",
        "leaders": "Лидеры",
        "world": "Туризм в странах мира",
        "world_lead": "Официальные ряды национальных служб статистики и международных организаций.",
        "ratings": "Рейтинги стран",
    },
    "en": {
        "regions": "Tourism across Russia's regions",
        "regions_lead": "Regional rankings: where there are more hotels, tourists and trips. Top three for the latest year.",
        "leaders": "Leaders",
        "world": "Tourism in countries worldwide",
        "world_lead": "Official series from national statistical offices and international organisations.",
        "ratings": "Country rankings",
    },
}


def _a(path: str, label: str) -> str:
    return f'<a href="{escape(path)}">{escape(label)}</a>'


async def tourism_sections(db: AsyncSession) -> tuple[str, list[dict]]:
    """HTML двух этажей и элементы `mainEntity` для CollectionPage."""
    from app.services.seo_renderer import _absolute

    copy = _COPY["en" if get_locale() == "en" else "ru"]
    data = await tourism_overview(db)
    parts: list[str] = []
    entities: list[dict] = []

    regions = data.get("regions", {}).get("items") or []
    if regions:
        items = []
        for row in regions:
            leaders = row.get("leaders") or []
            tail = ""
            if leaders:
                tail = f' — {escape(copy["leaders"])}: ' + ", ".join(_a(l["path"], l["name"]) for l in leaders)
            items.append(f'<li>{_a(row["rating_path"], row["name"])}{tail}</li>')
            entities.append({"@type": "Dataset", "name": row["name"], "url": _absolute(row["rating_path"])})
        parts.append(
            f'<section><h2>{escape(copy["regions"])}</h2><p>{escape(copy["regions_lead"])}</p>'
            f'<ul>{"".join(items)}</ul></section>'
        )

    world = data.get("world", {})
    countries = world.get("countries") or []
    concepts = world.get("concepts") or []
    if countries or concepts:
        items = []
        for country in countries:
            series = ", ".join(_a(s["path"], s["name"]) for s in country.get("series") or [])
            items.append(f'<li>{_a(country["path"], country["name"])}{": " + series if series else ""}</li>')
            for s in country.get("series") or []:
                entities.append({"@type": "Dataset", "name": f'{country["name"]}: {s["name"]}',
                                 "url": _absolute(s["path"])})
        ratings = ""
        if concepts:
            ratings = (f'<h3>{escape(copy["ratings"])}</h3><ul>'
                       + "".join(f'<li>{_a(c["path"], c["name"])}</li>' for c in concepts) + "</ul>")
        parts.append(
            f'<section><h2>{escape(copy["world"])}</h2><p>{escape(copy["world_lead"])}</p>'
            f'{ratings}<ul>{"".join(items)}</ul></section>'
        )
    return ("\n".join(parts) + "\n") if parts else "", entities[:40]

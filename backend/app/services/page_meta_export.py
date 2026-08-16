"""Frontend-проекция PAGE_META / CATEGORY_META / world SEO-констант.

Единая точка истины для публичных title/description/h1 остаётся в
`seo_content.py` и `seo_world.py`. Этот модуль сериализует их в JSON-зеркало
для React (`pageMeta.generated.json`), чтобы CSR не перетирал SSR другими
строками (ADR-0003).
"""

from __future__ import annotations

from typing import Any

from app.services.seo_content import CATEGORY_META, PAGE_META
from app.services.seo_world import (
    COUNTRY_GENITIVE,
    WORLD_HOME_DESC,
    WORLD_HOME_H1,
    WORLD_HOME_TITLE,
)


def build_page_meta_blob() -> dict[str, Any]:
    pages = {
        slug: {
            "slug": page.slug,
            "path": page.path,
            "title": page.title,
            "description": page.description,
            "h1": page.h1,
            "intro": page.intro,
        }
        for slug, page in PAGE_META.items()
    }
    categories = {
        slug: {
            "slug": meta.slug,
            "name": meta.name,
            "title": meta.title,
            "description": meta.description,
            "h1": meta.title,
            "intro": meta.intro,
        }
        for slug, meta in CATEGORY_META.items()
    }
    return {
        "pages": pages,
        "categories": categories,
        "world": {
            "home": {
                "path": "/world",
                "title": WORLD_HOME_TITLE,
                "description": WORLD_HOME_DESC,
                "h1": WORLD_HOME_H1,
            },
            "countryTitleTemplate": "Экономика {genitive}: статистика и показатели",
            "countryDescEurostatTemplate": (
                "{name}: {n_phrase} Евростата — цены, ВВП, рынок труда, торговля "
                "и финансы. Графики и последние значения на Forecast Economy."
            ),
            "countryDescNationalTemplate": (
                "{name}: {n_phrase} — цены, ВВП, рынок труда, торговля и финансы. "
                "Источник: {source_phrase}. Графики и последние значения на Forecast Economy."
            ),
            "countryGenitive": dict(sorted(COUNTRY_GENITIVE.items())),
        },
    }

"""Frontend-проекция PAGE_META / CATEGORY_META / world SEO-констант.

Единая точка истины для публичных title/description/h1 остаётся в
`seo_content.py` и `seo_world.py`. Этот модуль сериализует их в JSON-зеркало
для React (`pageMeta.generated.json`), чтобы CSR не перетирал SSR другими
строками (ADR-0003).

EN twins (если заполнены контент-агентом в `data/i18n/seo_en.py`) кладутся
в blob["en"] — каркас; пустой dict пока EN не готов.
"""

from __future__ import annotations

from typing import Any

from app.data.i18n.seo_en import (
    CATEGORY_META_EN,
    PAGE_META_EN,
    WORLD_HOME_DESC_EN,
    WORLD_HOME_H1_EN,
    WORLD_HOME_TITLE_EN,
    WORLD_TEMPLATES_EN,
)
from app.services.seo_content import CATEGORY_META, PAGE_META
from app.services.seo_world import (
    COUNTRY_GENITIVE,
    WORLD_HOME_DESC,
    WORLD_HOME_H1,
    WORLD_HOME_TITLE,
)


def _serialize_pages(pages: dict) -> dict[str, Any]:
    return {
        slug: {
            "slug": page.slug,
            "path": page.path,
            "title": page.title,
            "description": page.description,
            "h1": page.h1,
            "intro": page.intro,
        }
        for slug, page in pages.items()
    }


def _serialize_categories(categories: dict) -> dict[str, Any]:
    return {
        slug: {
            "slug": meta.slug,
            "name": meta.name,
            "title": meta.title,
            "description": meta.description,
            "h1": meta.title,
            "intro": meta.intro,
        }
        for slug, meta in categories.items()
    }


def build_page_meta_blob() -> dict[str, Any]:
    blob: dict[str, Any] = {
        "pages": _serialize_pages(PAGE_META),
        "categories": _serialize_categories(CATEGORY_META),
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
    blob["en"] = {
        "pages": _serialize_pages(PAGE_META_EN),
        "categories": _serialize_categories(CATEGORY_META_EN),
        "world": {
            "home": {
                "path": "/world",
                "title": WORLD_HOME_TITLE_EN,
                "description": WORLD_HOME_DESC_EN,
                "h1": WORLD_HOME_H1_EN,
            },
            # Placeholders: {country}, {n_phrase}, {source_phrase} — см. WORLD_TEMPLATES_EN.
            "countryTitleTemplate": WORLD_TEMPLATES_EN["country_title"],
            "countryDescEurostatTemplate": WORLD_TEMPLATES_EN["country_desc_eurostat"],
            "countryDescNationalTemplate": WORLD_TEMPLATES_EN["country_desc_national"],
            "nIndicatorsOne": WORLD_TEMPLATES_EN["n_indicators_one"],
            "nIndicatorsMany": WORLD_TEMPLATES_EN["n_indicators_many"],
        },
    }
    return blob

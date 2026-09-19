"""Политика индексации: спрос × содержание, три уровня (план 2026-09-03).

Одна точка истины для sitemap (что подаём роботу) и SSR robots-meta
(что индексируем). Порог — таблица констант ниже; тот же предикат
используется билдерами `site_urls` и `seo_renderer.build_document`.

Tier 1 — sitemap priority 0.8–1.0, IndexNow, переобход.
Tier 2 — sitemap priority 0.3–0.4.
Tier 3 — `noindex,follow`, не в sitemap, доступны по ссылкам.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

Tier = Literal[1, 2, 3]

# --- Пороги (одна таблица) -------------------------------------------------

# Минимум наблюдений за год: полный квартальный/годовой ряд либо
# прежний порог шесть для месячных и более частых рядов.
RUSSIA_YEAR_MIN_POINTS = 6
RUSSIA_YEAR_MIN_POINTS_BY_FREQUENCY = {"annual": 1, "quarterly": 4}
# Мировые карточки Tier 2: минимум точек и не «сырое» машинное имя.
WORLD_CARD_MIN_POINTS = 8

TIER1_PRIORITY = "0.8"
TIER2_PRIORITY = "0.4"

# `?mode=` никогда не каноничен: в view_model_families нет per-mode seo-title.
MODE_CANONICAL = False

_HONEYPOT_PATH = "/__honeypot__/trap"


def curated_world_dataset_ids() -> frozenset[str]:
    """dataset_id контрактов WORLD_CONCEPTS — SQL-фильтр мировых годовых."""
    from app.data.world_concepts import WORLD_CONCEPTS

    ids: set[str] = set()
    for concept in WORLD_CONCEPTS:
        ids.update(concept.dataset_ids or ())
        for extra in (concept.provider_dataset_ids or {}).values():
            ids.update(extra or ())
    return frozenset(ids)


def robots_for_path(path: str, *, today: date | None = None) -> str:
    """Содержимое meta robots для SSR. Preview-локаль обрабатывает renderer."""
    if is_noindex_path(path, today=today):
        return (
            "noindex, follow, max-snippet:-1, max-image-preview:large, "
            "max-video-preview:-1"
        )
    return (
        "index, follow, max-snippet:-1, max-image-preview:large, "
        "max-video-preview:-1"
    )


def is_noindex_path(path: str, *, today: date | None = None) -> bool:
    """Tier 3: страница живая, но не для индекса."""
    raw = (path or "").split("?", 1)[0].rstrip("/") or "/"
    if raw == honeypot_path() or raw.startswith("/__honeypot__/"):
        return True
    # Возраст не определяет полезность истории. Наличие данных и канон
    # проверяют маршруты и sitemap, а не календарный cutoff по URL.
    return False


def strip_mode_query(path: str) -> str:
    """Канон карточки — без ?mode=, кроме curated per-mode (их нет)."""
    if MODE_CANONICAL:
        return path
    if "?" not in path:
        return path
    base, _, query = path.partition("?")
    kept = [
        part for part in query.split("&")
        if part and not part.startswith("mode=")
    ]
    return f"{base}?{'&'.join(kept)}" if kept else base


def honeypot_path() -> str:
    return _HONEYPOT_PATH

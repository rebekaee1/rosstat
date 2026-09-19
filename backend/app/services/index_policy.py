"""Политика индексации: спрос × содержание, три уровня (план 2026-09-03).

Одна точка истины для sitemap (что подаём роботу) и SSR robots-meta
(что индексируем). Порог — таблица констант ниже; тот же предикат
используется билдерами `site_urls` и `seo_renderer.build_document`.

Tier 1 — sitemap priority 0.8–1.0, IndexNow, переобход.
Tier 2 — sitemap priority 0.3–0.4.
Tier 3 — `noindex,follow`, не в sitemap, доступны по ссылкам.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Literal

from app.services.display import today_msk

Tier = Literal[1, 2, 3]

# --- Пороги (одна таблица) -------------------------------------------------

# Годовые лендинги макро РФ: минимум точек за календарный год.
RUSSIA_YEAR_MIN_POINTS = 6
# Региональные годовые: последние N лет listed-пар.
REGIONAL_YEAR_LOOKBACK = 5
# Мировые годовые: только curated-концепты, последние N лет.
WORLD_YEAR_LOOKBACK = 10
# Месячные лендинги макро: текущий + прошлый календарный год.
MONTH_LOOKBACK_YEARS = 1
# Мировые карточки Tier 2: минимум точек и не «сырое» машинное имя.
WORLD_CARD_MIN_POINTS = 8

TIER1_PRIORITY = "0.8"
TIER2_PRIORITY = "0.4"

# `?mode=` никогда не каноничен: в view_model_families нет per-mode seo-title.
MODE_CANONICAL = False

_HONEYPOT_PATH = "/__honeypot__/trap"

# /russia/region/{slug}/{code}/{year}
_RE_REGION_YEAR = re.compile(
    r"^/russia/region/[^/]+/[^/]+/(\d{4})$"
)
# /russia/indicator/{code}/{year}  (не месяц YYYY-MM)
_RE_RU_YEAR = re.compile(
    r"^/russia/indicator/[^/]+/(\d{4})$"
)
# /russia/indicator/{code}/{year}-{mm}
_RE_RU_MONTH = re.compile(
    r"^/russia/indicator/[^/]+/(\d{4})-(\d{2})$"
)
# /{country}/indicator/{code}/{year}  (не russia)
_RE_WORLD_YEAR = re.compile(
    r"^/(?!russia/)[a-z0-9-]+/indicator/[^/]+/(\d{4})$"
)


def regional_year_min(today: date | None = None) -> int:
    t = today or today_msk()
    return t.year - REGIONAL_YEAR_LOOKBACK


def world_year_min(today: date | None = None) -> int:
    t = today or today_msk()
    return t.year - WORLD_YEAR_LOOKBACK


def month_year_min(today: date | None = None) -> int:
    t = today or today_msk()
    return t.year - MONTH_LOOKBACK_YEARS


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
    t = today or today_msk()
    m = _RE_REGION_YEAR.match(raw)
    if m and int(m.group(1)) < regional_year_min(t):
        return True
    m = _RE_RU_MONTH.match(raw)
    if m and int(m.group(1)) < month_year_min(t):
        return True
    m = _RE_WORLD_YEAR.match(raw)
    if m and int(m.group(1)) < world_year_min(t):
        return True
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

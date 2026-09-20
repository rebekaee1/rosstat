"""Все действующие публичные canonical-страницы доступны для индексации.

Решение владельца 2026-09-20: sitemap не отбирает контент по теме,
возрасту, популярности или объёму данных сверх условий самого SSR.
Priority задаёт очередность обхода, а не исключение страниц.
Служебные поверхности, preview, редиректы и несуществующие страницы
не являются дополнительными публичными canonical-страницами.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

Tier = Literal[1, 2, 3]

# --- Пороги (одна таблица) -------------------------------------------------

# Годовая SSR-страница РФ существует при хотя бы одном наблюдении.
RUSSIA_YEAR_MIN_POINTS = 1

TIER1_PRIORITY = "0.8"
TIER2_PRIORITY = "0.4"

# `?mode=` никогда не каноничен: в view_model_families нет per-mode seo-title.
MODE_CANONICAL = False

_HONEYPOT_PATH = "/__honeypot__/trap"


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

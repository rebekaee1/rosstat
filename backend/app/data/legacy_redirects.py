"""301-карта легаси-URL (А-2/А-3, Волна 4.5 CTO-аудита).

Одна точка истины для серверных редиректов SSR-слоя. Робот Яндекса продолжает
обходить URL, которых больше нет (переименованные коды, старые слаги регионов,
unlisted sibling-ряды из старых sitemap) — каждый 404 по ранее известному URL
минусует траст домена, 301 передаёт накопленный вес каноническому адресу.

Три источника редиректов:
1. `LEGACY_INDICATOR_REDIRECTS` — переименованные/удалённые коды из выгрузок
   Вебмастера (06.07.2026): точечная ручная карта.
2. `resolve_unlisted_indicator()` — unlisted sibling generic-семьи → канонический
   `/indicator/{base}?mode={mode}` (данные те же, карточка одна). Плюс bespoke
   легаси-ряды (unemployment-*, *-yoy-abs), которых нет в generic-реестре.
3. `LEGACY_REGION_SLUG_PREFIXES` — старые короткие слаги регионов
   («tatarstan» → «respublika-tatarstan»): проверяется в SSR-роуте по БД.
"""

from functools import lru_cache

# Переименованные/исчезнувшие коды (подтверждено выгрузкой Вебмастера).
LEGACY_INDICATOR_REDIRECTS: dict[str, str] = {
    "inflation": "/indicator/cpi",
    "gasoline-ai92": "/indicator/fuel-ai92",
    "gasoline-ai95": "/indicator/fuel-ai95",
    "gdp-deflator": "/indicator/gdp-nominal",
    "refinancing-rate": "/indicator/key-rate",
}

# Bespoke-ряды вне generic-реестра, державшиеся только на клиентском
# canonical-редиректе (ЭСКАЛАЦИЯ-зона AGENTS.md: их SSR-404 = тихая просадка).
_BESPOKE_UNLISTED_CANONICAL: dict[str, str] = {
    "unemployment-quarterly": "/indicator/unemployment?mode=quarterly",
    "unemployment-annual": "/indicator/unemployment?mode=annual",
    "trade-balance-yoy-abs": "/indicator/trade-balance?mode=yoy_abs",
    "current-account-yoy-abs": "/indicator/current-account?mode=yoy_abs",
}

# Старые короткие слаги регионов: пробуем канонический с префиксом.
LEGACY_REGION_SLUG_PREFIXES = ("respublika-",)


@lru_cache(maxsize=1)
def _generic_sibling_index() -> dict[str, str]:
    """code sibling-ряда → канонический путь семьи (ленивая сборка из FAMILIES)."""
    from app.data.view_model_families import FAMILIES

    index: dict[str, str] = {}
    for fam in FAMILIES:
        for mode in fam.modes:
            if mode.code != fam.base:
                index[mode.code] = f"/indicator/{fam.base}?mode={mode.mode}"
    return index


def resolve_legacy_indicator(code: str) -> str | None:
    """Целевой путь 301 для легаси-кода карточки, или None."""
    return LEGACY_INDICATOR_REDIRECTS.get(code)


def resolve_unlisted_indicator(code: str) -> str | None:
    """Канонический путь для unlisted sibling-ряда (generic или bespoke)."""
    return _BESPOKE_UNLISTED_CANONICAL.get(code) or _generic_sibling_index().get(code)

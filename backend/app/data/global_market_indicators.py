"""Мировые рыночные ряды в общем каталоге indicators.

Живут по URL `/russia/indicator/{code}` (общий data plane), но это не
российская статистика: в крошках «Россия» не показываем, публичные тексты
без отсылок «для российской аудитории».
"""

from __future__ import annotations

# Базовые коды (siblings view-mode: `{base}-avg-month`, `{base}-yoy`, …).
GLOBAL_MARKET_INDICATOR_BASES: frozenset[str] = frozenset(
    {
        "btc-usd",
        "eth-usd",
        "sol-usd",
        "usd-index",
        "ust-10y",
        "eur-usd",
        "gbp-usd",
        "usd-cny",
        "brent",
        "natural-gas",
        "copper",
        "silver",
        "wheat",
        "soybean",
        "coal",
    }
)


def is_global_market_indicator(code: str | None) -> bool:
    if not code:
        return False
    if code in GLOBAL_MARKET_INDICATOR_BASES:
        return True
    return any(code.startswith(f"{base}-") for base in GLOBAL_MARKET_INDICATOR_BASES)


# Страна → базовые коды из GLOBAL_MARKET_INDICATOR_BASES.
# Только экономически очевидные привязки: ряд живёт в общем каталоге, но
# со страницы страны на него должен быть прямой выход. Пустой кортеж = блока нет.
COUNTRY_MARKET_INDICATOR_CODES: dict[str, tuple[str, ...]] = {
    "united-states": ("ust-10y", "usd-index"),
}


def market_indicator_codes_for_country(slug: str | None) -> tuple[str, ...]:
    """Коды рыночных рядов, связанные со страной. Неизвестная страна → ()."""
    if not slug:
        return ()
    codes = COUNTRY_MARKET_INDICATOR_CODES.get(slug, ())
    return tuple(code for code in codes if code in GLOBAL_MARKET_INDICATOR_BASES)

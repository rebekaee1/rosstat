"""Реестр мировых рыночных рядов: SSR и SPA обязаны видеть один список.

Ряды живут в общем каталоге (`/russia/indicator/{code}`), но российской
статистикой не являются: в крошках у них нет узла «Россия», а публичные тексты
идут без отсылок к российской аудитории. Список зеркалится в JS — если копии
разойдутся, SSR-крошки перестанут совпадать с клиентскими, и поисковик
переиндексирует карточку как изменившуюся.
"""

import re
from pathlib import Path

from app.data.global_market_indicators import (
    GLOBAL_MARKET_INDICATOR_BASES,
    is_global_market_indicator,
    market_indicator_codes_for_country,
)

ROOT = Path(__file__).resolve().parents[2]
MIRROR = ROOT / "frontend/src/lib/globalMarketIndicators.js"


def _js_bases() -> set[str]:
    text = MIRROR.read_text(encoding="utf-8")
    block = text.split("GLOBAL_MARKET_INDICATOR_BASES", 1)[1].split("]", 1)[0]
    return set(re.findall(r"'([a-z0-9-]+)'", block))


def test_registry_mirrored_in_frontend():
    assert _js_bases() == set(GLOBAL_MARKET_INDICATOR_BASES)


def test_view_mode_siblings_inherit_the_flag():
    assert is_global_market_indicator("ust-10y")
    assert is_global_market_indicator("ust-10y-avg-month")
    assert is_global_market_indicator("brent-yoy")
    # Российские ряды и пустой код флаг не получают.
    assert not is_global_market_indicator("cpi")
    assert not is_global_market_indicator("")
    assert not is_global_market_indicator(None)


def test_country_market_codes_only_united_states():
    assert market_indicator_codes_for_country("united-states") == ("ust-10y", "usd-index")
    assert all(
        code in GLOBAL_MARKET_INDICATOR_BASES
        for code in market_indicator_codes_for_country("united-states")
    )
    assert market_indicator_codes_for_country("germany") == ()
    assert market_indicator_codes_for_country("france") == ()
    assert market_indicator_codes_for_country(None) == ()
    assert market_indicator_codes_for_country("") == ()

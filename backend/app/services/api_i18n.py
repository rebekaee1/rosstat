"""Locale-aware strings for user-visible API error ``detail``.

Only the handful of messages shown in login/register/account/download UI —
not a general translation layer. Uses ``get_locale()`` (bound by locale
middleware from Host / ``X-FE-Locale``).
"""

from __future__ import annotations

from app.services.locale import get_locale


def api_detail(ru: str, en: str) -> str:
    """Pick RU or EN for an HTTPException detail / validation message."""
    return en if get_locale() == "en" else ru

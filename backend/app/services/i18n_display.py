"""Public display name selection by locale (name vs name_en)."""

from __future__ import annotations

from app.services.locale import Locale, get_locale


def public_name(
    name_ru: str | None,
    name_en: str | None = None,
    *,
    locale: Locale | None = None,
) -> str:
    """Return the locale-facing label. Falls back to Russian if EN missing."""
    loc = locale or get_locale()
    ru = (name_ru or "").strip()
    en = (name_en or "").strip()
    if loc == "en" and en:
        return en
    return ru or en

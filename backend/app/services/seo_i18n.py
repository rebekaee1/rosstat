"""SEO / copy helpers that respect the request locale.

Content twins:
  - ``seo_en.py`` — PAGE_META_EN / CATEGORY_META_EN / world / regional templates
  - ``indicator_copy_en.py`` — macro INDICATOR_COPY_EN (content agent)
  - ``regions_en.py`` / ``region_indicators_en.py`` — regional EN
Missing EN → fall back to Russian registries.
"""

from __future__ import annotations

from app.data.i18n.glossary_en import GLOSSARY_EN
from app.data.i18n.indicator_copy_en import INDICATOR_COPY_EN
from app.data.i18n.region_indicators_en import REGION_INDICATORS_EN
from app.data.i18n.regions_en import REGIONS_EN
from app.data.i18n.seo_en import (
    CALENDAR_TEMPLATES_EN,
    CATEGORY_META_EN,
    HOME_TEMPLATES_EN,
    INDICATOR_TEMPLATES_EN,
    PAGE_META_EN,
    PAGE_TEMPLATES_EN,
    REGIONAL_TEMPLATES_EN,
    TODAY_HUB_DESC_EN,
    TODAY_HUB_H1_EN,
    TODAY_HUB_TITLE_EN,
    TODAY_SPECS_EN,
    TODAY_TEMPLATES_EN,
    WORLD_HOME_DESC_EN,
    WORLD_HOME_H1_EN,
    WORLD_HOME_TITLE_EN,
    WORLD_TEMPLATES_EN,
    YEAR_TEMPLATES_EN,
)
from app.services.locale import Locale, get_locale
from app.services.seo_content import (
    CATEGORY_META,
    PAGE_META,
    CategorySeo,
    PageSeo,
)

# RU view-mode / group labels → EN (picker + SSR mode suffix).
_VIEW_MODE_LABEL_EN: dict[str, str] = {
    "На конец периода": "Period end",
    "Средняя за период": "Period average",
    "К прошлому периоду": "Vs previous period",
    "К соотв. периоду пред. года": "Vs same period previous year",
    "Г/г": "YoY",
    "Год к году": "Year on year",
    "Кв/Кв": "QoQ",
    "М/м": "MoM",
    "Н/н": "WoW",
    "По месяцам": "Monthly",
    "По кварталам": "Quarterly",
    "По годам": "Annual",
    "По неделям": "Weekly",
    "По дням": "Daily",
    "Уровень": "Level",
    "Индекс": "Index",
    "За период": "Over the period",
    "Помесячно": "Monthly",
    "Сглаживание": "Smoothing",
    "12М среднее": "12M average",
    "Уровень ставки": "Rate level",
    "Ежедневно": "Daily",
    "Понедельно": "Weekly",
    "Поквартально": "Quarterly",
    "Годово": "Annual",
    "Частота отображения": "Display frequency",
    "Режим отображения": "Display mode",
}

_HERO_LABEL_EN: dict[str, str] = {
    "Год к году": "Year on year",
    "Изменение г/г": "YoY change",
}

# World/Russia category_ru (api_category) → EN display name.
# Synced with CATEGORY_META_EN.name / categories.js nameEn; extras for world-only buckets.
_WORLD_CATEGORY_EN_EXTRA: dict[str, str] = {
    "Общество": "Society",
    "Прочее": "Other",
    "Национальные счета": "National accounts",
    "Статистика": "Statistics",
    "разделе": "section",
}


def _category_ru_to_en_map() -> dict[str, str]:
    out = dict(_WORLD_CATEGORY_EN_EXTRA)
    for meta in CATEGORY_META_EN.values():
        if meta.api_category:
            out[meta.api_category] = meta.name
    return out


def localize_category_name(
    category_ru: str | None,
    *,
    locale: Locale | None = None,
    fallback: str | None = None,
) -> str:
    """Locale-facing category label from Russian ``category_ru`` / api_category."""
    raw = (category_ru or "").strip()
    loc = locale or get_locale()
    if not raw:
        if loc == "en":
            return fallback or "Other"
        return fallback or "Прочее"
    if loc != "en":
        return raw
    return _category_ru_to_en_map().get(raw, raw)


def event_public_title(
    title_ru: str | None,
    title_en: str | None = None,
    *,
    locale: Locale | None = None,
) -> str:
    """Calendar event title: prefer ``title_en`` on EN locale (no MT)."""
    loc = locale or get_locale()
    if loc == "en":
        en = (title_en or "").strip()
        if en:
            return en
    return (title_ru or "").strip()


def get_page_seo(slug: str, locale: Locale | None = None) -> PageSeo | None:
    loc = locale or get_locale()
    if loc == "en":
        page = PAGE_META_EN.get(slug)
        if page is not None:
            return page
    return PAGE_META.get(slug)


def get_category_seo(slug: str, locale: Locale | None = None) -> CategorySeo | None:
    loc = locale or get_locale()
    if loc == "en":
        meta = CATEGORY_META_EN.get(slug)
        if meta is not None:
            return meta
    return CATEGORY_META.get(slug)


def home_template(key: str, locale: Locale | None = None) -> str | None:
    """EN twin for apex homepage SSR fragments. Missing key → None (RU caller)."""
    loc = locale or get_locale()
    if loc == "en":
        return HOME_TEMPLATES_EN.get(key)
    return None


def page_template(key: str, locale: Locale | None = None) -> str | None:
    """EN twin for PAGE_META SSR section headings. Missing key → None (RU caller)."""
    loc = locale or get_locale()
    if loc == "en":
        return PAGE_TEMPLATES_EN.get(key)
    return None


def world_home_title(locale: Locale | None = None) -> str | None:
    loc = locale or get_locale()
    if loc == "en" and WORLD_HOME_TITLE_EN:
        return WORLD_HOME_TITLE_EN
    return None


def world_home_description(locale: Locale | None = None) -> str | None:
    loc = locale or get_locale()
    if loc == "en" and WORLD_HOME_DESC_EN:
        return WORLD_HOME_DESC_EN
    return None


def world_home_h1(locale: Locale | None = None) -> str | None:
    loc = locale or get_locale()
    if loc == "en" and WORLD_HOME_H1_EN:
        return WORLD_HOME_H1_EN
    return None


def region_display_name(slug: str, name_ru: str, locale: Locale | None = None) -> str:
    loc = locale or get_locale()
    if loc == "en":
        return REGIONS_EN.get(slug) or name_ru
    return name_ru


def region_indicator_copy(
    code: str,
    *,
    name_ru: str,
    unit_ru: str,
    note_ru: str | None = None,
    section_ru: str | None = None,
    locale: Locale | None = None,
) -> dict[str, str | None]:
    loc = locale or get_locale()
    if loc == "en":
        en = REGION_INDICATORS_EN.get(code) or {}
        return {
            "name": en.get("name") or name_ru,
            "unit": en.get("unit") or unit_ru,
            "note": en.get("note") if en.get("note") is not None else note_ru,
            "section": en.get("section") or section_ru,
        }
    return {
        "name": name_ru,
        "unit": unit_ru,
        "note": note_ru,
        "section": section_ru,
    }


def regional_template(key: str, locale: Locale | None = None) -> str | None:
    loc = locale or get_locale()
    if loc == "en":
        return REGIONAL_TEMPLATES_EN.get(key)
    return None


def world_template(key: str, locale: Locale | None = None) -> str | None:
    """EN twin for world SSR title/desc/h1 fragments. Missing key → None (RU)."""
    loc = locale or get_locale()
    if loc == "en":
        return WORLD_TEMPLATES_EN.get(key)
    return None


def today_template(key: str, locale: Locale | None = None) -> str | None:
    loc = locale or get_locale()
    if loc == "en":
        return TODAY_TEMPLATES_EN.get(key)
    return None


def today_spec_en(code: str, locale: Locale | None = None) -> dict[str, str] | None:
    """EN query/question overlay for a today-code, or None (use RU TodaySpec)."""
    loc = locale or get_locale()
    if loc != "en":
        return None
    return TODAY_SPECS_EN.get(code)


def today_hub_title(date_text: str, locale: Locale | None = None) -> str | None:
    loc = locale or get_locale()
    if loc == "en" and TODAY_HUB_TITLE_EN:
        return TODAY_HUB_TITLE_EN.format(date=date_text)
    return None


def today_hub_description(locale: Locale | None = None) -> str | None:
    loc = locale or get_locale()
    if loc == "en" and TODAY_HUB_DESC_EN:
        return TODAY_HUB_DESC_EN
    return None


def today_hub_h1(locale: Locale | None = None) -> str | None:
    loc = locale or get_locale()
    if loc == "en" and TODAY_HUB_H1_EN:
        return TODAY_HUB_H1_EN
    return None


def calendar_template(key: str, locale: Locale | None = None) -> str | None:
    loc = locale or get_locale()
    if loc != "en":
        return None
    value = CALENDAR_TEMPLATES_EN.get(key)
    return value if isinstance(value, str) else None


def calendar_month_name(month: int, locale: Locale | None = None) -> str | None:
    """English month name (1–12), or None for RU callers."""
    loc = locale or get_locale()
    if loc != "en":
        return None
    months = CALENDAR_TEMPLATES_EN.get("months")
    if isinstance(months, (tuple, list)) and 1 <= month <= 12:
        name = months[month]
        return name if isinstance(name, str) and name else None
    return None


_RU_MONTH_TO_EN = {
    "января": "January",
    "февраля": "February",
    "марта": "March",
    "апреля": "April",
    "мая": "May",
    "июня": "June",
    "июля": "July",
    "августа": "August",
    "сентября": "September",
    "октября": "October",
    "ноября": "November",
    "декабря": "December",
    "январь": "January",
    "февраль": "February",
    "март": "March",
    "апрель": "April",
    "май": "May",
    "июнь": "June",
    "июль": "July",
    "август": "August",
    "сентябрь": "September",
    "октябрь": "October",
    "ноябрь": "November",
    "декабрь": "December",
}


def localize_reference_period(
    period: str | None,
    *,
    locale: Locale | None = None,
) -> str | None:
    """Translate Russian month tokens in calendar ``reference_period`` (e.g. «июль 2026»)."""
    if not period:
        return period
    loc = locale or get_locale()
    if loc != "en":
        return period
    out = period
    for ru, en in sorted(_RU_MONTH_TO_EN.items(), key=lambda kv: len(kv[0]), reverse=True):
        if ru in out.lower():
            # Case-insensitive replace preserving surrounding text.
            import re

            out = re.sub(re.escape(ru), en, out, flags=re.IGNORECASE)
    return out


def indicator_copy_en(code: str) -> dict | None:
    """Raw EN overlay for a macro indicator code, or None."""
    return INDICATOR_COPY_EN.get(code)


def public_indicator_fields(
    code: str,
    *,
    name_ru: str | None,
    name_en: str | None = None,
    description_ru: str | None = None,
    methodology_ru: str | None = None,
    unit_ru: str | None = None,
    locale: Locale | None = None,
) -> dict[str, str | None]:
    """Locale-facing name/description/methodology/unit for API/SSR."""
    from app.services.i18n_display import public_name

    loc = locale or get_locale()
    overlay = INDICATOR_COPY_EN.get(code) if loc == "en" else None
    name = public_name(
        name_ru,
        (overlay or {}).get("name") or name_en,
        locale=loc,
    )
    if loc == "en" and overlay:
        from app.services.display import localize_unit

        return {
            "name": name,
            "description": overlay.get("description") or description_ru,
            "methodology": overlay.get("methodology") or methodology_ru,
            "unit": overlay.get("unit") or localize_unit(unit_ru, locale="en") or unit_ru,
        }
    if loc == "en":
        from app.services.display import localize_unit

        return {
            "name": name,
            "description": description_ru,
            "methodology": methodology_ru,
            "unit": localize_unit(unit_ru, locale="en") or unit_ru,
        }
    return {
        "name": name,
        "description": description_ru,
        "methodology": methodology_ru,
        "unit": unit_ru,
    }


def indicator_template(key: str, locale: Locale | None = None) -> str | None:
    loc = locale or get_locale()
    if loc != "en":
        return None
    return INDICATOR_TEMPLATES_EN.get(key)


def year_template(key: str, locale: Locale | None = None) -> str | None:
    """EN twin for annual landing fragments. Missing key → None (RU)."""
    loc = locale or get_locale()
    if loc != "en":
        return None
    return YEAR_TEMPLATES_EN.get(key)


def translate_source(source: str | None, locale: Locale | None = None) -> str | None:
    """Locale-facing publisher name (Rosstat / Bank of Russia / …)."""
    if not source:
        return source
    loc = locale or get_locale()
    if loc != "en":
        return source
    exact = GLOSSARY_EN.get(source)
    if exact:
        return exact
    # Longest-first so «Минфин России» wins over bare «Минфин».
    for ru, en in sorted(GLOSSARY_EN.items(), key=lambda kv: len(kv[0]), reverse=True):
        if ru in source:
            return source.replace(ru, en)
    return source


def localize_territory_fact(payload: dict | None, locale: Locale | None = None) -> dict | None:
    """EN twin for area/population API fragments (unit + source)."""
    if not payload:
        return payload
    loc = locale or get_locale()
    if loc != "en":
        return payload
    from app.services.display import localize_unit

    out = dict(payload)
    unit = out.get("unit")
    if unit:
        out["unit"] = localize_unit(unit, locale="en") or unit
    src = out.get("source")
    if src:
        out["source"] = translate_source(src, "en") or src
    return out


def localize_view_mode_label(label: str | None, locale: Locale | None = None) -> str | None:
    if not label:
        return label
    loc = locale or get_locale()
    if loc != "en":
        return label
    return _VIEW_MODE_LABEL_EN.get(label, label)


def localize_hero_label(label: str | None, locale: Locale | None = None) -> str | None:
    if not label:
        return label
    loc = locale or get_locale()
    if loc != "en":
        return label
    return _HERO_LABEL_EN.get(label, localize_view_mode_label(label, loc))


def frequency_label_en(frequency: str | None) -> str:
    key = {
        "daily": "freq_daily",
        "weekly": "freq_weekly",
        "monthly": "freq_monthly",
        "quarterly": "freq_quarterly",
        "annual": "freq_annual",
    }.get(frequency or "", "")
    return INDICATOR_TEMPLATES_EN.get(key) or (frequency or "periodic")


def build_indicator_seo_blocks_en(
    *,
    name: str,
    description: str | None,
    methodology: str | None,
    source: str | None,
    frequency: str | None = None,
) -> list[dict[str, str]]:
    """Six-block EN FAQ from overlay description/methodology — not unique essays."""
    tpl = INDICATOR_TEMPLATES_EN
    src = translate_source(source, "en") or "the official publisher"
    freq = frequency_label_en(frequency)
    what = (description or "").strip() or (
        f"{name} is an official macroeconomic series published for Russia."
    )
    method = (methodology or "").strip() or tpl["methodology_fallback"]
    return [
        {"title": tpl["block_what"], "body": what},
        {"title": tpl["block_why"], "body": tpl["block_why_body"].format(name=name)},
        {"title": tpl["block_read"], "body": tpl["block_read_body"]},
        {
            "title": tpl["block_freq"],
            "body": tpl["block_freq_body"].format(frequency=freq),
        },
        {"title": tpl["block_method"], "body": method},
        {
            "title": tpl["block_source"],
            "body": tpl["block_source_body"].format(source=src),
        },
    ]


def public_indicator_seo(
    code: str,
    *,
    name_ru: str | None,
    name_en: str | None = None,
    description_ru: str | None = None,
    methodology_ru: str | None = None,
    unit_ru: str | None = None,
    source_ru: str | None = None,
    seo_title_ru: str | None = None,
    seo_description_ru: str | None = None,
    seo_blocks_ru: list | None = None,
    frequency: str | None = None,
    locale: Locale | None = None,
) -> dict:
    """Full locale overlay for indicator card API + SSR (title, blocks, source)."""
    loc = locale or get_locale()
    fields = public_indicator_fields(
        code,
        name_ru=name_ru,
        name_en=name_en,
        description_ru=description_ru,
        methodology_ru=methodology_ru,
        unit_ru=unit_ru,
        locale=loc,
    )
    name = fields["name"] or name_ru or code
    source = translate_source(source_ru, loc)
    if loc != "en":
        return {
            **fields,
            "source": source_ru,
            "seo_title": seo_title_ru,
            "seo_description": seo_description_ru,
            "seo_blocks": seo_blocks_ru,
        }

    tpl = INDICATOR_TEMPLATES_EN
    seo_title = tpl["title"].format(name=name)
    # Never fall through to Russian seo_description_ru (may carry
    # «Актуальное значение» / «за N квартал» onto EN pages).
    en_desc = (fields.get("description") or "").strip()
    if en_desc and any(ch in en_desc for ch in "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя"):
        # Overlay missing: description_ru leaked via public_indicator_fields.
        en_desc = ""
    seo_description = en_desc or tpl["description_fallback"].format(name=name)
    # Never ship Russian FAQ bodies on EN — always template from EN copy.
    seo_blocks = build_indicator_seo_blocks_en(
        name=name,
        description=fields["description"],
        methodology=fields["methodology"],
        source=source_ru,
        frequency=frequency,
    )
    return {
        **fields,
        "source": source,
        "seo_title": seo_title,
        "seo_description": seo_description,
        "seo_blocks": seo_blocks,
    }


def localize_mode_display_suffix(
    family,
    resolved_mode,
    *,
    locale: Locale | None = None,
) -> str | None:
    """EN twin of ``mode_display_suffix`` using localized group/mode labels."""
    from app.data.view_model_families import mode_display_suffix

    loc = locale or get_locale()
    if loc != "en":
        return mode_display_suffix(family, resolved_mode)
    if resolved_mode.mode == family.default_mode:
        return None
    group = next((g for g in family.groups if g.id == resolved_mode.group), None)
    if not group:
        return localize_view_mode_label(resolved_mode.label, loc)
    g_label = localize_view_mode_label(group.label, loc) or group.label
    if group.leaf:
        return g_label
    m_label = localize_view_mode_label(resolved_mode.label, loc) or resolved_mode.label
    return f"{g_label}, {m_label}"


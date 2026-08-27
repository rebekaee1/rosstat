"""301-карта легаси-URL (А-2/А-3, Волна 4.5 CTO-аудита + ADR-0013 path-cut).

Одна точка истины для серверных редиректов SSR-слоя. Робот Яндекса продолжает
обходить URL, которых больше нет (переименованные коды, старые слаги регионов,
unlisted sibling-ряды из старых sitemap) — каждый 404 по ранее известному URL
минусует траст домена, 301 передаёт накопленный вес каноническому адресу.

Инвариант path-cut: каждый резолвер возвращает **уже финальный** путь
(`site_paths`), не старый канон. Иначе цепочка legacy → старый → новый.

Четыре источника редиректов:
1. `LEGACY_INDICATOR_REDIRECTS` — переименованные/удалённые коды из выгрузок
   Вебмастера (06.07.2026): точечная ручная карта.
2. `resolve_unlisted_indicator()` — unlisted sibling generic-семьи → канонический
   `/russia/indicator/{base}?mode={mode}` (данные те же, карточка одна). Плюс
   bespoke легаси-ряды (unemployment-*, *-yoy-abs), которых нет в generic-реестре.
3. `LEGACY_REGION_SLUG_PREFIXES` — старые короткие слаги регионов
   («tatarstan» → «respublika-tatarstan»): проверяется в SSR-роуте по БД.
4. `resolve_world_frequency_sibling()` — квартальный/годовой близнец мировой
   карточки → `/{slug}/indicator/{primary}?mode=level-{freq}` (частота в query).
"""

from __future__ import annotations

import re
from functools import lru_cache

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import site_paths as paths

# Переименованные/исчезнувшие коды (подтверждено выгрузкой Вебмастера).
LEGACY_INDICATOR_REDIRECTS: dict[str, str] = {
    "inflation": paths.russia_indicator("cpi"),
    "gasoline-ai92": paths.russia_indicator("fuel-ai92"),
    "gasoline-ai95": paths.russia_indicator("fuel-ai95"),
    "gdp-deflator": paths.russia_indicator("gdp-nominal"),
    "refinancing-rate": paths.russia_indicator("key-rate"),
    # Сталь снята с витрины: свободного официального ряда котировок нет,
    # держать мёртвый ряд с биржевого агрегатора нельзя. URL были в sitemap.
    "steel": paths.russia_category("commodities"),
}

# Bespoke-ряды вне generic-реестра, державшиеся только на клиентском
# canonical-редиректе (ЭСКАЛАЦИЯ-зона AGENTS.md: их SSR-404 = тихая просадка).
_BESPOKE_UNLISTED_CANONICAL: dict[str, str] = {
    "unemployment-quarterly": f"{paths.russia_indicator('unemployment')}?mode=quarterly",
    "unemployment-annual": f"{paths.russia_indicator('unemployment')}?mode=annual",
    "trade-balance-yoy-abs": f"{paths.russia_indicator('trade-balance')}?mode=yoy_abs",
    "current-account-yoy-abs": f"{paths.russia_indicator('current-account')}?mode=yoy_abs",
    # ИЦП: bespoke-режимы карточки /russia/indicator/ppi?mode=… (ppiViewMode*).
    "ppi-yoy": f"{paths.russia_indicator('ppi')}?mode=yoy",
    "ppi-qoq": f"{paths.russia_indicator('ppi')}?mode=qoq",
    "ppi-mom": f"{paths.russia_indicator('ppi')}?mode=mom",
    "ppi-annual": f"{paths.russia_indicator('ppi')}?mode=annual",
}

# Суффиксы sibling-рядов generic-семей: длинные раньше коротких, иначе
# «-yoy-year» срежется как «-yoy» и база получится с хвостом «-year».
_SIBLING_SUFFIXES: tuple[str, ...] = (
    "-avg-week", "-eop-week", "-avg-month", "-eop-month",
    "-avg-quarter", "-eop-quarter", "-avg-year", "-eop-year",
    "-yoy-quarter", "-yoy-year", "-mom", "-qoq", "-yoy",
)

# Старые короткие слаги регионов: пробуем канонический с префиксом.
LEGACY_REGION_SLUG_PREFIXES = ("respublika-",)

_WORLD_FREQ_SUFFIX_RE = re.compile(
    r"(?:"
    r",\s*(помесячно|поквартально|за год|понедельно|по дням)"
    r"|"
    r"\s*[-–—]\s*(monthly|quarterly|annual|yearly|weekly|daily)\s+data"
    r")\s*$",
    re.I,
)
_WORLD_FREQ_RANK = {
    "monthly": 0,
    "quarterly": 1,
    "annual": 2,
    "weekly": 3,
    "daily": 4,
}


@lru_cache(maxsize=1)
def _generic_sibling_index() -> dict[str, str]:
    """code sibling-ряда → канонический путь семьи (ленивая сборка из FAMILIES)."""
    from app.data.view_model_families import FAMILIES

    index: dict[str, str] = {}
    for fam in FAMILIES:
        for mode in fam.modes:
            if mode.code != fam.base:
                index[mode.code] = f"{paths.russia_indicator(fam.base)}?mode={mode.mode}"
    return index


def resolve_legacy_indicator(code: str) -> str | None:
    """Целевой путь 301 для легаси-кода карточки, или None."""
    return LEGACY_INDICATOR_REDIRECTS.get(code)


def resolve_unlisted_indicator(code: str) -> str | None:
    """Канонический путь для unlisted sibling-ряда (generic или bespoke)."""
    return (
        _BESPOKE_UNLISTED_CANONICAL.get(code)
        or _generic_sibling_index().get(code)
        or _resolve_retired_sibling(code)
    )


def _resolve_retired_sibling(code: str) -> str | None:
    """Sibling, исчезнувший при смене семьи ряда (дневная → месячная и т.п.).

    Такие URL годами были в sitemap: недельные и месячные срезы меди, угля,
    зерна пережили перевод базовых рядов на месячную сводку. Ведём их на живую
    карточку базы, а не в 404.
    """
    from app.data.view_model_families import FAMILIES

    for suffix in _SIBLING_SUFFIXES:
        if not code.endswith(suffix):
            continue
        base = code[: -len(suffix)]
        if any(fam.base == base for fam in FAMILIES):
            return paths.russia_indicator(base)
        retired = LEGACY_INDICATOR_REDIRECTS.get(base)
        if retired:
            return retired
    return None


def strip_world_frequency_suffix(name: str | None) -> str:
    """Убрать суффикс частоты из публичного имени мировой карточки."""
    if not name:
        return ""
    return _WORLD_FREQ_SUFFIX_RE.sub("", name).strip()


def world_card_primary_rank(ind) -> tuple:
    """Меньше = лучше primary: месячный глубже квартального/годового."""
    from app.data.eurostat_listing import normalize_frequency

    freq = normalize_frequency(getattr(ind, "frequency", None))
    return (
        _WORLD_FREQ_RANK.get(freq, 9),
        -int(getattr(ind, "points_count", 0) or 0),
        getattr(ind, "code", "") or "",
    )


async def world_card_siblings(db: AsyncSession, indicator) -> list:
    """Все ряды той же карточки (card_key без frequency)."""
    from app.data.eurostat_listing import card_key, dataset_stem
    from app.models import WorldIndicator

    stem = dataset_stem(indicator.dataset_id)
    if not stem:
        return [indicator]
    key = card_key(
        country_id=indicator.country_id,
        dataset_id=indicator.dataset_id,
        unit=indicator.unit,
        unit_ru=indicator.unit_ru,
        slice_json=indicator.slice_json,
    )
    rows = (
        await db.execute(
            select(WorldIndicator).where(
                WorldIndicator.country_id == indicator.country_id,
                WorldIndicator.provider == indicator.provider,
                or_(
                    WorldIndicator.dataset_id == stem,
                    WorldIndicator.dataset_id.like(f"{stem}_%"),
                ),
            )
        )
    ).scalars().all()
    siblings = [
        r for r in rows
        if card_key(
            country_id=r.country_id,
            dataset_id=r.dataset_id,
            unit=r.unit,
            unit_ru=r.unit_ru,
            slice_json=r.slice_json,
        ) == key
    ]
    return siblings or [indicator]


async def resolve_world_frequency_sibling(
    db: AsyncSession, slug: str, code: str
) -> str | None:
    """Вторичная частота мировой карточки → 301 на primary?mode=level-{freq}.

    Тот же механизм, что `resolve_unlisted_indicator` для России: один
    канонический URL на показатель, частота в query.
    """
    from app.data.eurostat_listing import normalize_frequency
    from app.models import WorldCountry, WorldIndicator

    country = (
        await db.execute(
            select(WorldCountry).where(
                WorldCountry.slug == slug,
                WorldCountry.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if country is None:
        return None

    indicator = (
        await db.execute(
            select(WorldIndicator).where(
                WorldIndicator.country_id == country.id,
                WorldIndicator.code == code,
            )
        )
    ).scalar_one_or_none()
    if indicator is None:
        return None

    siblings = await world_card_siblings(db, indicator)
    if len(siblings) < 2:
        return None

    primary = min(siblings, key=world_card_primary_rank)
    # Unlisted/нулевой primary — не 301 ни на мёртвую карточку, ни на /world/{slug}.
    if not getattr(primary, "is_listed", False):
        return None
    if primary.code == indicator.code:
        return None

    freq = normalize_frequency(indicator.frequency) or "monthly"
    if freq not in ("monthly", "quarterly", "annual"):
        freq = "monthly"
    return f"{paths.indicator(slug, primary.code)}?mode=level-{freq}"


async def resolve_world_unlisted_indicator(
    db: AsyncSession, slug: str, code: str
) -> str | None:
    """Пустой/нулевой unlisted ряд → 301 на страницу страны.

    Срезы с реальным сигналом остаются открытыми (variant-пикер), даже если
    ``is_listed=false`` и они не в каталоге страны.
    """
    from sqlalchemy import select as sa_select

    from app.models import WorldCountry, WorldDataPoint, WorldIndicator

    country = (
        await db.execute(
            select(WorldCountry).where(
                WorldCountry.slug == slug,
                WorldCountry.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if country is None:
        return None

    indicator = (
        await db.execute(
            select(WorldIndicator).where(
                WorldIndicator.country_id == country.id,
                WorldIndicator.code == code,
            )
        )
    ).scalar_one_or_none()
    if indicator is None:
        return None

    siblings = await world_card_siblings(db, indicator)
    primary = min(siblings, key=world_card_primary_rank)
    if getattr(primary, "is_listed", False):
        return None

    has_signal = (
        await db.execute(
            sa_select(WorldDataPoint.indicator_id)
            .where(
                WorldDataPoint.indicator_id.in_([indicator.id, primary.id]),
                WorldDataPoint.value != 0,
            )
            .limit(1)
        )
    ).first()
    if has_signal is not None:
        return None
    return paths.country(slug)

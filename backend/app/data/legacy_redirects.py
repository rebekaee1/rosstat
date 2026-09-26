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
   Фолбэк — ряд, слитый в карточку каталога (`catalog_merge_key`: темпы ГИПЦ
   manr/mmor/mv12r, среднегодовой aind) и снятый с листинга →
   `?mode={yoy|step|level}-{freq}` по мере ряда (2026-09-20).
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
    # T9s канон «Г/г» — mode=yoy (abs-pipeline), не устаревший yoy_abs.
    "trade-balance-yoy-abs": f"{paths.russia_indicator('trade-balance')}?mode=yoy",
    "current-account-yoy-abs": f"{paths.russia_indicator('current-account')}?mode=yoy",
    # Bespoke ИПЦ / жильё: derived-URL → карточка parent + режим.
    "inflation-weekly": f"{paths.russia_indicator('cpi')}?mode=step-weekly",
    "inflation-annual": f"{paths.russia_indicator('cpi')}?mode=yoy",
    "inflation-quarterly": f"{paths.russia_indicator('cpi')}?mode=index-quarterly",
    "inflation-weekly-food": paths.russia_indicator("cpi-food"),
    "inflation-weekly-nonfood": paths.russia_indicator("cpi-nonfood"),
    "inflation-weekly-services": paths.russia_indicator("cpi-services"),
    "housing-yoy-primary": f"{paths.russia_indicator('housing-price-primary')}?mode=yoy",
    "housing-yoy-secondary": f"{paths.russia_indicator('housing-price-secondary')}?mode=yoy",
    "housing-qoq-primary": f"{paths.russia_indicator('housing-price-primary')}?mode=qoq",
    "housing-qoq-secondary": f"{paths.russia_indicator('housing-price-secondary')}?mode=qoq",
    "housing-annual-primary": f"{paths.russia_indicator('housing-price-primary')}?mode=yoy-annual",
    "housing-annual-secondary": f"{paths.russia_indicator('housing-price-secondary')}?mode=yoy-annual",
    # ИЦП: bespoke-режимы карточки /russia/indicator/ppi?mode=… (ppiViewMode*).
    "ppi-yoy": f"{paths.russia_indicator('ppi')}?mode=yoy",
    "ppi-qoq": f"{paths.russia_indicator('ppi')}?mode=qoq",
    "ppi-mom": f"{paths.russia_indicator('ppi')}?mode=mom",
    "ppi-annual": f"{paths.russia_indicator('ppi')}?mode=annual",
    # Недельный ИПЦ-сиблинг bespoke CPI-семьи (не в generic-реестре): URL
    # был подан в IndexNow из локального стека до отката прода (2026-08-30).
    "cpi-period-weekly": f"{paths.russia_indicator('cpi')}?mode=period-weekly",
    "cpi-food-period-weekly": f"{paths.russia_indicator('cpi-food')}?mode=period-weekly",
    "cpi-nonfood-period-weekly": f"{paths.russia_indicator('cpi-nonfood')}?mode=period-weekly",
    "cpi-services-period-weekly": f"{paths.russia_indicator('cpi-services')}?mode=period-weekly",
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


def bespoke_mode_data_code(parent: str, mode: str | None) -> str | None:
    """Ряд, который показывает bespoke-режим карточки (?mode=…).

    Обратная сторона _BESPOKE_UNLISTED_CANONICAL: /ppi-yoy → 301 ppi?mode=yoy,
    значит видимое тело ppi?mode=yoy — данные ppi-yoy (г/г %), а не уровень
    индекса. Только точные пары (parent, mode) из таблицы редиректов.
    """
    if not mode:
        return None
    return _bespoke_mode_index().get((parent, mode))


@lru_cache(maxsize=1)
def _bespoke_mode_index() -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    for sibling, target in _BESPOKE_UNLISTED_CANONICAL.items():
        path, _, query = target.partition("?mode=")
        if not query:
            continue
        parent = path.rstrip("/").rsplit("/", 1)[-1]
        out.setdefault((parent, query), sibling)
    return out


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


def _like_escape(value: str) -> str:
    """Литерал для LIKE с ESCAPE '\\': `\\`, `%`, `_` перестают быть спецсимволами."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _request_memo(db) -> dict | None:
    """Per-request memo на сессии (perf batch 2).

    SSR мировой карточки раньше грузил страну, ряд и соседей по карточке до
    трёх раз за запрос (резолвер частот, блок частот, рендер). Сессия живёт
    ровно один запрос (get_db), поэтому ``session.info`` — естественная
    область кэша; у тестовых заглушек без ``info`` memo просто выключен.
    """
    info = getattr(db, "info", None)
    if not isinstance(info, dict):
        return None
    return info.setdefault("fe_world_memo", {})


async def world_country_by_slug(db: AsyncSession, slug: str):
    """Активная страна по слагу (memo на запрос)."""
    from app.models import WorldCountry

    memo = _request_memo(db)
    key = ("country", slug)
    if memo is not None and key in memo:
        return memo[key]
    country = (
        await db.execute(
            select(WorldCountry).where(
                WorldCountry.slug == slug,
                WorldCountry.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if memo is not None:
        memo[key] = country
    return country


async def world_indicator_by_code(db: AsyncSession, country_id: int, code: str):
    """Ряд страны по коду (memo на запрос; полная строка — рендеру нужны тексты)."""
    from app.models import WorldIndicator

    memo = _request_memo(db)
    key = ("indicator", country_id, code)
    if memo is not None and key in memo:
        return memo[key]
    indicator = (
        await db.execute(
            select(WorldIndicator).where(
                WorldIndicator.country_id == country_id,
                WorldIndicator.code == code,
            )
        )
    ).scalar_one_or_none()
    if memo is not None:
        memo[key] = indicator
    return indicator


async def world_card_siblings(db: AsyncSession, indicator) -> list:
    """Все ряды той же карточки (card_key без frequency)."""
    from app.data.eurostat_listing import card_key, dataset_stem
    from app.models import WorldIndicator

    stem = dataset_stem(indicator.dataset_id)
    if not stem:
        return [indicator]
    memo = _request_memo(db)
    memo_key = ("siblings", getattr(indicator, "id", None))
    if memo is not None and memo_key[1] is not None and memo_key in memo:
        return list(memo[memo_key])
    key = card_key(
        country_id=indicator.country_id,
        dataset_id=indicator.dataset_id,
        unit=indicator.unit,
        unit_ru=indicator.unit_ru,
        slice_json=indicator.slice_json,
    )
    # `_` в stem (ei_bsco) для LIKE — одиночный wildcard: без экранирования
    # префикс индекса схлопывался до «ei», и планировщик читал сотни широких
    # строк вместо ~14. Экранируем и stem, и разделитель частоты.
    like_prefix = _like_escape(stem) + "\\_%"
    rows = (
        await db.execute(
            select(WorldIndicator)
            .options(*_light_world_indicator_options())
            .where(
                WorldIndicator.country_id == indicator.country_id,
                WorldIndicator.provider == indicator.provider,
                or_(
                    WorldIndicator.dataset_id == stem,
                    WorldIndicator.dataset_id.like(like_prefix, escape="\\"),
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
    result = siblings or [indicator]
    if memo is not None and memo_key[1] is not None:
        memo[memo_key] = list(result)
    return result


def _light_world_indicator_options() -> list:
    """Соседям карточки нужны ключ/частота/код — не SEO-тексты (defer).

    Объекты, уже загруженные целиком в этой сессии (сам ряд), identity map
    отдаёт как есть; отложенные колонки дочитываются только явным запросом.
    """
    from sqlalchemy.orm import defer

    from app.models import WorldIndicator

    return [
        defer(getattr(WorldIndicator, name), raiseload=True)
        for name in (
            "description", "methodology", "seo_title", "seo_description", "seo_keywords",
        )
    ]


async def resolve_world_frequency_sibling(
    db: AsyncSession, slug: str, code: str
) -> str | None:
    """Вторичная частота мировой карточки → 301 на primary?mode=level-{freq}.

    Тот же механизм, что `resolve_unlisted_indicator` для России: один
    канонический URL на показатель, частота в query.
    """
    country = await world_country_by_slug(db, slug)
    if country is None:
        return None

    indicator = await world_indicator_by_code(db, country.id, code)
    if indicator is None:
        return None

    siblings = await world_card_siblings(db, indicator)
    if len(siblings) >= 2:
        primary = min(siblings, key=world_card_primary_rank)
        # Unlisted/нулевой primary — не 301 ни на мёртвую карточку, ни на /world/{slug}.
        if not getattr(primary, "is_listed", False):
            return None
        if primary.code == indicator.code:
            return None
        return f"{paths.indicator(slug, primary.code)}?mode=level-{_mode_freq(indicator)}"

    return await _resolve_world_catalog_merge(db, slug, indicator)


def _mode_freq(indicator) -> str:
    from app.data.eurostat_listing import normalize_frequency

    freq = normalize_frequency(indicator.frequency) or "monthly"
    return freq if freq in ("monthly", "quarterly", "annual") else "monthly"


def is_retired_world_hicp(slug: str, code: str) -> bool:
    """Only the retired 2015-base headline HICP index, never HICP rates."""
    return bool(re.fullmatch(r"[a-z]{2}-prc_hicp_midx-cp00-i15", code))


async def resolve_world_hicp_successor(
    db: AsyncSession, slug: str, code: str, year: int | None = None,
) -> str | None:
    """Redirect an old HICP index URL when the same 2015-base index exists."""
    if not is_retired_world_hicp(slug, code):
        return None
    from app.models import WorldCountry, WorldDataPoint, WorldIndicator
    from sqlalchemy import func

    old = (
        await db.execute(
            select(WorldIndicator).join(WorldCountry).where(
                WorldCountry.slug == slug,
                WorldIndicator.code == code,
                WorldIndicator.dataset_id == "prc_hicp_midx",
            )
        )
    ).scalar_one_or_none()
    if old is None:
        return None
    successor_code = code.replace("-prc_hicp_midx-cp00-i15", "-prc_hicp_minr-total-i15")
    successor = (
        await db.execute(
            select(WorldIndicator).where(
                WorldIndicator.country_id == old.country_id,
                WorldIndicator.code == successor_code,
                WorldIndicator.dataset_id == "prc_hicp_minr",
                WorldIndicator.is_listed.is_(True),
            )
        )
    ).scalar_one_or_none()
    if successor is None:
        return None
    if year is not None:
        has_year = (
            await db.execute(
                select(WorldDataPoint.id).where(
                    WorldDataPoint.indicator_id == successor.id,
                    func.extract("year", WorldDataPoint.date) == year,
                ).limit(1)
            )
        ).scalar_one_or_none()
        if has_year is None:
            return None
        return paths.indicator_year(slug, successor_code, year)
    return paths.indicator(slug, successor_code)


# Мера снятого с листинга ряда → тип режима слитой карточки. Темп к
# аналогичному периоду прошлого года (RCH_A, PCH_SM/SAME, скользящий 12-мес.)
# → yoy; темп к предыдущему периоду (RCH_M, RT1, PCH_PRE, RT_M_DIF) → step.
_MERGE_MODE_TYPE_BY_UNIT: dict[str, str] = {
    "RCH_A": "yoy", "PCH_SM": "yoy", "PCH_SAME": "yoy", "RCH_MV12MAVR": "yoy",
    "RCH_A_AVG": "yoy",
    "RCH_M": "step", "RT1": "step", "RT1_SCA": "step", "PCH_PRE": "step",
    "RT_M_DIF": "step",
}


async def _resolve_world_catalog_merge(
    db: AsyncSession, slug: str, indicator
) -> str | None:
    """Ряд, слитый в карточку каталога (ГИПЦ индекс + темпы, ooq/ooa) → 301.

    После склейки (`catalog_merge_key`) темп ГИПЦ снят с листинга и в SSR
    отдаёт 404, хотя тот же ряд живёт в матрице режимов primary-карточки.
    Отправляем на listed primary группы с режимом по мере: RCH_A →
    `yoy-{freq}`, RCH_M → `step-{freq}`, индекс → `level-{freq}`.
    """
    from app.data.eurostat_listing import (
        catalog_merge_key,
        catalog_stem_alias,
        measure_preference_rank,
    )
    from app.models import WorldIndicator

    if getattr(indicator, "is_listed", False):
        return None
    alias = catalog_stem_alias(indicator.dataset_id)
    if not alias:
        return None

    def _mkey(ind) -> tuple:
        return catalog_merge_key(
            country_id=ind.country_id,
            provider=getattr(ind, "provider", None),
            dataset_id=ind.dataset_id,
            unit=ind.unit,
            unit_ru=ind.unit_ru,
            slice_json=ind.slice_json,
        )

    key = _mkey(indicator)
    conds = []
    for stem in alias.split("|"):
        conds.append(WorldIndicator.dataset_id == stem)
        conds.append(WorldIndicator.dataset_id.like(_like_escape(stem) + "%", escape="\\"))
    rows = (
        await db.execute(
            select(WorldIndicator).where(
                WorldIndicator.country_id == indicator.country_id,
                WorldIndicator.provider == indicator.provider,
                WorldIndicator.is_listed.is_(True),
                WorldIndicator.points_count > 0,
                or_(*conds),
            )
        )
    ).scalars().all()
    members = [r for r in rows if r.code != indicator.code and _mkey(r) == key]
    if not members:
        return None
    primary = min(members, key=measure_preference_rank)
    unit = (indicator.unit or "").strip().upper().replace("-", "_")
    mode_type = _MERGE_MODE_TYPE_BY_UNIT.get(unit, "level")
    return f"{paths.indicator(slug, primary.code)}?mode={mode_type}-{_mode_freq(indicator)}"


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

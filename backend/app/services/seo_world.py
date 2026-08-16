"""SSR-рендер раздела «Мировая экономика»: /world, /{slug}, /{slug}/indicator/{code}.

По образцу seo_regional.py (ADR-0003): видимый контент + meta + JSON-LD +
картинка-график тремя путями (og:image, ImageObject, <img class="seo-chart">).
Прогнозов нет. Публичный источник — «Евростат» для eurostat-рядов либо
русское имя национального ведомства/ЦБ (Banxico → «Банк Мексики» и т.п.).
Внутренние идентификаторы наборов и технический жаргон наружу не выдаём.
"""

from __future__ import annotations

from app.services import breadcrumbs as crumbs
from app.services import site_paths as paths

from datetime import date
from html import escape

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.eurostat_titles_ru import country_prepositional
from app.data.eurostat_units_ru import unit_suffix
from app.data.legacy_redirects import (
    strip_world_frequency_suffix,
    world_card_primary_rank,
    world_card_siblings,
)
from app.data.world_concept_national import national_codes_for_concept
from app.data.world_concepts import CONCEPT_BY_SLUG, WORLD_CONCEPTS, WorldConcept, concept_for_indicator
from app.models import WorldCountry, WorldDataPoint, WorldIndicator
from app.services.display import format_date_ru, format_month_ru, format_number_ru
from app.services.seo_renderer import DOMAIN, _breadcrumbs, _breadcrumbs_nav, build_document
from app.services.world_rank_values import (
    money_unit_compatible,
    ranking_display_name,
    ranking_period_method,
    ranking_public_unit,
    ranking_value_mode,
    resolve_default_coverage_year,
    world_rating_title,
    WORLD_RATING_QUERY_NAMES,
    yearly_last_points,
)
from app.services.world_russia_rank import (
    merge_russia_into_values_by_year,
    russia_country_public,
    russia_meta_for_concept,
)

_SOURCE_PUBLIC = "Евростат"
WORLD_RATING_DEFAULT_CONCEPT = "unemployment-rate"
_WORLD_RATING_LOW_FIRST = frozenset({"unemployment-rate", "long-term-interest-rate"})
_WORLD_RATING_MONEY_CONCEPTS = frozenset({"gdp-volume-quarterly", "gdp-volume-annual"})

# Публичные константы хаба /world — зеркалятся в pageMeta.generated.json (ADR-0003).
WORLD_HOME_TITLE = "Мировая экономика — статистика по странам"
WORLD_HOME_DESC = (
    "Официальная статистика по странам: цены, ВВП, рынок труда, торговля и "
    "финансы. Графики и таблицы по данным Евростата, национальных "
    "статистических ведомств и центральных банков."
)
WORLD_HOME_H1 = "Мировая экономика: статистика по странам"

# Родительный падеж для заголовков «Экономика {страны}».
# Nominative в БД (name_ru); для публичных фраз нужен genitive.
COUNTRY_GENITIVE: dict[str, str] = {
    "austria": "Австрии",
    "belgium": "Бельгии",
    "bulgaria": "Болгарии",
    "croatia": "Хорватии",
    "cyprus": "Кипра",
    "czechia": "Чехии",
    "denmark": "Дании",
    "estonia": "Эстонии",
    "finland": "Финляндии",
    "france": "Франции",
    "germany": "Германии",
    "greece": "Греции",
    "hungary": "Венгрии",
    "ireland": "Ирландии",
    "italy": "Италии",
    "latvia": "Латвии",
    "lithuania": "Литвы",
    "luxembourg": "Люксембурга",
    "malta": "Мальты",
    "netherlands": "Нидерландов",
    "poland": "Польши",
    "portugal": "Португалии",
    "romania": "Румынии",
    "slovakia": "Словакии",
    "slovenia": "Словении",
    "spain": "Испании",
    "sweden": "Швеции",
    "iceland": "Исландии",
    "norway": "Норвегии",
    "switzerland": "Швейцарии",
    "united-kingdom": "Великобритании",
    "turkey": "Турции",
    "serbia": "Сербии",
    "montenegro": "Черногории",
    "north-macedonia": "Северной Македонии",
    "albania": "Албании",
    "bosnia": "Боснии и Герцеговины",
    "kosovo": "Косово",
    "ukraine": "Украины",
    "moldova": "Молдовы",
    "georgia": "Грузии",
    "armenia": "Армении",
    "azerbaijan": "Азербайджана",
    "united-states": "США",
    "canada": "Канады",
    "japan": "Японии",
    "south-korea": "Южной Кореи",
    "china": "Китая",
    "india": "Индии",
    "brazil": "Бразилии",
    "mexico": "Мексики",
    "australia": "Австралии",
    "new-zealand": "Новой Зеландии",
    "south-africa": "ЮАР",
    "israel": "Израиля",
}


def _genitive(country: WorldCountry) -> str:
    return COUNTRY_GENITIVE.get(country.slug, country.name_ru)


def _prep(country: WorldCountry) -> str:
    return country_prepositional(country.slug, country.name_ru)


def _n_indicators_phrase(n: int) -> str:
    """«1 показатель» / «22 показателя» / «105 показателей»."""
    n = abs(int(n))
    mod10, mod100 = n % 10, n % 100
    if mod10 == 1 and mod100 != 11:
        word = "показатель"
    elif mod10 in (2, 3, 4) and mod100 not in (12, 13, 14):
        word = "показателя"
    else:
        word = "показателей"
    return f"{n} {word}"


_FREQ_RU = {
    "monthly": "помесячно",
    "quarterly": "поквартально",
    "annual": "ежегодно",
    "daily": "ежедневно",
    "weekly": "еженедельно",
}

# Категории, которые поднимаем в «ключевые» на странице страны.
_KEY_CATEGORY_ORDER = (
    "Цены",
    "ВВП",
    "Рынок труда",
    "Финансы",
    "Торговля",
    "Бизнес",
    "Общество",
    "Товарные рынки",
)


def _display_name(ind: WorldIndicator) -> str:
    return strip_world_frequency_suffix(ind.name_ru) or ind.name_ru


def _pick_card_primaries(inds: list[WorldIndicator]) -> list[WorldIndicator]:
    """Одна карточка на card_key: только primary частоты."""
    from app.data.eurostat_listing import card_key

    buckets: dict[tuple, list[WorldIndicator]] = {}
    order: list[tuple] = []
    for ind in inds:
        key = card_key(
            country_id=ind.country_id,
            dataset_id=ind.dataset_id,
            unit=ind.unit,
            unit_ru=ind.unit_ru,
            slice_json=ind.slice_json,
        )
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(ind)
    out: list[WorldIndicator] = []
    for key in order:
        members = buckets[key]
        out.append(min(members, key=world_card_primary_rank))
    return out


_FREQ_LINK_LABEL = {
    "monthly": "по месяцам",
    "quarterly": "по кварталам",
    "annual": "по годам",
    "weekly": "по неделям",
    "daily": "по дням",
}


def _fmt(value: float | None) -> str:
    if value is None:
        return "—"
    return format_number_ru(value)


async def _frequency_links_html(
    db, slug: str, indicator: WorldIndicator
) -> str:
    from app.data.eurostat_listing import normalize_frequency

    siblings = await world_card_siblings(db, indicator)
    if len(siblings) < 2:
        freq = normalize_frequency(indicator.frequency)
        label = _FREQ_LINK_LABEL.get(freq or "", freq or "")
        if not label:
            return ""
        return (
            f'<section class="seo-section"><h2>Частота</h2>'
            f"<p>{escape(label.capitalize())}.</p></section>"
        )
    primary = min(siblings, key=world_card_primary_rank)
    links = []
    for sib in sorted(siblings, key=world_card_primary_rank):
        freq = normalize_frequency(sib.frequency) or "monthly"
        label = _FREQ_LINK_LABEL.get(freq, freq)
        href = f"{escape(paths.indicator(slug, primary.code))}?mode=level-{escape(freq)}"
        links.append(f'<li><a href="{href}">{escape(label.capitalize())}</a></li>')
    return (
        '<section class="seo-section"><h2>Частота наблюдений</h2>'
        f'<ul class="seo-pills">{"".join(links)}</ul></section>'
    )


def _unit_of(ind: WorldIndicator) -> str:
    return (ind.unit_ru or ind.unit or "").strip()


def _unit_sfx(unit: str) -> str:
    """Единица справа от числа: у безразмерных величин — ничего (не «12,4 индекс»).

    Возвращает plain text — экранировать на месте вставки в разметку.
    """
    sfx = unit_suffix(unit)
    return f" {sfx}" if sfx else ""


# Публичные имена национальных источников (provider → русский).
# Дублируем здесь, чтобы SSR не зависел от модуля national ingest.
_SOURCE_BY_PROVIDER: dict[str, str] = {
    "eurostat": _SOURCE_PUBLIC,
    "statcan": "Статистическое управление Канады",
    "boc_valet": "Банк Канады",
    "abs": "Австралийское бюро статистики",
    "rba": "Резервный банк Австралии",
    "ons": "Управление национальной статистики Великобритании",
    "boe_iadb": "Банк Англии",
    "fred": "Федеральный резервный банк Сент-Луиса",
    "bls": "Бюро трудовой статистики США",
    "bea": "Бюро экономического анализа США",
    "boj": "Банк Японии",
    "estat": "Статистическое бюро Японии",
    "ecos": "Банк Кореи",
    "bcb_sgs": "Банк Бразилии",
    "banxico_sie": "Банк Мексики",
    "nbs": "Национальное статистическое бюро Китая",
    "cfets": "Китайская система валютных торгов",
    "mospi": "Министерство статистики и программной реализации Индии",
    "rbi": "Резервный банк Индии",
}


def _source_label(raw: str | None, provider: str | None = None) -> str:
    """Публичное имя источника без латиницы/жаргона.

    Eurostat → «Евростат». Национальный provider → кириллическое имя ведомства.
    Иначе — кириллический ``source`` из БД.
    """
    prov = (provider or "").strip().lower()
    if prov:
        mapped = _SOURCE_BY_PROVIDER.get(prov)
        if mapped:
            return mapped
    if not raw:
        return _SOURCE_PUBLIC
    low = raw.strip().lower()
    if low in ("eurostat", "евростат"):
        return _SOURCE_PUBLIC
    # Уже русское публичное имя (национальный passport пишет кириллицу).
    if any("\u0400" <= ch <= "\u04FF" for ch in raw):
        return raw.strip()
    # Латиница без известного provider — не светим наружу.
    return _SOURCE_PUBLIC


def _join_sources_ru(labels: list[str]) -> str:
    """«A» / «A и B» / «A, B и C»."""
    uniq: list[str] = []
    seen: set[str] = set()
    for label in labels:
        text = (label or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        uniq.append(text)
    if not uniq:
        return _SOURCE_PUBLIC
    if len(uniq) == 1:
        return uniq[0]
    if len(uniq) == 2:
        return f"{uniq[0]} и {uniq[1]}"
    return f"{', '.join(uniq[:-1])} и {uniq[-1]}"


def _country_source_phrase(inds: list[WorldIndicator]) -> tuple[str, bool]:
    """(публичная фраза источников, True если есть non-eurostat ряды)."""
    labels = [
        _source_label(getattr(ind, "source", None), getattr(ind, "provider", None))
        for ind in inds
    ]
    has_national = any(
        (getattr(ind, "provider", None) or "").strip().lower() not in ("", "eurostat")
        for ind in inds
    )
    return _join_sources_ru(labels), has_national


def world_rating_default_sort(concept_slug: str) -> str:
    return "asc" if concept_slug in _WORLD_RATING_LOW_FIRST else "desc"


def _is_money_rating(concept: WorldConcept) -> bool:
    return concept.slug in _WORLD_RATING_MONEY_CONCEPTS


def _same_public_unit(indicator: WorldIndicator, concept: WorldConcept) -> bool:
    """Денежные рейтинги строятся только в одной уже опубликованной единице."""
    if not _is_money_rating(concept):
        return True
    return money_unit_compatible(concept.measure, indicator.unit, indicator.unit_ru)


def _concept_allowed_datasets(concept: WorldConcept) -> set[str]:
    allowed = {str(ds).lower() for ds in concept.dataset_ids}
    if concept.provider_dataset_ids:
        for ids in concept.provider_dataset_ids.values():
            allowed.update(str(ds).lower() for ds in ids)
    return allowed


async def _world_rating_countries(db: AsyncSession) -> list[WorldCountry]:
    counts_q = (
        select(
            WorldIndicator.country_id,
            func.count().label("cnt"),
        )
        .where(WorldIndicator.is_listed.is_(True))
        .group_by(WorldIndicator.country_id)
        .subquery()
    )
    rows = (
        await db.execute(
            select(WorldCountry, counts_q.c.cnt)
            .outerjoin(counts_q, WorldCountry.id == counts_q.c.country_id)
            .where(WorldCountry.is_active.is_(True))
            .order_by(WorldCountry.sort_order, WorldCountry.name_ru)
        )
    ).all()
    return [country for country, cnt in rows if int(cnt or 0) > 0]


async def _world_rating_members(
    db: AsyncSession,
    concept: WorldConcept,
) -> list[tuple[WorldCountry, WorldIndicator]]:
    """Одна страна — один сопоставимый ряд для рейтинга."""
    allowed = _concept_allowed_datasets(concept)
    national_codes = national_codes_for_concept(concept.slug)
    rows = (
        await db.execute(
            select(WorldCountry, WorldIndicator)
            .join(WorldIndicator, WorldIndicator.country_id == WorldCountry.id)
            .where(
                WorldCountry.is_active.is_(True),
                WorldIndicator.is_listed.is_(True),
                (
                    or_(
                        func.lower(WorldIndicator.dataset_id).in_(sorted(allowed)),
                        WorldIndicator.code.in_(sorted(national_codes)),
                    )
                    if national_codes
                    else func.lower(WorldIndicator.dataset_id).in_(sorted(allowed))
                ),
            )
            .order_by(WorldCountry.sort_order, WorldCountry.name_ru, WorldIndicator.code)
        )
    ).all()
    matched: list[tuple[WorldCountry, WorldIndicator]] = []
    for country, indicator in rows:
        if indicator.code in national_codes:
            if _same_public_unit(indicator, concept):
                matched.append((country, indicator))
            continue
        if concept_for_indicator(indicator) == concept and _same_public_unit(indicator, concept):
            matched.append((country, indicator))

    by_country: dict[int, tuple[WorldCountry, WorldIndicator]] = {}
    for country, indicator in matched:
        prev = by_country.get(country.id)
        if prev is None:
            by_country[country.id] = (country, indicator)
            continue
        prev_is_national = prev[1].code in national_codes
        cur_is_national = indicator.code in national_codes
        if cur_is_national and not prev_is_national:
            by_country[country.id] = (country, indicator)
        elif prev_is_national == cur_is_national:
            # Оставляем первый по стабильному order_by: стране нужен один ряд рейтинга,
            # а не исчезновение из-за дубля частоты/публикации.
            continue
    return list(by_country.values())


def _resolve_rating_year(
    years: list[int],
    preferred: int | None,
    values_by_year: dict[str, dict[str, dict]],
) -> int | None:
    if not years:
        return None
    if preferred in years:
        return preferred
    return resolve_default_coverage_year(years, values_by_year)


async def build_world_rating_payload(
    concept_slug: str,
    db: AsyncSession,
    *,
    year: int | None = None,
) -> dict | None:
    concept = CONCEPT_BY_SLUG.get(concept_slug)
    if concept is None or "rating" not in concept.enabled_surfaces:
        return None

    countries = await _world_rating_countries(db)
    members = await _world_rating_members(db, concept)
    mode = ranking_value_mode(concept.slug, members)
    public_unit = ranking_public_unit(mode, concept.unit_ru)
    public_name = ranking_display_name(mode, concept.slug, concept.name_ru)

    values_by_year: dict[str, dict[str, dict]] = {}
    ids = [indicator.id for _, indicator in members]
    series_by_id: dict[int, list[tuple[date, float]]] = {}
    if ids:
        rows = (
            await db.execute(
                select(
                    WorldDataPoint.indicator_id,
                    WorldDataPoint.date,
                    WorldDataPoint.value,
                )
                .where(WorldDataPoint.indicator_id.in_(ids))
                .order_by(WorldDataPoint.indicator_id, WorldDataPoint.date)
            )
        ).all()
        for indicator_id, point_date, value in rows:
            series_by_id.setdefault(indicator_id, []).append((point_date, float(value)))

    for country, indicator in members:
        for point_year, (point_date, value) in yearly_last_points(
            series_by_id.get(indicator.id, []), mode
        ).items():
            bucket = values_by_year.setdefault(str(point_year), {})
            bucket[country.code] = {
                "country_code": country.code,
                "country_slug": country.slug,
                "country_name": country.name_ru,
                "indicator_code": indicator.code,
                "date": point_date.isoformat(),
                "frequency": indicator.frequency,
                "value": round(value, 4),
                "unit": public_unit,
                "source": _source_label(indicator.source, indicator.provider),
            }

    russia_meta = await merge_russia_into_values_by_year(
        db,
        concept.slug,
        values_by_year,
        concept_mode=mode,
        public_unit=public_unit,
    )

    years = sorted(int(y) for y, items in values_by_year.items() if items)
    active_year = _resolve_rating_year(years, year, values_by_year)
    active_items = list(values_by_year.get(str(active_year), {}).values()) if active_year else []
    reverse = world_rating_default_sort(concept.slug) == "desc"
    active_items.sort(key=lambda item: item["value"], reverse=reverse)
    for i, item in enumerate(active_items, 1):
        item["rank"] = i

    with_data_codes = {item["country_code"] for item in active_items}
    without_data = [
        {
            "code": country.code,
            "slug": country.slug,
            "name": country.name_ru,
            "name_en": country.name_en,
            "region": country.region_ru,
        }
        for country in countries
        if country.code not in with_data_codes
    ]
    # Россия в каталоге покрытия только если ряд сопоставим по смыслу.
    if russia_meta is not None and "RU" not in with_data_codes:
        ru = russia_country_public()
        without_data.append({
            "code": ru["code"],
            "slug": ru["slug"],
            "name": ru["name_ru"],
            "name_en": ru["name_en"],
            "region": ru["region_ru"],
        })
    russia_in_total = 1 if russia_meta is not None else 0
    source_labels = _join_sources_ru([item["source"] for item in active_items])
    last_date = max((item["date"] for item in active_items), default=None)
    page_title = world_rating_title(concept.slug, public_name, active_year)

    return {
        "concept": {
            "slug": concept.slug,
            "name": public_name,
            "unit": public_unit,
            "value_mode": mode,
            "default_sort": world_rating_default_sort(concept.slug),
            "period_method": ranking_period_method(mode),
            "money_unit_guard": _is_money_rating(concept),
            "index_base_guard": mode == "yoy" and concept.slug == "hicp-index",
            "title": page_title,
            "russia": russia_meta,
        },
        "years": years,
        "active_year": active_year,
        "items": active_items,
        "countries_without_data": without_data,
        "coverage": {
            "with_data": len(active_items),
            "without_data": len(without_data),
            "total": len(countries) + russia_in_total,
        },
        "sources": source_labels,
        "last_date": last_date,
        "values_by_year": values_by_year,
    }


def _period_label(d: date | None, frequency: str | None) -> str:
    if d is None:
        return "нет данных"
    freq = (frequency or "").lower()
    if freq == "annual":
        return f"{d.year} год"
    if freq in ("monthly", "quarterly", "weekly"):
        return format_month_ru(d) or format_date_ru(d)
    return format_date_ru(d)


def _date_range_ru(start: date | None, end: date | None) -> str:
    """Период истории: «2024» или «2015–2025» (среднее тире)."""
    if start is None or end is None:
        return ""
    if start.year == end.year:
        return str(start.year)
    return f"{start.year}–{end.year}"


async def _country(db: AsyncSession, slug: str) -> WorldCountry | None:
    return (
        await db.execute(
            select(WorldCountry).where(
                WorldCountry.slug == slug,
                WorldCountry.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()


async def render_world_home_html(db: AsyncSession) -> tuple[int, str]:
    counts_q = (
        select(
            WorldIndicator.country_id,
            func.count().label("cnt"),
        )
        .where(WorldIndicator.is_listed.is_(True))
        .group_by(WorldIndicator.country_id)
        .subquery()
    )
    rows = (
        await db.execute(
            select(WorldCountry, counts_q.c.cnt)
            .outerjoin(counts_q, WorldCountry.id == counts_q.c.country_id)
            .where(WorldCountry.is_active.is_(True))
            .order_by(WorldCountry.sort_order, WorldCountry.name_ru)
        )
    ).all()
    if not rows:
        return 404, "<h1>Страны не найдены</h1>"

    n_listed = sum(int(cnt or 0) for _c, cnt in rows)
    n_countries = sum(1 for _c, cnt in rows if int(cnt or 0) > 0)

    links = "".join(
        f'<li><a href="{escape(paths.country(c.slug))}">{escape(c.name_ru)}</a>'
        f" — {_n_indicators_phrase(int(cnt or 0))}</li>"
        for c, cnt in rows
        if int(cnt or 0) > 0
    )

    body = f"""<div class="seo-page">
{_breadcrumbs_nav(crumbs.world_home_trail())}
<p class="seo-eyebrow">Официальная статистика по странам</p>
<h1>{escape(WORLD_HOME_H1)}</h1>
<p>Раздел собирает официальные ряды по странам — цены, валовой внутренний
продукт, рынок труда, внешняя торговля и финансы. Сейчас доступны данные по
{n_countries} странам и {_n_indicators_phrase(n_listed)} с графиками динамики
и таблицами значений. Основа европейской части — Евростат; показатели по
странам за пределами Европы приходят от их национальных статистических
ведомств и центральных банков.</p>
<section class="seo-section"><h2>Страны</h2><ul>{links}</ul></section>
<section class="seo-section"><h2>Россия и сравнение</h2>
<p>Макроэкономика России — в разделе
<a href="/">главной витрины</a> и каталоге
<a href="{paths.russia_category('prices')}">цен</a>,
<a href="{paths.russia_category('gdp')}">ВВП</a> и
<a href="{paths.russia_category('labor')}">рынка труда</a>.
Сопоставить ряды можно на странице
<a href="/compare">сравнения индикаторов</a>.</p></section>
</div>"""

    json_ld = [_breadcrumbs(crumbs.world_home_trail())]
    html = await build_document(
        title=WORLD_HOME_TITLE,
        description=WORLD_HOME_DESC,
        canonical_path=paths.world_hub(),
        body=body,
        json_ld=json_ld,
        keywords=(
            "мировая экономика статистика, экономика стран, "
            "евростат данные, инфляция по странам, ввп стран"
        ),
        og_image=f"{DOMAIN}/og-image-v2.png",
    )
    return 200, html


async def render_world_rating_html(
    concept_slug: str,
    db: AsyncSession,
    *,
    year: int | None = None,
) -> tuple[int, str]:
    payload = await build_world_rating_payload(concept_slug, db, year=year)
    if payload is None:
        return 404, "<h1>Показатель рейтинга не найден</h1>"
    active_year = payload["active_year"]
    items = payload["items"]
    if active_year is None or not items:
        return 404, "<h1>Нет данных для рейтинга</h1>"

    concept = payload["concept"]
    name = concept["name"]
    unit = concept["unit"]
    total = payload["coverage"]["total"]
    with_data = payload["coverage"]["with_data"]
    without_data = payload["coverage"]["without_data"]
    sources = payload["sources"]
    last_date = payload["last_date"]
    query_name = WORLD_RATING_QUERY_NAMES.get(concept_slug, name.lower())
    order_uri = (
        "https://schema.org/ItemListOrderAscending"
        if concept["default_sort"] == "asc"
        else "https://schema.org/ItemListOrderDescending"
    )

    def _value_text(item: dict, with_unit: bool = True) -> str:
        if not with_unit:
            return format_number_ru(item["value"])
        row_unit = item.get("unit") or unit
        suffix = unit_suffix(row_unit)
        return f"{format_number_ru(item['value'])} {suffix}".strip()

    def _date_text(raw: str | None, frequency: str | None = None) -> str:
        if not raw:
            return "нет данных"
        # Месячный индекс относится к месяцу целиком: «1 декабря 2025» создаёт
        # ложное впечатление замера на конкретный день.
        return _period_label(date.fromisoformat(raw), frequency)

    def _countries_phrase(n: int) -> str:
        n = int(n)
        tail = n % 100
        if 11 <= tail <= 14:
            return f"{n} стран"
        last = n % 10
        if last == 1:
            return f"{n} страна"
        if last in (2, 3, 4):
            return f"{n} страны"
        return f"{n} стран"

    first = items[0]
    last = items[-1]
    title = concept.get("title") or world_rating_title(concept_slug, name, active_year)
    # Перечень ведомств живёт в теле страницы: в meta он раздувает описание до
    # обрезки и вытесняет то, ради чего посетитель кликает.
    desc = (
        f"{title}: полная таблица "
        f"{_countries_phrase(with_data)} из {total}, карта и ссылки на карточки стран. "
        f"Официальная статистика национальных ведомств и Евростата."
    )
    intro = (
        f"Рейтинг стран по показателю «{name}» за {active_year} год. "
        f"В таблице {_countries_phrase(with_data)} с опубликованным значением; ещё "
        f"{_countries_phrase(without_data)} мирового каталога не имеют значения за этот год. "
        f"Порядок таблицы нейтральный: пользователь может переключить сортировку "
        f"по возрастанию или убыванию значения."
    )
    if concept["money_unit_guard"]:
        intro += (
            " Денежные показатели не пересчитываются в другую валюту: в рейтинг "
            "попадают только ряды, уже опубликованные в сопоставимой единице."
        )
    if concept.get("index_base_guard"):
        intro += (
            " Сравнивается изменение потребительских цен за год в процентах: "
            "базовые периоды национальных индексов при таком расчёте сокращаются, "
            "и величины сопоставимы между странами."
        )
    russia_note = (concept.get("russia") or {}).get("note")
    if russia_note:
        intro += f" {russia_note}"

    concept_links = "".join(
        f'<li><a href="{escape(paths.world_rating(c.slug))}">{escape(c.name_ru)}</a></li>'
        for c in WORLD_CONCEPTS
        if "rating" in c.enabled_surfaces
    )
    year_links = "".join(
        f'<li><a href="{escape(paths.world_rating(concept_slug))}?year={y}">{y}</a></li>'
        for y in payload["years"][-12:]
    )

    # Колонка единицы нужна, только когда единицы у стран разные: при общей
    # единице она повторяет одно и то же в каждой строке и выносится в шапку.
    row_units = {(item.get("unit") or unit or "").strip() for item in items}
    shared_unit = row_units.pop() if len(row_units) == 1 else None
    unit_head = "" if shared_unit is not None else "<th>Единица</th>"

    def _unit_cell(item: dict) -> str:
        if shared_unit is not None:
            return ""
        return f"<td>{escape(item.get('unit') or unit or 'единицы источника')}</td>"

    rows_html = "".join(
        f"<tr><td>{item['rank']}</td>"
        f'<td><a href="{escape(paths.indicator(item["country_slug"], item["indicator_code"]))}">'
        f'{escape(item["country_name"])}</a></td>'
        f"<td>{escape(_value_text(item, with_unit=shared_unit is None))}</td>"
        f"{_unit_cell(item)}"
        f"<td>{escape(_date_text(item.get('date'), item.get('frequency')))}</td></tr>"
        for item in items
    )
    if not shared_unit:
        value_head = "Значение"
    elif shared_unit.startswith("%"):
        value_head = f"Значение, {escape(shared_unit)}"
    else:
        # «изменение за год, %» само описывает колонку: «Значение, изменение
        # за год, %» распадается на три запятых и не читается.
        value_head = escape(shared_unit[0].upper() + shared_unit[1:])
    table_html = (
        '<div class="seo-scroll"><table><thead><tr>'
        f"<th>Место</th><th>Страна</th><th>{value_head}</th>{unit_head}<th>Период</th>"
        f"</tr></thead><tbody>{rows_html}</tbody></table></div>"
    )

    missing = payload["countries_without_data"]
    missing_html = ""
    if missing:
        missing_items = "".join(
            f'<li><a href="{escape(paths.country(country["slug"]))}">{escape(country["name"])}</a></li>'
            for country in missing
        )
        missing_html = (
            f'<section class="seo-section"><h2>Страны без данных за {active_year} год</h2>'
            f'<p>У этих стран нет опубликованного значения по выбранному показателю '
            f"за {active_year} год.</p><ul class=\"seo-pills\">{missing_items}</ul></section>"
        )

    og_path = paths.og_world_rating(concept_slug)
    figure_alt = (
        f"{name} по странам — рейтинг {active_year} года, "
        f"первое значение в текущем порядке: {first['country_name']} ({_value_text(first)})"
    )
    figure_html = (
        f'<figure class="seo-chart"><img src="{escape(og_path)}" alt="{escape(figure_alt)}" '
        f'width="1200" height="630" loading="eager">'
        f"<figcaption>{escape(name)} по странам, {active_year} год. "
        f"Источник: {escape(sources)}. forecasteconomy.com</figcaption></figure>"
    )

    canonical = paths.world_rating(concept_slug)
    if year is not None and year == active_year:
        canonical = f"{canonical}?year={year}"

    json_ld = [
        _breadcrumbs(crumbs.world_rating_trail(name, paths.world_rating(concept_slug))),
        {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "name": title,
            "description": desc,
            "url": f"{DOMAIN}{canonical}",
            "itemListOrder": order_uri,
            "numberOfItems": with_data,
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": item["rank"],
                    "name": item["country_name"],
                    "url": f"{DOMAIN}{paths.indicator(item['country_slug'], item['indicator_code'])}",
                    "item": {
                        "@type": "Country",
                        "name": item["country_name"],
                        "url": f"{DOMAIN}{paths.country(item['country_slug'])}",
                    },
                }
                for item in items
            ],
        },
        {
            "@context": "https://schema.org",
            "@type": "ImageObject",
            "contentUrl": f"{DOMAIN}{og_path}",
            "url": f"{DOMAIN}{og_path}",
            "width": 1200,
            "height": 630,
            "name": f"{name} — рейтинг стран, {active_year}",
            "caption": figure_alt,
            "representativeOfPage": True,
        },
    ]

    body = f"""<div class="seo-page">
{_breadcrumbs_nav(crumbs.world_rating_trail(name, paths.world_rating(concept_slug)))}
<p class="seo-eyebrow">Сопоставимые показатели стран</p>
<h1>{escape(title)}</h1>
<p>{escape(intro)}</p>
{figure_html}
<div class="seo-tiles">
<div class="seo-tile"><span>Первое значение в текущем порядке — {escape(first["country_name"])}</span><b>{escape(_value_text(first))}</b></div>
<div class="seo-tile"><span>Последнее значение в текущем порядке — {escape(last["country_name"])}</span><b>{escape(_value_text(last))}</b></div>
<div class="seo-tile"><span>Стран с данными</span><b>{with_data} из {total}</b></div>
<div class="seo-tile"><span>Последняя дата в срезе</span><b>{escape(_date_text(last_date))}</b></div>
</div>
<section class="seo-section"><h2>Полный рейтинг стран</h2>{table_html}</section>
{missing_html}
<section class="seo-section"><h2>Другие показатели рейтинга</h2><ul class="seo-pills">{concept_links}</ul></section>
<section class="seo-section"><h2>Другие годы</h2><ul class="seo-pills">{year_links}</ul></section>
<section class="seo-section"><h2>Источник данных</h2>
<p>{escape(sources)}. Единицы измерения: {escape(unit or 'единицы источника')}.
Для каждого календарного года берётся последнее опубликованное значение внутри года.</p></section>
</div>"""

    html = await build_document(
        title=title,
        description=desc,
        canonical_path=canonical,
        body=body,
        json_ld=json_ld,
        keywords=(
            f"{name} по странам, рейтинг стран по {name}, "
            f"{name} {active_year}, мировая экономика рейтинг"
        ),
        og_image=f"{DOMAIN}{og_path}",
    )
    return 200, html


async def render_world_country_html(slug: str, db: AsyncSession) -> tuple[int, str]:
    country = await _country(db, slug)
    if country is None:
        return 404, "<h1>Страна не найдена</h1>"

    inds = (
        await db.execute(
            select(WorldIndicator)
            .where(
                WorldIndicator.country_id == country.id,
                WorldIndicator.is_listed.is_(True),
            )
            .order_by(WorldIndicator.category_ru, WorldIndicator.name_ru)
        )
    ).scalars().all()
    if not inds:
        return 404, "<h1>Нет показателей</h1>"

    # Каталог = карточки (primary частоты), не ряды M/Q/A.
    inds = _pick_card_primaries(list(inds))
    inds.sort(key=lambda i: (i.category_ru or "", _display_name(i)))

    ids = [i.id for i in inds]
    rn = func.row_number().over(
        partition_by=WorldDataPoint.indicator_id,
        order_by=WorldDataPoint.date.desc(),
    ).label("rn")
    sub = (
        select(
            WorldDataPoint.indicator_id,
            WorldDataPoint.date,
            WorldDataPoint.value,
            rn,
        )
        .where(WorldDataPoint.indicator_id.in_(ids))
        .subquery()
    )
    latest = {
        iid: (dt, float(value))
        for iid, dt, value in (
            await db.execute(
                select(sub.c.indicator_id, sub.c.date, sub.c.value).where(sub.c.rn == 1)
            )
        ).all()
    }

    # Ключевые: сначала приоритетные категории, внутри — больше точек.
    cat_rank = {name: i for i, name in enumerate(_KEY_CATEGORY_ORDER)}

    def _key_sort(ind: WorldIndicator) -> tuple:
        return (
            cat_rank.get(ind.category_ru or "", 99),
            -(ind.points_count or 0),
            ind.name_ru,
        )

    key_inds = sorted(
        [i for i in inds if i.id in latest],
        key=_key_sort,
    )[:12]

    key_rows = "".join(
        (
            f"<tr><td><a href=\"{escape(paths.indicator(slug, ind.code))}\">"
            f"{escape(_display_name(ind))}</a></td>"
            f"<td>{_fmt(latest[ind.id][1])}{escape(_unit_sfx(_unit_of(ind)))}</td>"
            f"<td>{escape(_period_label(latest[ind.id][0], ind.frequency))}</td></tr>"
        )
        for ind in key_inds
    )
    key_table = (
        '<div class="seo-scroll"><table><thead><tr>'
        "<th>Показатель</th><th>Значение</th><th>Дата</th>"
        "</tr></thead><tbody>"
        + key_rows
        + "</tbody></table></div>"
        if key_rows
        else ""
    )

    by_cat: dict[str, list[WorldIndicator]] = {}
    for ind in inds:
        by_cat.setdefault(ind.category_ru or "Прочее", []).append(ind)

    sections = []
    for cat in sorted(by_cat.keys(), key=lambda c: (cat_rank.get(c, 99), c)):
        items = by_cat[cat]
        links = "".join(
            f'<li><a href="{escape(paths.indicator(slug, ind.code))}">'
            f"{escape(_display_name(ind))}</a></li>"
            for ind in items[:40]
        )
        more = (
            f"<p>Всего в разделе — {len(items)} показателей.</p>"
            if len(items) > 40
            else ""
        )
        sections.append(
            f'<section class="seo-section"><h2>{escape(cat)}</h2>'
            f"<ul>{links}</ul>{more}</section>"
        )

    neighbors = (
        await db.execute(
            select(WorldCountry)
            .where(
                WorldCountry.is_active.is_(True),
                WorldCountry.slug != slug,
            )
            .order_by(WorldCountry.sort_order, WorldCountry.name_ru)
            .limit(12)
        )
    ).scalars().all()
    neighbors_html = ""
    if neighbors:
        nlinks = "".join(
            f'<li><a href="{escape(paths.country(n.slug))}">{escape(n.name_ru)}</a></li>'
            for n in neighbors
        )
        neighbors_html = (
            '<section class="seo-section"><h2>Другие страны</h2>'
            f'<ul class="seo-pills">{nlinks}</ul></section>'
        )

    og_path = paths.og_country(slug)
    n_ind = len(inds)
    gen = _genitive(country)
    n_phrase = _n_indicators_phrase(n_ind)
    source_phrase, has_national = _country_source_phrase(inds)
    title = f"Экономика {gen}: статистика и показатели"
    if has_national:
        desc = (
            f"{country.name_ru}: {n_phrase} — цены, ВВП, "
            f"рынок труда, торговля и финансы. Источник: {source_phrase}. "
            f"Графики и последние значения на Forecast Economy."
        )
        figure_alt = (
            f"Экономика {gen} — сводка ключевых показателей, "
            f"источник {source_phrase}"
        )
        eyebrow = f"Национальная статистика — {country.name_ru}"
        lead = (
            f"Официальные национальные ряды для {escape(gen)}: "
            f"{n_phrase} в {len(by_cat)} разделах — цены, ВВП, рынок труда, "
            f"внешняя торговля, финансы и другие темы. У каждого показателя — график "
            f"динамики, таблица значений и ссылка на первоисточник."
        )
        source_section = (
            f"Данные публикует {escape(source_phrase)}. На сайте ряды приведены "
            f"в единицах источника; дата последнего значения указана у каждого "
            f"показателя."
        )
    else:
        desc = (
            f"{country.name_ru}: {n_phrase} Евростата — цены, ВВП, "
            f"рынок труда, торговля и финансы. Графики и последние значения "
            f"на Forecast Economy."
        )
        figure_alt = (
            f"Экономика {gen} — сводка ключевых показателей, "
            f"источник Евростат"
        )
        eyebrow = f"Статистика Евростата — {country.name_ru}"
        lead = (
            f"Официальные ряды Евростата для {escape(gen)}: "
            f"{n_phrase} в {len(by_cat)} разделах — цены, ВВП, рынок труда, "
            f"внешняя торговля, финансы и другие темы. У каждого показателя — график "
            f"динамики, таблица значений и ссылка на первоисточник."
        )
        source_section = (
            f"Данные публикует {_SOURCE_PUBLIC}. На сайте ряды приведены в единицах "
            f"источника; дата последнего значения указана у каждого показателя."
        )
    figure_html = (
        f'<figure class="seo-chart"><img src="{escape(og_path)}" '
        f'alt="{escape(figure_alt)}" width="1200" height="630" loading="eager">'
        f"<figcaption>Ключевые показатели экономики {escape(gen)}. "
        f"Источник: {escape(source_phrase)}. forecasteconomy.com</figcaption></figure>"
    )

    body = f"""<div class="seo-page">
{_breadcrumbs_nav(crumbs.world_country_trail(country.name_ru, paths.country(slug)))}
<p class="seo-eyebrow">{escape(eyebrow)}</p>
<h1>Экономика {escape(gen)}: статистика и показатели</h1>
<p>{lead}</p>
{figure_html}
<section class="seo-section"><h2>Ключевые показатели</h2>{key_table}</section>
{''.join(sections)}
{neighbors_html}
<section class="seo-section"><h2>Источник данных</h2>
<p>{source_section}</p></section>
<section class="seo-section"><h2>Россия</h2>
<p>Сопоставить с российскими рядами можно в
<a href="/compare">сравнении индикаторов</a> и на
<a href="/">главной витрине</a> Forecast Economy.</p></section>
</div>"""

    json_ld = [
        _breadcrumbs(crumbs.world_country_trail(country.name_ru, paths.country(slug))),
        {
            "@context": "https://schema.org",
            "@type": "ImageObject",
            "contentUrl": f"{DOMAIN}{og_path}",
            "url": f"{DOMAIN}{og_path}",
            "width": 1200,
            "height": 630,
            "name": f"Экономика {gen} — сводка показателей",
            "caption": figure_alt,
            "representativeOfPage": True,
        },
    ]
    html = await build_document(
        title=title,
        description=desc,
        canonical_path=paths.country(slug),
        body=body,
        json_ld=json_ld,
        keywords=(
            f"{country.name_ru} экономика, {country.name_ru} статистика, "
            f"{country.name_ru} ввп, {country.name_ru} инфляция, "
            f"{country.name_ru} безработица"
        ),
        og_image=f"{DOMAIN}{og_path}",
    )
    return 200, html


async def render_world_indicator_html(
    slug: str, code: str, db: AsyncSession
) -> tuple[int, str]:
    country = await _country(db, slug)
    if country is None:
        return 404, "<h1>Страна не найдена</h1>"

    indicator = (
        await db.execute(
            select(WorldIndicator).where(
                WorldIndicator.country_id == country.id,
                WorldIndicator.code == code,
                WorldIndicator.is_listed.is_(True),
            )
        )
    ).scalar_one_or_none()
    if indicator is None:
        return 404, "<h1>Показатель не найден</h1>"

    rows = (
        await db.execute(
            select(WorldDataPoint.date, WorldDataPoint.value)
            .where(WorldDataPoint.indicator_id == indicator.id)
            .order_by(WorldDataPoint.date)
        )
    ).all()
    if not rows:
        return 404, "<h1>Нет данных</h1>"

    series = [(d, float(v)) for d, v in rows]
    first_date, first_value = series[0]
    last_date, last_value = series[-1]
    unit = _unit_of(indicator)
    unit_sfx = _unit_sfx(unit)
    source = _source_label(indicator.source, indicator.provider)
    display = _display_name(indicator)
    period = _date_range_ru(first_date, last_date) or (
        f"{first_date.year}–{last_date.year}"
    )
    last_label = _period_label(last_date, indicator.frequency)
    freq_links_html = await _frequency_links_html(db, slug, indicator)
    siblings = await world_card_siblings(db, indicator)
    multi_freq = len(siblings) >= 2

    prep = _prep(country)
    desc_text = (indicator.description or "").strip()
    if not desc_text:
        desc_text = (
            f"{display} в {prep} — официальный ряд {source}. "
            f"На графике — динамика показателя за доступный период наблюдений"
            + (f"; значения приведены в единицах: {unit}" if unit else "")
            + "."
        )

    period_line = f"Период наблюдений: {escape(period)}. Источник — {escape(source)}."
    if not multi_freq:
        freq_ru = _FREQ_RU.get((indicator.frequency or "").lower(), "")
        if freq_ru:
            period_line = (
                f"Период наблюдений: {escape(period)}, "
                f"публикация — {escape(freq_ru)}. Источник — {escape(source)}."
            )

    paragraphs = [
        (
            f"{escape(display)} в {escape(prep)}: "
            f"последнее значение {_fmt(last_value)}{escape(unit_sfx)} "
            f"на {escape(last_label)}."
        ),
        escape(desc_text),
        period_line,
    ]
    if indicator.methodology and indicator.methodology.strip():
        paragraphs.append(escape(indicator.methodology.strip()))

    paragraphs_html = "".join(f"<p>{p}</p>" for p in paragraphs)

    recent = list(reversed(series[-24:]))
    table_rows = "".join(
        f"<tr><td>{escape(_period_label(d, indicator.frequency))}</td>"
        f"<td>{_fmt(v)}</td></tr>"
        for d, v in recent
    )
    table_html = (
        f"<h2>Последние значения</h2>"
        f'<div class="seo-scroll"><table><thead><tr><th>Период</th>'
        f"<th>{escape(unit or 'Значение')}</th></tr></thead>"
        f"<tbody>{table_rows}</tbody></table></div>"
    )

    og_path = paths.og_indicator(slug, code)
    alt = (
        f"{display} в {prep}: график динамики {period}, "
        f"последнее значение {_fmt(last_value)}{unit_sfx}".strip()
        + f", источник {source}"
    )
    figure_html = (
        f'<figure class="seo-chart"><img src="{escape(og_path)}" '
        f'alt="{escape(alt)}" width="1200" height="630" loading="eager">'
        f"<figcaption>{escape(display)} в {escape(prep)}, "
        f"{escape(period)}. Источник: {escape(source)}.</figcaption></figure>"
    )

    # Тот же срез у других стран (dataset + slice_hash).
    peers = (
        await db.execute(
            select(WorldCountry.slug, WorldCountry.name_ru, WorldIndicator.code)
            .join(WorldIndicator, WorldIndicator.country_id == WorldCountry.id)
            .where(
                WorldIndicator.provider == indicator.provider,
                WorldIndicator.dataset_id == indicator.dataset_id,
                WorldIndicator.slice_hash == indicator.slice_hash,
                WorldIndicator.is_listed.is_(True),
                WorldCountry.is_active.is_(True),
                WorldCountry.id != country.id,
            )
            .order_by(WorldCountry.sort_order, WorldCountry.name_ru)
            .limit(12)
        )
    ).all()
    peers_html = ""
    if peers:
        items = "".join(
            f'<li><a href="{escape(paths.indicator(s, c))}">'
            f"{escape(display)} — {escape(n)}</a></li>"
            for s, n, c in peers
        )
        peers_html = (
            '<section class="seo-section"><h2>Этот показатель в других странах</h2>'
            f"<ul>{items}</ul></section>"
        )

    cat_siblings = (
        await db.execute(
            select(WorldIndicator)
            .where(
                WorldIndicator.country_id == country.id,
                WorldIndicator.category_ru == indicator.category_ru,
                WorldIndicator.code != indicator.code,
                WorldIndicator.is_listed.is_(True),
            )
            .order_by(WorldIndicator.name_ru)
        )
    ).scalars().all()
    cat_siblings = [
        s for s in _pick_card_primaries(list(cat_siblings))
        if s.code != indicator.code
    ][:12]
    siblings_html = ""
    if cat_siblings:
        items = "".join(
            f'<li><a href="{escape(paths.indicator(slug, s.code))}">'
            f"{escape(_display_name(s))}</a></li>"
            for s in cat_siblings
        )
        cat = indicator.category_ru or "разделе"
        siblings_html = (
            f'<section class="seo-section"><h2>Ещё в разделе «{escape(cat)}» '
            f"— {escape(country.name_ru)}</h2>"
            f'<ul class="seo-pills">{items}</ul></section>'
        )

    source_url = (indicator.source_url or "").strip()
    source_link = (
        f'<p><a href="{escape(source_url)}" rel="noopener noreferrer">'
        f"Открыть ряд на сайте {_SOURCE_PUBLIC}</a></p>"
        if source_url
        else ""
    )

    title = (
        f"{display} в {prep}: {_fmt(last_value)}{unit_sfx} ({last_label})"
    ).strip()
    meta_desc = (
        f"{display} в {prep}: {_fmt(last_value)}{unit_sfx} на {last_label}. "
        f"Динамика {period}, график и таблица. Источник: {source}."
    ).strip()

    json_ld = [
        _breadcrumbs(crumbs.world_indicator_trail(
            country.name_ru, paths.country(slug), display, paths.indicator(slug, code),
        )),
        {
            "@context": "https://schema.org",
            "@type": "Dataset",
            "name": f"{display} в {prep}",
            "description": (
                f"{display}"
                + (f" ({unit})" if unit else "")
                + f" в {prep}, {period}. Источник: {source}."
            ),
            "url": f"{DOMAIN}{paths.indicator(slug, code)}",
            "temporalCoverage": f"{first_date.isoformat()}/{last_date.isoformat()}",
            "spatialCoverage": country.name_ru,
            "creator": {"@type": "Organization", "name": source},
            "license": "https://creativecommons.org/licenses/by/4.0/",
            "image": f"{DOMAIN}{og_path}",
        },
        {
            "@context": "https://schema.org",
            "@type": "ImageObject",
            "contentUrl": f"{DOMAIN}{og_path}",
            "url": f"{DOMAIN}{og_path}",
            "width": 1200,
            "height": 630,
            "name": f"{display} в {prep}: график",
            "caption": alt,
            "representativeOfPage": True,
        },
    ]

    body = f"""<div class="seo-page">
{_breadcrumbs_nav(crumbs.world_indicator_trail(
    country.name_ru, paths.country(slug), display, paths.indicator(slug, code),
))}
<p class="seo-eyebrow">{escape(indicator.category_ru or 'Статистика')} — {escape(country.name_ru)}</p>
<h1>{escape(display)} в {escape(prep)}</h1>
{figure_html}
<div class="seo-tiles">
<div class="seo-tile"><span>Последнее значение</span><b>{_fmt(last_value)}{escape(unit_sfx)}</b></div>
<div class="seo-tile"><span>Дата</span><b>{escape(last_label)}</b></div>
<div class="seo-tile"><span>Период</span><b>{escape(period)}</b></div>
<div class="seo-tile"><span>Источник</span><b>{escape(source)}</b></div>
</div>
{paragraphs_html}
{freq_links_html}
{table_html}
{peers_html}
{siblings_html}
<section class="seo-section"><h2>Источник данных</h2>
<p>{escape(source)}. Единицы: {escape(unit or 'единицы источника')}.
Период наблюдений: {escape(period)}.</p>
{source_link}
</section>
<section class="seo-section"><h2>Россия</h2>
<p>Российские макропоказатели — на
<a href="/">главной</a> и в
<a href="/compare">сравнении</a>.</p></section>
</div>"""

    html = await build_document(
        title=title,
        description=meta_desc,
        canonical_path=paths.indicator(slug, code),
        body=body,
        json_ld=json_ld,
        keywords=(
            f"{display} {country.name_ru}, {country.name_ru} "
            f"{display} график, {country.name_ru} статистика"
        ),
        og_image=f"{DOMAIN}{og_path}",
    )
    return 200, html

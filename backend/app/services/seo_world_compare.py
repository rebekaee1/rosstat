"""SSR-страницы сравнения двух стран по курируемому мировому показателю:
``/{country_a}-vs-{country_b}/{concept_slug}`` (мировой аналог
``/russia/region-vs/{a}-vs-{b}`` из seo_region_compare.py).

Контракт для роута (app/api/seo_pages.py, следующий агент):
- ``(200, html)`` — готовый документ, canonical = упорядоченная пара;
- ``(301, redirect_path)`` — пара пришла в обратном порядке; роут обязан
  отдать ``_permanent_redirect(redirect_path)`` (относительный путь
  вида ``/france-vs-germany/gdp-usd``);
- ``(404, html)`` — неизвестная страна/понятие либо у одной из стран нет
  сопоставимого ряда понятия.

Канонизация пары — алфавитный порядок слагов, без обращения к БД; проверка
стран выполняется до редиректа, чтобы мусорные пары отдавали 404, а не 301
на несуществующую страницу.

Данные — тот же сопоставимый срез, что у карты и рейтинга мира
(``_concept_members`` в app/api/world.py): ряды понятия по
dataset + measure + срез с приоритетом национального crosswalk и классом
меры для денежных понятий. Представление (уровень / изменение за год)
решает движок рейтингов (ranking_value_mode), поэтому страница не может
показать несопоставимый уровень (например, индексы цен с разными базами).

Ряды обеих стран по всем compare-понятиям берутся одной union-выборкой
(``_fetch_compare_candidates``) и матчатся по понятиям в Python
(``_match_concept_pair``) — лид, таблица и блок «другие показатели»
обходятся одним SQL-запросом по рядам.

Разница значений публикуется честно по типу единицы: для процентных
рядов — в процентных пунктах (п.п. / pp), для одинаковых единиц — в
единице показателя; при разных непроцентных единицах сумма разницы не
публикуется (только «у кого выше»).

Нужные снаружи контракты (реализует роут-агент): роут
``/seo/world-vs/{pair}/{concept}`` + nginx-локация; OG-эндпоинт
``/og/world-vs/{a}-vs-{b}/{concept}.png`` (картинка уже встроена в
страницу тремя путями: og:image, ImageObject, видимый <img>); sitemap-секция
через ``world_vs_path`` / ``og_world_vs_path``. Публичные тексты строятся
на месте (в WORLD_TEMPLATES_EN ключей vs_* нет — файл вне зоны владения
этой задачи).
"""

from __future__ import annotations

from app.services import breadcrumbs as crumbs
from app.services import site_paths as paths

from datetime import date
from html import escape

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.eurostat_listing import normalize_frequency
from app.data.world_concept_national import national_codes_for_concept
from app.data.world_concepts import (
    CONCEPT_BY_SLUG,
    WORLD_CONCEPTS,
    concept_for_indicator,
    concept_public_name,
    concept_public_unit,
)
from app.models import WorldCountry, WorldDataPoint, WorldIndicator
from app.services.display import localize_unit
from app.services.locale import get_locale, in_language
from app.services.seo_renderer import (
    _absolute,
    _breadcrumbs,
    _breadcrumbs_nav,
    _iso_date,
    _site_json_ld,
    build_document,
)
from app.services.seo_world import (
    _concept_allowed_datasets,
    _country,
    _country_label,
    _date_range_ru,
    _fmt,
    _genitive,
    _join_sources,
    _period_label,
    _period_sentence,
    _same_public_unit,
    _source_label,
    _unit_of,
)
from app.services.world_rank_values import (
    apply_rank_series,
    ranking_display_name,
    ranking_period_method,
    ranking_public_unit,
    ranking_value_mode,
)

_TABLE_ROWS = 12
_OTHER_CONCEPTS_LIMIT = 6


def _seg(value: str) -> str:
    s = (value or "").strip().strip("/")
    if not s:
        raise ValueError("empty slug")
    return s


def world_vs_path(slug_a: str, slug_b: str, concept_slug: str) -> str:
    """Канонический публичный путь сравнения: /{a}-vs-{b}/{concept}."""
    return f"/{_seg(slug_a)}-vs-{_seg(slug_b)}/{_seg(concept_slug)}"


def og_world_vs_path(slug_a: str, slug_b: str, concept_slug: str) -> str:
    """Публичный путь OG-картинки сравнения (эндпоинт строит роут-агент)."""
    return f"/og/world-vs/{_seg(slug_a)}-vs-{_seg(slug_b)}/{_seg(concept_slug)}.png"


async def _fetch_compare_candidates(
    db: AsyncSession,
    country_a: WorldCountry,
    country_b: WorldCountry,
) -> list[WorldIndicator]:
    """Одна union-выборка кандидатов для всех compare-понятий пары.

    Тот же фильтр, что у ``_compare_concepts``/``_concept_members`` API
    (listed + dataset понятий + национальный crosswalk), но по двум странам
    и без per-concept повторов: SSR-страница рендерится одним SQL-запросом.
    """
    allowed: set[str] = set()
    national_codes: set[str] = set()
    for concept in WORLD_CONCEPTS:
        if "compare" not in concept.enabled_surfaces:
            continue
        allowed.update(_concept_allowed_datasets(concept))
        national_codes.update(national_codes_for_concept(concept.slug))
    return list(
        (
            await db.execute(
                select(WorldIndicator)
                .where(
                    WorldIndicator.country_id.in_((country_a.id, country_b.id)),
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
                .order_by(WorldIndicator.country_id, WorldIndicator.code)
            )
        ).scalars().all()
    )


def _match_concept_pair(
    candidates: list[WorldIndicator],
    concept,
    country_a: WorldCountry,
    country_b: WorldCountry,
) -> tuple[WorldIndicator | None, WorldIndicator | None]:
    """Сопоставимый ряд понятия для двух стран (правила _concept_members API).

    Одна страна — один ряд: национальный crosswalk приоритетнее
    eurostat-дубля; денежные понятия сопоставляются по классу меры.
    """
    national_codes = national_codes_for_concept(concept.slug)

    def _match(country: WorldCountry) -> WorldIndicator | None:
        national = [
            ind for ind in candidates
            if ind.country_id == country.id
            and ind.code in national_codes
            and _same_public_unit(ind, concept)
        ]
        if national:
            return national[0]
        eurostat = [
            ind for ind in candidates
            if ind.country_id == country.id
            and ind.code not in national_codes
            and concept_for_indicator(ind) == concept
            and _same_public_unit(ind, concept)
        ]
        return eurostat[0] if eurostat else None

    return _match(country_a), _match(country_b)


async def _load_pair_series(
    db: AsyncSession,
    ind_a: WorldIndicator,
    ind_b: WorldIndicator,
) -> tuple[list[tuple[date, float]], list[tuple[date, float]]]:
    rows = (
        await db.execute(
            select(
                WorldDataPoint.indicator_id,
                WorldDataPoint.date,
                WorldDataPoint.value,
            )
            .where(WorldDataPoint.indicator_id.in_((ind_a.id, ind_b.id)))
            .order_by(WorldDataPoint.indicator_id, WorldDataPoint.date)
        )
    ).all()
    by_id: dict[int, list[tuple[date, float]]] = {ind_a.id: [], ind_b.id: []}
    for indicator_id, point_date, value in rows:
        by_id.setdefault(int(indicator_id), []).append((point_date, float(value)))
    return by_id[ind_a.id], by_id[ind_b.id]


def _value_as_of(series: list[tuple[date, float]], day: date) -> float | None:
    """Последнее значение ряда на дату или раньше (честное as-of соединение)."""
    value: float | None = None
    for point_date, point_value in series:
        if point_date <= day:
            value = point_value
        else:
            break
    return value


async def render_world_vs_html(
    slug_a: str, slug_b: str, concept_slug: str, db: AsyncSession
) -> tuple[int, str]:
    """SSR-страница сравнения двух стран по понятию мира.

    Возвращает (200, html) | (301, canonical_path) | (404, html);
    контракт 301 для роута описан в docstring модуля.
    """
    concept = CONCEPT_BY_SLUG.get(concept_slug)
    if concept is None or "compare" not in concept.enabled_surfaces:
        return 404, "<h1>Показатель сравнения не найден</h1>"

    country_a = await _country(db, slug_a)
    country_b = await _country(db, slug_b)
    if country_a is None or country_b is None:
        return 404, "<h1>Страна не найдена</h1>"
    if slug_a == slug_b:
        return 404, "<h1>Нужны две разные страны</h1>"

    canon_a, canon_b = sorted((slug_a, slug_b))
    if (slug_a, slug_b) != (canon_a, canon_b):
        # Контракт роута: (301, path) → _permanent_redirect(path).
        return 301, world_vs_path(canon_a, canon_b, concept.slug)

    candidates = await _fetch_compare_candidates(db, country_a, country_b)
    ind_a, ind_b = _match_concept_pair(candidates, concept, country_a, country_b)
    if ind_a is None or ind_b is None:
        return 404, "<h1>Нет сопоставимого ряда для одной из стран</h1>"

    raw_a, raw_b = await _load_pair_series(db, ind_a, ind_b)
    mode = ranking_value_mode(
        concept.slug, ((country_a, ind_a), (country_b, ind_b))
    )
    series_a = apply_rank_series(raw_a, mode)
    series_b = apply_rank_series(raw_b, mode)
    if len(series_a) < 2 or len(series_b) < 2 or (
        mode == "level" and (series_a[-1][1] == 0 or series_b[-1][1] == 0)
    ):
        return 404, "<h1>Недостаточно данных для сравнения</h1>"

    loc = get_locale()
    en = loc == "en"
    nat_codes = national_codes_for_concept(concept.slug)

    name = ranking_display_name(
        mode, concept.slug, concept_public_name(concept, locale=loc), locale=loc,
    )
    unit = ranking_public_unit(
        mode, concept_public_unit(concept, locale=loc), locale=loc,
    )
    unit_ru = ranking_public_unit(
        mode, concept_public_unit(concept, locale="ru"), locale="ru",
    )

    def _unit_tail(unit_text: str) -> str:
        """Последний осмысленный сегмент составной единицы после запятой:
        «в постоянных ценах 2015 года, млн евро» → «млн евро»."""
        s = (unit_text or "").strip()
        if "," in s:
            tail = s.rsplit(",", 1)[1].strip()
            if tail and not tail[0].isdigit():
                return tail
        return s

    # Процентная природа ряда: режим «изменение за год» или единица-доля.
    # Значение тогда публикуется со знаком «%», разница — в процентных
    # пунктах (п.п. / pp), без хвостовой базы («экономически активного
    # населения», «ВВП») — база названа в строке единиц.
    pct_like = mode == "yoy" or unit_ru.strip().startswith("%")

    # Национальный ряд в уровне публикуется в своей единице (как в
    # /world/compare/catalog); совпадающая с концептом русская единица
    # локализуется концептом (человек → persons).
    def _row_unit(ind: WorldIndicator) -> str:
        if mode != "level" or ind.code not in nat_codes:
            return unit
        raw = _unit_of(ind)
        if raw == concept_public_unit(concept, locale="ru"):
            return unit
        return (localize_unit(raw) or raw) if en else raw

    unit_a = _row_unit(ind_a)
    unit_b = _row_unit(ind_b)
    shared_unit = unit_a == unit_b

    def _value_sfx(row_unit: str) -> str:
        if pct_like:
            return "%"
        return _unit_tail(row_unit)

    def _dot(text: str) -> str:
        return text if text.rstrip().endswith(".") else f"{text.rstrip()}."

    label_a_name = _country_label(country_a)
    label_b_name = _country_label(country_b)
    gen_a = _genitive(country_a)
    gen_b = _genitive(country_b)

    last_a_date, value_a = series_a[-1]
    last_b_date, value_b = series_b[-1]
    freq_a = normalize_frequency(ind_a.frequency)
    freq_b = normalize_frequency(ind_b.frequency)
    date_label_a = _period_label(last_a_date, freq_a)
    date_label_b = _period_label(last_b_date, freq_b)
    table_freq = (
        "annual" if freq_a == "annual" and freq_b == "annual"
        else (freq_a if freq_a == freq_b else None)
    )

    diff = value_a - value_b
    same = abs(diff) < 5e-9
    diff_text = _fmt(round(abs(diff), 4))
    vsfx = f" {_value_sfx(unit_a)}" if shared_unit else ""
    vsfx_a = f" {_value_sfx(unit_a)}" if not shared_unit else vsfx
    vsfx_b = f" {_value_sfx(unit_b)}" if not shared_unit else vsfx
    diff_sfx = (
        (" п.п." if not en else " pp")
        if pct_like
        else (f" {_unit_tail(unit_a)}" if shared_unit else "")
    )

    if en:
        if last_a_date == last_b_date:
            lead = (
                f"Latest data: {label_a_name} — {_fmt(value_a)}{vsfx_a}, "
                f"{label_b_name} — {_fmt(value_b)}{vsfx_b} (as of {date_label_a})."
            )
        else:
            lead = (
                f"Latest data: {label_a_name} — {_fmt(value_a)}{vsfx_a} "
                f"(as of {date_label_a}), {label_b_name} — {_fmt(value_b)}{vsfx_b} "
                f"(as of {date_label_b})."
            )
        if same:
            verdict = "The values are equal."
        elif diff_sfx:
            verdict = _dot(f"{label_a_name if diff > 0 else label_b_name} is higher by {diff_text}{diff_sfx}")
        else:
            verdict = _dot(f"{label_a_name if diff > 0 else label_b_name} is higher")
    else:
        if last_a_date == last_b_date:
            lead = (
                f"Последние данные: {label_a_name} — {_fmt(value_a)}{vsfx_a}, "
                f"{label_b_name} — {_fmt(value_b)}{vsfx_b} (на {date_label_a})."
            )
        else:
            lead = (
                f"Последние данные: {label_a_name} — {_fmt(value_a)}{vsfx_a} "
                f"(на {date_label_a}), {label_b_name} — {_fmt(value_b)}{vsfx_b} "
                f"(на {date_label_b})."
            )
        if same:
            verdict = "Значения совпадают."
        elif diff_sfx:
            verdict = _dot(
                f"Выше значение у {gen_a if diff > 0 else gen_b}: "
                f"разница — {diff_text}{diff_sfx}"
            )
        else:
            verdict = _dot(f"Выше значение у {gen_a if diff > 0 else gen_b}")

    # Таблица: объединение дат публикации, значения — по ближайшей дате
    # ряда (последнее значение на дату или раньше). Даты до старта более
    # короткого ряда отсекаются, чтобы у обеих стран было значение.
    start = max(series_a[0][0], series_b[0][0])
    merged = sorted({d for d, _ in series_a} | {d for d, _ in series_b})
    table_dates = [d for d in merged if d >= start][-_TABLE_ROWS:]

    def _cell(series: list[tuple[date, float]], day: date) -> str:
        v = _value_as_of(series, day)
        return "—" if v is None else _fmt(v)

    body_rows = "".join(
        f"<tr><td>{escape(_period_label(d, table_freq))}</td>"
        f"<td>{_cell(series_a, d)}</td><td>{_cell(series_b, d)}</td></tr>"
        for d in table_dates
    )
    th_date = "Date" if en else "Дата"
    if shared_unit:
        units_line = f"Units: {unit_a}." if en else f"Единицы: {unit_a}."
    else:
        units_line = (
            f"Units: {unit_a} ({label_a_name}), {unit_b} ({label_b_name})."
            if en
            else f"Единицы: {unit_a} ({label_a_name}), {unit_b} ({label_b_name})."
        )
    table_note = ""
    if last_a_date != last_b_date:
        table_note = (
            f"Values are shown as of the nearest publication date; latest slice: "
            f"{label_a_name} — {date_label_a}, {label_b_name} — {date_label_b}."
            if en
            else (
                f"Значения приведены по ближайшей дате публикации ряда; "
                f"последний срез: {label_a_name} — {date_label_a}, "
                f"{label_b_name} — {date_label_b}."
            )
        )

    canonical = world_vs_path(canon_a, canon_b, concept.slug)
    og_path = og_world_vs_path(canon_a, canon_b, concept.slug)
    period_range = _date_range_ru(
        min(series_a[0][0], series_b[0][0]), max(last_a_date, last_b_date),
    )
    sources = _join_sources([
        _source_label(ind_a.source, ind_a.provider),
        _source_label(ind_b.source, ind_b.provider),
    ])
    compare_href = (
        f"/compare?codes=w:{canon_a}:{concept.slug},w:{canon_b}:{concept.slug}"
    )

    if en:
        h1_text = f"{name}: {label_a_name} vs {label_b_name}"
        title = f"{h1_text} — data comparison"
        desc = (
            f"{name}: {label_a_name} — {_fmt(value_a)}{vsfx_a}, {label_b_name} — "
            f"{_fmt(value_b)}{vsfx_b} by the latest published data. "
            f"Difference — {diff_text}{diff_sfx}. Table of the latest values and "
            f"live comparison. Source: {sources}."
        )
        eyebrow = "Country comparison"
        h2_table = "Latest values"
        cta_h2 = "Compare live"
        cta_p = (
            f'Interactive comparison of the two series with period and mode '
            f'controls — <a href="{escape(compare_href)}">on the comparison '
            f'page</a>. Country profiles: '
            f'<a href="{escape(paths.country(canon_a))}">{escape(label_a_name)}</a>, '
            f'<a href="{escape(paths.country(canon_b))}">{escape(label_b_name)}</a>.'
        )
        h2_other = "Other indicators to compare"
        h2_source = "Data source"
        chart_alt = (
            f"{name}: {label_a_name} vs {label_b_name} — comparison of the "
            f"latest values, {label_a_name} {_fmt(value_a)}{vsfx_a}, "
            f"{label_b_name} {_fmt(value_b)}{vsfx_b}"
        )
        figcaption = (
            f"{name}: {label_a_name} and {label_b_name}, {period_range}. "
            f"Source: {sources}. forecasteconomy.com"
        )
        keywords = (
            f"{label_a_name} vs {label_b_name} {name.lower()}, "
            f"{label_a_name} {label_b_name} comparison, {name.lower()} by country"
        )
    else:
        h1_text = f"{name}: {label_a_name} против {gen_b}"
        title = f"{h1_text} — сравнение данных"
        desc = (
            f"{name}: {label_a_name} — {_fmt(value_a)}{vsfx_a}, {label_b_name} — "
            f"{_fmt(value_b)}{vsfx_b} по последним опубликованным данным. "
            f"Разница — {diff_text}{diff_sfx}. Таблица последних значений и "
            f"живое сравнение. Источник: {sources}."
        )
        eyebrow = "Сравнение стран"
        h2_table = "Последние значения"
        cta_h2 = "Сравнить вживую"
        cta_p = (
            f'Интерактивное сравнение этих двух рядов с выбором периода — '
            f'<a href="{escape(compare_href)}">на странице сравнения</a>. '
            f'Профили стран: '
            f'<a href="{escape(paths.country(canon_a))}">{escape(label_a_name)}</a>, '
            f'<a href="{escape(paths.country(canon_b))}">{escape(label_b_name)}</a>.'
        )
        h2_other = "Другие показатели для сравнения"
        h2_source = "Источник данных"
        chart_alt = (
            f"{name}: {label_a_name} против {gen_b} — сравнение последних "
            f"значений, {label_a_name} {_fmt(value_a)}{vsfx_a}, "
            f"{label_b_name} {_fmt(value_b)}{vsfx_b}"
        )
        figcaption = (
            f"{name}: {label_a_name} и {label_b_name}, {period_range}. "
            f"Источник: {sources}. forecasteconomy.com"
        )
        keywords = (
            f"{label_a_name} или {label_b_name} — {name.lower()}, "
            f"сравнение {label_a_name} и {label_b_name}, "
            f"{name.lower()} {label_a_name} {label_b_name}"
        )

    figure_html = (
        f'<figure class="seo-chart"><a class="seo-chart-link" '
        f'href="{escape(compare_href)}">'
        f'<img src="{escape(og_path)}" alt="{escape(chart_alt)}" '
        f'width="1200" height="630" loading="eager"></a>'
        f"<figcaption>{escape(figcaption)}</figcaption></figure>"
    )

    other_items: list[tuple[str, str]] = []
    for other in WORLD_CONCEPTS:
        if other.slug == concept.slug or "compare" not in other.enabled_surfaces:
            continue
        other_a, other_b = _match_concept_pair(candidates, other, country_a, country_b)
        if other_a is None or other_b is None:
            continue
        other_mode = ranking_value_mode(
            other.slug, ((country_a, other_a), (country_b, other_b))
        )
        other_name = ranking_display_name(
            other_mode,
            other.slug,
            concept_public_name(other, locale=loc),
            locale=loc,
        )
        other_items.append((world_vs_path(canon_a, canon_b, other.slug), other_name))
        if len(other_items) >= _OTHER_CONCEPTS_LIMIT:
            break
    other_section = ""
    if other_items:
        links = "".join(
            f'<li><a href="{escape(href)}">{escape(label)}</a></li>'
            for href, label in other_items
        )
        other_section = (
            f'<section class="seo-section"><h2>{escape(h2_other)}</h2>'
            f'<ul class="seo-pills">{links}</ul></section>'
        )

    method_sentence = ranking_period_method(mode, locale=loc)
    date_sentence = _period_sentence(
        max(last_a_date, last_b_date).isoformat(),
        freq="annual" if table_freq == "annual" else None,
    )
    source_phrase = f"Source: {sources}." if en else f"Источник: {sources}."
    source_parts = [f"<p>{escape(method_sentence)}</p>"]
    if date_sentence:
        source_parts.append(f"<p>{escape(date_sentence)}</p>")
    source_parts.append(f"<p>{escape(source_phrase)}</p>")

    trail = crumbs.tool_trail(h1_text, canonical)

    json_ld = [
        _site_json_ld(),
        _breadcrumbs(trail),
    ]
    for ind, country, series, unit_label in (
        (ind_a, country_a, series_a, unit_a),
        (ind_b, country_b, series_b, unit_b),
    ):
        json_ld.append({
            "@context": "https://schema.org",
            "@type": "Dataset",
            "name": f"{name} — {_country_label(country)}",
            "description": desc,
            "url": _absolute(canonical),
            "inLanguage": in_language(),
            "creator": {
                "@type": "Organization",
                "name": _source_label(ind.source, ind.provider),
            },
            "temporalCoverage": f"{_iso_date(series[0][0])}/{_iso_date(series[-1][0])}",
            "spatialCoverage": _country_label(country),
            "variableMeasured": f"{name}, {unit_label}",
            "image": _absolute(og_path),
        })
    json_ld.append({
        "@context": "https://schema.org",
        "@type": "ImageObject",
        "contentUrl": _absolute(og_path),
        "url": _absolute(og_path),
        "width": 1200,
        "height": 630,
        "name": title,
        "caption": chart_alt,
        "representativeOfPage": True,
    })

    table_note_html = f"<p>{escape(table_note)}</p>" if table_note else ""
    body = f"""<div class="seo-page">
{_breadcrumbs_nav(trail)}
<p class="seo-eyebrow">{escape(eyebrow)}</p>
<h1>{escape(h1_text)}</h1>
<p>{escape(lead)} {escape(verdict)}</p>
{figure_html}
<section class="seo-section"><h2>{escape(h2_table)}</h2>
<p>{escape(units_line)}</p>
<div class="seo-scroll"><table><thead><tr><th>{escape(th_date)}</th><th>{escape(label_a_name)}</th><th>{escape(label_b_name)}</th></tr></thead><tbody>{body_rows}</tbody></table></div>
{table_note_html}</section>
<section class="seo-section"><h2>{escape(cta_h2)}</h2>
<p>{cta_p}</p>
</section>
{other_section}
<section class="seo-section"><h2>{escape(h2_source)}</h2>
{''.join(source_parts)}</section>
</div>"""

    html = await build_document(
        title=title,
        description=desc,
        canonical_path=canonical,
        body=body,
        json_ld=json_ld,
        keywords=keywords,
        og_image=_absolute(og_path),
        # SPA-роута /{a}-vs-{b}/{concept} нет (App.jsx знает только
        # /russia/region-vs/:pair) — чистый SSR с брендовым хромом.
        include_app=False,
    )
    return 200, html

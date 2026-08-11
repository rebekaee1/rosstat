"""SSR-рендер раздела «Мировая экономика»: /world, /world/{slug}, /world/{slug}/{code}.

По образцу seo_regional.py (ADR-0003): видимый контент + meta + JSON-LD +
картинка-график тремя путями (og:image, ImageObject, <img class="seo-chart">).
Прогнозов нет. Источник в публичных текстах — «Евростат» (без внутренних
идентификаторов наборов и технического жаргона).
"""

from __future__ import annotations

from datetime import date
from html import escape

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.eurostat_titles_ru import country_prepositional
from app.data.eurostat_units_ru import unit_suffix
from app.data.legacy_redirects import (
    strip_world_frequency_suffix,
    world_card_primary_rank,
    world_card_siblings,
)
from app.models import WorldCountry, WorldDataPoint, WorldIndicator
from app.services.display import format_date_ru, format_month_ru, format_number_ru
from app.services.seo_renderer import DOMAIN, _breadcrumbs, build_document

_SOURCE_PUBLIC = "Евростат"

_WORLD_TITLE = "Мировая экономика — статистика стран Европы"
_WORLD_DESC = (
    "Официальная статистика по странам Европы: цены, ВВП, рынок труда, "
    "торговля и финансы. Графики и таблицы по данным Евростата на Forecast Economy."
)

# Родительный падеж для заголовков «Экономика {страны}».
# Nominative в БД (name_ru); для публичных фраз нужен genitive.
_COUNTRY_GENITIVE: dict[str, str] = {
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
    return _COUNTRY_GENITIVE.get(country.slug, country.name_ru)


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
        href = f"/world/{escape(slug)}/{escape(primary.code)}?mode=level-{escape(freq)}"
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


def _source_label(raw: str | None) -> str:
    """Публичное имя источника: всегда «Евростат», без латиницы/жаргона."""
    if not raw:
        return _SOURCE_PUBLIC
    low = raw.strip().lower()
    if low in ("eurostat", "евростат"):
        return _SOURCE_PUBLIC
    # На всякий случай не пропускаем латинские имена источников наружу.
    if any(c.isascii() and c.isalpha() for c in raw):
        return _SOURCE_PUBLIC
    return raw.strip() or _SOURCE_PUBLIC


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
        f'<li><a href="/world/{escape(c.slug)}">{escape(c.name_ru)}</a>'
        f" — {_n_indicators_phrase(int(cnt or 0))}</li>"
        for c, cnt in rows
        if int(cnt or 0) > 0
    )

    body = f"""<div class="seo-page">
<nav><a href="/">Главная</a> → Мировая экономика</nav>
<p class="seo-eyebrow">Официальная статистика стран Европы</p>
<h1>Мировая экономика: статистика по странам Европы</h1>
<p>Раздел собирает официальные ряды Евростата по странам Европы —
цены, валовой внутренний продукт, рынок труда, внешняя торговля и финансы.
Сейчас доступны данные по {n_countries} странам и {_n_indicators_phrase(n_listed)}
с графиками динамики и таблицами значений. Источник — Евростат.</p>
<section class="seo-section"><h2>Страны</h2><ul>{links}</ul></section>
<section class="seo-section"><h2>Россия и сравнение</h2>
<p>Макроэкономика России — в разделе
<a href="/">главной витрины</a> и каталоге
<a href="/category/prices">цен</a>,
<a href="/category/gdp">ВВП</a> и
<a href="/category/labor">рынка труда</a>.
Сопоставить ряды можно на странице
<a href="/compare">сравнения индикаторов</a>.</p></section>
</div>"""

    json_ld = [_breadcrumbs([("/", "Главная"), ("/world", "Мировая экономика")])]
    html = await build_document(
        title=_WORLD_TITLE,
        description=_WORLD_DESC,
        canonical_path="/world",
        body=body,
        json_ld=json_ld,
        keywords=(
            "мировая экономика статистика, экономика стран европы, "
            "евростат данные, инфляция европы, ввп стран европы"
        ),
        og_image=f"{DOMAIN}/og.png",
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
            f"<tr><td><a href=\"/world/{escape(slug)}/{escape(ind.code)}\">"
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
            f'<li><a href="/world/{escape(slug)}/{escape(ind.code)}">'
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
            f'<li><a href="/world/{escape(n.slug)}">{escape(n.name_ru)}</a></li>'
            for n in neighbors
        )
        neighbors_html = (
            '<section class="seo-section"><h2>Другие страны</h2>'
            f'<ul class="seo-pills">{nlinks}</ul></section>'
        )

    og_path = f"/og/world/{slug}.png"
    n_ind = len(inds)
    gen = _genitive(country)
    n_phrase = _n_indicators_phrase(n_ind)
    title = f"Экономика {gen}: статистика и показатели"
    desc = (
        f"{country.name_ru}: {n_phrase} Евростата — цены, ВВП, "
        f"рынок труда, торговля и финансы. Графики и последние значения "
        f"на Forecast Economy."
    )
    figure_alt = (
        f"Экономика {gen} — сводка ключевых показателей, "
        f"источник Евростат"
    )
    figure_html = (
        f'<figure class="seo-chart"><img src="{escape(og_path)}" '
        f'alt="{escape(figure_alt)}" width="1200" height="630" loading="eager">'
        f"<figcaption>Ключевые показатели экономики {escape(gen)}. "
        f"Источник: {_SOURCE_PUBLIC}. forecasteconomy.com</figcaption></figure>"
    )

    n_sections = len(by_cat)
    body = f"""<div class="seo-page">
<nav><a href="/">Главная</a> → <a href="/world">Мировая экономика</a> → {escape(country.name_ru)}</nav>
<p class="seo-eyebrow">Статистика Евростата — {escape(country.name_ru)}</p>
<h1>Экономика {escape(gen)}: статистика и показатели</h1>
<p>Официальные ряды Евростата для {escape(gen)}:
{n_phrase} в {n_sections} разделах — цены, ВВП, рынок труда,
внешняя торговля, финансы и другие темы. У каждого показателя — график
динамики, таблица значений и ссылка на первоисточник.</p>
{figure_html}
<section class="seo-section"><h2>Ключевые показатели</h2>{key_table}</section>
{''.join(sections)}
{neighbors_html}
<section class="seo-section"><h2>Источник данных</h2>
<p>Данные публикует {_SOURCE_PUBLIC}. На сайте ряды приведены в единицах
источника; дата последнего значения указана у каждого показателя.</p></section>
<section class="seo-section"><h2>Россия</h2>
<p>Сопоставить с российскими рядами можно в
<a href="/compare">сравнении индикаторов</a> и на
<a href="/">главной витрине</a> Forecast Economy.</p></section>
</div>"""

    json_ld = [
        _breadcrumbs([
            ("/", "Главная"),
            ("/world", "Мировая экономика"),
            (f"/world/{slug}", country.name_ru),
        ]),
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
        canonical_path=f"/world/{slug}",
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
    source = _source_label(indicator.source)
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
            f"{display} в {prep} — официальный ряд {_SOURCE_PUBLIC}. "
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

    og_path = f"/og/world/{slug}/{code}.png"
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
            f'<li><a href="/world/{escape(s)}/{escape(c)}">'
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
            f'<li><a href="/world/{escape(slug)}/{escape(s.code)}">'
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
        _breadcrumbs([
            ("/", "Главная"),
            ("/world", "Мировая экономика"),
            (f"/world/{slug}", country.name_ru),
            (f"/world/{slug}/{code}", display),
        ]),
        {
            "@context": "https://schema.org",
            "@type": "Dataset",
            "name": f"{display} в {prep}",
            "description": (
                f"{display}"
                + (f" ({unit})" if unit else "")
                + f" в {prep}, {period}. Источник: {source}."
            ),
            "url": f"{DOMAIN}/world/{slug}/{code}",
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
<nav><a href="/">Главная</a> → <a href="/world">Мировая экономика</a> → <a href="/world/{escape(slug)}">{escape(country.name_ru)}</a> → {escape(display)}</nav>
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
        canonical_path=f"/world/{slug}/{code}",
        body=body,
        json_ld=json_ld,
        keywords=(
            f"{display} {country.name_ru}, {country.name_ru} "
            f"{display} график, {country.name_ru} статистика"
        ),
        og_image=f"{DOMAIN}{og_path}",
    )
    return 200, html

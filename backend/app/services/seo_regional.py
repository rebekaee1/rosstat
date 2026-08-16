"""SSR-рендер регионального блока: /russia/region, /russia/region/{slug},
/russia/region/{slug}/{code}, /russia/region-rating/{code}, /russia/region/map/{code}.

Каждая страница регион-показателя получает уникальный автоконтент из данных:
текущее значение, динамика за год/5 лет/весь период, место в рейтинге регионов,
сравнение с общероссийским уровнем, полная таблица значений, видимый график
(/og/region/...) для Яндекс.Картинок и Алисы. Это ~39 тыс. страниц с
осмысленным контентом — по образцу макроблока (ADR-0003), но в своём модуле.

Рейтинги (/russia/region-rating/{code}) — программатик-страницы под спрос
«топ регионов по X», «где самая высокая/низкая X»: полная ранжированная
таблица всех субъектов по последнему году + лидеры/аутсайдеры/РФ.

Карта (/russia/region/map/{code}?year=YYYY) — интерактивная choropleth-поверхность
(SPA hydrates); SSR даёт title/description/OG/JSON-LD для шаринга и краулеров.
Это НЕ рейтинг: рейтинг = таблица мест, карта = пространственный срез + год.
Legacy query `/regions?view=map&indicator=&year=` → 301 на канон (seo_pages).
"""

from html import escape

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.region_indicator_polarity import (
    region_rating_is_achievement,
    region_rating_order_by,
)
from app.models import Region, RegionDataPoint, RegionIndicator
from app.services import breadcrumbs as crumbs
from app.services import site_paths as paths
from app.services.seo_renderer import (
    DOMAIN,
    _breadcrumbs,
    _breadcrumbs_nav,
    build_document,
)

# Мост «регион ↔ макро»: table_code сборника → код макро-индикатора.
# Единая точка истины: отсюда берут и SSR (ссылка на общероссийскую карточку),
# и API каталога (`/regions/catalog` отдаёт `macro_code` фронту — кросс-ссылки
# на карточках и обратный маппинг для блока «По регионам» макро-карточки).
MACRO_BY_TABLE = {
    "1.1": "population",
    "3.4": "wages-nominal",
    "2.10.1": "unemployment",
    "20.1": "cpi",
    "8.1": "gdp-nominal",
    "10.1": "capital-investment",
}

_REGIONS_TITLE = "Регионы России — социально-экономические показатели 85 субъектов РФ"
_REGIONS_DESC = (
    "Статистика по 85 регионам России: население, зарплаты, ВРП, безработица, "
    "инвестиции, цены — 489 показателей Росстата с 1990 года. Графики, "
    "рейтинги регионов, сравнение с общероссийским уровнем."
)

# Дефолтный чип карты на фронте (MAP_METRICS[0]) — общий канон для 301
# `/regions?view=map` без indicator и для sitemap-хаба.
DEFAULT_MAP_CODE = (
    "srednemesyachnaya-nominalnaya-nachislennaya-zarabotnaya-plata-rabotnikov-organizatsiy"
)
MAP_OVERVIEW_CODE = "overview"


def _fmt(value: float) -> str:
    """Русская типографика: пробел-разряды, запятая-дробь, без хвостовых нулей."""
    if value is None:
        return "—"
    v = float(value)
    digits = 0 if abs(v) >= 1000 else (1 if abs(v) >= 1 else 2)
    text = f"{v:,.{digits}f}".replace(",", "\u202f").replace(".", ",")
    if "," in text:
        text = text.rstrip("0").rstrip(",")
    return text


def _times_word(times: float) -> str:
    """«в 2,5 раза» / «в 45 раз» — согласование с дробностью и величиной."""
    rounded = round(times, 1)
    word = "раза" if rounded != int(rounded) or int(rounded) in (2, 3, 4) else "раз"
    return f"в {_fmt(rounded)} {word}"


def _pct(cur: float, base: float) -> str | None:
    """Фраза динамики: «вырос на 22,2%» / «вырос в 44,6 раза» / «снизился…»."""
    if base is None or cur is None or base == 0:
        return None
    pct = (cur - base) / abs(base) * 100
    if abs(pct) < 0.05:
        return "практически не изменился"
    verb = "вырос" if pct > 0 else "снизился"
    if pct >= 200 and base > 0:
        return f"{verb} {_times_word(cur / base)}"
    return f"{verb} на {_fmt(round(abs(pct), 1))}%"


async def _region(db: AsyncSession, slug: str) -> Region | None:
    return (await db.execute(select(Region).where(Region.slug == slug))).scalar_one_or_none()


async def render_regions_home_html(db: AsyncSession) -> tuple[int, str]:
    regions = (await db.execute(
        select(Region).order_by(Region.sort_order)
    )).scalars().all()
    n_ind = (await db.execute(select(func.count()).select_from(RegionIndicator))).scalar()
    if not regions:
        return 404, "<h1>Регионы не найдены</h1>"

    districts = [r for r in regions if r.kind == "district"]
    by_district: dict[str, list[Region]] = {}
    for r in regions:
        if r.kind == "region":
            by_district.setdefault(r.district_slug or "", []).append(r)

    n_regions = sum(len(v) for v in by_district.values())
    sections = []
    for d in districts:
        links = "".join(
            f'<li><a href="{escape(paths.region(r.slug))}">{escape(r.name)}</a></li>'
            for r in by_district.get(d.slug, [])
        )
        sections.append(
            f"<section class=\"seo-section\"><h2>{escape(d.name)}</h2><ul>{links}</ul></section>"
        )

    # Точка входа робота в рейтинги и карту: ключевые показатели с мостом в макро.
    rating_inds = (await db.execute(
        select(RegionIndicator.code, RegionIndicator.name)
        .where(RegionIndicator.table_code.in_(list(MACRO_BY_TABLE)),
               RegionIndicator.is_listed.is_(True))
        .order_by(RegionIndicator.section_num)
    )).all()
    ratings_html = ""
    if rating_inds:
        rating_items = "".join(
            f'<li><a href="{escape(paths.region_rating(c))}">Рейтинг: {escape(n)}</a></li>'
            for c, n in rating_inds
        )
        map_items = "".join(
            f'<li><a href="{escape(paths.region_map(c))}">Карта: {escape(n)}</a></li>'
            for c, n in rating_inds
        )
        ratings_html = (
            f"<section class=\"seo-section\"><h2>Рейтинги и карта регионов</h2>"
            f"<p>Все субъекты РФ по значению показателя: полная таблица мест "
            f"или интерактивная карта с выбором года.</p>"
            f"<h3>Рейтинги</h3><ul>{rating_items}</ul>"
            f"<h3>Карта</h3><ul>{map_items}</ul></section>"
        )

    body = f"""<div class="seo-page">
{_breadcrumbs_nav(crumbs.regions_trail())}
<p class="seo-eyebrow">Региональная статистика Росстата</p>
<h1>Регионы России: социально-экономические показатели</h1>
<p>Официальная статистика по {n_regions} субъектам Российской Федерации:
население, занятость и зарплаты, уровень жизни, валовой региональный продукт,
инвестиции, промышленность, сельское хозяйство, строительство, торговля,
транспорт, наука и цены. Всего {n_ind} показателей с 1990 года по данным
сборника Росстата «Регионы России. Социально-экономические показатели».</p>
{ratings_html}
{''.join(sections)}
</div>"""

    json_ld = [_breadcrumbs(crumbs.regions_trail())]
    html = await build_document(
        title=_REGIONS_TITLE,
        description=_REGIONS_DESC,
        canonical_path=paths.region_hub(),
        body=body,
        json_ld=json_ld,
        keywords="регионы россии статистика, экономика регионов, показатели субъектов рф",
    )
    return 200, html


async def render_region_html(slug: str, db: AsyncSession) -> tuple[int, str]:
    region = await _region(db, slug)
    if region is None or region.kind not in ("region", "district", "country"):
        return 404, "<h1>Регион не найден</h1>"

    inds = (await db.execute(
        select(RegionIndicator)
        .where(RegionIndicator.is_listed.is_(True))
        .order_by(RegionIndicator.section_num, RegionIndicator.code)
    )).scalars().all()

    # последние значения всех показателей региона
    rn = func.row_number().over(
        partition_by=RegionDataPoint.indicator_id,
        order_by=RegionDataPoint.year.desc(),
    ).label("rn")
    sub = (
        select(RegionDataPoint.indicator_id, RegionDataPoint.year, RegionDataPoint.value, rn)
        .where(RegionDataPoint.region_id == region.id)
        .subquery()
    )
    latest = {
        iid: (year, float(value))
        for iid, year, value in (await db.execute(
            select(sub.c.indicator_id, sub.c.year, sub.c.value).where(sub.c.rn == 1)
        )).all()
    }

    sections: dict[int, list[str]] = {}
    section_names: dict[int, str] = {}
    n_present = 0
    for ind in inds:
        got = latest.get(ind.id)
        if got is None:
            continue
        n_present += 1
        year, value = got
        unit = f" {escape(ind.unit)}" if ind.unit else ""
        sections.setdefault(ind.section_num, []).append(
            f'<li><a href="{escape(paths.region_indicator(slug, ind.code))}">{escape(ind.name)}</a>'
            f' — {_fmt(value)}{unit} ({year})</li>'
        )
        section_names[ind.section_num] = ind.section_name

    n_catalog = len(inds)
    section_html = "".join(
        f"<section class=\"seo-section\"><h2>{escape(section_names[num])}</h2>"
        f"<ul>{''.join(items)}</ul></section>"
        for num, items in sorted(sections.items())
    )

    title = f"{region.name} — статистика региона: население, зарплата, ВРП, цены"
    desc = (
        f"{region.name}: {n_catalog} показателей в каталоге Росстата"
        + (f", данные по региону — {n_present}" if n_present < n_catalog else "")
        + f" с 1990 года — население, зарплаты, безработица, ВРП, инвестиции, "
        f"строительство, цены. Графики и место региона в рейтингах России."
    )
    catalog_line = (
        f"{n_catalog} показателей в каталоге; по региону — данные по {n_present}"
        if n_present < n_catalog
        else f"{n_catalog} показателей"
    )
    # Выход к РФ и флагманским рейтингам: профиль иначе замыкается на свои
    # показатели и не отдаёт боту путь «регион → Россия / рейтинг».
    flagship = (await db.execute(
        select(RegionIndicator.code, RegionIndicator.name)
        .where(
            RegionIndicator.table_code.in_(list(MACRO_BY_TABLE)),
            RegionIndicator.is_listed.is_(True),
        )
        .order_by(RegionIndicator.section_num)
        .limit(6)
    )).all()
    cross_items = [
        f'<li><a href="{paths.region_hub()}">Все регионы России</a></li>',
    ]
    if slug != "russia":
        cross_items.append(
            f'<li><a href="{paths.region("russia")}">Российская Федерация — сводные показатели</a></li>'
        )
    cross_items.extend(
        f'<li><a href="{escape(paths.region_rating(c))}">{escape(n)}</a></li>'
        for c, n in flagship
    )
    cross_html = (
        '<section class="seo-section"><h2>Смотрите также</h2>'
        f'<ul>{"".join(cross_items)}</ul></section>'
    )
    body = f"""<div class="seo-page">
{_breadcrumbs_nav(crumbs.region_trail(region.name, paths.region(slug)))}
<p class="seo-eyebrow">Региональная статистика Росстата</p>
<h1>{escape(region.name)}: социально-экономические показатели</h1>
<p>Официальные данные Росстата по региону {escape(region.name)}: {catalog_line}
в {len(sections)} разделах — от численности населения и заработной платы до валового
регионального продукта, инвестиций и потребительских цен. Ряды с 1990 года,
по каждому показателю — график динамики и место региона среди субъектов РФ.</p>
{section_html}
{cross_html}
</div>"""

    json_ld = [
        _breadcrumbs(crumbs.region_trail(region.name, paths.region(slug))),
    ]
    html = await build_document(
        title=title,
        description=desc,
        canonical_path=paths.region(slug),
        body=body,
        json_ld=json_ld,
        keywords=(
            f"{region.name} статистика, {region.name} экономика, {region.name} население, "
            f"{region.name} зарплата, {region.name} врп"
        ),
    )
    return 200, html


def _rank_phrase(
    position: int,
    total: int,
    *,
    achievement: bool = False,
) -> str:
    """Фраза места региона. Для неизвестной полярности — нейтрально по величине."""
    if achievement:
        if position <= 3:
            return f"входит в тройку лучших среди {total} субъектов РФ"
        if position <= 10:
            return f"входит в десятку лучших среди {total} субъектов РФ"
        if position > total - 5:
            return f"находится в конце рейтинга — {position}-е место из {total}"
        return f"занимает {position}-е место из {total}"
    if position <= 3:
        return f"входит в тройку регионов с наибольшим значением среди {total} субъектов РФ"
    if position <= 10:
        return f"входит в десятку регионов с наибольшим значением среди {total} субъектов РФ"
    if position > total - 5:
        return (
            f"находится в конце списка по величине показателя — "
            f"{position}-е положение из {total}"
        )
    return f"занимает {position}-е положение в списке по величине показателя из {total}"


def _rating_copy(*, achievement: bool) -> dict[str, str]:
    """Подписи рейтинга: достижение vs нейтральный список по величине."""
    if achievement:
        return {
            "eyebrow": "рейтинг регионов",
            "h1_suffix": "рейтинг регионов России",
            "intro_lead": "Первые места занимают",
            "intro_tail": "Замыкает рейтинг",
            "table_col": "Место",
            "section_h2": "Полный рейтинг",
            "best_tile": "Лучшее значение",
            "worst_tile": "Наихудшее значение",
            "figcaption": "регионы с лучшими значениями",
            "map_leaders_h2": "Лидеры",
            "faq_best_q": "У какого региона лучшее значение показателя",
            "faq_best_a_lead": "первое место занимает",
            "faq_worst_q": "У какого региона наихудшее значение?",
            "faq_worst_a_lead": "Наихудшее значение у региона",
            "desc_best": "Лучшее значение",
            "meta_rank_word": "рейтинг",
        }
    return {
        "eyebrow": "сравнение регионов",
        "h1_suffix": "сравнение регионов России",
        "intro_lead": "Наибольшие значения у регионов",
        "intro_tail": "Наименьшее значение у региона",
        "table_col": "№",
        "section_h2": "Список регионов по величине показателя",
        "best_tile": "Наибольшее значение",
        "worst_tile": "Наименьшее значение",
        "figcaption": "регионы с наибольшими значениями",
        "map_leaders_h2": "Наибольшие значения",
        "faq_best_q": "У какого региона наибольшее значение показателя",
        "faq_best_a_lead": "наибольшее значение у региона",
        "faq_worst_q": "У какого региона наименьшее значение?",
        "faq_worst_a_lead": "Наименьшее значение у региона",
        "desc_best": "Наибольшее значение",
        "meta_rank_word": "сравнение",
    }


async def render_region_rating_html(code: str, db: AsyncSession) -> tuple[int, str]:
    """Рейтинг всех регионов по показателю: /russia/region-rating/{code}."""
    indicator = (await db.execute(
        select(RegionIndicator).where(
            RegionIndicator.code == code, RegionIndicator.is_listed.is_(True)
        )
    )).scalar_one_or_none()
    if indicator is None:
        return 404, "<h1>Показатель не найден</h1>"

    last_year = (await db.execute(
        select(func.max(RegionDataPoint.year))
        .join(Region, Region.id == RegionDataPoint.region_id)
        .where(RegionDataPoint.indicator_id == indicator.id, Region.kind == "region")
    )).scalar_one_or_none()
    if last_year is None:
        return 404, "<h1>Нет данных</h1>"

    achievement = region_rating_is_achievement(indicator.code, indicator.table_code)
    copy = _rating_copy(achievement=achievement)
    rows = (await db.execute(
        select(Region.slug, Region.name, RegionDataPoint.value)
        .join(Region, Region.id == RegionDataPoint.region_id)
        .where(RegionDataPoint.indicator_id == indicator.id,
               RegionDataPoint.year == last_year,
               Region.kind == "region")
        .order_by(region_rating_order_by(
            RegionDataPoint.value, indicator.code, indicator.table_code
        ))
    )).all()
    if len(rows) < 10:
        return 404, "<h1>Недостаточно данных</h1>"

    unit = indicator.unit or ""
    total = len(rows)
    top = rows[:3]
    bottom = rows[-3:]

    rf_value = None
    rf = await _region(db, "russia")
    if rf:
        rf_value = (await db.execute(
            select(RegionDataPoint.value)
            .where(RegionDataPoint.indicator_id == indicator.id,
                   RegionDataPoint.region_id == rf.id,
                   RegionDataPoint.year == last_year)
        )).scalar_one_or_none()

    def _vu(v) -> str:
        return f"{_fmt(float(v))} {unit}".strip()

    top_names = ", ".join(f"{n} ({_vu(v)})" for _s, n, v in top)
    list_word = "Рейтинг" if achievement else "Сравнение"
    intro = (
        f"{list_word} {total} субъектов Российской Федерации по показателю "
        f"«{indicator.name}» за {last_year} год. {copy['intro_lead']}: {top_names}. "
        f"{copy['intro_tail']} {bottom[-1][1]} — {_vu(bottom[-1][2])}."
    )
    if rf_value is not None:
        intro += f" Значение по России в целом — {_vu(rf_value)}."

    table_rows = "".join(
        f"<tr><td>{i}</td>"
        f'<td><a href="{escape(paths.region_indicator(s, code))}">{escape(n)}</a></td>'
        f"<td>{_fmt(float(v))}</td></tr>"
        for i, (s, n, v) in enumerate(rows, 1)
    )
    table_html = (
        f'<div class="seo-scroll"><table><thead><tr><th>{escape(copy["table_col"])}</th>'
        f"<th>Регион</th>"
        f"<th>{escape(unit or 'Значение')}</th></tr></thead>"
        f"<tbody>{table_rows}</tbody></table></div>"
    )

    faq_best_a = (
        f"По итогам {last_year} года {copy['faq_best_a_lead']} {top[0][1]} — {_vu(top[0][2])}."
    )
    faq = [
        (f"{copy['faq_best_q']} «{indicator.name}»?", faq_best_a),
        (copy["faq_worst_q"],
         f"{copy['faq_worst_a_lead']} {bottom[-1][1]} — {_vu(bottom[-1][2])}."),
        (f"За какой год приведены данные и откуда они?",
         f"Данные за {last_year} год из сборника Росстата "
         f"«Регионы России. Социально-экономические показатели»."),
    ]
    faq_html = "<section class=\"seo-section\"><h2>Вопросы и ответы</h2>" + "".join(
        f'<div class="seo-faq"><h3>{escape(q)}</h3><p>{escape(a)}</p></div>' for q, a in faq
    ) + "</section>"

    siblings = (await db.execute(
        select(RegionIndicator.code, RegionIndicator.name)
        .where(RegionIndicator.section_num == indicator.section_num,
               RegionIndicator.code != code,
               RegionIndicator.is_listed.is_(True))
        .order_by(RegionIndicator.code)
        .limit(12)
    )).all()
    siblings_html = ""
    if siblings:
        sib_h2 = (
            f"Другие рейтинги раздела «{escape(indicator.section_name)}»"
            if achievement
            else f"Другие показатели раздела «{escape(indicator.section_name)}»"
        )
        items = "".join(
            f'<li><a href="{escape(paths.region_rating(c))}">{escape(n)}</a></li>'
            for c, n in siblings
        )
        siblings_html = (
            f"<section class=\"seo-section\"><h2>{sib_h2}</h2>"
            f"<ul class=\"seo-pills\">{items}</ul></section>"
        )

    macro_code = MACRO_BY_TABLE.get(indicator.table_code or "")
    macro_html = ""
    if macro_code:
        macro_html = (
            f"<section class=\"seo-section\"><h2>Общероссийская динамика</h2>"
            f"<p>Показатель по России в целом, с более частым обновлением и прогнозом — "
            f"на карточке <a href=\"{escape(paths.russia_indicator(macro_code))}\">общероссийского "
            f"индикатора</a>.</p></section>"
        )

    title = (
        f"Рейтинг регионов России: {indicator.name} ({last_year})"
        if achievement
        else f"{indicator.name} по регионам России ({last_year})"
    )
    desc = (
        f"{indicator.name} по регионам России за {last_year} год: "
        f"{copy['meta_rank_word']} всех {total} субъектов РФ. "
        f"{copy['desc_best']} — {top[0][1]} ({_vu(top[0][2])}). "
        f"Полная таблица, данные Росстата."
    )

    crumb_label = (
        f"Рейтинг: {indicator.name}" if achievement else indicator.name
    )
    rating_trail = crumbs.region_rating_trail(crumb_label, paths.region_rating(code))
    json_ld = [
        _breadcrumbs(rating_trail),
        {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": q,
                 "acceptedAnswer": {"@type": "Answer", "text": a}}
                for q, a in faq
            ],
        },
        {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "name": title,
            "numberOfItems": total,
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": i,
                    "name": n,
                    "url": f"{DOMAIN}{paths.region_indicator(s, code)}",
                }
                for i, (s, n, _v) in enumerate(rows[:10], 1)
            ],
        },
    ]

    rf_tile = ""
    if rf_value is not None:
        rf_tile = f'<div class="seo-tile"><span>Россия в целом</span><b>{escape(_vu(rf_value))}</b></div>'
    tiles_html = f"""<div class="seo-tiles">
<div class="seo-tile"><span>{escape(copy["best_tile"])} — {escape(top[0][1])}</span><b>{escape(_vu(top[0][2]))}</b></div>
{rf_tile}
<div class="seo-tile"><span>{escape(copy["worst_tile"])} — {escape(bottom[-1][1])}</span><b>{escape(_vu(bottom[-1][2]))}</b></div>
<div class="seo-tile"><span>Данные за</span><b>{last_year} год</b></div>
</div>"""

    og_path = paths.og_region_rating(code)
    rating_alt = (
        f"{indicator.name} по регионам России — {copy['meta_rank_word']} {last_year} года, "
        f"{copy['desc_best'].lower()} — {top[0][1]} ({_vu(top[0][2])})"
    )
    figure_html = (
        f'<figure class="seo-chart"><img src="{escape(og_path)}" alt="{escape(rating_alt)}" '
        f'width="1200" height="630" loading="eager">'
        f"<figcaption>{escape(indicator.name)}: {escape(copy['figcaption'])}, {last_year} год. "
        f"Источник: Росстат. forecasteconomy.com</figcaption></figure>"
    )

    map_html = (
        f"<section class=\"seo-section\"><h2>На карте регионов</h2>"
        f"<p>Тот же показатель на интерактивной карте России — цвет регионов "
        f"по значению, ползунок по годам: "
        f"<a href=\"{escape(paths.region_map(code))}\">открыть карту «{escape(indicator.name)}»</a>.</p>"
        f"</section>"
    )

    body = f"""<div class="seo-page">
{_breadcrumbs_nav(rating_trail)}
<p class="seo-eyebrow">{escape(indicator.section_name)} — {escape(copy["eyebrow"])}</p>
<h1>{escape(indicator.name)}: {escape(copy["h1_suffix"])}, {last_year} год</h1>
<p>{escape(intro)}</p>
{figure_html}
{tiles_html}
<section class="seo-section"><h2>{escape(copy["section_h2"])} ({total} регионов)</h2>{table_html}</section>
{faq_html}
{map_html}
{macro_html}
{siblings_html}
<section class="seo-section"><h2>Источник данных</h2>
<p>Сборник Росстата «Регионы России. Социально-экономические показатели».
Значения за {last_year} год, единицы: {escape(unit or 'единицы источника')}.
По каждому региону доступна страница с полной динамикой показателя с 1990 года.</p></section>
</div>"""

    json_ld.append({
        "@context": "https://schema.org",
        "@type": "ImageObject",
        "contentUrl": f"{DOMAIN}{og_path}",
        "url": f"{DOMAIN}{og_path}",
        "name": f"{indicator.name} — {copy['meta_rank_word']} регионов России, {last_year}",
        "description": rating_alt,
        "representativeOfPage": True,
        "width": 1200,
        "height": 630,
    })
    html = await build_document(
        title=title,
        description=desc,
        canonical_path=paths.region_rating(code),
        body=body,
        json_ld=json_ld,
        keywords=(
            f"{indicator.name} по регионам, {indicator.name} по субъектам рф, "
            f"{indicator.name} сравнение регионов"
        ),
        og_image=f"{DOMAIN}{og_path}",
    )
    return 200, html


async def render_region_ratings_hub_html(db: AsyncSession) -> tuple[int, str]:
    """Хаб рейтингов регионов: /russia/region-rating."""
    rating_inds = (await db.execute(
        select(RegionIndicator.code, RegionIndicator.name, RegionIndicator.section_name)
        .where(RegionIndicator.is_listed.is_(True))
        .order_by(RegionIndicator.section_num, RegionIndicator.code)
    )).all()
    if not rating_inds:
        return 404, "<h1>Рейтинги не найдены</h1>"

    by_section: dict[str, list[tuple[str, str]]] = {}
    for code, name, section in rating_inds:
        by_section.setdefault(section or "Показатели", []).append((code, name))

    sections = []
    for section, items in by_section.items():
        links = "".join(
            f'<li><a href="{escape(paths.region_rating(c))}">{escape(n)}</a></li>'
            for c, n in items
        )
        sections.append(
            f'<section class="seo-section"><h2>{escape(section)}</h2><ul>{links}</ul></section>'
        )

    trail = crumbs.region_rating_hub_trail()
    title = "Рейтинги регионов России по показателям Росстата"
    desc = (
        "Сравнение субъектов Российской Федерации по социально-экономическим "
        "показателям: полные таблицы мест, лидеры и аутсайдеры. Данные Росстата."
    )
    body = f"""<div class="seo-page">
{_breadcrumbs_nav(trail)}
<p class="seo-eyebrow">Региональная статистика Росстата</p>
<h1>Рейтинги регионов России</h1>
<p>Выберите показатель, чтобы увидеть полный рейтинг субъектов РФ за последний
доступный год: место каждого региона, лидеры и аутсайдеры, ссылки на динамику
по субъектам.</p>
{''.join(sections)}
</div>"""
    html = await build_document(
        title=title,
        description=desc,
        canonical_path=paths.region_rating_hub(),
        body=body,
        json_ld=[_breadcrumbs(trail)],
        keywords=(
            "рейтинг регионов россии, сравнение субъектов рф, "
            "топ регионов по показателям, росстат регионы"
        ),
    )
    return 200, html


async def render_regions_map_html(
    code: str, db: AsyncSession, *, year: int | None = None
) -> tuple[int, str]:
    """Интерактивная карта регионов: /russia/region/map/{code}?year=YYYY.

    SSR с React-bundle (include_app=True): краулер/превью получают meta +
    видимый контент; SPA гидратирует choropleth. OG переиспользует барчарт
    рейтинга — отдельный map-PNG не заводим (минимальный корректный SEO).
    """
    if code == MAP_OVERVIEW_CODE:
        title = "Карта регионов России — обзор субъектов РФ"
        desc = (
            "Интерактивная карта 85 субъектов Российской Федерации: откройте "
            "профиль региона или выберите показатель Росстата для цветовой шкалы "
            "по годам. Forecast Economy."
        )
        map_overview_trail = crumbs.trail(
            crumbs.home(),
            crumbs.russia(),
            crumbs.regions(),
            (paths.region_map("overview"), "Карта"),
        )
        body = f"""<div class="seo-page">
{_breadcrumbs_nav(map_overview_trail)}
<p class="seo-eyebrow">Интерактивная карта субъектов РФ</p>
<h1>Карта регионов России</h1>
<p>Обзорный режим: клик по субъекту открывает профиль региона со всеми
показателями сборника Росстата. Выберите показатель на странице, чтобы
увидеть цветовую карту и динамику по годам.</p>
<section class="seo-section"><h2>Популярные срезы на карте</h2>
<ul>
<li><a href="{escape(paths.region_map(DEFAULT_MAP_CODE))}">Среднемесячная заработная плата</a></li>
<li><a href="{paths.region_map('chislennost-naseleniya')}">Численность населения</a></li>
<li><a href="{paths.region_map('uroven-bezrabotitsy')}">Уровень безработицы</a></li>
</ul></section>
<section class="seo-section"><h2>Рейтинги</h2>
<p>Таблицу мест по показателю смотрите в разделе
<a href="{paths.region_rating_hub()}">рейтингов регионов</a>.</p></section>
</div>"""
        json_ld = [_breadcrumbs(map_overview_trail)]
        html = await build_document(
            title=title,
            description=desc,
            canonical_path=paths.region_map("overview"),
            body=body,
            json_ld=json_ld,
            keywords="карта регионов россии, субъекты рф на карте, регионы россии статистика",
        )
        return 200, html

    indicator = (await db.execute(
        select(RegionIndicator).where(
            RegionIndicator.code == code, RegionIndicator.is_listed.is_(True)
        )
    )).scalar_one_or_none()
    if indicator is None:
        return 404, "<h1>Показатель не найден</h1>"

    years_avail = (await db.execute(
        select(RegionDataPoint.year)
        .join(Region, Region.id == RegionDataPoint.region_id)
        .where(RegionDataPoint.indicator_id == indicator.id, Region.kind == "region")
        .group_by(RegionDataPoint.year)
        .having(func.count(func.distinct(RegionDataPoint.region_id)) >= 10)
        .order_by(RegionDataPoint.year)
    )).scalars().all()
    if not years_avail:
        return 404, "<h1>Нет данных для карты</h1>"

    years_list = [int(y) for y in years_avail]
    last_year = years_list[-1]
    map_year = year if year in years_list else last_year

    achievement = region_rating_is_achievement(indicator.code, indicator.table_code)
    copy = _rating_copy(achievement=achievement)
    rows = (await db.execute(
        select(Region.slug, Region.name, RegionDataPoint.value)
        .join(Region, Region.id == RegionDataPoint.region_id)
        .where(RegionDataPoint.indicator_id == indicator.id,
               RegionDataPoint.year == map_year,
               Region.kind == "region")
        .order_by(region_rating_order_by(
            RegionDataPoint.value, indicator.code, indicator.table_code
        ))
    )).all()
    if len(rows) < 10:
        return 404, "<h1>Недостаточно данных</h1>"

    unit = indicator.unit or ""
    total = len(rows)
    top = rows[:3]
    bottom = rows[-3:]

    def _vu(v) -> str:
        return f"{_fmt(float(v))} {unit}".strip()

    year_note = (
        f" за {map_year} год"
        if map_year == last_year
        else f" за {map_year} год (последний доступный — {last_year})"
    )
    title = f"Карта регионов России: {indicator.name} ({map_year})"
    desc = (
        f"{indicator.name} на карте 85 субъектов РФ{year_note}. "
        f"{copy['desc_best']} — {top[0][1]} ({_vu(top[0][2])}), "
        f"{copy['worst_tile'].lower()} — {bottom[-1][1]} ({_vu(bottom[-1][2])}). "
        f"Интерактивная карта и таблица, данные Росстата."
    )

    canonical = paths.region_map(code)
    if year is not None and year in years_list:
        canonical = f"{canonical}?year={year}"

    og_path = paths.og_region_rating(code)
    map_alt = (
        f"{indicator.name} по регионам России — карта, {map_year} год, "
        f"{copy['desc_best'].lower()} — {top[0][1]} ({_vu(top[0][2])})"
    )
    figure_html = (
        f'<figure class="seo-chart"><img src="{escape(og_path)}" alt="{escape(map_alt)}" '
        f'width="1200" height="630" loading="eager">'
        f"<figcaption>{escape(indicator.name)} по регионам, {map_year} год. "
        f"Источник: Росстат. forecasteconomy.com</figcaption></figure>"
    )

    leaders = "".join(
        f"<li><a href=\"{escape(paths.region_indicator(s, code))}\">{escape(n)}</a> — "
        f"{escape(_vu(v))}</li>"
        for s, n, v in top
    )
    year_links = "".join(
        f'<li><a href="{escape(paths.region_map(code))}?year={y}">{y}</a></li>'
        for y in years_list[-8:]
    )

    json_ld = [
        _breadcrumbs(crumbs.trail(
            crumbs.home(),
            crumbs.russia(),
            crumbs.regions(),
            (paths.region_map(code), f"Карта: {indicator.name}"),
        )),
        {
            "@context": "https://schema.org",
            "@type": "WebApplication",
            "name": title,
            "description": desc,
            "url": f"{DOMAIN}{canonical}",
            "applicationCategory": "BusinessApplication",
            "operatingSystem": "Any",
            "isAccessibleForFree": True,
            "inLanguage": "ru-RU",
        },
        {
            "@context": "https://schema.org",
            "@type": "ImageObject",
            "contentUrl": f"{DOMAIN}{og_path}",
            "url": f"{DOMAIN}{og_path}",
            "name": f"{indicator.name} — карта регионов, {map_year}",
            "description": map_alt,
            "representativeOfPage": True,
            "width": 1200,
            "height": 630,
        },
    ]

    rating_link_label = (
        f"рейтинг регионов по «{escape(indicator.name)}»"
        if achievement
        else f"таблица регионов по «{escape(indicator.name)}»"
    )
    map_trail = crumbs.trail(
        crumbs.home(),
        crumbs.russia(),
        crumbs.regions(),
        (paths.region_map(code), f"Карта: {indicator.name}"),
    )
    body = f"""<div class="seo-page">
{_breadcrumbs_nav(map_trail)}
<p class="seo-eyebrow">{escape(indicator.section_name)} — карта регионов</p>
<h1>{escape(indicator.name)} на карте регионов России, {map_year} год</h1>
<p>Интерактивная карта {total} субъектов Российской Федерации по показателю
«{escape(indicator.name)}»{escape(year_note)}. Цвет региона отражает значение
относительно других субъектов; ползунок на странице переключает годы
с {years_list[0]} по {last_year}. Данные — сборник Росстата
«Регионы России. Социально-экономические показатели».</p>
{figure_html}
<div class="seo-tiles">
<div class="seo-tile"><span>{escape(copy["best_tile"])} — {escape(top[0][1])}</span><b>{escape(_vu(top[0][2]))}</b></div>
<div class="seo-tile"><span>{escape(copy["worst_tile"])} — {escape(bottom[-1][1])}</span><b>{escape(_vu(bottom[-1][2]))}</b></div>
<div class="seo-tile"><span>Год на карте</span><b>{map_year}</b></div>
<div class="seo-tile"><span>Регионов на срезе</span><b>{total}</b></div>
</div>
<section class="seo-section"><h2>{escape(copy["map_leaders_h2"])} {map_year} года</h2><ol>{leaders}</ol>
<p>Полная таблица —
<a href="{escape(paths.region_rating(code))}">{rating_link_label}</a>.</p>
</section>
<section class="seo-section"><h2>Другие годы</h2><ul class="seo-pills">{year_links}</ul></section>
<section class="seo-section"><h2>Источник</h2>
<p>Росстат, единицы: {escape(unit or 'единицы источника')}. После загрузки страницы
доступна интерактивная карта с выбором года и переходом в карточку региона.</p>
</section>
</div>"""

    html = await build_document(
        title=title,
        description=desc,
        canonical_path=canonical,
        body=body,
        json_ld=json_ld,
        keywords=(
            f"{indicator.name} карта регионов, {indicator.name} по регионам россии, "
            f"карта субъектов рф {indicator.name}, {indicator.name} {map_year}"
        ),
        og_image=f"{DOMAIN}{og_path}",
    )
    return 200, html


async def render_region_indicator_html(
    slug: str, code: str, db: AsyncSession
) -> tuple[int, str]:
    region = await _region(db, slug)
    if region is None or region.kind not in ("region", "district", "country"):
        return 404, "<h1>Регион не найден</h1>"
    indicator = (await db.execute(
        select(RegionIndicator).where(RegionIndicator.code == code)
    )).scalar_one_or_none()
    if indicator is None:
        return 404, "<h1>Показатель не найден</h1>"

    rows = (await db.execute(
        select(RegionDataPoint.year, RegionDataPoint.value)
        .where(RegionDataPoint.indicator_id == indicator.id,
               RegionDataPoint.region_id == region.id)
        .order_by(RegionDataPoint.year)
    )).all()
    if not rows:
        return 404, "<h1>Нет данных</h1>"
    series = [(int(y), float(v)) for y, v in rows]
    first_year, first_value = series[0]
    last_year, last_value = series[-1]
    by_year = dict(series)

    # РФ для сравнения
    rf_last = None
    rf = await _region(db, "russia")
    if rf and region.slug != "russia":
        rf_last = (await db.execute(
            select(RegionDataPoint.value)
            .where(RegionDataPoint.indicator_id == indicator.id,
                   RegionDataPoint.region_id == rf.id,
                   RegionDataPoint.year == last_year)
        )).scalar_one_or_none()

    # рейтинг по последнему году
    achievement = region_rating_is_achievement(indicator.code, indicator.table_code)
    rank_rows = (await db.execute(
        select(Region.slug, RegionDataPoint.value)
        .join(Region, Region.id == RegionDataPoint.region_id)
        .where(RegionDataPoint.indicator_id == indicator.id,
               RegionDataPoint.year == last_year,
               Region.kind == "region")
        .order_by(region_rating_order_by(
            RegionDataPoint.value, indicator.code, indicator.table_code
        ))
    )).all()
    position = next(
        (i for i, (s, _v) in enumerate(rank_rows, 1) if s == region.slug), None
    )

    unit = indicator.unit or ""
    unit_sfx = f" {escape(unit)}" if unit else ""

    # --- уникальный автоконтент ---
    paragraphs = []
    p1 = (
        f"{escape(indicator.name)} в регионе {escape(region.name)} "
        f"в {last_year} году: {_fmt(last_value)}{unit_sfx}."
    )
    prev = by_year.get(last_year - 1)
    ch1 = _pct(last_value, prev)
    if ch1:
        p1 += f" За год показатель {ch1}."
    paragraphs.append(p1)

    base5 = by_year.get(last_year - 5)
    ch5 = _pct(last_value, base5)
    chfull = _pct(last_value, first_value)
    p2 = ""
    if ch5:
        p2 += f"За пять лет (с {last_year - 5} года) показатель {ch5}."
    if chfull and first_year < last_year - 5:
        p2 += (f" С {first_year} года, начала доступного ряда, показатель {chfull} "
               f"(с {_fmt(first_value)} до {_fmt(last_value)}{unit_sfx}).")
    if p2:
        paragraphs.append(p2)

    if position and region.kind == "region":
        # Ссылка на рейтинг — только когда страница рейтинга существует
        # (у неё порог >= 10 регионов с данными за последний год).
        rating_ref = (
            f" (<a href=\"{escape(paths.region_rating(code))}\">"
            f"{'полный рейтинг регионов' if achievement else 'таблица по всем регионам'}"
            f"</a>)"
            if len(rank_rows) >= 10 else ""
        )
        p3 = (f"По значению этого показателя {escape(region.name)} "
              f"{_rank_phrase(position, len(rank_rows), achievement=achievement)} "
              f"в {last_year} году{rating_ref}.")
        if rf_last is not None:
            rel = "выше" if last_value > float(rf_last) else "ниже"
            if abs(last_value - float(rf_last)) / (abs(float(rf_last)) or 1) < 0.005:
                rel = "на уровне"
            p3 += (f" Общероссийское значение — {_fmt(float(rf_last))}{unit_sfx}: "
                   f"регион {rel} среднего по стране.")
        paragraphs.append(p3)

    values_desc = [v for _y, v in series]
    vmax = max(values_desc); vmin = min(values_desc)
    ymax = series[[v for _y, v in series].index(vmax)][0]
    ymin = series[[v for _y, v in series].index(vmin)][0]
    paragraphs.append(
        f"Максимум за весь период наблюдений — {_fmt(vmax)}{unit_sfx} в {ymax} году, "
        f"минимум — {_fmt(vmin)}{unit_sfx} в {ymin} году. "
        f"Данные обновляются ежегодно по мере публикации сборника Росстата."
    )

    paragraphs_html = "".join(f"<p>{p}</p>" for p in paragraphs)

    # Контрольные годы: плотная факт-выжимка для поисковиков и ИИ-ассистентов —
    # ответ на запросы вида «X в Y в 2010 году» без чтения полной таблицы.
    checkpoint_years = [y for y in range(1990, last_year, 5) if y in by_year]
    checkpoints_html = ""
    if len(checkpoint_years) >= 3:
        cp_items = "".join(
            f"<li>{y} год — {_fmt(by_year[y])}{unit_sfx}</li>" for y in checkpoint_years
        )
        cp_items += f"<li>{last_year} год — {_fmt(last_value)}{unit_sfx}</li>"
        checkpoints_html = (
            f"<section class=\"seo-section\"><h2>{escape(indicator.name)} "
            f"в регионе {escape(region.name)} по контрольным годам</h2>"
            f"<ul>{cp_items}</ul></section>"
        )

    # FAQ: видимый блок + FAQPage JSON-LD (одинаковый контент — требование
    # поисковиков). Вопросы повторяют реальные формулировки пользователей.
    faq: list[tuple[str, str]] = []
    faq.append((
        f"Какое значение показателя «{indicator.name}» в регионе {region.name}?",
        f"По данным Росстата за {last_year} год — {_fmt(last_value)} {unit}".strip() + ".",
    ))
    if position and region.kind == "region":
        if achievement:
            faq.append((
                f"Какое место занимает {region.name} по этому показателю среди регионов России?",
                f"{position}-е место из {len(rank_rows)} субъектов РФ по итогам {last_year} года.",
            ))
        else:
            faq.append((
                f"Какое положение в списке по величине показателя занимает {region.name}?",
                f"{position}-е из {len(rank_rows)} субъектов РФ при упорядочивании "
                f"по убыванию значения за {last_year} год.",
            ))
    if ch1:
        faq.append((
            "Как изменился показатель за последний год?",
            f"С {last_year - 1} по {last_year} год показатель {ch1}.",
        ))
    faq.append((
        "Откуда взяты данные и как часто они обновляются?",
        "Источник — официальный сборник Росстата «Регионы России. Социально-экономические "
        "показатели». Данные годовые, обновляются после выхода нового выпуска сборника.",
    ))
    faq_html = (
        "<section class=\"seo-section\"><h2>Вопросы и ответы</h2>"
        + "".join(
            f"<h3>{escape(q)}</h3><p>{escape(a)}</p>" for q, a in faq
        )
        + "</section>"
    )
    faq_json_ld = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": a},
            }
            for q, a in faq
        ],
    }

    # Мост в макроблок: у ключевых показателей есть общероссийская карточка
    # с месячной/квартальной частотой и прогнозом.
    macro_code = MACRO_BY_TABLE.get(indicator.table_code or "")
    macro_html = ""
    if macro_code:
        macro_html = (
            f"<section class=\"seo-section\"><h2>Общероссийский показатель</h2>"
            f"<p>Динамика по России в целом, с более частым обновлением и прогнозом — "
            f"на странице <a href=\"{escape(paths.russia_indicator(macro_code))}\">общероссийского "
            f"индикатора</a>. Сравнить регион с федеральным уровнем можно в разделе "
            f"<a href=\"/compare?codes={escape(macro_code)},r:{escape(slug)}:{escape(code)}\">"
            f"«Сравнение»</a>.</p></section>"
        )

    # Тот же показатель у соседей по федеральному округу.
    district_html = ""
    if region.kind == "region" and region.district_slug:
        neighbors = (await db.execute(
            select(Region.slug, Region.name)
            .where(Region.district_slug == region.district_slug,
                   Region.kind == "region",
                   Region.slug != region.slug)
            .order_by(Region.sort_order)
        )).all()
        if neighbors:
            items = "".join(
                f'<li><a href="{escape(paths.region_indicator(s, code))}">'
                f"{escape(indicator.name)} — {escape(n)}</a></li>"
                for s, n in neighbors
            )
            district_html = (
                f"<section class=\"seo-section\"><h2>Этот показатель у соседей "
                f"по округу</h2><ul>{items}</ul></section>"
            )

    # таблица всех значений (полный контент для индексации)
    table_rows = "".join(
        f"<tr><td>{y}</td><td>{_fmt(v)}</td></tr>" for y, v in reversed(series)
    )
    table_html = (
        f"<h2>{escape(indicator.name)} по годам</h2>"
        f"<table><thead><tr><th>Год</th><th>{escape(unit or 'Значение')}</th></tr></thead>"
        f"<tbody>{table_rows}</tbody></table>"
    )

    # видимый график — ключ к Яндекс.Картинкам и Алисе
    og_path = paths.og_region(slug, code)
    alt = (f"{indicator.name} — {region.name}: график динамики {first_year}–{last_year}, "
           f"последнее значение {_fmt(last_value)} {unit}".strip())
    figure_html = (
        f'<figure class="seo-chart"><img src="{escape(og_path)}" alt="{escape(alt)}" '
        f'width="1200" height="630" loading="eager">'
        f"<figcaption>{escape(indicator.name)} в регионе {escape(region.name)}, "
        f"{first_year}–{last_year}. Источник: Росстат.</figcaption></figure>"
    )

    # соседние показатели раздела
    siblings = (await db.execute(
        select(RegionIndicator.code, RegionIndicator.name)
        .where(RegionIndicator.section_num == indicator.section_num,
               RegionIndicator.code != indicator.code,
               RegionIndicator.is_listed.is_(True))
        .order_by(RegionIndicator.code)
        .limit(10)
    )).all()
    siblings_html = ""
    if siblings:
        items = "".join(
            f'<li><a href="{escape(paths.region_indicator(slug, c))}">{escape(n)}</a></li>'
            for c, n in siblings
        )
        siblings_html = (
            f"<section class=\"seo-section\"><h2>Ещё в разделе "
            f"«{escape(indicator.section_name)}»</h2><ul>{items}</ul></section>"
        )

    title = (f"{indicator.name} — {region.name}: {_fmt(last_value)} "
             f"{unit} ({last_year})").strip()
    if position and achievement:
        rank_bit = f", {position}-е место среди {len(rank_rows)} регионов России."
    elif position:
        rank_bit = (
            f", {position}-е положение в списке по величине среди "
            f"{len(rank_rows)} регионов России."
        )
    else:
        rank_bit = ". Данные Росстата."
    desc = (
        f"{indicator.name} в регионе {region.name}: {_fmt(last_value)} {unit} "
        f"в {last_year} году. Динамика с {first_year} года, график по годам, "
        f"таблица значений{rank_bit}"
    )

    json_ld = [
        _breadcrumbs(crumbs.region_indicator_trail(
            region.name, paths.region(slug), indicator.name,
            paths.region_indicator(slug, code),
        )),
        faq_json_ld,
        {
            "@context": "https://schema.org",
            "@type": "Dataset",
            "name": f"{indicator.name} — {region.name}",
            "description": (f"{indicator.name} ({unit}), {region.name}, "
                            f"{first_year}–{last_year}. Источник: Росстат."),
            "url": f"{DOMAIN}{paths.region_indicator(slug, code)}",
            "temporalCoverage": f"{first_year}/{last_year}",
            "spatialCoverage": region.name,
            "creator": {"@type": "Organization", "name": "Росстат"},
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
            "name": f"{indicator.name} — {region.name}: график",
            "caption": alt,
            "representativeOfPage": True,
        },
    ]

    body = f"""<div class="seo-page">
{_breadcrumbs_nav(crumbs.region_indicator_trail(
    region.name, paths.region(slug), indicator.name,
    paths.region_indicator(slug, code),
))}
<p class="seo-eyebrow">{escape(indicator.section_name)} — {escape(region.name)}</p>
<h1>{escape(indicator.name)} — {escape(region.name)}</h1>
{figure_html}
{paragraphs_html}
{checkpoints_html}
{table_html}
{faq_html}
{macro_html}
{district_html}
{siblings_html}
<section class="seo-section"><h2>Источник данных</h2>
<p>Сборник Росстата «Регионы России. Социально-экономические показатели».
Значения приведены в единицах: {escape(unit or 'единицы источника')}.
Период наблюдений: {first_year}–{last_year}.</p></section>
</div>"""

    html = await build_document(
        title=title,
        description=desc,
        canonical_path=paths.region_indicator(slug, code),
        body=body,
        json_ld=json_ld,
        keywords=(
            f"{indicator.name} {region.name}, {region.name} {indicator.name} по годам, "
            f"{indicator.name} {region.name} график, {region.name} статистика"
        ),
        og_image=f"{DOMAIN}{og_path}",
    )
    return 200, html

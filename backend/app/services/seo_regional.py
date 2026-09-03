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
from app.models import Region, RegionDataPoint, RegionIndicator, RegionMonthlyPoint, WebmasterSearchQuery
from app.services import breadcrumbs as crumbs
from app.services import site_paths as paths
from app.services.seo_i18n import (
    region_display_name,
    region_indicator_copy,
    regional_template,
)
from app.services.seo_renderer import (
    _absolute,
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
    # Помесячные цены на топливо (раздел 16) → федеральные карточки ЦБ Росстата
    # (fuel-ai92/ai95/diesel); годовые опт/розница 16.23–16.25 — без моста:
    # федерального аналога той же методологии нет.
    "16.20": "fuel-ai92",
    "16.21": "fuel-ai95",
    "16.22": "fuel-diesel",
}

_REGIONS_TITLE = "Регионы России — социально-экономические показатели 85 субъектов РФ"
_REGIONS_DESC = (
    "Статистика по 85 регионам России: население, зарплаты, ВРП, безработица, "
    "инвестиции, цены — 495 показателей Росстата с 1990 года. Графики, "
    "рейтинги регионов, сравнение с общероссийским уровнем."
)

# Дефолтный чип карты на фронте (MAP_METRICS[0]) — общий канон для 301
# `/regions?view=map` без indicator и для sitemap-хаба.
DEFAULT_MAP_CODE = (
    "srednemesyachnaya-nominalnaya-nachislennaya-zarabotnaya-plata-rabotnikov-organizatsiy"
)
MAP_OVERVIEW_CODE = "overview"


def _rname(slug: str, name_ru: str) -> str:
    return region_display_name(slug, name_ru)


def _icopy(ind: RegionIndicator) -> dict[str, str | None]:
    return region_indicator_copy(
        ind.code,
        name_ru=ind.name,
        unit_ru=ind.unit or "",
        note_ru=ind.note,
        section_ru=ind.section_name,
    )


def _rt(key: str, **kwargs) -> str | None:
    tpl = regional_template(key)
    if not tpl:
        return None
    return tpl.format(**kwargs) if kwargs else tpl


def _fmt(value: float) -> str:
    """Русская типографика: пробел-разряды, запятая-дробь, без хвостовых нулей.

    Знаки после запятой — по природе величины, не по коду показателя:
    крупные счётные без дроби, десятки–сотни — один знак, коэффициенты
    порядка единиц (суммарная рождаемость 1,152 vs 1,195) — до трёх.
    """
    if value is None:
        return "—"
    v = float(value)
    abs_v = abs(v)
    if abs_v >= 1000:
        digits = 0
    elif abs_v >= 10:
        digits = 1
    else:
        digits = 3
    text = f"{v:,.{digits}f}".replace(",", "\u202f").replace(".", ",")
    if "," in text:
        text = text.rstrip("0").rstrip(",")
    return text


def _times_word(times: float) -> str:
    """«в 2,5 раза» / «в 45 раз» — согласование с дробностью и величиной."""
    rounded = round(times, 1)
    en = _rt("region_indicator.times_word")
    if en:
        return en.format(n=_fmt(rounded))
    word = "раза" if rounded != int(rounded) or int(rounded) in (2, 3, 4) else "раз"
    return f"в {_fmt(rounded)} {word}"


def _pct(cur: float, base: float) -> str | None:
    """Фраза динамики: «вырос на 22,2%» / «вырос в 44,6 раза» / «снизился…»."""
    if base is None or cur is None or base == 0:
        return None
    pct = (cur - base) / abs(base) * 100
    flat = _rt("region_indicator.pct_flat")
    if abs(pct) < 0.05:
        return flat or "практически не изменился"
    up = _rt("region_indicator.pct_up") or "вырос"
    down = _rt("region_indicator.pct_down") or "снизился"
    verb = up if pct > 0 else down
    if pct >= 200 and base > 0:
        times_tpl = _rt("region_indicator.pct_times") or " {times}"
        return f"{verb}{times_tpl.format(times=_times_word(cur / base))}"
    by_tpl = _rt("region_indicator.pct_by") or " на {pct}%"
    return f"{verb}{by_tpl.format(pct=_fmt(round(abs(pct), 1)))}"


async def _region(db: AsyncSession, slug: str) -> Region | None:
    return (await db.execute(select(Region).where(Region.slug == slug))).scalar_one_or_none()


def _rank_phrase(
    position: int,
    total: int,
    *,
    achievement: bool = False,
) -> str:
    """Фраза места региона. Для неизвестной полярности — нейтрально по величине."""
    if achievement:
        if position <= 3:
            return (_rt("region_indicator.rank_top3") or (
                f"входит в тройку лучших среди {total} субъектов РФ"
            )).format(total=total)
        if position <= 10:
            return (_rt("region_indicator.rank_top10") or (
                f"входит в десятку лучших среди {total} субъектов РФ"
            )).format(total=total)
        if position > total - 5:
            return (_rt("region_indicator.rank_bottom") or (
                f"находится в конце рейтинга — {position}-е место из {total}"
            )).format(position=position, total=total)
        return (_rt("region_indicator.rank_place") or (
            f"занимает {position}-е место из {total}"
        )).format(position=position, total=total)
    if position <= 3:
        return (_rt("region_indicator.list_top3") or (
            f"входит в тройку регионов с наибольшим значением среди {total} субъектов РФ"
        )).format(total=total)
    if position <= 10:
        return (_rt("region_indicator.list_top10") or (
            f"входит в десятку регионов с наибольшим значением среди {total} субъектов РФ"
        )).format(total=total)
    if position > total - 5:
        return (_rt("region_indicator.list_bottom") or (
            f"находится в конце списка по величине показателя — "
            f"{position}-е положение из {total}"
        )).format(position=position, total=total)
    return (_rt("region_indicator.list_place") or (
        f"занимает {position}-е положение в списке по величине показателя из {total}"
    )).format(position=position, total=total)


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
        d_name = _rname(d.slug, d.name)
        links = "".join(
            f'<li><a href="{escape(paths.region(r.slug))}">{escape(_rname(r.slug, r.name))}</a></li>'
            for r in by_district.get(d.slug, [])
        )
        sections.append(
            f"<section class=\"seo-section\"><h2>{escape(d_name)}</h2><ul>{links}</ul></section>"
        )

    # Точка входа робота в рейтинги и карту: ключевые показатели с мостом в макро.
    rating_inds = (await db.execute(
        select(RegionIndicator)
        .where(RegionIndicator.table_code.in_(list(MACRO_BY_TABLE)),
               RegionIndicator.is_listed.is_(True))
        .order_by(RegionIndicator.section_num)
    )).scalars().all()
    ratings_html = ""
    if rating_inds:
        rating_items = "".join(
            f'<li><a href="{escape(paths.region_rating(ind.code))}">'
            f'{escape(_icopy(ind)["name"] or ind.name)}</a></li>'
            for ind in rating_inds
        )
        map_items = "".join(
            f'<li><a href="{escape(paths.region_map(ind.code))}">'
            f'{escape(_icopy(ind)["name"] or ind.name)}</a></li>'
            for ind in rating_inds
        )
        ratings_html = (
            f"<section class=\"seo-section\"><h2>{escape(_rt('regions_hub.ratings_h2') or 'Рейтинги и карта регионов')}</h2>"
            f"<p>{escape(_rt('regions_hub.ratings_p') or ('Все субъекты РФ по значению показателя: полная таблица мест '
            'или интерактивная карта с выбором года.'))}</p>"
            f"<h3>{escape(_rt('regions_hub.ratings_h3') or 'Рейтинги')}</h3><ul>{rating_items}</ul>"
            f"<h3>{escape(_rt('regions_hub.map_h3') or 'Карта')}</h3><ul>{map_items}</ul></section>"
        )

    title = _rt("regions_hub.title") or _REGIONS_TITLE
    desc = _rt("regions_hub.description") or _REGIONS_DESC
    h1 = _rt("regions_hub.h1") or "Регионы России: социально-экономические показатели"
    eyebrow = _rt("regions_hub.eyebrow") or "Региональная статистика Росстата"
    lead = _rt(
        "regions_hub.lead",
        n_regions=n_regions,
        n_ind=n_ind,
    ) or (
        f"Официальная статистика по {n_regions} субъектам Российской Федерации: "
        f"население, занятость и зарплаты, уровень жизни, валовой региональный продукт, "
        f"инвестиции, промышленность, сельское хозяйство, строительство, торговля, "
        f"транспорт, наука и цены. Всего {n_ind} показателей с 1990 года по данным "
        f"сборника Росстата «Регионы России. Социально-экономические показатели»."
    )

    body = f"""<div class="seo-page">
{_breadcrumbs_nav(crumbs.regions_trail())}
<p class="seo-eyebrow">{escape(eyebrow)}</p>
<h1>{escape(h1)}</h1>
<p>{escape(lead)}</p>
{ratings_html}
{''.join(sections)}
</div>"""

    json_ld = [_breadcrumbs(crumbs.regions_trail())]
    html = await build_document(
        title=title,
        description=desc,
        canonical_path=paths.region_hub(),
        body=body,
        json_ld=json_ld,
        keywords=_rt("regions_hub.keywords") or (
            "регионы россии статистика, экономика регионов, показатели субъектов рф"
        ),
    )
    return 200, html


async def render_region_html(slug: str, db: AsyncSession) -> tuple[int, str]:
    region = await _region(db, slug)
    if region is None or region.kind not in ("region", "district", "country"):
        return 404, "<h1>Регион не найден</h1>"

    region_name = _rname(region.slug, region.name)

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
        copy = _icopy(ind)
        unit = f" {escape(copy['unit'])}" if copy["unit"] else ""
        sections.setdefault(ind.section_num, []).append(
            f'<li><a href="{escape(paths.region_indicator(slug, ind.code))}">{escape(copy["name"] or ind.name)}</a>'
            f' — {_fmt(value)}{unit} ({year})</li>'
        )
        section_names[ind.section_num] = copy["section"] or ind.section_name

    featured_html = await _region_demand_links(db, slug, inds)

    n_catalog = len(inds)
    section_html = "".join(
        f"<section class=\"seo-section\"><h2>{escape(section_names[num])}</h2>"
        f"<ul>{''.join(items)}</ul></section>"
        for num, items in sorted(sections.items())
    )

    title = _rt("region_profile.title", region=region_name) or (
        f"{region_name} — статистика региона: население, зарплата, ВРП, цены"
    )
    desc = _rt("region_profile.description", region=region_name) or (
        f"{region_name}: {n_catalog} показателей в каталоге Росстата"
        + (f", данные по региону — {n_present}" if n_present < n_catalog else "")
        + f" с 1990 года — население, зарплаты, безработица, ВРП, инвестиции, "
        f"строительство, цены. Графики и место региона в рейтингах России."
    )
    h1 = _rt("region_profile.h1", region=region_name) or (
        f"{region_name}: социально-экономические показатели"
    )
    catalog_line = (
        (_rt("region_profile.catalog_partial") or (
            "{n_catalog} показателей в каталоге; по региону — данные по {n_present}"
        )).format(n_catalog=n_catalog, n_present=n_present)
        if n_present < n_catalog
        else (_rt("region_profile.catalog_full") or "{n_catalog} показателей").format(
            n_catalog=n_catalog
        )
    )
    # Выход к РФ и флагманским рейтингам: профиль иначе замыкается на свои
    # показатели и не отдаёт боту путь «регион → Россия / рейтинг».
    flagship = (await db.execute(
        select(RegionIndicator)
        .where(
            RegionIndicator.table_code.in_(list(MACRO_BY_TABLE)),
            RegionIndicator.is_listed.is_(True),
        )
        .order_by(RegionIndicator.section_num)
        .limit(6)
    )).scalars().all()
    cross_items = [
        f'<li><a href="{paths.region_hub()}">'
        f'{escape(_rt("region_profile.all_regions") or "Все регионы России")}</a></li>',
    ]
    if slug != "russia":
        russia_label = _rname("russia", "Российская Федерация")
        cross_items.append(
            f'<li><a href="{paths.region("russia")}">'
            f'{escape((_rt("region_profile.russia_summary") or "{russia} — сводные показатели").format(russia=russia_label))}</a></li>'
        )
    cross_items.extend(
        f'<li><a href="{escape(paths.region_rating(ind.code))}">{escape(_icopy(ind)["name"] or ind.name)}</a></li>'
        for ind in flagship
    )
    cross_html = (
        f'<section class="seo-section"><h2>{escape(_rt("region_profile.see_also") or "Смотрите также")}</h2>'
        f'<ul>{"".join(cross_items)}</ul></section>'
    )
    eyebrow = _rt("region_profile.eyebrow") or "Региональная статистика Росстата"
    lead = _rt(
        "region_profile.lead",
        region=region_name,
        catalog_line=catalog_line,
        n_sections=len(sections),
    ) or (
        f"Официальные данные Росстата по региону {region_name}: {catalog_line} "
        f"в {len(sections)} разделах — от численности населения и заработной платы до валового "
        f"регионального продукта, инвестиций и потребительских цен. Ряды с 1990 года, "
        f"по каждому показателю — график динамики и место региона среди субъектов РФ."
    )
    body = f"""<div class="seo-page">
{_breadcrumbs_nav(crumbs.region_trail(region_name, paths.region(slug)))}
<p class="seo-eyebrow">{escape(eyebrow)}</p>
<h1>{escape(h1)}</h1>
<p>{escape(lead)}</p>
{featured_html}
{section_html}
{cross_html}
</div>"""

    json_ld = [
        _breadcrumbs(crumbs.region_trail(region_name, paths.region(slug))),
    ]
    html = await build_document(
        title=title,
        description=desc,
        canonical_path=paths.region(slug),
        body=body,
        json_ld=json_ld,
        keywords=_rt("region_profile.keywords", region=region_name) or (
            f"{region_name} статистика, {region_name} экономика, {region_name} население, "
            f"{region_name} зарплата, {region_name} врп"
        ),
    )
    return 200, html


async def _region_demand_links(db: AsyncSession, slug: str, inds: list) -> str:
    """Топ-20 показателей региона по спросу Вебмастера, иначе флагманы MACRO."""

    by_code = {ind.code: ind for ind in inds}
    prefix = f"/russia/region/{slug}/"
    demand_codes: list[str] = []
    try:
        rows = (await db.execute(
            select(WebmasterSearchQuery.url, func.coalesce(func.sum(WebmasterSearchQuery.impressions), 0))
            .where(WebmasterSearchQuery.url.contains(prefix))
            .group_by(WebmasterSearchQuery.url)
            .order_by(func.coalesce(func.sum(WebmasterSearchQuery.impressions), 0).desc())
            .limit(120)
        )).all()
        for url, _imp in rows:
            rest = (url or "").split(f"/region/{slug}/", 1)
            if len(rest) < 2:
                continue
            code = rest[1].split("/", 1)[0].split("?", 1)[0]
            if code in by_code and code not in demand_codes:
                demand_codes.append(code)
            if len(demand_codes) >= 20:
                break
    except Exception:  # noqa: BLE001
        demand_codes = []
    if len(demand_codes) < 8:
        extra = [
            ind.code for ind in inds
            if (ind.table_code or "") in MACRO_BY_TABLE and ind.code not in demand_codes
        ]
        demand_codes.extend(extra)
    demand_codes = demand_codes[:20]
    if not demand_codes:
        return ""
    items = []
    for code in demand_codes:
        ind = by_code.get(code)
        if ind is None:
            continue
        copy = _icopy(ind)
        items.append(
            f'<li><a href="{escape(paths.region_indicator(slug, ind.code))}">{escape(copy["name"] or ind.name)}</a></li>'
        )
    if not items:
        return ""
    heading = _rt("region_profile.top_demand") or "Часто смотрят"
    return (
        f'<section class="seo-section"><h2>{escape(heading)}</h2>'
        f'<ul>{"".join(items)}</ul></section>'
    )


def _rating_copy(*, achievement: bool) -> dict[str, str]:
    """Подписи рейтинга: достижение vs нейтральный список по величине."""
    from app.services.locale import get_locale

    if get_locale() == "en":
        if achievement:
            return {
                "eyebrow": "regional ranking",
                "h1_suffix": "ranking of Russian regions",
                "intro_lead": "The top places are held by",
                "intro_tail": "At the bottom of the ranking is",
                "table_col": "Rank",
                "section_h2": "Full ranking",
                "best_tile": "Best value",
                "worst_tile": "Worst value",
                "figcaption": "regions with the best values",
                "map_leaders_h2": "Leaders",
                "faq_best_q": "Which region has the best value for",
                "faq_best_a_lead": "first place goes to",
                "faq_worst_q": "Which region has the worst value?",
                "faq_worst_a_lead": "The worst value is in",
                "desc_best": "Best value",
                "meta_rank_word": "ranking",
                "list_word": "Ranking",
                "intro_frame": (
                    "{list_word} of {total} federal subjects of the Russian Federation "
                    "by «{indicator}» for {year}. {lead}: {top_names}. "
                    "{tail} {bottom_name} — {bottom_value}."
                ),
                "intro_rf": " The Russia-wide figure is {value}.",
            }
        return {
            "eyebrow": "regional comparison",
            "h1_suffix": "comparison of Russian regions",
            "intro_lead": "The largest values are in",
            "intro_tail": "The smallest value is in",
            "table_col": "No.",
            "section_h2": "Regions by indicator magnitude",
            "best_tile": "Largest value",
            "worst_tile": "Smallest value",
            "figcaption": "regions with the largest values",
            "map_leaders_h2": "Largest values",
            "faq_best_q": "Which region has the largest value for",
            "faq_best_a_lead": "the largest value is in",
            "faq_worst_q": "Which region has the smallest value?",
            "faq_worst_a_lead": "The smallest value is in",
            "desc_best": "Largest value",
            "meta_rank_word": "comparison",
            "list_word": "Comparison",
            "intro_frame": (
                "{list_word} of {total} federal subjects of the Russian Federation "
                "by «{indicator}» for {year}. {lead}: {top_names}. "
                "{tail} {bottom_name} — {bottom_value}."
            ),
            "intro_rf": " The Russia-wide figure is {value}.",
        }
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
            "list_word": "Рейтинг",
            "intro_frame": (
                "{list_word} {total} субъектов Российской Федерации по показателю "
                "«{indicator}» за {year} год. {lead}: {top_names}. "
                "{tail} {bottom_name} — {bottom_value}."
            ),
            "intro_rf": " Значение по России в целом — {value}.",
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
        "list_word": "Сравнение",
        "intro_frame": (
            "{list_word} {total} субъектов Российской Федерации по показателю "
            "«{indicator}» за {year} год. {lead}: {top_names}. "
            "{tail} {bottom_name} — {bottom_value}."
        ),
        "intro_rf": " Значение по России в целом — {value}.",
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

    icopy = _icopy(indicator)
    ind_name = icopy["name"] or indicator.name
    unit = icopy["unit"] or (indicator.unit or "")
    section_name = icopy["section"] or indicator.section_name
    rows = [(s, _rname(s, n), v) for s, n, v in rows]
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
    intro = copy["intro_frame"].format(
        list_word=copy["list_word"],
        total=total,
        indicator=ind_name,
        year=last_year,
        lead=copy["intro_lead"],
        top_names=top_names,
        tail=copy["intro_tail"],
        bottom_name=bottom[-1][1],
        bottom_value=_vu(bottom[-1][2]),
    )
    if rf_value is not None:
        intro += copy["intro_rf"].format(value=_vu(rf_value))

    th_region = _rt("region_rating.th_region") or "Регион"
    th_value = unit or ("Value" if _rt("region_rating.th_region") else "Значение")
    table_rows = "".join(
        f"<tr><td>{i}</td>"
        f'<td><a href="{escape(paths.region_indicator(s, code))}">{escape(n)}</a></td>'
        f"<td>{_fmt(float(v))}</td></tr>"
        for i, (s, n, v) in enumerate(rows, 1)
    )
    table_html = (
        f'<div class="seo-scroll"><table><thead><tr><th>{escape(copy["table_col"])}</th>'
        f"<th>{escape(th_region)}</th>"
        f"<th>{escape(th_value)}</th></tr></thead>"
        f"<tbody>{table_rows}</tbody></table></div>"
    )

    faq_best_a = (
        f"По итогам {last_year} года {copy['faq_best_a_lead']} {top[0][1]} — {_vu(top[0][2])}."
        if _rt("region_rating.faq_year_q") is None
        else (
            f"As of {last_year}, {copy['faq_best_a_lead']} {top[0][1]} — {_vu(top[0][2])}."
        )
    )
    faq_year_q = _rt("region_rating.faq_year_q") or "За какой год приведены данные и откуда они?"
    faq_year_a = _rt("region_rating.faq_year_a", year=last_year) or (
        f"Данные за {last_year} год из сборника Росстата "
        f"«Регионы России. Социально-экономические показатели»."
    )
    faq = [
        (f"{copy['faq_best_q']} «{ind_name}»?", faq_best_a),
        (copy["faq_worst_q"],
         f"{copy['faq_worst_a_lead']} {bottom[-1][1]} — {_vu(bottom[-1][2])}."),
        (faq_year_q, faq_year_a),
    ]
    faq_h2 = _rt("region_rating.faq_h2") or "Вопросы и ответы"
    faq_html = f"<section class=\"seo-section\"><h2>{escape(faq_h2)}</h2>" + "".join(
        f'<div class="seo-faq"><h3>{escape(q)}</h3><p>{escape(a)}</p></div>' for q, a in faq
    ) + "</section>"

    siblings = (await db.execute(
        select(RegionIndicator)
        .where(RegionIndicator.section_num == indicator.section_num,
               RegionIndicator.code != code,
               RegionIndicator.is_listed.is_(True))
        .order_by(RegionIndicator.code)
        .limit(12)
    )).scalars().all()
    siblings_html = ""
    if siblings:
        sib_h2 = (
            (_rt("region_rating.siblings_rankings", section=section_name)
             if achievement else
             _rt("region_rating.siblings_indicators", section=section_name))
            or (
                f"Другие рейтинги раздела «{section_name}»"
                if achievement
                else f"Другие показатели раздела «{section_name}»"
            )
        )
        items = "".join(
            f'<li><a href="{escape(paths.region_rating(sib.code))}">{escape(_icopy(sib)["name"] or sib.name)}</a></li>'
            for sib in siblings
        )
        siblings_html = (
            f"<section class=\"seo-section\"><h2>{escape(sib_h2)}</h2>"
            f"<ul class=\"seo-pills\">{items}</ul></section>"
        )

    macro_code = MACRO_BY_TABLE.get(indicator.table_code or "")
    macro_html = ""
    if macro_code:
        macro_h2 = _rt("region_rating.macro_h2") or "Общероссийская динамика"
        macro_p = _rt(
            "region_rating.macro_p",
            href=escape(paths.russia_indicator(macro_code)),
        ) or (
            f"Показатель по России в целом, с более частым обновлением и прогнозом — "
            f"на карточке <a href=\"{escape(paths.russia_indicator(macro_code))}\">общероссийского "
            f"индикатора</a>."
        )
        macro_html = (
            f"<section class=\"seo-section\"><h2>{escape(macro_h2)}</h2>"
            f"<p>{macro_p}</p></section>"
        )

    title = _rt("region_rating.title", indicator=ind_name, year=last_year) or (
        f"Рейтинг регионов России: {ind_name} ({last_year})"
        if achievement
        else f"{ind_name} по регионам России ({last_year})"
    )
    desc = _rt("region_rating.description", indicator=ind_name, year=last_year) or (
        f"{ind_name} по регионам России за {last_year} год: "
        f"{copy['meta_rank_word']} всех {total} субъектов РФ. "
        f"{copy['desc_best']} — {top[0][1]} ({_vu(top[0][2])}). "
        f"Полная таблица, данные Росстата."
    )
    h1 = _rt("region_rating.h1", indicator=ind_name, year=last_year) or (
        f"{ind_name}: {copy['h1_suffix']}, {last_year} год"
    )

    crumb_label = ind_name
    if achievement:
        crumb_label = (
            f"Ranking: {ind_name}"
            if _rt("region_rating.title")
            else f"Рейтинг: {ind_name}"
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
                    "url": _absolute(paths.region_indicator(s, code)),
                }
                for i, (s, n, _v) in enumerate(rows[:10], 1)
            ],
        },
    ]

    rf_tile = ""
    if rf_value is not None:
        rf_label = _rt("region_rating.russia_tile") or "Россия в целом"
        rf_tile = f'<div class="seo-tile"><span>{escape(rf_label)}</span><b>{escape(_vu(rf_value))}</b></div>'
    data_for = _rt("region_rating.data_for") or "Данные за"
    year_label = _rt("region_rating.year_suffix", year=last_year) or f"{last_year} год"
    tiles_html = f"""<div class="seo-tiles">
<div class="seo-tile"><span>{escape(copy["best_tile"])} — {escape(top[0][1])}</span><b>{escape(_vu(top[0][2]))}</b></div>
{rf_tile}
<div class="seo-tile"><span>{escape(copy["worst_tile"])} — {escape(bottom[-1][1])}</span><b>{escape(_vu(bottom[-1][2]))}</b></div>
<div class="seo-tile"><span>{escape(data_for)}</span><b>{escape(year_label)}</b></div>
</div>"""

    og_path = paths.og_region_rating(code)
    rating_alt = _rt(
        "region_rating.alt",
        indicator=ind_name,
        rank_word=copy["meta_rank_word"],
        year=last_year,
        best_label=copy["desc_best"].lower() if _rt("region_rating.alt") is None else copy["desc_best"].lower(),
        top_name=top[0][1],
        top_value=_vu(top[0][2]),
    ) or (
        f"{ind_name} по регионам России — {copy['meta_rank_word']} {last_year} года, "
        f"{copy['desc_best'].lower()} — {top[0][1]} ({_vu(top[0][2])})"
    )
    figure_html = (
        f'<figure class="seo-chart"><a class="seo-chart-link" '
        f'href="{escape(paths.region_rating(code))}#chart">'
        f'<img src="{escape(og_path)}" alt="{escape(rating_alt)}" '
        f'width="1200" height="630" loading="eager"></a>'
        f"<figcaption>{escape(ind_name)}: {escape(copy['figcaption'])}, {escape(year_label)}. "
        f"Источник: Росстат. forecasteconomy.com</figcaption></figure>"
    )
    # Prefer EN source label when locale is EN.
    if _rt("region_rating.source_h2"):
        figure_html = figure_html.replace(
            "Источник: Росстат.", "Source: Rosstat."
        )

    map_h2 = _rt("region_rating.map_h2") or "На карте регионов"
    map_p = _rt(
        "region_rating.map_p",
        href=escape(paths.region_map(code)),
        indicator=escape(ind_name),
    ) or (
        f"Тот же показатель на интерактивной карте России — цвет регионов "
        f"по значению, ползунок по годам: "
        f"<a href=\"{escape(paths.region_map(code))}\">открыть карту «{escape(ind_name)}»</a>."
    )
    map_html = (
        f"<section class=\"seo-section\"><h2>{escape(map_h2)}</h2>"
        f"<p>{map_p}</p></section>"
    )

    regions_n = _rt("region_rating.regions_n", n=total) or f"{total} регионов"
    source_h2 = _rt("region_rating.source_h2") or "Источник данных"
    source_p = _rt(
        "region_rating.source_p",
        year=last_year,
        unit=unit or ("source units" if _rt("region_rating.source_h2") else "единицы источника"),
    ) or (
        f"Сборник Росстата «Регионы России. Социально-экономические показатели». "
        f"Значения за {last_year} год, единицы: {unit or 'единицы источника'}. "
        f"По каждому региону доступна страница с полной динамикой показателя с 1990 года."
    )

    body = f"""<div class="seo-page">
{_breadcrumbs_nav(rating_trail)}
<p class="seo-eyebrow">{escape(section_name)} — {escape(copy["eyebrow"])}</p>
<h1>{escape(h1)}</h1>
<p>{escape(intro)}</p>
{figure_html}
{tiles_html}
<section class="seo-section"><h2>{escape(copy["section_h2"])} ({escape(regions_n)})</h2>{table_html}</section>
{faq_html}
{map_html}
{macro_html}
{siblings_html}
<section class="seo-section"><h2>{escape(source_h2)}</h2>
<p>{escape(source_p)}</p></section>
</div>"""

    json_ld.append({
        "@context": "https://schema.org",
        "@type": "ImageObject",
        "contentUrl": _absolute(og_path),
        "url": _absolute(og_path),
        "name": _rt(
            "region_rating.image_name",
            indicator=ind_name,
            rank_word=copy["meta_rank_word"],
            year=last_year,
        ) or f"{ind_name} — {copy['meta_rank_word']} регионов России, {last_year}",
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
        keywords=_rt("region_rating.keywords", indicator=ind_name) or (
            f"{ind_name} по регионам, {ind_name} по субъектам рф, "
            f"{ind_name} сравнение регионов"
        ),
        og_image=_absolute(og_path),
    )
    return 200, html


async def render_region_ratings_hub_html(db: AsyncSession) -> tuple[int, str]:
    """Хаб рейтингов регионов: /russia/region-rating."""
    rating_inds = (await db.execute(
        select(RegionIndicator)
        .where(RegionIndicator.is_listed.is_(True))
        .order_by(RegionIndicator.section_num, RegionIndicator.code)
    )).scalars().all()
    if not rating_inds:
        return 404, "<h1>Рейтинги не найдены</h1>"

    by_section: dict[str, list[tuple[str, str]]] = {}
    for ind in rating_inds:
        copy = _icopy(ind)
        section = copy["section"] or ind.section_name or "Показатели"
        by_section.setdefault(section, []).append((ind.code, copy["name"] or ind.name))

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
    title = _rt("region_rating_hub.title") or "Рейтинги регионов России по показателям Росстата"
    desc = _rt("region_rating_hub.description") or (
        "Сравнение субъектов Российской Федерации по социально-экономическим "
        "показателям: полные таблицы мест, лидеры и аутсайдеры. Данные Росстата."
    )
    h1 = _rt("region_rating_hub.h1") or "Рейтинги регионов России"
    eyebrow = _rt("region_rating_hub.eyebrow") or "Региональная статистика Росстата"
    lead = _rt("region_rating_hub.lead") or (
        "Выберите показатель, чтобы увидеть полный рейтинг субъектов РФ за последний "
        "доступный год: место каждого региона, лидеры и аутсайдеры, ссылки на динамику "
        "по субъектам."
    )
    body = f"""<div class="seo-page">
{_breadcrumbs_nav(trail)}
<p class="seo-eyebrow">{escape(eyebrow)}</p>
<h1>{escape(h1)}</h1>
<p>{escape(lead)}</p>
{''.join(sections)}
</div>"""
    html = await build_document(
        title=title,
        description=desc,
        canonical_path=paths.region_rating_hub(),
        body=body,
        json_ld=[_breadcrumbs(trail)],
        keywords=_rt("region_rating_hub.keywords") or (
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
        title = _rt("region_map.overview_title") or "Карта регионов России — обзор субъектов РФ"
        desc = _rt("region_map.overview_desc") or (
            "Интерактивная карта 85 субъектов Российской Федерации: откройте "
            "профиль региона или выберите показатель Росстата для цветовой шкалы "
            "по годам. Forecast Economy."
        )
        crumb_map = "Map" if _rt("region_map.overview_h1") else "Карта"
        map_overview_trail = crumbs.trail(
            crumbs.home(),
            crumbs.russia(),
            crumbs.regions(),
            (paths.region_map("overview"), crumb_map),
        )
        # Popular slice labels from EN indicator overlay when locale=en.
        from app.services.seo_i18n import region_indicator_copy
        wage_name = region_indicator_copy(
            DEFAULT_MAP_CODE, name_ru="Среднемесячная заработная плата", unit_ru="",
        )["name"]
        pop_name = region_indicator_copy(
            "chislennost-naseleniya", name_ru="Численность населения", unit_ru="",
        )["name"]
        unemp_name = region_indicator_copy(
            "uroven-bezrabotitsy", name_ru="Уровень безработицы", unit_ru="",
        )["name"]
        eyebrow = _rt("region_map.overview_eyebrow") or "Интерактивная карта субъектов РФ"
        h1 = _rt("region_map.overview_h1") or "Карта регионов России"
        lead = _rt("region_map.overview_lead") or (
            "Обзорный режим: клик по субъекту открывает профиль региона со всеми "
            "показателями сборника Росстата. Выберите показатель на странице, чтобы "
            "увидеть цветовую карту и динамику по годам."
        )
        pop_h2 = _rt("region_map.overview_popular_h2") or "Популярные срезы на карте"
        rank_h2 = _rt("region_map.overview_rankings_h2") or "Рейтинги"
        rank_p = _rt(
            "region_map.overview_rankings_p",
            href=paths.region_rating_hub(),
        ) or (
            f"Таблицу мест по показателю смотрите в разделе "
            f'<a href="{paths.region_rating_hub()}">рейтингов регионов</a>.'
        )
        body = f"""<div class="seo-page">
{_breadcrumbs_nav(map_overview_trail)}
<p class="seo-eyebrow">{escape(eyebrow)}</p>
<h1>{escape(h1)}</h1>
<p>{escape(lead)}</p>
<section class="seo-section"><h2>{escape(pop_h2)}</h2>
<ul>
<li><a href="{escape(paths.region_map(DEFAULT_MAP_CODE))}">{escape(wage_name)}</a></li>
<li><a href="{paths.region_map('chislennost-naseleniya')}">{escape(pop_name)}</a></li>
<li><a href="{paths.region_map('uroven-bezrabotitsy')}">{escape(unemp_name)}</a></li>
</ul></section>
<section class="seo-section"><h2>{escape(rank_h2)}</h2>
<p>{rank_p}</p></section>
</div>"""
        json_ld = [_breadcrumbs(map_overview_trail)]
        html = await build_document(
            title=title,
            description=desc,
            canonical_path=paths.region_map("overview"),
            body=body,
            json_ld=json_ld,
            keywords=_rt("region_map.overview_keywords") or (
                "карта регионов россии, субъекты рф на карте, регионы россии статистика"
            ),
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

    icopy = _icopy(indicator)
    ind_name = icopy["name"] or indicator.name
    section_name = icopy["section"] or indicator.section_name
    unit = icopy["unit"] or (indicator.unit or "")
    rows = [(s, _rname(s, n), v) for s, n, v in rows]
    total = len(rows)
    top = rows[:3]
    bottom = rows[-3:]

    def _vu(v) -> str:
        return f"{_fmt(float(v))} {unit}".strip()

    if map_year == last_year:
        year_note = (_rt("region_map.year_note") or " за {year} год").format(year=map_year)
    else:
        year_note = (_rt("region_map.year_note_stale") or (
            " за {year} год (последний доступный — {last_year})"
        )).format(year=map_year, last_year=last_year)
    title = _rt("region_map.title", indicator=ind_name, year=map_year) or (
        f"Карта регионов России: {ind_name} ({map_year})"
    )
    desc = _rt("region_map.description", indicator=ind_name, year=map_year) or (
        f"{ind_name} на карте 85 субъектов РФ{year_note}. "
        f"{copy['desc_best']} — {top[0][1]} ({_vu(top[0][2])}), "
        f"{copy['worst_tile'].lower()} — {bottom[-1][1]} ({_vu(bottom[-1][2])}). "
        f"Интерактивная карта и таблица, данные Росстата."
    )
    h1 = _rt("region_map.h1", indicator=ind_name, year=map_year) or (
        f"{ind_name} на карте регионов России, {map_year} год"
    )

    canonical = paths.region_map(code)
    if year is not None and year in years_list:
        canonical = f"{canonical}?year={year}"

    og_path = paths.og_region_rating(code)
    map_alt = _rt(
        "region_map.alt",
        indicator=ind_name,
        year=map_year,
        best_label=copy["desc_best"].lower(),
        top_name=top[0][1],
        top_value=_vu(top[0][2]),
    ) or (
        f"{ind_name} по регионам России — карта, {map_year} год, "
        f"{copy['desc_best'].lower()} — {top[0][1]} ({_vu(top[0][2])})"
    )
    caption = _rt(
        "region_map.caption", indicator=ind_name, year=map_year,
    ) or (
        f"{ind_name} по регионам, {map_year} год. "
        f"Источник: Росстат. forecasteconomy.com"
    )
    figure_html = (
        f'<figure class="seo-chart"><a class="seo-chart-link" '
        f'href="{escape(paths.region_map(code))}#chart">'
        f'<img src="{escape(og_path)}" alt="{escape(map_alt)}" '
        f'width="1200" height="630" loading="eager"></a>'
        f"<figcaption>{escape(caption)}</figcaption></figure>"
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

    crumb_label = (_rt("region_map.crumb") or "Карта: {indicator}").format(indicator=ind_name)
    map_trail = crumbs.trail(
        crumbs.home(),
        crumbs.russia(),
        crumbs.regions(),
        (paths.region_map(code), crumb_label),
    )
    json_ld = [
        _breadcrumbs(map_trail),
        {
            "@context": "https://schema.org",
            "@type": "WebApplication",
            "name": title,
            "description": desc,
            "url": _absolute(canonical),
            "applicationCategory": "BusinessApplication",
            "operatingSystem": "Any",
            "isAccessibleForFree": True,
            "inLanguage": "en" if _rt("region_map.lead") else "ru-RU",
        },
        {
            "@context": "https://schema.org",
            "@type": "ImageObject",
            "contentUrl": _absolute(og_path),
            "url": _absolute(og_path),
            "name": (
                f"{ind_name} — regions map, {map_year}"
                if _rt("region_map.lead")
                else f"{ind_name} — карта регионов, {map_year}"
            ),
            "description": map_alt,
            "representativeOfPage": True,
            "width": 1200,
            "height": 630,
        },
    ]

    rating_link_label = (
        (_rt("region_map.rating_label_achievement") or "рейтинг регионов по «{indicator}»")
        if achievement
        else (_rt("region_map.rating_label_list") or "таблица регионов по «{indicator}»")
    ).format(indicator=ind_name)
    eyebrow = (_rt("region_map.eyebrow") or "{section} — карта регионов").format(
        section=section_name
    )
    lead = _rt(
        "region_map.lead",
        total=total,
        indicator=ind_name,
        year_note=year_note,
        first_year=years_list[0],
        last_year=last_year,
    ) or (
        f"Интерактивная карта {total} субъектов Российской Федерации по показателю "
        f"«{ind_name}»{year_note}. Цвет региона отражает значение "
        f"относительно других субъектов; ползунок на странице переключает годы "
        f"с {years_list[0]} по {last_year}. Данные — сборник Росстата "
        f"«Регионы России. Социально-экономические показатели»."
    )
    tile_year = _rt("region_map.tile_year") or "Год на карте"
    tile_regions = _rt("region_map.tile_regions") or "Регионов на срезе"
    leaders_h2 = (_rt("region_map.leaders_h2") or "{label} {year} года").format(
        label=copy["map_leaders_h2"], year=map_year,
    )
    rating_p = _rt(
        "region_map.rating_p",
        href=escape(paths.region_rating(code)),
        label=escape(rating_link_label),
    ) or (
        f"Полная таблица — "
        f'<a href="{escape(paths.region_rating(code))}">{escape(rating_link_label)}</a>.'
    )
    years_h2 = _rt("region_map.years_h2") or "Другие годы"
    source_h2 = _rt("region_map.source_h2") or "Источник"
    source_p = _rt(
        "region_map.source_p",
        unit=unit or ("source units" if _rt("region_map.source_p") else "единицы источника"),
    ) or (
        f"Росстат, единицы: {unit or 'единицы источника'}. После загрузки страницы "
        f"доступна интерактивная карта с выбором года и переходом в карточку региона."
    )
    body = f"""<div class="seo-page">
{_breadcrumbs_nav(map_trail)}
<p class="seo-eyebrow">{escape(eyebrow)}</p>
<h1>{escape(h1)}</h1>
<p>{escape(lead)}</p>
{figure_html}
<div class="seo-tiles">
<div class="seo-tile"><span>{escape(copy["best_tile"])} — {escape(top[0][1])}</span><b>{escape(_vu(top[0][2]))}</b></div>
<div class="seo-tile"><span>{escape(copy["worst_tile"])} — {escape(bottom[-1][1])}</span><b>{escape(_vu(bottom[-1][2]))}</b></div>
<div class="seo-tile"><span>{escape(tile_year)}</span><b>{map_year}</b></div>
<div class="seo-tile"><span>{escape(tile_regions)}</span><b>{total}</b></div>
</div>
<section class="seo-section"><h2>{escape(leaders_h2)}</h2><ol>{leaders}</ol>
<p>{rating_p}</p>
</section>
<section class="seo-section"><h2>{escape(years_h2)}</h2><ul class="seo-pills">{year_links}</ul></section>
<section class="seo-section"><h2>{escape(source_h2)}</h2>
<p>{escape(source_p)}</p>
</section>
</div>"""

    html = await build_document(
        title=title,
        description=desc,
        canonical_path=canonical,
        body=body,
        json_ld=json_ld,
        keywords=_rt(
            "region_map.keywords", indicator=ind_name, year=map_year,
        ) or (
            f"{ind_name} карта регионов, {ind_name} по регионам россии, "
            f"карта субъектов рф {ind_name}, {ind_name} {map_year}"
        ),
        og_image=_absolute(og_path),
    )
    return 200, html


_MONTH_NAMES_GEN = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)


def _month_label(month_int: int) -> str:
    """YYYYMM → «май 2012» (для осей, таблиц, alt)."""
    return f"{_MONTH_NAMES_GEN[month_int % 100 - 1]} {month_int // 100}"


async def _render_region_indicator_monthly(
    slug: str,
    code: str,
    region: Region,
    indicator: RegionIndicator,
    rows: list,
    db: AsyncSession,
) -> tuple[int, str]:
    """SSR-карточка месячного показателя региона (цены на топливо, ЕМИСС).

    Годовой рендер строит тексты вокруг «года»: контрольные годы, рейтинг по
    последнему году, «за пять лет». Для месячного ряда своя аналогичная
    обвязка: последний месяц, изменение к предыдущему месяцу и к тому же
    месяцу прошлого года, полная таблица по месяцам. Рейтинг по цене региона
    не строится — уровень цены зависит от структуры рынка и логистики,
    «место в рейтинге цен» вводило бы в заблуждение.
    """
    series = [(int(m), float(v)) for m, v in rows]
    first_period, first_value = series[0]
    last_period, last_value = series[-1]
    first_year = first_period // 100
    last_year = last_period // 100
    by_period = dict(series)
    prev_value = series[-2][1] if len(series) > 1 else None
    year_ago_value = by_period.get(last_period - 100)

    region_name = _rname(region.slug, region.name)
    icopy = _icopy(indicator)
    ind_name = icopy["name"] or indicator.name
    unit_loc = icopy["unit"] or (indicator.unit or "")
    section_name = icopy["section"] or indicator.section_name

    rf = None if region.slug == "russia" else await _region(db, "russia")
    rf_last = None
    if rf:
        rf_last = (await db.execute(
            select(RegionMonthlyPoint.value)
            .where(RegionMonthlyPoint.indicator_id == indicator.id,
                   RegionMonthlyPoint.region_id == rf.id,
                   RegionMonthlyPoint.month == last_period)
        )).scalar_one_or_none()

    unit = unit_loc
    unit_sfx = f" {escape(unit)}" if unit else ""
    last_label = _month_label(last_period)
    first_label = _month_label(first_period)

    paragraphs = []
    p1 = (
        f"{escape(ind_name)} в регионе {escape(region_name)} "
        f"в {escape(last_label)}: {_fmt(last_value)}{unit_sfx}."
    )
    mom = _pct(last_value, prev_value)
    if mom:
        p1 += f" К предыдущему месяцу показатель {mom}."
    yoy = _pct(last_value, year_ago_value)
    if yoy:
        yoy_label = _month_label(last_period - 100)
        p1 += f" К {escape(yoy_label)} — {yoy}."
    paragraphs.append(p1)

    p2 = (
        f"Наблюдение ведётся с {escape(first_label)} — данные публикуются ежемесячно. "
        f"Это средние потребительские цены отчётного месяца, а не котировка конкретной заправки."
    )
    paragraphs.append(p2)

    if rf_last is not None:
        if abs(last_value - float(rf_last)) / (abs(float(rf_last)) or 1) < 0.005:
            rel = "на уровне"
        elif last_value > float(rf_last):
            rel = "выше"
        else:
            rel = "ниже"
        p3 = (
            f"Среднероссийская цена в {escape(last_label)} — "
            f"{_fmt(float(rf_last))}{unit_sfx}: регион {rel} среднего по стране. "
            f"Региональные цены различаются из-за логистики, структуры сети "
            f"продаж и локальных акцизов и сборов."
        )
        paragraphs.append(p3)

    values_desc = [v for _p, v in series]
    vmax = max(values_desc)
    vmin = min(values_desc)
    p_at = series[values_desc.index(vmax)][0]
    n_at = series[values_desc.index(vmin)][0]
    paragraphs.append(
        f"Максимум за весь период наблюдений — {_fmt(vmax)}{unit_sfx} "
        f"({escape(_month_label(p_at))}), минимум — {_fmt(vmin)}{unit_sfx} "
        f"({escape(_month_label(n_at))})."
    )
    paragraphs_html = "".join(f"<p>{p}</p>" for p in paragraphs)

    # контрольные точки: январь каждого пятого года + последний месяц
    checkpoint_periods = [
        y * 100 + 1 for y in range(first_year, last_year, 5) if y * 100 + 1 in by_period
    ]
    checkpoints_html = ""
    if len(checkpoint_periods) >= 3:
        cp_items = "".join(
            f"<li>{escape(_month_label(p))} — {_fmt(by_period[p])}{unit_sfx}</li>"
            for p in checkpoint_periods
        )
        cp_items += (
            f"<li>{escape(last_label)} — {_fmt(last_value)}{unit_sfx}</li>"
        )
        cp_h2 = f"{escape(ind_name)} в регионе {escape(region_name)} по контрольным месяцам"
        checkpoints_html = (
            f'<section class="seo-section"><h2>{cp_h2}</h2>'
            f"<ul>{cp_items}</ul></section>"
        )

    faq: list[tuple[str, str]] = [
        (
            f"Какая цена на «{ind_name.split(',')[0].lower()}» в регионе {region_name}?",
            f"В {last_label} — {_fmt(last_value)}{unit}. "
            f"Это средняя потребительская цена по данным Росстата (ЕМИСС).",
        ),
        (
            "Как изменилась цена за последний месяц?",
            (
                f"С {escape(_month_label(last_period - 100))} по {escape(last_label)} "
                f"показатель {mom}."
                if mom else
                f"К предыдущему месяцу значение почти не изменилось."
            ),
        ),
        (
            "Откуда взяты данные и как часто они обновляются?",
            "Источник — система показателей Росстата (ЕМИСС), средние "
            "потребительские цены на топливо по субъектам РФ. Данные месячные, "
            "обновляются ежемесячно после очередной публикации.",
        ),
    ]
    faq_h2 = "Вопросы и ответы"
    faq_html = (
        f'<section class="seo-section"><h2>{escape(faq_h2)}</h2>'
        + "".join(f"<h3>{escape(q)}</h3><p>{escape(a)}</p>" for q, a in faq)
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

    # соседи по округу
    district_html = ""
    if region.kind == "region" and region.district_slug:
        neighbors = (await db.execute(
            select(Region.slug, Region.name)
            .where(Region.district_slug == region.district_slug,
                   Region.kind == "region",
                   Region.slug != region.slug)
            .order_by(Region.sort_order)
        )).all()
        neighbor_periods = []
        if neighbors:
            n_slugs = [s for s, _n in neighbors]
            n_ids = dict((await db.execute(
                select(Region.slug, Region.id).where(Region.slug.in_(n_slugs))
            )).all())
            nb_rows = (await db.execute(
                select(RegionMonthlyPoint.region_id, RegionMonthlyPoint.value)
                .where(RegionMonthlyPoint.indicator_id == indicator.id,
                       RegionMonthlyPoint.region_id.in_(set(n_ids.values())),
                       RegionMonthlyPoint.month == last_period)
            )).all()
            nb_by_slug = {n_ids[rid]: v for rid, v in nb_rows if rid in n_ids}
            neighbor_periods = [
                (s, n, nb_by_slug.get(s)) for s, n in neighbors if s in nb_by_slug
            ]
        if neighbor_periods:
            items = "".join(
                f'<li><a href="{escape(paths.region_indicator(s, code))}">'
                f"{escape(ind_name)} — {escape(_rname(s, n))}: "
                f"{_fmt(v)}{unit_sfx}</a></li>"
                for s, n, v in neighbor_periods
            )
            n_h2 = "Этот показатель у соседей по округу"
            district_html = (
                f'<section class="seo-section"><h2>{escape(n_h2)}</h2>'
                f"<ul>{items}</ul></section>"
            )

    # таблица по месяцам (полная — 283 строки, помещается в скролл)
    table_h2 = f"{ind_name} по месяцам"
    th_month = "Месяц"
    th_value = unit or "Значение"
    table_rows = "".join(
        f"<tr><td>{escape(_month_label(p))}</td><td>{_fmt(v)}</td></tr>"
        for p, v in reversed(series)
    )
    table_html = (
        f"<h2>{escape(table_h2)}</h2>"
        f"<table><thead><tr><th>{escape(th_month)}</th>"
        f"<th>{escape(th_value)}</th></tr></thead>"
        f"<tbody>{table_rows}</tbody></table>"
    )

    og_path = paths.og_region(slug, code)
    alt = (
        f"{ind_name} — {region_name}: график динамики, "
        f"{first_label} — {last_label}, последнее значение "
        f"{_fmt(last_value)} {unit}"
    )
    caption = (
        f"{ind_name} в регионе {region_name}, {first_year}–{last_year}. "
        f"Источник: Росстат (ЕМИСС)."
    )
    figure_html = (
        f'<figure class="seo-chart"><a class="seo-chart-link" '
        f'href="{escape(paths.region_indicator(slug, code))}#chart">'
        f'<img src="{escape(og_path)}" alt="{escape(alt)}" '
        f'width="1200" height="630" loading="eager"></a>'
        f"<figcaption>{escape(caption)}</figcaption></figure>"
    )

    siblings = (await db.execute(
        select(RegionIndicator)
        .where(RegionIndicator.section_num == indicator.section_num,
               RegionIndicator.code != indicator.code,
               RegionIndicator.is_listed.is_(True))
        .order_by(RegionIndicator.code)
        .limit(10)
    )).scalars().all()
    siblings_html = ""
    if siblings:
        items = "".join(
            f'<li><a href="{escape(paths.region_indicator(slug, sib.code))}">'
            f'{escape(_icopy(sib)["name"] or sib.name)}</a></li>'
            for sib in siblings
        )
        sib_h2 = f"Ещё в разделе «{section_name}»"
        siblings_html = (
            f'<section class="seo-section"><h2>{escape(sib_h2)}</h2>'
            f"<ul>{items}</ul></section>"
        )

    title = (
        f"{ind_name} — {region_name}: {_fmt(last_value)} "
        f"{unit} ({last_label})"
    ).strip()
    desc = (
        f"{ind_name} в регионе {region_name}: {_fmt(last_value)} {unit} "
        f"в {last_label}. Динамика с {first_year} года, график и таблица "
        f"по месяцам, сравнение со среднероссийской ценой. "
        f"Данные Росстата, обновление ежемесячное."
    )

    json_ld = [
        _breadcrumbs(crumbs.region_indicator_trail(
            region_name, paths.region(slug), ind_name,
            paths.region_indicator(slug, code),
        )),
        faq_json_ld,
        {
            "@context": "https://schema.org",
            "@type": "Dataset",
            "name": f"{ind_name} — {region_name}",
            "description": (
                f"{ind_name} ({unit}), {region_name}, "
                f"{first_year}–{last_year}, помесячно. Источник: Росстат (ЕМИСС)."
            ),
            "url": _absolute(paths.region_indicator(slug, code)),
            "temporalCoverage": f"{first_year}/{last_year}",
            "spatialCoverage": region_name,
            "creator": {"@type": "Organization", "name": "Росстат"},
            "license": "https://creativecommons.org/licenses/by/4.0/",
            "image": _absolute(og_path),
        },
        {
            "@context": "https://schema.org",
            "@type": "ImageObject",
            "contentUrl": _absolute(og_path),
            "url": _absolute(og_path),
            "width": 1200,
            "height": 630,
            "name": f"{ind_name} — {region_name}: график",
            "caption": alt,
            "representativeOfPage": True,
        },
    ]

    h1 = f"{ind_name} — {region_name}"
    source_h2 = "Источник данных"
    source_p = (
        f"Система показателей Росстата (ЕМИСС), средние потребительские цены. "
        f"Значения приведены в единицах: {unit or 'единицы источника'}. "
        f"Период наблюдений: {first_label} — {last_label}, обновление ежемесячное."
    )
    body = f"""<div class="seo-page">
{_breadcrumbs_nav(crumbs.region_indicator_trail(
    region_name, paths.region(slug), ind_name,
    paths.region_indicator(slug, code),
))}
<p class="seo-eyebrow">{escape(section_name)} — {escape(region_name)}</p>
<h1>{escape(h1)}</h1>
{figure_html}
{paragraphs_html}
{checkpoints_html}
{table_html}
{faq_html}
{district_html}
{siblings_html}
<section class="seo-section"><h2>{escape(source_h2)}</h2>
<p>{escape(source_p)}</p></section>
</div>"""

    html = await build_document(
        title=title,
        description=desc,
        canonical_path=paths.region_indicator(slug, code),
        body=body,
        json_ld=json_ld,
        keywords=(
            f"{ind_name} {region_name}, {region_name} цены на топливо, "
            f"{ind_name} по месяцам, {region_name} бензин цена, статистика"
        ),
        og_image=_absolute(og_path),
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

    # Частота ряда: месячные витрины (цены на топливо) живут в
    # region_monthly_data, годовые — в region_data. У показателя обычно
    # заполнена только одна из двух таблиц.
    monthly_rows = (await db.execute(
        select(RegionMonthlyPoint.month, RegionMonthlyPoint.value)
        .where(RegionMonthlyPoint.indicator_id == indicator.id,
               RegionMonthlyPoint.region_id == region.id)
        .order_by(RegionMonthlyPoint.month)
    )).all()

    if monthly_rows:
        return await _render_region_indicator_monthly(slug, code, region, indicator, monthly_rows, db)

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

    region_name = _rname(region.slug, region.name)
    icopy = _icopy(indicator)
    ind_name = icopy["name"] or indicator.name
    unit_loc = icopy["unit"] or (indicator.unit or "")
    section_name = icopy["section"] or indicator.section_name

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

    unit = unit_loc
    unit_sfx = f" {escape(unit)}" if unit else ""

    # --- уникальный автоконтент ---
    paragraphs = []
    p1_tpl = _rt("region_indicator.p1")
    if p1_tpl:
        p1 = p1_tpl.format(
            indicator=escape(ind_name), region=escape(region_name), year=last_year,
            value=_fmt(last_value), unit=unit_sfx,
        )
    else:
        p1 = (
            f"{escape(ind_name)} в регионе {escape(region_name)} "
            f"в {last_year} году: {_fmt(last_value)}{unit_sfx}."
        )
    prev = by_year.get(last_year - 1)
    ch1 = _pct(last_value, prev)
    if ch1:
        ch_tpl = _rt("region_indicator.p1_change")
        p1 += (ch_tpl.format(change=ch1) if ch_tpl else f" За год показатель {ch1}.")
    paragraphs.append(p1)

    base5 = by_year.get(last_year - 5)
    ch5 = _pct(last_value, base5)
    chfull = _pct(last_value, first_value)
    p2 = ""
    if ch5:
        p2_tpl = _rt("region_indicator.p2_5y")
        p2 += (
            p2_tpl.format(year=last_year - 5, change=ch5)
            if p2_tpl
            else f"За пять лет (с {last_year - 5} года) показатель {ch5}."
        )
    if chfull and first_year < last_year - 5:
        full_tpl = _rt("region_indicator.p2_full")
        p2 += (
            full_tpl.format(
                first_year=first_year, change=chfull,
                first_value=_fmt(first_value), last_value=_fmt(last_value), unit=unit_sfx,
            )
            if full_tpl
            else (
                f" С {first_year} года, начала доступного ряда, показатель {chfull} "
                f"(с {_fmt(first_value)} до {_fmt(last_value)}{unit_sfx})."
            )
        )
    if p2:
        paragraphs.append(p2)

    if position and region.kind == "region":
        rating_label = (
            (_rt("region_indicator.rating_full") or "полный рейтинг регионов")
            if achievement
            else (_rt("region_indicator.rating_table") or "таблица по всем регионам")
        )
        rating_ref = (
            f' (<a href="{escape(paths.region_rating(code))}">{escape(rating_label)}</a>)'
            if len(rank_rows) >= 10 else ""
        )
        p3_tpl = _rt("region_indicator.p3")
        rank_phrase = _rank_phrase(position, len(rank_rows), achievement=achievement)
        if p3_tpl:
            p3 = p3_tpl.format(
                region=escape(region_name), rank=rank_phrase,
                year=last_year, rating_ref=rating_ref,
            )
        else:
            p3 = (
                f"По значению этого показателя {escape(region_name)} "
                f"{rank_phrase} в {last_year} году{rating_ref}."
            )
        if rf_last is not None:
            if abs(last_value - float(rf_last)) / (abs(float(rf_last)) or 1) < 0.005:
                rel = _rt("region_indicator.rel_level") or "на уровне"
            elif last_value > float(rf_last):
                rel = _rt("region_indicator.rel_above") or "выше"
            else:
                rel = _rt("region_indicator.rel_below") or "ниже"
            rf_tpl = _rt("region_indicator.p3_rf")
            if rf_tpl:
                p3 += rf_tpl.format(
                    rf_value=_fmt(float(rf_last)), unit=unit_sfx, rel=rel,
                )
            else:
                p3 += (
                    f" Общероссийское значение — {_fmt(float(rf_last))}{unit_sfx}: "
                    f"регион {rel} среднего по стране."
                )
        paragraphs.append(p3)

    values_desc = [v for _y, v in series]
    vmax = max(values_desc); vmin = min(values_desc)
    ymax = series[[v for _y, v in series].index(vmax)][0]
    ymin = series[[v for _y, v in series].index(vmin)][0]
    p4_tpl = _rt("region_indicator.p4")
    if p4_tpl:
        paragraphs.append(p4_tpl.format(
            vmax=_fmt(vmax), vmin=_fmt(vmin), ymax=ymax, ymin=ymin, unit=unit_sfx,
        ))
    else:
        paragraphs.append(
            f"Максимум за весь период наблюдений — {_fmt(vmax)}{unit_sfx} в {ymax} году, "
            f"минимум — {_fmt(vmin)}{unit_sfx} в {ymin} году. "
            f"Данные обновляются ежегодно по мере публикации сборника Росстата."
        )

    paragraphs_html = "".join(f"<p>{p}</p>" for p in paragraphs)

    checkpoint_years = [y for y in range(1990, last_year, 5) if y in by_year]
    checkpoints_html = ""
    if len(checkpoint_years) >= 3:
        cp_item_tpl = _rt("region_indicator.checkpoint_item") or "{year} год — {value}{unit}"
        cp_items = "".join(
            f"<li>{cp_item_tpl.format(year=y, value=_fmt(by_year[y]), unit=unit_sfx)}</li>"
            for y in checkpoint_years
        )
        cp_items += (
            f"<li>{cp_item_tpl.format(year=last_year, value=_fmt(last_value), unit=unit_sfx)}</li>"
        )
        cp_h2 = (_rt("region_indicator.checkpoints_h2") or (
            "{indicator} в регионе {region} по контрольным годам"
        )).format(indicator=ind_name, region=region_name)
        checkpoints_html = (
            f'<section class="seo-section"><h2>{escape(cp_h2)}</h2>'
            f"<ul>{cp_items}</ul></section>"
        )

    faq: list[tuple[str, str]] = []
    faq.append((
        (_rt("region_indicator.faq_value_q") or (
            "Какое значение показателя «{indicator}» в регионе {region}?"
        )).format(indicator=ind_name, region=region_name),
        (_rt("region_indicator.faq_value_a") or (
            "По данным Росстата за {year} год — {value} {unit}."
        )).format(year=last_year, value=_fmt(last_value), unit=unit).strip(),
    ))
    if position and region.kind == "region":
        if achievement:
            faq.append((
                (_rt("region_indicator.faq_rank_q") or (
                    "Какое место занимает {region} по этому показателю среди регионов России?"
                )).format(region=region_name),
                (_rt("region_indicator.faq_rank_a") or (
                    "{position}-е место из {total} субъектов РФ по итогам {year} года."
                )).format(position=position, total=len(rank_rows), year=last_year),
            ))
        else:
            faq.append((
                (_rt("region_indicator.faq_list_q") or (
                    "Какое положение в списке по величине показателя занимает {region}?"
                )).format(region=region_name),
                (_rt("region_indicator.faq_list_a") or (
                    "{position}-е из {total} субъектов РФ при упорядочивании "
                    "по убыванию значения за {year} год."
                )).format(position=position, total=len(rank_rows), year=last_year),
            ))
    if ch1:
        faq.append((
            _rt("region_indicator.faq_change_q") or "Как изменился показатель за последний год?",
            (_rt("region_indicator.faq_change_a") or (
                "С {prev_year} по {year} год показатель {change}."
            )).format(prev_year=last_year - 1, year=last_year, change=ch1),
        ))
    faq.append((
        _rt("region_indicator.faq_source_q") or (
            "Откуда взяты данные и как часто они обновляются?"
        ),
        _rt("region_indicator.faq_source_a") or (
            "Источник — официальный сборник Росстата «Регионы России. Социально-экономические "
            "показатели». Данные годовые, обновляются после выхода нового выпуска сборника."
        ),
    ))
    faq_h2 = _rt("region_indicator.faq_h2") or "Вопросы и ответы"
    faq_html = (
        f'<section class="seo-section"><h2>{escape(faq_h2)}</h2>'
        + "".join(f"<h3>{escape(q)}</h3><p>{escape(a)}</p>" for q, a in faq)
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

    macro_code = MACRO_BY_TABLE.get(indicator.table_code or "")
    macro_html = ""
    if macro_code:
        macro_h2 = _rt("region_indicator.macro_h2") or "Общероссийский показатель"
        macro_p = _rt(
            "region_indicator.macro_p",
            href=escape(paths.russia_indicator(macro_code)),
            compare=escape(f"/compare?codes={macro_code},r:{slug}:{code}"),
        ) or (
            f"Динамика по России в целом, с более частым обновлением и прогнозом — "
            f"на странице <a href=\"{escape(paths.russia_indicator(macro_code))}\">общероссийского "
            f"индикатора</a>. Сравнить регион с федеральным уровнем можно в разделе "
            f"<a href=\"/compare?codes={escape(macro_code)},r:{escape(slug)}:{escape(code)}\">"
            f"«Сравнение»</a>."
        )
        macro_html = (
            f'<section class="seo-section"><h2>{escape(macro_h2)}</h2>'
            f"<p>{macro_p}</p></section>"
        )

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
                f"{escape(ind_name)} — {escape(_rname(s, n))}</a></li>"
                for s, n in neighbors
            )
            n_h2 = _rt("region_indicator.neighbors_h2") or (
                "Этот показатель у соседей по округу"
            )
            district_html = (
                f'<section class="seo-section"><h2>{escape(n_h2)}</h2>'
                f"<ul>{items}</ul></section>"
            )

    table_h2 = (_rt("region_indicator.table_h2") or "{indicator} по годам").format(
        indicator=ind_name
    )
    th_year = _rt("region_indicator.th_year") or "Год"
    th_value = unit or (_rt("region_indicator.th_value") or "Значение")
    table_rows = "".join(
        f"<tr><td>{y}</td><td>{_fmt(v)}</td></tr>" for y, v in reversed(series)
    )
    table_html = (
        f"<h2>{escape(table_h2)}</h2>"
        f"<table><thead><tr><th>{escape(th_year)}</th>"
        f"<th>{escape(th_value)}</th></tr></thead>"
        f"<tbody>{table_rows}</tbody></table>"
    )

    og_path = paths.og_region(slug, code)
    alt = (_rt("region_indicator.alt") or (
        "{indicator} — {region}: график динамики {first}–{last}, "
        "последнее значение {value} {unit}"
    )).format(
        indicator=ind_name, region=region_name,
        first=first_year, last=last_year,
        value=_fmt(last_value), unit=unit,
    ).strip()
    caption = (_rt("region_indicator.caption") or (
        "{indicator} в регионе {region}, {first}–{last}. Источник: Росстат."
    )).format(
        indicator=ind_name, region=region_name, first=first_year, last=last_year,
    )
    figure_html = (
        f'<figure class="seo-chart"><a class="seo-chart-link" '
        f'href="{escape(paths.region_indicator(slug, code))}#chart">'
        f'<img src="{escape(og_path)}" alt="{escape(alt)}" '
        f'width="1200" height="630" loading="eager"></a>'
        f"<figcaption>{escape(caption)}</figcaption></figure>"
    )

    siblings = (await db.execute(
        select(RegionIndicator)
        .where(RegionIndicator.section_num == indicator.section_num,
               RegionIndicator.code != indicator.code,
               RegionIndicator.is_listed.is_(True))
        .order_by(RegionIndicator.code)
        .limit(10)
    )).scalars().all()
    siblings_html = ""
    if siblings:
        items = "".join(
            f'<li><a href="{escape(paths.region_indicator(slug, sib.code))}">'
            f'{escape(_icopy(sib)["name"] or sib.name)}</a></li>'
            for sib in siblings
        )
        sib_h2 = (_rt("region_indicator.siblings_h2") or (
            "Ещё в разделе «{section}»"
        )).format(section=section_name)
        siblings_html = (
            f'<section class="seo-section"><h2>{escape(sib_h2)}</h2>'
            f"<ul>{items}</ul></section>"
        )

    title = _rt(
        "region_indicator.title",
        indicator=ind_name,
        region=region_name,
        value=_fmt(last_value),
        year=last_year,
    ) or (f"{ind_name} — {region_name}: {_fmt(last_value)} "
             f"{unit} ({last_year})").strip()
    if position and achievement:
        rank_bit = (_rt("region_indicator.rank_bit_achievement") or (
            ", {position}-е место среди {total} регионов России."
        )).format(position=position, total=len(rank_rows))
    elif position:
        rank_bit = (_rt("region_indicator.rank_bit_list") or (
            ", {position}-е положение в списке по величине среди "
            "{total} регионов России."
        )).format(position=position, total=len(rank_rows))
    else:
        rank_bit = _rt("region_indicator.rank_bit_none") or ". Данные Росстата."
    desc = _rt(
        "region_indicator.description",
        indicator=ind_name,
        region=region_name,
        value=_fmt(last_value),
        unit=unit,
        year=last_year,
    ) or (
        f"{ind_name} в регионе {region_name}: {_fmt(last_value)} {unit} "
        f"в {last_year} году. Динамика с {first_year} года, график по годам, "
        f"таблица значений{rank_bit}"
    )

    json_ld = [
        _breadcrumbs(crumbs.region_indicator_trail(
            region_name, paths.region(slug), ind_name,
            paths.region_indicator(slug, code),
        )),
        faq_json_ld,
        {
            "@context": "https://schema.org",
            "@type": "Dataset",
            "name": f"{ind_name} — {region_name}",
            "description": (
                f"{ind_name} ({unit}), {region_name}, {first_year}–{last_year}. "
                f"{'Source: Rosstat.' if _rt('region_indicator.faq_source_a') else 'Источник: Росстат.'}"
            ),
            "url": _absolute(paths.region_indicator(slug, code)),
            "temporalCoverage": f"{first_year}/{last_year}",
            "spatialCoverage": region_name,
            "creator": {
                "@type": "Organization",
                "name": "Rosstat" if _rt("region_indicator.faq_source_a") else "Росстат",
            },
            "license": "https://creativecommons.org/licenses/by/4.0/",
            "image": _absolute(og_path),
        },
        {
            "@context": "https://schema.org",
            "@type": "ImageObject",
            "contentUrl": _absolute(og_path),
            "url": _absolute(og_path),
            "width": 1200,
            "height": 630,
            "name": (
                f"{ind_name} — {region_name}: chart"
                if _rt("region_indicator.alt")
                else f"{ind_name} — {region_name}: график"
            ),
            "caption": alt,
            "representativeOfPage": True,
        },
    ]

    h1 = _rt("region_indicator.h1", indicator=ind_name, region=region_name) or (
        f"{ind_name} — {region_name}"
    )
    source_h2 = _rt("region_rating.source_h2") or "Источник данных"
    source_p = _rt(
        "region_rating.source_p",
        year=f"{first_year}–{last_year}",
        unit=unit or (
            "source units" if _rt("region_rating.source_p") else "единицы источника"
        ),
    ) or (
        f"Сборник Росстата «Регионы России. Социально-экономические показатели». "
        f"Значения приведены в единицах: {unit or 'единицы источника'}. "
        f"Период наблюдений: {first_year}–{last_year}."
    )
    body = f"""<div class="seo-page">
{_breadcrumbs_nav(crumbs.region_indicator_trail(
    region_name, paths.region(slug), ind_name,
    paths.region_indicator(slug, code),
))}
<p class="seo-eyebrow">{escape(section_name)} — {escape(region_name)}</p>
<h1>{escape(h1)}</h1>
{figure_html}
{paragraphs_html}
{checkpoints_html}
{table_html}
{faq_html}
{macro_html}
{district_html}
{siblings_html}
<section class="seo-section"><h2>{escape(source_h2)}</h2>
<p>{escape(source_p)}</p></section>
</div>"""

    html = await build_document(
        title=title,
        description=desc,
        canonical_path=paths.region_indicator(slug, code),
        body=body,
        json_ld=json_ld,
        keywords=_rt(
            "region_indicator.keywords",
            indicator=ind_name,
            region=region_name,
        ) or (
            f"{ind_name} {region_name}, {region_name} {ind_name} по годам, "
            f"{ind_name} {region_name} график, {region_name} статистика"
        ),
        og_image=_absolute(og_path),
    )
    return 200, html

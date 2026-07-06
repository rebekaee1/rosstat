"""SSR-рендер регионального блока: /regions, /region/{slug}, /region/{slug}/{code},
/region-rating/{code}.

Каждая страница регион-показателя получает уникальный автоконтент из данных:
текущее значение, динамика за год/5 лет/весь период, место в рейтинге регионов,
сравнение с общероссийским уровнем, полная таблица значений, видимый график
(/og/region/...) для Яндекс.Картинок и Алисы. Это ~39 тыс. страниц с
осмысленным контентом — по образцу макроблока (ADR-0003), но в своём модуле.

Рейтинги (/region-rating/{code}) — программатик-страницы под спрос
«топ регионов по X», «где самая высокая/низкая X»: полная ранжированная
таблица всех субъектов по последнему году + лидеры/аутсайдеры/РФ.
"""

from html import escape

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Region, RegionDataPoint, RegionIndicator
from app.services.seo_renderer import (
    DOMAIN,
    _breadcrumbs,
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
            f'<li><a href="/region/{escape(r.slug)}">{escape(r.name)}</a></li>'
            for r in by_district.get(d.slug, [])
        )
        sections.append(
            f"<section class=\"seo-section\"><h2>{escape(d.name)}</h2><ul>{links}</ul></section>"
        )

    # Точка входа робота в рейтинги: ключевые показатели с мостом в макро.
    rating_inds = (await db.execute(
        select(RegionIndicator.code, RegionIndicator.name)
        .where(RegionIndicator.table_code.in_(list(MACRO_BY_TABLE)),
               RegionIndicator.is_listed.is_(True))
        .order_by(RegionIndicator.section_num)
    )).all()
    ratings_html = ""
    if rating_inds:
        items = "".join(
            f'<li><a href="/region-rating/{escape(c)}">Рейтинг регионов: {escape(n)}</a></li>'
            for c, n in rating_inds
        )
        ratings_html = (
            f"<section class=\"seo-section\"><h2>Рейтинги регионов</h2>"
            f"<p>Все субъекты РФ, ранжированные по значению показателя за последний год.</p>"
            f"<ul>{items}</ul></section>"
        )

    body = f"""<div class="seo-page">
<nav><a href="/">Главная</a> → Регионы России</nav>
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

    json_ld = [_breadcrumbs([("/", "Главная"), ("/regions", "Регионы России")])]
    html = await build_document(
        title=_REGIONS_TITLE,
        description=_REGIONS_DESC,
        canonical_path="/regions",
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
            f'<li><a href="/region/{escape(slug)}/{escape(ind.code)}">{escape(ind.name)}</a>'
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
    body = f"""<div class="seo-page">
<nav><a href="/">Главная</a> → <a href="/regions">Регионы</a> → {escape(region.name)}</nav>
<p class="seo-eyebrow">Региональная статистика Росстата</p>
<h1>{escape(region.name)}: социально-экономические показатели</h1>
<p>Официальные данные Росстата по региону {escape(region.name)}: {catalog_line}
в {len(sections)} разделах — от численности населения и заработной платы до валового
регионального продукта, инвестиций и потребительских цен. Ряды с 1990 года,
по каждому показателю — график динамики и место региона среди субъектов РФ.</p>
{section_html}
</div>"""

    json_ld = [
        _breadcrumbs([("/", "Главная"), ("/regions", "Регионы"), (f"/region/{slug}", region.name)]),
    ]
    html = await build_document(
        title=title,
        description=desc,
        canonical_path=f"/region/{slug}",
        body=body,
        json_ld=json_ld,
        keywords=(
            f"{region.name} статистика, {region.name} экономика, {region.name} население, "
            f"{region.name} зарплата, {region.name} врп"
        ),
    )
    return 200, html


def _rank_phrase(position: int, total: int) -> str:
    if position <= 3:
        return f"входит в тройку регионов с наибольшим значением среди {total} субъектов РФ"
    if position <= 10:
        return f"входит в десятку регионов с наибольшим значением среди {total} субъектов РФ"
    if position > total - 5:
        return f"находится в конце списка — {position}-е место из {total}"
    return f"занимает {position}-е место из {total}"


async def render_region_rating_html(code: str, db: AsyncSession) -> tuple[int, str]:
    """Рейтинг всех регионов по показателю: /region-rating/{code}."""
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

    rows = (await db.execute(
        select(Region.slug, Region.name, RegionDataPoint.value)
        .join(Region, Region.id == RegionDataPoint.region_id)
        .where(RegionDataPoint.indicator_id == indicator.id,
               RegionDataPoint.year == last_year,
               Region.kind == "region")
        .order_by(RegionDataPoint.value.desc())
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
    intro = (
        f"Рейтинг {total} субъектов Российской Федерации по показателю "
        f"«{indicator.name}» за {last_year} год. Первые места занимают: {top_names}. "
        f"Замыкает список {bottom[-1][1]} — {_vu(bottom[-1][2])}."
    )
    if rf_value is not None:
        intro += f" Значение по России в целом — {_vu(rf_value)}."

    table_rows = "".join(
        f"<tr><td>{i}</td>"
        f'<td><a href="/region/{escape(s)}/{escape(code)}">{escape(n)}</a></td>'
        f"<td>{_fmt(float(v))}</td></tr>"
        for i, (s, n, v) in enumerate(rows, 1)
    )
    table_html = (
        f'<div class="seo-scroll"><table><thead><tr><th>Место</th><th>Регион</th>'
        f"<th>{escape(unit or 'Значение')}</th></tr></thead>"
        f"<tbody>{table_rows}</tbody></table></div>"
    )

    faq = [
        (f"У какого региона наибольшее значение показателя «{indicator.name}»?",
         f"По итогам {last_year} года первое место занимает {top[0][1]} — {_vu(top[0][2])}."),
        ("У какого региона наименьшее значение?",
         f"Наименьшее значение у региона {bottom[-1][1]} — {_vu(bottom[-1][2])}."),
        ("За какой год приведён рейтинг и откуда данные?",
         f"Рейтинг построен по данным за {last_year} год из сборника Росстата "
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
        items = "".join(
            f'<li><a href="/region-rating/{escape(c)}">{escape(n)}</a></li>'
            for c, n in siblings
        )
        siblings_html = (
            f"<section class=\"seo-section\"><h2>Другие рейтинги раздела "
            f"«{escape(indicator.section_name)}»</h2><ul class=\"seo-pills\">{items}</ul></section>"
        )

    macro_code = MACRO_BY_TABLE.get(indicator.table_code or "")
    macro_html = ""
    if macro_code:
        macro_html = (
            f"<section class=\"seo-section\"><h2>Общероссийская динамика</h2>"
            f"<p>Показатель по России в целом, с более частым обновлением и прогнозом — "
            f"на карточке <a href=\"/indicator/{escape(macro_code)}\">общероссийского "
            f"индикатора</a>.</p></section>"
        )

    title = f"Рейтинг регионов России: {indicator.name} ({last_year})"
    desc = (
        f"{indicator.name} по регионам России за {last_year} год: рейтинг всех {total} "
        f"субъектов РФ. Наибольшее значение — {top[0][1]} ({_vu(top[0][2])}). "
        f"Полная таблица, данные Росстата."
    )

    json_ld = [
        _breadcrumbs([
            ("/", "Главная"), ("/regions", "Регионы"),
            (f"/region-rating/{code}", f"Рейтинг: {indicator.name}"),
        ]),
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
                    "url": f"{DOMAIN}/region/{s}/{code}",
                }
                for i, (s, n, _v) in enumerate(rows[:10], 1)
            ],
        },
    ]

    rf_tile = ""
    if rf_value is not None:
        rf_tile = f'<div class="seo-tile"><span>Россия в целом</span><b>{escape(_vu(rf_value))}</b></div>'
    tiles_html = f"""<div class="seo-tiles">
<div class="seo-tile"><span>Наибольшее значение — {escape(top[0][1])}</span><b>{escape(_vu(top[0][2]))}</b></div>
{rf_tile}
<div class="seo-tile"><span>Наименьшее значение — {escape(bottom[-1][1])}</span><b>{escape(_vu(bottom[-1][2]))}</b></div>
<div class="seo-tile"><span>Данные за</span><b>{last_year} год</b></div>
</div>"""

    og_path = f"/og/region-rating/{code}.png"
    rating_alt = (f"{indicator.name} по регионам России — рейтинг {last_year} года, "
                  f"наибольшее значение — {top[0][1]} ({_vu(top[0][2])})")
    figure_html = (
        f'<figure class="seo-chart"><img src="{escape(og_path)}" alt="{escape(rating_alt)}" '
        f'width="1200" height="630" loading="eager">'
        f"<figcaption>{escape(indicator.name)}: регионы с наибольшими значениями, {last_year} год. "
        f"Источник: Росстат. forecasteconomy.com</figcaption></figure>"
    )

    body = f"""<div class="seo-page">
<nav><a href="/">Главная</a> → <a href="/regions">Регионы</a> → Рейтинг: {escape(indicator.name)}</nav>
<p class="seo-eyebrow">{escape(indicator.section_name)} — рейтинг регионов</p>
<h1>{escape(indicator.name)}: рейтинг регионов России, {last_year} год</h1>
<p>{escape(intro)}</p>
{figure_html}
{tiles_html}
<section class="seo-section"><h2>Полный рейтинг ({total} регионов)</h2>{table_html}</section>
{faq_html}
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
        "name": f"{indicator.name} — рейтинг регионов России, {last_year}",
        "description": rating_alt,
        "representativeOfPage": True,
        "width": 1200,
        "height": 630,
    })
    html = await build_document(
        title=title,
        description=desc,
        canonical_path=f"/region-rating/{code}",
        body=body,
        json_ld=json_ld,
        keywords=(
            f"{indicator.name} по регионам, рейтинг регионов {indicator.name}, "
            f"{indicator.name} по субъектам рф, топ регионов {indicator.name}"
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
    rank_rows = (await db.execute(
        select(Region.slug, RegionDataPoint.value)
        .join(Region, Region.id == RegionDataPoint.region_id)
        .where(RegionDataPoint.indicator_id == indicator.id,
               RegionDataPoint.year == last_year,
               Region.kind == "region")
        .order_by(RegionDataPoint.value.desc())
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
            f" (<a href=\"/region-rating/{escape(code)}\">полный рейтинг регионов</a>)"
            if len(rank_rows) >= 10 else ""
        )
        p3 = (f"По значению этого показателя {escape(region.name)} "
              f"{_rank_phrase(position, len(rank_rows))} в {last_year} году{rating_ref}.")
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
        faq.append((
            f"Какое место занимает {region.name} по этому показателю среди регионов России?",
            f"{position}-е место из {len(rank_rows)} субъектов РФ по итогам {last_year} года.",
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
            f"на странице <a href=\"/indicator/{escape(macro_code)}\">общероссийского "
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
                f'<li><a href="/region/{escape(s)}/{escape(code)}">'
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
    og_path = f"/og/region/{slug}/{code}.png"
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
            f'<li><a href="/region/{escape(slug)}/{escape(c)}">{escape(n)}</a></li>'
            for c, n in siblings
        )
        siblings_html = (
            f"<section class=\"seo-section\"><h2>Ещё в разделе "
            f"«{escape(indicator.section_name)}»</h2><ul>{items}</ul></section>"
        )

    title = (f"{indicator.name} — {region.name}: {_fmt(last_value)} "
             f"{unit} ({last_year})").strip()
    desc = (
        f"{indicator.name} в регионе {region.name}: {_fmt(last_value)} {unit} "
        f"в {last_year} году. Динамика с {first_year} года, график по годам, "
        f"таблица значений"
        + (f", {position}-е место среди {len(rank_rows)} регионов России."
           if position else ". Данные Росстата.")
    )

    json_ld = [
        _breadcrumbs([
            ("/", "Главная"), ("/regions", "Регионы"),
            (f"/region/{slug}", region.name),
            (f"/region/{slug}/{code}", indicator.name),
        ]),
        faq_json_ld,
        {
            "@context": "https://schema.org",
            "@type": "Dataset",
            "name": f"{indicator.name} — {region.name}",
            "description": (f"{indicator.name} ({unit}), {region.name}, "
                            f"{first_year}–{last_year}. Источник: Росстат."),
            "url": f"{DOMAIN}/region/{slug}/{code}",
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
<nav><a href="/">Главная</a> → <a href="/regions">Регионы</a> → <a href="/region/{escape(slug)}">{escape(region.name)}</a> → {escape(indicator.name)}</nav>
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
        canonical_path=f"/region/{slug}/{code}",
        body=body,
        json_ld=json_ld,
        keywords=(
            f"{indicator.name} {region.name}, {region.name} {indicator.name} по годам, "
            f"{indicator.name} {region.name} график, {region.name} статистика"
        ),
        og_image=f"{DOMAIN}{og_path}",
    )
    return 200, html

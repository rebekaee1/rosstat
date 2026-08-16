"""Dynamic sitemap.xml, RSS feed and OG endpoints generated from the database."""
import logging
from datetime import date, datetime, timezone
from email.utils import format_datetime
from html import escape

from fastapi import APIRouter, Depends, Response
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Indicator, IndicatorData
from app.services.display import (
    annual_summary,
    display_value,
    display_value_text,
    format_date_ru,
    format_number_ru,
)
# CATEGORIES/PAGE_META/STATIC_PAGES реэкспортируются для тестов
# (test_sitemap_static_pages_constant) — сама генерация живёт в site_urls.py.
from app.services.seo_content import (  # noqa: F401
    CATEGORIES,
    CATEGORY_META,
    DOMAIN,
    PAGE_META,
    STATIC_PAGES,
)
from app.services.seo_renderer import render_category_html, render_home_html, render_indicator_html, render_page_html

logger = logging.getLogger(__name__)
router = APIRouter(tags=["seo"])


def _sitemap_priority(*, listed: bool, is_indicator: bool) -> str:
    """Приоритет crawl budget: главная и категории выше, derived-sibling ниже."""
    if not is_indicator:
        return "0.8"
    return "0.8" if listed else "0.5"


def _sitemap_lastmod(last_data: date | None, fallback: date) -> str:
    return (last_data or fallback).isoformat()


_SITEMAP_TTL = 6 * 3600


def _render_urlset(urls) -> str:
    entries = "\n".join(
        f"  <url>\n"
        f"    <loc>{DOMAIN}{u.path}</loc>\n"
        f"    <lastmod>{u.lastmod}</lastmod>\n"
        f"    <changefreq>{u.changefreq}</changefreq>\n"
        f"    <priority>{u.priority}</priority>\n"
        f"  </url>"
        for u in urls
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + entries
        + "\n</urlset>"
    )


@router.api_route("/sitemap.xml", methods=["GET", "HEAD"], include_in_schema=False)
async def sitemap_index(db: AsyncSession = Depends(get_db)):
    """Sitemap-индекс: секции по типам страниц, регионы — чанками по ~10k.

    Секционирование даёт per-file статистику обхода в Вебмастере и честный
    lastmod на каждую часть (регионы обновляются раз в год, «сегодня» — ежедневно).
    """
    from app.core.cache import cache_get, cache_set
    from app.services.site_urls import collect_url_sections

    cached = await cache_get("fe:sitemap:index")
    if cached:
        return Response(content=cached, media_type="application/xml")

    sections = await collect_url_sections(db)
    today = date.today().isoformat()
    entries = "\n".join(
        f"  <sitemap>\n"
        f"    <loc>{DOMAIN}/sitemap-{name}.xml</loc>\n"
        f"    <lastmod>{max((u.lastmod for u in urls), default=today)}</lastmod>\n"
        f"  </sitemap>"
        for name, urls in sections.items()
        if urls
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + entries
        + "\n</sitemapindex>"
    )
    await cache_set("fe:sitemap:index", xml, _SITEMAP_TTL)
    return Response(content=xml, media_type="application/xml")


@router.api_route("/sitemap-{section}.xml", methods=["GET", "HEAD"], include_in_schema=False)
async def sitemap_section(section: str, db: AsyncSession = Depends(get_db)):
    from app.core.cache import cache_get, cache_set
    from app.services.site_urls import collect_url_sections

    cache_key = f"fe:sitemap:section:{section}"
    cached = await cache_get(cache_key)
    if cached:
        return Response(content=cached, media_type="application/xml")

    # Мусорное имя секции не должно каждый раз запускать полную сборку 43k URL
    # (боты/сканеры любят перебирать пути) — держим список известных секций.
    known = await cache_get("fe:sitemap:known-sections")
    if isinstance(known, list) and section not in known:
        return Response(status_code=404)

    # П-13: miss любой секции стоит полного collect_url_sections (~43k URL) —
    # раз уже собрали, прогреваем ВСЕ секции одним проходом, чтобы обход
    # робота по 12 файлам не запускал сборку 12 раз.
    sections = await collect_url_sections(db)
    requested_xml: str | None = None
    names: list[str] = []
    for name, urls in sections.items():
        if not urls:
            continue
        names.append(name)
        xml = _render_urlset(urls)
        await cache_set(f"fe:sitemap:section:{name}", xml, _SITEMAP_TTL)
        if name == section:
            requested_xml = xml
    await cache_set("fe:sitemap:known-sections", names, _SITEMAP_TTL)
    if requested_xml is None:
        return Response(status_code=404)
    return Response(content=requested_xml, media_type="application/xml")


@router.api_route("/feed.xml", methods=["GET", "HEAD"], include_in_schema=False)
async def rss_feed(db: AsyncSession = Depends(get_db)):
    """RSS 2.0 — последние обновления данных по listed-индикаторам.

    Item на индикатор: имя + актуальное значение, pubDate = дата последней
    точки. Поисковики и агрегаторы узнают об обновлениях без переобхода.
    """
    last_point = (
        select(
            IndicatorData.indicator_id,
            func.max(IndicatorData.date).label("last_date"),
        )
        .group_by(IndicatorData.indicator_id)
        .subquery()
    )
    stmt = (
        select(Indicator, IndicatorData.value, IndicatorData.date)
        .join(last_point, last_point.c.indicator_id == Indicator.id)
        .join(
            IndicatorData,
            (IndicatorData.indicator_id == Indicator.id)
            & (IndicatorData.date == last_point.c.last_date),
        )
        .where(Indicator.is_active.is_(True), Indicator.is_listed.is_(True))
        .order_by(desc(IndicatorData.date), Indicator.code)
        .limit(60)
    )
    rows = (await db.execute(stmt)).all()

    items = []
    for ind, value, dt in rows:
        pub = format_datetime(datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc))
        # Display-adapter: CPI-индекс → изменение цен («+0,17 % за месяц»),
        # русские числа и даты — сырой «100.2 %» в RSS был классом инцидента.
        shown = display_value_text(ind.code, value, ind.unit, ind.frequency)
        title = escape(f"{ind.name}: {shown}")
        desc_text = escape(
            f"{ind.name} — значение {shown} на {format_date_ru(dt)}. "
            f"Источник: {ind.source}."
        )
        link = f"{DOMAIN}/indicator/{ind.code}"
        items.append(
            f"  <item>\n"
            f"    <title>{title}</title>\n"
            f"    <link>{link}</link>\n"
            f"    <guid isPermaLink=\"false\">{ind.code}-{dt.isoformat()}</guid>\n"
            f"    <pubDate>{pub}</pubDate>\n"
            f"    <description>{desc_text}</description>\n"
            f"  </item>"
        )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        "<channel>\n"
        "  <title>Forecast Economy — обновления экономических данных России</title>\n"
        f"  <link>{DOMAIN}</link>\n"
        "  <description>Последние обновления макроэкономических индикаторов России: "
        "Росстат, Банк России, Минфин.</description>\n"
        "  <language>ru</language>\n"
        f'  <atom:link href="{DOMAIN}/feed.xml" rel="self" type="application/rss+xml"/>\n'
        + "\n".join(items)
        + "\n</channel>\n</rss>"
    )
    return Response(
        content=xml,
        media_type="application/rss+xml; charset=utf-8",
        headers={"Cache-Control": "public, max-age=1800"},
    )


@router.get("/api/v1/og-image/indicator/{code}.png", include_in_schema=False)
async def og_image_indicator(code: str, db: AsyncSession = Depends(get_db)):
    """PNG-превью индикатора для og:image (спарклайн + актуальное значение)."""
    from app.services.og_image import cached_og, render_indicator_og, store_og

    png = cached_og(code)
    if png is None:
        q = await db.execute(
            select(Indicator).where(Indicator.code == code, Indicator.is_active.is_(True))
        )
        indicator = q.scalar_one_or_none()
        if not indicator:
            return Response(status_code=404)
        rows_q = await db.execute(
            select(IndicatorData.value, IndicatorData.date)
            .where(IndicatorData.indicator_id == indicator.id)
            .order_by(IndicatorData.date)  # старое → новое, вся история
        )
        rows = rows_q.all()
        # Превью «representativeOfPage»: вся история, прореженная до ~180 точек
        # (для дневных индексов last-120 показывало бы лишь ~4 месяца и дублировало
        # бы год на обеих X-метках). Форма ряда сохраняется, последняя точка — всегда.
        ordered = rows
        _MAXP = 180
        if len(ordered) > _MAXP:
            step = len(ordered) / _MAXP
            idx = sorted({int(i * step) for i in range(_MAXP)} | {len(ordered) - 1})
            ordered = [ordered[i] for i in idx]
        # CPI-индекс на картинке показывается изменением цен, не сырыми
        # «100.17 %» (инцидент «инфляция 100,2%» — картинка уходит в Алису
        # и Яндекс.Картинки); даты — по-русски.
        values = [
            v if (v := display_value(code, raw)) is not None else 0.0
            for raw, _ in ordered
        ]
        current_value, current_date = (rows[-1] if rows else (None, None))
        unit = (indicator.unit or "").strip()
        value_text = display_value_text(code, current_value, unit, indicator.frequency)
        date_text = f"на {format_date_ru(current_date)}" if current_date else ""
        x_labels = None
        if len(ordered) >= 2:
            first_d, last_d = ordered[0][1], ordered[-1][1]
            x_labels = (
                (str(first_d.year), str(last_d.year))
                if first_d.year != last_d.year
                else (first_d.strftime("%m.%Y"), last_d.strftime("%m.%Y"))
            )
        png = render_indicator_og(
            code=code,
            name=indicator.name,
            value_text=value_text,
            date_text=date_text,
            values=values,
            x_labels=x_labels,
        )
        store_og(code, png)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/api/v1/og-image/indicator/{code}/{year}.png", include_in_schema=False)
async def og_image_indicator_year(code: str, year: int, db: AsyncSession = Depends(get_db)):
    """PNG-превью индикатора за конкретный год для годовой landing-страницы.

    При ≥2 точках за год — спарклайн внутри года. При одной точке (годовые ряды)
    рисуем окно соседних лет: одна точка на графике бессмысленна, а контекст
    истории остаётся содержательным для Алисы/Нейро.
    """
    from app.services.og_image import cached_og, render_indicator_og, store_og
    from app.services.seo_renderer import (
        neighbor_year_window,
        yearly_last_points,
    )
    from app.services.site_urls import YEAR_LANDING_MIN_POINTS

    cache_key = f"{code}:{year}"
    png = cached_og(cache_key)
    if png is None:
        q = await db.execute(
            select(Indicator).where(Indicator.code == code, Indicator.is_active.is_(True))
        )
        indicator = q.scalar_one_or_none()
        if not indicator:
            return Response(status_code=404)
        rows_q = await db.execute(
            select(IndicatorData.value, IndicatorData.date)
            .where(
                IndicatorData.indicator_id == indicator.id,
                func.extract("year", IndicatorData.date) == year,
            )
            .order_by(IndicatorData.date)
        )
        rows = rows_q.all()
        if len(rows) < YEAR_LANDING_MIN_POINTS:
            return Response(status_code=404)
        raw_values = [float(v) for v, _ in rows]
        first_date = rows[0][1]
        last_value, last_date = rows[-1]
        unit = (indicator.unit or "").strip()
        # Display-adapter: спарклайн и подписи в пользовательской семантике
        # (CPI — изменение цен), годовой итог — по природе ряда (сумма для
        # потоков, конец года для запасов, цепной рост для CPI), а не
        # «среднее за год» для всего подряд.
        summary_label, summary_text = annual_summary(code, raw_values, unit)
        value_text = display_value_text(code, last_value, unit, indicator.frequency)
        date_text = f"{summary_label.lower()} — {summary_text}"

        if len(rows) >= 2:
            values = [
                v if (v := display_value(code, raw)) is not None else 0.0
                for raw in raw_values
            ]
            x_labels = (first_date.strftime("%d.%m"), last_date.strftime("%d.%m"))
        else:
            # Одна точка за год: график соседних лет (иначе area-chart пустой).
            series = await yearly_last_points(db, indicator.id)
            window = neighbor_year_window(series, year, size=10)
            if len(window) < 2:
                # Крайний случай — совсем короткая история: дублируем точку,
                # чтобы превью не 404ило (страница при этом уже 200).
                shown = display_value(code, float(last_value))
                values = [shown if shown is not None else 0.0] * 2
                x_labels = (str(year), str(year))
            else:
                values = [
                    v if (v := display_value(code, raw)) is not None else 0.0
                    for _y, raw, _d in window
                ]
                x_labels = (str(window[0][0]), str(window[-1][0]))
            # Подпись даты — изменение к прошлому году, если есть.
            prev = next((raw for y, raw, _d in series if y == year - 1), None)
            if prev is not None:
                cur_s = display_value(code, float(last_value))
                prev_s = display_value(code, float(prev))
                if cur_s is not None and prev_s is not None and prev_s != 0:
                    pct = ((cur_s - prev_s) / abs(prev_s)) * 100.0
                    date_text = (
                        f"к {year - 1} году — "
                        f"{format_number_ru(pct, signed=True)} %"
                    )

        png = render_indicator_og(
            code=code,
            name=indicator.name,
            value_text=value_text,
            date_text=date_text,
            values=values,
            period_text=f"{year} год",
            x_labels=x_labels,
        )
        store_og(cache_key, png)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/api/v1/og-image/region/{slug}/{code}.png", include_in_schema=False)
async def og_image_region_indicator(slug: str, code: str, db: AsyncSession = Depends(get_db)):
    """PNG-график регионального показателя: og:image + видимый <img> SSR-страницы."""
    from app.models import Region, RegionDataPoint, RegionIndicator
    from app.services.og_image import cached_og, render_indicator_og, store_og
    from app.services.seo_regional import _fmt as _fmt_ru

    cache_key = f"region:{slug}:{code}"
    png = cached_og(cache_key)
    if png is None:
        region = (await db.execute(
            select(Region).where(Region.slug == slug)
        )).scalar_one_or_none()
        indicator = (await db.execute(
            select(RegionIndicator).where(RegionIndicator.code == code)
        )).scalar_one_or_none()
        if not region or not indicator:
            return Response(status_code=404)
        rows = (await db.execute(
            select(RegionDataPoint.year, RegionDataPoint.value)
            .where(RegionDataPoint.indicator_id == indicator.id,
                   RegionDataPoint.region_id == region.id)
            .order_by(RegionDataPoint.year)
        )).all()
        if len(rows) < 2:
            return Response(status_code=404)
        values = [float(v) for _y, v in rows]
        unit = (indicator.unit or "").strip()
        value_text = f"{_fmt_ru(values[-1])} {unit}".strip()
        png = render_indicator_og(
            code=cache_key,
            name=f"{indicator.name} — {region.name}",
            value_text=value_text,
            date_text=f"{rows[-1][0]} год",
            values=values,
            x_labels=(str(rows[0][0]), str(rows[-1][0])),
        )
        store_og(cache_key, png)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/api/v1/og-image/region-rating/{code}.png", include_in_schema=False)
async def og_image_region_rating(code: str, db: AsyncSession = Depends(get_db)):
    """PNG-барчарт рейтинга регионов: og:image + видимый <img> на /region-rating."""
    from app.data.region_indicator_polarity import (
        region_rating_is_achievement,
        region_rating_order_by,
    )
    from app.models import Region, RegionDataPoint, RegionIndicator
    from app.services.og_image import cached_og, render_rating_og, store_og

    cache_key = f"rating:v2:{code}"
    png = cached_og(cache_key)
    if png is None:
        indicator = (await db.execute(
            select(RegionIndicator).where(RegionIndicator.code == code)
        )).scalar_one_or_none()
        if not indicator:
            return Response(status_code=404)
        last_year = (await db.execute(
            select(func.max(RegionDataPoint.year))
            .join(Region, Region.id == RegionDataPoint.region_id)
            .where(RegionDataPoint.indicator_id == indicator.id, Region.kind == "region")
        )).scalar_one_or_none()
        if last_year is None:
            return Response(status_code=404)
        rows = (await db.execute(
            select(Region.name, RegionDataPoint.value)
            .join(Region, Region.id == RegionDataPoint.region_id)
            .where(RegionDataPoint.indicator_id == indicator.id,
                   RegionDataPoint.year == last_year,
                   Region.kind == "region")
            .order_by(region_rating_order_by(
                RegionDataPoint.value, indicator.code, indicator.table_code
            ))
        )).all()
        if len(rows) < 5:
            return Response(status_code=404)
        achievement = region_rating_is_achievement(indicator.code, indicator.table_code)
        png = render_rating_og(
            name=indicator.name,
            year=int(last_year),
            unit=(indicator.unit or "").strip(),
            rows=[(n, float(v)) for n, v in rows],
            total=len(rows),
            order_label=(
                "лучшие значения" if achievement else "наибольшие значения"
            ),
        )
        store_og(cache_key, png)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/api/v1/og-image/today.png", include_in_schema=False)
async def og_image_today_hub(db: AsyncSession = Depends(get_db)):
    """PNG-сводка «Экономика России сегодня» для хаба /today."""
    from app.services.og_image import cached_og, render_today_hub_og, store_og
    from app.services.seo_today import (
        TODAY_CODES, TODAY_SPECS, _format_number, _indicator_with_rows, _ru_date,
    )
    from datetime import date as _date

    cache_key = "today-hub"
    png = cached_og(cache_key)
    if png is None:
        items: list[tuple[str, str]] = []
        for code in TODAY_CODES:
            spec = TODAY_SPECS[code]
            indicator, rows = await _indicator_with_rows(db, spec.series_code, limit=1)
            if indicator is None or not rows:
                continue
            unit = (indicator.unit or "").strip()
            items.append((spec.query, f"{_format_number(rows[0].value)} {unit}".strip()))
        if not items:
            return Response(status_code=404)
        png = render_today_hub_og(date_text=_ru_date(_date.today()), items=items)
        store_og(cache_key, png)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/api/v1/og-image/region-vs/{slug_a}-vs-{slug_b}.png", include_in_schema=False)
async def og_image_region_vs(slug_a: str, slug_b: str, db: AsyncSession = Depends(get_db)):
    """PNG-таблица сравнения двух регионов для /region-vs."""
    from app.services.og_image import cached_og, render_region_vs_og, store_og
    from app.services.region_compare_data import build_region_compare_payload
    from app.services.seo_regional import _fmt as _fmt_ru

    cache_key = f"vs:{slug_a}:{slug_b}"
    png = cached_og(cache_key)
    if png is None:
        payload = await build_region_compare_payload(slug_a, slug_b, db)
        if payload is None:
            return Response(status_code=404)

        _UNIT_SHORT = {
            "тысяч человек": "тыс. чел.",
            "в процентах": "%",
            "рублей": "руб.",
            "миллионов рублей": "млн руб.",
        }

        def _vu(v, unit):
            v = float(v)
            u = (unit or "").strip()
            # ВРП/инвестиции в «миллионах рублей» — конвертируем в трлн/млрд,
            # иначе «32 339 002 миллионов рублей» не влезает в колонку картинки.
            if u == "миллионов рублей":
                if abs(v) >= 1_000_000:
                    return f"{_fmt_ru(round(v / 1_000_000, 1))} трлн руб."
                if abs(v) >= 1_000:
                    return f"{_fmt_ru(round(v / 1_000, 1))} млрд руб."
            return f"{_fmt_ru(v)} {_UNIT_SHORT.get(u, u)}".strip()

        rows = [
            (r["name"], _vu(r["a"]["value"], r["unit"]), _vu(r["b"]["value"], r["unit"]))
            for r in payload["rows"]
        ]
        if not rows:
            return Response(status_code=404)
        png = render_region_vs_og(
            name_a=payload["region_a"]["name"],
            name_b=payload["region_b"]["name"],
            rows=rows,
        )
        store_og(cache_key, png)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/api/v1/og-image/world/{slug}.png", include_in_schema=False)
async def og_image_world_country(slug: str, db: AsyncSession = Depends(get_db)):
    """PNG-сводка страны для /world/{slug}: og:image + видимый <img> SSR."""
    from app.data.eurostat_units_ru import unit_suffix
    from app.models import WorldCountry, WorldDataPoint, WorldIndicator
    from app.services.display import format_number_ru
    from app.services.og_image import cached_og, render_world_country_og, store_og

    cache_key = f"world:{slug}"
    png = cached_og(cache_key)
    if png is None:
        country = (
            await db.execute(
                select(WorldCountry).where(
                    WorldCountry.slug == slug,
                    WorldCountry.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if country is None:
            return Response(status_code=404)

        inds = (
            await db.execute(
                select(WorldIndicator)
                .where(
                    WorldIndicator.country_id == country.id,
                    WorldIndicator.is_listed.is_(True),
                )
                .order_by(WorldIndicator.points_count.desc(), WorldIndicator.name_ru)
                .limit(12)
            )
        ).scalars().all()
        if not inds:
            return Response(status_code=404)

        ids = [i.id for i in inds]
        rn = func.row_number().over(
            partition_by=WorldDataPoint.indicator_id,
            order_by=WorldDataPoint.date.desc(),
        ).label("rn")
        sub = (
            select(
                WorldDataPoint.indicator_id,
                WorldDataPoint.value,
                rn,
            )
            .where(WorldDataPoint.indicator_id.in_(ids))
            .subquery()
        )
        latest = {
            iid: float(value)
            for iid, value in (
                await db.execute(
                    select(sub.c.indicator_id, sub.c.value).where(sub.c.rn == 1)
                )
            ).all()
        }
        items: list[tuple[str, str]] = []
        for ind in inds:
            if ind.id not in latest:
                continue
            unit = unit_suffix((ind.unit_ru or ind.unit or "").strip())
            label = ind.name_ru if len(ind.name_ru) <= 42 else ind.name_ru[:41] + "…"
            value_text = f"{format_number_ru(latest[ind.id])} {unit}".strip()
            items.append((label, value_text))
            if len(items) >= 6:
                break
        if not items:
            return Response(status_code=404)

        n_listed = (
            await db.execute(
                select(func.count()).select_from(WorldIndicator).where(
                    WorldIndicator.country_id == country.id,
                    WorldIndicator.is_listed.is_(True),
                )
            )
        ).scalar() or len(inds)

        from app.services.seo_world import _genitive

        png = render_world_country_og(
            country_name=_genitive(country),
            indicators_count=int(n_listed),
            items=items,
        )
        store_og(cache_key, png)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/api/v1/og-image/world-rating/{concept_slug}.png", include_in_schema=False)
async def og_image_world_rating(concept_slug: str, db: AsyncSession = Depends(get_db)):
    """PNG-барчарт рейтинга стран: og:image + видимый <img> на /world/rating."""
    from app.data.eurostat_units_ru import unit_suffix
    from app.services.og_image import cached_og, render_world_rating_og, store_og
    from app.services.seo_world import build_world_rating_payload

    cache_key = f"world-rating:{concept_slug}"
    png = cached_og(cache_key)
    if png is None:
        payload = await build_world_rating_payload(concept_slug, db)
        if not payload or not payload["items"]:
            return Response(status_code=404)
        concept = payload["concept"]
        order_label = (
            "по возрастанию"
            if concept["default_sort"] == "asc"
            else "по убыванию"
        )
        unit = unit_suffix(concept["unit"]) or concept["unit"]
        png = render_world_rating_og(
            name=concept["name"],
            year=int(payload["active_year"]),
            unit=unit,
            rows=[
                (item["country_name"], float(item["value"]))
                for item in payload["items"]
            ],
            total=int(payload["coverage"]["with_data"]),
            order_label=order_label,
        )
        store_og(cache_key, png)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/api/v1/og-image/world/{slug}/{code}.png", include_in_schema=False)
async def og_image_world_indicator(
    slug: str, code: str, db: AsyncSession = Depends(get_db)
):
    """PNG-график мирового показателя: og:image + видимый <img> SSR-страницы."""
    from app.data.eurostat_units_ru import unit_suffix
    from app.models import WorldCountry, WorldDataPoint, WorldIndicator
    from app.services.display import format_number_ru, format_month_ru
    from app.services.og_image import cached_og, render_indicator_og, store_og

    cache_key = f"world:{slug}:{code}"
    png = cached_og(cache_key)
    if png is None:
        country = (
            await db.execute(
                select(WorldCountry).where(
                    WorldCountry.slug == slug,
                    WorldCountry.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        indicator = (
            await db.execute(
                select(WorldIndicator).where(
                    WorldIndicator.code == code,
                    WorldIndicator.is_listed.is_(True),
                )
            )
        ).scalar_one_or_none()
        if (
            country is None
            or indicator is None
            or indicator.country_id != country.id
        ):
            return Response(status_code=404)
        rows = (
            await db.execute(
                select(WorldDataPoint.date, WorldDataPoint.value)
                .where(WorldDataPoint.indicator_id == indicator.id)
                .order_by(WorldDataPoint.date)
            )
        ).all()
        if len(rows) < 2:
            return Response(status_code=404)
        values = [float(v) for _d, v in rows]
        unit = unit_suffix((indicator.unit_ru or indicator.unit or "").strip())
        value_text = f"{format_number_ru(values[-1])} {unit}".strip()
        last_date = rows[-1][0]
        first_date = rows[0][0]
        date_text = format_month_ru(last_date) or last_date.isoformat()
        from app.data.eurostat_titles_ru import country_prepositional
        from app.data.legacy_redirects import strip_world_frequency_suffix

        subject = strip_world_frequency_suffix(indicator.name_ru) or indicator.name_ru
        prep = country_prepositional(country.slug, country.name_ru)
        png = render_indicator_og(
            code=cache_key,
            name=f"{subject} в {prep}",
            value_text=value_text,
            date_text=date_text,
            values=values,
            x_labels=(str(first_date.year), str(last_date.year)),
        )
        store_og(cache_key, png)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


def _html_response(status_code: int, html: str) -> Response:
    return Response(content=html, status_code=status_code, media_type="text/html; charset=utf-8")


@router.get("/api/v1/og/indicator/{code}", include_in_schema=False)
async def og_indicator(code: str, db: AsyncSession = Depends(get_db)):
    """Backward-compatible social-preview endpoint using the universal renderer."""
    status, html = await render_indicator_html(code, db)
    return _html_response(status, html)


@router.get("/api/v1/og/category/{slug}", include_in_schema=False)
async def og_category(slug: str, db: AsyncSession = Depends(get_db)):
    """Backward-compatible social-preview endpoint using the universal renderer."""
    status, html = await render_category_html(slug, db)
    return _html_response(status, html)


@router.get("/api/v1/og/page/{page}", include_in_schema=False)
async def og_page(page: str, db: AsyncSession = Depends(get_db)):
    """Backward-compatible social-preview endpoint using the universal renderer."""
    if page == "home":
        return _html_response(200, await render_home_html(db))
    status, html = await render_page_html(page)
    return _html_response(status, html)

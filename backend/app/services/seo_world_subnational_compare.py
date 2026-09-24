"""Canonical fast pages comparing US states and DC on common observation dates."""

from __future__ import annotations

from html import escape

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import SubnationalDataPoint, SubnationalIndicator, SubnationalRegion
from app.services import site_paths as paths
from app.services.display import format_number_ru
from app.services.locale import get_locale
from app.services.seo_renderer import (
    _absolute, _breadcrumbs, _breadcrumbs_nav, _seo_chart_figure,
    build_document, fast_answer_block,
)
from app.services.seo_world_subnational import (
    _country, _cname, _iname, _iunit, _kind_plural, _rname,
)
from app.services.world_subnational_ingest import load_subnational_passport, period_label


def og_subnational_compare(country: str, a: str, b: str) -> str:
    left, right = sorted((a, b))
    return f"/og/world/{country}/region-vs/{left}-vs-{right}.png"


async def subnational_compare_payload(
    country_slug: str, slug_a: str, slug_b: str, db: AsyncSession,
) -> dict | None:
    if slug_a == slug_b:
        return None
    country = await _country(db, country_slug)
    if country is None:
        return None
    region_rows = (await db.execute(select(SubnationalRegion).where(
        SubnationalRegion.country_code == country.code,
        SubnationalRegion.slug.in_((slug_a, slug_b)),
        SubnationalRegion.kind.in_(("state", "district")),
    ))).scalars().all()
    by_slug = {row.slug: row for row in region_rows}
    if slug_a not in by_slug or slug_b not in by_slug:
        return None
    left, right = sorted((slug_a, slug_b))
    a, b = by_slug[left], by_slug[right]
    featured = load_subnational_passport(country.code.lower()).featured_indicators
    indicators = (await db.execute(select(SubnationalIndicator).where(
        SubnationalIndicator.country_code == country.code,
        SubnationalIndicator.code.in_(tuple(featured)),
        SubnationalIndicator.is_listed.is_(True),
    ))).scalars().all()
    by_code = {ind.code: ind for ind in indicators}
    pa = aliased(SubnationalDataPoint)
    pb = aliased(SubnationalDataPoint)
    rows = []
    for code in featured:
        ind = by_code.get(code)
        if ind is None:
            continue
        common = (await db.execute(select(pa.period, pa.value, pb.value).select_from(pa).join(
            pb, and_(pb.indicator_id == pa.indicator_id,
                     pb.period == pa.period, pb.region_id == b.id),
        ).where(pa.indicator_id == ind.id, pa.region_id == a.id)
            .order_by(pa.period.desc()).limit(1))).first()
        if common is None:
            continue
        period, va, vb = common
        rows.append({
            "code": code,
            "name": _iname(ind),
            "unit": _iunit(ind),
            "period": period,
            "period_label": period_label(period, ind.frequency, get_locale()),
            "a": float(va), "b": float(vb),
        })
    if not rows:
        return None
    return {"country": country, "a": a, "b": b, "rows": rows}


async def render_subnational_compare_html(
    country_slug: str, slug_a: str, slug_b: str, db: AsyncSession,
) -> tuple[int, str]:
    payload = await subnational_compare_payload(country_slug, slug_a, slug_b, db)
    if payload is None:
        return 404, "Not found"
    country, a, b, rows = (payload[key] for key in ("country", "a", "b", "rows"))
    en = get_locale() == "en"
    an, bn, cn = _rname(a), _rname(b), _cname(country)
    district_pair = a.kind == "district" or b.kind == "district"
    title = (
        f"{an} vs {bn}: US regional statistics" if en else f"{an} и {bn}: сравнение регионов США"
    ) if district_pair else (
        f"{an} vs {bn}: state statistics" if en else f"{an} и {bn}: сравнение штатов"
    )
    desc = (f"Compare {an} and {bn} using {len(rows)} official indicators on matching publication dates."
            if en else f"Сравнение регионов США {an} и {bn} по {len(rows)} официальным показателям за одинаковые периоды наблюдений.")
    path = paths.country_region_vs(country.slug, a.slug, b.slug)
    og_path = og_subnational_compare(country.slug, a.slug, b.slug)
    th_period = "Period" if en else "Период"
    table_rows = []
    quick_links = []
    for row in rows:
        unit = row["unit"]
        va, vb = row["a"], row["b"]
        diff = va - vb
        sign = "+" if diff > 0 else ""
        link_a = paths.country_region_indicator(country.slug, a.slug, row["code"])
        link_b = paths.country_region_indicator(country.slug, b.slug, row["code"])
        table_rows.append(
            f"<tr><td>{escape(row['name'])}</td><td>{escape(row['period_label'])}</td>"
            f'<td><a href="{escape(link_a)}">{escape(format_number_ru(va, locale=get_locale()))} {escape(unit)}</a></td>'
            f'<td><a href="{escape(link_b)}">{escape(format_number_ru(vb, locale=get_locale()))} {escape(unit)}</a></td>'
            f"<td>{escape(sign + format_number_ru(diff, locale=get_locale()))} {escape(unit)}</td></tr>"
        )
        year = row["period"].year
        quick_links.append(
            f'<li><a href="{escape(paths.country_region_indicator_year(country.slug, a.slug, row["code"], year))}">'
            f'{escape(row["name"])}: {escape(an)}, {year}</a> — '
            f'<a href="{escape(paths.country_region_indicator_year(country.slug, b.slug, row["code"], year))}">'
            f'{escape(bn)}, {year}</a></li>'
        )
    figure = _seo_chart_figure(og_path, f"{title}: {len(rows)} {'official indicators' if en else 'официальных показателей'}", desc,
                               href=path, loading="eager")
    body = (
        fast_answer_block(eyebrow=("US states and DC" if en else "Штаты и округ Колумбия") if district_pair else
                          ("State comparison" if en else "Сравнение штатов"),
                          title=title, value=f"{len(rows)} {'indicators' if en else 'показателей'}",
                          note=desc)
        + figure
        + f"<section><h2>{'Comparison on matching dates' if en else 'Показатели за совпадающие периоды'}</h2>"
          f"<p>{'Values are not compared across different release dates.' if en else 'Значения за разные даты не сопоставляются.'}</p>"
          f"<table><thead><tr><th>{'Indicator' if en else 'Показатель'}</th>"
          f"<th>{th_period}</th><th>{escape(an)}</th><th>{escape(bn)}</th>"
          f"<th>{'Difference, first minus second' if en else 'Разница: первый минус второй'}</th>"
          f"</tr></thead><tbody>{''.join(table_rows)}</tbody></table></section>"
        + f"<section><h2>{'By year' if en else 'Сравнить по годам'}</h2><ul>{''.join(quick_links)}</ul></section>"
        + f'<p><a href="{escape(paths.country_region(country.slug, a.slug))}">{escape(an)}</a> — '
          f'<a href="{escape(paths.country_region(country.slug, b.slug))}">{escape(bn)}</a></p>'
    )
    trail = [(paths.country(country.slug), cn),
             (paths.country_regions(country.slug), _kind_plural(country.code)),
             (path, title)]
    json_ld = [
        {"@context": "https://schema.org", "@type": "WebPage", "name": title,
         "description": desc, "url": _absolute(path), "image": _absolute(og_path),
         "inLanguage": "en" if en else "ru"},
        _breadcrumbs(trail),
        {"@context": "https://schema.org", "@type": "ImageObject", "contentUrl": _absolute(og_path),
         "name": title, "representativeOfPage": True, "width": 1200, "height": 630},
    ]
    html = await build_document(
        title=title + " | Forecast Economy", description=desc,
        canonical_path=path, body=_breadcrumbs_nav(trail) + body,
        json_ld=json_ld, keywords=f"{an}, {bn}, {cn}, comparison",
        og_image=_absolute(og_path), include_app=False,
    )
    return 200, html

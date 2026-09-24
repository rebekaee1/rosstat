"""Data-backed yearly quicklinks for US states and other published regions.

Each page exists only when the selected state has an observation in that year.
Monthly/quarterly rows are labelled as observations; the last point is never
silently described as an annual total.
"""

from __future__ import annotations

from datetime import date
from html import escape

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SubnationalDataPoint, SubnationalIndicator, SubnationalRegion, WorldDataPoint, WorldIndicator
from app.services import site_paths as paths
from app.services.display import format_number_ru
from app.services.locale import get_locale
from app.services.seo_renderer import (
    _absolute, _breadcrumbs, _breadcrumbs_nav, _seo_chart_figure,
    build_document, fast_answer_block,
)
from app.services.seo_world_subnational import (
    _country, _cname, _iname, _iunit, _kind_plural, _rname,
    og_subnational_indicator,
)
from app.services.seo_world import _unit_of as _national_unit
from app.services.world_subnational_ingest import period_label


def og_subnational_indicator_year(country: str, region: str, code: str, year: int) -> str:
    return f"/og/world/{country}/region/{region}/{code}/{year}.png"


async def render_subnational_indicator_year_html(
    country_slug: str, region_slug: str, code: str, year: int, db: AsyncSession,
) -> tuple[int, str]:
    if not paths.is_public_year(year):
        return 404, "Not found"
    country = await _country(db, country_slug)
    if country is None:
        return 404, "Not found"
    region = (await db.execute(select(SubnationalRegion).where(
        SubnationalRegion.country_code == country.code,
        SubnationalRegion.slug == region_slug,
    ))).scalar_one_or_none()
    indicator = (await db.execute(select(SubnationalIndicator).where(
        SubnationalIndicator.country_code == country.code,
        SubnationalIndicator.code == code,
        SubnationalIndicator.is_listed.is_(True),
    ))).scalar_one_or_none()
    if region is None or indicator is None:
        return 404, "Not found"
    series = (await db.execute(select(SubnationalDataPoint.period, SubnationalDataPoint.value).where(
        SubnationalDataPoint.indicator_id == indicator.id,
        SubnationalDataPoint.region_id == region.id,
    ).order_by(SubnationalDataPoint.period))).all()
    year_rows = [(day, float(value)) for day, value in series if day.year == year]
    if not year_rows:
        return 404, "Not found"

    en = get_locale() == "en"
    country_name, region_name, name, unit = _cname(country), _rname(region), _iname(indicator), _iunit(indicator)
    value_date, value = year_rows[-1]
    value_text = f"{format_number_ru(value, locale=get_locale())} {unit}".strip()
    period_text = period_label(value_date, indicator.frequency, get_locale())
    years = sorted({day.year for day, _value in series if paths.is_public_year(day.year)})
    prev_year = year - 1
    # A partial current year must be compared with the same month/quarter of
    # the previous year, never with its December/Q4 observation.
    prev_rows = [
        (day, float(v)) for day, v in series
        if day.year == prev_year
        and (indicator.frequency == "annual" or day.month == value_date.month)
    ]
    prev = prev_rows[-1] if prev_rows else None
    path = paths.country_region_indicator_year(country.slug, region.slug, indicator.code, year)
    card = paths.country_region_indicator(country.slug, region.slug, indicator.code)
    og_path = og_subnational_indicator_year(country.slug, region.slug, indicator.code, year)

    title = (f"{name} in {region_name}, {year}" if en else f"{name} — {region_name}, {year} год")
    description = (
        f"Official {name.lower()} observations for {region_name} in {year}; latest published observation: {value_text} ({period_text})."
        if en else
        f"Официальные значения показателя «{name}» в регионе {region_name} за {year} год; последнее наблюдение: {value_text} ({period_text})."
    )
    # The chosen year has a value, but M/Q may have only partial coverage.
    expected = {"monthly": 12, "quarterly": 4}.get(indicator.frequency)
    coverage = ""
    if expected:
        got = len({(day.month - 1) // (1 if indicator.frequency == "monthly" else 3) for day, _v in year_rows})
        coverage = (
            f"{got} of {expected} published periods; this is not an annual total."
            if en else f"Опубликовано {got} из {expected} периодов; это не годовая сумма."
        )
    elif indicator.frequency == "annual":
        coverage = "Annual observation." if en else "Годовое наблюдение."

    compare = ""
    if prev:
        diff = value - prev[1]
        pct = diff / abs(prev[1]) * 100 if prev[1] else None
        sign = "+" if diff > 0 else ""
        diff_text = f"{sign}{format_number_ru(diff, locale=get_locale())} {unit}".strip()
        pct_text = f" ({sign}{format_number_ru(pct, locale=get_locale())}%)" if pct is not None else ""
        compare = (
            f"<p>{'Change from' if en else 'Изменение к'} {prev_year}: {escape(diff_text + pct_text)}. "
            f"<a href=\"{escape(paths.country_region_indicator_year(country.slug, region.slug, code, prev_year))}\">"
            f"{'Previous year' if en else 'Предыдущий год'}</a></p>"
        )

    national = ""
    if indicator.national_code:
        national_ind = (await db.execute(select(WorldIndicator).where(
            WorldIndicator.country_id == country.id,
            WorldIndicator.code == indicator.national_code,
            WorldIndicator.is_listed.is_(True),
        ))).scalar_one_or_none()
        if national_ind:
            national_rows = (await db.execute(select(WorldDataPoint.date, WorldDataPoint.value).where(
                WorldDataPoint.indicator_id == national_ind.id,
                WorldDataPoint.date >= date(year, 1, 1),
                WorldDataPoint.date < date(year + 1, 1, 1),
            ).order_by(WorldDataPoint.date.desc()).limit(1))).first()
            if national_rows:
                nval = format_number_ru(float(national_rows[1]), locale=get_locale())
                nunit = _national_unit(national_ind)
                national = (
                    f"<p>{'United States, latest observation in' if en else 'США в целом, последнее наблюдение за'} "
                    f"{year}: {escape(nval)} {escape(nunit)}. "
                    f"<a href=\"{escape(paths.indicator_year(country.slug, national_ind.code, year))}\">"
                    f"{'US series for this year' if en else 'Ряд США за этот год'}</a></p>"
                )

    peer_rows = (await db.execute(select(SubnationalRegion.slug, SubnationalRegion.name_en,
        SubnationalRegion.name_ru, SubnationalDataPoint.value).join(
        SubnationalDataPoint, SubnationalDataPoint.region_id == SubnationalRegion.id,
    ).where(
        SubnationalDataPoint.indicator_id == indicator.id,
        SubnationalDataPoint.period == value_date,
        SubnationalRegion.country_code == country.code,
        SubnationalRegion.kind == region.kind,
        SubnationalRegion.id != region.id,
    ).order_by(SubnationalRegion.sort_order).limit(6))).all()
    peer_links = "".join(
        f'<li><a href="{escape(paths.country_region_indicator_year(country.slug, slug, code, year))}">'
        f'{escape(name_en if en else name_ru)} — {escape(format_number_ru(float(v), locale=get_locale()))} {escape(unit)}</a></li>'
        for slug, name_en, name_ru, v in peer_rows
    )
    other_years = [y for y in years if y != year]
    years_html = "".join(
        f'<li><a href="{escape(paths.country_region_indicator_year(country.slug, region.slug, code, y))}">{y}</a></li>'
        for y in other_years
    )
    observations = "".join(
        f"<tr><td>{escape(period_label(day, indicator.frequency, get_locale()))}</td>"
        f"<td>{escape(format_number_ru(v, locale=get_locale()))} {escape(unit)}</td></tr>"
        for day, v in year_rows
    )
    alt = (f"{name}, {region_name}, {year}: official series and latest value {value_text}"
           if en else f"{name} — {region_name}, {year}: график и последнее значение {value_text}")
    body = (
        fast_answer_block(eyebrow="Official statistics" if en else "Официальная статистика",
                          title=title, value=value_text, note=f"{period_text}. {coverage}")
        + _seo_chart_figure(og_path, alt, description, href=card, loading="eager")
        + f"<section><h2>{'Year-on-year and US comparison' if en else 'Сравнение с прошлым годом и США'}</h2>{compare}{national}</section>"
        + f"<section><h2>{'Published observations' if en else 'Опубликованные значения'}</h2><table>"
          f"<thead><tr><th>{'Period' if en else 'Период'}</th><th>{'Value' if en else 'Значение'}</th></tr></thead>"
          f"<tbody>{observations}</tbody></table></section>"
        + f"<section><h2>{'Other years' if en else 'Другие годы'}</h2><ul>{years_html}</ul></section>"
        + (f"<section><h2>{'Compare states' if en else 'Сравнить со штатами'}</h2><ul>{peer_links}</ul></section>" if peer_links else "")
        + f'<p><a href="{escape(card)}">{"Full history" if en else "Вся история ряда"}</a></p>'
    )
    trail = [
        (paths.country(country.slug), country_name),
        (paths.country_regions(country.slug), _kind_plural(country.code)),
        (paths.country_region(country.slug, region.slug), region_name),
        (card, name), (path, str(year)),
    ]
    json_ld = [
        {"@context": "https://schema.org", "@type": "Dataset", "name": title,
         "description": description, "url": _absolute(path), "temporalCoverage": str(year),
         "spatialCoverage": region_name, "image": _absolute(og_path),
         "inLanguage": "en" if en else "ru"},
        _breadcrumbs(trail),
        {"@context": "https://schema.org", "@type": "ImageObject", "contentUrl": _absolute(og_path),
         "name": title, "representativeOfPage": True, "width": 1200, "height": 630},
    ]
    html = await build_document(
        title=title + " | Forecast Economy", description=description,
        canonical_path=path, body=_breadcrumbs_nav(trail) + body,
        json_ld=json_ld, keywords=f"{name}, {region_name}, {year}",
        og_image=_absolute(og_path), include_app=False,
    )
    return 200, html

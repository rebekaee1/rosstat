"""SSR субнациональных регионов: /{country}/regions, /{country}/region/{slug}[/{code}].

Отдельный контур (ADR-0014). Российский seo_regional не трогаем.
"""

from __future__ import annotations

from html import escape

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    SubnationalDataPoint,
    SubnationalIndicator,
    SubnationalRegion,
    WorldCountry,
)
from app.services import breadcrumbs as crumbs
from app.services import site_paths as paths
from app.services.display import format_number_ru
from app.services.locale import get_locale
from app.services.seo_renderer import (
    _absolute,
    _breadcrumbs,
    _breadcrumbs_nav,
    _seo_chart_figure,
    build_document,
)
from app.services.world_subnational_ingest import (
    country_has_subnational,
    load_subnational_passport,
    period_label,
)

_NOT_FOUND = (404, "Not found")


def _en() -> bool:
    return get_locale() == "en"


async def _country(db: AsyncSession, slug: str) -> WorldCountry | None:
    row = (
        await db.execute(
            select(WorldCountry).where(
                WorldCountry.slug == slug,
                WorldCountry.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if row is None or not country_has_subnational(row.code):
        return None
    return row


def _cname(country: WorldCountry) -> str:
    return country.name_en if _en() else country.name_ru


def _rname(region: SubnationalRegion) -> str:
    return region.name_en if _en() else region.name_ru


def _iname(ind: SubnationalIndicator) -> str:
    return ind.name_en if _en() else ind.name_ru


def _iunit(ind: SubnationalIndicator) -> str:
    return (ind.unit_en if _en() else ind.unit_ru) or ind.unit


def _kind_plural(country_code: str) -> str:
    passport = load_subnational_passport(country_code.lower())
    return passport.region_kind_label_en_plural if _en() else passport.region_kind_label_ru_plural


def _kind(country_code: str) -> str:
    passport = load_subnational_passport(country_code.lower())
    return passport.region_kind_label_en if _en() else passport.region_kind_label_ru


def og_subnational_hub(country_slug: str) -> str:
    return f"/og/world/{country_slug}/regions.png"


def og_subnational_region(country_slug: str, region_slug: str) -> str:
    return f"/og/world/{country_slug}/region/{region_slug}.png"


def og_subnational_indicator(country_slug: str, region_slug: str, code: str) -> str:
    return f"/og/world/{country_slug}/region/{region_slug}/{code}.png"


def _image_ld(og_path: str, name: str, description: str) -> dict:
    abs_url = _absolute(og_path)
    return {
        "@context": "https://schema.org",
        "@type": "ImageObject",
        "contentUrl": abs_url,
        "url": abs_url,
        "name": name,
        "description": description,
        "representativeOfPage": True,
        "width": 1200,
        "height": 630,
    }


async def render_subnational_hub_html(country_slug: str, db: AsyncSession) -> tuple[int, str]:
    country = await _country(db, country_slug)
    if country is None:
        return _NOT_FOUND
    loc = get_locale()
    country_name = _cname(country)
    kind_plural = _kind_plural(country.code)
    path = paths.country_regions(country.slug)
    title = f"{kind_plural} — {country_name} | Forecast Economy"
    description = (
        f"Official statistics by {kind_plural.lower()} of {country_name}: map, rankings and time series from national agencies."
        if _en()
        else f"Официальная статистика по {kind_plural.lower()} — {country_name}: карта, рейтинги и ряды национальных ведомств."
    )
    indicators = (
        await db.execute(
            select(SubnationalIndicator)
            .where(
                SubnationalIndicator.country_code == country.code,
                SubnationalIndicator.is_listed.is_(True),
            )
            .order_by(SubnationalIndicator.code)
        )
    ).scalars().all()
    regions = (
        await db.execute(
            select(SubnationalRegion)
            .where(SubnationalRegion.country_code == country.code)
            .order_by(SubnationalRegion.sort_order)
        )
    ).scalars().all()
    rows = "".join(
        f"<tr><td><a href=\"{escape(paths.country_region(country.slug, r.slug))}\">{escape(_rname(r))}</a></td></tr>"
        for r in regions
    )
    metrics = "".join(
        f"<li><a href=\"{escape(paths.country_region_map(country.slug, i.code))}\">{escape(_iname(i))}</a></li>"
        for i in indicators
    )
    loc_label = "Indicators" if _en() else "Показатели"
    list_label = kind_plural
    og_path = og_subnational_hub(country.slug)
    passport = load_subnational_passport(country.code.lower())
    default_ind = next((i for i in indicators if i.code == passport.default_indicator), None)
    default_name = _iname(default_ind) if default_ind else ""
    if _en():
        alt = (
            f"{kind_plural} — {country_name}: ranking by {default_name}"
            if default_name
            else f"{kind_plural} — {country_name}"
        )
        caption = f"{kind_plural} — {country_name}. Official statistics. forecasteconomy.com"
    else:
        alt = (
            f"{kind_plural} — {country_name}: рейтинг по показателю «{default_name}»"
            if default_name
            else f"{kind_plural} — {country_name}"
        )
        caption = f"{kind_plural} — {country_name}. Официальная статистика. forecasteconomy.com"
    figure = _seo_chart_figure(og_path, alt, caption, href=path, loading="eager")
    body = (
        f"<h1>{escape(kind_plural)} — {escape(country_name)}</h1>"
        f"{figure}"
        f"<p>{escape(description)}</p>"
        f"<h2>{escape(loc_label)}</h2><ul>{metrics}</ul>"
        f"<h2>{escape(list_label)}</h2>"
        f"<table><thead><tr><th>{escape(kind_plural)}</th></tr></thead><tbody>{rows}</tbody></table>"
    )
    trail = crumbs.world_subnational_hub_trail(country_name, paths.country(country.slug), kind_plural, path)
    json_ld = [
        {
            "@context": "https://schema.org",
            "@type": "Dataset",
            "name": title,
            "description": description,
            "url": _absolute(path),
            "inLanguage": "en" if loc == "en" else "ru",
            "image": _absolute(og_path),
        },
        _breadcrumbs(trail),
        _image_ld(og_path, title, alt),
    ]
    html = await build_document(
        title=title,
        description=description,
        canonical_path=path,
        body=_breadcrumbs_nav(trail) + body,
        json_ld=json_ld,
        keywords=f"{country_name}, {kind_plural}",
        og_image=_absolute(og_path),
    )
    return 200, html


async def render_subnational_region_html(
    country_slug: str, region_slug: str, db: AsyncSession,
) -> tuple[int, str]:
    country = await _country(db, country_slug)
    if country is None:
        return _NOT_FOUND
    region = (
        await db.execute(
            select(SubnationalRegion).where(
                SubnationalRegion.country_code == country.code,
                SubnationalRegion.slug == region_slug,
            )
        )
    ).scalar_one_or_none()
    if region is None:
        return _NOT_FOUND
    loc = get_locale()
    country_name = _cname(country)
    region_name = _rname(region)
    kind = _kind(country.code)
    kind_plural = _kind_plural(country.code)
    path = paths.country_region(country.slug, region.slug)
    title = f"{region_name} — {kind}, {country_name} | Forecast Economy"
    description = (
        f"Latest official indicators for {region_name} ({country_name}) and rank among {kind_plural.lower()}."
        if _en()
        else f"Последние официальные показатели {region_name} ({country_name}) и место среди {kind_plural.lower()}."
    )
    indicators = (
        await db.execute(
            select(SubnationalIndicator)
            .where(
                SubnationalIndicator.country_code == country.code,
                SubnationalIndicator.is_listed.is_(True),
            )
            .order_by(SubnationalIndicator.code)
        )
    ).scalars().all()
    rows_html = []
    for ind in indicators:
        last = (
            await db.execute(
                select(SubnationalDataPoint.period, SubnationalDataPoint.value)
                .where(
                    SubnationalDataPoint.indicator_id == ind.id,
                    SubnationalDataPoint.region_id == region.id,
                )
                .order_by(SubnationalDataPoint.period.desc())
                .limit(1)
            )
        ).first()
        value_txt = format_number_ru(last[1], locale=loc) if last else ("—" if _en() else "нет данных")
        when = period_label(last[0], ind.frequency, loc) if last else ""
        href = escape(paths.country_region_indicator(country.slug, region.slug, ind.code))
        unit = escape(_iunit(ind))
        label = f'<a href="{href}">{escape(_iname(ind))}</a>' if last else escape(_iname(ind))
        rows_html.append(
            f"<tr><td>{label}</td>"
            f"<td>{escape(value_txt)} {unit}</td><td>{escape(when)}</td></tr>"
        )
    th_ind = "Indicator" if _en() else "Показатель"
    th_val = "Latest" if _en() else "Последнее"
    th_date = "Period" if _en() else "Период"
    og_path = og_subnational_region(country.slug, region.slug)
    place = f"{region_name} — {country_name}"
    if _en():
        alt = f"{place}: key official indicators"
        caption = f"{place}. Official statistics. forecasteconomy.com"
    else:
        alt = f"{place}: ключевые официальные показатели"
        caption = f"{place}. Официальная статистика. forecasteconomy.com"
    figure = _seo_chart_figure(og_path, alt, caption, href=path, loading="eager")
    body = (
        f"<h1>{escape(region_name)}</h1>"
        f"{figure}"
        f"<p>{escape(kind)}, {escape(country_name)}</p>"
        f"<table><thead><tr><th>{th_ind}</th><th>{th_val}</th><th>{th_date}</th></tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody></table>"
    )
    trail = crumbs.world_subnational_region_trail(
        country_name, paths.country(country.slug),
        kind_plural, paths.country_regions(country.slug),
        region_name, path,
    )
    json_ld = [
        {
            "@context": "https://schema.org",
            "@type": "Dataset",
            "name": title,
            "description": description,
            "url": _absolute(path),
            "spatialCoverage": region_name,
            "inLanguage": "en" if loc == "en" else "ru",
            "image": _absolute(og_path),
        },
        _breadcrumbs(trail),
        _image_ld(og_path, title, alt),
    ]
    html = await build_document(
        title=title,
        description=description,
        canonical_path=path,
        body=_breadcrumbs_nav(trail) + body,
        json_ld=json_ld,
        keywords=f"{region_name}, {country_name}",
        og_image=_absolute(og_path),
    )
    return 200, html


async def render_subnational_indicator_html(
    country_slug: str, region_slug: str, code: str, db: AsyncSession,
) -> tuple[int, str]:
    country = await _country(db, country_slug)
    if country is None:
        return _NOT_FOUND
    region = (
        await db.execute(
            select(SubnationalRegion).where(
                SubnationalRegion.country_code == country.code,
                SubnationalRegion.slug == region_slug,
            )
        )
    ).scalar_one_or_none()
    indicator = (
        await db.execute(
            select(SubnationalIndicator).where(
                SubnationalIndicator.country_code == country.code,
                SubnationalIndicator.code == code,
                SubnationalIndicator.is_listed.is_(True),
            )
        )
    ).scalar_one_or_none()
    if region is None or indicator is None:
        return _NOT_FOUND
    loc = get_locale()
    country_name = _cname(country)
    region_name = _rname(region)
    ind_name = _iname(indicator)
    kind_plural = _kind_plural(country.code)
    path = paths.country_region_indicator(country.slug, region.slug, indicator.code)
    title = f"{ind_name} — {region_name} | Forecast Economy"
    description = (
        f"{ind_name} in {region_name} ({country_name}). Official series, latest value and history."
        if _en()
        else f"{ind_name} — {region_name} ({country_name}). Официальный ряд, последнее значение и история."
    )
    points = (
        await db.execute(
            select(SubnationalDataPoint.period, SubnationalDataPoint.value)
            .where(
                SubnationalDataPoint.indicator_id == indicator.id,
                SubnationalDataPoint.region_id == region.id,
            )
            .order_by(SubnationalDataPoint.period.desc())
            .limit(24)
        )
    ).all()
    if not points:
        return _NOT_FOUND
    th_date = "Period" if _en() else "Период"
    th_val = "Value" if _en() else "Значение"
    unit = _iunit(indicator)
    rows = "".join(
        f"<tr><td>{escape(period_label(p, indicator.frequency, loc))}</td>"
        f"<td>{escape(format_number_ru(v, locale=loc))} {escape(unit)}</td></tr>"
        for p, v in points
    )
    last = points[0] if points else None
    last_txt = (
        f"{format_number_ru(last[1], locale=loc)} {unit} ({period_label(last[0], indicator.frequency, loc)})"
        if last else ("no data" if _en() else "нет данных")
    )
    desc = (indicator.description_en if _en() else indicator.description_ru) or ""
    meth = (indicator.methodology_en if _en() else indicator.methodology_ru) or ""
    src = (indicator.source_en if _en() else indicator.source_ru) or ""
    about = "About" if _en() else "О показателе"
    meth_h = "Methodology" if _en() else "Методология"
    src_h = "Source" if _en() else "Источник"
    latest_h = "Latest value" if _en() else "Последнее значение"
    og_path = og_subnational_indicator(country.slug, region.slug, indicator.code)
    src_label = src or ("official source" if _en() else "официальный источник")
    if last:
        last_value = f"{format_number_ru(last[1], locale=loc)} {unit}".strip()
        last_period = period_label(last[0], indicator.frequency, loc)
        if _en():
            alt = (
                f"{region_name} {ind_name.lower()} — chart, latest value "
                f"{last_value} ({last_period}), source {src_label}"
            )
            caption = (
                f"{ind_name} in {region_name}, {country_name}. "
                f"Source: {src_label}. forecasteconomy.com"
            )
        else:
            alt = (
                f"{ind_name} — {region_name}: график динамики, последнее значение "
                f"{last_value} ({last_period}), источник {src_label}"
            )
            caption = (
                f"{ind_name} — {region_name}, {country_name}. "
                f"Источник: {src_label}. forecasteconomy.com"
            )
    elif _en():
        alt = f"{region_name} {ind_name.lower()} — chart, source {src_label}"
        caption = f"{ind_name} in {region_name}. Source: {src_label}. forecasteconomy.com"
    else:
        alt = f"{ind_name} — {region_name}: график, источник {src_label}"
        caption = f"{ind_name} — {region_name}. Источник: {src_label}. forecasteconomy.com"
    figure = _seo_chart_figure(og_path, alt, caption, href=path, loading="eager")
    body = (
        f"<h1>{escape(ind_name)} — {escape(region_name)}</h1>"
        f"{figure}"
        f"<p><strong>{escape(latest_h)}:</strong> {escape(last_txt)}</p>"
        f"<p>{escape(desc)}</p>"
        f"<h2>{escape(meth_h)}</h2><p>{escape(meth)}</p>"
        f"<p><strong>{escape(src_h)}:</strong> {escape(src)}</p>"
        f"<h2>{escape(about)}</h2>"
        f"<table><thead><tr><th>{th_date}</th><th>{th_val}</th></tr></thead><tbody>{rows}</tbody></table>"
    )
    trail = crumbs.world_subnational_indicator_trail(
        country_name, paths.country(country.slug),
        kind_plural, paths.country_regions(country.slug),
        region_name, paths.country_region(country.slug, region.slug),
        ind_name, path,
    )
    json_ld = [
        {
            "@context": "https://schema.org",
            "@type": "Dataset",
            "name": title,
            "description": description,
            "url": _absolute(path),
            "spatialCoverage": region_name,
            "inLanguage": "en" if loc == "en" else "ru",
            "image": _absolute(og_path),
        },
        _breadcrumbs(trail),
        _image_ld(og_path, title, alt),
    ]
    html = await build_document(
        title=title,
        description=description,
        canonical_path=path,
        body=_breadcrumbs_nav(trail) + body,
        json_ld=json_ld,
        keywords=f"{ind_name}, {region_name}, {country_name}",
        og_image=_absolute(og_path),
    )
    return 200, html

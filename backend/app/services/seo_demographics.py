"""Observed age-structure infographic and accessible data for the public page."""
from html import escape
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import site_paths as paths
from app.services.demographics import AGE_GROUP_CODES, age_structure, complete_snapshot, snapshot_groups
from app.services.display import format_number_ru, localize_unit
from app.services.locale import get_locale, in_language
from app.services.seo_i18n import get_page_seo, translate_source
from app.services.seo_renderer import (
    _absolute, _breadcrumbs, _page_body, _page_trail, _seo_chart_figure,
    _site_json_ld, build_document, render_page_html,
)


async def render_demographics_html(db: AsyncSession) -> tuple[int, str]:
    data = await age_structure(db)
    row = complete_snapshot(data)
    if row is None:
        return await render_page_html("demographics")
    loc = get_locale()
    page = get_page_seo("demographics")
    trail = _page_trail("demographics", page)
    groups = snapshot_groups(row, loc)
    unit = localize_unit(data["meta"][AGE_GROUP_CODES[0]]["unit"], locale=loc)
    year = row["year"]
    heading = f"Population by age group, {year}" if loc == "en" else f"Население по возрастным группам, {year}"
    source = translate_source(data["meta"][AGE_GROUP_CODES[0]].get("source"), loc) or ("Rosstat" if loc == "en" else "Росстат")
    source_label = ("Source: " if loc == "en" else "Источник: ") + source
    image_path = "/og/russia/demographics.png"
    rows = "".join(
        f'<tr><th scope="row"><a href="{paths.russia_indicator(code)}">{escape(label)}</a></th>'
        f'<td>{escape(format_number_ru(value, locale=loc))}</td></tr>'
        for code, (label, value) in zip(AGE_GROUP_CODES, groups)
    )
    figure = _seo_chart_figure(image_path, f"{heading} — {unit}. {source_label}", heading,
                               href=paths.demographics(), loading="eager")
    section = (f'<section><h2>{escape(heading)}</h2>{figure}'
               f'<table><caption>{escape(unit)}</caption><tbody>{rows}</tbody></table>'
               f'<p><a href="{paths.russia_category("population")}">{escape(source_label)}</a></p></section>')
    body = _page_body(page, trail).replace("</main>", section + "</main>")
    source_urls = sorted({meta.get("source_url") for meta in data["meta"].values() if meta.get("source_url")})
    image = {"@context": "https://schema.org", "@type": "ImageObject",
             "contentUrl": _absolute(image_path), "name": heading,
             "width": 1200, "height": 630, "representativeOfPage": True}
    dataset = {"@context": "https://schema.org", "@type": "Dataset", "name": heading,
               "description": page.description, "url": _absolute(page.path),
               "temporalCoverage": str(year), "inLanguage": in_language(),
               "creator": {"@type": "Organization", "name": source},
               "variableMeasured": [{"@type": "PropertyValue", "name": label,
                                      "value": value, "unitText": unit} for label, value in groups]}
    if source_urls:
        dataset["isBasedOn"] = source_urls
    return 200, await build_document(
        title=page.title, description=page.description, canonical_path=page.path,
        body=body, json_ld=[_site_json_ld(), _breadcrumbs(trail), dataset, image],
        keywords=page.keywords, og_image=_absolute(image_path),
    )

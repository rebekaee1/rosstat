"""SSR-карточка квартального показателя региона (цена 1 м² жилья, доходы к прожиточному минимуму; 19.11.2026).

Годовой рендер строит тексты вокруг «года» (контрольные годы, «за пять лет»), месячный — вокруг цен товаров.
Квартальному ряду нужна своя короткая обвязка: последний квартал, изменение к прошлому кварталу и к тому же
кварталу год назад, место среди регионов, сравнение с Россией, таблица по кварталам. Тексты — на языке хоста.
"""

from __future__ import annotations

from html import escape

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.region_indicator_polarity import region_rating_order_by
from app.models import Region, RegionIndicator, RegionQuarterlyPoint
from app.services import breadcrumbs as crumbs
from app.services import site_paths as paths
from app.services.locale import get_locale
from app.services.regional_quarterly import quarter_label
from app.services.seo_renderer import _absolute, _breadcrumbs, _breadcrumbs_nav, build_document

_T = {
    "ru": {
        "p1": "{indicator} — {region}: {value}{unit} в {period}.",
        "q_change": " За квартал — {change}.",
        "y_change": " За год (к {period}) — {change}.",
        "rank": "Среди {total} регионов {region} на {position}-м месте по величине в {period}.",
        "rf": " По России в целом — {value}{unit}.",
        "table_h2": "{indicator} по кварталам",
        "th_period": "Квартал",
        "th_value": "Значение",
        "faq_h2": "Вопросы и ответы",
        "faq_value_q": "Сколько составляет показатель «{indicator}» в регионе {region}?",
        "faq_value_a": "По данным Росстата за {period} — {value}{unit}.",
        "faq_source_q": "Откуда данные и как часто они обновляются?",
        "faq_source_a": "Источник — Росстат. Данные квартальные, выходят примерно через полтора месяца "
                        "после конца квартала; прошлые кварталы Росстат иногда уточняет.",
        "neighbors_h2": "Этот показатель у соседей по округу",
        "siblings_h2": "Ещё в разделе «{section}»",
        "description": "{indicator} в регионе {region}: {value}{unit} в {period}. Ряд по кварталам с {first}, "
                       "сравнение с Россией и другими регионами. Данные Росстата.",
        "title": "{indicator} — {region}: {value}{unit} ({period})",
        "pct_up": "рост на {pct}%",
        "pct_down": "снижение на {pct}%",
        "pct_flat": "без изменений",
        "source_h2": "Источник данных",
        "source_p": "Росстат. Период наблюдений: {first} — {last}.",
    },
    "en": {
        "p1": "{indicator} — {region}: {value}{unit} in {period}.",
        "q_change": " Over the quarter: {change}.",
        "y_change": " Over the year (vs {period}): {change}.",
        "rank": "{region} ranks {position} of {total} regions by value in {period}.",
        "rf": " Russia as a whole: {value}{unit}.",
        "table_h2": "{indicator} by quarter",
        "th_period": "Quarter",
        "th_value": "Value",
        "faq_h2": "Questions and answers",
        "faq_value_q": "What is the value of “{indicator}” in {region}?",
        "faq_value_a": "According to Rosstat, {value}{unit} in {period}.",
        "faq_source_q": "Where do the data come from and how often are they updated?",
        "faq_source_a": "Source: Rosstat. Quarterly data come out about six weeks after the quarter ends; "
                        "Rosstat sometimes revises earlier quarters.",
        "neighbors_h2": "The same indicator in neighbouring regions",
        "siblings_h2": "More in “{section}”",
        "description": "{indicator} in {region}: {value}{unit} in {period}. Quarterly series since {first}, "
                       "comparison with Russia and other regions. Rosstat data.",
        "title": "{indicator} — {region}: {value}{unit} ({period})",
        "pct_up": "up {pct}%",
        "pct_down": "down {pct}%",
        "pct_flat": "unchanged",
        "source_h2": "Data source",
        "source_p": "Rosstat. Observation period: {first} to {last}.",
    },
}


def _t(key: str, **kw) -> str:
    tpl = _T["en" if get_locale() == "en" else "ru"][key]
    return tpl.format(**kw) if kw else tpl


_SOURCE_KEYS = {
    "ru": {
        "faq_value_a": "За {period} — {value}{unit}. Источник — {source}.",
        "description": "{indicator} в регионе {region}: {value}{unit} в {period}. Ряд по кварталам с {first}, "
                       "сравнение с Россией и другими регионами. Источник — {source}.",
        "source_p": "{source}. Период наблюдений: {first} — {last}.",
    },
    "en": {
        "faq_value_a": "In {period}: {value}{unit}. Source: {source}.",
        "description": "{indicator} in {region}: {value}{unit} in {period}. Quarterly series since {first}, "
                       "comparison with Russia and other regions. Source: {source}.",
        "source_p": "{source}. Observation period: {first} to {last}.",
    },
}


def _ts(code: str, key: str, **kw) -> str:
    """Фраза с источником ряда: у туризма по регионам (20.11.2026) это не всегда Росстат (ЦБ — «Поездки»)."""
    from app.data.tourism_regional import source_of

    src = source_of(code)
    lang = "en" if get_locale() == "en" else "ru"
    if src is None:
        return ("Rosstat" if lang == "en" else "Росстат") if key == "creator" else _t(key, **kw)
    if key == "faq_source_a":
        return src[f"about_{lang}"]
    if key == "creator":
        return src[lang]
    return _SOURCE_KEYS[lang][key].format(source=src[lang], **kw)


def _change(cur: float, base: float | None, fmt) -> str | None:
    if base is None or base == 0:
        return None
    pct = (cur - base) / abs(base) * 100
    if abs(pct) < 0.05:
        return _t("pct_flat")
    return _t("pct_up" if pct > 0 else "pct_down", pct=fmt(round(abs(pct), 1)))


async def render_region_indicator_quarterly(
    slug: str, code: str, region: Region, indicator: RegionIndicator, rows: list[tuple[int, float]],
    db: AsyncSession, *, fmt, rname, icopy,
) -> tuple[int, str]:
    """``fmt``/``rname``/``icopy`` — те же помощники, что у годового рендера (``seo_regional``)."""
    first_q = rows[0][0]
    last_q, last_value = rows[-1]
    by_q = dict(rows)
    region_name = rname(region.slug, region.name)
    copy = icopy(indicator)
    ind_name = copy["name"] or indicator.name
    unit = copy["unit"] or indicator.unit or ""
    unit_sfx = f" {unit}" if unit else ""
    section = copy["section"] or indicator.section_name
    period = quarter_label(last_q)

    paragraphs = [_t("p1", indicator=escape(ind_name), region=escape(region_name), value=fmt(last_value),
                     unit=escape(unit_sfx), period=period)]
    prev_q = rows[-2][1] if len(rows) > 1 else None
    ch_q = _change(last_value, prev_q, fmt)
    if ch_q:
        paragraphs[0] += _t("q_change", change=ch_q)
    ch_y = _change(last_value, by_q.get(last_q - 10), fmt)
    if ch_y:
        paragraphs[0] += _t("y_change", period=quarter_label(last_q - 10), change=ch_y)

    rank_rows = (await db.execute(
        select(Region.slug, RegionQuarterlyPoint.value).join(Region, Region.id == RegionQuarterlyPoint.region_id)
        .where(RegionQuarterlyPoint.indicator_id == indicator.id, RegionQuarterlyPoint.quarter == last_q,
               Region.kind == "region")
        .order_by(region_rating_order_by(RegionQuarterlyPoint.value, indicator.code, indicator.table_code))
    )).all()
    position = next((i for i, (s, _v) in enumerate(rank_rows, 1) if s == region.slug), None)
    p2 = ""
    if position and region.kind == "region":
        p2 = _t("rank", total=len(rank_rows), region=escape(region_name), position=position, period=period)
    if region.slug != "russia":
        rf_value = (await db.execute(
            select(RegionQuarterlyPoint.value).join(Region, Region.id == RegionQuarterlyPoint.region_id)
            .where(RegionQuarterlyPoint.indicator_id == indicator.id, RegionQuarterlyPoint.quarter == last_q,
                   Region.slug == "russia")
        )).scalar_one_or_none()
        if rf_value is not None:
            p2 += _t("rf", value=fmt(float(rf_value)), unit=escape(unit_sfx))
    if p2:
        paragraphs.append(p2.strip())
    if copy.get("note"):
        paragraphs.append(escape(copy["note"]))
    paragraphs_html = "".join(f"<p>{p}</p>" for p in paragraphs)

    table_rows = "".join(f"<tr><td>{quarter_label(q)}</td><td>{fmt(v)}</td></tr>" for q, v in reversed(rows[-40:]))
    table_html = (
        f"<h2>{escape(_t('table_h2', indicator=ind_name))}</h2>"
        f"<table><thead><tr><th>{escape(_t('th_period'))}</th><th>{escape(unit or _t('th_value'))}</th></tr>"
        f"</thead><tbody>{table_rows}</tbody></table>"
    )

    faq = [
        (_t("faq_value_q", indicator=ind_name, region=region_name),
         _ts(code, "faq_value_a", period=period, value=fmt(last_value), unit=unit_sfx)),
        (_t("faq_source_q"), _ts(code, "faq_source_a")),
    ]
    faq_html = (
        f'<section class="seo-section"><h2>{escape(_t("faq_h2"))}</h2>'
        + "".join(f"<h3>{escape(q)}</h3><p>{escape(a)}</p>" for q, a in faq) + "</section>"
    )

    district_html = ""
    if region.kind == "region" and region.district_slug:
        neighbors = (await db.execute(
            select(Region.slug, Region.name).where(
                Region.district_slug == region.district_slug, Region.kind == "region", Region.slug != region.slug)
            .order_by(Region.sort_order)
        )).all()
        if neighbors:
            items = "".join(
                f'<li><a href="{escape(paths.region_indicator(s, code))}">{escape(ind_name)} — '
                f"{escape(rname(s, n))}</a></li>" for s, n in neighbors
            )
            district_html = (f'<section class="seo-section"><h2>{escape(_t("neighbors_h2"))}</h2>'
                             f"<ul>{items}</ul></section>")

    siblings = (await db.execute(
        select(RegionIndicator).where(
            RegionIndicator.section_num == indicator.section_num, RegionIndicator.code != indicator.code,
            RegionIndicator.is_listed.is_(True), RegionIndicator.table_code.like(
                (indicator.table_code or "").split(".")[0] + ".q%"))
        .order_by(RegionIndicator.table_code).limit(12)
    )).scalars().all()
    siblings_html = ""
    if siblings:
        items = "".join(
            f'<li><a href="{escape(paths.region_indicator(slug, x.code))}">{escape(icopy(x)["name"] or x.name)}</a></li>'
            for x in siblings
        )
        siblings_html = (f'<section class="seo-section"><h2>{escape(_t("siblings_h2", section=section))}</h2>'
                         f"<ul>{items}</ul></section>")

    title = _t("title", indicator=ind_name, region=region_name, value=fmt(last_value), unit=unit_sfx, period=period)
    desc = _ts(code, "description", indicator=ind_name, region=region_name, value=fmt(last_value), unit=unit_sfx,
              period=period, first=quarter_label(first_q))
    trail = crumbs.region_indicator_trail(region_name, paths.region(slug), ind_name, paths.region_indicator(slug, code))
    json_ld = [
        _breadcrumbs(trail),
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]},
        {"@context": "https://schema.org", "@type": "Dataset", "name": f"{ind_name} — {region_name}",
         "description": desc, "url": _absolute(paths.region_indicator(slug, code)),
         "temporalCoverage": f"{first_q // 10}/{last_q // 10}", "spatialCoverage": region_name,
         "creator": {"@type": "Organization", "name": _ts(code, "creator")}},
    ]
    body = f"""<div class="seo-page">
{_breadcrumbs_nav(trail)}
<p class="seo-eyebrow">{escape(section)} — {escape(region_name)}</p>
<h1>{escape(ind_name)} — {escape(region_name)}</h1>
{paragraphs_html}
{table_html}
{faq_html}
{district_html}
{siblings_html}
<section class="seo-section"><h2>{escape(_t("source_h2"))}</h2>
<p>{escape(_ts(code, "source_p", first=quarter_label(first_q), last=period))}</p></section>
</div>"""
    html = await build_document(
        title=title, description=desc, canonical_path=paths.region_indicator(slug, code), body=body,
        json_ld=json_ld, keywords=f"{ind_name} {region_name}, {ind_name} {region_name} {last_q // 10}",
    )
    return 200, html

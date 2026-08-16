"""SSR-посадочные календаря статистики: /russia/calendar/{year}/{month}.

Под запросы «когда выйдет инфляция за июль», «календарь росстата август 2026».
Показываются только официальные даты с provenance (ADR-0005) — estimated
скрыты, как и в интерактивном календаре.
"""

from __future__ import annotations

from app.services import breadcrumbs as crumbs
from app.services import site_paths as paths

from datetime import date

from app.services.display import today_msk
from html import escape

from sqlalchemy import extract, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EconomicEvent
from app.services.seo_renderer import (
    _breadcrumbs,
    _breadcrumbs_nav,
    _site_json_ld,
    build_document,
)

_MONTHS_NOM = (
    "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
)
_MONTHS_GEN = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)

_SOURCE_NAMES = {
    "rosstat": "Росстат",
    "cbr": "Банк России",
    "minfin": "Минфин России",
}


async def render_calendar_month_html(
    year: int, month: int, db: AsyncSession
) -> tuple[int, str]:
    if not (2000 <= year <= 2100 and 1 <= month <= 12):
        return 404, "Not found"

    from app.api.calendar import _public_calendar_conditions
    from app.services.seo_i18n import calendar_month_name, calendar_template, event_public_title

    events = (await db.execute(
        select(EconomicEvent)
        .where(
            extract("year", EconomicEvent.scheduled_date) == year,
            extract("month", EconomicEvent.scheduled_date) == month,
            *_public_calendar_conditions(),
        )
        .order_by(EconomicEvent.scheduled_date, EconomicEvent.importance.desc())
    )).scalars().all()
    if len(events) < 3:
        return 404, "Not found"

    month_nom = _MONTHS_NOM[month - 1]
    month_gen = _MONTHS_GEN[month - 1]
    today = today_msk()
    is_future = (year, month) >= (today.year, today.month)

    en_month = calendar_month_name(month)
    month_display = en_month or month_nom
    month_gen_display = en_month or month_gen

    source_names = {
        "rosstat": calendar_template("source_rosstat") or _SOURCE_NAMES["rosstat"],
        "cbr": calendar_template("source_cbr") or _SOURCE_NAMES["cbr"],
        "minfin": calendar_template("source_minfin") or _SOURCE_NAMES["minfin"],
    }
    status_expected = calendar_template("status_expected") or "ожидается"
    status_dash = calendar_template("status_dash") or "—"
    actual_prefix = calendar_template("actual_prefix")

    rows_html = []
    for ev in events:
        d = ev.scheduled_date
        src = source_names.get(ev.source, ev.source)
        period = f" ({escape(ev.reference_period)})" if ev.reference_period else ""
        value = ""
        if ev.actual_value:
            if actual_prefix:
                value = escape(actual_prefix.format(value=ev.actual_value))
            else:
                value = f" Факт: {escape(ev.actual_value)}."
        day_label = (
            f"{d.day} {escape(en_month)}" if en_month else f"{d.day} {escape(month_gen)}"
        )
        pub_title = event_public_title(ev.title, ev.title_en)
        rows_html.append(
            f"<tr><td>{day_label}</td>"
            f"<td>{escape(pub_title)}{period}</td>"
            f"<td>{escape(src)}</td>"
            f"<td>{value or (status_expected if is_future else status_dash)}</td></tr>"
        )

    verb = "выйдут" if is_future else "вышли"
    en_title = calendar_template("title")
    en_desc = calendar_template("desc_future" if is_future else "desc_past")
    en_h1 = calendar_template("h1")
    en_intro = calendar_template("intro")
    title = (
        en_title.format(month=month_display, year=year)
        if en_title
        else f"Календарь экономической статистики — {month_nom} {year}: даты публикаций"
    )
    desc = (
        en_desc.format(month_gen=month_gen_display, year=year, n=len(events))
        if en_desc
        else (
            f"Какие данные по экономике России {verb} в {month_gen} {year} года: "
            f"{len(events)} публикаций Росстата, Банка России и Минфина с точными датами — "
            f"инфляция, ставка, ВВП и другие показатели."
        )
    )
    h1_text = (
        en_h1.format(month=month_display, year=year)
        if en_h1
        else f"Календарь статистики: {month_nom} {year}"
    )
    intro = (
        en_intro.format(month_gen=month_gen_display, year=year)
        if en_intro
        else (
            f"Официальные даты публикаций экономической статистики России в "
            f"{month_gen} {year} года. "
            f"Даты — официальные, из графиков раскрытия информации самих ведомств."
        )
    )
    canonical = paths.calendar(year, month)

    prev_y, prev_m = (year - 1, 12) if month == 1 else (year, month - 1)
    next_y, next_m = (year + 1, 1) if month == 12 else (year, month + 1)

    n_rosstat = sum(1 for e in events if e.source == "rosstat")
    n_cbr = sum(1 for e in events if e.source == "cbr")
    month_label = f"{(en_month or month_nom).capitalize()} {year}"
    month_trail = crumbs.calendar_month_trail(month_label, paths.calendar(year, month))
    prev_label = calendar_month_name(prev_m) or _MONTHS_NOM[prev_m - 1]
    next_label = calendar_month_name(next_m) or _MONTHS_NOM[next_m - 1]

    eyebrow = calendar_template("eyebrow") or "Календарь публикаций"
    tile_pub = calendar_template("tile_publications") or "Публикаций"
    tile_rosstat = calendar_template("tile_rosstat") or "Росстат"
    tile_cbr = calendar_template("tile_cbr") or "Банк России"
    tile_other = calendar_template("tile_other") or "Минфин и другие"
    h2_month = calendar_template("h2_month") or "Публикации месяца"
    h2_neighbors = calendar_template("h2_neighbors") or "Соседние месяцы"
    th_date = calendar_template("th_date") or "Дата"
    th_pub = calendar_template("th_publication") or "Публикация"
    th_agency = calendar_template("th_agency") or "Ведомство"
    th_status = calendar_template("th_status") or "Статус"
    interactive = calendar_template("interactive") or "Интерактивный календарь"
    en_kw = calendar_template("keywords")
    keywords = (
        en_kw.format(month=month_display, year=year)
        if en_kw
        else (
            f"календарь статистики {month_nom} {year}, когда выйдет инфляция {month_nom} {year}, "
            f"публикации росстата {month_nom} {year}, календарь цб {year}"
        )
    )

    body = f"""<main class="seo-page">
{_breadcrumbs_nav(month_trail)}
<p class="seo-eyebrow">{escape(eyebrow)}</p>
<h1>{escape(h1_text)}</h1>
<p>{escape(intro)}</p>
<div class="seo-tiles">
<div class="seo-tile"><span>{escape(tile_pub)}</span><b>{len(events)}</b></div>
<div class="seo-tile"><span>{escape(tile_rosstat)}</span><b>{n_rosstat}</b></div>
<div class="seo-tile"><span>{escape(tile_cbr)}</span><b>{n_cbr}</b></div>
<div class="seo-tile"><span>{escape(tile_other)}</span><b>{len(events) - n_rosstat - n_cbr}</b></div>
</div>
<section><h2>{escape(h2_month)}</h2>
<div class="seo-scroll"><table><thead><tr><th>{escape(th_date)}</th><th>{escape(th_pub)}</th><th>{escape(th_agency)}</th><th>{escape(th_status)}</th></tr></thead>
<tbody>{''.join(rows_html)}</tbody></table></div></section>
<section><h2>{escape(h2_neighbors)}</h2>
<ul class="seo-pills"><li><a href="{paths.calendar(prev_y, prev_m)}">← {escape(prev_label.capitalize())} {prev_y}</a></li>
<li><a href="{paths.calendar(next_y, next_m)}">{escape(next_label.capitalize())} {next_y} →</a></li>
<li><a href="{paths.calendar()}">{escape(interactive)}</a></li></ul></section>
</main>"""

    json_ld = [
        _site_json_ld(),
        _breadcrumbs(month_trail),
    ]
    html = await build_document(
        title=title,
        description=desc,
        canonical_path=canonical,
        body=body,
        json_ld=json_ld,
        keywords=keywords,
    )
    return 200, html

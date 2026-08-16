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

    # В-7: тот же provenance-фильтр, что у публичного API (ADR-0005) — иначе
    # legacy-строка без event_key/source_hash показалась бы только в SSR.
    from app.api.calendar import _public_calendar_conditions

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

    rows_html = []
    for ev in events:
        d = ev.scheduled_date
        src = _SOURCE_NAMES.get(ev.source, ev.source)
        period = f" ({escape(ev.reference_period)})" if ev.reference_period else ""
        value = ""
        if ev.actual_value:
            value = f" Факт: {escape(ev.actual_value)}."
        rows_html.append(
            f"<tr><td>{d.day} {escape(month_gen)}</td>"
            f"<td>{escape(ev.title)}{period}</td>"
            f"<td>{escape(src)}</td><td>{value or ('ожидается' if is_future else '—')}</td></tr>"
        )

    verb = "выйдут" if is_future else "вышли"
    title = f"Календарь экономической статистики — {month_nom} {year}: даты публикаций"
    desc = (
        f"Какие данные по экономике России {verb} в {month_gen} {year} года: "
        f"{len(events)} публикаций Росстата, Банка России и Минфина с точными датами — "
        f"инфляция, ставка, ВВП и другие показатели."
    )
    canonical = paths.calendar(year, month)

    prev_y, prev_m = (year - 1, 12) if month == 1 else (year, month - 1)
    next_y, next_m = (year + 1, 1) if month == 12 else (year, month + 1)

    n_rosstat = sum(1 for e in events if e.source == "rosstat")
    n_cbr = sum(1 for e in events if e.source == "cbr")
    month_label = f"{month_nom.capitalize()} {year}"
    month_trail = crumbs.calendar_month_trail(month_label, paths.calendar(year, month))
    body = f"""<main class="seo-page">
{_breadcrumbs_nav(month_trail)}
<p class="seo-eyebrow">Календарь публикаций</p>
<h1>Календарь статистики: {escape(month_nom)} {year}</h1>
<p>Официальные даты публикаций экономической статистики России в {escape(month_gen)} {year} года.
Даты — официальные, из графиков раскрытия информации самих ведомств.</p>
<div class="seo-tiles">
<div class="seo-tile"><span>Публикаций</span><b>{len(events)}</b></div>
<div class="seo-tile"><span>Росстат</span><b>{n_rosstat}</b></div>
<div class="seo-tile"><span>Банк России</span><b>{n_cbr}</b></div>
<div class="seo-tile"><span>Минфин и другие</span><b>{len(events) - n_rosstat - n_cbr}</b></div>
</div>
<section><h2>Публикации месяца</h2>
<div class="seo-scroll"><table><thead><tr><th>Дата</th><th>Публикация</th><th>Ведомство</th><th>Статус</th></tr></thead>
<tbody>{''.join(rows_html)}</tbody></table></div></section>
<section><h2>Соседние месяцы</h2>
<ul class="seo-pills"><li><a href="{paths.calendar(prev_y, prev_m)}">← {escape(_MONTHS_NOM[prev_m - 1].capitalize())} {prev_y}</a></li>
<li><a href="{paths.calendar(next_y, next_m)}">{escape(_MONTHS_NOM[next_m - 1].capitalize())} {next_y} →</a></li>
<li><a href="{paths.calendar()}">Интерактивный календарь</a></li></ul></section>
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
        keywords=(
            f"календарь статистики {month_nom} {year}, когда выйдет инфляция {month_nom} {year}, "
            f"публикации росстата {month_nom} {year}, календарь цб {year}"
        ),
    )
    return 200, html

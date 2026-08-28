"""SSR-страницы «индикатор за месяц»: /{country}/indicator/{code}/{year}-{mm}.

Long-tail спрос «инфляция в июле 2025», «курс доллара в марте 2024».
Эталон контента — годовой лендинг (`seo_renderer.render_indicator_year_html`):
крошки, видимая OG-картинка месяца, таблица значений, навигация по соседним
периодам, CTA на живую карточку. Чистый SSR (include_app=False): у SPA-роутера
нет такого маршрута.

Лендинги за месяц отдаём только для monthly-рядов (daily/weekly — не
создаются, решение владельца). OG-путь месяца (`/og/russia/cpi/2025-07.png`)
строится тем же шаблоном, что и годовой, чтобы nginx-rewrite месяца лёг
ровно на существующий формат картинок.
"""

from __future__ import annotations

from datetime import date
from html import escape

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.global_market_indicators import is_global_market_indicator
from app.models import Indicator, IndicatorData
from app.services import breadcrumbs as crumbs
from app.services import site_paths as paths
from app.services.display import (
    display_value,
    format_month_year,
    format_number_ru,
    is_cpi_index,
)
from app.services.seo_renderer import (
    _absolute,
    _breadcrumbs,
    _breadcrumbs_nav,
    _format_date,
    _iso_date,
    _link,
    _links_list,
    _seo_chart_figure,
    _site_json_ld,
    build_document,
)

_MONTH_WINDOW = 12
_YEARS_LINKS_MAX = 10

_EN_MONTHS = (
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


def _month_label(year: int, month: int) -> str:
    """«июль 2025» / «July 2025» — по активной локали."""
    return format_month_year(date(year, month, 1))


def _month_label_en(year: int, month: int) -> str:
    """«July 2025» — явный EN-вариант для title независимо от локали."""
    return f"{_EN_MONTHS[month]} {year}"


def _og_month_path(code: str, year: int, month: int) -> str:
    """OG-картинка месячного среза: /og/russia/cpi/2025-07.png."""
    return paths.og_indicator(paths.RUSSIA, code, f"{int(year)}-{int(month):02d}")


def _prev_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


async def _month_last_values(
    db: AsyncSession, indicator_id: int,
) -> dict[tuple[int, int], tuple[float, date]]:
    """Последняя точка каждого месяца ряда (дельты, окно соседей, список лет)."""
    result = await db.execute(
        select(IndicatorData.date, IndicatorData.value)
        .where(IndicatorData.indicator_id == indicator_id)
        .order_by(IndicatorData.date)
    )
    by_month: dict[tuple[int, int], tuple[float, date]] = {}
    for dt, raw in result.all():
        if dt is None or raw is None:
            continue
        by_month[(dt.year, dt.month)] = (float(raw), dt)
    return by_month


def _neighbor_month_window(
    by_month: dict[tuple[int, int], tuple[float, date]],
    year: int, month: int, *, size: int = _MONTH_WINDOW,
) -> list[tuple[int, int]]:
    """Окно из `size` существующих месяцев ряда, центрированное на текущем."""
    keys = sorted(by_month)
    current = (year, month)
    if current in by_month:
        idx = keys.index(current)
    else:
        idx = min(
            range(len(keys)),
            key=lambda i: abs((keys[i][0] - year) * 12 + keys[i][1] - month),
        )
    half = size // 2
    start = max(0, idx - half)
    end = min(len(keys), start + size)
    start = max(0, end - size)
    return keys[start:end]


def _format_delta(
    shown: float | None, base_shown: float | None, code: str, unit: str,
) -> str:
    """Изменение показываемых величин: «+0,09 п.п.» (CPI) / «−1,2 % (+1,5 %)».

    Для CPI-семейства разность двух изменений цен — это процентные пункты,
    а не «%», и процент от разности изменений экономике неинтересен.
    """
    from app.services.locale import get_locale

    if shown is None or base_shown is None:
        return "нет данных"
    cpi_mode = is_cpi_index(code)
    if cpi_mode:
        delta = format_number_ru(shown - base_shown, signed=True)
        pp = " pp" if get_locale() == "en" else " п.п."
        return f"{delta}{pp}"
    unit_suffix = f" {escape(unit)}" if unit else ""
    delta = format_number_ru(shown - base_shown, signed=True)
    if base_shown != 0:
        pct = format_number_ru(
            round((shown - base_shown) / abs(base_shown) * 100.0, 2), signed=True,
        )
        return f"{delta}{unit_suffix} ({pct} %)"
    return f"{delta}{unit_suffix}"


def _value_line(code: str, unit: str, value_date: date, shown: float | None) -> str:
    """«Значение на 31 июля 2025: +0,17 %» / «Value as of July 31, 2025: +0.17 %»."""
    from app.services.locale import get_locale

    en = get_locale() == "en"
    cpi_mode = is_cpi_index(code)
    unit_suffix = f" {escape(unit)}" if unit and not cpi_mode else (" %" if cpi_mode else "")
    shown_text = format_number_ru(shown, signed=cpi_mode) if shown is not None else (
        "no data" if en else "нет данных"
    )
    if en:
        return f"Value as of {_format_date(value_date)}: {shown_text}{unit_suffix}"
    return f"Значение на {_format_date(value_date)}: {shown_text}{unit_suffix}"


def _month_trail(
    code: str,
    category,
    cat_name: str | None,
    name: str,
    canonical_path: str,
    month_label: str,
) -> list[tuple[str, str]]:
    """Крошки: Главная / Россия / [Категория] / Показатель / Месяц.

    Для мировых рыночных рядов узел «Россия» опускается — как на годовом
    лендинге (ряд не относится к российской статистике).
    """
    indicator_path = paths.russia_indicator(code)
    category_path = paths.russia_category(category.slug) if category else None
    trail_fn = (
        crumbs.global_market_indicator_trail
        if is_global_market_indicator(code)
        else crumbs.russia_indicator_trail
    )
    items = trail_fn(cat_name, category_path, name, indicator_path)
    items.append((canonical_path, month_label))
    return items


def _category_for(api_category: str | None):
    from app.services.seo_content import CATEGORY_META
    from app.services.seo_i18n import get_category_seo

    if not api_category:
        return None
    for slug, category in CATEGORY_META.items():
        if category.api_category == api_category:
            return get_category_seo(slug) or category
    return None


async def render_indicator_month_html(
    code: str, year: int, month: int, db: AsyncSession,
) -> tuple[int, str]:
    """Месячная landing-страница `/russia/indicator/{code}/{year}-{mm}`."""
    from app.services.locale import get_locale, in_language
    from app.services.seo_i18n import (
        get_category_seo,
        public_indicator_fields,
        translate_source,
    )

    year, month = int(year), int(month)
    if not 1 <= month <= 12:
        return 404, "Not found"

    q = await db.execute(
        select(Indicator).where(
            Indicator.code == code,
            Indicator.is_active.is_(True),
            Indicator.is_listed.is_(True),
        )
    )
    indicator = q.scalar_one_or_none()
    if not indicator:
        return 404, "Not found"
    # Месячный срез имеет смысл только у monthly-рядов: карточка «за июль»
    # у дневного/недельного ряда вводила бы в заблуждение (страницы не
    # создаём — см. docstring модуля).
    if not (indicator.frequency or "").lower().startswith("month"):
        return 404, "Not found"

    rows_q = await db.execute(
        select(IndicatorData)
        .where(
            IndicatorData.indicator_id == indicator.id,
            func.extract("year", IndicatorData.date) == year,
            func.extract("month", IndicatorData.date) == month,
        )
        .order_by(IndicatorData.date)
    )
    rows = list(rows_q.scalars().all())
    if not rows:
        return 404, "Not found"

    en = get_locale() == "en"
    fields = public_indicator_fields(
        code,
        name_ru=indicator.name,
        name_en=indicator.name_en,
        unit_ru=indicator.unit,
    )
    name = fields["name"] or indicator.name
    unit = fields["unit"] or (indicator.unit or "")
    source = translate_source(indicator.source) or indicator.source
    category = _category_for(indicator.category)
    cat_name = None
    if category is not None:
        en_cat = get_category_seo(category.slug)
        cat_name = (en_cat.name if en_cat else None) or category.name

    first, last = rows[0], rows[-1]
    cpi_mode = is_cpi_index(code)
    month_label = _month_label(year, month)
    month_label_en = _month_label_en(year, month)
    trail_label = month_label_en if en else month_label
    canonical_path = paths.indicator_month(paths.RUSSIA, code, year, month)
    trail = _month_trail(code, category, cat_name, name, canonical_path, trail_label)

    by_month = await _month_last_values(db, indicator.id)
    prev_year, prev_month = _prev_month(year, month)
    prev_shown = (
        display_value(code, by_month[(prev_year, prev_month)][0])
        if (prev_year, prev_month) in by_month else None
    )
    yoy_shown = (
        display_value(code, by_month[(year - 1, month)][0])
        if (year - 1, month) in by_month else None
    )
    shown_last = display_value(code, last.value)

    # RU-месяц в H1 — именительный падеж; EN — свой словарь месяцев.
    if en:
        title = f"{name} in Russia — {month_label_en}, monthly value"
        h1 = f"{name} in Russia, {month_label_en}"
        desc = (
            f"{name} in Russia for {month_label_en}: monthly value, change versus "
            f"the previous month and the same month a year earlier. "
            f"Official data — {source}."
        )
    else:
        title = f"{name} — {month_label}"
        h1 = f"{name} — {month_label}"
        desc = (
            f"{name} за {month_label} года: значение, изменение к предыдущему "
            f"месяцу и к тому же месяцу прошлого года. "
            f"Официальные данные — {source}."
        )

    mom_label = "Change versus previous month" if en else "Изменение к предыдущему месяцу"
    prev_key = _month_label(prev_year, prev_month)
    yoy_label = (
        f"Change versus {month_label_en.split()[0]} {year - 1}"
        if en
        else f"Изменение к тому же месяцу прошлого года ({_month_label(year - 1, month)})"
    )
    lead_lines = [_value_line(code, unit, last.date, shown_last)]
    if prev_shown is not None:
        lead_lines.append(
            f"{mom_label} ({prev_key}): {_format_delta(shown_last, prev_shown, code, unit)}"
        )
    if yoy_shown is not None:
        lead_lines.append(f"{yoy_label}: {_format_delta(shown_last, yoy_shown, code, unit)}")
    lead_items = "".join(f"<li>{escape(line)}</li>" for line in lead_lines)
    lead_h2 = f"Value for {month_label_en}" if en else f"Значение за {month_label}"

    def value_heading() -> str:
        if cpi_mode:
            return "Price change, %" if en else "Изменение цен, %"
        if unit:
            return f"Value, {escape(unit)}" if en else f"Значение, {escape(unit)}"
        return "Value" if en else "Значение"

    # Таблица: все точки месяца (daily — до 31 строки); одна точка за месяц —
    # окно соседних месяцев вместо бессмысленной таблицы из одной строки.
    if len(rows) == 1:
        window = _neighbor_month_window(by_month, year, month)
        neighbor_rows = "".join(
            (
                f"<tr><td><strong>{escape(_month_label(y, m))}</strong></td>"
                f"<td><strong>{escape(format_number_ru(display_value(code, by_month[(y, m)][0]), signed=cpi_mode))}</strong></td></tr>"
                if (y, m) == (year, month)
                else (
                    f"<tr><td>{escape(_month_label(y, m))}</td>"
                    f"<td>{escape(format_number_ru(display_value(code, by_month[(y, m)][0]), signed=cpi_mode))}</td></tr>"
                )
            )
            for y, m in window
        )
        data_section = f"""<section><h2>{escape("Neighboring months" if en else "Динамика соседних месяцев")}</h2>
<table><thead><tr><th>{escape("Month" if en else "Месяц")}</th><th>{value_heading()}</th></tr></thead>
<tbody>{neighbor_rows}</tbody></table></section>"""
    else:
        data_rows = "".join(
            f"<tr><td>{escape(_format_date(r.date))}</td>"
            f"<td>{escape(format_number_ru(display_value(code, r.value), signed=cpi_mode))}</td></tr>"
            for r in rows
        )
        all_h2 = f"All values for {month_label_en}" if en else f"Все значения за {month_label}"
        data_section = f"""<section><h2>{escape(all_h2)}</h2>
<table><thead><tr><th>{escape("Date" if en else "Дата")}</th><th>{value_heading()}</th></tr></thead>
<tbody>{data_rows}</tbody></table></section>"""

    # «Другие месяцы этого года» — только реально существующие месяцы ряда.
    months_in_year = sorted(m for y, m in by_month if y == year)
    month_links = _links_list(
        tuple(
            (paths.indicator_month(paths.RUSSIA, code, year, m), _month_label(year, m))
            for m in months_in_year
            if m != month
        )
    )
    other_months_section = ""
    if month_links:
        other_months_h2 = f"Other months of {year}" if en else f"Другие месяцы {year} года"
        other_months_section = (
            f"<section><h2>{escape(other_months_h2)}</h2>{month_links}</section>"
        )

    # «Другие годы» — годовые лендинги: до 10 последних лет плюс текущий.
    years = sorted({y for y, _m in by_month})
    year_link_tpl = "{name} in {year}" if en else "{name} в {year} году"
    year_links = _links_list(
        tuple(
            (paths.indicator_year(paths.RUSSIA, code, y), year_link_tpl.format(name=name, year=y))
            for y in years[-(_YEARS_LINKS_MAX + 1):]
        )
    )
    other_years_h2 = "Other years" if en else "Другие годы"

    chart_caption = (
        f"{name} in {month_label_en} — monthly value. Source: {source}. forecasteconomy.com"
        if en
        else f"{name} за {month_label} года — значение за месяц. Источник: {source}. forecasteconomy.com"
    )
    chart_alt = (
        f"{name} in {month_label_en} — chart with the monthly value, source {source}"
        if en
        else f"{name} за {month_label} года — график со значением за месяц, источник {source}"
    )
    image_caption = (
        f"{name} in {month_label_en} — monthly value and context"
        if en
        else f"{name} за {month_label} года — значение и контекст"
    )
    card_path = paths.russia_indicator(code)
    chart_h2 = "Interactive chart" if en else "График и прогноз"
    chart_p = (
        "Full history, interactive chart and forecast — on the {_link} page."
        if en
        else "Полная история, интерактивный график и прогноз — на странице {_link}."
    ).format(_link=_link(card_path, name))

    og_path = _og_month_path(code, year, month)
    body = f"""<main class="seo-page">
{_breadcrumbs_nav(trail)}
<h1>{escape(h1)}</h1>
<p>{escape(desc)}</p>
{_seo_chart_figure(og_path, chart_alt, chart_caption, href=card_path)}
<section><h2>{escape(lead_h2)}</h2>
<ul>
{lead_items}
</ul></section>
{data_section}
<section><h2>{escape(chart_h2)}</h2><p>{chart_p}</p></section>
{other_months_section}
<section><h2>{escape(other_years_h2)}</h2>{year_links}</section>
</main>"""

    jsonld_name = (
        f"{name} in Russia — {month_label_en}" if en else f"{name} — {month_label} {year}"
    )
    json_ld = [
        _site_json_ld(),
        _breadcrumbs(trail),
        {
            "@context": "https://schema.org",
            "@type": "Dataset",
            "name": jsonld_name,
            "description": desc,
            "url": _absolute(canonical_path),
            "inLanguage": in_language(),
            "creator": {"@type": "Organization", "name": source},
            # Месяц-срез: покрытие — от первой до последней точки месяца.
            "temporalCoverage": f"{_iso_date(first.date)}/{_iso_date(last.date)}",
            "variableMeasured": name,
            "image": _absolute(og_path),
        },
        {
            "@context": "https://schema.org",
            "@type": "ImageObject",
            "contentUrl": _absolute(og_path),
            "url": _absolute(og_path),
            "caption": image_caption,
            "width": 1200,
            "height": 630,
            "representativeOfPage": True,
        },
    ]
    keywords = (
        f"{name} {month_label_en}, {name} {year}"
        if en
        else f"{name} {month_label} {year}, {name} за {month_label} {year}, {indicator.seo_keywords or name}"
    )
    html = await build_document(
        title=title,
        description=desc,
        canonical_path=canonical_path,
        body=body,
        json_ld=json_ld,
        keywords=keywords,
        og_image=_absolute(og_path),
        include_app=False,
    )
    return 200, html

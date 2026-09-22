"""SSR-рендер годовых лендингов мира: /{country}/indicator/{code}/{year}.

Мировой аналог ``render_indicator_year_html`` (Россия) из seo_renderer.py.
include_app=False — у SPA-роутера нет такого маршрута. Данные — WorldDataPoint;
помощники страны/единиц/источника переиспользуются импортом из seo_world.py,
разметка и каркас документа — из seo_renderer.py (ADR-0003).
Прогнозов у мировых рядов нет, поэтому секция перехода ведёт только на живую
карточку с полной историей. Внутренние идентификаторы наборов наружу не выдаём.
"""

from __future__ import annotations

from datetime import date
from html import escape
from statistics import fmean

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.eurostat_listing import normalize_frequency
from app.models import WorldIndicator, WorldDataPoint
from app.services import breadcrumbs as crumbs
from app.services import site_paths as paths
from app.services.display import (
    display_value_text,
    format_number_ru,
    localize_unit,
    today_msk,
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
    fast_answer_block,
    _site_json_ld,
    build_document,
    neighbor_year_window,
    year_history_position_lines,
)

_NEIGHBOR_WINDOW = 10
_OTHER_YEARS_MAX = 15


def _observation_summary(
    rows: list[tuple[date, float]], frequency: str, unit: str, *, en: bool
) -> tuple[str, str]:
    """Без метаданных об агрегации world описываем наблюдения, не итог."""
    if len(rows) == 1:
        label = (
            ("Annual value" if en else "Годовое значение")
            if frequency == "annual"
            else ("Published observation" if en else "Опубликованное наблюдение")
        )
        value = rows[0][1]
    else:
        label = (
            "Mean of published observations" if en
            else "Среднее по опубликованным наблюдениям"
        )
        value = fmean(v for _d, v in rows)
    return label, display_value_text(None, value, unit or None)


def _coverage_note(
    rows: list[tuple[date, float]], frequency: str, *, en: bool
) -> str:
    """Календарное покрытие M/Q проверяем по периодам, не числу строк."""
    dates = [d for d, _v in rows]
    if frequency == "annual" and len(rows) == 1:
        return ""
    period_size = {"monthly": 1, "quarterly": 3}.get(frequency)
    if period_size:
        expected = 12 // period_size
        periods = {(d.month - 1) // period_size for d in dates}
        incomplete = len(periods) < expected
        unit = ("months" if frequency == "monthly" else "quarters") if en else (
            "месяцев" if frequency == "monthly" else "кварталов"
        )
        prefix = (
            ("Incomplete year: " if en else "Неполное покрытие года: ")
            if incomplete else ("Coverage: " if en else "Покрытие: ")
        )
        coverage = prefix + (
            f"{len(periods)} of {expected} {unit}." if en
            else f"{len(periods)} из {expected} {unit}."
        )
    else:
        coverage = (
            f"Published observations: {len(rows)}. Full-year coverage is not confirmed."
            if en else f"Опубликовано наблюдений: {len(rows)}. Полнота покрытия года не подтверждена."
        )
    bounds = (
        f" Observation dates: {_format_date(dates[0])} — {_format_date(dates[-1])}."
        if en else f" Даты наблюдений: {_format_date(dates[0])} — {_format_date(dates[-1])}."
    )
    method = (
        " No annual total is calculated; the arithmetic mean of available observations "
        "is not an official annual value."
        if en else " Годовой итог не рассчитывается; среднее арифметическое доступных "
        "наблюдений не является официальным годовым значением."
    )
    return coverage + bounds + method


def _title_desc(
    *,
    name: str,
    country_name: str,
    year: int,
    frequency: str,
    n_rows: int,
    current_year: bool,
    period_note: str,
    summary_label: str,
    summary_text: str,
    source: str,
    en: bool,
    yt,
) -> tuple[str, str]:
    """Заголовок и description по числу точек года (зеркало РФ-веток)."""
    freq = (frequency or "").lower()
    summary_bit = summary_text.rstrip(".")
    if en:
        label_out = summary_label
    else:
        label_out = summary_label.lower()

    if en:
        if n_rows > 1:
            title = f"{name} in {country_name}, {year} — published observations"
            desc = (
                f"{name} in {country_name}, {year}{period_note}: {n_rows} observations, "
                f"{label_out} — {summary_bit}. Official data — {source}."
            )
            return title, desc
        if freq == "annual":
            title_key = "title_annual_current" if current_year else "title_annual"
        elif current_year:
            title_key = "title_ytd"
        else:
            title_key = "title_single"
        title = yt(title_key).format(name=name, year=year, country=country_name)
        desc_key = "desc_single" if freq == "annual" and n_rows == 1 else "desc_multi"
        desc = yt(desc_key).format(
            name=name,
            year=year,
            country=country_name,
            period_note=period_note,
            summary_label=label_out,
            summary_bit=summary_bit,
            source=source,
            n=n_rows,
        )
        return title, desc

    name = f"{name} в {country_name}"
    if freq == "annual" and n_rows == 1:
        title = (
            f"{name} в {year} году — актуальное годовое значение"
            if current_year
            else f"{name} в {year} году — значение и динамика"
        )
        desc = (
            f"{name} в {year} году{period_note}: {label_out} — {summary_bit}. "
            f"Сравнение с прошлым годом и положение в истории ряда. "
            f"Официальные данные — {source}."
        )
        return title, desc
    if current_year:
        title = f"{name} в {year} году — данные с начала года"
    elif n_rows == 1:
        title = f"{name} в {year} году — значение и динамика"
    elif freq == "quarterly":
        title = f"{name} в {year} году — наблюдения по кварталам"
    elif freq == "weekly":
        title = f"{name} в {year} году — наблюдения по неделям"
    elif freq == "daily":
        title = f"{name} в {year} году — дневные наблюдения"
    else:
        title = f"{name} в {year} году — наблюдения по месяцам"
    desc = (
        f"{name} в {year} году{period_note}: {n_rows} наблюдений, "
        f"{label_out} — {summary_bit}. Официальные данные — {source}."
    )
    return title, desc


async def render_world_indicator_year_html(
    slug: str, code: str, year: int, db: AsyncSession
) -> tuple[int, str]:
    """Годовой лендинг мира — чистый SSR без React-bundle."""
    from app.services.locale import get_locale, in_language
    from app.services.seo_i18n import year_template as yt

    from app.services.seo_world import (
        _country,
        _country_label,
        _display_name,
        _prep,
        _source_label,
        _unit_of,
    )

    country = await _country(db, slug)
    if country is None:
        return 404, "Not found"

    indicator = (
        await db.execute(
            select(WorldIndicator).where(
                WorldIndicator.country_id == country.id,
                WorldIndicator.code == code,
                WorldIndicator.is_listed.is_(True),
            )
        )
    ).scalar_one_or_none()
    if indicator is None:
        return 404, "Not found"

    rows = (
        await db.execute(
            select(WorldDataPoint.date, WorldDataPoint.value)
            .where(WorldDataPoint.indicator_id == indicator.id)
            .order_by(WorldDataPoint.date)
        )
    ).all()
    if not rows:
        return 404, "Not found"
    series = [(d, float(v)) for d, v in rows]

    year_rows = [pair for pair in series if pair[0].year == year]
    if not year_rows:
        return 404, "Not found"

    loc = get_locale()
    en = loc == "en"
    prep = _prep(country)
    country_label = _country_label(country)
    place = country_label if en else prep
    display = _display_name(indicator)
    unit = _unit_of(indicator)
    # Русская каноническая единица → локализованная для показа (EN: pp вместо п.п.).
    shown_unit = ((localize_unit(unit) or unit) if unit else "") if en else unit
    unit_sfx = f" {shown_unit}" if shown_unit else ""
    source = _source_label(indicator.source, indicator.provider)
    frequency = normalize_frequency(indicator.frequency) or ""
    values = [v for _d, v in year_rows]
    first_date, first_value = year_rows[0]
    last_date, last_value = year_rows[-1]
    current_year = today_msk().year == year
    period_note = (
        (yt("period_note_ytd") or " (данные с начала года по {date})").format(
            date=_format_date(last_date)
        )
        if current_year
        else ""
    )

    # Последняя точка каждого года по всей истории: база для сравнения годов
    # (аналог yearly_last_points РФ; считается inline — у мировой модели
    # нет идентичности с Indicator.id, которую та функция ожидает).
    last_by_year: dict[int, tuple[float, date]] = {}
    for d, v in series:
        known = last_by_year.get(d.year)
        if known is None or d >= known[1]:
            last_by_year[d.year] = (v, d)
    series_lp = [(y, v, d) for y, (v, d) in sorted(last_by_year.items())]
    prev_year = year - 1 if (year - 1) in last_by_year else None
    prev_value = last_by_year[year - 1][0] if prev_year is not None else None
    neighbors = neighbor_year_window(series_lp, year, size=_NEIGHBOR_WINDOW)
    navigation = neighbor_year_window(series_lp, year, size=_OTHER_YEARS_MAX - 1)
    other_years = sorted(
        ({y for y, _v, _d in navigation} | {series_lp[0][0], series_lp[-1][0]}) - {year}
    )

    summary_label, summary_text = _observation_summary(
        year_rows, frequency, shown_unit, en=en
    )
    coverage_note = _coverage_note(year_rows, frequency, en=en)
    n_rows = len(year_rows)
    single_point = n_rows == 1 and frequency == "annual"
    if current_year:
        summary_label = (
            yt("summary_as_of") or "{label} (на {date})"
        ).format(label=summary_label, date=_format_date(last_date))

    title, desc = _title_desc(
        name=display,
        country_name=country_label if en else prep,
        year=year,
        frequency=frequency,
        n_rows=n_rows,
        current_year=current_year,
        period_note=period_note,
        summary_label=summary_label,
        summary_text=summary_text,
        source=source,
        en=en,
        yt=yt,
    )
    h1_text = title.split(" — ")[0]

    og_path = paths.og_indicator(slug, code, year)
    canonical_path = paths.indicator_year(slug, code, year)
    card_path = paths.indicator(slug, code)

    if en:
        value_head = (
            (yt("th_value_unit") or "Value, {unit}").format(unit=shown_unit)
            if shown_unit
            else (yt("th_value") or "Value")
        )
        th_date = yt("th_date") or "Date"
    else:
        value_head = f"Значение, {unit}" if unit else "Значение"
        th_date = "Дата"

    if single_point:
        # Одно наблюдение за год: изменение к прошлому году считаем прямой
        # разницей (мировые коды не входят в российские семействы display-
        # адаптера; CPI-режим не применяется). Прошлогодняя точка — последняя
        # строго до 1 января текущего запрошенного года.
        if current_year:
            totals_head = (
                yt("h2_single_as_of") or "{name} в {year} году: данные на {date}"
            ).format(name=display, year=year, date=_format_date(last_date))
        else:
            totals_head = (yt("h2_single") or "{name} в {year} году").format(
                name=display, year=year
            )
        change_lines: list[str] = [
            (yt("change_value") or "Значение: {value}").format(
                value=f"{format_number_ru(last_value)}{unit_sfx}"
            )
        ]
        if prev_value is None or prev_year is None:
            change_lines.append(
                yt("change_no_prev")
                or "Изменение к предыдущему году: нет сопоставимого значения"
            )
        else:
            delta = last_value - prev_value
            abs_text = format_number_ru(round(delta, 4), signed=True)
            if prev_value == 0:
                pct_text = (
                    yt("change_zero_base") or "не рассчитывается (база равна нулю)"
                )
            else:
                pct = round((delta / abs(prev_value)) * 100.0, 2)
                pct_text = f"{format_number_ru(pct, signed=True)} %"
            change_lines.append(
                (yt("change_vs") or "Изменение к {prev_year} году: {abs}{unit} ({pct})").format(
                    prev_year=prev_year, abs=abs_text, unit=unit_sfx, pct=pct_text,
                )
            )
        history_lines = year_history_position_lines(
            year=year,
            value=last_value,
            series=series_lp,
            code=None,
            unit=shown_unit,
        )
        context_items = "".join(
            f"<li>{escape(line)}</li>" for line in (change_lines + history_lines)
        )
        context_items += (
            f"<li>{escape((yt('li_value_date') or 'Дата значения: {date}').format(date=_format_date(last_date)))}</li>"
            f"<li>{escape((yt('li_source') or 'Источник: {source}').format(source=source))}</li>"
        )
        neighbor_rows = "".join(
            (
                f"<tr><td><strong>{y}</strong></td>"
                f"<td><strong>{escape(format_number_ru(v))}</strong></td></tr>"
                if y == year
                else f"<tr><td>{y}</td><td>{escape(format_number_ru(v))}</td></tr>"
            )
            for y, v, _d in neighbors
        )
        neighbors_h2 = yt("h2_neighbors") or "Динамика соседних лет"
        th_year = yt("th_year") or "Год"
        data_section = f"""<section><h2>{escape(totals_head)}</h2>
<ul>
{context_items}
</ul></section>
<section><h2>{escape(neighbors_h2)}</h2>
<table><thead><tr><th>{escape(th_year)}</th><th>{escape(value_head)}</th></tr></thead>
<tbody>{neighbor_rows}</tbody></table></section>"""
        chart_caption = (
            yt("chart_caption_single")
            or "{name} в {year} году — значение в контексте соседних лет. Источник: {source}. forecasteconomy.com"
        ).format(name=display, year=year, source=source)
        chart_alt = (
            yt("chart_alt_single")
            or "{name} в {year} году — график соседних лет, {summary_label} {summary_text}, источник {source}"
        ).format(
            name=display,
            year=year,
            summary_label=summary_label if en else summary_label.lower(),
            summary_text=summary_text,
            source=source,
        )
        image_caption = (
            yt("image_caption_single") or "{name} в {year} году — значение и динамика"
        ).format(name=display, year=year)
    else:
        if current_year:
            totals_head = (
                yt("h2_ytd") or "{name} в {year} году: данные с начала года"
            ).format(name=display, year=year)
        else:
            totals_head = (
                f"Published observations in {year}" if en
                else f"Опубликованные наблюдения за {year} год"
            )
        range_label = yt("range_minmax") or "Минимум и максимум"
        vmin, vmax = min(values), max(values)
        data_rows = "".join(
            f"<tr><td>{escape(_format_date(d))}</td>"
            f"<td>{escape(format_number_ru(v))}</td></tr>"
            for d, v in year_rows
        )
        li_start = (
            "First observation: {value} ({date})" if en
            else "Первое наблюдение: {value} ({date})"
        ).format(
            value=display_value_text(None, first_value, shown_unit),
            date=_format_date(first_date),
        )
        li_end = (
            "Last observation: {value} ({date})" if en
            else "Последнее наблюдение: {value} ({date})"
        ).format(
            value=display_value_text(None, last_value, shown_unit),
            date=_format_date(last_date),
        )
        all_h2 = (yt("h2_all_values") or "Все значения за {year} год").format(year=year)
        data_section = f"""<section><h2>{escape(totals_head)}</h2>
<ul>
<li>{escape(summary_label)}: {escape(summary_text)}</li>
<li>{escape(li_start)}</li>
<li>{escape(li_end)}</li>
<li>{escape(range_label)}: {escape(format_number_ru(vmin))} … {escape(format_number_ru(vmax))}{escape(unit_sfx)}</li>
<li>{escape((yt('li_obs') or 'Количество наблюдений: {n}').format(n=n_rows))}</li>
<li>{escape((yt('li_source') or 'Источник: {source}').format(source=source))}</li>
</ul></section>
<section><h2>{escape(all_h2)}</h2><table><thead><tr><th>{escape(th_date)}</th><th>{escape(value_head)}</th></tr></thead><tbody>{data_rows}</tbody></table></section>"""
        chart_caption = (
            yt("chart_caption_multi")
            or "{name} в {year} году — график динамики. Источник: {source}. forecasteconomy.com"
        ).format(name=display, year=year, source=source)
        chart_alt = (
            yt("chart_alt_multi")
            or "{name} в {year} году — график, {summary_label} {summary_text}, источник {source}"
        ).format(
            name=display,
            year=year,
            summary_label=summary_label if en else summary_label.lower(),
            summary_text=summary_text,
            source=source,
        )
        image_caption = (
            f"{display}, {year} — chart of published observations" if en
            else f"{display} в {year} году — график опубликованных наблюдений"
        )

    year_link_tpl = yt("year_link") or "{name} в {year} году"
    year_links_html = _links_list(
        tuple(
            (paths.indicator_year(slug, code, y), year_link_tpl.format(name=display, year=y))
            for y in other_years
        )
    )
    other_years_h2 = yt("h2_other_years") or "Другие годы"

    # Переход на живую карточку: полная история и интерактивные режимы.
    # Прогнозов у мировых рядов нет — формулировка честная, без обещания прогноза.
    if en:
        card_h2 = "Full history and interactive chart"
        card_p_tpl = "Complete series for {place} — on the {_link} page."
    else:
        card_h2 = "Полная история и интерактивный график"
        card_p_tpl = "Весь ряд данных по показателю в {place} — на странице {_link}."
    card_p = card_p_tpl.format(place=escape(place), _link=_link(card_path, display))

    trail = crumbs.world_indicator_trail(
        country_label, paths.country(slug), display, card_path,
    )
    if en:
        last_crumb = f"{display} in {country_label}, {year}"
    else:
        last_crumb = f"{display} {year}"
    trail.append((canonical_path, last_crumb))

    body = f"""<main class="seo-page">
{_breadcrumbs_nav(trail)}
{fast_answer_block(eyebrow=summary_label, title=h1_text, value=summary_text, note=desc)}
{f'<p>{escape(coverage_note)}</p>' if coverage_note else ''}
{_seo_chart_figure(og_path, chart_alt, chart_caption, href=card_path, loading="eager")}
{data_section}
<section><h2>{escape(card_h2)}</h2><p>{card_p}</p></section>
<section><h2>{escape(other_years_h2)}</h2>{year_links_html}</section>
</main>"""

    jsonld_name = (yt("jsonld_name") or "{name} — {year} год").format(name=display, year=year)
    coverage_end = _iso_date(last_date)
    spatial = country.name_en if en else country.name_ru
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
            "license": "https://creativecommons.org/licenses/by/4.0/",
            "spatialCoverage": spatial,
            "temporalCoverage": f"{_iso_date(first_date)}/{coverage_end}",
            "variableMeasured": display,
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
    keywords = f"{display.lower()} {year}"

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

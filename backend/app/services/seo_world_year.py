"""SSR-рендер годовых лендингов мира: /{country}/indicator/{code}/{year}.

Мировой аналог ``render_indicator_year_html`` (Россия) из seo_renderer.py.
include_app=False — у SPA-роутера нет такого маршрута. Данные — WorldDataPoint;
помощники страны/единиц/источника переиспользуются импортом из seo_world.py,
разметка и каркас документа — из seo_renderer.py (ADR-0003).
Прогнозов у мировых рядов нет, поэтому секция перехода ведёт только на живую
карточку с полной историей. Внутренние идентификаторы наборов наружу не выдаём.
"""

from __future__ import annotations

from collections.abc import Callable

from datetime import date
from html import escape
from statistics import fmean

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.eurostat_listing import normalize_frequency
from app.data.eurostat_titles_ru import in_place
from app.models import WorldIndicator, WorldDataPoint
from app.services import breadcrumbs as crumbs
from app.services import site_paths as paths
from app.services.display import (
    display_value_text,
    localize_unit,
    today_msk,
)
from app.services import seo_year_ui as ui
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
    rows: list[tuple[date, float]], frequency: str, unit: str, *, en: bool,
    value_fmt: Callable[[float], str] | None = None,
) -> tuple[str, str]:
    """Без метаданных об агрегации world описываем наблюдения, не итог.

    ``value_fmt`` — число с единицей по правилу ряда (14.11.2026); без него — прежний
    ``display_value_text`` с полной единицей.
    """
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
    if value_fmt is not None:
        return label, value_fmt(value)
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
    range_note: str = "",
) -> tuple[str, str]:
    """Заголовок и description по числу точек года (зеркало РФ-веток)."""
    freq = (frequency or "").lower()
    summary_bit = summary_text.rstrip(".")
    if en:
        label_out = summary_label
    else:
        label_out = summary_label.lower()

    if en:
        # Description (14.11.2026): показатель, страна, год и значение — в первом предложении; источник
        # последним (английский хост держит description ≤ 160 знаков, хвост отбрасывается первым).
        if n_rows > 1:
            title = f"{name} in {country_name}, {year} — published observations"
            desc = (
                f"{name} in {country_name}, {year}{period_note}: average of {n_rows} observations "
                f"— {summary_bit}.{range_note} Source: {source}."
            )
            return title, desc
        if freq == "annual":
            title_key = "title_annual_current" if current_year else "title_annual"
        elif current_year:
            title_key = "title_ytd"
        else:
            title_key = "title_single"
        title = yt(title_key).format(name=name, year=year, country=country_name)
        # Общие шаблоны desc_single/desc_multi (их делят страницы России) не знают страны: у стран мира
        # страна в description обязательна — своя строка.
        desc = (
            f"{name} in {country_name}, {year}{period_note}: {summary_bit}. "
            f"Change on the previous year and place in the series history. Source: {source}."
        )
        return title, desc

    # country_name — предложный падеж без предлога; «в/во/на» ставит in_place
    name = f"{name} {in_place(country_name)}"
    if freq == "annual" and n_rows == 1:
        title = (
            f"{name} в {year} году — актуальное годовое значение"
            if current_year
            else f"{name} в {year} году — значение и динамика"
        )
        desc = (
            f"{name} в {year} году{period_note}: {label_out} — {summary_bit}. "
            f"Сравнение с прошлым годом и положение в истории показателя. "
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
        f"{label_out} — {summary_bit}.{range_note} Официальные данные — {source}."
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
        _in,
        _prep,
        _source_label,
        _unit_of,
    )

    country = await _country(db, slug)
    if country is None:
        return 404, "Not found"

    from app.data.legacy_redirects import is_retired_world_hicp

    indicator = (
        await db.execute(
            select(WorldIndicator).where(
                WorldIndicator.country_id == country.id,
                WorldIndicator.code == code,
            )
        )
    ).scalar_one_or_none()
    if indicator is None or not (indicator.is_listed or is_retired_world_hicp(slug, code)):
        return 404, "Not found"

    # Год без данных (перебор лет роботами) отвечает 404 по одному запросу по индексу (indicator_id, date), без чтения
    # всего ряда: 404 не кэшируется, и раньше каждый такой адрес читал ряд целиком (у дневных рядов — тысячи строк).
    if 1 <= year < 9999:
        has_year = (
            await db.execute(
                select(WorldDataPoint.date)
                .where(
                    WorldDataPoint.indicator_id == indicator.id,
                    WorldDataPoint.date >= date(year, 1, 1),
                    WorldDataPoint.date < date(year + 1, 1, 1),
                )
                .limit(1)
            )
        ).first()
        if has_year is None:
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
    prep = _prep(country)  # «Франции» — без предлога
    in_country = _in(country)  # «в Германии» / «во Франции» / «на Кипре»
    country_label = _country_label(country)
    place = country_label if en else in_country
    display = _display_name(indicator)
    unit = _unit_of(indicator)
    # Русская каноническая единица → локализованная для показа (EN: pp вместо п.п.).
    shown_unit = ((localize_unit(unit) or unit) if unit else "") if en else unit
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
    other_years = sorted({y for y, _v, _d in series_lp if y != year and paths.is_public_year(y)})

    # Точность и единица (14.11.2026): точность всего ряда по правилу SPA (display.world_series_digits),
    # справа от числа — короткая единица страницы (seo_world._unit_sfx_of: «7,71 %», у индексов — без
    # единицы), а не полная («7,7092 изменение за год, %»). Полная единица остаётся в заголовке столбца.
    from app.services.display import format_fixed, world_series_digits
    from app.services.seo_world import _unit_sfx_of

    digits = world_series_digits(v for _d, v in series)
    if len(year_rows) > 1:
        # Среднее наблюдений года задаёт формат страницы вместе с рядом: «117,5» при целых данных → «112,0».
        digits = max(digits, world_series_digits([fmean(v for _d, v in year_rows)]))
    value_sfx = _unit_sfx_of(indicator)
    # Ряд в процентах (доля, изменение): разница — в п.п., «процент от процента» не считаем.
    pct_like = value_sfx.strip().startswith("%")

    def _plain(v: float) -> str:
        return format_fixed(v, digits)

    def _with_unit(v: float) -> str:
        return f"{_plain(v)}{value_sfx}"

    summary_label, summary_text = _observation_summary(
        year_rows, frequency, shown_unit, en=en, value_fmt=_with_unit,
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
        range_note=ui.year_range_note(
            values, shown_unit, en=en, last_is_partial=current_year, value_fmt=_with_unit,
        ) if n_rows > 2 else "",
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
            (yt("change_value") or "Значение: {value}").format(value=_with_unit(last_value))
        ]
        if prev_value is None or prev_year is None:
            change_lines.append(
                yt("change_no_prev")
                or "Изменение к предыдущему году: нет сопоставимого значения"
            )
        else:
            delta = last_value - prev_value
            abs_text = _plain(delta)
            if delta > 0 and abs_text.strip("0,.") != "":
                abs_text = f"+{abs_text}"
            if pct_like:
                change_lines.append(
                    (yt("change_vs_pp") or "Изменение к {prev_year} году: {abs}{unit}").format(
                        prev_year=prev_year, abs=abs_text, unit=" pp" if en else " п.п.",
                    )
                )
            else:
                if prev_value == 0:
                    pct_text = (
                        yt("change_zero_base") or "не рассчитывается (база равна нулю)"
                    )
                else:
                    pct = (delta / abs(prev_value)) * 100.0
                    pct_text = f"{'+' if pct > 0 else ''}{format_fixed(pct, 1)} %"
                change_lines.append(
                    (yt("change_vs") or "Изменение к {prev_year} году: {abs}{unit} ({pct})").format(
                        prev_year=prev_year, abs=abs_text, unit=value_sfx, pct=pct_text,
                    )
                )
        history_lines = year_history_position_lines(
            year=year,
            value=last_value,
            series=series_lp,
            code=None,
            unit=value_sfx.strip(),
            value_fmt=_plain,
        )
        facts = [
            *change_lines[1:],
            *history_lines,
            # У годового ряда дата значения — год, а не «1 января 2023» (14.11.2026).
            (yt("li_value_date") or "Дата значения: {date}").format(
                date=str(last_date.year) if frequency == "annual" else _format_date(last_date)
            ),
        ]
        neighbor_rows = [(str(y), _plain(v), y == year) for y, v, _d in neighbors]
        neighbors_h2 = yt("h2_neighbors") or "Динамика соседних лет"
        th_year = yt("th_year") or "Год"
        totals_section = f"<section><h2>{escape(totals_head)}</h2>{ui.year_facts(facts)}</section>"
        table_section = (
            f"<section><h2>{escape(neighbors_h2)}</h2>"
            f"{ui.year_values_table(neighbor_rows, head_date=th_year, head_value=value_head)}</section>"
        )
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
        vmin, vmax = min(values), max(values)
        (low_date, _low), (high_date, _high) = ui.extreme_dates(year_rows)
        cell_u = ui.cell_unit(shown_unit)
        _num = _plain

        totals_section = (
            f"<section><h2>{escape(totals_head)}</h2>"
            + ui.year_tiles((
                ("First value" if en else "Первое значение",
                 _num(first_value), shown_unit, _format_date(first_date)),
                ("Latest value" if en else "Последнее значение",
                 _num(last_value), shown_unit, _format_date(last_date)),
                ("Lowest" if en else "Минимум", _num(vmin), shown_unit, _format_date(low_date)),
                ("Highest" if en else "Максимум", _num(vmax), shown_unit, _format_date(high_date)),
            ))
            + "</section>"
        )
        table_rows = [
            (_format_date(d), ui.with_unit(_num(v), cell_u)) for d, v in year_rows
        ]
        all_h2 = (yt("h2_all_values") or "Все значения за {year} год").format(year=year)
        table_section = (
            f"<section><h2>{escape(all_h2)}</h2>"
            f"{ui.year_values_table(table_rows, head_date=th_date, head_value=value_head)}</section>"
        )
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
        card_p_tpl = "Весь ряд данных по показателю {place} — на странице {_link}."
    card_p = card_p_tpl.format(place=escape(place), _link=_link(card_path, display))

    trail = crumbs.world_indicator_trail(
        country_label, paths.country(slug), display, card_path,
    )
    if en:
        last_crumb = f"{display} in {country_label}, {year}"
    else:
        last_crumb = f"{display} {year}"
    trail.append((canonical_path, last_crumb))

    year_lead_text = ui.year_lead(
        n_rows=n_rows,
        year=year,
        source=source,
        current_year=current_year,
        last_date_text=_format_date(last_date),
        annual=frequency == "annual",
    )
    body = f"""<main class="seo-page">
{_breadcrumbs_nav(trail)}
{f'<p>{escape("Архивный ряд ГИПЦ: Евростат прекратил выпуск этого набора; показана сохранённая история." if not en else "Archived HICP series: Eurostat discontinued this dataset; its published history is retained.")}</p>' if is_retired_world_hicp(slug, code) else ''}
{fast_answer_block(eyebrow=summary_label, title=h1_text, value=summary_text, note=year_lead_text)}
{ui.collapsible_note("About data coverage" if en else "О полноте данных", coverage_note)}
{totals_section}
{_seo_chart_figure(og_path, chart_alt, ui.chart_caption(year), href=card_path, loading="eager", brand=False)}
{table_section}
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

"""SSR-страницы «на сегодня»: /russia/today и /russia/today/{code}.

Горячий высокочастотный спрос «курс доллара сегодня», «ключевая ставка сегодня»,
«инфляция сейчас». Страница не дублирует карточку индикатора: собственный
canonical, интент «актуальное значение прямо сейчас» — крупное значение,
изменение к предыдущей точке, свежая таблица и ссылка на полную карточку.
Контент полностью data-driven, обновляется вместе с ETL.
"""

from __future__ import annotations

from app.services import breadcrumbs as crumbs
from app.services import site_paths as paths

from dataclasses import dataclass
from datetime import date

from app.services.display import today_msk
from html import escape

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Indicator, IndicatorData
from app.services.seo_renderer import (
    _absolute,
    _breadcrumbs,
    _breadcrumbs_nav,
    _site_json_ld,
    build_document,
)


def _format_number(value) -> str:
    """Locale typography via shared display formatter."""
    from app.services.display import format_number_ru
    from app.services.locale import get_locale

    return format_number_ru(value, locale=get_locale())


def _public_unit(indicator) -> str:
    from app.services.display import localize_unit

    return localize_unit((indicator.unit or "").strip()) or ""

_MONTHS_GEN = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)


def _ru_date(d: date) -> str:
    return f"{d.day} {_MONTHS_GEN[d.month - 1]} {d.year} года"


def _en_date(d: date) -> str:
    months = (
        "", "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    )
    return f"{d.day} {months[d.month]} {d.year}"


def _locale_date(d: date) -> str:
    from app.services.locale import get_locale

    return _en_date(d) if get_locale() == "en" else _ru_date(d)


def _today_query_question(spec: TodaySpec) -> tuple[str, str]:
    from app.services.seo_i18n import today_spec_en

    en = today_spec_en(spec.code)
    if en:
        return en.get("query") or spec.query, en.get("question") or spec.question
    return spec.query, spec.question


def _dot(text: str) -> str:
    """Точка в конце предложения без удвоения после сокращений («руб.»)."""
    return text if text.rstrip().endswith(".") else text + "."


def _ru_date_short(d: date) -> str:
    return d.strftime("%d.%m.%Y")


# Freshness-SLA по частоте ряда (В-4): страница «X сегодня» продаёт свежесть,
# поэтому при умершем ETL заголовок обязан честно переключиться на «последнее
# доступное значение». Пороги — с запасом на лаг публикации источника
# (месячный ряд Росстата выходит через ~4–6 недель после периода).
_STALE_AFTER_DAYS = {
    "daily": 7,
    "weekly": 21,
    "monthly": 75,
    "quarterly": 150,
    "annual": 500,
}


def is_stale(frequency: str | None, last_date: date, today: date | None = None) -> bool:
    """Свежесть значения относительно SLA своей частоты."""
    today = today or today_msk()
    limit = _STALE_AFTER_DAYS.get((frequency or "").lower(), 75)
    return (today - last_date).days > limit


@dataclass(frozen=True)
class TodaySpec:
    code: str         # slug страницы /today/{code} и код карточки для ссылки
    query: str        # формулировка пользовательского запроса («Курс доллара»)
    question: str     # FAQ-вопрос («Сколько стоит доллар сегодня?»)
    series: str = ""  # код ряда данных, если отличается от code (cpi → cpi-yoy)

    @property
    def series_code(self) -> str:
        return self.series or self.code


# Отбор — по реальному поисковому спросу (Метрика/Вебмастер): валюты,
# ставка, инфляция, золото, топливо, индекс МосБиржи.
# «Инфляция сейчас» — это годовая инфляция (cpi-yoy), а не сырой
# месячный индекс cpi (~100), который вводит в заблуждение.
TODAY_SPECS: dict[str, TodaySpec] = {
    s.code: s for s in (
        TodaySpec("usd-rub", "Курс доллара", "Сколько стоит доллар сегодня?"),
        TodaySpec("eur-rub", "Курс евро", "Сколько стоит евро сегодня?"),
        TodaySpec("cny-rub", "Курс юаня", "Сколько стоит юань сегодня?"),
        TodaySpec("key-rate", "Ключевая ставка ЦБ", "Какая ключевая ставка ЦБ сегодня?"),
        TodaySpec("cpi", "Инфляция", "Какая инфляция в России сейчас?", series="cpi-yoy"),
        TodaySpec("gold-price", "Цена золота", "Сколько стоит грамм золота сегодня?"),
        TodaySpec("fuel-ai92", "Цена бензина АИ-92", "Сколько стоит бензин АИ-92 сегодня?"),
        TodaySpec("fuel-ai95", "Цена бензина АИ-95", "Сколько стоит бензин АИ-95 сегодня?"),
        TodaySpec("fuel-diesel", "Цена дизельного топлива", "Сколько стоит дизельное топливо сегодня?"),
        TodaySpec("imoex", "Индекс МосБиржи", "Какое значение индекса МосБиржи сегодня?"),
    )
}
TODAY_CODES: tuple[str, ...] = tuple(TODAY_SPECS)


async def _indicator_with_rows(
    db: AsyncSession, code: str, *, limit: int = 15
) -> tuple[Indicator | None, list[IndicatorData]]:
    indicator = (await db.execute(
        select(Indicator).where(Indicator.code == code, Indicator.is_active.is_(True))
    )).scalar_one_or_none()
    if indicator is None:
        return None, []
    rows = list((await db.execute(
        select(IndicatorData)
        .where(IndicatorData.indicator_id == indicator.id)
        .order_by(desc(IndicatorData.date))
        .limit(limit)
    )).scalars().all())
    return indicator, rows


def _change_phrase(cur: float, prev: float, unit: str) -> str:
    from app.services.seo_i18n import today_template

    diff = cur - prev
    if abs(diff) < 1e-12:
        return today_template("change_flat") or "без изменений к предыдущему значению"
    en_up = today_template("change_up")
    en_down = today_template("change_down")
    en_up_pp = today_template("change_up_pp")
    en_down_pp = today_template("change_down_pp")
    if unit == "%":
        delta = _format_number(abs(diff))
        if en_up_pp and en_down_pp:
            tpl = en_up_pp if diff > 0 else en_down_pp
            return tpl.format(delta=delta)
        verb = "выше" if diff > 0 else "ниже"
        return f"{verb} предыдущего значения на {delta} п. п."
    text = f"на {_format_number(abs(diff))} {unit}".strip()
    if prev:
        pct = abs(diff) / abs(prev) * 100
        text += f" ({_format_number(round(pct, 2))}%)"
    if en_up and en_down:
        # EN templates expect “{amount} {unit}”, without Russian «на».
        amount = f"{_format_number(abs(diff))} {unit}".strip()
        if prev:
            pct = abs(diff) / abs(prev) * 100
            amount += f" ({_format_number(round(pct, 2))}%)"
        tpl = en_up if diff > 0 else en_down
        return tpl.format(text=amount)
    verb = "выше" if diff > 0 else "ниже"
    return f"{verb} предыдущего значения {text}"


def _change_badge(cur: float, prev: float, unit: str) -> str:
    """Короткий цветной бейдж изменения для hero-карточки и плиток хаба."""
    from app.services.seo_i18n import today_template

    diff = cur - prev
    if abs(diff) < 1e-12:
        flat = today_template("badge_flat") or "без изменений"
        return f'<span class="seo-badge flat">{escape(flat)}</span>'
    cls = "up" if diff > 0 else "down"
    arrow = "▲" if diff > 0 else "▼"
    if unit == "%":
        pp = "pp" if today_template("change_up_pp") else "п. п."
        delta = f"{_format_number(abs(diff))} {pp}"
    else:
        delta = f"{_format_number(abs(diff))} {unit}".strip()
        if prev:
            pct = abs(diff) / abs(prev) * 100
            delta += f" ({_format_number(round(pct, 2))}%)"
    return f'<span class="seo-badge {cls}">{arrow} {escape(delta)}</span>'


async def render_today_indicator_html(code: str, db: AsyncSession) -> tuple[int, str]:
    spec = TODAY_SPECS.get(code)
    if spec is None:
        return 404, "Not found"
    indicator, rows = await _indicator_with_rows(db, spec.series_code)
    if indicator is None or len(rows) < 2:
        return 404, "Not found"

    from app.services.seo_i18n import today_template, translate_source
    from app.services.i18n_display import public_name

    query, question = _today_query_question(spec)
    last, prev = rows[0], rows[1]
    unit = _public_unit(indicator)
    source = translate_source(indicator.source) or indicator.source or ""
    ind_display = public_name(indicator.name, indicator.name_en)
    today = today_msk()
    value_text = f"{_format_number(last.value)} {unit}".strip()
    change = _change_phrase(float(last.value), float(prev.value), unit)

    # Freshness-guard (В-4): если значение старше SLA своей частоты, страница
    # не продаёт «сегодня, {дата}» — честная рамка «последнее доступное значение».
    stale = is_stale(indicator.frequency, last.date, today)
    date_today = _locale_date(today)
    date_last = _locale_date(last.date)
    en_title = today_template("title_stale" if stale else "title_fresh")
    if en_title:
        title = en_title.format(
            query=query,
            date=date_today,
            last_date=date_last,
            value_text=value_text,
        )
    elif stale:
        title = f"{query} — последнее значение на {_ru_date(last.date)}: {value_text}"
    else:
        title = f"{query} сегодня, {_ru_date(today)} — {value_text}"
    if today_template("desc"):
        fresh_frame = (
            f"latest available value as of {date_last}" if stale
            else f"data as of {date_last}"
        )
        stale_clause = today_template("stale_clause") or ""
        fresh_clause = today_template("fresh_clause") or ""
        desc_text = today_template("desc").format(
            query=query,
            stale_clause=stale_clause if stale else fresh_clause,
            value_text=value_text,
            fresh_frame=fresh_frame,
            change=change,
            source=source,
        )
    else:
        fresh_frame = (
            f"последнее доступное значение на {_ru_date(last.date)}" if stale
            else f"данные на {_ru_date(last.date)}"
        )
        desc_text = (
            f"{query}{' — последнее доступное значение' if stale else ' на сегодня'}: "
            f"{value_text} ({fresh_frame}, "
            f"{change}). Источник — {indicator.source}. График, таблица последних значений "
            f"и прогноз."
        )

    table_rows = "".join(
        f"<tr><td>{escape(_ru_date_short(r.date))}</td>"
        f"<td>{escape(_format_number(r.value))}</td></tr>"
        for r in rows
    )
    values_window = [float(r.value) for r in rows]
    vmin, vmax = min(values_window), max(values_window)

    faq_last = today_template("faq_answer_last")
    faq_change = today_template("faq_answer_change")
    if faq_last and faq_change:
        faq_a1 = (
            _dot(faq_last.format(date=date_last, value=value_text))
            + " "
            + _dot(faq_change.format(change=change))
        )
        faq_q2 = today_template("faq_freq_q") or "Как часто обновляются данные?"
        faq_a2 = (
            today_template("faq_freq_a") or ""
        ).format(source=source) or (
            f"Данные обновляются по мере публикации источником ({indicator.source}); "
            f"страница всегда показывает последнее доступное значение."
        )
        faq_h2 = today_template("faq_h2") or "Вопросы и ответы"
    else:
        faq_a1 = (
            _dot(f"По последним данным ({_ru_date(last.date)}) — {value_text}")
            + " " + _dot(f"Значение {change}")
        )
        faq_q2 = "Как часто обновляются данные?"
        faq_a2 = (
            f"Данные обновляются по мере публикации источником ({indicator.source}); "
            f"страница всегда показывает последнее доступное значение."
        )
        faq_h2 = "Вопросы и ответы"
    faq = [
        (question, faq_a1),
        (faq_q2, faq_a2),
    ]
    faq_html = f"<section><h2>{escape(faq_h2)}</h2>" + "".join(
        f'<div class="seo-faq"><h3>{escape(q)}</h3><p>{escape(a)}</p></div>' for q, a in faq
    ) + "</section>"
    faq_json_ld = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in faq
        ],
    }

    og_path = paths.og_indicator(paths.RUSSIA, spec.series_code)
    canonical = paths.today(code)
    badge = _change_badge(float(last.value), float(prev.value), unit)
    en_eyebrow = today_template("eyebrow_stale" if stale else "eyebrow_fresh")
    eyebrow = en_eyebrow or (
        "Последнее доступное значение" if stale else "Показатель на сегодня"
    )
    en_h1 = today_template("h1_stale" if stale else "h1_fresh")
    h1_text = (
        en_h1.format(query=query)
        if en_h1
        else (f"{query} — последнее значение" if stale else f"{query} сегодня")
    )
    en_stale_note = today_template("stale_note")
    if stale:
        if en_stale_note:
            stale_note = (
                f'<p class="seo-note">{escape(en_stale_note.format(date=date_last))}</p>'
            )
        else:
            stale_note = (
                f'<p class="seo-note">Новых публикаций источника пока нет: показано последнее '
                f'доступное значение на {escape(_ru_date(last.date))}.</p>'
            )
    else:
        stale_note = ""

    th_date = today_template("th_date") or "Дата"
    th_value = today_template("th_value") or (unit or "Значение")
    if today_template("th_value") and unit:
        th_value = unit
    tile_prev = today_template("tile_prev") or "Предыдущее"
    tile_min = (today_template("tile_min") or "Минимум за {n} набл.").format(n=len(rows))
    tile_max = (today_template("tile_max") or "Максимум за {n} набл.").format(n=len(rows))
    tile_updated = today_template("tile_updated") or "Обновлено"
    on_date = (today_template("on_date") or "на {date}").format(date=date_last)
    source_meta = (today_template("source_meta") or "источник: {source}").format(
        source=source
    )
    body_lead_tpl = today_template("body_lead")
    if body_lead_tpl:
        body_lead = body_lead_tpl.format(
            date=escape(date_last),
            value=escape(value_text),
            change=escape(_dot(change)),
            source=escape(source),
        )
    else:
        body_lead = (
            f"Актуальное значение на {escape(_ru_date(last.date))}: "
            f"<strong>{escape(value_text)}</strong> — {escape(_dot(change))} "
            f"Данные официального источника ({escape(indicator.source)}); "
            f"страница обновляется автоматически по мере выхода новых значений."
        )
    chart_alt = (
        today_template("chart_alt") or "{query} сегодня — график, последнее значение {value}, источник {source}"
    ).format(query=query, value=value_text, source=source)
    chart_caption = (
        today_template("chart_caption")
        or "{query}: динамика. Источник: {source}. forecasteconomy.com"
    ).format(query=query, source=source)
    cta = today_template("cta_chart") or "Интерактивный график и прогноз →"
    table_h2 = today_template("table_h2") or "Последние значения"
    range_note = (
        today_template("range_note")
        or "Диапазон последних {n} наблюдений: от {vmin} до {vmax} {unit}"
    ).format(
        n=len(rows),
        vmin=_format_number(vmin),
        vmax=_format_number(vmax),
        unit=unit,
    ).rstrip()
    history_h2 = today_template("history_h2") or "Полная история и прогноз"
    history_tpl = today_template("history_p")
    if history_tpl:
        history_p = history_tpl.format(
            href=escape(paths.russia_indicator(spec.code)),
            name=escape(ind_display),
        )
    else:
        history_p = (
            f"Интерактивный график с историей с первого доступного года, режимы представления и прогноз — на странице "
            f'<a href="{escape(paths.russia_indicator(spec.code))}">{escape(indicator.name)}</a>.'
        )

    body = f"""<main class="seo-page">
{_breadcrumbs_nav(crumbs.today_indicator_trail(query, paths.today(code)))}
<p class="seo-eyebrow">{escape(eyebrow)}</p>
<h1>{escape(h1_text)}</h1>
<div class="seo-hero">
<div class="seo-hero-value">{escape(_format_number(last.value))}<small>{escape(unit)}</small></div>
<div class="seo-hero-meta">{badge}<span>{escape(on_date)}</span><span>{escape(source_meta)}</span></div>
</div>
{stale_note}
<div class="seo-tiles">
<div class="seo-tile"><span>{escape(tile_prev)}</span><b>{escape(_format_number(prev.value))} {escape(unit)}</b></div>
<div class="seo-tile"><span>{escape(tile_min)}</span><b>{escape(_format_number(vmin))} {escape(unit)}</b></div>
<div class="seo-tile"><span>{escape(tile_max)}</span><b>{escape(_format_number(vmax))} {escape(unit)}</b></div>
<div class="seo-tile"><span>{escape(tile_updated)}</span><b>{escape(_ru_date_short(last.date))}</b></div>
</div>
<p>{body_lead}</p>
<figure class="seo-chart"><img src="{escape(og_path)}" width="1200" height="630" alt="{escape(chart_alt)}" loading="eager"><figcaption>{escape(chart_caption)}</figcaption></figure>
<p><a class="seo-linkbtn" href="{escape(paths.russia_indicator(spec.code))}">{escape(cta)}</a></p>
<section><h2>{escape(table_h2)}</h2>
<div class="seo-scroll"><table><thead><tr><th>{escape(th_date)}</th><th>{escape(th_value)}</th></tr></thead><tbody>{table_rows}</tbody></table></div>
<p>{escape(_dot(range_note))}</p></section>
{faq_html}
<section><h2>{escape(history_h2)}</h2>
<p>{history_p}</p></section>
</main>"""

    from app.services.locale import in_language

    json_ld = [
        _site_json_ld(),
        _breadcrumbs(crumbs.today_indicator_trail(query, paths.today(code))),
        faq_json_ld,
        {
            "@context": "https://schema.org",
            "@type": "Dataset",
            "name": h1_text,
            "description": desc_text,
            "url": _absolute(canonical),
            "inLanguage": in_language(),
            "creator": {"@type": "Organization", "name": source},
            "image": _absolute(og_path),
        },
    ]
    en_kw = today_template("keywords")
    if en_kw:
        # Never fall through to Russian seo_keywords from DB.
        keywords = en_kw.format(
            query_lower=query.lower(),
            seo_keywords=query,
        )
    else:
        keywords = (
            f"{query.lower()} сегодня, {query.lower()} сейчас, "
            f"{query.lower()} на сегодня, {indicator.seo_keywords or indicator.name}"
        )
    html = await build_document(
        title=title,
        description=desc_text,
        canonical_path=canonical,
        body=body,
        json_ld=json_ld,
        keywords=keywords,
        og_image=_absolute(og_path),
    )
    return 200, html


async def render_today_hub_html(db: AsyncSession) -> tuple[int, str]:
    today = today_msk()
    items_html = []
    list_items = []
    from app.services.seo_i18n import today_template

    item_today_tpl = today_template("hub_item_today")
    on_date_tpl = today_template("on_date")
    for i, code in enumerate(TODAY_CODES, 1):
        spec = TODAY_SPECS[code]
        query, _question = _today_query_question(spec)
        indicator, rows = await _indicator_with_rows(db, spec.series_code, limit=2)
        if indicator is None or not rows:
            continue
        unit = _public_unit(indicator)
        badge = ""
        if len(rows) > 1:
            badge = _change_badge(float(rows[0].value), float(rows[1].value), unit)
        item_name = (
            item_today_tpl.format(query=query)
            if item_today_tpl
            else f"{query} сегодня"
        )
        date_short = _ru_date_short(rows[0].date)
        as_of_label = (
            on_date_tpl.format(date=date_short) if on_date_tpl else f"на {date_short}"
        )
        items_html.append(
            f'<li><a class="seo-item" href="{escape(paths.today(code))}">'
            f'<div class="seo-item-name">{escape(item_name)}</div>'
            f'<div class="seo-item-value">{escape(_format_number(rows[0].value))}'
            f"<small>{escape(unit)}</small></div>"
            f'<div class="seo-item-meta">{badge}<span>{escape(as_of_label)}</span></div>'
            f"</a></li>"
        )
        list_items.append({
            "@type": "ListItem",
            "position": i,
            "name": item_name,
            "url": _absolute(paths.today(code)),
        })

    if not items_html:
        return 404, "Not found"

    from app.services.seo_i18n import (
        today_hub_description,
        today_hub_h1,
        today_hub_title,
    )

    date_text = _locale_date(today)
    title = today_hub_title(date_text) or (
        f"Экономика России сегодня, {_ru_date(today)}: курсы, ставка, инфляция, цены"
    )
    # «Обновление по мере публикации», не «ежедневно» (В-16): половина рядов —
    # недельные/месячные, обещание ежедневности вводило в заблуждение.
    desc_text = today_hub_description() or (
        "Ключевые экономические показатели России на сегодня: курс доллара, евро и юаня, "
        "ключевая ставка ЦБ, инфляция, цена золота и топлива, индекс МосБиржи. "
        "Официальные данные, обновление по мере публикации источников."
    )
    hub_h1 = today_hub_h1() or "Экономика России сегодня"
    og_path = paths.og_today()
    hub_alt_tpl = today_template("hub_alt")
    hub_alt = (
        hub_alt_tpl.format(date=date_text)
        if hub_alt_tpl
        else (
            f"Экономика России сегодня, {_ru_date(today)}: курс доллара, евро и юаня, "
            f"ключевая ставка, инфляция, цена золота и топлива, индекс МосБиржи"
        )
    )
    hub_caption = (
        today_template("hub_caption") or "Ключевые показатели экономики России на {date}. forecasteconomy.com"
    ).format(date=date_text if today_template("hub_caption") else _ru_date(today))
    eyebrow = (
        today_template("hub_eyebrow") or "Сводка на {date}"
    ).format(date=date_text if today_template("hub_eyebrow") else _ru_date(today))
    hub_lead = today_template("hub_lead") or (
        "Актуальные значения ключевых показателей. Каждая карточка ведёт на "
        "страницу показателя с последними значениями, графиком и таблицей; полная история и прогноз — "
        "на карточках индикаторов."
    )
    hub_h2 = today_template("hub_h2") or "Показатели на сегодня"
    hub_more_h2 = today_template("hub_more_h2") or "Больше данных"
    hub_more_tpl = today_template("hub_more_p")
    if hub_more_tpl:
        hub_more = hub_more_tpl.format(
            regions=paths.region_hub(),
            calendar=paths.calendar(),
        )
    else:
        hub_more = (
            f'Более 100 макроэкономических индикаторов — на <a href="/">главной странице</a>; '
            f'региональная статистика — в разделе <a href="{paths.region_hub()}">Регионы России</a>; '
            f'даты будущих публикаций — в <a href="{paths.calendar()}">календаре статистики</a>.'
        )
    body = f"""<main class="seo-page">
{_breadcrumbs_nav(crumbs.today_trail())}
<p class="seo-eyebrow">{escape(eyebrow)}</p>
<h1>{escape(hub_h1)}</h1>
<p>{hub_lead}</p>
<figure class="seo-chart"><img src="{escape(og_path)}" width="1200" height="630" alt="{escape(hub_alt)}" loading="eager"><figcaption>{escape(hub_caption)}</figcaption></figure>
<section><h2>{escape(hub_h2)}</h2><ul class="seo-grid">{''.join(items_html)}</ul></section>
<section><h2>{escape(hub_more_h2)}</h2><p>{hub_more}</p></section>
</main>"""

    json_ld = [
        _site_json_ld(),
        _breadcrumbs(crumbs.today_trail()),
        {"@context": "https://schema.org", "@type": "ItemList", "itemListElement": list_items},
        {
            "@context": "https://schema.org",
            "@type": "ImageObject",
            "contentUrl": _absolute(og_path),
            "url": _absolute(og_path),
            "name": title,
            "description": hub_alt,
            "representativeOfPage": True,
            "width": 1200,
            "height": 630,
        },
    ]
    hub_kw = today_template("hub_keywords")
    html = await build_document(
        title=title,
        description=desc_text,
        canonical_path=paths.today(),
        body=body,
        json_ld=json_ld,
        keywords=hub_kw or (
            "курс доллара сегодня, ключевая ставка сегодня, инфляция сейчас, "
            "экономика россии сегодня, цена золота сегодня, цена бензина сегодня"
        ),
        og_image=_absolute(og_path),
    )
    return 200, html

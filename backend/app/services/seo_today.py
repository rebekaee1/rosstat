"""SSR-страницы «на сегодня»: /today и /today/{code}.

Горячий высокочастотный спрос «курс доллара сегодня», «ключевая ставка сегодня»,
«инфляция сейчас». Страница не дублирует карточку индикатора: собственный
canonical, интент «актуальное значение прямо сейчас» — крупное значение,
изменение к предыдущей точке, свежая таблица и ссылка на полную карточку.
Контент полностью data-driven, обновляется вместе с ETL.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.services.display import today_msk
from html import escape

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Indicator, IndicatorData
from app.services.seo_renderer import (
    DOMAIN,
    _breadcrumbs,
    _site_json_ld,
    build_document,
)


def _format_number(value) -> str:
    """Русская типографика: пробел-разряды, запятая-дробь, до 2 знаков."""
    v = float(value)
    digits = 0 if abs(v) >= 1000 else (1 if abs(v) >= 100 else 2)
    text = f"{v:,.{digits}f}".replace(",", "\u202f").replace(".", ",")
    if "," in text:
        text = text.rstrip("0").rstrip(",")
    return text

_MONTHS_GEN = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)


def _ru_date(d: date) -> str:
    return f"{d.day} {_MONTHS_GEN[d.month - 1]} {d.year} года"


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
    diff = cur - prev
    if abs(diff) < 1e-12:
        return "без изменений к предыдущему значению"
    verb = "выше" if diff > 0 else "ниже"
    if unit == "%":
        # Разница долей в процентах — это процентные пункты.
        return f"{verb} предыдущего значения на {_format_number(abs(diff))} п. п."
    text = f"на {_format_number(abs(diff))} {unit}".strip()
    if prev:
        pct = abs(diff) / abs(prev) * 100
        text += f" ({_format_number(round(pct, 2))}%)"
    return f"{verb} предыдущего значения {text}"


def _change_badge(cur: float, prev: float, unit: str) -> str:
    """Короткий цветной бейдж изменения для hero-карточки и плиток хаба."""
    diff = cur - prev
    if abs(diff) < 1e-12:
        return '<span class="seo-badge flat">без изменений</span>'
    cls = "up" if diff > 0 else "down"
    arrow = "▲" if diff > 0 else "▼"
    if unit == "%":
        delta = f"{_format_number(abs(diff))} п. п."
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

    last, prev = rows[0], rows[1]
    unit = (indicator.unit or "").strip()
    today = today_msk()
    value_text = f"{_format_number(last.value)} {unit}".strip()
    change = _change_phrase(float(last.value), float(prev.value), unit)

    # Freshness-guard (В-4): если значение старше SLA своей частоты, страница
    # не продаёт «сегодня, {дата}» — честная рамка «последнее доступное значение».
    stale = is_stale(indicator.frequency, last.date, today)
    if stale:
        title = f"{spec.query} — последнее значение на {_ru_date(last.date)}: {value_text}"
    else:
        title = f"{spec.query} сегодня, {_ru_date(today)} — {value_text}"
    fresh_frame = (
        f"последнее доступное значение на {_ru_date(last.date)}" if stale
        else f"данные на {_ru_date(last.date)}"
    )
    desc_text = (
        f"{spec.query}{' — последнее доступное значение' if stale else ' на сегодня'}: "
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

    faq = [
        (spec.question,
         _dot(f"По последним данным ({_ru_date(last.date)}) — {value_text}")
         + " " + _dot(f"Значение {change}")),
        ("Как часто обновляются данные?",
         f"Данные обновляются по мере публикации источником ({indicator.source}); "
         f"страница всегда показывает последнее доступное значение."),
    ]
    faq_html = "<section><h2>Вопросы и ответы</h2>" + "".join(
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

    og_path = f"/og/{spec.series_code}.png"
    canonical = f"/today/{code}"
    badge = _change_badge(float(last.value), float(prev.value), unit)
    eyebrow = "Последнее доступное значение" if stale else "Показатель на сегодня"
    h1_text = f"{spec.query} — последнее значение" if stale else f"{spec.query} сегодня"
    stale_note = (
        f'<p class="seo-note">Новых публикаций источника пока нет: показано последнее '
        f'доступное значение на {escape(_ru_date(last.date))}.</p>' if stale else ""
    )
    body = f"""<main class="seo-page">
<nav aria-label="Хлебные крошки"><a href="/">Главная</a> / <a href="/today">Сегодня</a> / {escape(spec.query)}</nav>
<p class="seo-eyebrow">{escape(eyebrow)}</p>
<h1>{escape(h1_text)}</h1>
<div class="seo-hero">
<div class="seo-hero-value">{escape(_format_number(last.value))}<small>{escape(unit)}</small></div>
<div class="seo-hero-meta">{badge}<span>на {escape(_ru_date(last.date))}</span><span>· источник: {escape(indicator.source)}</span></div>
</div>
{stale_note}
<div class="seo-tiles">
<div class="seo-tile"><span>Предыдущее</span><b>{escape(_format_number(prev.value))} {escape(unit)}</b></div>
<div class="seo-tile"><span>Минимум за {len(rows)} набл.</span><b>{escape(_format_number(vmin))} {escape(unit)}</b></div>
<div class="seo-tile"><span>Максимум за {len(rows)} набл.</span><b>{escape(_format_number(vmax))} {escape(unit)}</b></div>
<div class="seo-tile"><span>Обновлено</span><b>{escape(_ru_date_short(last.date))}</b></div>
</div>
<p>Актуальное значение на {escape(_ru_date(last.date))}: <strong>{escape(value_text)}</strong> — {escape(_dot(change))}
Данные официального источника ({escape(indicator.source)}); страница обновляется автоматически по мере выхода новых значений.</p>
<figure class="seo-chart"><img src="{escape(og_path)}" width="1200" height="630" alt="{escape(spec.query)} сегодня — график, последнее значение {escape(value_text)}, источник {escape(indicator.source)}" loading="eager"><figcaption>{escape(spec.query)}: динамика. Источник: {escape(indicator.source)}. forecasteconomy.com</figcaption></figure>
<p><a class="seo-linkbtn" href="/indicator/{escape(spec.code)}">Интерактивный график и прогноз →</a></p>
<section><h2>Последние значения</h2>
<div class="seo-scroll"><table><thead><tr><th>Дата</th><th>{escape(unit or 'Значение')}</th></tr></thead><tbody>{table_rows}</tbody></table></div>
<p>{escape(_dot(f"Диапазон последних {len(rows)} наблюдений: от {_format_number(vmin)} до {_format_number(vmax)} {unit}".rstrip()))}</p></section>
{faq_html}
<section><h2>Полная история и прогноз</h2>
<p>Интерактивный график с историей с первого доступного года, режимы представления и прогноз — на странице
<a href="/indicator/{escape(spec.code)}">{escape(indicator.name)}</a>.</p></section>
</main>"""

    json_ld = [
        _site_json_ld(),
        _breadcrumbs([
            ("/", "Главная"), ("/today", "Сегодня"), (canonical, spec.query),
        ]),
        faq_json_ld,
        {
            "@context": "https://schema.org",
            "@type": "Dataset",
            "name": f"{spec.query} сегодня",
            "description": desc_text,
            "url": f"{DOMAIN}{canonical}",
            "inLanguage": "ru-RU",
            "creator": {"@type": "Organization", "name": indicator.source},
            "image": f"{DOMAIN}{og_path}",
        },
    ]
    html = await build_document(
        title=title,
        description=desc_text,
        canonical_path=canonical,
        body=body,
        json_ld=json_ld,
        keywords=(
            f"{spec.query.lower()} сегодня, {spec.query.lower()} сейчас, "
            f"{spec.query.lower()} на сегодня, {indicator.seo_keywords or indicator.name}"
        ),
        og_image=f"{DOMAIN}{og_path}",
    )
    return 200, html


async def render_today_hub_html(db: AsyncSession) -> tuple[int, str]:
    today = today_msk()
    items_html = []
    list_items = []
    for i, code in enumerate(TODAY_CODES, 1):
        spec = TODAY_SPECS[code]
        indicator, rows = await _indicator_with_rows(db, spec.series_code, limit=2)
        if indicator is None or not rows:
            continue
        unit = (indicator.unit or "").strip()
        badge = ""
        if len(rows) > 1:
            badge = _change_badge(float(rows[0].value), float(rows[1].value), unit)
        items_html.append(
            f'<li><a class="seo-item" href="/today/{escape(code)}">'
            f'<div class="seo-item-name">{escape(spec.query)} сегодня</div>'
            f'<div class="seo-item-value">{escape(_format_number(rows[0].value))}'
            f"<small>{escape(unit)}</small></div>"
            f'<div class="seo-item-meta">{badge}<span>на {escape(_ru_date_short(rows[0].date))}</span></div>'
            f"</a></li>"
        )
        list_items.append({
            "@type": "ListItem",
            "position": i,
            "name": f"{spec.query} сегодня",
            "url": f"{DOMAIN}/today/{code}",
        })

    if not items_html:
        return 404, "Not found"

    title = f"Экономика России сегодня, {_ru_date(today)}: курсы, ставка, инфляция, цены"
    # «Обновление по мере публикации», не «ежедневно» (В-16): половина рядов —
    # недельные/месячные, обещание ежедневности вводило в заблуждение.
    desc_text = (
        "Ключевые экономические показатели России на сегодня: курс доллара, евро и юаня, "
        "ключевая ставка ЦБ, инфляция, цена золота и топлива, индекс МосБиржи. "
        "Официальные данные, обновление по мере публикации источников."
    )
    og_path = "/og/today.png"
    hub_alt = (f"Экономика России сегодня, {_ru_date(today)}: курс доллара, евро и юаня, "
               f"ключевая ставка, инфляция, цена золота и топлива, индекс МосБиржи")
    body = f"""<main class="seo-page">
<nav aria-label="Хлебные крошки"><a href="/">Главная</a> / Сегодня</nav>
<p class="seo-eyebrow">Сводка на {escape(_ru_date(today))}</p>
<h1>Экономика России сегодня</h1>
<p>Актуальные значения ключевых показателей. Каждая карточка ведёт на
страницу показателя с последними значениями, графиком и таблицей; полная история и прогноз —
на карточках индикаторов.</p>
<figure class="seo-chart"><img src="{escape(og_path)}" width="1200" height="630" alt="{escape(hub_alt)}" loading="eager"><figcaption>Ключевые показатели экономики России на {escape(_ru_date(today))}. forecasteconomy.com</figcaption></figure>
<section><h2>Показатели на сегодня</h2><ul class="seo-grid">{''.join(items_html)}</ul></section>
<section><h2>Больше данных</h2><p>Более 100 макроэкономических индикаторов — на <a href="/">главной странице</a>;
региональная статистика — в разделе <a href="/regions">Регионы России</a>;
даты будущих публикаций — в <a href="/calendar">календаре статистики</a>.</p></section>
</main>"""

    json_ld = [
        _site_json_ld(),
        _breadcrumbs([("/", "Главная"), ("/today", "Сегодня")]),
        {"@context": "https://schema.org", "@type": "ItemList", "itemListElement": list_items},
        {
            "@context": "https://schema.org",
            "@type": "ImageObject",
            "contentUrl": f"{DOMAIN}{og_path}",
            "url": f"{DOMAIN}{og_path}",
            "name": f"Экономика России сегодня, {_ru_date(today)}",
            "description": hub_alt,
            "representativeOfPage": True,
            "width": 1200,
            "height": 630,
        },
    ]
    html = await build_document(
        title=title,
        description=desc_text,
        canonical_path="/today",
        body=body,
        json_ld=json_ld,
        keywords=(
            "курс доллара сегодня, ключевая ставка сегодня, инфляция сейчас, "
            "экономика россии сегодня, цена золота сегодня, цена бензина сегодня"
        ),
        og_image=f"{DOMAIN}{og_path}",
    )
    return 200, html

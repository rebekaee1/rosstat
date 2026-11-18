"""Чтение недельного слоя регионального показателя (``region_weekly_data``, 18.11.2026).

Один источник для API карточки «топливо × регион», для SSR той же страницы и для блока
«по регионам» на федеральных страницах топлива. Страница одна на пару (топливо, регион),
даты выбираются на ней, отдельных адресов на дату нет — так не появляются тысячи тонких
страниц с одной цифрой.
"""

from __future__ import annotations

from datetime import date
from html import escape

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Region, RegionIndicator, RegionWeeklyPoint
from app.services.locale import get_locale

# Федеральный недельный ряд → региональный показатель той же марки (обратный мост к MACRO_BY_TABLE).
FEDERAL_TO_REGIONAL = {
    "fuel-ai92": "ceni-ai92",
    "fuel-ai95": "ceni-ai95",
    "fuel-diesel": "ceni-dt",
}

# Названия марок для фраз: «литр дизельного топлива», а не «литр потребительские цены на…».
# (именительный, родительный, английский, английский внутри фразы)
_FUEL_NAMES = {
    "ceni-ai92": ("Бензин АИ-92", "бензина АИ-92", "AI-92 petrol", "AI-92 petrol"),
    "ceni-ai95": ("Бензин АИ-95", "бензина АИ-95", "AI-95 petrol", "AI-95 petrol"),
    "ceni-ai98": ("Бензин АИ-98", "бензина АИ-98", "AI-98 petrol", "AI-98 petrol"),
    "ceni-dt": ("Дизельное топливо", "дизельного топлива", "Diesel fuel", "diesel fuel"),
}


def fuel_name_gen(code: str, fallback: str) -> str:
    """«дизельного топлива» / «diesel fuel» — для «литр …», «цена …»."""
    names = _FUEL_NAMES.get(code)
    if not names:
        return fallback.split(",")[0].lower()
    return names[3] if get_locale() == "en" else names[1]


def fuel_name_nom(code: str, fallback: str) -> str:
    """«Дизельное топливо» / «Diesel fuel» — для заголовка."""
    names = _FUEL_NAMES.get(code)
    if not names:
        return fallback.split(",")[0]
    return names[2] if get_locale() == "en" else names[0]


def fmt_kop(value: float) -> str:
    """Недельная цена с копейками («75,83»): от недели к неделе она меняется на копейки, «75,8» их съедает."""
    text = f"{float(value):.2f}"
    return text if get_locale() == "en" else text.replace(".", ",")


def weekly_unit(unit: str) -> str:
    """«рубль за литр» → «руб./л» (как на федеральных страницах топлива); прочее — как в источнике."""
    low = (unit or "").lower()
    if ("рубл" in low or "rub" in low or "rouble" in low) and ("литр" in low or "litre" in low or "liter" in low):
        return "RUB/l" if get_locale() == "en" else "руб./л"
    return unit


async def weekly_points(db: AsyncSession, indicator_id: int, region_id: int) -> list[tuple[date, float]]:
    """Недельные цены пары (показатель, регион) по возрастанию даты; нет слоя — пустой список."""
    rows = (await db.execute(
        select(RegionWeeklyPoint.date, RegionWeeklyPoint.value)
        .where(RegionWeeklyPoint.indicator_id == indicator_id,
               RegionWeeklyPoint.region_id == region_id)
        .order_by(RegionWeeklyPoint.date)
    )).all()
    return [(d, float(v)) for d, v in rows]


def value_on(points: list[tuple[date, float]], day: date) -> tuple[date, float] | None:
    """Цена «на дату»: последняя регистрация не позже дня; до первой регистрации — первая."""
    if not points:
        return None
    best = None
    for d, v in points:
        if d <= day:
            best = (d, v)
        else:
            break
    return best or points[0]


_SECTION_RU = {
    "h2": "Цена {fuel} по регионам на {date}",
    "p": (
        "Средняя цена литра по заправкам каждого субъекта на день записи Росстата; в среднем по России — "
        "{rf} руб./л. В регионе — цены по неделям с {first} года и выбор любой даты."
    ),
    "th_region": "Регион",
    "th_value": "руб./л",
}
_SECTION_EN = {
    "h2": "{fuel} prices by region on {date}",
    "p": (
        "Average price per litre across filling stations of each federal subject on the Rosstat record date; "
        "Russia-wide average {rf} RUB/l. Open a region for weekly prices since {first} and any date."
    ),
    "th_region": "Region",
    "th_value": "RUB/l",
}


async def fuel_regions_section(db: AsyncSession, federal_code: str, *, year: int | None = None) -> str:
    """Блок «цена по регионам» для федеральной страницы топлива: все субъекты на одну дату записи.

    Без ``year`` — последняя запись; с ``year`` — последняя запись этого года (годовая страница).
    Нет недельного слоя — пустая строка. Ссылки ведут на страницы «топливо × регион»: из поиска
    «ДТ в СПб на дату» чаще приходят на федеральную страницу, отсюда до региона один шаг.
    """
    code = FEDERAL_TO_REGIONAL.get(federal_code)
    if not code:
        return ""
    ind_id = (await db.execute(
        select(RegionIndicator.id).where(RegionIndicator.code == code)
    )).scalar_one_or_none()
    if ind_id is None:
        return ""
    q = select(func.max(RegionWeeklyPoint.date)).where(RegionWeeklyPoint.indicator_id == ind_id)
    if year is not None:
        q = q.where(RegionWeeklyPoint.date <= date(year, 12, 31))
    day = (await db.execute(q)).scalar_one_or_none()
    if day is None:
        return ""
    first = (await db.execute(
        select(func.min(RegionWeeklyPoint.date)).where(RegionWeeklyPoint.indicator_id == ind_id)
    )).scalar_one()
    rows = (await db.execute(
        select(Region.slug, Region.name, Region.kind, RegionWeeklyPoint.value)
        .join(Region, Region.id == RegionWeeklyPoint.region_id)
        .where(RegionWeeklyPoint.indicator_id == ind_id, RegionWeeklyPoint.date == day,
               Region.kind.in_(("region", "country")))
    )).all()
    subjects = [(s, n, float(v)) for s, n, k, v in rows if k == "region"]
    rf = next((float(v) for s, _n, _k, v in rows if s == "russia"), None)
    if not subjects:
        return ""

    from app.services import site_paths as paths
    from app.services.display import format_date_locale
    from app.services.seo_i18n import region_display_name

    en = get_locale() == "en"
    tpl = _SECTION_EN if en else _SECTION_RU
    named = sorted(((s, region_display_name(s, n), v) for s, n, v in subjects), key=lambda r: r[1].lower())
    items = "".join(
        f'<tr><td><a href="{escape(paths.region_indicator(s, code))}">{escape(n)}</a></td>'
        f"<td>{fmt_kop(v)}</td></tr>"
        for s, n, v in named
    )
    fuel = fuel_name_nom(code, code) if en else fuel_name_gen(code, code)
    p = tpl["p"].format(rf=fmt_kop(rf) if rf is not None else "—", first=first.year)
    return (
        f'<section id="regions"><h2>{escape(tpl["h2"].format(fuel=fuel, date=format_date_locale(day)))}</h2>'
        f"<p>{escape(p)}</p>"
        f"<table><thead><tr><th>{tpl['th_region']}</th><th>{tpl['th_value']}</th></tr></thead>"
        f"<tbody>{items}</tbody></table></section>"
    )

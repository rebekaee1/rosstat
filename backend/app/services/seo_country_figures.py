"""«Главное» страны в серверном HTML и в инлайн-предзагрузке (/{country}).

Те же цифры, что страница страны рисует в четырёх карточках: название,
значение, период, «год назад». Поисковик видит их в HTML, а приложение берёт
из `#fe-country-bootstrap` и рисует карточки, не дожидаясь сети.

Данные не считаются заново: «Главное» берётся из уже собранного каталога страны
в Redis (`country:v19`, его же читает API), а при промахе строится тем же
`build_country_overview`. Серии для мини-графика читаются одним коротким
запросом на последние точки (`latest_world_point_series`), без полных историй.
Результат лежит внутри SSR-кэша страницы (`ssr-world`), отдельного ключа нет.

Правила подачи повторяют `frontend/src/lib/countryKeyFigures.js` и
`components/country/CountryKeyFigures.jsx`: «849,7 млрд €», а не «849 680»;
«II кв. 2026» / «Q2 2026»; подпись «с поправкой на инфляцию».
"""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from html import escape

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import site_paths as paths

logger = logging.getLogger(__name__)

KEY_FIGURES_MAX = 4
BOOTSTRAP_ELEMENT_ID = "fe-country-bootstrap"
BOOTSTRAP_VERSION = 1

# Сколько последних точек рисует мини-график (как SPARK_POINTS во фронте).
_SPARK_POINTS = {"daily": 120, "weekly": 120, "monthly": 120, "quarterly": 40, "annual": 12}
_SPARK_DEFAULT = 40
# Для темпа за год нужны ещё 12 месячных точек до начала окна графика.
_FETCH_LIMIT = 132

_TOLERANCE_DAYS = {"daily": 10, "weekly": 20, "monthly": 25, "quarterly": 50, "annual": 190}
_TOLERANCE_DEFAULT = 45

_LABELS_RU = {
    "hicp-index": "Инфляция",
    "unemployment-rate": "Безработица",
    "gdp-volume-quarterly": "ВВП, квартал",
    "gdp-volume-annual": "ВВП, год",
    "gdp-usd": "ВВП",
    "gdp-per-capita-usd": "ВВП на душу населения",
    "population": "Население",
    "budget-balance-gdp": "Баланс бюджета",
    "government-debt-gdp": "Госдолг к ВВП",
    "long-term-interest-rate": "Доходность гособлигаций",
    "activity-rate": "Экономическая активность населения",
    "gdp-per-capita-eu": "ВВП на душу, % от среднего по ЕС",
}
_LABELS_EN = {
    "hicp-index": "Inflation",
    "unemployment-rate": "Unemployment",
    "gdp-volume-quarterly": "GDP, quarterly",
    "gdp-volume-annual": "GDP, annual",
    "gdp-usd": "GDP",
    "gdp-per-capita-usd": "GDP per capita",
    "population": "Population",
    "budget-balance-gdp": "Budget balance",
    "government-debt-gdp": "Government debt to GDP",
    "long-term-interest-rate": "Government bond yield",
    "activity-rate": "Economic activity rate",
    "gdp-per-capita-eu": "GDP per capita, % of EU average",
}

_SCALES_RU = ("тыс.", "млн", "млрд", "трлн")
_SCALES_EN = ("thousand", "million", "billion", "trillion")
_CURRENCY_SYMBOL = {
    "евро": "€", "euro": "€", "eur": "€",
    "доллар": "$", "доллара": "$", "usd": "$",
    "руб.": "₽", "руб": "₽", "рублей": "₽", "rub": "₽",
}
_SCALED_UNIT = re.compile(
    r"^(тыс\.|млн|млрд|трлн|thousand|million|billion|trillion|ths)\s+(\S+)$", re.IGNORECASE,
)
_REAL_QUALIFIER = re.compile(
    r"постоянн[а-яё]*\s+цен|constant prices|chain[- ]linked|in \d{4} prices|цены \d{4}",
    re.IGNORECASE,
)
_YOY_WORDS = re.compile(r"за год|year[- ]over[- ]year|yoy", re.IGNORECASE)


def _tpl(key: str, default: str) -> str:
    from app.services.seo_i18n import world_template

    return world_template(key) or default


# ---------------------------------------------------------------- числа


def _group(int_part: str, locale: str) -> str:
    sep = "," if locale == "en" else "\u00a0"
    out = ""
    while len(int_part) > 3:
        out = sep + int_part[-3:] + out
        int_part = int_part[:-3]
    return int_part + out


def _fixed(value: float, digits: int, locale: str) -> str:
    """Как `formatValue` фронта: RU запятая и неразрывный пробел, EN точка и запятая."""
    # toFixed в JS при равной близости берёт большее число (3,25 -> 3,3), а format() в
    # Python округляет к чётному: считаем Decimal от точного двоичного значения.
    quantum = Decimal(1).scaleb(-digits)
    rounded = Decimal(abs(float(value))).quantize(quantum, rounding=ROUND_HALF_UP)
    text = f"{rounded:f}"
    int_part, _, frac = text.partition(".")
    sign = "-" if value < 0 and rounded != 0 else ""
    dec = "." if locale == "en" else ","
    body = _group(int_part, locale) + (dec + frac if frac else "")
    return ("\u2212" + body) if sign else body


def _digits(value: float) -> int:
    magnitude = abs(float(value))
    if magnitude >= 1000:
        return 0
    return 1 if magnitude >= 1 else 2


def _tidy_unit_en(text: str) -> str:
    out = re.sub(
        r"chain[- ]linked volumes,?\s*\(?(\d{4})\)?", r"in \1 prices", text, flags=re.IGNORECASE,
    )
    return out.strip()


def _parse_scaled(unit_text: str) -> tuple[str, int, str] | None:
    """«в постоянных ценах 2015 года, млн евро» -> (голова, разряд, валюта)."""
    text = (unit_text or "").strip()
    if not text:
        return None
    head, comma, tail = text.rpartition(",")
    head = head.strip() if comma else ""
    tail = (tail if comma else text).strip()
    match = _SCALED_UNIT.match(tail)
    if not match:
        return None
    word = match.group(1).lower()
    if word == "ths":
        level = 0
    elif word in _SCALES_RU:
        level = _SCALES_RU.index(word)
    else:
        level = _SCALES_EN.index(word)
    return head, level, match.group(2)


def _scale_money(value: float, unit_text: str, locale: str) -> tuple[float, str, str] | None:
    parsed = _parse_scaled(unit_text)
    if parsed is None:
        return None
    head, level, token = parsed
    scaled = float(value)
    while abs(scaled) >= 1000 and level < 3:
        scaled /= 1000
        level += 1
    symbol = _CURRENCY_SYMBOL.get(token.lower(), token)
    word = (_SCALES_EN if locale == "en" else _SCALES_RU)[level]
    return scaled, f"{word} {symbol}", head


def _split_unit(text: str) -> tuple[str, str]:
    """(коротко рядом с числом, длинно в подписи): как `splitUnit` фронта."""
    value = (text or "").strip()
    if not value:
        return "", ""
    if value.startswith("%") or value.endswith(", %"):
        return "%", ("" if value == "%" else value)
    if len(value) <= 14:
        return value, ""
    return "", value


def _period_text(day: date, frequency: str, locale: str) -> str:
    from app.services.display import format_date_locale, format_month_year

    if frequency == "annual":
        return str(day.year)
    if frequency == "quarterly":
        quarter = (day.month - 1) // 3 + 1
        if locale == "en":
            return f"Q{quarter} {day.year}"
        return f"{('I', 'II', 'III', 'IV')[quarter - 1]} кв. {day.year}"
    if frequency in ("monthly",):
        return format_month_year(day, locale)
    return format_date_locale(day, locale)


# ---------------------------------------------------------------- ряды


def year_ago_point(
    points: list[tuple[date, float]], frequency: str,
) -> tuple[date, float] | None:
    """Значение примерно год назад: тот же расчёт, что `yearAgoPoint` фронта."""
    if len(points) < 2:
        return None
    last_day = points[-1][0]
    try:
        target = last_day.replace(year=last_day.year - 1)
    except ValueError:  # 29 февраля
        target = last_day.replace(year=last_day.year - 1, day=28)
    tolerance = timedelta(days=_TOLERANCE_DAYS.get(frequency, _TOLERANCE_DEFAULT))
    best: tuple[date, float] | None = None
    best_gap: timedelta | None = None
    for day, value in reversed(points[:-1]):
        gap = abs(day - target)
        if best_gap is None or gap < best_gap:
            best, best_gap = (day, value), gap
        if day < target - tolerance:
            break
    if best is None or best_gap is None or best_gap > tolerance:
        return None
    return best


async def _overview_for(db: AsyncSession, country) -> tuple[list[dict], dict | None]:
    """«Главное» из Redis-каталога страны; при промахе тот же расчёт без каталога."""
    from app.api import world as world_api
    from app.core.cache import cache_get

    try:
        cached = await cache_get(await world_api.country_detail_cache_key(country.slug))
    except Exception:  # noqa: BLE001 — Redis недоступен: считаем из базы
        logger.warning("country overview cache unavailable", exc_info=True)
        cached = None
    if isinstance(cached, dict) and isinstance(cached.get("overview"), list):
        return list(cached["overview"]), cached.get("country")
    all_inds = await world_api._country_indicators_for_listing(db, country.id)
    return await world_api.build_country_overview(db, country, all_inds), None


async def load_country_key_figures(db: AsyncSession, country) -> dict | None:
    """Предзагрузка «Главного»: до четырёх карточек с точками мини-графика.

    None, если показывать нечего или чтение не удалось (страница страны
    остаётся прежней).
    """
    try:
        return await _load(db, country)
    except Exception:  # noqa: BLE001 — SSR не должен падать из-за блока «Главное»
        logger.warning("country key figures unavailable slug=%s", getattr(country, "slug", ""), exc_info=True)
        return None


async def _load(db: AsyncSession, country) -> dict | None:
    from app.api import world as world_api
    from app.data.eurostat_listing import normalize_frequency
    from app.models import WorldIndicator
    from app.services.locale import get_locale
    from app.services.seo_world import world_listing_light_options
    from app.services.world_rank_values import apply_rank_series, rank_yoy_kind, ranking_value_mode
    from app.services.world_subnational_queries import latest_world_point_series

    overview, country_payload = await _overview_for(db, country)
    items = [item for item in overview if isinstance(item, dict)][:KEY_FIGURES_MAX]
    if not items:
        return None
    codes = [str(item.get("indicator_code") or "") for item in items]
    rows = (
        await db.execute(
            select(WorldIndicator)
            .options(*world_listing_light_options())
            .where(WorldIndicator.country_id == country.id, WorldIndicator.code.in_(codes))
        )
    ).scalars().all()
    by_code = {row.code: row for row in rows}
    tails = await latest_world_point_series(
        db, [row.id for row in rows], limit=_FETCH_LIMIT,
    )

    figures: list[dict] = []
    for item in items:
        indicator = by_code.get(str(item.get("indicator_code") or ""))
        frequency = normalize_frequency(item.get("frequency")) or "annual"
        series: list[tuple[date, float]] = []
        if indicator is not None:
            raw = sorted(tails.get(indicator.id) or [], key=lambda point: point[0])
            mode = ranking_value_mode(str(item.get("concept_slug") or ""), [])
            series = apply_rank_series(raw, mode, yoy_kind=rank_yoy_kind(indicator))
        figure = dict(item)
        if series:
            # Последняя точка из базы главнее кэша каталога: цифры и график из одного снимка.
            figure["date"] = series[-1][0].isoformat()
            figure["value"] = round(series[-1][1], 4)
        keep = _SPARK_POINTS.get(frequency, _SPARK_DEFAULT)
        figure["points"] = [[day.isoformat(), round(value, 4)] for day, value in series[-keep:]]
        figures.append(figure)

    if country_payload is None:
        country_payload = world_api._country_payload(country)
    return {
        "v": BOOTSTRAP_VERSION,
        "slug": country.slug,
        "locale": get_locale(),
        "country": {
            key: country_payload.get(key)
            for key in ("code", "slug", "name", "name_en", "region", "region_en")
        },
        "overview": figures,
    }


# ---------------------------------------------------------------- HTML


def _figure_sentence(figure: dict, slug: str, locale: str) -> str | None:
    """Одна карточка человеческим текстом: название, значение, период, год назад."""
    try:
        value = float(figure["value"])
        day = date.fromisoformat(str(figure["date"])[:10])
    except (KeyError, TypeError, ValueError):
        return None
    concept = str(figure.get("concept_slug") or "")
    labels = _LABELS_EN if locale == "en" else _LABELS_RU
    full_name = (
        (figure.get("name_en") or figure.get("name")) if locale == "en" else figure.get("name")
    ) or ""
    name = labels.get(concept) or str(full_name).strip() or concept
    frequency = str(figure.get("frequency") or "annual")
    unit_text = str(figure.get("unit") or "").strip()
    if locale == "en":
        unit_text = _tidy_unit_en(unit_text)

    scaled = _scale_money(value, unit_text, locale)
    short, long_unit = _split_unit(unit_text)
    if scaled:
        number = _fixed(scaled[0], _digits(scaled[0]), locale)
        unit = scaled[1]
        qualifier = scaled[2]
        caption_extra = (
            _tpl("country_figure_real", "adjusted for inflation" if locale == "en" else "с поправкой на инфляцию")
            if _REAL_QUALIFIER.search(qualifier) else qualifier
        )
    else:
        number = _fixed(value, _digits(value), locale)
        unit = short
        caption_extra = long_unit
        if _YOY_WORDS.search(long_unit):
            # \u00ab\u0438\u0437\u043c\u0435\u043d\u0435\u043d\u0438\u0435 \u0437\u0430 \u0433\u043e\u0434, %\u00bb -> \u00ab11,4 % \u0437\u0430 \u0433\u043e\u0434\u00bb
            unit = f"{short} {_tpl('country_figure_yoy', 'year over year' if locale == 'en' else '\u0437\u0430 \u0433\u043e\u0434')}"
            caption_extra = ""
        elif short == "%" and long_unit.startswith("%") and len(long_unit) > 1:
            # \u00ab% \u044d\u043a\u043e\u043d\u043e\u043c\u0438\u0447\u0435\u0441\u043a\u0438 \u0430\u043a\u0442\u0438\u0432\u043d\u043e\u0433\u043e \u043d\u0430\u0441\u0435\u043b\u0435\u043d\u0438\u044f\u00bb \u0447\u0438\u0442\u0430\u0435\u0442\u0441\u044f \u0441\u0440\u0430\u0437\u0443 \u043f\u043e\u0441\u043b\u0435 \u0447\u0438\u0441\u043b\u0430.
            unit = long_unit
            caption_extra = ""
    shown = f"{number}\u00a0{unit}" if unit else number
    period = _period_text(day, frequency, locale)
    caption = f"{period}, {caption_extra}" if caption_extra else period

    points = []
    for pair in figure.get("points") or []:
        try:
            points.append((date.fromisoformat(str(pair[0])[:10]), float(pair[1])))
        except (TypeError, ValueError, IndexError):
            continue
    ago_text = ""
    ago = year_ago_point(points, frequency)
    if ago is not None:
        if scaled:
            scaled_ago = _scale_money(ago[1], unit_text, locale)
            ago_number = _fixed(scaled_ago[0], _digits(scaled_ago[0]), locale) if scaled_ago else ""
            ago_unit = scaled_ago[1] if scaled_ago else unit
        else:
            ago_number = _fixed(ago[1], _digits(value), locale)
            ago_unit = short
        ago_value = f"{ago_number}\u00a0{ago_unit}" if ago_unit else ago_number
        ago_text = " " + _tpl("country_figure_year_ago", "Год назад: {value}.").format(
            value=escape(ago_value),
        )

    href = paths.indicator(slug, str(figure.get("indicator_code") or ""))
    return (
        f'<li><a href="{escape(href)}"><strong>{escape(str(name))}</strong></a>: '
        f"<strong>{escape(shown)}</strong>, {escape(caption)}.{ago_text}</li>"
    )


def render_key_figures_html(payload: dict | None, slug: str) -> str:
    """Секция «Главное» для тела страницы страны; пусто, если данных нет."""
    if not payload:
        return ""
    from app.services.locale import get_locale

    locale = get_locale()
    rows = [
        sentence
        for sentence in (_figure_sentence(f, slug, locale) for f in payload.get("overview") or [])
        if sentence
    ]
    if not rows:
        return ""
    heading = _tpl("country_h2_main", "Главное")
    return (
        f'<section class="seo-section" id="key-figures"><h2>{escape(heading)}</h2>'
        f"<ul>{''.join(rows)}</ul></section>"
    )


def render_bootstrap_head(payload: dict | None) -> str:
    """Инлайн JSON предзагрузки для приложения (в head, вне #root)."""
    if not payload or not payload.get("overview"):
        return ""
    from app.services.seo_renderer import _json_application_script

    return _json_application_script(element_id=BOOTSTRAP_ELEMENT_ID, data=payload)

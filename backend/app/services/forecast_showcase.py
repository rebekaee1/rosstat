"""Витрина «Прогнозы»: только то, что платформа реально прогнозирует сама.

Источники витрины (проверено по коду 2026-10-05):

- Россия: ``forecasts`` / ``forecast_values`` (стратегии ``forecast_strategies``),
  отдаются как на карточках показателей; инфляция за 12 месяцев считается тем же
  расчётом, что ``/indicators/cpi/inflation``.
- Мир: ``world_forecasts`` / ``world_forecast_values``; публичен только прогноз,
  прошедший строгую проверку на прошлых данных (``publishable_world_forecast``),
  для Евростата ещё и при подтверждённом свежем состоянии набора данных.

Чего здесь нет намеренно: проекции МВФ (WEO) платформа не хранит и не
пересказывает (``world_forecast_policy``: у фонда собственные проекции, их не
подменяем), ключевую ставку и курсы валют не прогнозируем.

Модуль отдаёт готовую структуру для API, SSR и страницы; чистые функции сверху
(расчёт изменения, горизонт, срезы истории) покрыты тестами без БД.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Sequence

logger = logging.getLogger(__name__)

# Горизонт витрины: «на год вперёд». Допускаем 9–15 месяцев между последним
# фактом и концом прогноза (квартальный ряд на 4 квартала, месячный на 12).
MIN_HORIZON_MONTHS = 9
MAX_HORIZON_MONTHS = 15

# Сколько точек истории рисуем рядом с прогнозом (по частоте ряда).
HISTORY_POINTS = {"monthly": 36, "quarterly": 12, "annual": 8}

CACHE_TTL_SECONDS = 1800
CACHE_KEY_REST = "forecast-showcase:v2"  # v2: в ответе нет границ диапазона (только точечный прогноз)

# Темы витрины: порядок вкладок на странице.
THEMES: tuple[dict[str, str], ...] = (
    {"id": "inflation", "ru": "Цены", "en": "Prices"},
    {"id": "gdp", "ru": "Экономика", "en": "Output"},
    {"id": "unemployment", "ru": "Работа", "en": "Jobs"},
    {"id": "rates", "ru": "Ставки", "en": "Rates"},
    {"id": "wages", "ru": "Зарплаты", "en": "Wages"},
)

# Россия: код показателя на платформе -> подписи. Только ряды, у которых
# платформа действительно строит прогноз (forecast_steps > 0 в каталоге).
RUSSIA_ITEMS: tuple[dict[str, Any], ...] = (
    {
        "id": "russia-inflation",
        "code": "cpi",
        "theme": "inflation",
        "kind": "inflation12",
        "title_ru": "Россия: инфляция за 12 месяцев",
        "title_en": "Russia: inflation over 12 months",
        "unit_ru": "% за 12 месяцев",
        "unit_en": "% over 12 months",
    },
    {
        "id": "russia-gdp",
        "code": "gdp-real",
        "theme": "gdp",
        "kind": "level",
        "title_ru": "Россия: ВВП в постоянных ценах",
        "title_en": "Russia: GDP at constant prices",
    },
    {
        "id": "russia-unemployment",
        "code": "unemployment",
        "theme": "unemployment",
        "kind": "percent",
        "title_ru": "Россия: безработица",
        "title_en": "Russia: unemployment rate",
        "unit_ru": "% рабочей силы",
        "unit_en": "% of the labour force",
    },
    {
        "id": "russia-mortgage",
        "code": "mortgage-rate",
        "theme": "rates",
        "kind": "percent",
        "title_ru": "Россия: ставка по ипотеке",
        "title_en": "Russia: mortgage rate",
        "unit_ru": "% годовых",
        "unit_en": "% per year",
    },
    {
        "id": "russia-wages",
        "code": "wages-nominal",
        "theme": "wages",
        "kind": "level",
        "title_ru": "Россия: средняя зарплата",
        "title_en": "Russia: average wage",
    },
)

# Мир: тема -> концепт каталога и тип величины. ``max_items`` держит страницу
# короткой; страны берутся в порядке PRIORITY_SLUGS.
WORLD_THEMES: tuple[dict[str, Any], ...] = (
    {
        "theme": "inflation",
        "concept": "hicp-index",
        "kind": "level",
        "title_ru": "{country}: цены",
        "title_en": "{country}: consumer prices",
        "max_items": 4,
    },
    {
        "theme": "unemployment",
        "concept": "unemployment-rate",
        "kind": "percent",
        "title_ru": "{country}: безработица",
        "title_en": "{country}: unemployment rate",
        "max_items": 4,
    },
    {
        "theme": "gdp",
        "concept": "gdp-volume-quarterly",
        "kind": "level",
        "title_ru": "{country}: ВВП в постоянных ценах",
        "title_en": "{country}: GDP at constant prices",
        "max_items": 4,
    },
)

PRIORITY_SLUGS: tuple[str, ...] = (
    "united-states", "germany", "france", "united-kingdom", "japan", "canada",
    "italy", "spain", "china", "india", "brazil", "mexico", "south-korea",
    "australia", "netherlands", "poland", "turkey",
)

# Национальные ряды цен, у которых величина уже «изменение за год» либо
# индекс «к тому же месяцу прошлого года»: уровень индекса к прошлому месяцу
# для них не определён, в витрину они не берутся (см. world_concept_national).
_YOY_NATIONAL_PRICE_CODES = frozenset({"cn-cpi-all", "br-cpi-ipca-yoy"})


# ---------------------------------------------------------------------------
# Чистые функции
# ---------------------------------------------------------------------------


def months_between(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month)


def horizon_ok(last_actual: date | None, last_forecast: date | None) -> bool:
    """Конец прогноза должен лежать примерно через год после последнего факта."""
    if last_actual is None or last_forecast is None:
        return False
    return MIN_HORIZON_MONTHS <= months_between(last_actual, last_forecast) <= MAX_HORIZON_MONTHS


def compute_change(kind: str, last_value: float, end_value: float) -> dict[str, Any] | None:
    """Изменение от последнего факта до конца прогноза.

    ``percent`` — ряд уже в процентах (безработица, ставка, инфляция за год):
    считаем разницу в процентных пунктах. ``level`` — уровень (индекс цен,
    ВВП, зарплата): считаем относительное изменение в процентах.
    """
    if kind == "percent":
        value = end_value - last_value
        unit = "points"
    else:
        if last_value == 0 or last_value < 0:
            return None
        value = (end_value / last_value - 1.0) * 100.0
        unit = "percent"
    value = round(value, 4)
    if abs(value) < 0.05:
        direction = "flat"
    else:
        direction = "up" if value > 0 else "down"
    return {"unit": unit, "value": value, "direction": direction}


def _decimal(value: float, digits: int, locale: str) -> str:
    text = f"{abs(value):.{digits}f}"
    return text if locale == "en" else text.replace(".", ",")


def change_phrase(change: dict[str, Any], locale: str) -> str:
    """Изменение словами: «ниже на 0,3 пункта», «выше на 2,5 %», «down 0.3 percentage points»."""
    direction = change.get("direction")
    value = float(change.get("value") or 0.0)
    en = locale == "en"
    if direction == "flat":
        return "about the same" if en else "почти без изменений"
    up = direction == "up"
    if change.get("unit") == "points":
        number = _decimal(value, 1, locale)
        if en:
            return f"{'up' if up else 'down'} {number} percentage points"
        return f"{'выше' if up else 'ниже'} на {number} пункта"
    number = _decimal(value, 1, locale)
    if en:
        return f"{'up' if up else 'down'} {number}%"
    return f"{'выше' if up else 'ниже'} на {number} %"


def tail_points(points: Sequence[tuple[date, float]], frequency: str) -> list[tuple[date, float]]:
    limit = HISTORY_POINTS.get(frequency, 12)
    return list(points)[-limit:]


def _point(day: date, value: float) -> dict[str, Any]:
    return {"date": day.isoformat(), "value": round(float(value), 4)}


def build_item(
    *,
    item_id: str,
    scope: str,
    theme: str,
    kind: str,
    title: str,
    country: dict[str, str],
    unit: str,
    frequency: str,
    source: str,
    path: str,
    actual: Sequence[tuple[date, float]],
    forecast: Sequence[tuple[date, float]],
    updated: date | None,
    verified: bool,
) -> dict[str, Any] | None:
    """Карточка витрины или None, если ряд не годится для честной подачи."""
    if not actual or not forecast:
        return None
    last_day, last_value = actual[-1]
    future = [row for row in forecast if row[0] > last_day]
    if not future:
        return None
    end_day, end_value = future[-1]
    if not horizon_ok(last_day, end_day):
        return None
    change = compute_change(kind, last_value, end_value)
    if change is None:
        return None
    change["horizon_months"] = months_between(last_day, end_day)
    return {
        "id": item_id,
        "scope": scope,
        "theme": theme,
        "kind": kind,
        "title": title,
        "country": country,
        "unit": unit,
        "frequency": frequency,
        "source": source,
        "path": path,
        "last_actual": _point(last_day, last_value),
        "forecast_end": _point(end_day, end_value),
        "change": change,
        "history": [_point(d, v) for d, v in tail_points(actual, frequency)],
        "forecast": [_point(d, v) for d, v in future],
        "updated": updated.isoformat() if updated else None,
        "verified": verified,
    }


def pick_world_candidates(
    candidates: Sequence[dict[str, Any]], *, max_items: int,
) -> list[dict[str, Any]]:
    """По одной записи на страну, страны крупных экономик первыми."""
    best: dict[str, dict[str, Any]] = {}
    for cand in candidates:
        slug = cand["country_slug"]
        current = best.get(slug)
        # При двух рядах у страны берём тот, чей факт свежее.
        if current is None or (cand["history_end"] or date.min) > (current["history_end"] or date.min):
            best[slug] = cand

    def rank(slug: str) -> tuple[int, str]:
        try:
            return (PRIORITY_SLUGS.index(slug), slug)
        except ValueError:
            return (len(PRIORITY_SLUGS), slug)

    return [best[s] for s in sorted(best, key=rank)][:max_items]


def empty_payload(locale: str) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "locale": locale,
        "themes": [{"id": t["id"], "name": t[locale if locale in ("ru", "en") else "ru"]} for t in THEMES],
        "items": [],
    }


# ---------------------------------------------------------------------------
# Сборка из базы
# ---------------------------------------------------------------------------


async def _russia_items(db, locale: str) -> list[dict[str, Any]]:
    from sqlalchemy import desc, select

    from app.models import Forecast, ForecastValue, Indicator, IndicatorData
    from app.services import site_paths as paths
    from app.services.seo_i18n import translate_source

    items: list[dict[str, Any]] = []
    for spec in RUSSIA_ITEMS:
        try:
            ind = (
                await db.execute(select(Indicator).where(Indicator.code == spec["code"]))
            ).scalar_one_or_none()
            if ind is None or not ind.is_active:
                continue
            title = spec["title_en"] if locale == "en" else spec["title_ru"]
            country = {
                "slug": "russia",
                "code": "RU",
                "name": "Russia" if locale == "en" else "Россия",
            }
            if spec["kind"] == "inflation12":
                from app.api.forecasts import get_inflation

                resp = await get_inflation(spec["code"], db)
                data = resp if isinstance(resp, dict) else resp.model_dump(mode="json")
                actual = [
                    (date.fromisoformat(str(p["date"])), float(p["value"]))
                    for p in data.get("actuals") or []
                ]
                fc = [
                    (
                        date.fromisoformat(str(p["date"])),
                        float(p["value"]),
                    )
                    for p in data.get("forecast") or []
                ]
                kind, unit = "percent", spec["unit_en"] if locale == "en" else spec["unit_ru"]
                # Те же даты у факта и прогноза в первом числе месяца.
                updated = None
            else:
                forecast = (
                    await db.execute(
                        select(Forecast)
                        .where(
                            Forecast.indicator_id == ind.id,
                            Forecast.is_current,
                            ~Forecast.model_name.like("Inflation-12M%"),
                        )
                        .order_by(desc(Forecast.created_at))
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if forecast is None:
                    continue
                rows = (
                    await db.execute(
                        select(ForecastValue)
                        .where(ForecastValue.forecast_id == forecast.id)
                        .order_by(ForecastValue.date)
                    )
                ).scalars().all()
                fc = [
                    (
                        r.date,
                        float(r.value),
                    )
                    for r in rows
                ]
                hist = (
                    await db.execute(
                        select(IndicatorData.date, IndicatorData.value)
                        .where(IndicatorData.indicator_id == ind.id)
                        .order_by(desc(IndicatorData.date))
                        .limit(HISTORY_POINTS.get(ind.frequency, 12) + 1)
                    )
                ).all()
                actual = [(d, float(v)) for d, v in reversed(hist)]
                kind = spec["kind"]
                unit = (
                    spec.get("unit_en" if locale == "en" else "unit_ru")
                    or (ind.unit or "").strip()
                )
                updated = forecast.created_at.date() if forecast.created_at else None
            item = build_item(
                item_id=spec["id"],
                scope="russia",
                theme=spec["theme"],
                kind=kind,
                title=title,
                country=country,
                unit=unit,
                frequency=ind.frequency,
                source=translate_source(ind.source, locale) or ind.source,
                path=paths.russia_indicator(spec["code"]),
                actual=actual,
                forecast=fc,
                updated=updated,
                verified=False,
            )
            if item is not None:
                items.append(item)
        except Exception:  # noqa: BLE001 — одна карточка не должна ронять витрину
            logger.warning("forecast showcase: Russia item %s skipped", spec["id"], exc_info=True)
    return items


def _theme_for_world(indicator: Any, spec: dict[str, Any]) -> bool:
    """Ряд страны подходит под тему: тот же концепт и подходящий смысл величины."""
    from app.data.world_concept_national import concept_slug_for_national_code
    from app.data.world_concepts import concept_for_indicator

    if str(getattr(indicator, "provider", "") or "").lower() == "imf":
        return False
    if indicator.code in _YOY_NATIONAL_PRICE_CODES:
        return False
    if str(indicator.frequency or "").lower() not in {"monthly", "quarterly"}:
        return False
    concept = concept_for_indicator(indicator)
    slug = concept.slug if concept is not None else concept_slug_for_national_code(indicator.code)
    return slug == spec["concept"]


async def _world_items(db, locale: str) -> list[dict[str, Any]]:
    from sqlalchemy import or_, select

    from app.data.world_concept_national import national_codes_for_concept
    from app.data.world_concepts import CONCEPT_BY_SLUG
    from app.models import WorldCountry, WorldDataPoint, WorldForecast, WorldForecastValue, WorldIndicator
    from app.services import site_paths as paths
    from app.services.seo_i18n import translate_source
    from app.services.world_forecast_pipeline import world_forecast_source_ready
    from app.services.world_forecaster import PUBLISHED_GATE_STATUSES, publishable_world_forecast

    items: list[dict[str, Any]] = []
    for spec in WORLD_THEMES:
        try:
            concept = CONCEPT_BY_SLUG.get(spec["concept"])
            if concept is None:
                continue
            datasets: set[str] = set(concept.dataset_ids)
            for ids in (concept.provider_dataset_ids or {}).values():
                datasets |= set(ids)
            codes = national_codes_for_concept(spec["concept"])
            conditions = []
            if datasets:
                conditions.append(WorldIndicator.dataset_id.in_(sorted(datasets)))
            if codes:
                conditions.append(WorldIndicator.code.in_(sorted(codes)))
            if not conditions:
                continue
            rows = (
                await db.execute(
                    select(WorldForecast, WorldIndicator, WorldCountry)
                    .join(WorldIndicator, WorldForecast.world_indicator_id == WorldIndicator.id)
                    .join(WorldCountry, WorldIndicator.country_id == WorldCountry.id)
                    .where(
                        WorldForecast.is_current,
                        WorldForecast.gate_status.in_(PUBLISHED_GATE_STATUSES),
                        WorldIndicator.is_listed,
                        or_(*conditions),
                    )
                    .order_by(WorldForecast.created_at.desc())
                )
            ).all()
            seen_indicators: set[int] = set()
            candidates: list[dict[str, Any]] = []
            for forecast, ind, country in rows:
                if ind.id in seen_indicators:
                    continue
                if not publishable_world_forecast(forecast) or not _theme_for_world(ind, spec):
                    continue
                if not await world_forecast_source_ready(db, ind, forecast=forecast):
                    continue
                seen_indicators.add(ind.id)
                candidates.append({
                    "forecast": forecast,
                    "indicator": ind,
                    "country": country,
                    "country_slug": country.slug,
                    "history_end": ind.history_end,
                })
            for cand in pick_world_candidates(candidates, max_items=spec["max_items"]):
                forecast, ind, country = cand["forecast"], cand["indicator"], cand["country"]
                values = (
                    await db.execute(
                        select(WorldForecastValue)
                        .where(WorldForecastValue.forecast_id == forecast.id)
                        .order_by(WorldForecastValue.date)
                    )
                ).scalars().all()
                limit = HISTORY_POINTS.get(str(ind.frequency).lower(), 12) + 1
                hist = (
                    await db.execute(
                        select(WorldDataPoint.date, WorldDataPoint.value)
                        .where(WorldDataPoint.indicator_id == ind.id)
                        .order_by(WorldDataPoint.date.desc())
                        .limit(limit)
                    )
                ).all()
                actual = [(d, float(v)) for d, v in reversed(hist)]
                fc = [
                    (
                        v.date,
                        float(v.value),
                    )
                    for v in values
                ]
                name = country.name_en if locale == "en" and (country.name_en or "").strip() else country.name_ru
                title = (spec["title_en"] if locale == "en" else spec["title_ru"]).format(country=name)
                unit = _world_unit(ind, locale)
                item = build_item(
                    item_id=f"{country.slug}-{spec['theme']}",
                    scope="world",
                    theme=spec["theme"],
                    kind=spec["kind"],
                    title=title,
                    country={"slug": country.slug, "code": country.code, "name": name},
                    unit=unit,
                    frequency=str(ind.frequency).lower(),
                    source=translate_source(ind.source, locale) or ind.source,
                    path=paths.indicator(country.slug, ind.code),
                    actual=actual,
                    forecast=fc,
                    updated=forecast.created_at.date() if forecast.created_at else None,
                    verified=True,
                )
                if item is not None:
                    items.append(item)
        except Exception:  # noqa: BLE001
            logger.warning("forecast showcase: world theme %s skipped", spec["theme"], exc_info=True)
    return items


def _world_unit(indicator: Any, locale: str) -> str:
    """Подпись единицы: для Евростата из концепта, для национальных рядов из каталога."""
    from app.data.world_concepts import concept_for_indicator

    own = concept_for_indicator(indicator)
    if own is not None:
        text = (own.unit_en or own.unit_ru) if locale == "en" else own.unit_ru
        return text or ""
    if locale == "en":
        from app.services.display import public_unit_en

        return public_unit_en(indicator.unit_ru, unit_storage=indicator.unit)
    return (indicator.unit_ru or indicator.unit or "").strip()


def _theme_order(theme: str) -> int:
    for index, row in enumerate(THEMES):
        if row["id"] == theme:
            return index
    return len(THEMES)


async def build_showcase(db, locale: str) -> dict[str, Any]:
    """Полная витрина: Россия первой, затем мир; внутри — по теме."""
    locale = "en" if locale == "en" else "ru"
    payload = empty_payload(locale)
    items = await _russia_items(db, locale) + await _world_items(db, locale)
    items.sort(key=lambda it: (_theme_order(it["theme"]), 0 if it["scope"] == "russia" else 1))
    present = {it["theme"] for it in items}
    payload["themes"] = [t for t in payload["themes"] if t["id"] in present]
    payload["items"] = items
    return payload

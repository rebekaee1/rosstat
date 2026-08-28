"""Подмешивание России в снапшот/карту/SSR рейтинга из отечественных рядов.

Одна точка правды: и API (`/compare/map-series`, `/compare/snapshot`), и SEO
вызывают эти функции. Клиент значения России не пересчитывает.

ВВП в долларах (gdp-usd, gdp-per-capita-usd) для России считается здесь же
по национальной методологии платформы (директива владельца 2026-08, «НА
правки 16»): годовой номинальный ВВП Росстата (gdp-nominal-annual, млрд руб.)
пересчитывается в миллиарды долларов по среднегодовому официальному курсу
Банка России (usd-rub-avg-year, среднее дневных курсов за календарный год);
ВВП на душу — полученный ВВП в долларах, делённый на численность населения
России Росстата того же года. Годы — только завершённые: gdp-nominal-annual
пишется лишь за год с четырьмя кварталами, usd-rub-avg-year — лишь за год
с двенадцатью месяцами, а сама формула берёт пересечение годов трёх рядов.
Ряды МВФ для России (weo-gdp-usd и пр.) остаются в каталоге отдельными
карточками и служат резервным источником, если национальные ряды недоступны.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.world_concept_russia import (
    RUSSIA_COUNTRY_PAYLOAD,
    RussiaConceptLink,
    russia_link_for_concept,
)
from app.models import Indicator, IndicatorData
from app.services.world_rank_values import (
    RankMode,
    yearly_last_points,
)

# Концепты, где значение России переопределяется национальным расчётом
# (Росстат × курс Банка России) до применения универсального link-механизма.
_GDP_USD_METHOD_CONCEPTS = frozenset({"gdp-usd", "gdp-per-capita-usd"})

_GDP_RUB_CODE = "gdp-nominal-annual"
_USD_RUB_AVG_CODE = "usd-rub-avg-year"
_POPULATION_CODE = "population"

_GDP_SOURCE_RU = "Росстат, Банк России"
_GDP_SOURCE_EN = "Rosstat, Bank of Russia"


def gdp_usd_by_year_from_parts(
    gdp_rub: dict[int, float],
    usd_rub: dict[int, float],
    population_mln: dict[int, float],
) -> tuple[dict[int, float], dict[int, float]]:
    """Национальный расчёт: (ВВП млрд $ по годам, ВВП $ на душу по годам).

    Чистая функция по пересечению годов: ВВП-USD требует ВВП в рублях и курс,
    на душу дополнительно население. Год без курса в расчёт не попадает,
    год без населения — только из пер-капиты. Незакрывшийся календарный год
    исключён: годовой итог ещё не состоялся.
    """
    running_year = date.today().year
    gdp_usd: dict[int, float] = {}
    per_capita: dict[int, float] = {}
    for year, rub in gdp_rub.items():
        if year >= running_year:
            continue
        rate = usd_rub.get(year)
        if rate is None or rate <= 0:
            continue
        usd_bln = rub / rate
        gdp_usd[year] = round(usd_bln, 4)
        pop = population_mln.get(year)
        if pop is None or pop <= 0:
            continue
        # млрд $ → $ (1e9) / млн чел. (1e6) = тыс. $ на человека × 1000.
        per_capita[year] = round(usd_bln * 1e9 / (pop * 1e6), 1)
    return gdp_usd, per_capita


async def _annual_last_points(
    db: AsyncSession,
    indicator_code: str,
) -> dict[int, tuple[date, float]]:
    """Год → (дата, значение) годового ряда; пусто, если ряда нет."""
    indicator = (
        await db.execute(select(Indicator).where(Indicator.code == indicator_code))
    ).scalar_one_or_none()
    if indicator is None:
        return {}
    rows = (
        await db.execute(
            select(IndicatorData.date, IndicatorData.value)
            .where(IndicatorData.indicator_id == indicator.id)
            .order_by(IndicatorData.date)
        )
    ).all()
    out: dict[int, tuple[date, float]] = {}
    for point_date, value in rows:
        if value is None:
            continue
        out[point_date.year] = (point_date, float(value))
    return out


async def _gdp_usd_method_yearly_items(
    db: AsyncSession,
    concept_slug: str,
    *,
    public_unit: str,
) -> dict[str, dict[str, Any]] | None:
    """Годовые корзины России по национальному расчёту; None → резервный путь.

    Единица входа: ВВП Росстата млрд руб., курс руб. за доллар, население
    млн человек. Единица выхода задаётся ``public_unit`` концепта
    (gdp-usd: млрд $; gdp-per-capita-usd: $ на человека).
    """
    gdp_yearly = await _annual_last_points(db, _GDP_RUB_CODE)
    fx_yearly = await _annual_last_points(db, _USD_RUB_AVG_CODE)
    if not gdp_yearly or not fx_yearly:
        return None
    gdp_rub = {year: value for year, (_d, value) in gdp_yearly.items()}
    usd_rub = {year: value for year, (_d, value) in fx_yearly.items()}
    population_mln: dict[int, float] = {}
    if concept_slug == "gdp-per-capita-usd":
        pop_yearly = await _annual_last_points(db, _POPULATION_CODE)
        population_mln = {
            year: value for year, (_d, value) in pop_yearly.items()
        }
        if not population_mln:
            return None
    gdp_usd, per_capita = gdp_usd_by_year_from_parts(
        gdp_rub, usd_rub, population_mln,
    )
    yearly_values = per_capita if concept_slug == "gdp-per-capita-usd" else gdp_usd
    if not yearly_values:
        return None
    from app.services.locale import get_locale

    en = get_locale() == "en"
    country_name = "Russia" if en else "Россия"
    source = _GDP_SOURCE_EN if en else _GDP_SOURCE_RU
    out: dict[str, dict[str, Any]] = {}
    for year, value in yearly_values.items():
        point_date, _raw = gdp_yearly[year]
        out[str(year)] = {
            "country_code": "RU",
            "country_slug": "russia",
            "country_name": country_name,
            "indicator_code": _GDP_RUB_CODE,
            "date": point_date.isoformat(),
            "value": value,
            "unit": public_unit,
            "source": source,
            "frequency": "annual",
        }
    return out


def russia_country_public() -> dict[str, Any]:
    """Публичный каркас страны для каталога карты (без значения)."""
    from app.services.locale import get_locale

    payload = dict(RUSSIA_COUNTRY_PAYLOAD)
    if get_locale() == "en":
        payload["name"] = (payload.get("name_en") or "Russia").strip() or "Russia"
    return payload


def russia_meta_for_concept(concept_slug: str) -> dict[str, Any] | None:
    from app.services.locale import get_locale

    link = russia_link_for_concept(concept_slug)
    if link is None:
        return None
    note = link.note_ru
    if get_locale() == "en" and (link.note_en or "").strip():
        note = link.note_en
    return {
        "eligible": True,
        "indicator_code": link.indicator_code,
        "note": note,
        "country": russia_country_public(),
    }


async def _load_indicator_series(
    db: AsyncSession,
    indicator_code: str,
) -> tuple[Indicator, list[tuple[date, float]]] | None:
    indicator = (
        await db.execute(
            select(Indicator).where(Indicator.code == indicator_code)
        )
    ).scalar_one_or_none()
    if indicator is None:
        return None
    rows = (
        await db.execute(
            select(IndicatorData.date, IndicatorData.value)
            .where(IndicatorData.indicator_id == indicator.id)
            .order_by(IndicatorData.date)
        )
    ).all()
    series = [(d, float(v)) for d, v in rows if v is not None]
    if not series:
        return None
    return indicator, series


def _scaled_series(
    series: list[tuple[date, float]],
    link: RussiaConceptLink,
) -> list[tuple[date, float]]:
    if link.scale == 1.0:
        return series
    return [(d, float(v) * link.scale) for d, v in series]


def _rank_mode_for_link(link: RussiaConceptLink, concept_mode: RankMode) -> RankMode:
    # cpi-yoy уже годовое изменение: второй YoY превратил бы % в бессмыслицу.
    if link.value_kind == "yoy_ready":
        return "level"
    return concept_mode


async def russia_yearly_by_code(
    db: AsyncSession,
    concept_slug: str,
    *,
    concept_mode: RankMode,
    public_unit: str,
) -> dict[str, dict[str, Any]]:
    """Год → элемент values_by_year[year]['RU'] или пусто, если ряда нет."""
    # ВВП в долларах — национальный расчёт (Росстат × курс Банка России);
    # МВФ-ряд — резерв, если национальные ряды недоступны.
    if concept_slug in _GDP_USD_METHOD_CONCEPTS:
        method_items = await _gdp_usd_method_yearly_items(
            db, concept_slug, public_unit=public_unit,
        )
        if method_items is not None:
            return method_items
    link = russia_link_for_concept(concept_slug)
    if link is None:
        return {}
    loaded = await _load_indicator_series(db, link.indicator_code)
    if loaded is None:
        return {}
    _indicator, series = loaded
    series = _scaled_series(series, link)
    mode = _rank_mode_for_link(link, concept_mode)
    from app.services.locale import get_locale
    from app.services.seo_i18n import translate_source

    loc = get_locale()
    country_name = "Russia" if loc == "en" else "Россия"
    if loc == "en" and (link.source_en or "").strip():
        source = link.source_en
    elif (link.source_ru or "").strip():
        source = translate_source(link.source_ru, loc) or link.source_ru
    else:
        source = translate_source("Росстат", loc) or (
            "Rosstat" if loc == "en" else "Росстат"
        )
    out: dict[str, dict[str, Any]] = {}
    for year, (point_date, value) in yearly_last_points(
        series, mode, concept_slug=concept_slug,
    ).items():
        out[str(year)] = {
            "country_code": "RU",
            "country_slug": "russia",
            "country_name": country_name,
            "indicator_code": link.indicator_code,
            "date": point_date.isoformat(),
            "value": round(float(value), 4),
            "unit": public_unit,
            "source": source,
            "frequency": getattr(_indicator, "frequency", None),
        }
    return out


async def merge_russia_into_values_by_year(
    db: AsyncSession,
    concept_slug: str,
    values_by_year: dict[str, dict[str, dict]],
    *,
    concept_mode: RankMode,
    public_unit: str,
) -> dict[str, Any] | None:
    """Вписывает RU в годовые корзины. Возвращает russia meta или None."""
    meta = russia_meta_for_concept(concept_slug)
    if meta is None:
        return None
    yearly = await russia_yearly_by_code(
        db,
        concept_slug,
        concept_mode=concept_mode,
        public_unit=public_unit,
    )
    for year, item in yearly.items():
        values_by_year.setdefault(year, {})["RU"] = item
    return meta


async def russia_latest_snapshot_item(
    db: AsyncSession,
    concept_slug: str,
    *,
    concept_mode: RankMode,
    public_unit: str,
) -> dict[str, Any] | None:
    yearly = await russia_yearly_by_code(
        db,
        concept_slug,
        concept_mode=concept_mode,
        public_unit=public_unit,
    )
    if not yearly:
        return None
    latest_year = max(int(y) for y in yearly)
    item = dict(yearly[str(latest_year)])
    item.pop("frequency", None)
    return item


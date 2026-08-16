"""Подмешивание России в снапшот/карту/SSR рейтинга из отечественных рядов.

Одна точка правды: и API (`/compare/map-series`, `/compare/snapshot`), и SEO
вызывают эти функции. Клиент значения России не пересчитывает.
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


def russia_country_public() -> dict[str, Any]:
    """Публичный каркас страны для каталога карты (без значения)."""
    return dict(RUSSIA_COUNTRY_PAYLOAD)


def russia_meta_for_concept(concept_slug: str) -> dict[str, Any] | None:
    link = russia_link_for_concept(concept_slug)
    if link is None:
        return None
    return {
        "eligible": True,
        "indicator_code": link.indicator_code,
        "note": link.note_ru,
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
    link = russia_link_for_concept(concept_slug)
    if link is None:
        return {}
    loaded = await _load_indicator_series(db, link.indicator_code)
    if loaded is None:
        return {}
    _indicator, series = loaded
    series = _scaled_series(series, link)
    mode = _rank_mode_for_link(link, concept_mode)
    out: dict[str, dict[str, Any]] = {}
    for year, (point_date, value) in yearly_last_points(series, mode).items():
        out[str(year)] = {
            "country_code": "RU",
            "country_slug": "russia",
            "country_name": "Россия",
            "indicator_code": link.indicator_code,
            "date": point_date.isoformat(),
            "value": round(float(value), 4),
            "unit": public_unit,
            "source": "Росстат",
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


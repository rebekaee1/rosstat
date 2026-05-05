"""ETL: ключевая ставка ЦБ (cbr.ru hd_base/KeyRate) → IndicatorData.

Особенность: после bulk_upsert парсер дополнительно ищет последнее решение
СД ЦБ из пресс-релиза (ставка вступает в силу со следующего рабочего дня
после публикации в 13:30 МСК). Если эта точка новее последней в hd_base —
добавляется отдельной точкой («опережающее» значение). Это сделано через
override `_post_upsert(...)`.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import ClassVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator, IndicatorData
from app.services.base_parser import BaseParser
from app.services.cbr_keyrate import (
    DataPoint,
    fetch_key_rate_html,
    parse_keyrate_html,
    get_latest_keyrate_announcement,
)
from app.services.forecast_pipeline import clear_current_forecasts, retrain_indicator_forecast
from app.services.upsert import bulk_upsert

logger = logging.getLogger(__name__)

DEFAULT_BACKFILL_FROM = date(2013, 9, 13)


class CbrKeyRateParser(BaseParser):
    parser_type: ClassVar[str] = "cbr_keyrate_html"

    async def _fetch_and_parse(
        self,
        db: AsyncSession,
        indicator: Indicator,
        cfg: dict,
        fetch_log: FetchLog,
    ) -> tuple[list, str]:
        date_to = date.today()

        existing_n = (
            await db.execute(
                select(func.count(IndicatorData.id)).where(IndicatorData.indicator_id == indicator.id)
            )
        ).scalar() or 0

        if cfg.get("backfill_from"):
            date_from = date.fromisoformat(cfg["backfill_from"])
        elif existing_n == 0:
            date_from = DEFAULT_BACKFILL_FROM
        else:
            win = int(cfg.get("incremental_fetch_days", 150))
            date_from = date_to - timedelta(days=win)

        html, final_url = await asyncio.to_thread(fetch_key_rate_html, date_from, date_to)
        points: list[DataPoint] = await asyncio.to_thread(parse_keyrate_html, html)
        return points, final_url

    async def _post_upsert(
        self,
        db: AsyncSession,
        indicator: Indicator,
        cfg: dict,
        fetch_log: FetchLog,
        points: list,
        records_added: int,
        records_updated: int,
    ) -> tuple[int, int]:
        """Добавить опережающую точку из пресс-релиза СД ЦБ, если она новее
        последней в ряду и отличается от последней ставки.

        ЦБ публикует решение в 13:30 МСК; новая ставка вступает в силу
        со следующего рабочего дня. В hd_base она появится только тогда же,
        и сайт «висит» с устаревшим значением до тех пор. Чтобы карточка
        ставки сразу показывала актуальное значение, добавляем точку из
        пресс-релиза (`get_latest_keyrate_announcement`).
        """
        try:
            ann = await asyncio.to_thread(get_latest_keyrate_announcement)
        except Exception:
            ann = None
            logger.exception("Press-release lookup failed (non-critical)")

        if ann is None or ann.rate is None or not points:
            return 0, 0

        last_in_series = points[-1]
        last_value = float(last_in_series.value)
        last_date = last_in_series.date

        # (а) дата вступления в силу > последней даты в ряду,
        # (б) ставка отличается от последней (защита от no-op для решения
        #     «оставить»),
        # (в) дата объявления ≥ дата последней точки (нет регрессии
        #     устаревшим решением).
        if (
            ann.effective_date > last_date
            and ann.decision_date >= last_date
            and abs(float(ann.rate) - last_value) > 1e-9
        ):
            extra_added, extra_updated = await bulk_upsert(
                db, indicator.id,
                [DataPoint(date=ann.effective_date, value=float(ann.rate))],
            )
            logger.info(
                "Press-release announcement applied: %s — %s (added=%d, updated=%d)",
                ann, indicator.code, extra_added, extra_updated,
            )
            return extra_added, extra_updated

        logger.info(
            "Press-release announcement %s — already in series or stale, skip",
            ann,
        )
        return 0, 0

    async def _handle_forecasts(
        self,
        db: AsyncSession,
        indicator: Indicator,
        cfg: dict,
        records_added: int,
        records_updated: int,
    ) -> None:
        """Особое поведение: при steps==0 чистим текущие прогнозы (key-rate
        не прогнозируется — мы публикуем только реакцию на решения СД ЦБ).
        """
        steps = int(cfg.get("forecast_steps", 12) or 0)
        if steps > 0:
            if records_added > 0 or records_updated > 0:
                await retrain_indicator_forecast(db, indicator)
            return

        removed = await clear_current_forecasts(db, indicator)
        if removed:
            logger.info("Removed %d stale forecast(s) for '%s'", removed, indicator.code)

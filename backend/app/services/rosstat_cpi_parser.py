"""ETL: Росстат CPI XLSX → IndicatorData (реализация BaseParser)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import ClassVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator, IndicatorData
from app.services.base_parser import BaseParser
from app.services.cbr_keyrate_parser import CbrKeyRateParser
from app.services.cbr_fx_parser import CbrFxParser
from app.services.cbr_ruonia_parser import CbrRuoniaParser
from app.services.cbr_monetary_parser import CbrMonetaryParser
from app.services.cbr_dataservice_parser import CbrDataServiceParser
from app.services.rosstat_labor_parser import RosstatLaborParser
from app.services.rosstat_gdp_parser import RosstatGdpParser
from app.services.data_validator import validate_points
from app.services.fetcher import RosstatFetcher
from app.services.upsert import bulk_upsert
from app.services.forecast_pipeline import retrain_indicator_forecast
from app.services.parser import parse_cpi_sheet
from app.core.cache import cache_invalidate_indicator

logger = logging.getLogger(__name__)


class RosstatCpiParser(BaseParser):
    parser_type: ClassVar[str] = "rosstat_cpi_xlsx"

    async def run(self, db: AsyncSession, indicator: Indicator, fetch_log: FetchLog) -> None:
        indicator_code = indicator.code
        try:
            fetcher = RosstatFetcher()
            try:
                content, source_url = await asyncio.to_thread(fetcher.fetch_latest)
            finally:
                fetcher.session.close()

            if not content:
                fetch_log.status = "failed"
                fetch_log.error_message = "No file available on Rosstat"
                fetch_log.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                await db.commit()
                return

            fetch_log.source_url = source_url

            sheet = indicator.excel_sheet or "01"
            points = await asyncio.to_thread(parse_cpi_sheet, content, sheet)
            cfg = indicator.model_config_json or {}
            points = validate_points(points, cfg)

            for p in points:
                if p.value < 90 or p.value > 200:
                    logger.warning("Suspicious CPI value %.2f for %s at %s", p.value, indicator_code, p.date)

            if not points:
                fetch_log.status = "failed"
                fetch_log.error_message = "Parser returned 0 data points"
                fetch_log.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                await db.commit()
                return

            records_added, records_updated = await bulk_upsert(db, indicator.id, points)
            logger.info(
                "Upserted %d new, %d updated for '%s'",
                records_added, records_updated, indicator_code,
            )
            fetch_log.records_added = records_added

            if records_added > 0 or records_updated > 0:
                await retrain_indicator_forecast(db, indicator)
                await cache_invalidate_indicator(indicator_code)

            fetch_log.status = "success" if (records_added > 0 or records_updated > 0) else "no_new_data"
            fetch_log.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await db.commit()

            logger.info("ETL complete for '%s': %d new, %d updated", indicator_code, records_added, records_updated)

        except Exception as e:
            logger.exception("ETL failed for '%s'", indicator_code)
            await db.rollback()
            fetch_log.status = "failed"
            fetch_log.error_message = str(e)[:500]
            fetch_log.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.add(fetch_log)
            await db.commit()


from app.services.cbr_dataservice_sum_parser import CbrDataServiceSumParser
from app.services.minfin_budget_parser import MinfinBudgetParser
from app.services.rosstat_weekly_inflation_parser import RosstatWeeklyCpiParser
from app.services.rosstat_ipi_parser import RosstatIpiParser
from app.services.rosstat_housing_parser import RosstatHousingParser
from app.services.rosstat_population_parser import RosstatPopulationParser
from app.services.rosstat_ppi_parser import RosstatPpiParser
from app.services.cbr_bop_parser import CbrBopParser
from app.services.cbr_reserves_parser import CbrReservesParser
from app.services.cbr_debt_parser import CbrDebtParser
from app.services.cbr_gold_parser import CbrGoldParser
from app.services.rosstat_demo_parser import RosstatDemoParser
from app.services.rosstat_ind_parser import RosstatIndParser
from app.services.rosstat_science_parser import RosstatScienceParser
from app.services.rosstat_fixedassets_parser import RosstatFixedAssetsParser

PARSER_REGISTRY: dict[str, type[BaseParser]] = {
    RosstatCpiParser.parser_type: RosstatCpiParser,
    CbrKeyRateParser.parser_type: CbrKeyRateParser,
    CbrFxParser.parser_type: CbrFxParser,
    CbrRuoniaParser.parser_type: CbrRuoniaParser,
    CbrMonetaryParser.parser_type: CbrMonetaryParser,
    CbrDataServiceParser.parser_type: CbrDataServiceParser,
    RosstatLaborParser.parser_type: RosstatLaborParser,
    RosstatGdpParser.parser_type: RosstatGdpParser,
    CbrDataServiceSumParser.parser_type: CbrDataServiceSumParser,
    MinfinBudgetParser.parser_type: MinfinBudgetParser,
    RosstatWeeklyCpiParser.parser_type: RosstatWeeklyCpiParser,
    RosstatIpiParser.parser_type: RosstatIpiParser,
    RosstatHousingParser.parser_type: RosstatHousingParser,
    RosstatPopulationParser.parser_type: RosstatPopulationParser,
    RosstatPpiParser.parser_type: RosstatPpiParser,
    CbrBopParser.parser_type: CbrBopParser,
    CbrReservesParser.parser_type: CbrReservesParser,
    CbrDebtParser.parser_type: CbrDebtParser,
    CbrGoldParser.parser_type: CbrGoldParser,
    RosstatDemoParser.parser_type: RosstatDemoParser,
    RosstatIndParser.parser_type: RosstatIndParser,
    RosstatScienceParser.parser_type: RosstatScienceParser,
    RosstatFixedAssetsParser.parser_type: RosstatFixedAssetsParser,
}


def get_parser(parser_type: str) -> BaseParser | None:
    cls = PARSER_REGISTRY.get(parser_type)
    if cls is None:
        logger.error(
            "Unknown parser_type %r; available: %s",
            parser_type,
            ", ".join(sorted(PARSER_REGISTRY)),
        )
        return None
    return cls()

"""ETL: Росстат CPI XLSX → IndicatorData (реализация BaseParser).

Также служит модулем агрегатора PARSER_REGISTRY (исторический корень
импортов). После полной миграции на Template Method можно вынести
реестр в отдельный модуль.
"""

from __future__ import annotations

import asyncio
import logging
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FetchLog, Indicator
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
from app.services.parser import parse_cpi_sheet

logger = logging.getLogger(__name__)


class RosstatCpiParser(BaseParser):
    parser_type: ClassVar[str] = "rosstat_cpi_xlsx"

    async def _fetch_and_parse(
        self,
        db: AsyncSession,
        indicator: Indicator,
        cfg: dict,
        fetch_log: FetchLog,
    ) -> tuple[list, str]:
        fetcher = RosstatFetcher()
        try:
            content, source_url = await asyncio.to_thread(fetcher.fetch_latest)
        finally:
            fetcher.session.close()

        if not content:
            raise ValueError("No file available on Rosstat")

        sheet = indicator.excel_sheet or "01"
        points = await asyncio.to_thread(parse_cpi_sheet, content, sheet)

        for p in points:
            if p.value < 90 or p.value > 200:
                logger.warning("Suspicious CPI value %.2f for %s at %s", p.value, indicator.code, p.date)

        return points, source_url

    def _validate(self, points: list, cfg: dict) -> list:
        return validate_points(points, cfg)


from app.services.cbr_dataservice_sum_parser import CbrDataServiceSumParser
from app.services.minfin_budget_parser import MinfinBudgetParser
from app.services.rosstat_weekly_inflation_parser import RosstatWeeklyCpiParser
from app.services.rosstat_ipi_parser import RosstatIpiParser
from app.services.rosstat_housing_parser import RosstatHousingParser
from app.services.rosstat_population_parser import RosstatPopulationParser
from app.services.rosstat_ppi_parser import RosstatPpiParser
from app.services.cbr_bop_parser import CbrBopParser
from app.services.cbr_trade_goods_monthly_parser import CbrTradeGoodsMonthlyParser
from app.services.cbr_trade_services_monthly_parser import CbrTradeServicesMonthlyParser
from app.services.cbr_reserves_parser import CbrReservesParser
from app.services.cbr_debt_parser import CbrDebtParser
from app.services.cbr_gold_parser import CbrGoldParser
from app.services.rosstat_demo_parser import RosstatDemoParser
from app.services.rosstat_ind_parser import RosstatIndParser
from app.services.rosstat_science_parser import RosstatScienceParser
from app.services.rosstat_fixedassets_parser import RosstatFixedAssetsParser
from app.services.binance_btcusdt_parser import BinanceBtcUsdtParser
from app.services.brent_fred_parser import BrentDailyFredParser
from app.services.cbr_monetary_agg_parser import CbrMonetaryAggParser

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
    CbrTradeGoodsMonthlyParser.parser_type: CbrTradeGoodsMonthlyParser,
    CbrTradeServicesMonthlyParser.parser_type: CbrTradeServicesMonthlyParser,
    CbrReservesParser.parser_type: CbrReservesParser,
    CbrDebtParser.parser_type: CbrDebtParser,
    CbrGoldParser.parser_type: CbrGoldParser,
    RosstatDemoParser.parser_type: RosstatDemoParser,
    RosstatIndParser.parser_type: RosstatIndParser,
    RosstatScienceParser.parser_type: RosstatScienceParser,
    RosstatFixedAssetsParser.parser_type: RosstatFixedAssetsParser,
    BinanceBtcUsdtParser.parser_type: BinanceBtcUsdtParser,
    BrentDailyFredParser.parser_type: BrentDailyFredParser,
    CbrMonetaryAggParser.parser_type: CbrMonetaryAggParser,
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

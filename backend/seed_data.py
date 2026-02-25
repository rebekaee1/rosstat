"""
Seed script: populate database with initial indicator definitions and historical CPI data.
Run once after first migration: python seed_data.py
"""

import asyncio
import csv
import os
import sys
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from app.database import async_session
from app.models import Indicator, IndicatorData, Forecast, ForecastValue
from app.services.forecaster import train_and_forecast

CPI_DESCRIPTION = (
    "Индекс потребительских цен (ИПЦ) измеряет изменение цен на товары и услуги, "
    "приобретаемые населением для непроизводственного потребления. ИПЦ является ключевым "
    "показателем инфляции и используется для индексации заработной платы, пенсий и "
    "социальных выплат."
)

CPI_METHODOLOGY = (
    "ИПЦ рассчитывается как отношение стоимости фиксированного набора товаров и услуг "
    "в текущем периоде к его стоимости в базисном периоде. Наблюдение осуществляется "
    "в 283 населённых пунктах по 510 наименованиям товаров и услуг. "
    "База сравнения — предыдущий месяц (100%)."
)

INDICATORS = [
    {
        "code": "cpi",
        "name": "Индекс потребительских цен",
        "name_en": "Consumer Price Index",
        "unit": "%",
        "frequency": "monthly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/price",
        "description": CPI_DESCRIPTION,
        "methodology": CPI_METHODOLOGY,
        "parser_type": "rosstat_cpi_xlsx",
        "model_config_json": {"forecast_steps": 12},
        "is_active": True,
        "category": "Цены",
        "excel_sheet": "01",
    },
    {
        "code": "cpi-food",
        "name": "ИПЦ на продовольственные товары",
        "name_en": "Food CPI",
        "unit": "%",
        "frequency": "monthly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/price",
        "description": "Индекс потребительских цен на продовольственные товары.",
        "parser_type": "rosstat_cpi_xlsx",
        "model_config_json": {"forecast_steps": 12},
        "is_active": True,
        "category": "Цены",
        "excel_sheet": "02",
    },
    {
        "code": "cpi-nonfood",
        "name": "ИПЦ на непродовольственные товары",
        "name_en": "Non-food CPI",
        "unit": "%",
        "frequency": "monthly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/price",
        "description": "Индекс потребительских цен на непродовольственные товары.",
        "parser_type": "rosstat_cpi_xlsx",
        "model_config_json": {"forecast_steps": 12},
        "is_active": True,
        "category": "Цены",
        "excel_sheet": "03",
    },
    {
        "code": "cpi-services",
        "name": "ИПЦ на услуги",
        "name_en": "Services CPI",
        "unit": "%",
        "frequency": "monthly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/price",
        "description": "Индекс потребительских цен на услуги населению.",
        "parser_type": "rosstat_cpi_xlsx",
        "model_config_json": {"forecast_steps": 12},
        "is_active": True,
        "category": "Цены",
        "excel_sheet": "04",
    },
    {
        "code": "unemployment",
        "name": "Уровень безработицы",
        "name_en": "Unemployment Rate",
        "unit": "%",
        "frequency": "monthly",
        "source": "Росстат",
        "description": "Доля безработных в экономически активном населении.",
        "is_active": False,
        "category": "Рынок труда",
    },
    {
        "code": "key-rate",
        "name": "Ключевая ставка ЦБ РФ",
        "name_en": "Key Interest Rate",
        "unit": "%",
        "frequency": "irregular",
        "source": "ЦБ РФ",
        "source_url": "https://cbr.ru/hd_base/KeyRate/",
        "description": "Процентная ставка, по которой ЦБ РФ предоставляет кредиты банкам.",
        "is_active": False,
        "category": "Денежно-кредитная политика",
    },
]


async def seed():
    async with async_session() as db:
        # Seed indicators
        for ind_data in INDICATORS:
            existing = await db.execute(
                select(Indicator).where(Indicator.code == ind_data["code"])
            )
            if existing.scalar_one_or_none():
                print(f"  Indicator '{ind_data['code']}' already exists, skipping")
                continue

            indicator = Indicator(**ind_data)
            db.add(indicator)
            print(f"  Added indicator: {ind_data['code']}")

        await db.commit()

        # Seed CPI data from CSV
        csv_candidates = [
            os.path.join(os.path.dirname(__file__), "data", "ipc_monthly.csv"),     # Docker mount
            os.path.join(os.path.dirname(__file__), "..", "output", "ipc_monthly.csv"),  # local dev
        ]
        csv_path = next((p for p in csv_candidates if os.path.exists(p)), None)
        if not csv_path:
            print(f"  CSV not found at {csv_candidates}, skipping data seed")
            return

        ind_q = await db.execute(select(Indicator).where(Indicator.code == "cpi"))
        cpi = ind_q.scalar_one_or_none()
        if not cpi:
            print("  CPI indicator not found, skipping data seed")
            return

        count = 0
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                dt = date.fromisoformat(row["date"])
                val = float(row["ipc"])
                stmt = pg_insert(IndicatorData).values(
                    indicator_id=cpi.id, date=dt, value=val,
                ).on_conflict_do_nothing(constraint="uq_indicator_date")
                result = await db.execute(stmt)
                if result.rowcount > 0:
                    count += 1

        await db.commit()
        print(f"  Seeded {count} CPI data points from CSV")

        # Generate initial forecast
        await generate_forecasts()


async def generate_forecasts():
    """Generate OLS forecasts for all active indicators that have enough data."""
    async with async_session() as db:
        ind_q = await db.execute(
            select(Indicator).where(Indicator.is_active.is_(True))
        )
        indicators = ind_q.scalars().all()

        for indicator in indicators:
            data_q = await db.execute(
                select(IndicatorData)
                .where(IndicatorData.indicator_id == indicator.id)
                .order_by(IndicatorData.date)
            )
            all_data = data_q.scalars().all()

            if len(all_data) < 36:
                print(f"  {indicator.code}: not enough data ({len(all_data)} points), skipping forecast")
                continue

            print(f"  {indicator.code}: generating forecast from {len(all_data)} data points...")

            dates = [d.date for d in all_data]
            values = [float(d.value) for d in all_data]

            cfg = indicator.model_config_json or {}
            forecast_steps = cfg.get("forecast_steps", 12)

            result = train_and_forecast(dates, values, forecast_steps=forecast_steps)

            old_q = await db.execute(
                select(Forecast).where(
                    Forecast.indicator_id == indicator.id,
                    Forecast.is_current.is_(True),
                )
            )
            for old_fc in old_q.scalars().all():
                old_fc.is_current = False

            new_forecast = Forecast(
                indicator_id=indicator.id,
                model_name=result.model_name,
                model_params={"cumulative_12m": result.cumulative_12m},
                aic=result.aic,
                bic=result.bic,
                is_current=True,
            )
            db.add(new_forecast)
            await db.flush()

            for fp in result.points:
                db.add(ForecastValue(
                    forecast_id=new_forecast.id,
                    date=fp.date,
                    value=fp.value,
                    lower_bound=fp.lower_bound,
                    upper_bound=fp.upper_bound,
                ))

            await db.commit()
            print(f"  {indicator.code}: forecast saved ({result.model_name}, "
                  f"cumulative 12m = {result.cumulative_12m:.2f}%)")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--forecast-only":
        print("Generating forecasts...")
        asyncio.run(generate_forecasts())
    else:
        print("Seeding database...")
        asyncio.run(seed())
    print("Done.")

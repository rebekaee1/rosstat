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

from sqlalchemy import select, update
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

# Коды ниже должны быть в frontend/nginx.conf (location ~ ^/indicator/(...)/?$).
# Статические страницы /about и /privacy — отдельный location в том же файле.
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
        "code": "key-rate",
        "name": "Ключевая ставка ЦБ РФ",
        "name_en": "Key Interest Rate",
        "unit": "%",
        "frequency": "daily",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/hd_base/KeyRate/",
        "description": (
            "Ключевая ставка — основной инструмент денежно-кредитной политики Банка России. "
            "Данные — официальная база cbr.ru (история значений по дням)."
        ),
        "methodology": (
            "Ряд подгружается из публичной страницы «Ключевая ставка Банка России» "
            "(единая база данных). Значение указывается в % годовых; при смене ставки "
            "ряд отражает уровень на каждую дату публикации."
        ),
        "parser_type": "cbr_keyrate_html",
        "model_config_json": {
            "forecast_steps": 0,
            "validation": {"min": 0, "max": 60},
        },
        "is_active": True,
        "category": "Ставки",
    },
    # ─── Курсы валют ───
    {
        "code": "usd-rub",
        "name": "Курс доллара США",
        "name_en": "USD/RUB Exchange Rate",
        "unit": "руб.",
        "frequency": "daily",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/currency_base/daily/",
        "description": (
            "Официальный курс доллара США к рублю, устанавливаемый Банком России. "
            "Обновляется ежедневно."
        ),
        "methodology": (
            "Курс устанавливается на основе результатов биржевых торгов. "
            "Источник: XML-канал ЦБ РФ (XML_dynamic.asp)."
        ),
        "parser_type": "cbr_fx_xml",
        "model_config_json": {
            "forecast_steps": 6,
            "forecast_transform": "absolute",
            "validation": {"min": 1, "max": 500},
        },
        "is_active": True,
        "category": "Финансы",
    },
    {
        "code": "eur-rub",
        "name": "Курс евро",
        "name_en": "EUR/RUB Exchange Rate",
        "unit": "руб.",
        "frequency": "daily",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/currency_base/daily/",
        "description": "Официальный курс евро к рублю, устанавливаемый Банком России.",
        "parser_type": "cbr_fx_xml",
        "model_config_json": {
            "forecast_steps": 6,
            "forecast_transform": "absolute",
            "validation": {"min": 1, "max": 500},
        },
        "is_active": True,
        "category": "Финансы",
    },
    {
        "code": "cny-rub",
        "name": "Курс юаня",
        "name_en": "CNY/RUB Exchange Rate",
        "unit": "руб.",
        "frequency": "daily",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/currency_base/daily/",
        "description": "Официальный курс китайского юаня к рублю, устанавливаемый Банком России.",
        "parser_type": "cbr_fx_xml",
        "model_config_json": {
            "forecast_steps": 6,
            "forecast_transform": "absolute",
            "validation": {"min": 0.1, "max": 100},
        },
        "is_active": True,
        "category": "Финансы",
    },
    # ─── RUONIA ───
    {
        "code": "ruonia",
        "name": "Ставка RUONIA",
        "name_en": "RUONIA Rate",
        "unit": "%",
        "frequency": "daily",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/hd_base/ruonia/",
        "description": (
            "Ruble OverNight Index Average — индикативная взвешенная ставка "
            "однодневных рублёвых кредитов (депозитов) на условиях «овернайт» "
            "на межбанковском рынке."
        ),
        "methodology": (
            "Рассчитывается Банком России по данным о необеспеченных сделках банков-участников. "
            "Источник: HTML-таблица cbr.ru/hd_base/ruonia/."
        ),
        "parser_type": "cbr_ruonia_html",
        "model_config_json": {
            "forecast_steps": 0,
            "validation": {"min": -5, "max": 100},
        },
        "is_active": True,
        "category": "Ставки",
    },
    # ─── Денежные агрегаты ───
    {
        "code": "m0",
        "name": "Денежная масса М0",
        "name_en": "M0 Money Supply",
        "unit": "млрд руб.",
        "frequency": "monthly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/macro_itm/dkfs/",
        "description": (
            "Наличные деньги в обращении вне банковской системы (агрегат М0). "
            "Публикуется ежемесячно на 1-е число."
        ),
        "parser_type": "cbr_dataservice_json",
        "model_config_json": {
            "dataservice": {
                "publicationId": 5,
                "datasetId": 5,
                "measureId": None,
                "element_id": None,
                "date_offset_months": 0,
            },
            "backfill_from_year": 2010,
            "forecast_steps": 6,
            "forecast_transform": "absolute",
            "validation": {"min": 0},
        },
        "is_active": True,
        "category": "Финансы",
    },
    {
        "code": "m2",
        "name": "Денежная масса М2",
        "name_en": "M2 Money Supply",
        "unit": "млрд руб.",
        "frequency": "monthly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/macro_itm/dkfs/",
        "description": (
            "Широкая денежная масса (агрегат М2): наличные + безналичные средства "
            "на счетах резидентов. Публикуется ежемесячно на 1-е число."
        ),
        "parser_type": "cbr_dataservice_json",
        "model_config_json": {
            "dataservice": {
                "publicationId": 5,
                "datasetId": 7,
                "measureId": None,
                "element_id": 12,
                "date_offset_months": 0,
            },
            "backfill_from_year": 2010,
            "forecast_steps": 6,
            "forecast_transform": "absolute",
            "validation": {"min": 0},
        },
        "is_active": True,
        "category": "Финансы",
    },
    # ─── Банковские ставки (CBR Data Service) ───
    {
        "code": "mortgage-rate",
        "name": "Ставка по ипотеке",
        "name_en": "Mortgage Interest Rate",
        "unit": "%",
        "frequency": "monthly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/pdko/int_rat/",
        "description": (
            "Средневзвешенная процентная ставка по ипотечным жилищным кредитам "
            "физическим лицам-резидентам в рублях."
        ),
        "methodology": (
            "Данные из REST API CBR DataService (publicationId=14, datasetId=29). "
            "Значение — ставка по кредитам в рублях (element_id=36)."
        ),
        "parser_type": "cbr_dataservice_json",
        "model_config_json": {
            "dataservice": {
                "publicationId": 14,
                "datasetId": 29,
                "measureId": None,
                "element_id": 36,
            },
            "backfill_from_year": 2017,
            "forecast_steps": 6,
            "forecast_transform": "percentage",
            "validation": {"min": 0, "max": 50},
        },
        "is_active": True,
        "category": "Ставки",
    },
    {
        "code": "deposit-rate",
        "name": "Ставка по вкладам",
        "name_en": "Deposit Interest Rate",
        "unit": "%",
        "frequency": "monthly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/pdko/int_rat/",
        "description": (
            "Средневзвешенная процентная ставка по привлечённым вкладам (депозитам) "
            "физических лиц в рублях, до 1 года включая «до востребования»."
        ),
        "parser_type": "cbr_dataservice_json",
        "model_config_json": {
            "dataservice": {
                "publicationId": 18,
                "datasetId": 37,
                "measureId": 2,
                "element_id": 7,
            },
            "backfill_from_year": 2014,
            "forecast_steps": 6,
            "forecast_transform": "percentage",
            "validation": {"min": 0, "max": 50},
        },
        "is_active": True,
        "category": "Ставки",
    },
    {
        "code": "auto-loan-rate",
        "name": "Ставка по автокредитам",
        "name_en": "Auto Loan Interest Rate",
        "unit": "%",
        "frequency": "monthly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/pdko/int_rat/",
        "description": (
            "Средневзвешенная процентная ставка по автокредитам физическим лицам "
            "в рублях, свыше 1 года."
        ),
        "parser_type": "cbr_dataservice_json",
        "model_config_json": {
            "dataservice": {
                "publicationId": 14,
                "datasetId": 28,
                "measureId": 2,
                "element_id": 11,
            },
            "backfill_from_year": 2014,
            "forecast_steps": 6,
            "forecast_transform": "percentage",
            "validation": {"min": 0, "max": 50},
        },
        "is_active": True,
        "category": "Ставки",
    },
    # ─── Рынок труда (Росстат SDDS) ───
    {
        "code": "unemployment",
        "name": "Уровень безработицы",
        "name_en": "Unemployment Rate",
        "unit": "%",
        "frequency": "monthly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/labor_market_employment_salaries",
        "description": (
            "Доля безработных в экономически активном населении по методологии МОТ. "
            "Данные Росстата из обследования рабочей силы."
        ),
        "methodology": (
            "Расчёт: число безработных / экономически активное население × 100. "
            "Источник: SDDS XLSX Росстата (eng.rosstat.gov.ru). Обновляется ежемесячно."
        ),
        "parser_type": "rosstat_sdds_labor",
        "model_config_json": {
            "forecast_steps": 12,
            "forecast_transform": "percentage",
            "validation": {"min": 0, "max": 50},
        },
        "is_active": True,
        "category": "Рынок труда",
    },
    {
        "code": "wages-nominal",
        "name": "Средняя заработная плата",
        "name_en": "Average Nominal Wages",
        "unit": "руб.",
        "frequency": "monthly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/labor_market_employment_salaries",
        "description": (
            "Среднемесячная номинальная начисленная заработная плата "
            "работников организаций."
        ),
        "methodology": (
            "Фонд начисленной зарплаты / среднесписочная численность. "
            "Источник: SDDS XLSX Росстата. Обновляется ежемесячно."
        ),
        "parser_type": "rosstat_sdds_labor",
        "model_config_json": {
            "forecast_steps": 6,
            "forecast_transform": "absolute",
            "validation": {"min": 0},
        },
        "is_active": True,
        "category": "Рынок труда",
    },
    # ─── ВВП (Росстат SDDS) ───
    {
        "code": "gdp-nominal",
        "name": "ВВП номинальный",
        "name_en": "Nominal GDP",
        "unit": "млрд руб.",
        "frequency": "quarterly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/accounts",
        "description": (
            "Валовой внутренний продукт в текущих ценах (по расходному методу). "
            "Квартальные данные."
        ),
        "methodology": (
            "Рассчитывается Росстатом по системе национальных счетов (СНС 2008). "
            "Источник: SDDS XLSX национальных счетов. Обновляется поквартально."
        ),
        "parser_type": "rosstat_sdds_gdp",
        "model_config_json": {
            "forecast_steps": 4,
            "forecast_transform": "absolute",
            "validation": {"min": 0},
        },
        "is_active": True,
        "category": "ВВП",
    },
    # ─── Производные (CalculationEngine) ───
    {
        "code": "wages-real",
        "name": "Реальная заработная плата",
        "name_en": "Real Wages Index",
        "unit": "%",
        "frequency": "monthly",
        "source": "Расчёт",
        "description": (
            "Индекс реальной заработной платы: отношение номинальной зарплаты "
            "к индексу потребительских цен. Показывает покупательную способность."
        ),
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 6,
            "forecast_transform": "percentage",
        },
        "is_active": True,
        "category": "Рынок труда",
    },
    {
        "code": "gdp-yoy",
        "name": "Рост ВВП (г/г)",
        "name_en": "GDP Growth YoY",
        "unit": "%",
        "frequency": "quarterly",
        "source": "Расчёт",
        "description": (
            "Темп роста номинального ВВП к аналогичному кварталу предыдущего года."
        ),
        "parser_type": "derived",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "ВВП",
    },
    {
        "code": "gdp-qoq",
        "name": "Рост ВВП (кв/кв)",
        "name_en": "GDP Growth QoQ",
        "unit": "%",
        "frequency": "quarterly",
        "source": "Расчёт",
        "description": (
            "Темп роста номинального ВВП к предыдущему кварталу."
        ),
        "parser_type": "derived",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "ВВП",
    },
    {
        "code": "inflation-quarterly",
        "name": "Инфляция квартальная",
        "name_en": "Quarterly Inflation",
        "unit": "%",
        "frequency": "quarterly",
        "source": "Расчёт",
        "description": (
            "Квартальный индекс инфляции, рассчитываемый как произведение "
            "трёх месячных ИПЦ (к предыдущему кварталу)."
        ),
        "parser_type": "derived",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "inflation-annual",
        "name": "Инфляция годовая",
        "name_en": "Annual Inflation",
        "unit": "%",
        "frequency": "monthly",
        "source": "Расчёт",
        "description": (
            "Годовая инфляция: произведение 12 месячных ИПЦ — процент роста цен "
            "к аналогичному месяцу предыдущего года."
        ),
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 12,
            "forecast_transform": "percentage",
        },
        "is_active": True,
        "category": "Цены",
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

        # Фаза 2: актуализировать key-rate в уже существующих БД
        await db.execute(
            update(Indicator)
            .where(Indicator.code == "key-rate")
            .values(
                parser_type="cbr_keyrate_html",
                is_active=True,
                frequency="daily",
                source="Банк России",
                source_url="https://www.cbr.ru/hd_base/KeyRate/",
                category="Ставки",
                methodology=(
                    "Ряд подгружается из публичной страницы «Ключевая ставка Банка России» "
                    "(единая база данных). Значение указывается в % годовых."
                ),
                model_config_json={"forecast_steps": 0, "validation": {"min": 0, "max": 60}},
            )
        )
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
            forecast_steps = int(cfg.get("forecast_steps", 12) or 0)
            if forecast_steps <= 0:
                print(f"  {indicator.code}: forecast_steps=0, skipping")
                continue
            forecast_transform = cfg.get("forecast_transform", "cpi_index")

            result = train_and_forecast(
                dates, values, forecast_steps=forecast_steps,
                forecast_transform=forecast_transform,
            )

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

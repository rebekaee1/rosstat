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
from app.models import Indicator, IndicatorData
from app.services.forecast_pipeline import retrain_indicator_forecast

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
        "name": "Индекс потребительских цен на товары и услуги",
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
        "name": "Индекс потребительских цен на продовольственные товары",
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
        "name": "Индекс потребительских цен на непродовольственные товары",
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
        "name": "Индекс потребительских цен на услуги",
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
            "forecast_steps": 0,
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
            "forecast_steps": 0,
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
            "forecast_steps": 0,
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
            "forecast_steps": 0,
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
            "forecast_steps": 0,
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
            "forecast_steps": 0,
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
            "forecast_steps": 0,
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
            "forecast_steps": 0,
            "forecast_transform": "percentage",
            "validation": {"min": 0, "max": 50},
        },
        "is_active": True,
        "category": "Ставки",
    },
    # ─── Ставки по кредитам по срочности (CBR DataService) ───
    # ЦБ публикует средневзвешенные ставки по новым выданным рублёвым кредитам
    # с разбивкой по срочности кредитного договора. Нефинансовые организации (ds=25)
    # и физические лица — потребительские кредиты без ипотеки (ds=27).
    # Ряды доступны с января 2014 г. ежемесячно (publicationId=14).
    {
        "code": "credit-rate-corp-short",
        "name": "Ставка по кредитам юридическим лицам до 1 года",
        "name_en": "Corporate Loan Rate (up to 1 year)",
        "unit": "%",
        "frequency": "monthly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/pdko/int_rat/",
        "description": (
            "Средневзвешенная процентная ставка по кредитам нефинансовым "
            "организациям в рублях со сроком погашения до 1 года, включая "
            "«до востребования»."
        ),
        "methodology": (
            "Источник: REST API CBR DataService (publicationId=14, datasetId=25, "
            "measureId=2, element_id=7)."
        ),
        "parser_type": "cbr_dataservice_json",
        "model_config_json": {
            "dataservice": {
                "publicationId": 14,
                "datasetId": 25,
                "measureId": 2,
                "element_id": 7,
            },
            "backfill_from_year": 2014,
            "forecast_steps": 0,
            "forecast_transform": "percentage",
            "validation": {"min": 0, "max": 50},
        },
        "is_active": True,
        "category": "Ставки",
    },
    {
        "code": "credit-rate-corp-1to3y",
        "name": "Ставка по кредитам юридическим лицам от 1 до 3 лет",
        "name_en": "Corporate Loan Rate (1–3 years)",
        "unit": "%",
        "frequency": "monthly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/pdko/int_rat/",
        "description": (
            "Средневзвешенная процентная ставка по кредитам нефинансовым "
            "организациям в рублях со сроком погашения от 1 года до 3 лет."
        ),
        "methodology": (
            "Источник: REST API CBR DataService (publicationId=14, datasetId=25, "
            "measureId=2, element_id=9)."
        ),
        "parser_type": "cbr_dataservice_json",
        "model_config_json": {
            "dataservice": {
                "publicationId": 14,
                "datasetId": 25,
                "measureId": 2,
                "element_id": 9,
            },
            "backfill_from_year": 2014,
            "forecast_steps": 0,
            "forecast_transform": "percentage",
            "validation": {"min": 0, "max": 50},
        },
        "is_active": True,
        "category": "Ставки",
    },
    {
        "code": "credit-rate-corp-over3y",
        "name": "Ставка по кредитам юридическим лицам свыше 3 лет",
        "name_en": "Corporate Loan Rate (over 3 years)",
        "unit": "%",
        "frequency": "monthly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/pdko/int_rat/",
        "description": (
            "Средневзвешенная процентная ставка по кредитам нефинансовым "
            "организациям в рублях со сроком погашения свыше 3 лет."
        ),
        "methodology": (
            "Источник: REST API CBR DataService (publicationId=14, datasetId=25, "
            "measureId=2, element_id=10)."
        ),
        "parser_type": "cbr_dataservice_json",
        "model_config_json": {
            "dataservice": {
                "publicationId": 14,
                "datasetId": 25,
                "measureId": 2,
                "element_id": 10,
            },
            "backfill_from_year": 2014,
            "forecast_steps": 0,
            "forecast_transform": "percentage",
            "validation": {"min": 0, "max": 50},
        },
        "is_active": True,
        "category": "Ставки",
    },
    {
        "code": "credit-rate-ind-short",
        "name": "Ставка по кредитам физическим лицам до 1 года",
        "name_en": "Individual Loan Rate (up to 1 year)",
        "unit": "%",
        "frequency": "monthly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/pdko/int_rat/",
        "description": (
            "Средневзвешенная процентная ставка по кредитам физическим лицам "
            "в рублях со сроком погашения до 1 года, включая «до востребования»."
        ),
        "methodology": (
            "Источник: REST API CBR DataService (publicationId=14, datasetId=27, "
            "measureId=2, element_id=7)."
        ),
        "parser_type": "cbr_dataservice_json",
        "model_config_json": {
            "dataservice": {
                "publicationId": 14,
                "datasetId": 27,
                "measureId": 2,
                "element_id": 7,
            },
            "backfill_from_year": 2014,
            "forecast_steps": 0,
            "forecast_transform": "percentage",
            "validation": {"min": 0, "max": 50},
        },
        "is_active": True,
        "category": "Ставки",
    },
    {
        "code": "credit-rate-ind-1to3y",
        "name": "Ставка по кредитам физическим лицам от 1 до 3 лет",
        "name_en": "Individual Loan Rate (1–3 years)",
        "unit": "%",
        "frequency": "monthly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/pdko/int_rat/",
        "description": (
            "Средневзвешенная процентная ставка по кредитам физическим лицам "
            "в рублях со сроком погашения от 1 года до 3 лет."
        ),
        "methodology": (
            "Источник: REST API CBR DataService (publicationId=14, datasetId=27, "
            "measureId=2, element_id=9)."
        ),
        "parser_type": "cbr_dataservice_json",
        "model_config_json": {
            "dataservice": {
                "publicationId": 14,
                "datasetId": 27,
                "measureId": 2,
                "element_id": 9,
            },
            "backfill_from_year": 2014,
            "forecast_steps": 0,
            "forecast_transform": "percentage",
            "validation": {"min": 0, "max": 50},
        },
        "is_active": True,
        "category": "Ставки",
    },
    {
        "code": "credit-rate-ind-over3y",
        "name": "Ставка по кредитам физическим лицам свыше 3 лет",
        "name_en": "Individual Loan Rate (over 3 years)",
        "unit": "%",
        "frequency": "monthly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/pdko/int_rat/",
        "description": (
            "Средневзвешенная процентная ставка по кредитам физическим лицам "
            "в рублях со сроком погашения свыше 3 лет."
        ),
        "methodology": (
            "Источник: REST API CBR DataService (publicationId=14, datasetId=27, "
            "measureId=2, element_id=10)."
        ),
        "parser_type": "cbr_dataservice_json",
        "model_config_json": {
            "dataservice": {
                "publicationId": 14,
                "datasetId": 27,
                "measureId": 2,
                "element_id": 10,
            },
            "backfill_from_year": 2014,
            "forecast_steps": 0,
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
            "forecast_model_name": "Approved-GDP-Nominal-Notebook",
            "approved_forecast_values": [
                {"date": "2026-03-01", "value": 52231.888190},
                {"date": "2026-06-01", "value": 54123.118741},
                {"date": "2026-09-01", "value": 57010.414402},
                {"date": "2026-12-01", "value": 63675.196294},
            ],
            "forecast_transform": "absolute",
            "validation": {"min": 0},
        },
        "is_active": True,
        "category": "ВВП",
    },
    {
        "code": "gdp-real",
        "name": "ВВП реальный",
        "name_en": "Real GDP",
        "unit": "млрд руб.",
        "frequency": "quarterly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/accounts",
        "description": (
            "Валовой внутренний продукт в постоянных ценах 2021 года. "
            "Квартальные данные официального файла Росстата «ВВП кварталы»."
        ),
        "methodology": (
            "Источник — XLSX Росстата VVP_kvartal_s_1995-2025.xlsx, лист 9: "
            "«Валовой внутренний продукт (в ценах 2021 г., млрд руб.)»."
        ),
        "parser_type": "rosstat_sdds_gdp",
        "model_config_json": {
            "gdp_source": "official_quarterly",
            "gdp_sheet": "9",
            "forecast_steps": 0,
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
            "Квартальный индекс инфляции: произведение трёх внутриквартальных "
            "месячных ИПЦ (цепной индекс за квартал)."
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
            "forecast_steps": 0,
        },
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "cpi-food-quarterly",
        "name": "Квартальная инфляция продовольственных товаров",
        "name_en": "Food CPI Quarterly Inflation",
        "unit": "%",
        "frequency": "quarterly",
        "source": "Расчёт",
        "description": (
            "Квартальная инфляция продовольственных товаров: произведение трёх "
            "месячных индексов потребительских цен на продовольственные товары."
        ),
        "parser_type": "derived",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "cpi-food-annual",
        "name": "Годовая инфляция продовольственных товаров",
        "name_en": "Food CPI Annual Inflation",
        "unit": "%",
        "frequency": "monthly",
        "source": "Расчёт",
        "description": (
            "Годовая инфляция продовольственных товаров: скользящее изменение за "
            "12 месяцев по месячным индексам потребительских цен на продовольствие."
        ),
        "parser_type": "derived",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "cpi-nonfood-quarterly",
        "name": "Квартальная инфляция непродовольственных товаров",
        "name_en": "Non-food CPI Quarterly Inflation",
        "unit": "%",
        "frequency": "quarterly",
        "source": "Расчёт",
        "description": (
            "Квартальная инфляция непродовольственных товаров: произведение трёх "
            "месячных индексов потребительских цен на непродовольственные товары."
        ),
        "parser_type": "derived",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "cpi-nonfood-annual",
        "name": "Годовая инфляция непродовольственных товаров",
        "name_en": "Non-food CPI Annual Inflation",
        "unit": "%",
        "frequency": "monthly",
        "source": "Расчёт",
        "description": (
            "Годовая инфляция непродовольственных товаров: скользящее изменение за "
            "12 месяцев по месячным индексам потребительских цен на непродовольственные товары."
        ),
        "parser_type": "derived",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "cpi-services-quarterly",
        "name": "Квартальная инфляция услуг",
        "name_en": "Services CPI Quarterly Inflation",
        "unit": "%",
        "frequency": "quarterly",
        "source": "Расчёт",
        "description": (
            "Квартальная инфляция услуг: произведение трёх месячных индексов "
            "потребительских цен на услуги."
        ),
        "parser_type": "derived",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "cpi-services-annual",
        "name": "Годовая инфляция услуг",
        "name_en": "Services CPI Annual Inflation",
        "unit": "%",
        "frequency": "monthly",
        "source": "Расчёт",
        "description": (
            "Годовая инфляция услуг: скользящее изменение за 12 месяцев по месячным "
            "индексам потребительских цен на услуги."
        ),
        "parser_type": "derived",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "Цены",
    },
    # ─── Дополнительные финансы (CBR DataService) ───
    {
        "code": "m1",
        "name": "Денежная масса М1",
        "name_en": "M1 Money Supply",
        "unit": "млрд руб.",
        "frequency": "monthly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/macro_itm/dkfs/",
        "description": (
            "Денежный агрегат М1: наличные деньги (М0) плюс переводные депозиты. "
            "Публикуется ежемесячно на 1-е число."
        ),
        "parser_type": "cbr_dataservice_json",
        "model_config_json": {
            "dataservice": {
                "publicationId": 5,
                "datasetId": 6,
                "measureId": None,
                "element_id": 12,
                "date_offset_months": 0,
            },
            "backfill_from_year": 2010,
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "validation": {"min": 0},
        },
        "is_active": True,
        "category": "Финансы",
    },
    {
        "code": "consumer-credit",
        "name": "Кредиты физическим лицам",
        "name_en": "Consumer Credit Outstanding",
        "unit": "трлн руб.",
        "frequency": "monthly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/bank_sector/sors/",
        "description": (
            "Задолженность по кредитам физическим лицам (портфель). "
            "Данные Банка России по банковскому сектору."
        ),
        "parser_type": "cbr_dataservice_json",
        "model_config_json": {
            "dataservice": {
                "publicationId": 20,
                "datasetId": 42,
                "measureId": 22,
                "element_id": 35,
                "date_offset_months": 0,
            },
            "backfill_from_year": 2019,
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "validation": {"min": 0},
            "value_divisor": 1000000,
        },
        "is_active": True,
        "category": "Финансы",
    },
    {
        "code": "business-credit",
        "name": "Кредиты бизнесу",
        "name_en": "Business Credit Outstanding",
        "unit": "трлн руб.",
        "frequency": "monthly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/bank_sector/sors/",
        "description": (
            "Задолженность по кредитам юридическим лицам и ИП (портфель). "
            "Данные Банка России."
        ),
        "parser_type": "cbr_dataservice_json",
        "model_config_json": {
            "dataservice": {
                "publicationId": 22,
                "datasetId": 50,
                "measureId": 22,
                "element_id": 35,
                "date_offset_months": 0,
            },
            "backfill_from_year": 2019,
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "validation": {"min": 0},
            "value_divisor": 1000000,
        },
        "is_active": True,
        "category": "Финансы",
    },
    # ─── Депозиты (CBR DataService sum) ───
    {
        "code": "deposits-individual",
        "name": "Вклады физических лиц",
        "name_en": "Individual Deposits",
        "unit": "млрд руб.",
        "frequency": "monthly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/macro_itm/dkfs/",
        "description": (
            "Суммарные вклады физических лиц: переводные, срочные "
            "и валютные депозиты домашних хозяйств."
        ),
        "parser_type": "cbr_dataservice_sum",
        "model_config_json": {
            "dataservice_components": [
                {"publicationId": 5, "datasetId": 6, "element_id": 16, "date_offset_months": 0},
                {"publicationId": 5, "datasetId": 7, "element_id": 22, "date_offset_months": 0},
                {"publicationId": 5, "datasetId": 8, "element_id": 26, "date_offset_months": 0},
            ],
            "backfill_from_year": 2010,
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "validation": {"min": 0},
        },
        "is_active": True,
        "category": "Финансы",
    },
    {
        "code": "deposits-business",
        "name": "Депозиты организаций",
        "name_en": "Business Deposits",
        "unit": "млрд руб.",
        "frequency": "monthly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/macro_itm/dkfs/",
        "description": (
            "Суммарные депозиты нефинансовых организаций: переводные, "
            "срочные и валютные."
        ),
        "parser_type": "cbr_dataservice_sum",
        "model_config_json": {
            "dataservice_components": [
                {"publicationId": 5, "datasetId": 6, "element_id": 15, "date_offset_months": 0},
                {"publicationId": 5, "datasetId": 7, "element_id": 21, "date_offset_months": 0},
                {"publicationId": 5, "datasetId": 8, "element_id": 25, "date_offset_months": 0},
            ],
            "backfill_from_year": 2010,
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "validation": {"min": 0},
        },
        "is_active": True,
        "category": "Финансы",
    },
    # ─── Дефицит бюджета (Минфин CSV) ───
    {
        "code": "budget-deficit",
        "name": "Дефицит/профицит бюджета",
        "name_en": "Federal Budget Balance",
        "unit": "млрд руб.",
        "frequency": "monthly",
        "source": "Минфин",
        "source_url": "https://minfin.gov.ru/ru/statistics/fedbud/execute/",
        "description": (
            "Помесячный дефицит (−) или профицит (+) федерального бюджета РФ. "
            "Рассчитывается как разница доходов и расходов."
        ),
        "methodology": (
            "Данные из CSV открытых данных Минфина (7710168360-fedbud_month). "
            "Помесячные значения вычисляются из нарастающего итога с начала года."
        ),
        "parser_type": "minfin_budget_csv",
        "model_config_json": {
            "forecast_steps": 0,
            "forecast_transform": "absolute",
        },
        "is_active": True,
        "category": "Финансы",
    },
    # ─── Недельная инфляция (Росстат HTML) ───
    {
        "code": "inflation-weekly",
        "name": "Инфляция недельная",
        "name_en": "Weekly CPI Change",
        "unit": "%",
        "frequency": "weekly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/price",
        "description": (
            "Индекс потребительских цен за неделю (к предыдущей неделе). "
            "Публикуется Росстатом по средам."
        ),
        "parser_type": "rosstat_weekly_cpi",
        "model_config_json": {
            "forecast_steps": 0,
            "validation": {"min": 99, "max": 102},
            "backfill_max_pages": 1,
        },
        "is_active": True,
        "category": "Цены",
    },
    # ─── Цены на жильё (Росстат SDDS Housing) ───
    {
        "code": "housing-price-primary",
        "name": "Цены на первичное жильё",
        "name_en": "Primary Housing Price Index",
        "unit": "индекс",
        "frequency": "quarterly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/folder/10705",
        "description": (
            "Индекс цен на первичном рынке жилья (2010=100). "
            "Данные SDDS Росстата, квартальные."
        ),
        "parser_type": "rosstat_sdds_housing",
        "model_config_json": {
            "forecast_steps": 4,
            "forecast_transform": "absolute",
            "validation": {"min": 50, "max": 500},
        },
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "housing-price-secondary",
        "name": "Цены на вторичное жильё",
        "name_en": "Secondary Housing Price Index",
        "unit": "индекс",
        "frequency": "quarterly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/folder/10705",
        "description": (
            "Индекс цен на вторичном рынке жилья (2010=100). "
            "Данные SDDS Росстата, квартальные."
        ),
        "parser_type": "rosstat_sdds_housing",
        "model_config_json": {
            "forecast_steps": 4,
            "forecast_transform": "absolute",
            "validation": {"min": 50, "max": 500},
        },
        "is_active": True,
        "category": "Цены",
    },
    # ─── Индекс промышленного производства (Росстат SDDS IPI) ───
    {
        "code": "ipi",
        "name": "Индекс промышленного производства",
        "name_en": "Industrial Production Index",
        "unit": "индекс",
        "frequency": "monthly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/folder/10705",
        "description": (
            "Индекс промышленного производства (2023=100): горнодобыча, "
            "обработка, энергетика, водоснабжение. Ежемесячные данные SDDS Росстата."
        ),
        "parser_type": "rosstat_sdds_ipi",
        "model_config_json": {
            "forecast_steps": 6,
            "forecast_transform": "absolute",
            "validation": {"min": 30, "max": 200},
        },
        "is_active": True,
        "category": "Бизнес",
    },
    # ─── Население (Росстат SDDS + Popul components) ───
    {
        "code": "population",
        "name": "Численность населения",
        "name_en": "Population",
        "unit": "млн чел.",
        "frequency": "annual",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/folder/12781",
        "description": (
            "Численность постоянного населения РФ на 1 января (млн чел.). "
            "Исторический ряд Росстата с 1897 года, с ежегодными значениями с 1970 года."
        ),
        "methodology": (
            "Источник — официальные XLSX Росстата Popul_1897+.xlsx и SDDS_population. "
            "Для 1897 и 1914 годов используется строка «в современных границах»."
        ),
        "parser_type": "rosstat_population",
        "model_config_json": {
            "forecast_steps": 0,
            "validation": {"min": 50, "max": 200},
        },
        "is_active": True,
        "category": "Население",
    },
    {
        "code": "population-natural-growth",
        "name": "Естественный прирост населения",
        "name_en": "Natural Population Growth",
        "unit": "тыс. чел.",
        "frequency": "annual",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/folder/12781",
        "description": (
            "Естественный прирост населения (рождения минус смерти), "
            "тысяч человек в год. Данные Росстата с 1990 года."
        ),
        "parser_type": "rosstat_population",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "Население",
    },
    {
        "code": "population-total-growth",
        "name": "Общий прирост населения",
        "name_en": "Total Population Growth",
        "unit": "тыс. чел.",
        "frequency": "annual",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/folder/12781",
        "description": (
            "Общий прирост населения (естественный + миграционный), "
            "тысяч человек в год. Данные Росстата с 1990 года."
        ),
        "parser_type": "rosstat_population",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "Население",
    },
    {
        "code": "population-migration",
        "name": "Миграционный прирост",
        "name_en": "Migration Growth",
        "unit": "тыс. чел.",
        "frequency": "annual",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/folder/12781",
        "description": (
            "Миграционный прирост населения, тысяч человек в год. "
            "Данные Росстата с 1990 года."
        ),
        "parser_type": "rosstat_population",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "Население",
    },
    # ─── Внешняя торговля (ЦБ DataService — BOP) ───
    {
        "code": "current-account",
        "name": "Сальдо текущего счёта",
        "name_en": "Current Account Balance",
        "unit": "млн $",
        "frequency": "quarterly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/svs/",
        "description": (
            "Сальдо счёта текущих операций платёжного баланса РФ. "
            "Квартальные данные в млн долларов. Источник: Банк России."
        ),
        "parser_type": "cbr_dataservice_json",
        "model_config_json": {
            "dataservice": {
                "publicationId": 8,
                "datasetId": 9,
                "measureId": None,
                "element_id": None,
                "date_offset_months": 0,
            },
            "backfill_from_year": 2000,
            "forecast_steps": 0,
            "forecast_transform": "absolute",
        },
        "is_active": True,
        "category": "Торговля",
    },
    # ─── Производные: безработица агрегаты ───
    {
        "code": "unemployment-quarterly",
        "name": "Безработица квартальная",
        "name_en": "Quarterly Unemployment Rate",
        "unit": "%",
        "frequency": "quarterly",
        "source": "Расчёт",
        "description": (
            "Среднее значение месячного уровня безработицы за квартал."
        ),
        "parser_type": "derived",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "Рынок труда",
    },
    {
        "code": "unemployment-annual",
        "name": "Безработица среднегодовая",
        "name_en": "Annual Unemployment Rate",
        "unit": "%",
        "frequency": "monthly",
        "source": "Расчёт",
        "description": (
            "Скользящее среднее уровня безработицы за последние 12 месяцев."
        ),
        "parser_type": "derived",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "Рынок труда",
    },
    # ─── Производные: текущий счёт г/г ───
    {
        "code": "current-account-yoy",
        "name": "Текущий счёт (изм. г/г)",
        "name_en": "Current Account YoY Change",
        "unit": "%",
        "frequency": "quarterly",
        "source": "Расчёт",
        "description": "Изменение сальдо текущего счёта к аналогичному кварталу предыдущего года.",
        "parser_type": "derived",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "Торговля",
    },
    # ─── Производные: ИПП год к году ───
    {
        "code": "ipi-yoy",
        "name": "ИПП (изм. г/г)",
        "name_en": "Industrial Production YoY",
        "unit": "%",
        "frequency": "monthly",
        "source": "Расчёт",
        "description": "Изменение индекса промышленного производства к аналогичному месяцу предыдущего года.",
        "parser_type": "derived",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "Бизнес",
    },
    # ─── ИЦП (Росстат SDDS Price Indices) ───
    {
        "code": "ppi",
        "name": "Индекс цен производителей",
        "name_en": "Producer Price Index",
        "unit": "индекс",
        "frequency": "monthly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/price",
        "description": (
            "Индекс цен производителей промышленных товаров (2010=100). "
            "Ежемесячные данные SDDS Росстата."
        ),
        "methodology": (
            "Рассчитывается по ценам отгруженной продукции промышленных предприятий. "
            "Источник: SDDS XLSX Росстата (Price Indices)."
        ),
        "parser_type": "rosstat_sdds_ppi",
        "model_config_json": {
            "forecast_steps": 12,
            "forecast_model_name": "Approved-PPI-Notebook",
            "approved_forecast_values": [
                {"date": "2026-03-01", "value": 307.809703},
                {"date": "2026-04-01", "value": 309.304368},
                {"date": "2026-05-01", "value": 310.806289},
                {"date": "2026-06-01", "value": 312.315504},
                {"date": "2026-07-01", "value": 313.832048},
                {"date": "2026-08-01", "value": 315.355955},
                {"date": "2026-09-01", "value": 316.887262},
                {"date": "2026-10-01", "value": 318.426005},
                {"date": "2026-11-01", "value": 319.972220},
                {"date": "2026-12-01", "value": 321.525943},
                {"date": "2027-01-01", "value": 323.087210},
                {"date": "2027-02-01", "value": 324.656059},
            ],
            "forecast_transform": "absolute",
            "validation": {"min": 50, "max": 500},
        },
        "is_active": True,
        "category": "Цены",
    },
    # ─── Внешняя торговля (ЦБ BOP XLSX) ───
    {
        "code": "exports",
        "name": "Экспорт товаров",
        "name_en": "Goods Exports",
        "unit": "млн $",
        "frequency": "quarterly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/macro_itm/svs/",
        "description": (
            "Экспорт товаров из России (по методологии платёжного баланса). "
            "Квартальные данные в млн долларов. Источник: ЦБ РФ."
        ),
        "parser_type": "cbr_bop_xlsx",
        "model_config_json": {
            "bop_target": "exports",
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "validation": {"min": 0},
        },
        "is_active": True,
        "category": "Торговля",
    },
    {
        "code": "imports",
        "name": "Импорт товаров",
        "name_en": "Goods Imports",
        "unit": "млн $",
        "frequency": "quarterly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/macro_itm/svs/",
        "description": (
            "Импорт товаров в Россию (по методологии платёжного баланса). "
            "Квартальные данные в млн долларов. Источник: ЦБ РФ."
        ),
        "parser_type": "cbr_bop_xlsx",
        "model_config_json": {
            "bop_target": "imports",
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "validation": {"min": 0},
        },
        "is_active": True,
        "category": "Торговля",
    },
    {
        "code": "trade-balance",
        "name": "Торговый баланс",
        "name_en": "Trade Balance",
        "unit": "млн $",
        "frequency": "quarterly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/macro_itm/svs/",
        "description": (
            "Торговый баланс (экспорт минус импорт товаров) по методологии "
            "платёжного баланса. Квартальные данные. Источник: ЦБ РФ."
        ),
        "parser_type": "cbr_bop_xlsx",
        "model_config_json": {
            "bop_target": "trade-balance",
            "forecast_steps": 0,
            "forecast_transform": "absolute",
        },
        "is_active": True,
        "category": "Торговля",
    },
    # ─── Производные: торговля г/г ───
    {
        "code": "exports-yoy",
        "name": "Экспорт (изм. г/г)",
        "name_en": "Exports YoY Change",
        "unit": "%",
        "frequency": "quarterly",
        "source": "Расчёт",
        "description": "Изменение экспорта товаров к аналогичному кварталу предыдущего года.",
        "parser_type": "derived",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "Торговля",
    },
    {
        "code": "imports-yoy",
        "name": "Импорт (изм. г/г)",
        "name_en": "Imports YoY Change",
        "unit": "%",
        "frequency": "quarterly",
        "source": "Расчёт",
        "description": "Изменение импорта товаров к аналогичному кварталу предыдущего года.",
        "parser_type": "derived",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "Торговля",
    },
    # ─── Международные резервы (ЦБ HTML) ───
    {
        "code": "international-reserves",
        "name": "Международные резервы",
        "name_en": "International Reserves",
        "unit": "млрд $",
        "frequency": "weekly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/hd_base/mrrf/mrrf_7d/",
        "description": (
            "Международные (золотовалютные) резервы Российской Федерации. "
            "Еженедельные данные Банка России в млрд долларов."
        ),
        "methodology": (
            "Публикуются ЦБ РФ еженедельно на основе учётных данных. "
            "Включают валютные резервы, СДР, позицию в МВФ и монетарное золото."
        ),
        "parser_type": "cbr_reserves_html",
        "model_config_json": {
            "forecast_steps": 0,
            "validation": {"min": 0, "max": 2000},
        },
        "is_active": True,
        "category": "Финансы",
    },
    # ─── Внешний долг (ЦБ XLSX) ───
    {
        "code": "external-debt",
        "name": "Внешний долг",
        "name_en": "External Debt",
        "unit": "млн $",
        "frequency": "quarterly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/macro_itm/svs/",
        "description": (
            "Внешний долг Российской Федерации (всего). "
            "Квартальные данные в млн долларов с 2003 года. Источник: ЦБ РФ."
        ),
        "parser_type": "cbr_debt_xlsx",
        "model_config_json": {
            "forecast_steps": 0,
            "validation": {"min": 0},
        },
        "is_active": True,
        "category": "Финансы",
    },
    # ─── Производные: ИЦП г/г ───
    {
        "code": "ppi-yoy",
        "name": "ИЦП (изм. г/г)",
        "name_en": "Producer Price Index YoY",
        "unit": "%",
        "frequency": "monthly",
        "source": "Расчёт",
        "description": "Изменение индекса цен производителей к аналогичному месяцу предыдущего года.",
        "parser_type": "derived",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "housing-yoy-primary",
        "name": "Цены на первичное жильё (изм. г/г)",
        "name_en": "Primary Housing Prices YoY",
        "unit": "%",
        "frequency": "quarterly",
        "source": "Расчёт",
        "description": (
            "Изменение индекса цен на первичном рынке жилья к аналогичному кварталу "
            "предыдущего года. Расчёт на основе housing-price-primary."
        ),
        "parser_type": "derived",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "housing-yoy-secondary",
        "name": "Цены на вторичное жильё (изм. г/г)",
        "name_en": "Secondary Housing Prices YoY",
        "unit": "%",
        "frequency": "quarterly",
        "source": "Расчёт",
        "description": (
            "Изменение индекса цен на вторичном рынке жилья к аналогичному кварталу "
            "предыдущего года. Расчёт на основе housing-price-secondary."
        ),
        "parser_type": "derived",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "Цены",
    },
    # ─── Компоненты ВВП (Росстат SDDS National Accounts) ───
    {
        "code": "gdp-consumption",
        "name": "Расходы домохозяйств",
        "name_en": "Household Consumption",
        "unit": "млрд руб.",
        "frequency": "quarterly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/accounts",
        "description": (
            "Расходы на конечное потребление домашних хозяйств в текущих ценах. "
            "Компонент ВВП по расходному методу. Квартальные данные."
        ),
        "parser_type": "rosstat_sdds_gdp",
        "model_config_json": {
            "gdp_row_index": 4,
            "forecast_steps": 0,
            "validation": {"min": 0},
        },
        "is_active": True,
        "category": "ВВП",
    },
    {
        "code": "gdp-government",
        "name": "Государственное потребление",
        "name_en": "Government Consumption",
        "unit": "млрд руб.",
        "frequency": "quarterly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/accounts",
        "description": (
            "Расходы на конечное потребление государственного управления в текущих ценах. "
            "Компонент ВВП по расходному методу."
        ),
        "parser_type": "rosstat_sdds_gdp",
        "model_config_json": {
            "gdp_row_index": 5,
            "forecast_steps": 0,
            "validation": {"min": 0},
        },
        "is_active": True,
        "category": "ВВП",
    },
    {
        "code": "gdp-investment",
        "name": "Инвестиции в основной капитал",
        "name_en": "Gross Fixed Capital Formation",
        "unit": "млрд руб.",
        "frequency": "quarterly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/accounts",
        "description": (
            "Валовое накопление основного капитала в текущих ценах. "
            "Включает строительство, оборудование, транспорт. Квартальные данные."
        ),
        "parser_type": "rosstat_sdds_gdp",
        "model_config_json": {
            "gdp_row_index": 8,
            "forecast_steps": 0,
            "validation": {"min": 0},
        },
        "is_active": True,
        "category": "Бизнес",
    },
    # ─── Рынок труда: рабочая сила и занятость ───
    {
        "code": "labor-force",
        "name": "Рабочая сила",
        "name_en": "Labor Force",
        "unit": "млн чел.",
        "frequency": "monthly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/labor_market_employment_salaries",
        "description": (
            "Численность экономически активного населения (рабочая сила). "
            "Данные обследования рабочей силы Росстата."
        ),
        "parser_type": "rosstat_sdds_labor",
        "model_config_json": {
            "forecast_steps": 0,
            "validation": {"min": 50, "max": 100},
        },
        "is_active": True,
        "category": "Рынок труда",
    },
    {
        "code": "employment",
        "name": "Занятое население",
        "name_en": "Employment",
        "unit": "млн чел.",
        "frequency": "monthly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/labor_market_employment_salaries",
        "description": (
            "Численность занятого населения по данным обследования рабочей силы Росстата."
        ),
        "parser_type": "rosstat_sdds_labor",
        "model_config_json": {
            "forecast_steps": 0,
            "validation": {"min": 50, "max": 100},
        },
        "is_active": True,
        "category": "Рынок труда",
    },
    {
        "code": "wages-yoy",
        "name": "Зарплаты (изм. г/г)",
        "name_en": "Wages YoY Change",
        "unit": "%",
        "frequency": "monthly",
        "source": "Расчёт",
        "description": "Изменение средней номинальной зарплаты к аналогичному месяцу предыдущего года.",
        "parser_type": "derived",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "Рынок труда",
    },
    # ─── Бюджет: доходы и расходы (Минфин CSV) ───
    {
        "code": "budget-revenue",
        "name": "Доходы бюджета",
        "name_en": "Federal Budget Revenue",
        "unit": "млрд руб.",
        "frequency": "monthly",
        "source": "Минфин",
        "source_url": "https://minfin.gov.ru/ru/statistics/fedbud/execute/",
        "description": (
            "Доходы федерального бюджета помесячно. "
            "Рассчитываются из нарастающего итога открытых данных Минфина."
        ),
        "parser_type": "minfin_budget_csv",
        "model_config_json": {
            "budget_target": "revenue",
            "forecast_steps": 0,
            "forecast_transform": "absolute",
        },
        "is_active": True,
        "category": "Финансы",
    },
    {
        "code": "budget-expenditure",
        "name": "Расходы бюджета",
        "name_en": "Federal Budget Expenditure",
        "unit": "млрд руб.",
        "frequency": "monthly",
        "source": "Минфин",
        "source_url": "https://minfin.gov.ru/ru/statistics/fedbud/execute/",
        "description": (
            "Расходы федерального бюджета помесячно. "
            "Рассчитываются из нарастающего итога открытых данных Минфина."
        ),
        "parser_type": "minfin_budget_csv",
        "model_config_json": {
            "budget_target": "expenditure",
            "forecast_steps": 0,
            "forecast_transform": "absolute",
        },
        "is_active": True,
        "category": "Финансы",
    },
    # ─── Услуги BOP (ЦБ BOP XLSX) ───
    {
        "code": "services-exports",
        "name": "Экспорт услуг",
        "name_en": "Services Exports",
        "unit": "млн $",
        "frequency": "quarterly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/macro_itm/svs/",
        "description": (
            "Экспорт услуг из России по методологии платёжного баланса. "
            "Квартальные данные в млн долларов."
        ),
        "parser_type": "cbr_bop_xlsx",
        "model_config_json": {
            "bop_target": "services-exports",
            "forecast_steps": 0,
        },
        "is_active": True,
        "category": "Торговля",
    },
    {
        "code": "services-imports",
        "name": "Импорт услуг",
        "name_en": "Services Imports",
        "unit": "млн $",
        "frequency": "quarterly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/macro_itm/svs/",
        "description": (
            "Импорт услуг в Россию по методологии платёжного баланса. "
            "Квартальные данные в млн долларов."
        ),
        "parser_type": "cbr_bop_xlsx",
        "model_config_json": {
            "bop_target": "services-imports",
            "forecast_steps": 0,
        },
        "is_active": True,
        "category": "Торговля",
    },
    {
        "code": "fdi-net",
        "name": "Прямые иностранные инвестиции (нетто)",
        "name_en": "Foreign Direct Investment Net",
        "unit": "млн $",
        "frequency": "quarterly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/macro_itm/svs/",
        "description": (
            "Чистый приток прямых иностранных инвестиций по финансовому счёту. "
            "Квартальные данные платёжного баланса ЦБ."
        ),
        "parser_type": "cbr_bop_xlsx",
        "model_config_json": {
            "bop_target": "fdi-net",
            "forecast_steps": 0,
        },
        "is_active": True,
        "category": "Бизнес",
    },
    # ─── Производные: торговля кв/кв ───
    {
        "code": "exports-qoq",
        "name": "Экспорт (изм. кв/кв)",
        "name_en": "Exports QoQ Change",
        "unit": "%",
        "frequency": "quarterly",
        "source": "Расчёт",
        "description": "Изменение экспорта товаров к предыдущему кварталу.",
        "parser_type": "derived",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "Торговля",
    },
    {
        "code": "imports-qoq",
        "name": "Импорт (изм. кв/кв)",
        "name_en": "Imports QoQ Change",
        "unit": "%",
        "frequency": "quarterly",
        "source": "Расчёт",
        "description": "Изменение импорта товаров к предыдущему кварталу.",
        "parser_type": "derived",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "Торговля",
    },
    # ─── Демография (Росстат) ───
    {
        "code": "births",
        "name": "Число рождений",
        "name_en": "Number of Births",
        "unit": "тыс. чел.",
        "frequency": "annual",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/folder/12781",
        "description": "Число родившихся за год (тысяч человек). Данные Росстата с 1990 года.",
        "parser_type": "rosstat_demo",
        "model_config_json": {"demo_file": "demo21", "demo_series": "births", "forecast_steps": 0},
        "is_active": True,
        "category": "Население",
    },
    {
        "code": "deaths",
        "name": "Число смертей",
        "name_en": "Number of Deaths",
        "unit": "тыс. чел.",
        "frequency": "annual",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/folder/12781",
        "description": "Число умерших за год (тысяч человек). Данные Росстата с 1990 года.",
        "parser_type": "rosstat_demo",
        "model_config_json": {"demo_file": "demo21", "demo_series": "deaths", "forecast_steps": 0},
        "is_active": True,
        "category": "Население",
    },
    {
        "code": "birth-rate",
        "name": "Коэффициент рождаемости",
        "name_en": "Birth Rate",
        "unit": "‰",
        "frequency": "annual",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/folder/12781",
        "description": "Число родившихся на 1000 человек населения. Данные Росстата.",
        "parser_type": "rosstat_demo",
        "model_config_json": {"demo_file": "demo21", "demo_series": "birth-rate", "forecast_steps": 0},
        "is_active": True,
        "category": "Население",
    },
    {
        "code": "death-rate",
        "name": "Коэффициент смертности",
        "name_en": "Death Rate",
        "unit": "‰",
        "frequency": "annual",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/folder/12781",
        "description": "Число умерших на 1000 человек населения. Данные Росстата.",
        "parser_type": "rosstat_demo",
        "model_config_json": {"demo_file": "demo21", "demo_series": "death-rate", "forecast_steps": 0},
        "is_active": True,
        "category": "Население",
    },
    {
        "code": "working-age-population",
        "name": "Население в трудоспособном возрасте",
        "name_en": "Working-Age Population",
        "unit": "млн чел.",
        "frequency": "annual",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/folder/12781",
        "description": "Численность населения в трудоспособном возрасте (мужчины 16–59, женщины 16–54 лет). Данные Росстата.",
        "parser_type": "rosstat_demo",
        "model_config_json": {"demo_file": "demo14", "demo_series": "working-age-population", "forecast_steps": 0},
        "is_active": True,
        "category": "Население",
    },
    {
        "code": "pop-under-working-age",
        "name": "Население моложе трудоспособного возраста",
        "name_en": "Population Below Working Age",
        "unit": "млн чел.",
        "frequency": "annual",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/folder/12781",
        "description": "Численность населения моложе трудоспособного возраста (0–15 лет). Данные Росстата из таблицы demo14.",
        "parser_type": "rosstat_demo",
        "model_config_json": {"demo_file": "demo14", "demo_series": "pop-under-working-age", "forecast_steps": 0},
        "is_active": True,
        "category": "Население",
    },
    {
        "code": "pop-over-working-age",
        "name": "Население старше трудоспособного возраста",
        "name_en": "Population Above Working Age",
        "unit": "млн чел.",
        "frequency": "annual",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/folder/12781",
        "description": "Численность населения старше трудоспособного возраста (мужчины 60+, женщины 55+). Данные Росстата из таблицы demo14.",
        "parser_type": "rosstat_demo",
        "model_config_json": {"demo_file": "demo14", "demo_series": "pop-over-working-age", "forecast_steps": 0},
        "is_active": True,
        "category": "Население",
    },
    {
        "code": "pensioners",
        "name": "Численность пенсионеров",
        "name_en": "Number of Pensioners",
        "unit": "тыс. чел.",
        "frequency": "annual",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/folder/13877",
        "description": "Общая численность пенсионеров в РФ (тыс. чел. на 1 января). Данные Росстата/СФР.",
        "parser_type": "rosstat_demo",
        "model_config_json": {"demo_file": "pensioners", "forecast_steps": 0},
        "is_active": True,
        "category": "Население",
    },
    # ─── Розничная торговля (Росстат ежемесячный сборник) ───
    {
        "code": "retail-trade",
        "name": "Оборот розничной торговли",
        "name_en": "Retail Trade Turnover",
        "unit": "млрд руб.",
        "frequency": "monthly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/folder/10705",
        "description": (
            "Оборот розничной торговли в текущих ценах (млрд руб.). "
            "Ежемесячные данные из сборника индикаторов Росстата."
        ),
        "parser_type": "rosstat_ind_monthly",
        "model_config_json": {
            "ind_sheet": "1.12 ",
            "forecast_steps": 6,
            "forecast_transform": "absolute",
            "validation": {"min": 0},
        },
        "is_active": True,
        "category": "Бизнес",
    },
    # ─── Строительные работы (Росстат КЭП) ───
    {
        "code": "construction-work",
        "name": "Объём строительных работ",
        "name_en": "Construction Work Volume",
        "unit": "млрд руб.",
        "frequency": "monthly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/compendium/document/50802",
        "description": "Объём работ, выполненных по виду деятельности «Строительство». Включает новое строительство, капремонт, реконструкцию и модернизацию.",
        "methodology": "Данные из Краткосрочных экономических показателей (КЭП), публикуемых Росстатом. Лист 1.7, месячные данные в колонках G-R.",
        "parser_type": "rosstat_ind_monthly",
        "model_config_json": {"forecast_steps": 0, "ind_sheet": "1.7 "},
        "is_active": True,
        "category": "Бизнес",
    },
    # ─── Инвестиции в основной капитал (Росстат КЭП) ───
    {
        "code": "capital-investment",
        "name": "Инвестиции в основной капитал",
        "name_en": "Fixed Capital Investment",
        "unit": "млрд руб.",
        "frequency": "monthly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/compendium/document/50802",
        "description": "Инвестиции в основной капитал — затраты на создание и воспроизводство основных средств: строительство, приобретение оборудования, транспорта, IT-инфраструктуры.",
        "methodology": "Данные из Краткосрочных экономических показателей (КЭП), публикуемых Росстатом. Лист 1.6, месячные данные в колонках G-R.",
        "parser_type": "rosstat_ind_monthly",
        "model_config_json": {"forecast_steps": 0, "ind_sheet": "1.6 "},
        "is_active": True,
        "category": "Бизнес",
    },
    # ─── Ввод жилья (Росстат ежемесячный сборник) ───
    {
        "code": "housing-commissioned",
        "name": "Ввод в действие жилых домов",
        "name_en": "Housing Commissioned",
        "unit": "млн кв.м",
        "frequency": "monthly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/folder/10705",
        "description": (
            "Ввод в действие жилых домов (млн кв.м общей площади). "
            "Ежемесячные данные из сборника индикаторов Росстата."
        ),
        "parser_type": "rosstat_ind_monthly",
        "model_config_json": {
            "ind_sheet": "1.8 ",
            "forecast_steps": 0,
            "validation": {"min": 0},
        },
        "is_active": True,
        "category": "Бизнес",
    },
    # ─── Степень износа основных фондов ───
    {
        "code": "depreciation-rate",
        "name": "Степень износа основных фондов",
        "name_en": "Fixed Capital Depreciation Rate",
        "unit": "%",
        "frequency": "annual",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/folder/14304",
        "description": "Степень износа основных фондов (%). Годовые данные Росстата с 1990 года.",
        "parser_type": "rosstat_fixed_assets",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "Бизнес",
    },
    # ─── Наука и образование ───
    {
        "code": "grad-students",
        "name": "Численность аспирантов",
        "name_en": "Graduate Students",
        "unit": "чел.",
        "frequency": "annual",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/science",
        "description": "Численность аспирантов на начало учебного года. Данные Росстата.",
        "parser_type": "rosstat_science",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "Наука",
    },
    {
        "code": "doctoral-students",
        "name": "Численность докторантов",
        "name_en": "Doctoral Students",
        "unit": "чел.",
        "frequency": "annual",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/science",
        "description": "Численность докторантов на начало учебного года. Данные Росстата.",
        "parser_type": "rosstat_science",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "Наука",
    },
    {
        "code": "rd-organizations",
        "name": "Число организаций НИР",
        "name_en": "R&D Organizations",
        "unit": "ед.",
        "frequency": "annual",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/science",
        "description": "Число организаций, выполнявших научные исследования и разработки. Данные Росстата.",
        "parser_type": "rosstat_science",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "Наука",
    },
    {
        "code": "rd-personnel",
        "name": "Персонал НИР",
        "name_en": "R&D Personnel",
        "unit": "чел.",
        "frequency": "annual",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/science",
        "description": "Численность персонала, занятого научными исследованиями и разработками. Данные Росстата.",
        "parser_type": "rosstat_science",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "Наука",
    },
    {
        "code": "innovation-activity",
        "name": "Уровень инновационной активности",
        "name_en": "Innovation Activity Level",
        "unit": "%",
        "frequency": "annual",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/science",
        "description": "Уровень инновационной активности организаций (%). Данные Росстата.",
        "parser_type": "rosstat_science",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "Наука",
    },
    {
        "code": "tech-innovation-share",
        "name": "Доля организаций с технол. инновациями",
        "name_en": "Technology Innovation Share",
        "unit": "%",
        "frequency": "annual",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/science",
        "description": (
            "Удельный вес организаций, осуществлявших технологические инновации "
            "в отчётном году (%). Данные Росстата."
        ),
        "parser_type": "rosstat_science",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "Наука",
    },
    {
        "code": "small-business-innovation",
        "name": "Инновации малых предприятий",
        "name_en": "Small Business Innovation",
        "unit": "%",
        "frequency": "annual",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/science",
        "description": (
            "Удельный вес малых предприятий, осуществлявших "
            "инновационную деятельность (%). Данные Росстата."
        ),
        "parser_type": "rosstat_science",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "Наука",
    },
    # ─── Цена золота (ЦБ учётные цены) ───
    {
        "code": "gold-price",
        "name": "Цена золота (ЦБ)",
        "name_en": "Gold Price (CBR)",
        "unit": "руб./г",
        "frequency": "daily",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/hd_base/metall/metall_base_new/",
        "description": (
            "Учётная цена на золото, устанавливаемая Банком России. "
            "Ежедневные данные в рублях за грамм."
        ),
        "parser_type": "cbr_gold_html",
        "model_config_json": {
            "metal": "gold",
            "forecast_steps": 0,
            "validation": {"min": 100},
        },
        "is_active": True,
        "category": "Финансы",
    },
]


async def seed():
    async with async_session() as db:
        # Seed indicators — upsert metadata, preserve data
        _metadata_cols = [
            "name", "name_en", "unit", "frequency", "source", "source_url",
            "description", "methodology", "parser_type", "model_config_json",
            "is_active", "category", "excel_sheet",
        ]
        _attr_to_col = {"model_config_json": "model_config"}
        for ind_data in INDICATORS:
            stmt = pg_insert(Indicator).values(**ind_data)
            update_vals = {
                _attr_to_col.get(k, k): ind_data[k]
                for k in _metadata_cols if k in ind_data
            }
            stmt = stmt.on_conflict_do_update(
                index_elements=["code"],
                set_=update_vals,
            )
            await db.execute(stmt)
            print(f"  Upserted indicator: {ind_data['code']}")

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
        # Реактивировать торговые индикаторы (теперь парсятся из BOP XLSX ЦБ)
        for trade_code, trade_parser, trade_target in [
            ("exports", "cbr_bop_xlsx", "exports"),
            ("imports", "cbr_bop_xlsx", "imports"),
            ("trade-balance", "cbr_bop_xlsx", "trade-balance"),
        ]:
            await db.execute(
                update(Indicator)
                .where(Indicator.code == trade_code)
                .values(
                    is_active=True,
                    parser_type=trade_parser,
                    source="Банк России",
                    source_url="https://www.cbr.ru/statistics/macro_itm/svs/",
                )
            )
        for yoy_code in ("exports-yoy", "imports-yoy"):
            await db.execute(
                update(Indicator)
                .where(Indicator.code == yoy_code)
                .values(is_active=True, parser_type="derived")
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
    """Generate forecasts for all active indicators that have enough data."""
    async with async_session() as db:
        ind_q = await db.execute(
            select(Indicator).where(Indicator.is_active.is_(True))
        )
        indicators = ind_q.scalars().all()

        for indicator in indicators:
            await retrain_indicator_forecast(db, indicator)
            await db.commit()
            print(f"  {indicator.code}: forecast state refreshed")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--forecast-only":
        print("Generating forecasts...")
        asyncio.run(generate_forecasts())
    else:
        print("Seeding database...")
        asyncio.run(seed())
    print("Done.")

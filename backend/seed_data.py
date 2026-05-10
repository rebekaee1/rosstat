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

from sqlalchemy import delete, extract, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from app.database import async_session
from app.models import Indicator, IndicatorData
from app.services.forecast_pipeline import retrain_indicator_forecast
from app.data.indicator_seo import (
    INDICATOR_SEO,
    INDICATOR_SEO_BLOCKS,
    INDICATOR_SEO_KEYWORDS,
    INDICATOR_HIDDEN_FROM_LISTING,
    default_keywords,
)

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
        "source_url": "https://www.cbr.ru/statistics/bank_sector/int_rat/",
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
        "source_url": "https://www.cbr.ru/statistics/bank_sector/int_rat/",
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
        "source_url": "https://www.cbr.ru/statistics/bank_sector/int_rat/",
        "description": (
            "Средневзвешенная процентная ставка по автокредитам "
            "физическим лицам в рублях, по всем срокам."
        ),
        "parser_type": "cbr_dataservice_json",
        "model_config_json": {
            "dataservice": {
                # ЦБ в декабре 2025 переразложил dataset 28: исторические срезы
                # по срочности (id 2/4/5/6/7/9/10/11) больше не публикуются,
                # остался только агрегированный element_id=110 («По всем срокам»).
                # Полная история (~146 точек, 2014→2026) перевыложена под id=110.
                "publicationId": 14,
                "datasetId": 28,
                "measureId": 2,
                "element_id": 110,
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
        "source_url": "https://www.cbr.ru/statistics/bank_sector/int_rat/",
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
        "source_url": "https://www.cbr.ru/statistics/bank_sector/int_rat/",
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
        "source_url": "https://www.cbr.ru/statistics/bank_sector/int_rat/",
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
        "source_url": "https://www.cbr.ru/statistics/bank_sector/int_rat/",
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
        "source_url": "https://www.cbr.ru/statistics/bank_sector/int_rat/",
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
        "source_url": "https://www.cbr.ru/statistics/bank_sector/int_rat/",
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
            "Источник — SDDS Росстата. Обновляется ежемесячно."
        ),
        "parser_type": "rosstat_sdds_labor",
        "model_config_json": {
            "forecast_steps": 0,
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
            "Источник — SDDS Росстата. Обновляется ежемесячно."
        ),
        "parser_type": "rosstat_sdds_labor",
        "model_config_json": {
            "forecast_steps": 0,
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
        "source_url": "https://rosstat.gov.ru/statistics/accounts",
        "description": (
            "Валовой внутренний продукт в текущих ценах (по расходному методу). "
            "Квартальные данные."
        ),
        "methodology": (
            "Рассчитывается Росстатом по системе национальных счетов (СНС 2008). "
            "Источник — основная публикация Росстата `VVP_kvartal_s_1995-2025.xlsx` "
            "(раздел /statistics/accounts), лист 2 (текущие цены, ОКВЭД2, с 2011). "
            "Обновляется поквартально (T+45 дней prelim, T+90 final)."
        ),
        "parser_type": "rosstat_sdds_gdp",
        "model_config_json": {
            "gdp_source": "official_quarterly",
            "gdp_sheet": "2",
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
            "Источник — Росстат, ряды квартального ВВП в постоянных ценах 2021 г. "
            "по методологии СНС-2008. Обновляется поквартально."
        ),
        "parser_type": "rosstat_sdds_gdp",
        "model_config_json": {
            "gdp_source": "official_quarterly",
            "gdp_sheet": "9",
            "forecast_steps": 4,
            "forecast_strategy": "gdp_real_quarterly",
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
        "source": "Росстат",
        "description": (
            "Индекс реальной заработной платы: отношение номинальной зарплаты "
            "к индексу потребительских цен. Показывает покупательную способность."
        ),
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 0,
            "forecast_transform": "percentage",
        },
        "is_active": True,
        "category": "Рынок труда",
    },
    {
        "code": "gdp-yoy",
        "name": "Рост номинального ВВП (г/г)",
        "name_en": "Nominal GDP Growth YoY",
        "unit": "%",
        "frequency": "quarterly",
        "source": "Росстат",
        "description": (
            "Темп роста номинального ВВП (в текущих ценах) к аналогичному "
            "кварталу предыдущего года."
        ),
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 4,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "gdp-nominal",
                "operation": "yoy_quarterly",
                "model_name": "GDP-Nominal-YoY-Derived",
            },
        },
        "is_active": True,
        "category": "ВВП",
    },
    {
        "code": "gdp-qoq",
        "name": "Рост номинального ВВП (кв/кв)",
        "name_en": "Nominal GDP Growth QoQ",
        "unit": "%",
        "frequency": "quarterly",
        "source": "Росстат",
        "description": (
            "Темп роста номинального ВВП (в текущих ценах) к предыдущему кварталу."
        ),
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 4,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "gdp-nominal",
                "operation": "qoq",
                "model_name": "GDP-Nominal-QoQ-Derived",
            },
        },
        "is_active": True,
        "category": "ВВП",
    },
    {
        "code": "gdp-real-yoy",
        "name": "Рост реального ВВП (г/г)",
        "name_en": "Real GDP Growth YoY",
        "unit": "%",
        "frequency": "quarterly",
        "source": "Росстат",
        "description": (
            "Темп роста реального ВВП (в постоянных ценах 2021 г.) к аналогичному "
            "кварталу предыдущего года."
        ),
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 4,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "gdp-real",
                "operation": "yoy_quarterly",
                "model_name": "GDP-Real-YoY-Derived",
            },
        },
        "is_active": True,
        "category": "ВВП",
    },
    {
        "code": "gdp-real-qoq",
        "name": "Рост реального ВВП (кв/кв)",
        "name_en": "Real GDP Growth QoQ",
        "unit": "%",
        "frequency": "quarterly",
        "source": "Росстат",
        "description": (
            "Темп роста реального ВВП (в постоянных ценах 2021 г.) к предыдущему "
            "кварталу."
        ),
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 4,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "gdp-real",
                "operation": "qoq",
                "model_name": "GDP-Real-QoQ-Derived",
            },
        },
        "is_active": True,
        "category": "ВВП",
    },
    {
        "code": "gdp-nominal-annual",
        "name": "ВВП номинальный (годовой)",
        "name_en": "Nominal GDP Annual",
        "unit": "млрд руб.",
        "frequency": "annual",
        "source": "Росстат",
        "description": (
            "Номинальный ВВП, накопленный за календарный год — сумма четырёх "
            "квартальных значений в текущих ценах. Одна точка на каждый "
            "завершённый год."
        ),
        "methodology": (
            "Для каждого года Y: ВВП_nominal_Y = Σ ВВП_nominal_q за q ∈ Y "
            "(четыре квартала в текущих ценах). Прогноз — суммирование четырёх "
            "квартальных прогнозных значений из gdp-nominal."
        ),
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 2,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "gdp-nominal",
                "operation": "annual_sum",
                "model_name": "GDP-Nominal-Annual-Sum",
            },
            "validation": {"min": 0},
        },
        "is_active": True,
        "category": "ВВП",
    },
    {
        "code": "gdp-real-annual",
        "name": "ВВП реальный годовой",
        "name_en": "Real GDP Annual",
        "unit": "млрд руб.",
        "frequency": "annual",
        "source": "Росстат",
        "description": (
            "Реальный ВВП, накопленный за календарный год — сумма четырёх квартальных "
            "значений в постоянных ценах 2021 года. Одна точка на каждый завершённый год."
        ),
        "methodology": (
            "Для каждого года Y: ВВП_real_Y = Σ ВВП_real_q за q ∈ Y "
            "(четыре квартала в постоянных ценах). Прогноз — суммирование четырёх "
            "квартальных прогнозных значений из gdp-real."
        ),
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 2,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "gdp-real",
                "operation": "annual_sum",
                "model_name": "GDP-Real-Annual-Sum",
            },
            "validation": {"min": 0},
        },
        "is_active": True,
        "category": "ВВП",
    },
    {
        "code": "inflation-quarterly",
        "name": "Инфляция квартальная",
        "name_en": "Quarterly Inflation",
        "unit": "%",
        "frequency": "quarterly",
        "source": "Росстат",
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
        "frequency": "annual",
        "source": "Росстат",
        "description": (
            "Годовая инфляция «декабрь к декабрю»: произведение 12 месячных индексов "
            "потребительских цен внутри календарного года. Одна точка на каждый "
            "завершённый год — стандарт ЦБ и Росстата."
        ),
        "methodology": (
            "Для каждого года Y рассчитывается ∏(ИПЦ_m / 100) за m = январь…декабрь Y, "
            "затем результат переводится в проценты (× 100 − 100). Прогноз — то же "
            "произведение по 12 месячным значениям прогноза CPI-Monthly."
        ),
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 2,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "cpi",
                "operation": "december_to_december",
                "model_name": "Annual-Dec2Dec-CPI",
            },
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
        "source": "Росстат",
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
        "frequency": "annual",
        "source": "Росстат",
        "description": (
            "Годовая инфляция продовольствия «декабрь к декабрю»: произведение 12 "
            "месячных индексов потребительских цен на продовольственные товары "
            "внутри календарного года. Одна точка на каждый завершённый год."
        ),
        "methodology": (
            "Для каждого года Y: ∏(ИПЦ продовольствие_m / 100) за m = январь…декабрь Y, "
            "× 100 − 100. Прогноз — то же произведение по 12 месячным точкам прогноза CPI-food."
        ),
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 2,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "cpi-food",
                "operation": "december_to_december",
                "model_name": "Annual-Dec2Dec-CPI-Food",
            },
        },
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "cpi-nonfood-quarterly",
        "name": "Квартальная инфляция непродовольственных товаров",
        "name_en": "Non-food CPI Quarterly Inflation",
        "unit": "%",
        "frequency": "quarterly",
        "source": "Росстат",
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
        "frequency": "annual",
        "source": "Росстат",
        "description": (
            "Годовая инфляция непродовольственных товаров «декабрь к декабрю»: "
            "произведение 12 месячных индексов потребительских цен на "
            "непродовольственные товары внутри календарного года. Одна точка на год."
        ),
        "methodology": (
            "Для каждого года Y: ∏(ИПЦ непродовольств._m / 100) за m = январь…декабрь Y, "
            "× 100 − 100. Прогноз строится тем же произведением по месячным точкам "
            "прогноза CPI-nonfood."
        ),
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 2,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "cpi-nonfood",
                "operation": "december_to_december",
                "model_name": "Annual-Dec2Dec-CPI-Nonfood",
            },
        },
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "cpi-services-quarterly",
        "name": "Квартальная инфляция услуг",
        "name_en": "Services CPI Quarterly Inflation",
        "unit": "%",
        "frequency": "quarterly",
        "source": "Росстат",
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
        "frequency": "annual",
        "source": "Росстат",
        "description": (
            "Годовая инфляция услуг «декабрь к декабрю»: произведение 12 "
            "месячных индексов потребительских цен на услуги населению внутри "
            "календарного года. Одна точка на завершённый год."
        ),
        "methodology": (
            "Для каждого года Y: ∏(ИПЦ услуги_m / 100) за m = январь…декабрь Y, "
            "× 100 − 100. Прогноз — то же произведение по месячным точкам прогноза CPI-services."
        ),
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 2,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "cpi-services",
                "operation": "december_to_december",
                "model_name": "Annual-Dec2Dec-CPI-Services",
            },
        },
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
            # Прогноз для недельной инфляции выключен (решение НА от 2026-05-06):
            # Росстат публикует только за прошедшую неделю с лагом, ранние дни
            # новой недели дают слишком мало сигнала для обоснованного 8-недельного
            # прогноза. forecast_steps=0 → retrain_indicator_forecast() очищает
            # старые прогнозные ряды и API возвращает forecast=None.
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
            # Approved values from Никита's notebook
            # `Прогнозы_цены_на_жилье (1).ipynb` (May 2026), 4 quarters ahead.
            # Re-import when notebook is updated.
            "forecast_model_name": "Approved-Housing-Primary-Notebook",
            "approved_forecast_values": [
                {"date": "2026-03-01", "value": 345.357849},
                {"date": "2026-06-01", "value": 354.540996},
                {"date": "2026-09-01", "value": 361.433316},
                {"date": "2026-12-01", "value": 366.718878},
            ],
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
            # Reproduces Никита's quarterly OLS multi-window model from the
            # primary-housing notebook on our secondary series. When Никита
            # provides a secondary notebook, switch to approved_forecast_values.
            "forecast_model": "housing_quarterly",
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
            "forecast_steps": 0,
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
            "Источник — Росстат и SDDS Росстата. "
            "Для 1897 и 1914 годов используется ряд «в современных границах»."
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
        "source": "Росстат",
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
        "source": "Росстат",
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
        "source": "Банк России",
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
        "source": "Росстат",
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
            "Источник — SDDS Росстата."
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
        "source": "Банк России",
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
        "source": "Банк России",
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
        "source": "Росстат",
        "description": "Изменение индекса цен производителей к аналогичному месяцу предыдущего года.",
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 12,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "ppi",
                "operation": "yoy_monthly",
                "model_name": "PPI-YoY-Derived",
            },
        },
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "ppi-annual",
        "name": "ИЦП годовой (декабрь к декабрю)",
        "name_en": "Producer Price Index Annual",
        "unit": "%",
        "frequency": "annual",
        "source": "Росстат",
        "description": (
            "Годовая инфляция производителей «декабрь к декабрю»: произведение 12 "
            "месячных индексов цен производителей (ИЦП) внутри календарного года. "
            "Одна точка на каждый завершённый год."
        ),
        "methodology": (
            "Для каждого года Y: ∏(ИЦП_m / 100) за m = январь…декабрь Y, × 100 − 100. "
            "Прогноз — то же произведение по 12 месячным точкам прогноза PPI."
        ),
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 2,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "ppi",
                "operation": "december_to_december",
                "model_name": "Annual-Dec2Dec-PPI",
            },
        },
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "housing-yoy-primary",
        "name": "Цены на первичное жильё (изм. г/г)",
        "name_en": "Primary Housing Prices YoY",
        "unit": "%",
        "frequency": "quarterly",
        "source": "Росстат",
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
        "source": "Росстат",
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
        "source_url": "https://rosstat.gov.ru/statistics/accounts",
        "description": (
            "Расходы на конечное потребление домашних хозяйств в текущих ценах. "
            "Компонент ВВП по расходному методу. Квартальные данные."
        ),
        "methodology": (
            "Источник — `GDP-quarters-of-use-1995-4kv-2025.xls`, лист 2 (ОКВЭД2, с 2011), "
            "строка 8 (домашних хозяйств). Раздел rosstat.gov.ru/statistics/accounts."
        ),
        "parser_type": "rosstat_sdds_gdp",
        "model_config_json": {
            "gdp_source": "official_use",
            "gdp_sheet": "2",
            "gdp_row_index": 7,
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
        "source_url": "https://rosstat.gov.ru/statistics/accounts",
        "description": (
            "Расходы на конечное потребление государственного управления в текущих ценах. "
            "Компонент ВВП по расходному методу."
        ),
        "methodology": (
            "Источник — `GDP-quarters-of-use-1995-4kv-2025.xls`, лист 2 (ОКВЭД2, с 2011), "
            "строка 9 (государственного управления). Раздел rosstat.gov.ru/statistics/accounts."
        ),
        "parser_type": "rosstat_sdds_gdp",
        "model_config_json": {
            "gdp_source": "official_use",
            "gdp_sheet": "2",
            "gdp_row_index": 8,
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
        "source_url": "https://rosstat.gov.ru/statistics/accounts",
        "description": (
            "Валовое накопление основного капитала в текущих ценах. "
            "Включает строительство, оборудование, транспорт. Квартальные данные."
        ),
        "methodology": (
            "Источник — `GDP-quarters-of-use-1995-4kv-2025.xls`, лист 2 (ОКВЭД2, с 2011), "
            "строка 12 (валовое накопление основного капитала). Раздел rosstat.gov.ru/statistics/accounts."
        ),
        "parser_type": "rosstat_sdds_gdp",
        "model_config_json": {
            "gdp_source": "official_use",
            "gdp_sheet": "2",
            "gdp_row_index": 11,
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
        "source": "Росстат",
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
        "source": "Банк России",
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
        "source": "Банк России",
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
            "forecast_steps": 0,
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

        # Идемпотентная миграция (2026-05-06): семантика 4-х CPI-годовых индикаторов
        # сменилась с rolling-12M (monthly frequency, ~400 точек/индикатор) на
        # December-to-December (annual frequency, 1 точка/год). Удаляем старые
        # не-январские точки rolling-12M; январские (1-го числа) уже соответствуют
        # новой схеме «1 точка/год на 1 января» и будут перезаписаны
        # `bulk_upsert`-ом из CalculationEngine значениями новой формулы.
        # На повторных запусках seed_data не-январские точки уже удалены —
        # rowcount==0, операция NO-OP. Это критично: entrypoint.sh запускает
        # seed_data на каждом старте backend контейнера.
        ANNUAL_CPI_FAMILY = (
            "inflation-annual",
            "cpi-food-annual",
            "cpi-nonfood-annual",
            "cpi-services-annual",
        )
        for code in ANNUAL_CPI_FAMILY:
            ind_q = await db.execute(select(Indicator.id).where(Indicator.code == code))
            ind_id = ind_q.scalar_one_or_none()
            if ind_id is None:
                continue
            res = await db.execute(
                delete(IndicatorData)
                .where(IndicatorData.indicator_id == ind_id)
                .where(extract("month", IndicatorData.date) != 1)
            )
            if res.rowcount:
                print(f"  Cleaned {res.rowcount} stale rolling-12M points for {code}")
        await db.commit()

        # Backfill SEO metadata + listing visibility from data/indicator_seo.py
        # (single source of truth — DB columns indicators.seo_title/.seo_description
        # /.seo_keywords/.seo_blocks/.is_listed; this block makes the seed file
        # authoritative).
        seo_count = 0
        for code, vals in INDICATOR_SEO.items():
            await db.execute(
                update(Indicator)
                .where(Indicator.code == code)
                .values(
                    seo_title=vals["seo_title"],
                    seo_description=vals["seo_description"],
                )
            )
            seo_count += 1
        # seo_keywords: для каждого активного индикатора либо ручной override
        # из INDICATOR_SEO_KEYWORDS, либо генерация из (name + category + source).
        # Делаем после upsert, чтобы видеть актуальные name/category/source
        # из только что записанных строк.
        result = await db.execute(
            select(Indicator.code, Indicator.name, Indicator.category, Indicator.source)
        )
        kw_count = 0
        for code, name, category, source in result.all():
            kw = INDICATOR_SEO_KEYWORDS.get(code) or default_keywords(name, category, source)
            await db.execute(
                update(Indicator).where(Indicator.code == code).values(seo_keywords=kw)
            )
            kw_count += 1
        for code, blocks in INDICATOR_SEO_BLOCKS.items():
            await db.execute(
                update(Indicator)
                .where(Indicator.code == code)
                .values(seo_blocks=blocks)
            )
        # Reset is_listed to true everywhere first, then mark hidden codes false.
        await db.execute(update(Indicator).values(is_listed=True))
        for code in INDICATOR_HIDDEN_FROM_LISTING:
            await db.execute(
                update(Indicator)
                .where(Indicator.code == code)
                .values(is_listed=False)
            )
        await db.commit()
        print(
            f"  SEO metadata applied: {seo_count} titles/descriptions, "
            f"{kw_count} keywords sets, "
            f"{len(INDICATOR_SEO_BLOCKS)} block sets, "
            f"{len(INDICATOR_HIDDEN_FROM_LISTING)} hidden from listing"
        )

        # Re-run CalculationEngine to refresh ALL derived indicators after metadata
        # upserts and the migration cleanup. Idempotent: bulk_upsert is no-op for
        # unchanged values. Critical for the CPI-annual migration: after non-Jan
        # rolling-12M points are wiped, CE writes fresh December-to-December points
        # so the API serves the new shape immediately, without waiting for the
        # next ETL run at 06:00 МСК.
        try:
            from app.services.calculation_engine import (
                calculation_engine, DERIVED_SPECS,
            )
            all_sources = sorted({c for spec in DERIVED_SPECS for c in spec.src_codes})
            updated = await calculation_engine.run_for_updated_sources(db, all_sources)
            await db.commit()
            print(
                f"  CalculationEngine: refreshed derived from {len(all_sources)} "
                f"sources ({len(updated)} indicators changed)"
            )
        except Exception as exc:
            await db.rollback()
            print(f"  CalculationEngine refresh skipped: {exc}")

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
    """Generate forecasts for all active indicators that have enough data.

    Сперва прогоняем CalculationEngine: derived-индикаторы должны иметь
    свежие actuals до retrain, иначе derived_from_source стратегия будет
    смотреть на устаревший last_actual_date (актуально для свежих миграций
    типа CPI-annual rolling12M → December-to-December).
    """
    from app.services.calculation_engine import calculation_engine, DERIVED_SPECS

    async with async_session() as db:
        all_sources = sorted({c for spec in DERIVED_SPECS for c in spec.src_codes})
        try:
            await calculation_engine.run_for_updated_sources(db, all_sources)
            await db.commit()
            print(f"  CalculationEngine refreshed derived actuals from {len(all_sources)} sources")
        except Exception:
            await db.rollback()
            raise

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

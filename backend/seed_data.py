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
from app.data.view_model_families import iter_sibling_indicators as _iter_vmf_siblings

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
        "description": "Индекс потребительских цен на услуги.",
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
            "Историческая часть ряда до 13 сентября 2013 года представлена ставкой "
            "рефинансирования, которая выполняла ту же функцию до запуска ключевой ставки."
        ),
        "methodology": (
            "Официальный уровень ключевой ставки Банка России в процентах годовых: "
            "каждая точка — действующая ставка с даты её изменения; между заседаниями "
            "совета директоров значение не меняется. До 13 сентября 2013 года в ряде "
            "исторически указана ставка рефинансирования; с 2016 года она приравнена "
            "ключевой. На карточке также доступны средние по неделе, месяцу, кварталу "
            "и году — они рассчитываются из того же официального ряда."
        ),
        "parser_type": "cbr_keyrate_html",
        "model_config_json": {
            "forecast_steps": 0,
            "validation": {"min": 0, "max": 250},
        },
        "is_active": True,
        "category": "Ставки",
    },
    # ─── Курсы валют ───
    # D5: курсы валют выделены в отдельную категорию "Валюты" — это не общие
    # «Финансы», а самостоятельный fx-блок (по модели TradingEconomics).
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
            "Курс выражается в рублях за один доллар и обновляется ежедневно."
        ),
        "methodology": (
            "Официальный курс доллара к рублю, который Банк России устанавливает "
            "ежедневно на основе итогов валютного рынка. Каждая точка — курс "
            "на соответствующую дату в рублях за один доллар США. На карточке "
            "доступны ежедневное значение и средние по неделе, месяцу, "
            "кварталу и году — последние считаются из того же ряда для "
            "удобства сравнения тренда."
        ),
        "parser_type": "cbr_fx_xml",
        "model_config_json": {
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "validation": {"min": 1, "max": 500},
            # Пол истории — 1998-01-01 (деноминация рубля 1000:1). Раньше курс
            # выражался в «старых» рублях (1997-12 ≈ 5960), сплайс с новыми дал
            # бы разрыв ×1000 и не прошёл бы validation.max — поэтому floor 1998.
            "backfill_from": "1998-01-01",
        },
        "is_active": True,
        "category": "Валюты",
    },
    {
        "code": "eur-rub",
        "name": "Курс евро",
        "name_en": "EUR/RUB Exchange Rate",
        "unit": "руб.",
        "frequency": "daily",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/currency_base/daily/",
        "description": (
            "Официальный курс евро к рублю, устанавливаемый Банком России. "
            "Курс выражается в рублях за один евро и обновляется ежедневно."
        ),
        "methodology": (
            "Официальный курс евро к рублю, который Банк России устанавливает "
            "ежедневно на основе итогов валютного рынка. Каждая точка — курс "
            "на соответствующую дату в рублях за один евро. На карточке "
            "доступны ежедневное значение и средние по неделе, месяцу, "
            "кварталу и году — последние считаются из того же ряда для "
            "удобства сравнения тренда."
        ),
        "parser_type": "cbr_fx_xml",
        "model_config_json": {
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "validation": {"min": 1, "max": 500},
            # Евро у ЦБ — с 1999-01-01 (введение валюты), уже «новые» рубли.
            "backfill_from": "1999-01-01",
        },
        "is_active": True,
        "category": "Валюты",
    },
    {
        "code": "cny-rub",
        "name": "Курс юаня",
        "name_en": "CNY/RUB Exchange Rate",
        "unit": "руб.",
        "frequency": "daily",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/currency_base/daily/",
        "description": (
            "Официальный курс китайского юаня к рублю, устанавливаемый Банком России. "
            "Курс выражается в рублях за один юань и обновляется ежедневно."
        ),
        "methodology": (
            "Официальный курс юаня к рублю, который Банк России устанавливает "
            "ежедневно на основе итогов валютного рынка. Каждая точка — курс "
            "на соответствующую дату в рублях за один юань. На карточке "
            "доступны ежедневное значение и средние по неделе, месяцу, "
            "кварталу и году — последние считаются из того же ряда для "
            "удобства сравнения тренда."
        ),
        "parser_type": "cbr_fx_xml",
        "model_config_json": {
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "validation": {"min": 0.1, "max": 100},
            # Юань у ЦБ котируется давно; floor 1998-01-01 (новые рубли).
            "backfill_from": "1998-01-01",
        },
        "is_active": True,
        "category": "Валюты",
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
            "Индикативная взвешенная ставка однодневных рублёвых межбанковских "
            "кредитов и депозитов на условиях «овернайт»; рассчитывается Банком "
            "России по сделкам банков-участников. Публикуется по рабочим дням. "
            "На карточке доступны ежедневный уровень и средние по неделе, месяцу, "
            "кварталу и году — последние считаются из того же ряда для удобства "
            "сравнения."
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
        "methodology": (
            "Денежная масса М0 — наличные в обращении вне банков в млрд рублей "
            "на конец месяца по оценке Банка России. На карточке — помесячный "
            "ряд и средние по кварталу и году из того же источника; прогноз "
            "не строится. Семья «Денежные агрегаты» связывает М0 с узкой "
            "М1 и широкой М2 без сброса режима графика."
        ),
        "parser_type": "cbr_monetary_agg_xlsx",
        "model_config_json": {
            "monetary_agg": {
                "indicator": "M0",
                "date_offset_months": -1,
            },
            "backfill_from_year": 1993,
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
        "methodology": (
            "Широкая денежная масса М2 в млрд рублей на конец месяца — основной "
            "показатель ликвидности в определении Банка России. Помесячный "
            "ряд и средние по кварталу и году на карточке; прогноз не "
            "строится. В семье «Денежные агрегаты» рядом — наличные М0 и "
            "агрегат М1 для сопоставления на одних датах."
        ),
        "parser_type": "cbr_monetary_agg_xlsx",
        "model_config_json": {
            "monetary_agg": {
                "indicator": "M2",
                "date_offset_months": -1,
            },
            # XLSX ЦБ содержит M2 с 1992-12 — берём с самого начала (раньше
            # отсекали 1995, теряя ~2 года ранней истории).
            "backfill_from_year": 1992,
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
            "Средневзвешенная годовая ставка по ипотечным жилищным кредитам "
            "физических лиц-резидентов в рублях: в расчёт входят новые договоры "
            "и действующие сделки, веса — по объёмам выдач за месяц по отчётности "
            "банков. Публикуется Банком России ежемесячно, обычно с лагом "
            "один–два месяца. На карточке один режим — уровень ставки в процентах "
            "годовых, без отдельной разбивки по сроку."
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
        "name": "Ставка по вкладам физических лиц",
        "name_en": "Household Deposit Interest Rate",
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
    # ─── Ставки по вкладам ФЛ по срокам (CBR DataService) ───
    # Аналогично разбивке по кредитам — публикация publicationId=18, dataset=37
    # содержит ставки в разрезе срока вклада. element_id=9 (1-3 года), 10 (>3 лет).
    # Ряды доступны с января 2014 г. ежемесячно.
    {
        "code": "deposit-rate-medium",
        "name": "Ставка по вкладам на 1-3 года",
        "name_en": "Deposit Rate (1 to 3 years)",
        "unit": "%",
        "frequency": "monthly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/bank_sector/int_rat/",
        "description": (
            "Средневзвешенная процентная ставка по вкладам (депозитам) физических "
            "лиц в рублях со сроком от 1 года до 3 лет."
        ),
        "methodology": (
            "Средневзвешенная процентная ставка по среднесрочным вкладам в рублях, "
            "привлечённым кредитными организациями от физических лиц (срок от 1 года "
            "до 3 лет). Рассчитывается Банком России по форме отчётности 0409128. "
            "Публикуется ежемесячно."
        ),
        "parser_type": "cbr_dataservice_json",
        "model_config_json": {
            "dataservice": {
                "publicationId": 18,
                "datasetId": 37,
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
        "code": "deposit-rate-long",
        "name": "Ставка по вкладам свыше 3 лет",
        "name_en": "Deposit Rate (over 3 years)",
        "unit": "%",
        "frequency": "monthly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/bank_sector/int_rat/",
        "description": (
            "Средневзвешенная процентная ставка по вкладам (депозитам) физических "
            "лиц в рублях со сроком свыше 3 лет."
        ),
        "methodology": (
            "Средневзвешенная процентная ставка по долгосрочным вкладам в рублях, "
            "привлечённым кредитными организациями от физических лиц (срок свыше "
            "3 лет). Рассчитывается Банком России по форме отчётности 0409128. "
            "Публикуется ежемесячно."
        ),
        "parser_type": "cbr_dataservice_json",
        "model_config_json": {
            "dataservice": {
                "publicationId": 18,
                "datasetId": 37,
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
        "methodology": (
            "Средневзвешенная процентная ставка по новым и пролонгированным "
            "автокредитам в рублях, выданным кредитными организациями физическим "
            "лицам. Агрегат «по всем срокам» отражает взвешенную структуру "
            "выдач без разбивки по длительности договора. Рассчитывается Банком "
            "России по форме банковской отчётности о средневзвешенных ставках. "
            "Публикуется ежемесячно с лагом около одного месяца."
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
        "name": "Ставка по кредитам юридическим лицам",
        "name_en": "Corporate Loan Rate",
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
            "Средневзвешенная процентная ставка по краткосрочным кредитам в рублях, "
            "выданным юридическим лицам и индивидуальным предпринимателям "
            "(срок до 1 года). Рассчитывается Банком России по форме банковской "
            "отчётности 0409128. Публикуется ежемесячно."
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
            "Средневзвешенная процентная ставка по кредитам в рублях, выданным "
            "юридическим лицам и индивидуальным предпринимателям на срок "
            "от 1 года до 3 лет. Рассчитывается Банком России по форме "
            "банковской отчётности 0409128. Публикуется ежемесячно."
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
            "Средневзвешенная процентная ставка по долгосрочным кредитам в рублях, "
            "выданным юридическим лицам и индивидуальным предпринимателям "
            "(срок свыше 3 лет). Рассчитывается Банком России по форме "
            "банковской отчётности 0409128. Публикуется ежемесячно."
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
        "name": "Ставка по кредитам физическим лицам",
        "name_en": "Individual Loan Rate",
        "unit": "%",
        "frequency": "monthly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/bank_sector/int_rat/",
        "description": (
            "Средневзвешенная процентная ставка по кредитам физическим лицам "
            "в рублях со сроком погашения до 1 года, включая «до востребования»."
        ),
        "methodology": (
            "Средневзвешенная процентная ставка по краткосрочным кредитам в рублях, "
            "выданным физическим лицам (срок до 1 года). Рассчитывается "
            "Банком России по форме банковской отчётности 0409128. "
            "Публикуется ежемесячно."
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
            "Средневзвешенная процентная ставка по кредитам в рублях, выданным "
            "физическим лицам на срок от 1 года до 3 лет. Рассчитывается "
            "Банком России по форме банковской отчётности 0409128. "
            "Публикуется ежемесячно."
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
            "Средневзвешенная процентная ставка по долгосрочным кредитам в рублях, "
            "выданным физическим лицам (срок свыше 3 лет). Рассчитывается "
            "Банком России по форме банковской отчётности 0409128. "
            "Публикуется ежемесячно."
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
        "source_url": "https://rosstat.gov.ru/folder/210",
        "description": (
            "Доля безработных в экономически активном населении по методологии МОТ. "
            "Данные Росстата из обследования рабочей силы."
        ),
        "methodology": (
            "Уровень безработицы — доля безработных в рабочей силе в процентах "
            "на конец месяца по методологии Международной организации труда. "
            "Источник: обследование рабочей силы Росстата. На карточке — "
            "помесячный ряд, среднее по кварталам и скользящее 12-месячное "
            "среднее; переключатель «Сглаживание» выбирает отдельный ряд. "
            "Сопоставляйте с занятостью и рабочей силой в категории «Рынок труда»."
        ),
        "parser_type": "rosstat_labor",
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
        "source_url": "https://rosstat.gov.ru/folder/210",
        "description": (
            "Среднемесячная номинальная начисленная заработная плата "
            "работников организаций."
        ),
        "methodology": (
            "Среднемесячная номинальная начисленная заработная плата работников "
            "организаций: сумма начислений до удержания налога на доходы, "
            "включая социальные выплаты по правилам Росстата. Охват — крупные "
            "и средние организации; индивидуальные предприниматели и малый "
            "бизнес в показатель не входят. На карточке доступны помесячный "
            "ряд с 2015 года и годовая серия с 1991 года (переключатель частоты), "
            "а реальная заработная плата с поправкой на инфляцию — отдельный ряд "
            "в переключателе «Заработная плата». Публикация обычно с лагом около "
            "двух месяцев от отчётного периода."
        ),
        "parser_type": "rosstat_labor",
        "model_config_json": {
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "validation": {"min": 0},
            "alternate_frequencies": {"annual": "wages-nominal-annual"},
        },
        "is_active": True,
        "category": "Рынок труда",
    },
    # ─── ВВП (Росстат русский canonical, ADR-0004 + ratio-splice 1995+) ───
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
            "Валовой внутренний продукт России в текущих рыночных ценах "
            "по квартальным оценкам Росстата в системе национальных счетов. "
            "Каждая точка — объём за квартал в млрд рублей; история с 1995 года. "
            "Темпы год к году и квартал к кварталу, а также сумма за календарный "
            "год доступны переключателем режимов на карточке."
        ),
        "parser_type": "rosstat_gdp",
        "model_config_json": {
            "gdp_source": "official_quarterly",
            "gdp_sheet": "2",
            "gdp_history_sheet": "1",
            "gdp_overlap_year": 2011,
            "forecast_steps": 4,
            "forecast_strategy": "gdp_nominal_quarterly",
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
            "Валовой внутренний продукт России в постоянных ценах 2021 года "
            "по квартальным оценкам Росстата в системе национальных счетов. "
            "Ряд отражает объём выпуска без влияния текущих цен; история с 1995 года. "
            "Темпы год к году и квартал к кварталу, а также сумма за календарный год "
            "доступны переключателем режимов на карточке."
        ),
        "parser_type": "rosstat_gdp",
        "model_config_json": {
            "gdp_source": "official_quarterly",
            "gdp_sheet": "9",
            "gdp_history_sheet": "3",
            "gdp_overlap_year": 2011,
            "forecast_steps": 4,
            "forecast_strategy": "gdp_real_quarterly",
            "forecast_transform": "absolute",
            "validation": {"min": 0},
        },
        "is_active": True,
        "category": "ВВП",
    },
    # Annual sibling для wages-nominal: единый годовой ряд 1991+. Ранние годы
    # 1991-2014 — immutable Росстат-архив (`wages_historical.py`), 2015+ —
    # annual mean месячного ряда, продолжается движком автоматически (derived
    # spec `annual_mean_with_prefix`, calculation_engine). Не в каталоге;
    # доступен как режим «С 1991 года» на карточке wages-nominal.
    # См. trap «annual-in-monthly mixing» в CONTEXT.md.
    {
        "code": "wages-nominal-annual",
        "name": "Средняя зарплата (годовая)",
        "name_en": "Average Wages (Annual)",
        "unit": "руб.",
        "frequency": "annual",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/labour_costs",
        "description": (
            "Среднемесячная номинальная начисленная зарплата работников по полному "
            "кругу организаций, годовое значение. 1991-1997 в новых деноминированных "
            "рублях (исходные ×0,001 по факту деноминации 1998 г.), с 1998 — в рублях "
            "нынешней шкалы."
        ),
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 0,
            "primary_indicator_code": "wages-nominal",
        },
        "is_active": True,
        "is_listed": False,
        "category": "Рынок труда",
    },
    # ─── Производные (CalculationEngine) ───
    {
        "code": "wages-real",
        "name": "Реальная заработная плата",
        "name_en": "Real Wages Index",
        "unit": "индекс",
        "frequency": "monthly",
        "source": "Росстат",
        "description": (
            "Реальная заработная плата — покупательная способность средней начисленной "
            "зарплаты с поправкой на инфляцию. Представлена индексом с базой 100 в "
            "январе 2015 года: рост линии означает, что зарплата растёт быстрее цен."
        ),
        "methodology": (
            "Номинальная начисленная зарплата делится на индекс потребительских цен и "
            "приводится к базе 100 в январе 2015 года. Показывает, во сколько раз "
            "изменилась реальная покупательная способность зарплаты относительно начала "
            "ряда. Источник — Росстат."
        ),
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 0,
            "forecast_transform": "percentage",
        },
        "is_active": True,
        "category": "Рынок труда",
    },
    # C2 (звонок 2026-05-21): индекс зарплаты (среднее 2015 = 100). Тот же
    # экономический смысл, что и индексы цен на жильё — позволяет напрямую
    # сравнивать темпы роста зарплат и недвижимости. Считается из wages-nominal.
    {
        "code": "wages-index",
        "name": "Индекс заработной платы",
        "name_en": "Wages Index (2010=100)",
        "unit": "индекс",
        "frequency": "monthly",
        "source": "Росстат",
        "description": (
            "Индекс номинальной заработной платы относительно среднего значения 2010 года "
            "(базовый период = 100). Приведён к той же базе, что и индексы цен на жильё, "
            "поэтому удобен для прямого сопоставления темпов роста доходов и стоимости жилья."
        ),
        "methodology": (
            "Рассчитывается как отношение номинальной средней зарплаты текущего месяца к "
            "среднемесячной зарплате 2010 года, умноженное на 100. Базовый период — "
            "2010 год. Источник — Росстат."
        ),
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 0,
            "forecast_transform": "absolute",
        },
        "is_active": True,
        "category": "Рынок труда",
    },
    # C1 (звонок 2026-05-21, уточнено v7): индекс доступности жилья. Соотношение
    # индексов зарплаты и цен на жильё в общей базе 2010. Помесячный ряд:
    # индекс зарплаты месяца ÷ индекс цен последнего известного квартала × 100.
    # >100 → с 2010 зарплаты росли быстрее цен (доступность ↑), <100 → наоборот.
    {
        "code": "housing-affordability",
        "name": "Индекс доступности жилья",
        "name_en": "Housing Affordability Index",
        "unit": "индекс",
        "frequency": "monthly",
        "source": "Росстат",
        "description": (
            "Соотношение индекса заработной платы и индекса цен на вторичное жильё, "
            "приведённых к общей базе 2010 года. Значения выше 100 означают, что с "
            "базового периода зарплаты росли быстрее стоимости жилья (доступность "
            "повышается); ниже 100 — наоборот."
        ),
        "methodology": (
            "Расчёт: (индекс зарплаты ÷ индекс цен на вторичное жильё) × 100, помесячно. "
            "Оба индекса приведены к базе 2010 года, поэтому в окрестности базового года "
            "индекс близок к 100. Берётся вторичный рынок как более широкий и менее "
            "зависимый от государственных ипотечных программ."
        ),
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 0,
            "forecast_transform": "absolute",
        },
        "is_active": True,
        "category": "Цены",
    },
    # Первичный рынок — вторая карточка доступности (variant-picker «Рынок жилья»).
    # Скрыта из листинга (доступна с карточки вторичного через переключатель).
    {
        "code": "housing-affordability-primary",
        "name": "Индекс доступности жилья (первичное жильё)",
        "name_en": "Housing Affordability Index (Primary)",
        "unit": "индекс",
        "frequency": "monthly",
        "source": "Росстат",
        "description": (
            "Соотношение индекса заработной платы и индекса цен на первичное жильё, "
            "приведённых к общей базе 2010 года. Значения выше 100 означают, что с "
            "базового периода зарплаты росли быстрее стоимости новостроек (доступность "
            "повышается); ниже 100 — наоборот."
        ),
        "methodology": (
            "Расчёт: (индекс зарплаты ÷ индекс цен на первичное жильё) × 100, помесячно. "
            "Оба индекса приведены к базе 2010 года, поэтому в окрестности базового года "
            "индекс близок к 100. Первичный рынок отражает цены на новостройки, на "
            "которые сильнее влияют государственные ипотечные программы."
        ),
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 0,
            "forecast_transform": "absolute",
        },
        "is_active": True,
        "is_listed": False,
        "category": "Цены",
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
            "Годовое значение номинального ВВП — сумма четырёх квартальных "
            "значений в текущих ценах за календарный год. Прогноз получается "
            "суммированием квартальных прогнозов номинального ВВП на тот же год."
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
            "Годовое значение реального ВВП — сумма четырёх квартальных "
            "значений в постоянных ценах 2021 года за календарный год. "
            "Прогноз получается суммированием квартальных прогнозов реального ВВП "
            "на тот же год."
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
            "Годовая инфляция «декабрь к декабрю» — кумулятивное произведение "
            "двенадцати месячных индексов потребительских цен в пределах "
            "календарного года, переведённое в проценты. Прогноз получается "
            "аналогичным произведением по месячным точкам прогноза ИПЦ."
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
            "Годовая инфляция «декабрь к декабрю» по продовольственным товарам — "
            "кумулятивное произведение двенадцати месячных индексов потребительских "
            "цен на продовольствие в пределах календарного года, переведённое в "
            "проценты. Прогноз получается аналогичным произведением по месячным "
            "точкам прогноза."
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
            "Годовая инфляция «декабрь к декабрю» по непродовольственным товарам — "
            "кумулятивное произведение двенадцати месячных индексов потребительских "
            "цен на непродовольственные товары в пределах календарного года, "
            "переведённое в проценты. Прогноз получается аналогичным произведением "
            "по месячным точкам прогноза."
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
            "Годовая инфляция «декабрь к декабрю» по платным услугам — "
            "кумулятивное произведение двенадцати месячных индексов потребительских "
            "цен на услуги в пределах календарного года, переведённое в проценты. "
            "Прогноз получается аналогичным произведением по месячным точкам "
            "прогноза."
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
    {
        "code": "cpi-yoy",
        "name": "ИПЦ год к году",
        "name_en": "CPI YoY",
        "unit": "%",
        "frequency": "monthly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/price",
        "description": "Изменение потребительских цен к тому же месяцу прошлого года.",
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 12,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "cpi",
                "operation": "cpi_mom_yoy",
                "model_name": "CPI-YoY-Derived",
            },
        },
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "cpi-food-yoy",
        "name": "ИПЦ на продовольствие — год к году",
        "name_en": "Food CPI YoY",
        "unit": "%",
        "frequency": "monthly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/price",
        "description": "Изменение цен на продовольственные товары к тому же месяцу прошлого года.",
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 12,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "cpi-food",
                "operation": "cpi_mom_yoy",
                "model_name": "CPI-Food-YoY-Derived",
            },
        },
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "cpi-nonfood-yoy",
        "name": "ИПЦ на непродовольствие — год к году",
        "name_en": "Non-food CPI YoY",
        "unit": "%",
        "frequency": "monthly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/price",
        "description": "Изменение цен на непродовольственные товары к тому же месяцу прошлого года.",
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 12,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "cpi-nonfood",
                "operation": "cpi_mom_yoy",
                "model_name": "CPI-Nonfood-YoY-Derived",
            },
        },
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "cpi-services-yoy",
        "name": "ИПЦ на услуги — год к году",
        "name_en": "Services CPI YoY",
        "unit": "%",
        "frequency": "monthly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/price",
        "description": "Изменение цен на услуги к тому же месяцу прошлого года.",
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 12,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "cpi-services",
                "operation": "cpi_mom_yoy",
                "model_name": "CPI-Services-YoY-Derived",
            },
        },
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "cpi-qoq",
        "name": "ИПЦ квартал к кварталу",
        "name_en": "CPI QoQ",
        "unit": "%",
        "frequency": "quarterly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/price",
        "description": "Изменение уровня цен к концу предыдущего квартала.",
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 4,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "cpi",
                "operation": "cpi_mom_qoq",
                "model_name": "CPI-QoQ-Derived",
            },
        },
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "cpi-food-qoq",
        "name": "ИПЦ на продовольствие — квартал к кварталу",
        "name_en": "Food CPI QoQ",
        "unit": "%",
        "frequency": "quarterly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/price",
        "description": "Изменение цен на продовольствие к концу предыдущего квартала.",
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 4,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "cpi-food",
                "operation": "cpi_mom_qoq",
                "model_name": "CPI-Food-QoQ-Derived",
            },
        },
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "cpi-nonfood-qoq",
        "name": "ИПЦ на непродовольствие — квартал к кварталу",
        "name_en": "Non-food CPI QoQ",
        "unit": "%",
        "frequency": "quarterly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/price",
        "description": "Изменение цен на непродовольственные товары к концу предыдущего квартала.",
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 4,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "cpi-nonfood",
                "operation": "cpi_mom_qoq",
                "model_name": "CPI-Nonfood-QoQ-Derived",
            },
        },
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "cpi-services-qoq",
        "name": "ИПЦ на услуги — квартал к кварталу",
        "name_en": "Services CPI QoQ",
        "unit": "%",
        "frequency": "quarterly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/price",
        "description": "Изменение цен на услуги к концу предыдущего квартала.",
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 4,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "cpi-services",
                "operation": "cpi_mom_qoq",
                "model_name": "CPI-Services-QoQ-Derived",
            },
        },
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "cpi-period-weekly",
        "name": "Недельный рост ИПЦ с начала месяца",
        "name_en": "CPI Weekly MTD from Weekly",
        "unit": "%",
        "frequency": "weekly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/price",
        "description": (
            "Накопленный прирост цен с начала календарного месяца по состоянию "
            "на каждую отчётную неделю."
        ),
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 8,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "inflation-weekly",
                "operation": "weekly_mtd_in_calendar_month",
                "model_name": "CPI-Period-Weekly-Derived",
            },
        },
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "cpi-food-period-weekly",
        "name": "Недельный рост цен на продовольствие с начала месяца",
        "name_en": "Food CPI Weekly MTD",
        "unit": "%",
        "frequency": "weekly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/price",
        "description": (
            "Накопленный прирост цен на продовольствие с начала месяца "
            "по еженедельным оценкам."
        ),
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 8,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "inflation-weekly-food",
                "operation": "weekly_mtd_in_calendar_month",
                "model_name": "CPI-Food-Period-Weekly-Derived",
            },
        },
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "cpi-nonfood-period-weekly",
        "name": "Недельный рост цен на непродовольствие с начала месяца",
        "name_en": "Non-food CPI Weekly MTD",
        "unit": "%",
        "frequency": "weekly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/price",
        "description": (
            "Накопленный прирост цен на непродовольственные товары с начала месяца "
            "по еженедельным оценкам."
        ),
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 8,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "inflation-weekly-nonfood",
                "operation": "weekly_mtd_in_calendar_month",
                "model_name": "CPI-Nonfood-Period-Weekly-Derived",
            },
        },
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "cpi-services-period-weekly",
        "name": "Недельный рост цен на услуги с начала месяца",
        "name_en": "Services CPI Weekly MTD",
        "unit": "%",
        "frequency": "weekly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/price",
        "description": (
            "Накопленный прирост цен на услуги с начала месяца "
            "по еженедельным оценкам."
        ),
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 8,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "inflation-weekly-services",
                "operation": "weekly_mtd_in_calendar_month",
                "model_name": "CPI-Services-Period-Weekly-Derived",
            },
        },
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "cpi-period-monthly",
        "name": "Месячный рост ИПЦ по недельным оценкам",
        "name_en": "CPI Monthly from Weekly",
        "unit": "%",
        "frequency": "monthly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/price",
        "description": "Накопленный прирост цен за календарный месяц по еженедельным оценкам.",
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 3,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "inflation-weekly",
                "operation": "weekly_inflation_by_calendar_month",
                "model_name": "CPI-Period-Monthly-Derived",
            },
        },
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "cpi-food-period-monthly",
        "name": "Месячный рост цен на продовольствие по неделям",
        "name_en": "Food CPI Monthly from Weekly",
        "unit": "%",
        "frequency": "monthly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/price",
        "description": "Накопленный прирост цен на продовольствие за месяц по недельным оценкам.",
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 3,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "inflation-weekly-food",
                "operation": "weekly_inflation_by_calendar_month",
                "model_name": "CPI-Food-Period-Monthly-Derived",
            },
        },
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "cpi-nonfood-period-monthly",
        "name": "Месячный рост цен на непродовольствие по неделям",
        "name_en": "Non-food CPI Monthly from Weekly",
        "unit": "%",
        "frequency": "monthly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/price",
        "description": "Накопленный прирост цен на непродовольственные товары за месяц по недельным оценкам.",
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 3,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "inflation-weekly-nonfood",
                "operation": "weekly_inflation_by_calendar_month",
                "model_name": "CPI-Nonfood-Period-Monthly-Derived",
            },
        },
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "cpi-services-period-monthly",
        "name": "Месячный рост цен на услуги по неделям",
        "name_en": "Services CPI Monthly from Weekly",
        "unit": "%",
        "frequency": "monthly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/price",
        "description": "Накопленный прирост цен на услуги за календарный месяц по недельным оценкам.",
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 3,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "inflation-weekly-services",
                "operation": "weekly_inflation_by_calendar_month",
                "model_name": "CPI-Services-Period-Monthly-Derived",
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
        "methodology": (
            "Денежный агрегат М1 в млрд рублей: наличные (М0) и переводные "
            "депозиты до востребования на конец месяца по оценке Банка России. "
            "На карточке — помесячный ряд и средние по кварталу и году; "
            "прогноз не строится. Семья «Денежные агрегаты» позволяет "
            "переключаться на М0 и М2 с сохранением режима графика."
        ),
        "parser_type": "cbr_monetary_agg_xlsx",
        "model_config_json": {
            "monetary_agg": {
                "indicator": "M1",
                "date_offset_months": -1,
            },
            "backfill_from_year": 1995,
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
        "methodology": (
            "Совокупный остаток кредитов физическим лицам в трлн рублей на конец "
            "месяца — ипотека, потребительские и прочие рублёвые ссуды в одном "
            "портфеле банковского сектора. Источник: Банк России. На карточке "
            "доступны помесячные остатки и средние по кварталам или годам; "
            "в семье «Кредиты и вклады населения» — согласованный ряд вкладов "
            "физлиц в млрд рублей за те же даты. Это уровень задолженности, "
            "а не выдачи за месяц и не ставки по новым договорам."
        ),
        "parser_type": "cbr_dataservice_json",
        "model_config_json": {
            "dataservice": {
                "publicationId": 20,
                "datasetId": 42,
                "measureId": 22,
                "element_id": 35,
                "date_offset_months": -1,
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
        "methodology": (
            "Совокупный остаток кредитов нефинансовым организациям и "
            "индивидуальным предпринимателям в трлн рублей на конец месяца — "
            "оборотное и инвестиционное кредитование в одном рублёвом портфеле. "
            "Источник: Банк России. Помесячный ряд и средние по кварталам или "
            "годам на карточке. Показатель отражает остаток портфеля, "
            "а не объём новых выдач."
        ),
        "parser_type": "cbr_dataservice_json",
        "model_config_json": {
            "dataservice": {
                "publicationId": 22,
                "datasetId": 50,
                "measureId": 22,
                "element_id": 35,
                "date_offset_months": -1,
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
        "methodology": (
            "Совокупный остаток вкладов физических лиц в банках в млрд рублей "
            "на конец месяца — переводные, срочные и валютные депозиты "
            "домохозяйств в одном агрегате. Источник: Банк России. "
            "На карточке — помесячные остатки и средние по кварталам или "
            "годам; в семье «Кредиты и вклады населения» — ряд кредитов "
            "физлицам в трлн рублей за те же даты. Это уровень привлечённых "
            "средств, а не приток вкладов за месяц и не средняя ставка."
        ),
        "parser_type": "cbr_monetary_agg_xlsx",
        "model_config_json": {
            "monetary_agg": {
                "indicator": "deposits-individual",
                "date_offset_months": -1,
            },
            "backfill_from_year": 2000,
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
        "parser_type": "cbr_monetary_agg_xlsx",
        "model_config_json": {
            "monetary_agg": {
                "indicator": "deposits-business",
                "date_offset_months": -1,
            },
            "backfill_from_year": 2000,
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
            "Дефицит (или профицит) федерального бюджета — разница между доходами "
            "и расходами за календарный месяц в млрд рублей: отрицательное значение "
            "означает дефицит, положительное — профицит. Источник: Минфин России. "
            "На карточке — помесячный ряд и среднее за квартал или год; переключатель "
            "семьи ведёт к доходам и расходам того же бюджета."
        ),
        "parser_type": "minfin_budget_csv",
        "model_config_json": {
            "forecast_steps": 0,
            "forecast_transform": "absolute",
        },
        "is_active": True,
        "category": "Финансы",
    },
    # ─── Недельная инфляция (Росстат HTML, бюллетени с 2023-01-09) ───
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
            "Публикуется Росстатом по средам в бюллетенях "
            "«Об оценке индекса потребительских цен с … по …». Данные с 2023-01-09 "
            "(первый бюллетень из современного архива rosstat.gov.ru)."
        ),
        "parser_type": "rosstat_weekly_cpi",
        "model_config_json": {
            "forecast_steps": 8,
            "forecast_strategy": "generic_ols",
            # Ряд хранится как индекс ~100 (недельный прирост = value−100). OLS
            # на «absolute» сходится к среднему уровню (~100.15) → на графике
            # плоская линия 0.15%. cpi_index обучается на приростах.
            "forecast_transform": "cpi_index",
            "validation": {"min": 99, "max": 102},
            "backfill_max_pages": 1,
            # Cutoff: до 2023-01-09 у Росстата нет доступного архива bulletins
            # ни на rosstat.gov.ru (404 на старые номера), ни через search API,
            # ни в Wayback memento (CDX empty). До этой даты у нас был
            # XLSX-approximation по food basket → расхождения с monthly CPI
            # до 3 pp (март 2022). docs/missed_data_audit.md::Nedel_ipc.
            "weekly_cutoff_date": "2023-01-09",
        },
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "inflation-weekly-food",
        "name": "Недельная инфляция — продовольствие",
        "name_en": "Weekly CPI Food",
        "unit": "%",
        "frequency": "weekly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/price",
        "description": (
            "Недельное изменение цен на продовольственные товары: взвешенное среднее "
            "по еженедельной товарной корзине Росстата (структура расходов — по "
            "справочнику потребительских цен). Официальный недельный бюллетень "
            "публикуется только по полной корзине."
        ),
        "parser_type": "rosstat_weekly_cpi",
        "model_config_json": {
            "weekly_segment": "food",
            "forecast_steps": 8,
            "forecast_strategy": "generic_ols",
            "forecast_transform": "cpi_index",
        },
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "inflation-weekly-nonfood",
        "name": "Недельная инфляция — непродовольственные товары",
        "name_en": "Weekly CPI Non-food",
        "unit": "%",
        "frequency": "weekly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/price",
        "description": (
            "Недельное изменение цен на непродовольственные товары: взвешенное среднее "
            "по еженедельной корзине Росстата."
        ),
        "parser_type": "rosstat_weekly_cpi",
        "model_config_json": {
            "weekly_segment": "nonfood",
            "forecast_steps": 8,
            "forecast_strategy": "generic_ols",
            "forecast_transform": "cpi_index",
        },
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "inflation-weekly-services",
        "name": "Недельная инфляция — услуги",
        "name_en": "Weekly CPI Services",
        "unit": "%",
        "frequency": "weekly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/price",
        "description": (
            "Недельное изменение цен на услуги: взвешенное среднее по еженедельной "
            "корзине Росстата."
        ),
        "parser_type": "rosstat_weekly_cpi",
        "model_config_json": {
            "weekly_segment": "services",
            "forecast_steps": 8,
            "forecast_strategy": "generic_ols",
            "forecast_transform": "cpi_index",
        },
        "is_active": True,
        "category": "Цены",
    },
    # ─── Цены на жильё (Росстат русский, socioeconomic PDF report, ADR-0004) ───
    {
        "code": "housing-price-primary",
        "name": "Цены на первичное жильё",
        "name_en": "Primary Housing Price Index",
        "unit": "индекс",
        "frequency": "quarterly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/folder/210",
        "description": (
            "Квартальные цены на квартиры в новостройках: индекс с базой 2010 = 100, "
            "прирост к/к и г/г. Один из главных индикаторов рынка первичного жилья."
        ),
        "methodology": (
            "Росстат публикует квартальный индекс цен на первичном рынке в "
            "макроэкономическом обзоре. На странице доступны уровень индекса, "
            "изменение к предыдущему кварталу и к тому же кварталу год назад. "
            "История с 1998 года; прогноз на четыре квартала вперёд."
        ),
        "parser_type": "rosstat_housing",
        "model_config_json": {
            "forecast_steps": 4,
            "forecast_strategy": "housing_quarterly",
            "forecast_transform": "absolute",
            "validation": {"min": 50, "max": 500},
            "hero_view": "yoy_pct",
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
        "source_url": "https://rosstat.gov.ru/folder/210",
        "description": (
            "Квартальные цены на вторичном рынке: индекс 2010 = 100, к/к и г/г. "
            "Отражает сделки с квартирами в обращающемся жилищном фонде."
        ),
        "methodology": (
            "Отдельный квартальный индекс Росстата по сделкам на вторичном рынке. "
            "На графике — уровень индекса, квартальный прирост и год к году; "
            "переключатель «Рынок жилья» ведёт на первичные новостройки. "
            "История с 1998 года; прогноз на четыре квартала."
        ),
        "parser_type": "rosstat_housing",
        "model_config_json": {
            "forecast_steps": 4,
            "forecast_strategy": "housing_quarterly",
            "forecast_transform": "absolute",
            "validation": {"min": 50, "max": 500},
            "hero_view": "yoy_pct",
        },
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "housing-qoq-secondary",
        "name": "Цены на вторичное жильё (изм. к/к)",
        "name_en": "Secondary Housing Prices QoQ",
        "unit": "%",
        "frequency": "quarterly",
        "source": "Росстат",
        "description": (
            "Изменение индекса цен на вторичном рынке жилья к предыдущему кварталу, "
            "в процентах."
        ),
        "methodology": (
            "Рассчитывается как отношение индекса цен на вторичное жильё в текущем "
            "квартале к значению за непосредственно предшествующий квартал, "
            "выраженное в процентах."
        ),
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 4,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "housing-price-secondary",
                "operation": "qoq",
                "model_name": "Housing-Secondary-QoQ-Derived",
            },
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
        "source_url": "https://rosstat.gov.ru/enterprise_industrial",
        "description": (
            "Индекс промышленного производства (2023=100): горнодобыча, "
            "обработка, энергетика, водоснабжение. Ежемесячные данные Росстата."
        ),
        "methodology": (
            "Индекс промышленного производства — агрегированный показатель "
            "динамики выпуска по разделам B (добыча полезных ископаемых), "
            "C (обрабатывающие производства), D (обеспечение электроэнергией, "
            "газом, паром), E (водоснабжение, водоотведение). Веса разделов "
            "фиксируются на пятилетний период. Публикуется Росстатом ежемесячно "
            "с месячным лагом; индекс приведён к базе среднемесячного значения "
            "2023 года = 100."
        ),
        "parser_type": "rosstat_ipi",
        "model_config_json": {
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "validation": {"min": 30, "max": 200},
            "hero_view": "yoy_pct",
        },
        "is_active": True,
        "category": "Бизнес",
    },
    {
        "code": "ipi-mining",
        "name": "Индекс производства: добыча полезных ископаемых",
        "name_en": "Industrial Production: Mining",
        "unit": "индекс",
        "frequency": "monthly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/enterprise_industrial",
        "description": (
            "Индекс производства по разделу «добыча полезных ископаемых» "
            "(2023=100): добыча угля, нефти, газа, руд и прочих ископаемых. "
            "Ежемесячные данные Росстата."
        ),
        "methodology": (
            "Индекс выпуска по разделу B ОКВЭД2 (добыча полезных ископаемых) — "
            "одна из четырёх составляющих промышленного производства. Веса "
            "видов деятельности фиксируются на пятилетний период; ряд приведён "
            "к среднемесячному значению 2023 года = 100. Публикуется Росстатом "
            "ежемесячно с месячным лагом."
        ),
        "parser_type": "rosstat_ipi",
        "model_config_json": {
            "okved_section": "B",
            "forecast_transform": "absolute",
            "validation": {"min": 30, "max": 200},
            "hero_view": "yoy_pct",
        },
        "is_active": True,
        "category": "Бизнес",
    },
    {
        "code": "ipi-manufacturing",
        "name": "Индекс производства: обрабатывающие производства",
        "name_en": "Industrial Production: Manufacturing",
        "unit": "индекс",
        "frequency": "monthly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/enterprise_industrial",
        "description": (
            "Индекс производства по разделу «обрабатывающие производства» "
            "(2023=100): пищевая, химическая, металлургическая, "
            "машиностроительная и прочие отрасли. Ежемесячные данные Росстата."
        ),
        "methodology": (
            "Индекс выпуска по разделу C ОКВЭД2 (обрабатывающие производства) — "
            "крупнейшая из четырёх составляющих промышленного производства. "
            "Веса отраслей фиксируются на пятилетний период; ряд приведён к "
            "среднемесячному значению 2023 года = 100. Публикуется Росстатом "
            "ежемесячно с месячным лагом."
        ),
        "parser_type": "rosstat_ipi",
        "model_config_json": {
            "okved_section": "C",
            "forecast_transform": "absolute",
            "validation": {"min": 30, "max": 200},
            "hero_view": "yoy_pct",
        },
        "is_active": True,
        "category": "Бизнес",
    },
    {
        "code": "ipi-energy",
        "name": "Индекс производства: электроэнергия, газ и пар",
        "name_en": "Industrial Production: Electricity & Gas",
        "unit": "индекс",
        "frequency": "monthly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/enterprise_industrial",
        "description": (
            "Индекс производства по разделу «обеспечение электрической "
            "энергией, газом и паром; кондиционирование воздуха» (2023=100). "
            "Ежемесячные данные Росстата."
        ),
        "methodology": (
            "Индекс выпуска по разделу D ОКВЭД2 (обеспечение электроэнергией, "
            "газом и паром) — одна из четырёх составляющих промышленного "
            "производства. Веса фиксируются на пятилетний период; ряд приведён "
            "к среднемесячному значению 2023 года = 100. Публикуется Росстатом "
            "ежемесячно с месячным лагом. Ряд имеет выраженную сезонность."
        ),
        "parser_type": "rosstat_ipi",
        "model_config_json": {
            "okved_section": "D",
            "forecast_transform": "absolute",
            "validation": {"min": 30, "max": 200},
            "hero_view": "yoy_pct",
        },
        "is_active": True,
        "category": "Бизнес",
    },
    {
        "code": "ipi-water",
        "name": "Индекс производства: водоснабжение и водоотведение",
        "name_en": "Industrial Production: Water Supply",
        "unit": "индекс",
        "frequency": "monthly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/enterprise_industrial",
        "description": (
            "Индекс производства по разделу «водоснабжение; водоотведение, "
            "организация сбора и утилизации отходов» (2023=100). Ежемесячные "
            "данные Росстата."
        ),
        "methodology": (
            "Индекс выпуска по разделу E ОКВЭД2 (водоснабжение, водоотведение, "
            "сбор и утилизация отходов) — наименьшая из четырёх составляющих "
            "промышленного производства. Веса фиксируются на пятилетний период; "
            "ряд приведён к среднемесячному значению 2023 года = 100. "
            "Публикуется Росстатом ежемесячно с месячным лагом."
        ),
        "parser_type": "rosstat_ipi",
        "model_config_json": {
            "okved_section": "E",
            "forecast_transform": "absolute",
            "validation": {"min": 30, "max": 200},
            "hero_view": "yoy_pct",
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
            "Численность постоянного населения России на 1 января. Источник: "
            "Росстат, итоги текущего демографического учёта. Данные за 1897 "
            "и 1914 годы приведены в границах современной территории Российской "
            "Федерации для обеспечения сопоставимости долгого исторического ряда."
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
            "backfill_from_year": 1998,
            # Квартальное сальдо — знаковый ряд (меняет знак). Прогноз на 4
            # квартала по level-diff методологии (см. signed_quarterly).
            "forecast_steps": 4,
            "forecast_strategy": "signed_quarterly",
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
    # ─── Производные: текущий счёт YoY ABS (звонок 2026-05-22) ───
    # Заменяет старый current-account-yoy %, который оставлен депрекейтнутым
    # ниже (is_active=false): для balances со знаком процент бессмыслен,
    # считаем разницу в млн $.
    {
        "code": "current-account-yoy-abs",
        "name": "Текущий счёт (изм. г/г, абс.)",
        "name_en": "Current Account YoY Change (abs.)",
        "unit": "млн $",
        "frequency": "quarterly",
        "source": "Банк России",
        "description": "Изменение сальдо текущего счёта к аналогичному кварталу предыдущего года в миллионах долларов США.",
        "parser_type": "derived",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "Торговля",
    },
    {
        "code": "trade-balance-yoy-abs",
        "name": "Торговый баланс (изм. г/г, абс.)",
        "name_en": "Trade Balance YoY Change (abs.)",
        "unit": "млн $",
        "frequency": "quarterly",
        "source": "Банк России",
        "description": "Изменение торгового баланса к аналогичному кварталу предыдущего года в миллионах долларов США.",
        "parser_type": "derived",
        "model_config_json": {"forecast_steps": 0},
        "is_active": True,
        "category": "Торговля",
    },
    # ─── Депрекейтнут (звонок 2026-05-22): процент YoY для current-account
    # бессмыслен (база меняет знак). Оставлен в БД для исторических ссылок,
    # но is_active=false и из DERIVED_SPECS убран. Используйте
    # current-account-yoy-abs.
    {
        "code": "current-account-yoy",
        "name": "Текущий счёт (изм. г/г, % — депрекейт)",
        "name_en": "Current Account YoY Change (deprecated)",
        "unit": "%",
        "frequency": "quarterly",
        "source": "Банк России",
        "description": "Депрекейтнут: процент изменения от balance со знаком даёт мусор. См. current-account-yoy-abs.",
        "parser_type": "derived",
        "model_config_json": {"forecast_steps": 0},
        "is_active": False,
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
        "model_config_json": {
            "forecast_steps": 12,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "ipi",
                "operation": "pipeline",
                "pipeline": [["yoy", {}]],
                "model_name": "ipi-yoy-derived",
            },
        },
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
        "source_url": "https://rosstat.gov.ru/folder/210",
        "description": (
            "Индекс цен производителей промышленных товаров (2010=100). "
            "Ежемесячные данные Росстата."
        ),
        "methodology": (
            "Индекс цен производителей промышленных товаров отражает изменение "
            "оптовых цен на продукцию, реализуемую промышленными предприятиями "
            "на внутренний рынок. Рассчитывается Росстатом по выборке предприятий "
            "и видов продукции и публикуется ежемесячно в составе официальных "
            "макроэкономических обзоров. Индекс приведён к базе 2010 = 100; "
            "история накапливается с 2010 года."
        ),
        "parser_type": "rosstat_ppi",
        "model_config_json": {
            "forecast_steps": 12,
            "forecast_strategy": "ppi_monthly",
            "forecast_transform": "absolute",
            "validation": {"min": 50, "max": 500},
            "hero_view": "yoy_pct",
        },
        "is_active": True,
        "category": "Цены",
    },
    # ─── Внешняя торговля (ЦБ BOP XLSX) ───
    # Quarterly source = bal_of_payments_standart.xlsx лист «Кварталы», глубина с 1994-Q1.
    # alternate_frequencies → linkage на monthly counterpart (T3 plan, frequency switcher).
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
            "forecast_steps": 4,
            "forecast_strategy": "generic_quarterly",
            "forecast_transform": "absolute",
            "validation": {"min": 0},
            "alternate_frequencies": {"monthly": "exports-monthly"},
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
            "forecast_steps": 4,
            "forecast_strategy": "generic_quarterly",
            "forecast_transform": "absolute",
            "validation": {"min": 0},
            "alternate_frequencies": {"monthly": "imports-monthly"},
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
            # Знаковый ряд: прогноз — тождество exports − imports (оба имеют
            # квартальный прогноз), а не прямая модель на сальдо. Согласовано
            # с прогнозами компонент; пересчитывается каскадом при retrain
            # exports/imports. См. derived_from_source operation="subtract".
            "forecast_steps": 4,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "exports",
                "source_code_2": "imports",
                "operation": "subtract",
                "model_name": "Trade-Balance-Identity",
            },
            "forecast_transform": "absolute",
            "alternate_frequencies": {"monthly": "trade-balance-monthly"},
        },
        "is_active": True,
        "category": "Торговля",
    },
    # ─── Внешняя торговля (ЦБ monthly, ETG/ETS, T3 plan) ───
    # Источник: ЦБ trade/trade.xls лист «Ежемесячные» (товары, 1997-01+)
    #          trade/trade_monthly.xlsx лист «месяцы» (услуги, 2018-01+).
    # is_listed=False — карточки доступны через frequency switcher из родителя
    # (exports/imports/...), не дублируем в листинге категории «Торговля».
    {
        "code": "exports-monthly",
        "name": "Экспорт товаров (месячный ряд)",
        "name_en": "Goods Exports (monthly)",
        "unit": "млн $",
        "frequency": "monthly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/macro_itm/external_sector/etg/",
        "description": (
            "Экспорт товаров (ФОБ) по методологии платёжного баланса, "
            "месячный ряд с 1997 года. Источник: Банк России."
        ),
        "parser_type": "cbr_trade_goods_monthly",
        "model_config_json": {
            "bop_target": "exports-monthly",
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "validation": {"min": 0},
            "primary_indicator_code": "exports",
        },
        "is_active": True,
        "is_listed": False,
        "category": "Торговля",
    },
    {
        "code": "imports-monthly",
        "name": "Импорт товаров (месячный ряд)",
        "name_en": "Goods Imports (monthly)",
        "unit": "млн $",
        "frequency": "monthly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/macro_itm/external_sector/etg/",
        "description": (
            "Импорт товаров (ФОБ) по методологии платёжного баланса, "
            "месячный ряд с 1997 года. Источник: Банк России."
        ),
        "parser_type": "cbr_trade_goods_monthly",
        "model_config_json": {
            "bop_target": "imports-monthly",
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "validation": {"min": 0},
            "primary_indicator_code": "imports",
        },
        "is_active": True,
        "is_listed": False,
        "category": "Торговля",
    },
    {
        "code": "trade-balance-monthly",
        "name": "Торговый баланс (месячный ряд)",
        "name_en": "Trade Balance (monthly)",
        "unit": "млн $",
        "frequency": "monthly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/macro_itm/external_sector/etg/",
        "description": (
            "Сальдо торгового баланса товарами (экспорт минус импорт ФОБ) "
            "по методологии платёжного баланса, месячный ряд с 1997 года. "
            "Источник: Банк России."
        ),
        "parser_type": "cbr_trade_goods_monthly",
        "model_config_json": {
            "bop_target": "trade-balance-monthly",
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "primary_indicator_code": "trade-balance",
        },
        "is_active": True,
        "is_listed": False,
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
            "Международные резервы Российской Федерации в млрд долларов США "
            "на дату публикации Банка России: валютные активы, СДР, позиция "
            "в МВФ и монетарное золото в одном агрегате. На карточке — "
            "еженедельный ряд и средние по месяцу, кварталу и году из того же "
            "источника; прогноз не строится. Рост или снижение отражает "
            "накопление, использование резервов и переоценку активов."
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
            "Совокупный внешний долг Российской Федерации в млн долларов США. "
            "Квартальные остатки с 2003 года. Банк России."
        ),
        "methodology": (
            "Совокупные внешние обязательства резидентов Российской Федерации "
            "перед нерезидентами в млн долларов США на конец квартала — "
            "агрегат «всего» по оценке Банка России. Источник: Банк России. "
            "На карточке — поквартальный ряд и среднее по кварталам внутри "
            "года, с прогнозом на ближайшие кварталы. Это остаток долга на "
            "дату, а не новые заимствования за квартал."
        ),
        "parser_type": "cbr_debt_xlsx",
        "model_config_json": {
            "forecast_steps": 4,
            "forecast_strategy": "generic_quarterly",
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
        "code": "ppi-qoq",
        "name": "ИЦП (изм. кв/кв)",
        "name_en": "Producer Price Index QoQ",
        "unit": "%",
        "frequency": "quarterly",
        "source": "Росстат",
        "description": "Изменение индекса цен производителей к предыдущему кварталу, в процентах.",
        "methodology": (
            "Индекс цен производителей приводится к значению на конец квартала, "
            "затем считается процентное изменение к предыдущему кварталу."
        ),
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 4,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "ppi",
                "operation": "pipeline",
                "pipeline": [
                    ["period_over_period", {"granularity": "quarter", "method": "last"}],
                ],
                "complete_bucket": "quarter",
                "min_periods": 3,
                "model_name": "PPI-QoQ-Derived",
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
            "Годовой рост цен производителей «декабрь к декабрю» — кумулятивное "
            "произведение двенадцати месячных индексов цен производителей "
            "промышленных товаров в пределах календарного года, переведённое в "
            "проценты. Прогноз получается аналогичным произведением по месячным "
            "точкам прогноза."
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
            "предыдущего года, в процентах."
        ),
        "methodology": (
            "Рассчитывается как отношение индекса цен на первичное жильё в текущем "
            "квартале к значению за тот же квартал прошлого года, выраженное в процентах. "
            "Исходный квартальный индекс публикуется Росстатом в составе официальных "
            "макроэкономических обзоров."
        ),
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 4,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "housing-price-primary",
                "operation": "yoy_quarterly",
                "model_name": "Housing-Primary-YoY-Derived",
            },
        },
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "housing-qoq-primary",
        "name": "Цены на первичное жильё (изм. к/к)",
        "name_en": "Primary Housing Prices QoQ",
        "unit": "%",
        "frequency": "quarterly",
        "source": "Росстат",
        "description": (
            "Изменение индекса цен на первичном рынке жилья к предыдущему кварталу, "
            "в процентах."
        ),
        "methodology": (
            "Рассчитывается как отношение индекса цен на первичное жильё в текущем "
            "квартале к значению за непосредственно предшествующий квартал, "
            "выраженное в процентах."
        ),
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 4,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "housing-price-primary",
                "operation": "qoq",
                "model_name": "Housing-Primary-QoQ-Derived",
            },
        },
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
            "предыдущего года, в процентах."
        ),
        "methodology": (
            "Рассчитывается как отношение индекса цен на вторичное жильё в текущем "
            "квартале к значению за тот же квартал прошлого года, выраженное в процентах. "
            "Исходный квартальный индекс публикуется Росстатом в составе официальных "
            "макроэкономических обзоров."
        ),
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 4,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "housing-price-secondary",
                "operation": "yoy_quarterly",
                "model_name": "Housing-Secondary-YoY-Derived",
            },
        },
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "housing-annual-primary",
        "name": "Цены на первичное жильё (г/г, по годам)",
        "name_en": "Primary Housing Prices Annual",
        "unit": "%",
        "frequency": "annual",
        "source": "Росстат",
        "description": (
            "Годовое изменение цен на первичное жильё «год к году»: уровень цен "
            "на конец года к уровню на конец предыдущего года, в процентах. "
            "Одна точка на каждый завершённый год."
        ),
        "methodology": (
            "Рассчитывается как отношение индекса цен на первичное жильё на конец "
            "года к значению на конец предыдущего года, выраженное в процентах. "
            "В отличие от режима «к соответствующему периоду предыдущего года» "
            "(где сравнивается каждый квартал с тем же кварталом год назад), здесь "
            "одна точка на год. Прогноз продолжает ряд по прогнозу квартального "
            "индекса."
        ),
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 2,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "housing-price-primary",
                "operation": "december_to_december",
                "model_name": "Housing-Primary-Annual-Derived",
            },
        },
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "housing-annual-secondary",
        "name": "Цены на вторичное жильё (г/г, по годам)",
        "name_en": "Secondary Housing Prices Annual",
        "unit": "%",
        "frequency": "annual",
        "source": "Росстат",
        "description": (
            "Годовое изменение цен на вторичное жильё «год к году»: уровень цен "
            "на конец года к уровню на конец предыдущего года, в процентах. "
            "Одна точка на каждый завершённый год."
        ),
        "methodology": (
            "Рассчитывается как отношение индекса цен на вторичное жильё на конец "
            "года к значению на конец предыдущего года, выраженное в процентах. "
            "В отличие от режима «к соответствующему периоду предыдущего года» "
            "(где сравнивается каждый квартал с тем же кварталом год назад), здесь "
            "одна точка на год. Прогноз продолжает ряд по прогнозу квартального "
            "индекса."
        ),
        "parser_type": "derived",
        "model_config_json": {
            "forecast_steps": 2,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "housing-price-secondary",
                "operation": "december_to_december",
                "model_name": "Housing-Secondary-Annual-Derived",
            },
        },
        "is_active": True,
        "category": "Цены",
    },
    # ─── Компоненты ВВП (Росстат русский, GDP-quarters-of-use, ADR-0004) ───
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
            "Расходы домашних хозяйств на конечное потребление — компонент "
            "валового внутреннего продукта по методу использования в текущих "
            "ценах, млрд рублей. Включает покупки товаров и услуг населением, "
            "в том числе условно исчисленные жилищные услуги собственников жилья. "
            "Рассчитывается Росстатом по системе национальных счетов и "
            "публикуется ежеквартально; история на Forecast Economy — с 1995 года. "
            "На карточке доступны поквартальный ряд и среднее по годам; прогноз "
            "относится к поквартальному режиму."
        ),
        "parser_type": "rosstat_gdp",
        "model_config_json": {
            "gdp_source": "official_use",
            "gdp_sheet": "2",
            "gdp_history_sheet": "1",
            "gdp_overlap_year": 2011,
            "gdp_row_index": 7,
            "forecast_steps": 4,
            "forecast_strategy": "gdp_consumption_quarterly",
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
            "Расходы сектора государственного управления на конечное потребление — "
            "компонент валового внутреннего продукта по методу использования "
            "в текущих ценах, млрд рублей. Включают оплату труда бюджетников, "
            "государственные закупки товаров и услуг и потребление основного "
            "капитала учреждений госсектора. Рассчитывается Росстатом по системе "
            "национальных счетов и публикуется ежеквартально; история с 1995 года. "
            "На карточке — поквартальный ряд, среднее по годам и прогноз на "
            "поквартальном режиме. Не совпадает с исполнением федерального бюджета "
            "помесячно."
        ),
        "parser_type": "rosstat_gdp",
        "model_config_json": {
            "gdp_source": "official_use",
            "gdp_sheet": "2",
            "gdp_history_sheet": "1",
            "gdp_overlap_year": 2011,
            "gdp_row_index": 8,
            "forecast_steps": 4,
            "forecast_strategy": "gdp_government_quarterly",
            "validation": {"min": 0},
        },
        "is_active": True,
        "category": "ВВП",
    },
    {
        "code": "gdp-investment",
        "name": "Валовое накопление капитала",
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
            "Валовое накопление основного капитала — компонент ВВП по методу "
            "использования (инвестиции в основные фонды: здания, сооружения, "
            "машины, оборудование, программное обеспечение, объекты "
            "интеллектуальной собственности). Рассчитывается Росстатом по "
            "методологии системы национальных счетов СНС-2008 и публикуется "
            "ежеквартально. Исторический ряд с 1995 года приведён к единому "
            "классификатору ОКВЭД2."
        ),
        "parser_type": "rosstat_gdp",
        "model_config_json": {
            "gdp_source": "official_use",
            "gdp_sheet": "2",
            "gdp_history_sheet": "1",
            "gdp_overlap_year": 2011,
            "gdp_row_index": 11,
            "forecast_steps": 4,
            "forecast_strategy": "generic_quarterly",
            "forecast_transform": "absolute",
            "validation": {"min": 0},
        },
        "is_active": True,
        "category": "ВВП",
    },
    # ─── Рынок труда: рабочая сила и занятость ───
    {
        "code": "labor-force",
        "name": "Рабочая сила",
        "name_en": "Labor Force",
        "unit": "млн чел.",
        "frequency": "monthly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/folder/210",
        "description": (
            "Численность экономически активного населения (рабочая сила). "
            "Данные обследования рабочей силы Росстата (бюллетень "
            "«Социально-экономическое положение России»)."
        ),
        "methodology": (
            "Рабочая сила — экономически активное население в млн человек на конец "
            "месяца: занятые и безработные по методологии Международной организации "
            "труда. Источник: обследование рабочей силы Росстата. На карточке — "
            "помесячный ряд и средние по кварталам и годам; переключение с «Занятое "
            "население» в группе «Рынок труда: занятость» сохраняет выбранный режим "
            "графика. Прогноз не строится."
        ),
        "parser_type": "rosstat_labor",
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
        "source_url": "https://rosstat.gov.ru/folder/210",
        "description": (
            "Численность занятого населения по данным обследования рабочей силы "
            "Росстата (бюллетень «Социально-экономическое положение России»)."
        ),
        "methodology": (
            "Занятое население — лица с оплачиваемой работой и временно "
            "отсутствующие на рабочем месте, в млн человек на конец месяца по "
            "обследованию рабочей силы Росстата. На карточке — помесячный ряд "
            "и средние по кварталам и годам; вкладка «Рабочая сила» в той же "
            "группе показывает более широкий агрегат на тех же датах. Прогноз "
            "не строится."
        ),
        "parser_type": "rosstat_labor",
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
        "model_config_json": {
            "forecast_steps": 12,
            "forecast_strategy": "derived_from_source",
            "derived_forecast": {
                "source_code": "wages-nominal",
                "operation": "pipeline",
                "pipeline": [["yoy", {}]],
                "model_name": "wages-yoy-derived",
            },
        },
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
        "methodology": (
            "Доходы федерального бюджета — налоговые и неналоговые поступления "
            "за календарный месяц в млрд рублей. Источник: Минфин России. "
            "Помесячные значения восстанавливаются из официальной статистики "
            "исполнения бюджета; на карточке доступны режимы «помесячно» и "
            "среднее за квартал или год. Ряд согласован с карточками расходов "
            "и дефицита/профицита в группе «Федеральный бюджет»."
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
        "methodology": (
            "Расходы федерального бюджета — исполненные обязательства за "
            "календарный месяц в млрд рублей. Источник: Минфин России. "
            "Помесячный ряд публикуется в открытой статистике исполнения; "
            "на карточке можно выбрать помесячный вид или среднее за квартал "
            "или год. Согласован с доходами и сальдо в группе «Федеральный бюджет»."
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
            "forecast_steps": 4,
            "forecast_strategy": "generic_quarterly",
            "forecast_transform": "absolute",
            "validation": {"min": 0},
            "alternate_frequencies": {"monthly": "services-exports-monthly"},
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
            "forecast_steps": 4,
            "forecast_strategy": "generic_quarterly",
            "forecast_transform": "absolute",
            "validation": {"min": 0},
            "alternate_frequencies": {"monthly": "services-imports-monthly"},
        },
        "is_active": True,
        "category": "Торговля",
    },
    # ─── Услуги monthly (ЦБ trade_monthly.xlsx, T3 plan) ───
    {
        "code": "services-exports-monthly",
        "name": "Экспорт услуг (месячный ряд)",
        "name_en": "Services Exports (monthly)",
        "unit": "млн $",
        "frequency": "monthly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/macro_itm/external_sector/ets/",
        "description": (
            "Экспорт услуг по методологии платёжного баланса, месячный ряд "
            "с 2018 года. Источник: Банк России."
        ),
        "parser_type": "cbr_trade_services_monthly",
        "model_config_json": {
            "bop_target": "services-exports-monthly",
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "primary_indicator_code": "services-exports",
        },
        "is_active": True,
        "is_listed": False,
        "category": "Торговля",
    },
    {
        "code": "services-imports-monthly",
        "name": "Импорт услуг (месячный ряд)",
        "name_en": "Services Imports (monthly)",
        "unit": "млн $",
        "frequency": "monthly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/macro_itm/external_sector/ets/",
        "description": (
            "Импорт услуг по методологии платёжного баланса, месячный ряд "
            "с 2018 года. Источник: Банк России."
        ),
        "parser_type": "cbr_trade_services_monthly",
        "model_config_json": {
            "bop_target": "services-imports-monthly",
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "primary_indicator_code": "services-imports",
        },
        "is_active": True,
        "is_listed": False,
        "category": "Торговля",
    },
    {
        "code": "fdi-net",
        "name": "Прямые иностранные инвестиции (нетто)",
        "name_en": "Foreign Direct Investment Net",
        "unit": "млн $",
        "frequency": "quarterly",
        "source": "Банк России",
        "source_url": "https://www.cbr.ru/statistics/macro_itm/external_sector/di/",
        "description": (
            "Чистый приток прямых иностранных инвестиций по финансовому счёту "
            "платёжного баланса (квартальные потоки в млн долл. США). Включает "
            "приобретение нерезидентами долей в уставном капитале и долговых "
            "обязательств российских компаний за вычетом изъятий. Не путать "
            "с накопленными остатками прямых инвестиций (stocks/IIP) — это разный "
            "индикатор. Источник — сводный платёжный баланс ЦБ, обновляется раз "
            "в квартал с лагом ~2 месяца после конца квартала."
        ),
        "parser_type": "cbr_bop_xlsx",
        "model_config_json": {
            "bop_target": "fdi-net",
            # Знаковый ряд (нетто-приток может менять знак) → level-diff прогноз
            # на 4 квартала (см. signed_quarterly), как у сальдо счёта текущих
            # операций. Без validation.min — отрицательные значения легальны.
            "forecast_steps": 4,
            "forecast_strategy": "signed_quarterly",
            "forecast_transform": "absolute",
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
        "methodology": (
            "Объём выполненных строительных работ в текущих ценах. Включает "
            "новое строительство, реконструкцию, расширение и техническое "
            "перевооружение объектов всех форм собственности. Месячные данные "
            "публикуются Росстатом в составе сборника «Краткосрочные экономические "
            "показатели»."
        ),
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
        "frequency": "quarterly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/compendium/document/50802",
        "description": (
            "Инвестиции в основной капитал — затраты на создание и воспроизводство "
            "основных средств: строительство, приобретение оборудования, транспорта, "
            "IT-инфраструктуры. Публикуются Росстатом поквартально."
        ),
        "methodology": (
            "Объём инвестиций в основной капитал в текущих ценах. Включает "
            "затраты на приобретение, создание и модернизацию основных фондов "
            "(здания, сооружения, машины, оборудование) предприятиями и "
            "организациями всех форм собственности. Данные публикуются Росстатом "
            "поквартально, с лагом около двух месяцев после окончания квартала; "
            "помесячная разбивка по этому показателю не публикуется."
        ),
        "parser_type": "rosstat_ind_monthly",
        "model_config_json": {
            "forecast_steps": 4,
            "forecast_strategy": "generic_quarterly",
            "forecast_transform": "absolute",
            "validation": {"min": 0},
            "ind_sheet": "1.6 ",
            "quarterly_flow": True,
        },
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
        "description": (
            "Уровень инновационной активности организаций (%). С 2018 года "
            "показатель рассчитывается по обновлённой методике Росстата "
            "(4-я редакция Руководства Осло) и несопоставим с более ранними "
            "данными, поэтому ряд приведён с 2018 года. Данные Росстата."
        ),
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
            "в отчётном году (%). С 2018 года показатель рассчитывается по "
            "обновлённой методике Росстата (4-я редакция Руководства Осло) и "
            "несопоставим с более ранним рядом, поэтому история приведена "
            "с 2018 года. Данные Росстата."
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
        "methodology": (
            "Учётная цена золота Банка России в рублях за грамм на дату "
            "публикации — официальный ориентир регулятора, не биржевая "
            "котировка в долларах. Источник: Банк России. На карточке — "
            "ежедневный ряд и средние по неделе, месяцу, кварталу и году "
            "из того же ряда; прогноз не строится. Рост цены в рублях "
            "отражает и мировую динамику металла, и курс рубля."
        ),
        "parser_type": "cbr_gold_html",
        "model_config_json": {
            "metal": "gold",
            "forecast_steps": 0,
            # Учётная цена золота ЦБ доступна с 1998-01 (новые рубли, после
            # деноминации); ранний-1998 ≈ 52 руб/г до девальвации, поэтому
            # порог validation.min понижен с 100 до 40.
            "validation": {"min": 40},
            "backfill_from": "1998-01-01",
        },
        "is_active": True,
        "category": "Товарные рынки",
    },
    {
        "code": "btc-usd",
        "name": "Биткоин (BTC/USD)",
        "name_en": "Bitcoin (BTC/USD)",
        "unit": "USD",
        "frequency": "daily",
        "source": "Binance",
        "source_url": "https://www.binance.com/en/trade/BTC_USDT",
        "description": (
            "Курс биткоина к доллару США по данным крупнейшей криптовалютной "
            "биржи Binance. Биткоин — первая и самая капитализированная "
            "криптовалюта; для российской аудитории он стал альтернативным "
            "активом наряду с золотом и иностранной валютой."
        ),
        "methodology": (
            "Дневная цена биткоина в долларах США по спотовому рынку на бирже "
            "Binance: каждая точка — цена закрытия календарного дня. Рынок "
            "работает круглосуточно без выходных. На карточке доступны "
            "ежедневный курс и средние по неделе, месяцу, кварталу и году — "
            "последние считаются из того же ряда для удобства сравнения."
        ),
        "parser_type": "binance_btcusdt_daily",
        "model_config_json": {
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "binance_symbol": "BTCUSDT",
            "validation": {"min": 100, "max": 1_000_000},
        },
        "is_active": True,
        "category": "Валюты",
    },
    {
        "code": "eth-usd",
        "name": "Эфириум (ETH/USD)",
        "name_en": "Ethereum (ETH/USD)",
        "unit": "USD",
        "frequency": "daily",
        "source": "Binance",
        "source_url": "https://www.binance.com/en/trade/ETH_USDT",
        "description": (
            "Курс эфириума к доллару США по данным крупнейшей криптовалютной "
            "биржи Binance. Эфириум — вторая по капитализации криптовалюта и "
            "основная платформа для смарт-контрактов; для российской аудитории "
            "он входит в число альтернативных активов наряду с биткоином."
        ),
        "methodology": (
            "Дневная цена эфириума в долларах США по спотовому рынку на бирже "
            "Binance: каждая точка — цена закрытия календарного дня. Рынок "
            "работает круглосуточно без выходных. На карточке доступны "
            "ежедневный курс и средние по неделе, месяцу, кварталу и году — "
            "последние считаются из того же ряда для удобства сравнения."
        ),
        "parser_type": "binance_btcusdt_daily",
        "model_config_json": {
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "binance_symbol": "ETHUSDT",
            "validation": {"min": 10, "max": 100_000},
        },
        "is_active": True,
        "category": "Валюты",
    },
    {
        "code": "sol-usd",
        "name": "Солана (SOL/USD)",
        "name_en": "Solana (SOL/USD)",
        "unit": "USD",
        "frequency": "daily",
        "source": "Binance",
        "source_url": "https://www.binance.com/en/trade/SOL_USDT",
        "description": (
            "Курс монеты Solana к доллару США по данным крупнейшей "
            "криптовалютной биржи Binance. Solana — одна из крупнейших "
            "высокопроизводительных блокчейн-платформ; её курс отражает спрос "
            "на альтернативные криптоактивы помимо биткоина и эфириума."
        ),
        "methodology": (
            "Дневная цена монеты Solana в долларах США по спотовому рынку на "
            "бирже Binance: каждая точка — цена закрытия календарного дня. "
            "Рынок работает круглосуточно без выходных. На карточке доступны "
            "ежедневный курс и средние по неделе, месяцу, кварталу и году — "
            "последние считаются из того же ряда для удобства сравнения."
        ),
        "parser_type": "binance_btcusdt_daily",
        "model_config_json": {
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "binance_symbol": "SOLUSDT",
            "validation": {"min": 1, "max": 10_000},
        },
        "is_active": True,
        "category": "Валюты",
    },
    {
        "code": "imoex",
        "name": "Индекс МосБиржи",
        "name_en": "MOEX Russia Index",
        "unit": "пунктов",
        "frequency": "daily",
        "source": "Московская биржа",
        "source_url": "https://www.moex.com/ru/index/IMOEX",
        "description": (
            "Основной индекс российского рынка акций — взвешенный по "
            "капитализации показатель стоимости наиболее ликвидных бумаг "
            "крупнейших компаний. Рассчитывается в рублях и отражает общее "
            "состояние фондового рынка России."
        ),
        "methodology": (
            "Индекс рассчитывается Московской биржей в реальном времени по "
            "ценам сделок с акциями, входящими в базу расчёта; веса бумаг "
            "ограничены и пересматриваются ежеквартально. Каждая точка ряда — "
            "значение закрытия торгового дня."
        ),
        "parser_type": "moex_index_daily",
        "model_config_json": {
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "moex_secid": "IMOEX",
            "validation": {"min": 100, "max": 20_000},
        },
        "is_active": True,
        "category": "Индексы",
    },
    {
        "code": "mcftr",
        "name": "Индекс МосБиржи полной доходности",
        "name_en": "MOEX Total Return Index",
        "unit": "пунктов",
        "frequency": "daily",
        "source": "Московская биржа",
        "source_url": "https://www.moex.com/ru/index/MCFTR",
        "description": (
            "Индекс полной доходности рынка акций: к изменению цен бумаг "
            "добавляется реинвестирование выплаченных дивидендов. Показывает "
            "совокупный результат вложений в широкий рынок, а не только "
            "ценовую динамику."
        ),
        "methodology": (
            "Рассчитывается Московской биржей на той же базе бумаг, что и "
            "основной индекс рынка акций, но с учётом дивидендов, "
            "реинвестированных в индекс. Каждая точка — значение закрытия "
            "торгового дня."
        ),
        "parser_type": "moex_index_daily",
        "model_config_json": {
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "moex_secid": "MCFTR",
            "validation": {"min": 100, "max": 50_000},
        },
        "is_active": True,
        "category": "Индексы",
    },
    {
        "code": "rtsi",
        "name": "Индекс РТС",
        "name_en": "RTS Index",
        "unit": "пунктов",
        "frequency": "daily",
        "source": "Московская биржа",
        "source_url": "https://www.moex.com/ru/index/RTSI",
        "description": (
            "Долларовый индекс российского рынка акций: рассчитывается по тем "
            "же бумагам, что и рублёвый индекс рынка, но в пересчёте на доллары "
            "США. Поэтому он чувствителен и к динамике акций, и к курсу рубля."
        ),
        "methodology": (
            "Рассчитывается Московской биржей в долларах США по ценам сделок с "
            "акциями базы расчёта с учётом валютного курса. Каждая точка ряда — "
            "значение закрытия торгового дня."
        ),
        "parser_type": "moex_index_daily",
        "model_config_json": {
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "moex_secid": "RTSI",
            "validation": {"min": 100, "max": 5_000},
        },
        "is_active": True,
        "category": "Индексы",
    },
    {
        "code": "rgbi",
        "name": "Индекс гособлигаций (RGBI)",
        "name_en": "Russian Government Bond Index (RGBI)",
        "unit": "пунктов",
        "frequency": "daily",
        "source": "Московская биржа",
        "source_url": "https://www.moex.com/ru/index/RGBI",
        "description": (
            "Индекс рынка государственных облигаций (ОФЗ): отражает изменение "
            "чистых цен корзины наиболее ликвидных выпусков. Снижение индекса "
            "обычно сопутствует росту доходностей ОФЗ, рост — их снижению."
        ),
        "methodology": (
            "Рассчитывается Московской биржей по чистым ценам корзины выпусков "
            "облигаций федерального займа с фиксированным купоном. Каждая точка "
            "ряда — значение закрытия торгового дня."
        ),
        "parser_type": "moex_index_daily",
        "model_config_json": {
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "moex_secid": "RGBI",
            "validation": {"min": 50, "max": 1_000},
        },
        "is_active": True,
        "category": "Индексы",
    },
    {
        "code": "corp-bond-index",
        "name": "Индекс корпоративных облигаций МосБиржи",
        "name_en": "MOEX Corporate Bond Index",
        "unit": "пунктов",
        "frequency": "daily",
        "source": "Московская биржа",
        "source_url": "https://www.moex.com/ru/index/RUCBTRNS",
        "description": (
            "Индекс рынка корпоративных облигаций: отражает совокупную "
            "доходность корзины ликвидных рублёвых выпусков компаний с учётом "
            "купонов. Используется как ориентир доходности корпоративного "
            "долгового рынка."
        ),
        "methodology": (
            "Рассчитывается Московской биржей по корзине корпоративных "
            "облигаций как индекс совокупного дохода (с реинвестированием "
            "купонов). Каждая точка ряда — значение закрытия торгового дня."
        ),
        "parser_type": "moex_index_daily",
        "model_config_json": {
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "moex_secid": "RUCBTRNS",
            "validation": {"min": 50, "max": 2_000},
        },
        "is_active": True,
        "category": "Индексы",
    },
    {
        "code": "brent",
        "name": "Нефть Brent",
        "name_en": "Brent Crude Oil",
        "unit": "USD/баррель",
        "frequency": "daily",
        "source": "Рыночные котировки",
        "source_url": "https://www.moex.com/ru/derivatives/contract.aspx?code=BR",
        "description": (
            "Цена нефти марки Brent в долларах США за баррель по итогам "
            "каждого торгового дня. Brent — ключевой эталон мирового "
            "нефтяного рынка; для России динамика цены связана с "
            "бюджетными поступлениями, курсом рубля и платёжным балансом."
        ),
        "methodology": (
            "Дневная цена Brent в долларах за баррель по рыночным "
            "котировкам: каждая точка — цена закрытия календарного дня. "
            "На карточке доступны ежедневное значение и средние по неделе, "
            "месяцу, кварталу и году — последние считаются из того же ряда "
            "для удобства сравнения тренда."
        ),
        "parser_type": "moex_brent_daily",
        "model_config_json": {
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "yahoo_symbol": "BZ=F",
            "validation": {"min": 5, "max": 300},
        },
        "is_active": True,
        "category": "Товарные рынки",
    },
    {
        "code": "copper",
        "name": "Медь",
        "name_en": "Copper",
        "unit": "USD/фунт",
        "frequency": "daily",
        "source": "Рыночные котировки",
        "source_url": "https://www.cmegroup.com/markets/metals/base/copper.html",
        "description": (
            "Мировая цена меди в долларах США за фунт по итогам каждого "
            "торгового дня. Медь — ключевой промышленный металл, её котировки "
            "считаются опережающим индикатором мировой экономики; для России "
            "это важная статья сырьевого экспорта."
        ),
        "methodology": (
            "Дневная цена меди в долларах за фунт по рыночным котировкам "
            "ближайшего фьючерсного контракта: каждая точка — цена закрытия "
            "календарного дня. На карточке доступны ежедневное значение и "
            "средние по неделе, месяцу, кварталу и году, рассчитанные из того "
            "же ряда; прогноз не строится."
        ),
        "parser_type": "moex_brent_daily",
        "model_config_json": {
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "yahoo_symbol": "HG=F",
            "validation": {"min": 0.5, "max": 20},
        },
        "is_active": True,
        "category": "Товарные рынки",
    },
    {
        "code": "silver",
        "name": "Серебро",
        "name_en": "Silver",
        "unit": "USD/унция",
        "frequency": "daily",
        "source": "Рыночные котировки",
        "source_url": "https://www.cmegroup.com/markets/metals/precious/silver.html",
        "description": (
            "Мировая цена серебра в долларах США за тройскую унцию по итогам "
            "каждого торгового дня. Серебро сочетает функции драгоценного "
            "металла и промышленного сырья, поэтому его котировки реагируют и "
            "на инвестиционный спрос, и на промышленный цикл."
        ),
        "methodology": (
            "Дневная цена серебра в долларах за тройскую унцию по рыночным "
            "котировкам ближайшего фьючерсного контракта: каждая точка — цена "
            "закрытия календарного дня. На карточке доступны ежедневное "
            "значение и средние по неделе, месяцу, кварталу и году из того же "
            "ряда; прогноз не строится."
        ),
        "parser_type": "moex_brent_daily",
        "model_config_json": {
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "yahoo_symbol": "SI=F",
            "validation": {"min": 2, "max": 200},
        },
        "is_active": True,
        "category": "Товарные рынки",
    },
    {
        "code": "natural-gas",
        "name": "Природный газ",
        "name_en": "Natural Gas (Henry Hub)",
        "unit": "USD/MMBtu",
        "frequency": "daily",
        "source": "Рыночные котировки",
        "source_url": "https://www.cmegroup.com/markets/energy/natural-gas/natural-gas.html",
        "description": (
            "Мировая цена природного газа в долларах США за миллион британских "
            "тепловых единиц (MMBtu) по эталонному хабу Henry Hub. Газ — одна "
            "из ключевых статей российского экспорта, а его цена определяет "
            "доходы энергетического сектора."
        ),
        "methodology": (
            "Дневная цена природного газа в долларах за MMBtu по рыночным "
            "котировкам ближайшего фьючерсного контракта Henry Hub: каждая "
            "точка — цена закрытия календарного дня. На карточке доступны "
            "ежедневное значение и средние по неделе, месяцу, кварталу и году "
            "из того же ряда; прогноз не строится."
        ),
        "parser_type": "moex_brent_daily",
        "model_config_json": {
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "yahoo_symbol": "NG=F",
            "validation": {"min": 0.5, "max": 50},
        },
        "is_active": True,
        "category": "Товарные рынки",
    },
    {
        "code": "wheat",
        "name": "Пшеница",
        "name_en": "Wheat",
        "unit": "US¢/бушель",
        "frequency": "daily",
        "source": "Рыночные котировки",
        "source_url": "https://www.cmegroup.com/markets/agriculture/grains/wheat.html",
        "description": (
            "Мировая цена пшеницы в центах США за бушель по итогам каждого "
            "торгового дня. Россия — крупнейший экспортёр пшеницы, поэтому "
            "мировые котировки напрямую связаны с доходами "
            "агропромышленного комплекса."
        ),
        "methodology": (
            "Дневная цена пшеницы в центах США за бушель по рыночным "
            "котировкам ближайшего фьючерсного контракта: каждая точка — цена "
            "закрытия торгового дня. На карточке доступны ежедневное значение "
            "и средние по неделе, месяцу, кварталу и году из того же ряда; "
            "прогноз не строится."
        ),
        "parser_type": "moex_brent_daily",
        "model_config_json": {
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "yahoo_symbol": "ZW=F",
            "validation": {"min": 100, "max": 2000},
        },
        "is_active": True,
        "category": "Товарные рынки",
    },
    {
        "code": "soybean",
        "name": "Соевые бобы",
        "name_en": "Soybeans",
        "unit": "US¢/бушель",
        "frequency": "daily",
        "source": "Рыночные котировки",
        "source_url": "https://www.cmegroup.com/markets/agriculture/oilseeds/soybean.html",
        "description": (
            "Мировая цена соевых бобов в центах США за бушель по итогам "
            "каждого торгового дня. Соя — одна из ключевых "
            "сельскохозяйственных культур мирового рынка, индикатор спроса на "
            "корма и растительные масла."
        ),
        "methodology": (
            "Дневная цена соевых бобов в центах США за бушель по рыночным "
            "котировкам ближайшего фьючерсного контракта: каждая точка — цена "
            "закрытия торгового дня. На карточке доступны ежедневное значение "
            "и средние по неделе, месяцу, кварталу и году из того же ряда; "
            "прогноз не строится."
        ),
        "parser_type": "moex_brent_daily",
        "model_config_json": {
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "yahoo_symbol": "ZS=F",
            "validation": {"min": 300, "max": 3000},
        },
        "is_active": True,
        "category": "Товарные рынки",
    },
    {
        "code": "coal",
        "name": "Уголь",
        "name_en": "Coal (Rotterdam)",
        "unit": "USD/т",
        "frequency": "daily",
        "source": "Рыночные котировки",
        "source_url": "https://www.ice.com/products/243/Rotterdam-Coal-Futures",
        "description": (
            "Мировая цена энергетического угля в долларах США за тонну по "
            "эталонному европейскому хабу (Роттердам) по итогам каждого "
            "торгового дня. Уголь — значимая статья российского сырьевого "
            "экспорта, особенно в страны Азии."
        ),
        "methodology": (
            "Дневная цена энергетического угля в долларах за тонну по рыночным "
            "котировкам ближайшего фьючерсного контракта: каждая точка — цена "
            "закрытия торгового дня. На карточке доступны ежедневное значение "
            "и средние по неделе, месяцу, кварталу и году из того же ряда; "
            "прогноз не строится."
        ),
        "parser_type": "moex_brent_daily",
        "model_config_json": {
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "yahoo_symbol": "MTF=F",
            "validation": {"min": 20, "max": 600},
        },
        "is_active": True,
        "category": "Товарные рынки",
    },
    {
        "code": "steel",
        "name": "Сталь",
        "name_en": "Steel (HRC)",
        "unit": "USD/т",
        "frequency": "daily",
        "source": "Рыночные котировки",
        "source_url": "https://www.cmegroup.com/markets/metals/ferrous/hrc-steel.html",
        "description": (
            "Мировая цена горячекатаного стального проката (HRC) в долларах "
            "США за тонну по итогам каждого торгового дня. Сталь — базовый "
            "индустриальный материал; её цена отражает спрос в строительстве и "
            "машиностроении и важна для российской металлургии."
        ),
        "methodology": (
            "Дневная цена горячекатаного стального проката в долларах за тонну "
            "по рыночным котировкам ближайшего фьючерсного контракта: каждая "
            "точка — цена закрытия торгового дня. На карточке доступны "
            "ежедневное значение и средние по неделе, месяцу, кварталу и году "
            "из того же ряда; прогноз не строится."
        ),
        "parser_type": "moex_brent_daily",
        "model_config_json": {
            "forecast_steps": 0,
            "forecast_transform": "absolute",
            "yahoo_symbol": "HRC=F",
            "validation": {"min": 100, "max": 3000},
        },
        "is_active": True,
        "category": "Товарные рынки",
    },
    {
        "code": "fuel-ai92",
        "name": "Цены на бензин АИ-92",
        "name_en": "Gasoline AI-92",
        "unit": "руб./л",
        "frequency": "weekly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/price",
        "description": (
            "Средняя потребительская цена бензина марки АИ-92 в России, рублей "
            "за литр. Еженедельные данные Росстата на конец периода."
        ),
        "methodology": (
            "Средняя по России потребительская цена автомобильного бензина "
            "марки АИ-92 на конец недели, рублей за литр. Цена усредняется "
            "Росстатом по выборке регионов и автозаправочных станций и "
            "публикуется еженедельно. На карточке — недельный ряд и средние "
            "по месяцу, кварталу и году; прогноз строится по месячным средним, "
            "а квартальная и годовая оценки выводятся из месячного прогноза."
        ),
        "parser_type": "rosstat_weekly_price",
        "model_config_json": {
            "product_label": "Бензин автомобильный марки АИ-92, л",
            # Недельный прогноз отключён (профанация < месяца). Прогноз — на
            # месячной средней (fuel-ai92-avg-month, monthly_auto) с протяжкой
            # в квартал/год. См. view_model_families.monthly_forecast.
            "forecast_steps": 0,
            "validation": {"min": 20, "max": 300},
        },
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "fuel-ai95",
        "name": "Цены на бензин АИ-95",
        "name_en": "Gasoline AI-95",
        "unit": "руб./л",
        "frequency": "weekly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/price",
        "description": (
            "Средняя потребительская цена бензина марки АИ-95 в России, рублей "
            "за литр. Еженедельные данные Росстата на конец периода."
        ),
        "methodology": (
            "Средняя по России потребительская цена автомобильного бензина "
            "марки АИ-95 на конец недели, рублей за литр. Цена усредняется "
            "Росстатом по выборке регионов и автозаправочных станций и "
            "публикуется еженедельно. На карточке — недельный ряд и средние "
            "по месяцу, кварталу и году; прогноз строится по месячным средним, "
            "а квартальная и годовая оценки выводятся из месячного прогноза."
        ),
        "parser_type": "rosstat_weekly_price",
        "model_config_json": {
            "product_label": "Бензин автомобильный марки АИ-95, л",
            "forecast_steps": 0,
            "validation": {"min": 20, "max": 300},
        },
        "is_active": True,
        "category": "Цены",
    },
    {
        "code": "fuel-diesel",
        "name": "Цена дизельного топлива",
        "name_en": "Diesel Fuel",
        "unit": "руб./л",
        "frequency": "weekly",
        "source": "Росстат",
        "source_url": "https://rosstat.gov.ru/statistics/price",
        "description": (
            "Средняя потребительская цена дизельного топлива в России, рублей "
            "за литр. Еженедельные данные Росстата на конец периода."
        ),
        "methodology": (
            "Средняя по России потребительская цена дизельного топлива на "
            "конец недели, рублей за литр. Цена усредняется Росстатом по "
            "выборке регионов и автозаправочных станций и публикуется "
            "еженедельно. На карточке — недельный ряд и средние по месяцу, "
            "кварталу и году; прогноз строится по месячным средним, а "
            "квартальная и годовая оценки выводятся из месячного прогноза."
        ),
        "parser_type": "rosstat_weekly_price",
        "model_config_json": {
            "product_label": "Дизельное топливо, л",
            "forecast_steps": 0,
            "validation": {"min": 20, "max": 300},
        },
        "is_active": True,
        "category": "Цены",
    },
]


# --- Сгенерированные sibling-индикаторы режимов (canonical view-mode config) ---
#
# Каждый НЕ-нативный режим карточки = отдельный derived-ряд с верной частотой
# (ADR-0006) и публичными текстами (methodology-language.mdc). Скрыты из
# каталога (INDICATOR_HIDDEN_FROM_LISTING), но доступны через переключатель
# режимов и поиск. Единый источник истины — app.data.view_model_families;
# уже объявленные вручную коды (легаси gdp-*/wages-yoy) здесь пропускаются.

_PARENT_META = {ind["code"]: ind for ind in INDICATORS}
_EXISTING_CODES = set(_PARENT_META)

_GRAN_PERIOD = {
    "week": "за неделю", "month": "за месяц", "quarter": "за квартал", "year": "за год",
}
_GRAN_EOP = {
    "week": "на конец недели", "month": "на конец месяца",
    "quarter": "на конец квартала", "year": "на конец года",
}


def _sibling_texts(meta: dict) -> tuple[str, str]:
    """Публичные description/methodology для sibling-ряда (без внутренностей)."""
    pname = _PARENT_META[meta["parent"]]["name"]
    code = meta["code"]
    is_pct = meta.get("unit") == "%"
    unit = meta.get("unit", "единицах источника")
    if code.endswith("-mom"):
        if is_pct:
            return (
                f"Изменение показателя «{pname}» к предыдущему месяцу, в процентах.",
                "Прирост к предыдущему календарному месяцу: отношение текущего "
                "значения к значению месяцем ранее, выраженное в процентах.",
            )
        return (
            f"Изменение показателя «{pname}» к предыдущему месяцу, в {unit}.",
            f"Абсолютное изменение к предыдущему календарному месяцу, в {unit}. "
            "Подходит для ставок и долей, где процентное изменение вводит в заблуждение.",
        )
    if code.endswith("-qoq"):
        if is_pct:
            return (
                f"Изменение показателя «{pname}» к предыдущему кварталу, в процентах.",
                "Прирост к предыдущему кварталу: значения сводятся к квартальной "
                "частоте, после чего берётся отношение к предыдущему кварталу, в процентах.",
            )
        return (
            f"Изменение показателя «{pname}» к предыдущему кварталу, в {unit}.",
            f"Абсолютное изменение к предыдущему кварталу, в {unit}. Подходит для "
            "рядов со знаком и для ставок, где процентное изменение вводит в заблуждение.",
        )
    if code.endswith("-index"):
        return (
            f"Показатель «{pname}» в виде индекса: первое доступное наблюдение "
            "принято за 100.",
            "Индекс относительно первого доступного периода (база = 100): каждое "
            "значение делится на первое и умножается на 100. Показывает относительную "
            "динамику ряда нарастающим итогом.",
        )
    # Г/г на нативной частоте (-yoy) и его агрегаты по кварталам/годам
    # (-yoy-quarter / -yoy-year). Проверяем сначала более длинные суффиксы.
    _yoy_target = {
        "-yoy": "соответствующему периоду предыдущего года",
        "-yoy-quarter": "соответствующему кварталу предыдущего года",
        "-yoy-year": "предыдущему году",
    }
    _yoy_method_pct = {
        "-yoy": "Отношение значения к значению годом ранее, выраженное в процентах.",
        "-yoy-quarter": "Значения сводятся к квартальной частоте, затем берётся "
                        "отношение к тому же кварталу прошлого года, в процентах.",
        "-yoy-year": "Значения сводятся к годовой частоте, затем берётся отношение "
                     "к значению предыдущего года, в процентах.",
    }
    _yoy_method_abs = {
        "-yoy": "Абсолютное изменение к значению годом ранее",
        "-yoy-quarter": "Значения сводятся к квартальной частоте, затем берётся "
                        "абсолютное изменение к тому же кварталу прошлого года",
        "-yoy-year": "Значения сводятся к годовой частоте, затем берётся абсолютное "
                     "изменение к значению предыдущего года",
    }
    for _sfx in ("-yoy-quarter", "-yoy-year", "-yoy"):
        if code.endswith(_sfx):
            target = _yoy_target[_sfx]
            if is_pct:
                return (
                    f"Изменение показателя «{pname}» к {target}, в процентах.",
                    _yoy_method_pct[_sfx],
                )
            return (
                f"Изменение показателя «{pname}» к {target}, в {unit}.",
                f"{_yoy_method_abs[_sfx]}, в тех же единицах, что и исходный ряд. "
                "Подходит для рядов со знаком и для ставок, где процентное "
                "изменение вводит в заблуждение.",
            )
    kind, _, gran = code[len(meta["parent"]) + 1:].partition("-")
    period = _GRAN_PERIOD.get(gran, "за период")
    eop = _GRAN_EOP.get(gran, "на конец периода")
    if kind == "avg":
        return (
            f"Значение показателя «{pname}» в среднем {period}.",
            f"Среднее арифметическое наблюдений показателя {period}, "
            "в тех же единицах, что и исходный ряд.",
        )
    if kind == "sum":
        return (
            f"Суммарное значение показателя «{pname}» {period}.",
            f"Сумма наблюдений показателя {period}, в тех же единицах, что и исходный ряд.",
        )
    return (
        f"Значение показателя «{pname}» {eop}.",
        f"Значение показателя {eop} (последнее наблюдение периода), "
        "в тех же единицах, что и исходный ряд.",
    )


# Горизонт-gate прогноза для протянутых агрегатов (реальный горизонт берётся
# из длины прогноза источника через future_only в derived_from_source).
_FCAST_STEPS_BY_FREQ = {"monthly": 12, "quarterly": 4, "annual": 2}

_generated_sibling_codes: list[str] = []
for _meta in _iter_vmf_siblings():
    if _meta["code"] in _EXISTING_CODES:
        continue
    _parent = _PARENT_META[_meta["parent"]]
    _desc, _method = _sibling_texts(_meta)
    _fcast = _meta.get("forecast")
    _strategy = _meta.get("forecast_strategy")
    if _strategy == "monthly_auto":
        # avg-month недельной семьи (топливо): собственный monthly_auto по
        # месячной средней. Квартал/год протягиваются из неё (derived ниже).
        _model_cfg = {
            "forecast_steps": _meta.get("forecast_steps") or 12,
            "forecast_strategy": "monthly_auto",
        }
    elif _fcast:
        _model_cfg = {
            "forecast_steps": _meta.get("forecast_steps")
            or _FCAST_STEPS_BY_FREQ.get(_meta["frequency"], 4),
            "forecast_strategy": "derived_from_source",
            "derived_forecast": _fcast,
        }
    else:
        _model_cfg = {"forecast_steps": 0}
    INDICATORS.append({
        "code": _meta["code"],
        "name": _meta["name"],
        "unit": _meta["unit"],
        "frequency": _meta["frequency"],
        "source": _parent.get("source", ""),
        "source_url": _parent.get("source_url", ""),
        "description": _desc,
        "methodology": _method,
        "parser_type": "derived",
        "model_config_json": _model_cfg,
        "is_active": True,
        "category": _meta["category"],
    })
    _generated_sibling_codes.append(_meta["code"])
    _EXISTING_CODES.add(_meta["code"])

# Скрываем сгенерированные siblings из каталога (доступны через режимы/поиск).
INDICATOR_HIDDEN_FROM_LISTING.update(_generated_sibling_codes)


# --- Месячный прогноз (Прогноз_месячных_данных.ipynb, руководитель, июнь 2026) ---
#
# Руководитель допилил единый алгоритм прогноза для ВСЕХ месячных показателей
# (ADF-автотрансформ + multi-window OLS, см. forecast_strategies/monthly_auto).
# Включаем его для всех месячных source-рядов, у которых прогноз был выключен
# (forecast_steps=0). Немесячные ряды и индикаторы со своими стратегиями
# (CPI/ИЦП/ВВП/жильё, derived) не трогаем — оставляем как были.
MONTHLY_AUTO_FORECAST_CODES = {
    "auto-loan-rate", "budget-deficit", "budget-expenditure", "budget-revenue",
    "business-credit", "consumer-credit",
    "credit-rate-corp-1to3y", "credit-rate-corp-over3y", "credit-rate-corp-short",
    "credit-rate-ind-1to3y", "credit-rate-ind-over3y", "credit-rate-ind-short",
    "deposit-rate", "deposit-rate-long", "deposit-rate-medium",
    "deposits-business", "deposits-individual", "employment",
    "exports-monthly", "housing-commissioned", "imports-monthly",
    "labor-force", "m0", "m1", "m2", "mortgage-rate",
    "services-exports-monthly", "services-imports-monthly",
    "trade-balance-monthly", "unemployment", "wages-nominal",
    # Включены обновлённым алгоритмом (июнь 2026): rolling+пер-горизонтная
    # реконструкция чинят строительство/розницу/ИПП — раньше прогноз был выключен.
    "construction-work", "retail-trade", "ipi",
    # ИПП по разделам ОКВЭД2 (добыча/обработка/энергетика/водоснабжение) —
    # те же месячные индексы, что и агрегат, прогноз тем же monthly_auto.
    "ipi-mining", "ipi-manufacturing", "ipi-energy", "ipi-water",
    # Индекс доступности жилья — расчётный (derived) ряд, но прогнозируется
    # собственной моделью monthly_auto на самом ряде отношения (запрос
    # руководителя 2026-06-22 «почему по доступности нет прогноза»). Ретрейн
    # после пересчёта движком — в scheduler (источниковый каскад его не покрывает).
    "housing-affordability", "housing-affordability-primary",
    # Реальная зарплата — derived-индекс покупательной способности; прогнозируем
    # собственной monthly_auto прямо по ряду индекса (как housing-affordability).
    # Ретрейн после пересчёта движком — в scheduler.
    "wages-real",
}

for _ind in INDICATORS:
    if _ind["code"] in MONTHLY_AUTO_FORECAST_CODES:
        _cfg = _ind.setdefault("model_config_json", {})
        _cfg["forecast_steps"] = 12
        _cfg["forecast_strategy"] = "monthly_auto"


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

        # Точечная заливка известных дыр месячных source-рядов (напр. декабрь
        # 2022 у зарплаты — monthly ряд загружен разово, парсер исторические
        # пропуски не восстанавливает). on_conflict_do_nothing: никогда не
        # перетираем данные парсера, только заполняем отсутствующие даты.
        # ДО CalculationEngine, чтобы annual mean увидел полный год.
        from app.data.wages_historical import MONTHLY_GAP_FILL
        gap_count = 0
        for src_code, points in MONTHLY_GAP_FILL.items():
            ind_q = await db.execute(select(Indicator.id).where(Indicator.code == src_code))
            ind_id = ind_q.scalar_one_or_none()
            if ind_id is None:
                continue
            for pt_date, pt_value in points.items():
                stmt = pg_insert(IndicatorData).values(
                    indicator_id=ind_id, date=pt_date, value=pt_value,
                ).on_conflict_do_nothing(constraint="uq_indicator_date")
                res = await db.execute(stmt)
                if res.rowcount > 0:
                    gap_count += 1
        if gap_count:
            await db.commit()
            print(f"  Gap-fill: inserted {gap_count} missing monthly source point(s)")

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

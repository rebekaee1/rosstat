from __future__ import annotations

import logging
import re
import hashlib
from datetime import date, datetime, timedelta

import requests
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session as async_session_factory
from app.services.calendar_sources.common import CalendarCandidate, stable_key, upsert_calendar_candidates
from app.services.calendar_sources.working_calendar import (
    calendar_source_url,
    is_working_day,
    next_month,
    nth_working_day,
)

logger = logging.getLogger(__name__)

CBR_CALENDAR_PAGE = "https://www.cbr.ru/statistics/indcalendar/"
CBR_ICS_URL = "https://www.cbr.ru/Queries/FileSource/105732/vCalendar.ics?inline=True"
CBR_MONETARY_POLICY_CALENDAR_URL = "https://cbr.ru/dkp/cal_mp/"
MINFIN_SCHEDULE_URL = "https://minfin.gov.ru/ru/statistics/schedule"
ROSSTAT_CPI_RULE_URL = "https://rosstat.gov.ru/statistics/price"
ROSSTAT_PRICE_URL = "https://rosstat.gov.ru/statistics/price"
ROSSTAT_GDP_URL = "https://rosstat.gov.ru/statistics/accounts"
ROSSTAT_LABOR_URL = "https://rosstat.gov.ru/labor_market_employment_salaries"
ROSSTAT_BUSINESS_URL = "https://rosstat.gov.ru/enterprise_industrial"
ROSSTAT_TRADE_URL = "https://rosstat.gov.ru/folder/10705"
# Строительство / ввод жилья — не путать с торговлей (folder/10705).
ROSSTAT_CONSTRUCTION_URL = "https://rosstat.gov.ru/folder/14458"
ROSSTAT_CONSTRUCTION_KEP_URL = "https://rosstat.gov.ru/compendium/document/50802"


MONTH_NAMES_RU = [
    "", "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
]


# Per-indicator context shown on the calendar card. One human sentence about
# what the indicator measures, so the event description carries meaning beyond
# the bare scheduling note. Public text: no source filenames, no parser jargon.
INDICATOR_CALENDAR_CONTEXT = {
    "cpi": "Индекс потребительских цен измеряет среднее изменение стоимости фиксированного набора товаров и услуг и служит основной мерой инфляции для населения.",
    "cpi-food": "Изменение розничных цен на продовольственные товары — продуктовая составляющая потребительской инфляции.",
    "cpi-nonfood": "Изменение розничных цен на непродовольственные товары — одна из составляющих потребительской инфляции.",
    "cpi-services": "Изменение цен на платные услуги для населения — сервисная составляющая потребительской инфляции.",
    "ipi": "Индекс промышленного производства отражает динамику выпуска в добыче, обработке, энергетике и водоснабжении относительно базового периода.",
    "unemployment": "Доля рабочей силы, не имеющей работы, но активно ищущей её, по методологии Международной организации труда.",
    "wages-nominal": "Среднемесячная начисленная заработная плата работников организаций до вычета налогов.",
    "retail-trade": "Стоимость товаров, проданных населению через розничную сеть, — индикатор потребительского спроса.",
    "housing-commissioned": "Площадь введённых в эксплуатацию жилых домов — индикатор активности в жилищном строительстве.",
    "ppi": "Индекс цен производителей отражает изменение отпускных цен промышленных предприятий и обычно опережает потребительскую инфляцию.",
    "construction-work": "Объём работ, выполненных по виду деятельности «Строительство», в стоимостном выражении.",
    "gdp-nominal": "Совокупная рыночная стоимость всех конечных товаров и услуг, произведённых в стране за квартал, в текущих ценах.",
    "gdp-real": "Объём произведённых товаров и услуг в сопоставимых ценах, очищенный от влияния инфляции.",
    "budget-revenue": "Поступления в федеральный бюджет: налоговые и неналоговые доходы за отчётный период.",
    "budget-expenditure": "Кассовые расходы федерального бюджета за отчётный период.",
    "budget-deficit": "Разница между доходами и расходами федерального бюджета: профицит при превышении доходов, дефицит при их нехватке.",
    "usd-rub": "Официальный курс доллара США к рублю, устанавливаемый Банком России.",
    "eur-rub": "Официальный курс евро к рублю, устанавливаемый Банком России.",
    "cny-rub": "Официальный курс китайского юаня к рублю, устанавливаемый Банком России.",
    "gold-price": "Учётная цена на золото, устанавливаемая Банком России на основе мировых котировок.",
    "ruonia": "Индикативная взвешенная ставка однодневных рублёвых межбанковских кредитов крупнейших банков.",
    "key-rate": "Ключевая ставка — основной инструмент денежно-кредитной политики Банка России, определяющий стоимость денег в экономике.",
    "international-reserves": "Высоколиквидные иностранные активы государства: валюта, золото и резервная позиция в международных финансовых институтах.",
    "m2": "Денежный агрегат М2 — наличные деньги и средства на рублёвых счетах организаций и населения.",
    "m1": "Денежный агрегат М1 — наличные деньги и средства на текущих счетах до востребования.",
    "m0": "Денежный агрегат М0 — наличные деньги в обращении вне банковской системы.",
    "business-credit": "Объём кредитов, выданных банками юридическим лицам.",
    "consumer-credit": "Объём кредитов, выданных банками физическим лицам.",
    "deposits-business": "Средства организаций, привлечённые банками на счета и депозиты.",
    "deposits-individual": "Средства физических лиц, размещённые на банковских счетах и вкладах.",
    "deposit-rate": "Средневзвешенная ставка по банковским депозитам.",
    "credit-rate-corp-short": "Средневзвешенная ставка по краткосрочным кредитам организациям (до 1 года).",
    "credit-rate-corp-1to3y": "Средневзвешенная ставка по кредитам организациям на срок от 1 до 3 лет.",
    "credit-rate-corp-over3y": "Средневзвешенная ставка по кредитам организациям на срок свыше 3 лет.",
    "credit-rate-ind-short": "Средневзвешенная ставка по краткосрочным кредитам населению (до 1 года).",
    "credit-rate-ind-1to3y": "Средневзвешенная ставка по кредитам населению на срок от 1 до 3 лет.",
    "credit-rate-ind-over3y": "Средневзвешенная ставка по кредитам населению на срок свыше 3 лет.",
    "mortgage-rate": "Средневзвешенная ставка по жилищным (ипотечным) кредитам.",
    "auto-loan-rate": "Средневзвешенная ставка по автокредитам.",
    "exports": "Стоимость вывезенных из России товаров за период.",
    "imports": "Стоимость ввезённых в Россию товаров за период.",
    "trade-balance": "Сальдо торговли товарами: разница между экспортом и импортом.",
    "services-exports": "Стоимость услуг, оказанных резидентами России нерезидентам.",
    "services-imports": "Стоимость услуг, полученных резидентами России от нерезидентов.",
    "current-account": "Сальдо счёта текущих операций платёжного баланса: торговля товарами и услугами, первичные и вторичные доходы.",
    "external-debt": "Совокупная задолженность государства, банков и компаний России перед нерезидентами.",
    "fdi-net": "Чистый приток прямых иностранных инвестиций в небанковский сектор.",
}


def _event_description(code: str | None, schedule_note: str | None = None) -> str | None:
    """Combine the per-indicator context with a clean scheduling note.

    Keeps the card text meaningful (what the indicator is) and avoids the
    bare "дата рассчитана по правилу" phrasing that carried no information.
    """
    context = INDICATOR_CALENDAR_CONTEXT.get(code or "")
    parts = [p.strip() for p in (context, schedule_note) if p and p.strip()]
    if not parts:
        return None
    return " ".join(parts)


ROSSTAT_MONTHLY_RULES = [
    {
        "code": "cpi",
        "title": "Индекс потребительских цен (ИПЦ)",
        "title_en": "Consumer Price Index (CPI)",
        "importance": 3,
        "nth_workday": 9,
        "source_url": ROSSTAT_CPI_RULE_URL,
        "rule": "9-й рабочий день месяца, следующего за отчетным периодом",
    },
    {
        "code": "cpi-food",
        "title": "ИПЦ на продовольственные товары",
        "title_en": "CPI Food",
        "importance": 2,
        "nth_workday": 9,
        "source_url": ROSSTAT_CPI_RULE_URL,
        "rule": "9-й рабочий день месяца, следующего за отчетным периодом",
    },
    {
        "code": "cpi-nonfood",
        "title": "ИПЦ на непродовольственные товары",
        "title_en": "CPI Non-food",
        "importance": 2,
        "nth_workday": 9,
        "source_url": ROSSTAT_CPI_RULE_URL,
        "rule": "9-й рабочий день месяца, следующего за отчетным периодом",
    },
    {
        "code": "cpi-services",
        "title": "ИПЦ на услуги",
        "title_en": "CPI Services",
        "importance": 2,
        "nth_workday": 9,
        "source_url": ROSSTAT_CPI_RULE_URL,
        "rule": "9-й рабочий день месяца, следующего за отчетным периодом",
    },
    {
        "code": "ipi",
        "title": "Индекс промышленного производства (ИПП)",
        "title_en": "Industrial Production Index",
        "importance": 2,
        "nth_workday": 9,
        "source_url": ROSSTAT_BUSINESS_URL,
        "rule": "9-й рабочий день месяца, следующего за отчетным периодом",
    },
    {
        "code": "unemployment",
        "title": "Уровень безработицы",
        "title_en": "Unemployment Rate",
        "importance": 2,
        "nth_workday": 9,
        "source_url": ROSSTAT_LABOR_URL,
        "rule": "9-й рабочий день месяца, следующего за отчетным периодом",
    },
    {
        "code": "wages-nominal",
        "title": "Средняя номинальная заработная плата",
        "title_en": "Average Nominal Wages",
        "importance": 2,
        "nth_workday": 9,
        "source_url": ROSSTAT_LABOR_URL,
        "rule": "9-й рабочий день месяца, следующего за отчетным периодом",
    },
    {
        "code": "retail-trade",
        "title": "Оборот розничной торговли",
        "title_en": "Retail Trade Turnover",
        "importance": 2,
        "nth_workday": 15,
        "source_url": ROSSTAT_TRADE_URL,
        "rule": "15-й рабочий день месяца, следующего за отчетным периодом",
    },
    {
        "code": "housing-commissioned",
        "title": "Ввод в действие жилых домов",
        "title_en": "Housing Commissioned",
        "importance": 1,
        "nth_workday": 15,
        "source_url": ROSSTAT_CONSTRUCTION_URL,
        "rule": "15-й рабочий день месяца, следующего за отчетным периодом",
    },
    {
        "code": "ppi",
        "title": "Индекс цен производителей промышленных товаров (ИЦП)",
        "title_en": "Producer Price Index (PPI)",
        "importance": 2,
        "nth_workday": 18,
        "source_url": ROSSTAT_PRICE_URL,
        "rule": "18-й рабочий день месяца, следующего за отчетным периодом",
    },
    {
        "code": "construction-work",
        "title": "Объём работ по виду деятельности «Строительство»",
        "title_en": "Construction Work Volume",
        "importance": 1,
        "nth_workday": 15,
        "source_url": ROSSTAT_CONSTRUCTION_URL,
        "rule": "15-й рабочий день месяца, следующего за отчетным периодом",
    },
]

ROSSTAT_GDP_RULES = [
    {
        "code": "gdp-nominal",
        "title": "ВВП (предварительная оценка)",
        "title_en": "GDP First Estimate",
        "importance": 3,
        "lag_days": 60,
    },
    {
        "code": "gdp-real",
        "title": "ВВП (вторая оценка)",
        "title_en": "GDP Second Estimate",
        "importance": 2,
        "lag_days": 90,
    },
]

MINFIN_RULES = [
    {
        "code": "budget-revenue",
        "title": "Доходы федерального бюджета",
        "title_en": "Federal Budget Revenue",
        "importance": 2,
    },
    {
        "code": "budget-expenditure",
        "title": "Расходы федерального бюджета",
        "title_en": "Federal Budget Expenditure",
        "importance": 2,
    },
    {
        "code": "budget-deficit",
        "title": "Дефицит/профицит федерального бюджета",
        "title_en": "Federal Budget Deficit/Surplus",
        "importance": 2,
    },
]

CBR_KEY_RATE_MEETINGS_2026 = [
    {"date": date(2026, 2, 13), "has_forecast": True, "summary_date": date(2026, 2, 26)},
    {"date": date(2026, 3, 20), "has_forecast": False, "summary_date": date(2026, 4, 1)},
    {"date": date(2026, 4, 24), "has_forecast": True, "summary_date": date(2026, 5, 12)},
    {"date": date(2026, 6, 19), "has_forecast": False, "summary_date": date(2026, 7, 1)},
    {"date": date(2026, 7, 24), "has_forecast": True, "summary_date": date(2026, 8, 5)},
    {"date": date(2026, 9, 11), "has_forecast": False, "summary_date": date(2026, 9, 23)},
    {"date": date(2026, 10, 23), "has_forecast": True, "summary_date": date(2026, 11, 4)},
    {"date": date(2026, 12, 18), "has_forecast": False, "summary_date": date(2026, 12, 29)},
]

CBR_DAILY_RULES = [
    {
        "code": "usd-rub",
        "title": "Официальный курс доллара США",
        "title_en": "Official USD/RUB Exchange Rate",
        "scheduled_time": None,
        "importance": 1,
        "source_url": "https://www.cbr.ru/currency_base/",
        "rule": "ежедневно по рабочим дням",
    },
    {
        "code": "eur-rub",
        "title": "Официальный курс евро",
        "title_en": "Official EUR/RUB Exchange Rate",
        "scheduled_time": None,
        "importance": 1,
        "source_url": "https://www.cbr.ru/currency_base/",
        "rule": "ежедневно по рабочим дням",
    },
    {
        "code": "cny-rub",
        "title": "Официальный курс юаня",
        "title_en": "Official CNY/RUB Exchange Rate",
        "scheduled_time": None,
        "importance": 1,
        "source_url": "https://www.cbr.ru/currency_base/",
        "rule": "ежедневно по рабочим дням",
    },
    {
        "code": "gold-price",
        "title": "Учётная цена на золото",
        "title_en": "Official Gold Accounting Price",
        "scheduled_time": None,
        "importance": 1,
        "source_url": "https://www.cbr.ru/hd_base/metall/metall_base_new/",
        "rule": "ежедневно по рабочим дням",
    },
    {
        "code": "ruonia",
        "title": "Ставка RUONIA",
        "title_en": "RUONIA Rate",
        "scheduled_time": "15:00",
        "importance": 2,
        "source_url": "https://www.cbr.ru/hd_base/ruonia/",
        "rule": "ежедневно по рабочим дням до 15:00",
    },
]

CBR_EVENT_RULES = [
    (("key-rate",), "Резюме обсуждения ключевой ставки", "Key Rate Discussion Summary", "report", 2,
     (("резюме", "ключев"), ("summary", "key rate"))),
    (("key-rate",), "Заседание ЦБ по ключевой ставке", "CBR Key Rate Decision", "rate_decision", 3,
     (("заседание", "ключев"), ("совет директоров", "ключев"), ("key rate decision",))),
    (("international-reserves",), "Международные резервы РФ", "International Reserves", "data_release", 2,
     (("международн", "резерв"), ("international reserves",))),
    (("m2",), "Денежная масса М2", "Money Supply M2", "data_release", 2,
     (("денежная масса м2",), ("money supply",))),
    (("m0", "m1"), "Денежные агрегаты", "Monetary Aggregates", "data_release", 1,
     (("денежные агрегаты",),)),
    (("business-credit",), "Кредиты юридическим лицам",
     "Corporate Credit", "data_release", 1,
     (("сведения о размещенных средствах", "юридическим лицам"),)),
    (("consumer-credit",), "Кредиты физическим лицам",
     "Household Credit", "data_release", 1,
     (("сведения о размещенных средствах", "физическим лицам"),)),
    (("deposits-business", "deposits-individual"), "Привлечённые средства организаций и физлиц",
     "Deposits of Businesses and Households", "data_release", 1,
     (("сведения о привлеченных средствах",),)),
    ((
        "credit-rate-corp-short",
        "credit-rate-corp-1to3y",
        "credit-rate-corp-over3y",
        "credit-rate-ind-short",
        "credit-rate-ind-1to3y",
        "credit-rate-ind-over3y",
        "deposit-rate",
    ), "Средневзвешенные ставки по кредитам и депозитам",
     "Weighted Average Credit and Deposit Rates", "data_release", 1,
     (("средневзвешенные", "ставки", "кредитам", "депозитам"),)),
    (("mortgage-rate",), "Показатели ипотечного жилищного кредитования",
     "Mortgage Lending Market Indicators", "data_release", 1,
     (("показатели рынка жилищного", "кредитования"),)),
    (("auto-loan-rate",), "Показатели рынка автокредитования",
     "Auto Loan Market Indicators", "data_release", 1,
     (("автокредит",),)),
    (("exports", "imports", "trade-balance"), "Внешняя торговля товарами",
     "External Trade in Goods", "data_release", 2,
     (("внешняя торговля", "товарами"),)),
    (("services-exports", "services-imports"), "Внешняя торговля услугами",
     "External Trade in Services", "data_release", 1,
     (("внешняя торговля", "услугами по месяцам"),)),
    (("current-account",), "Счёт текущих операций платёжного баланса", "Current Account", "data_release", 2,
     (("счет текущих операций",), ("счёт текущих операций",), ("current account",))),
    (("external-debt",), "Внешний долг РФ", "External Debt of the Russian Federation", "data_release", 1,
     (("внешний долг российской федерации",), ("external debt",))),
    (("fdi-net",), "Прямые инвестиции РФ", "Foreign Direct Investment", "data_release", 1,
     (("прямые инвестиции", "российской федерации"),)),
    (("key-rate",), "Ключевая ставка Банка России", "Bank of Russia Key Rate", "data_release", 3,
     (("ключевая ставка",), ("key rate",))),
]


async def refresh_official_calendar(
    *,
    months_ahead: int = 12,
    today: date | None = None,
    db: AsyncSession | None = None,
) -> int:
    today = today or date.today()
    candidates = build_rule_candidates(today=today, months_ahead=months_ahead)
    candidates.extend(build_cbr_daily_rule_candidates(today=today, months_ahead=months_ahead))
    candidates.extend(build_cbr_monetary_policy_candidates(today=today, months_ahead=months_ahead))
    candidates.extend(fetch_cbr_calendar_candidates(today=today, months_ahead=months_ahead))

    async def _persist(session: AsyncSession) -> int:
        from app.services.calendar_sources.enrichment import (
            enrich_events_from_indicator_data,
            filter_speculative_rosstat_monthly,
            prune_persisted_speculative_rosstat_monthly,
        )

        filtered = await filter_speculative_rosstat_monthly(session, candidates)
        changed = await upsert_calendar_candidates(session, filtered)
        await prune_persisted_speculative_rosstat_monthly(session)
        await enrich_events_from_indicator_data(session)
        return changed

    if db is not None:
        return await _persist(db)
    async with async_session_factory() as session:
        return await _persist(session)


def build_rule_candidates(*, today: date, months_ahead: int) -> list[CalendarCandidate]:
    candidates: list[CalendarCandidate] = []
    candidates.extend(build_rosstat_rule_candidates(today=today, months_ahead=months_ahead))
    candidates.extend(build_minfin_rule_candidates(today=today, months_ahead=months_ahead))
    return candidates


def build_rosstat_rule_candidates(*, today: date, months_ahead: int) -> list[CalendarCandidate]:
    candidates: list[CalendarCandidate] = []
    horizon = today + timedelta(days=months_ahead * 31)
    cutoff = today - timedelta(days=14)

    for ref_year, ref_month in _iter_reference_months(today, months_ahead):
        release_year, release_month = next_month(ref_year, ref_month)
        if not calendar_source_url(release_year):
            continue
        for rule in ROSSTAT_MONTHLY_RULES:
            scheduled = nth_working_day(release_year, release_month, rule["nth_workday"])
            if not (cutoff <= scheduled <= horizon):
                continue
            candidates.append(CalendarCandidate(
                event_key=stable_key("rosstat", rule["code"], f"{ref_year}-{ref_month:02d}"),
                title=rule["title"],
                title_en=rule["title_en"],
                event_type="data_release",
                source="rosstat",
                indicator_code=rule["code"],
                scheduled_date=scheduled,
                date_confidence="official_rule",
                reference_period=_month_ref(ref_month, ref_year),
                importance=rule["importance"],
                source_url=rule["source_url"],
                description=_event_description(rule["code"], f"Плановая дата публикации Росстата: {rule['rule']}."),
                metadata={
                    "rule": rule["rule"],
                    "working_calendar_source": calendar_source_url(release_year),
                },
            ))

    for rule in ROSSTAT_GDP_RULES:
        for q_end in _quarter_ends(today.year - 1, today.year + 2):
            scheduled = q_end + timedelta(days=rule["lag_days"])
            if not (cutoff <= scheduled <= horizon):
                continue
            q = (q_end.month - 1) // 3 + 1
            candidates.append(CalendarCandidate(
                event_key=stable_key("rosstat", rule["code"], f"{q_end.year}-q{q}"),
                title=rule["title"],
                title_en=rule["title_en"],
                event_type="data_release",
                source="rosstat",
                indicator_code=rule["code"],
                scheduled_date=scheduled,
                date_confidence="official_rule",
                reference_period=f"Q{q} {q_end.year}",
                importance=rule["importance"],
                source_url=ROSSTAT_GDP_URL,
                description=_event_description(
                    rule["code"],
                    f"Оценка Росстата, публикуется ориентировочно через {rule['lag_days']} дней после окончания квартала.",
                ),
                metadata={"rule": f"quarter_end + {rule['lag_days']} days"},
            ))

    return candidates


def build_minfin_rule_candidates(*, today: date, months_ahead: int) -> list[CalendarCandidate]:
    candidates: list[CalendarCandidate] = []
    horizon = today + timedelta(days=months_ahead * 31)
    cutoff = today - timedelta(days=14)
    for ref_year, ref_month in _iter_reference_months(today, months_ahead):
        release_year, release_month = next_month(ref_year, ref_month)
        if not calendar_source_url(release_year):
            continue
        scheduled = nth_working_day(release_year, release_month, 14)
        if not (cutoff <= scheduled <= horizon):
            continue
        for rule in MINFIN_RULES:
            candidates.append(CalendarCandidate(
                event_key=stable_key("minfin", rule["code"], f"{ref_year}-{ref_month:02d}"),
                title=rule["title"],
                title_en=rule["title_en"],
                event_type="data_release",
                source="minfin",
                indicator_code=rule["code"],
                scheduled_date=scheduled,
                date_confidence="official_rule",
                reference_period=_month_ref(ref_month, ref_year),
                importance=rule["importance"],
                source_url=MINFIN_SCHEDULE_URL,
                description=_event_description(
                    rule["code"],
                    "Оперативные данные Минфина России об исполнении федерального бюджета; плановая дата — 14-й рабочий день месяца.",
                ),
                metadata={
                    "rule": "14-й рабочий день месяца, следующего за отчетным",
                    "working_calendar_source": calendar_source_url(release_year),
                },
            ))
    return candidates


def build_cbr_monetary_policy_candidates(*, today: date, months_ahead: int) -> list[CalendarCandidate]:
    candidates: list[CalendarCandidate] = []
    horizon = today + timedelta(days=months_ahead * 31)
    cutoff = today - timedelta(days=14)
    for meeting in CBR_KEY_RATE_MEETINGS_2026:
        meeting_date = meeting["date"]
        if cutoff <= meeting_date <= horizon:
            label = "опорное" if meeting["has_forecast"] else "промежуточное"
            candidates.append(CalendarCandidate(
                event_key=stable_key("cbr", "key-rate-decision", meeting_date.isoformat()),
                title=f"Заседание ЦБ по ключевой ставке ({label})",
                title_en=f"CBR Key Rate Decision ({'core' if meeting['has_forecast'] else 'interim'})",
                event_type="rate_decision",
                source="cbr",
                indicator_code="key-rate",
                scheduled_date=meeting_date,
                scheduled_time="13:30",
                date_confidence="official_explicit",
                importance=3,
                source_url=CBR_MONETARY_POLICY_CALENDAR_URL,
                source_event_uid=f"cbr-key-rate-decision-{meeting_date.isoformat()}",
                description=_event_description(
                    "key-rate",
                    "Пресс-релиз в 13:30 МСК, пресс-конференция в 15:00 МСК."
                    + (" С публикацией среднесрочного прогноза." if meeting["has_forecast"] else ""),
                ),
                metadata={
                    "calendar_url": CBR_MONETARY_POLICY_CALENDAR_URL,
                    "has_forecast": meeting["has_forecast"],
                    "schedule_year": 2026,
                },
            ))

        summary_date = meeting["summary_date"]
        if cutoff <= summary_date <= horizon:
            candidates.append(CalendarCandidate(
                event_key=stable_key("cbr", "key-rate-summary", summary_date.isoformat()),
                title="Резюме обсуждения ключевой ставки",
                title_en="Key Rate Discussion Summary",
                event_type="report",
                source="cbr",
                indicator_code="key-rate",
                scheduled_date=summary_date,
                date_confidence="official_explicit",
                importance=2,
                source_url=CBR_MONETARY_POLICY_CALENDAR_URL,
                source_event_uid=f"cbr-key-rate-summary-{summary_date.isoformat()}",
                description=_event_description(
                    "key-rate",
                    "Публикация резюме обсуждения ключевой ставки Советом директоров Банка России.",
                ),
                metadata={
                    "calendar_url": CBR_MONETARY_POLICY_CALENDAR_URL,
                    "schedule_year": 2026,
                },
            ))
    return candidates


def build_cbr_daily_rule_candidates(*, today: date, months_ahead: int) -> list[CalendarCandidate]:
    candidates: list[CalendarCandidate] = []
    horizon = today + timedelta(days=months_ahead * 31)
    cutoff = today - timedelta(days=14)
    cursor = cutoff
    while cursor <= horizon:
        source_url = calendar_source_url(cursor.year)
        if source_url and is_working_day(cursor):
            for rule in CBR_DAILY_RULES:
                candidates.append(CalendarCandidate(
                    event_key=stable_key("cbr", rule["code"], cursor.isoformat()),
                    title=rule["title"],
                    title_en=rule["title_en"],
                    event_type="data_release",
                    source="cbr",
                    indicator_code=rule["code"],
                    scheduled_date=cursor,
                    scheduled_time=rule["scheduled_time"],
                    date_confidence="official_rule",
                    importance=rule["importance"],
                    source_url=rule["source_url"],
                    source_event_uid=f"cbr-{rule['code']}-{cursor.isoformat()}",
                    description=_event_description(rule["code"], "Публикуется по рабочим дням."),
                    metadata={
                        "rule": rule["rule"],
                        "calendar_url": CBR_CALENDAR_PAGE,
                        "working_calendar_source": source_url,
                    },
                ))
        cursor += timedelta(days=1)
    return candidates


def fetch_cbr_calendar_candidates(*, today: date, months_ahead: int) -> list[CalendarCandidate]:
    try:
        page = requests.get(CBR_CALENDAR_PAGE, timeout=20)
        page.raise_for_status()
        ics_url = _extract_cbr_ics_url(page.text) or CBR_ICS_URL
        response = requests.get(ics_url, timeout=20)
        response.raise_for_status()
        response.encoding = "utf-8"
        return parse_cbr_ics(response.text, source_url=ics_url, today=today, months_ahead=months_ahead)
    except Exception:
        logger.exception("Failed to fetch CBR official calendar")
        return []


def parse_cbr_ics(
    text: str,
    *,
    source_url: str,
    today: date,
    months_ahead: int,
) -> list[CalendarCandidate]:
    horizon = today + timedelta(days=months_ahead * 31)
    cutoff = today - timedelta(days=14)
    candidates: list[CalendarCandidate] = []
    for event in _parse_ics_events(text):
        scheduled = _parse_ics_date(event.get("DTSTART"))
        if not scheduled or not (cutoff <= scheduled <= horizon):
            continue
        blob = " ".join([
            event.get("SUMMARY", ""),
            event.get("DESCRIPTION", ""),
            event.get("URL", ""),
        ]).lower()
        matches = _match_cbr_events(blob)
        if not matches:
            continue
        uid = _compact_source_uid(event.get("UID") or stable_key(event.get("SUMMARY", ""), scheduled.isoformat()))
        scheduled_time = _parse_ics_time(event.get("DTSTART"))
        for code, title, title_en, event_type, importance in matches:
            candidates.append(CalendarCandidate(
                event_key=stable_key("cbr", code, uid, scheduled.isoformat()),
                title=title,
                title_en=title_en,
                event_type=event_type,
                source="cbr",
                indicator_code=code,
                scheduled_date=scheduled,
                scheduled_time=scheduled_time,
                date_confidence="official_explicit",
                reference_period=_reference_from_text(event.get("SUMMARY", "") + " " + event.get("DESCRIPTION", "")),
                importance=importance,
                source_url=event.get("URL") or source_url,
                source_event_uid=uid,
                description=_event_description(code) or event.get("SUMMARY"),
                metadata={"calendar_url": source_url, "raw_summary": event.get("SUMMARY")},
            ))
    return candidates


def _extract_cbr_ics_url(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "vCalendar.ics" in href:
            if href.startswith("http"):
                return href
            return "https://www.cbr.ru" + href
    return None


def _parse_ics_events(text: str) -> list[dict[str, str]]:
    unfolded: list[str] = []
    for raw in text.splitlines():
        if raw.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += raw[1:]
        else:
            unfolded.append(raw.rstrip("\r"))

    events: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in unfolded:
        if line == "BEGIN:VEVENT":
            current = {}
            continue
        if line == "END:VEVENT":
            if current is not None:
                events.append(current)
            current = None
            continue
        if current is None or ":" not in line:
            continue
        key, value = line.split(":", 1)
        name = key.split(";", 1)[0].upper()
        current[name] = _clean_ics_text(value)
    return events


def _clean_ics_text(value: str) -> str:
    return (
        value
        .replace("\\n", " ")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .strip()
    )


def _parse_ics_date(value: str | None) -> date | None:
    if not value:
        return None
    compact = value.split("T", 1)[0]
    try:
        return datetime.strptime(compact[:8], "%Y%m%d").date()
    except ValueError:
        return None


def _parse_ics_time(value: str | None) -> str | None:
    if not value or "T" not in value:
        return None
    part = value.split("T", 1)[1]
    if len(part) < 4:
        return None
    return f"{part[:2]}:{part[2:4]}"


def _compact_source_uid(value: str) -> str:
    cleaned = value.strip()
    if len(cleaned) <= 120:
        return cleaned
    return "sha256:" + hashlib.sha256(cleaned.encode("utf-8")).hexdigest()


def _match_cbr_events(blob: str) -> list[tuple[str, str, str, str, int]]:
    matches: list[tuple[str, str, str, str, int]] = []
    for codes, title, title_en, event_type, importance, keyword_groups in CBR_EVENT_RULES:
        if any(all(keyword in blob for keyword in group) for group in keyword_groups):
            for code in codes:
                matches.append((code, title, title_en, event_type, importance))
    return matches


def _reference_from_text(text: str) -> str | None:
    match = re.search(r"((?:январ|феврал|март|апрел|ма[йя]|июн|июл|август|сентябр|октябр|ноябр|декабр)[а-я.\-]*\s+20\d{2})", text, re.I)
    if match:
        return match.group(1)
    match = re.search(r"(Q[1-4]\s+20\d{2}|[IVX]+\s+квартал\s+20\d{2})", text, re.I)
    if match:
        return match.group(1)
    match = re.search(r"(\d{2}\.\d{2}\.20\d{2})", text)
    if match:
        return match.group(1)
    return None


def _iter_reference_months(today: date, months_ahead: int):
    cursor = today.replace(day=1) - timedelta(days=1)
    cursor = cursor.replace(day=1)
    end = (today + timedelta(days=(months_ahead + 1) * 31)).replace(day=1)
    while cursor <= end:
        yield cursor.year, cursor.month
        cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)


def _quarter_ends(start_year: int, end_year: int) -> list[date]:
    values: list[date] = []
    for year in range(start_year, end_year + 1):
        values.extend([
            date(year, 3, 31),
            date(year, 6, 30),
            date(year, 9, 30),
            date(year, 12, 31),
        ])
    return values


def _month_ref(month: int, year: int) -> str:
    return f"{MONTH_NAMES_RU[month]} {year}"

from __future__ import annotations

import logging
import re
import hashlib
from datetime import date, datetime, timedelta

import requests
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

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
from app.services.calendar_sources.cbr_key_rate import CBR_MONETARY_POLICY_CALENDAR_URL  # noqa: E402
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


# Москва живёт по UTC+3 без перехода на летнее время с 26.10.2014.
MSK_UTC_OFFSET = timedelta(hours=3)


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
    "ipi": "Индекс промышленного производства показывает, как меняется выпуск в добыче, обработке, энергетике и водоснабжении.",
    "unemployment": "Доля рабочей силы, не имеющей работы, но активно ищущей её, по методологии Международной организации труда.",
    "wages-nominal": "Среднемесячная начисленная заработная плата работников организаций до вычета налогов.",
    "retail-trade": "Стоимость товаров, проданных населению через розничную сеть, — индикатор потребительского спроса.",
    "housing-commissioned": "Площадь введённых в эксплуатацию жилых домов — индикатор активности в жилищном строительстве.",
    "ppi": "Индекс цен производителей отражает изменение отпускных цен промышленных предприятий и обычно опережает потребительскую инфляцию.",
    "construction-work": "Объём работ, выполненных по виду деятельности «Строительство», в стоимостном выражении.",
    "gdp-nominal": "Совокупная рыночная стоимость всех конечных товаров и услуг, произведённых в стране за квартал, в текущих ценах.",
    "gdp-real": "Объём произведённых товаров и услуг в сопоставимых ценах, очищенный от влияния инфляции.",
    "budget-revenue": "Поступления в федеральный бюджет: налоговые и неналоговые доходы за месяц.",
    "budget-expenditure": "Фактические расходы федерального бюджета за месяц.",
    "budget-deficit": "Разница между доходами и расходами федерального бюджета: профицит при превышении доходов, дефицит при их нехватке.",
    "usd-rub": "Официальный курс доллара США к рублю, устанавливаемый Банком России.",
    "eur-rub": "Официальный курс евро к рублю, устанавливаемый Банком России.",
    "cny-rub": "Официальный курс китайского юаня к рублю, устанавливаемый Банком России.",
    "gold-price": "Учётная цена на золото, устанавливаемая Банком России на основе мировых котировок.",
    "ruonia": "Средняя ставка, по которой крупнейшие банки одалживают друг другу рубли на один день.",
    "key-rate": "Ключевая ставка — основной инструмент денежно-кредитной политики Банка России, определяющий стоимость денег в экономике.",
    "international-reserves": "Высоколиквидные иностранные активы государства: валюта, золото и резервная позиция в международных финансовых институтах.",
    "m2": "Денежная масса М2: наличные деньги и рубли на счетах организаций и населения.",
    "m1": "Денежная масса М1: наличные деньги и средства на счетах, которые можно снять в любой момент.",
    "m0": "Денежная масса М0: наличные деньги в обращении вне банков.",
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
    "exports": "Стоимость товаров, вывезенных из России за месяц.",
    "imports": "Стоимость товаров, ввезённых в Россию за месяц.",
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

# Даты заседаний по ключевой ставке читаются со страницы ЦБ (calendar_sources/cbr_key_rate.py);
# там же запасной список на случай недоступности страницы.

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
    # Ежемесячная оценка платёжного баланса (с 14.11.2026): ЦБ публикует её около 15-го числа,
    # это главная оперативная цифра по счёту текущих операций между квартальными выпусками.
    (("current-account",), "Оценка платёжного баланса", "Balance of Payments Estimate", "data_release", 2,
     (("платежный баланс – оценка",), ("оценка платежного баланса российской федерации",))),
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
    from app.services.display import today_msk

    today = today or today_msk()
    collected = await run_in_threadpool(_collect_calendar_feeds, today, months_ahead)
    candidates = collected.candidates

    async def _persist(session: AsyncSession) -> int:
        from app.services.calendar_sources.common import sweep_unseen_feed_events
        from app.services.calendar_sources.enrichment import (
            confirm_releases_from_loads,
            enrich_events_from_indicator_data,
            filter_speculative_rosstat_monthly,
            prune_persisted_speculative_rosstat_monthly,
        )

        from app.services.calendar_sources.common import prune_legacy_keyless_estimates

        await prune_legacy_keyless_estimates(session)
        filtered = await filter_speculative_rosstat_monthly(session, candidates)
        changed = await upsert_calendar_candidates(session, filtered)
        start = today - timedelta(days=14)
        end = today + timedelta(days=months_ahead * 31)
        for feed in collected.complete_feeds:
            feed_candidates = [c for c in candidates if (c.metadata or {}).get("feed") == feed]
            seen = {c.event_key for c in feed_candidates}
            feed_end = end
            if feed in ("rosstat_plan", "rosstat_oper"):
                # Граница — конец последнего прочитанного годового графика: если файл следующего
                # года не скачался, его ранее сохранённые события не считаются исчезнувшими.
                years = [int((c.metadata or {}).get("schedule_year") or 0) for c in feed_candidates]
                feed_end = min(end, date(max(years), 12, 31)) if years and max(years) else start
            await sweep_unseen_feed_events(session, feed=feed, seen_keys=seen, start=start, end=feed_end)
        from app.services.calendar_sources.common import repair_legacy_cbr_ics_times

        await repair_legacy_cbr_ics_times(session)
        await prune_persisted_speculative_rosstat_monthly(session)
        await enrich_events_from_indicator_data(session)
        await confirm_releases_from_loads(session)
        from app.services.calendar_sources.enrichment import fill_event_forecasts
        from app.services.calendar_sources.world_enrichment import enrich_world_events

        await enrich_world_events(session)
        await fill_event_forecasts(session)
        return changed

    if db is not None:
        return await _persist(db)
    async with async_session_factory() as session:
        return await _persist(session)


class CollectedCalendar:
    """Кандидаты всех источников и список источников, ответивших полным списком."""

    def __init__(self, candidates: list[CalendarCandidate], complete_feeds: list[str]):
        self.candidates = candidates
        self.complete_feeds = complete_feeds


def _collect_calendar_candidates(today: date, months_ahead: int) -> list[CalendarCandidate]:
    """Synchronous source HTTP/parsing must not block the serving event loop."""
    return _collect_calendar_feeds(today, months_ahead).candidates


def _collect_calendar_feeds(today: date, months_ahead: int) -> CollectedCalendar:
    from app.services.calendar_sources.cbr_key_rate import fetch_key_rate_calendar

    complete: list[str] = []
    candidates = build_rule_candidates(today=today, months_ahead=months_ahead)
    candidates.extend(build_cbr_daily_rule_candidates(today=today, months_ahead=months_ahead))

    meetings = fetch_key_rate_calendar()
    if meetings:
        complete.append("cbr_key_rate")
    candidates.extend(build_cbr_monetary_policy_candidates(
        today=today, months_ahead=months_ahead, meetings=meetings,
    ))

    cbr_ics = fetch_cbr_calendar_candidates(today=today, months_ahead=months_ahead)
    if cbr_ics:
        complete.append("cbr_ics")
    candidates.extend(cbr_ics)

    plan = fetch_rosstat_plan_candidates_safe(today=today, months_ahead=months_ahead)
    if plan:
        complete.append("rosstat_plan")
    candidates.extend(plan)

    oper = fetch_rosstat_oper_candidates_safe(today=today, months_ahead=months_ahead)
    if oper:
        complete.append("rosstat_oper")
    candidates.extend(oper)

    from app.services.calendar_sources.world_calendar import fetch_world_candidates

    for feed, world in fetch_world_candidates(today=today, months_ahead=months_ahead).items():
        complete.append(feed)
        candidates.extend(world)

    candidates = prefer_explicit_plan_candidates(candidates)
    return CollectedCalendar(candidates, complete)


def build_rule_candidates(*, today: date, months_ahead: int) -> list[CalendarCandidate]:
    candidates: list[CalendarCandidate] = []
    candidates.extend(build_rosstat_rule_candidates(today=today, months_ahead=months_ahead))
    candidates.extend(build_minfin_rule_candidates(today=today, months_ahead=months_ahead))
    return candidates


def prefer_explicit_plan_candidates(candidates: list[CalendarCandidate]) -> list[CalendarCandidate]:
    """Вытеснить rule-оценки дат официальными датами плана публикаций.

    Для одного выпуска Росстата конвейер собирает два кандидата: rule
    («N-й рабочий день следующего месяца», приблизительно) и explicit из
    docx-графика (точная дата). На витрине должен остаться один — explicit:
    точнее дата, выше класс provenance, и не создаётся второго ряда-дубликата
    по (indicator, reference_period). Сопоставление — по (indicator_code,
    reference_period) среди rosstat-кандидатов; события, чей ref-период
    парсер плана не распознал (None), не участвуют в вытеснении, чтобы не
    уронить rule-строку без замены.
    """
    explicit_refs: set[tuple[str, str]] = set()
    for c in candidates:
        if (
            c.source == "rosstat"
            and c.date_confidence == "official_explicit"
            and c.indicator_code
            and c.reference_period
        ):
            explicit_refs.add((c.indicator_code, c.reference_period))
    if not explicit_refs:
        return candidates
    kept = []
    for c in candidates:
        is_shadowed_rule = (
            c.source == "rosstat"
            and c.date_confidence in ("official_rule", "estimated")
            and c.indicator_code is not None
            and c.reference_period is not None
            and (c.indicator_code, c.reference_period) in explicit_refs
        )
        if not is_shadowed_rule:
            kept.append(c)
    return kept


def fetch_rosstat_plan_candidates_safe(*, today: date, months_ahead: int) -> list[CalendarCandidate]:
    """Кандидаты официального графика публикаций Росстата (official_explicit).

    Включено по умолчанию после сверки с живым документом: источник —
    docx «График размещения срочных информаций и справок» со страницы «План
    выпуска публикаций» rosstat.gov.ru/publications-plans. Включение —
    CALENDAR_ROSSTAT_PLAN_ENABLED=true в .env. Прогон сети только при
    включённом флаге; ошибка источника не ломает синхронизацию календаря.
    """
    from app.config import settings

    if not settings.calendar_rosstat_plan_enabled:
        return []
    from app.services.calendar_sources.rosstat_plan import fetch_rosstat_plan_candidates

    try:
        return fetch_rosstat_plan_candidates(today=today, months_ahead=months_ahead)
    except Exception:
        logger.exception("Rosstat plan candidates fetch failed")
        return []


def fetch_rosstat_oper_candidates_safe(*, today: date, months_ahead: int) -> list[CalendarCandidate]:
    """Даты доклада «Социально-экономическое положение России» и «Краткосрочных показателей»."""
    from app.config import settings

    if not settings.calendar_rosstat_plan_enabled:
        return []
    from app.services.calendar_sources.rosstat_oper_plan import fetch_rosstat_oper_candidates

    try:
        return fetch_rosstat_oper_candidates(today=today, months_ahead=months_ahead)
    except Exception:
        logger.exception("Rosstat operative schedule candidates fetch failed")
        return []


def build_rosstat_rule_candidates(*, today: date, months_ahead: int) -> list[CalendarCandidate]:
    candidates: list[CalendarCandidate] = []
    horizon = today + timedelta(days=months_ahead * 31)
    cutoff = today - timedelta(days=14)

    for ref_year, ref_month in _iter_reference_months(today, months_ahead):
        release_year, release_month = next_month(ref_year, ref_month)
        if not calendar_source_url(release_year):
            continue
        for rule in ROSSTAT_MONTHLY_RULES:
            try:
                scheduled = nth_working_day(release_year, release_month, rule["nth_workday"])
            except ValueError:
                # В январе 2027 года 15 рабочих дней: «18-й рабочий день» не существует. Оценка
                # по правилу скрыта с витрины — пропускаем, а не роняем весь проход календаря.
                continue
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
                date_confidence="estimated",
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
                date_confidence="estimated",
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
        try:
            scheduled = nth_working_day(release_year, release_month, 14)
        except ValueError:
            continue
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
                # Срок «не позднее» по опубликованному графику Минфина (minfin.gov.ru/ru/statistics/schedule,
                # сверено 14.11.2026); данные часто выходят раньше — выход подтверждает наша загрузка.
                date_confidence="official_deadline",
                reference_period=_month_ref(ref_month, ref_year),
                importance=rule["importance"],
                source_url=MINFIN_SCHEDULE_URL,
                source_event_uid=f"minfin-{rule['code']}-{ref_year}-{ref_month:02d}",
                description=_event_description(
                    rule["code"],
                    "Оперативные данные Минфина России об исполнении федерального бюджета: не позднее 14-го рабочего дня месяца, часто раньше.",
                ),
                metadata={
                    "feed": "minfin_rule",
                    "deadline": True,
                    "rule": "14-й рабочий день месяца, следующего за отчетным",
                    "working_calendar_source": calendar_source_url(release_year),
                },
            ))
    return candidates


def build_cbr_monetary_policy_candidates(
    *,
    today: date,
    months_ahead: int,
    meetings: list | tuple | None = None,
) -> list[CalendarCandidate]:
    """Заседания и резюме по ключевой ставке.

    ``meetings`` — разобранная страница cbr.ru/dkp/cal_mp/; без неё — запасной список
    ``cbr_key_rate.FALLBACK_MEETINGS``. Ключ резюме привязан к заседанию, а не к своей дате:
    если ЦБ сдвинет резюме, событие переедет с отметкой о переносе, а не раздвоится.
    """
    from app.services.calendar_sources.cbr_key_rate import FALLBACK_MEETINGS

    source_meetings = list(meetings) if meetings else list(FALLBACK_MEETINGS)
    candidates: list[CalendarCandidate] = []
    horizon = today + timedelta(days=months_ahead * 31)
    cutoff = today - timedelta(days=14)
    for meeting in source_meetings:
        meeting_date = meeting.date
        has_forecast = meeting.has_forecast
        if cutoff <= meeting_date <= horizon:
            label = "опорное" if has_forecast else "промежуточное"
            candidates.append(CalendarCandidate(
                event_key=stable_key("cbr", "key-rate-decision", meeting_date.isoformat()),
                title=f"Заседание ЦБ по ключевой ставке ({label})",
                title_en=f"CBR Key Rate Decision ({'core' if has_forecast else 'interim'})",
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
                    + (" С публикацией среднесрочного прогноза." if has_forecast else ""),
                ),
                metadata={
                    "feed": "cbr_key_rate",
                    "calendar_url": CBR_MONETARY_POLICY_CALENDAR_URL,
                    "has_forecast": has_forecast,
                    "schedule_year": meeting_date.year,
                },
            ))

        summary_date = meeting.summary_date
        if summary_date and cutoff <= summary_date <= horizon:
            candidates.append(CalendarCandidate(
                event_key=stable_key("cbr", "key-rate-summary", "meeting", meeting_date.isoformat()),
                title="Резюме обсуждения ключевой ставки",
                title_en="Key Rate Discussion Summary",
                event_type="report",
                source="cbr",
                indicator_code="key-rate",
                scheduled_date=summary_date,
                scheduled_time=None,
                date_confidence="official_explicit",
                importance=2,
                source_url=CBR_MONETARY_POLICY_CALENDAR_URL,
                source_event_uid=f"cbr-key-rate-summary-{summary_date.isoformat()}",
                description=_event_description(
                    "key-rate",
                    "Публикация резюме обсуждения ключевой ставки Советом директоров Банка России.",
                ),
                metadata={
                    "feed": "cbr_key_rate",
                    "calendar_url": CBR_MONETARY_POLICY_CALENDAR_URL,
                    "meeting_date": meeting_date.isoformat(),
                    "schedule_year": summary_date.year,
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
    """Файл календаря ЦБ → по одному событию на (показатель, тип, дату).

    14.11.2026: время в файле ЦБ записано в UTC (``DTSTART:20261119T130000Z``), а сайт
    подписывал его «МСК» — международные резервы стояли на 13:00 вместо 16:00 МСК, ставки
    по кредитам на 07:00 вместо 10:00. Теперь дата и время переводятся в московское время.
    В один день ЦБ кладёт несколько таблиц одной темы (внешний долг — 4 записи); раньше каждая
    давала свой ключ события и строки перетирали друг друга по естественному ключу базы.
    Теперь одна запись на показатель и день, время — самое раннее, ключ не зависит от UID таблицы.
    """
    horizon = today + timedelta(days=months_ahead * 31)
    cutoff = today - timedelta(days=14)
    chosen: dict[tuple[str, str, date], CalendarCandidate] = {}
    for event in _parse_ics_events(text):
        moment = _parse_ics_moment_msk(event.get("DTSTART"))
        if moment is None:
            continue
        scheduled, scheduled_time = moment
        if not (cutoff <= scheduled <= horizon):
            continue
        blob = " ".join([
            event.get("SUMMARY", ""),
            event.get("DESCRIPTION", ""),
            event.get("URL", ""),
        ]).lower()
        matches = _match_cbr_events(blob)
        if not matches:
            continue
        raw_uid = _compact_source_uid(event.get("UID") or stable_key(event.get("SUMMARY", ""), scheduled.isoformat()))
        seen_codes: set[str] = set()
        for code, title, title_en, event_type, importance in matches:
            # Первое совпавшее правило для показателя — главное (порядок CBR_EVENT_RULES значим).
            if code in seen_codes:
                continue
            seen_codes.add(code)
            slot = (code, event_type, scheduled)
            current = chosen.get(slot)
            if current is not None and (current.scheduled_time or "99:99") <= (scheduled_time or "99:99"):
                continue
            chosen[slot] = CalendarCandidate(
                event_key=stable_key("cbr", "ics", code, event_type, scheduled.isoformat()),
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
                source_event_uid=raw_uid,
                description=_event_description(code) or event.get("SUMMARY"),
                metadata={
                    "feed": "cbr_ics",
                    "calendar_url": source_url,
                    "raw_summary": event.get("SUMMARY"),
                },
            )
    return sorted(chosen.values(), key=lambda c: (c.scheduled_date, c.indicator_code or "", c.event_type))


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


def _parse_ics_moment_msk(value: str | None) -> tuple[date, str | None] | None:
    """DTSTART → (дата, «ЧЧ:ММ») по Москве. ``Z`` — UTC, сдвиг +3 ч; без ``Z`` — время уже местное."""
    if not value:
        return None
    raw = value.strip()
    if "T" not in raw:
        day = _parse_ics_date(raw)
        return (day, None) if day else None
    try:
        moment = datetime.strptime(raw.rstrip("Z")[:15], "%Y%m%dT%H%M%S")
    except ValueError:
        day = _parse_ics_date(raw)
        return (day, _parse_ics_time(raw)) if day else None
    if raw.endswith("Z"):
        moment = moment + MSK_UTC_OFFSET
    return moment.date(), moment.strftime("%H:%M")


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

"""Ежемесячные выпуски ЦБ привязаны к месячным рядам (20.11.2026).

Внешняя торговля товарами и услугами выходит каждый месяц, а стояла на квартальных рядах платёжного
баланса: новой точки не приходило, и у людей выпуск висел «ждём данные». Теперь месячные выпуски
идут на месячные ряды ЦБ, квартальные — на выпуск стандартных компонент. Оценка платёжного баланса
идёт без ряда (помесячной истории у ЦБ нет), краткосрочный долг и комментарии — не выпуски наших рядов.
"""
import asyncio
from datetime import date, datetime

from sqlalchemy import select

from app.models import EconomicEvent, Indicator, IndicatorData

# Записи из файла календаря ЦБ (vCalendar.ics, снят 20.11.2026), время в UTC.
ICS = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:g1
DTSTART:20261111T130000Z
SUMMARY:Внешняя торговля Российской Федерации товарами (по методологии платежного баланса)*
END:VEVENT
BEGIN:VEVENT
UID:s1
DTSTART:20261116T130000Z
SUMMARY:Внешняя торговля Российской Федерации услугами по месяцам
END:VEVENT
BEGIN:VEVENT
UID:b1
DTSTART:20261116T130000Z
SUMMARY:Платежный баланс – оценка
END:VEVENT
BEGIN:VEVENT
UID:b2
DTSTART:20261116T130000Z
SUMMARY:Оценка платежного баланса Российской Федерации
END:VEVENT
BEGIN:VEVENT
UID:b3
DTSTART:20261116T070000Z
SUMMARY:Информационно-аналитический комментарий «Оценка платежного баланса Российской Федерации»
END:VEVENT
BEGIN:VEVENT
UID:d1
DTSTART:20261113T070000Z
SUMMARY:Краткосрочный внешний долг Российской Федерации по остаточному сроку до погашения
END:VEVENT
BEGIN:VEVENT
UID:q1
DTSTART:20261230T130000Z
SUMMARY:Платежный баланс Российской Федерации. Cтандартные компоненты*
END:VEVENT
BEGIN:VEVENT
UID:q2
DTSTART:20261230T130000Z
SUMMARY:Внешний долг Российской Федерации
END:VEVENT
BEGIN:VEVENT
UID:f1
DTSTART:20270120T070000Z
SUMMARY:Прямые инвестиции Российской Федерации по принципу активов/пассивов и принципу направленности
END:VEVENT
END:VCALENDAR
"""


def _parse():
    from app.services.calendar_sources.official_calendar import parse_cbr_ics

    return parse_cbr_ics(ICS, source_url="https://www.cbr.ru/x.ics", today=date(2026, 11, 14), months_ahead=3)


def test_monthly_cbr_releases_go_to_monthly_series_and_quarterly_to_standard_components():
    by_day: dict[date, set] = {}
    for e in _parse():
        by_day.setdefault(e.scheduled_date, set()).add(e.indicator_code)
    assert by_day[date(2026, 11, 11)] == {"exports-monthly", "imports-monthly", "trade-balance-monthly"}
    assert by_day[date(2026, 11, 16)] == {"services-exports-monthly", "services-imports-monthly", None}
    assert by_day[date(2026, 12, 30)] == {
        "exports", "imports", "trade-balance", "services-exports", "services-imports", "fdi-net", "external-debt"}
    # Таблица прямых инвестиций по принципу активов/пассивов не обновляет наш ряд — событие без ряда.
    assert by_day[date(2027, 1, 20)] == {None}
    # Краткосрочный долг по остаточному сроку не меняет общий внешний долг — события нет.
    assert date(2026, 11, 13) not in by_day


def test_balance_of_payments_estimate_is_one_unbound_event_at_data_time():
    estimate = [e for e in _parse() if e.title == "Оценка платёжного баланса"]
    assert len(estimate) == 1
    ev = estimate[0]
    assert ev.indicator_code is None
    assert ev.event_key == "cbr:ics:balance-of-payments-estimate:data_release:2026-11-16"
    # Комментарий выходит в 10:00 и раньше сдвигал на себя время выпуска; данные — в 16:00 МСК.
    assert ev.scheduled_time == "16:00"
    assert ev.description.startswith("Первая оценка Банка России")


def test_new_calendar_texts_have_english_twins():
    from app.services.calendar_i18n import INDICATOR_CALENDAR_CONTEXT_EN, english_event_description
    from app.services.calendar_sources.official_calendar import INDICATOR_CALENDAR_CONTEXT

    assert set(INDICATOR_CALENDAR_CONTEXT) <= set(INDICATOR_CALENDAR_CONTEXT_EN)
    # Текст «за месяц», записанный до 20.11 на квартальный код, переводится как месячный.
    assert english_event_description("Стоимость товаров, вывезенных из России за месяц.", "exports") == \
        INDICATOR_CALENDAR_CONTEXT_EN["exports-monthly"]


def _indicator(code: str, frequency: str) -> Indicator:
    return Indicator(code=code, name=code, name_en=code, unit="млн $", frequency=frequency,
                     category="Test", source="fixture", source_url="https://example.test")


def _stored(code_id, key: str, day: date, summary: str) -> EconomicEvent:
    return EconomicEvent(
        title="t", event_type="data_release", source="cbr", status="scheduled", indicator_id=code_id,
        date_confidence="official_explicit", is_estimated=False, scheduled_date=day, scheduled_time="16:00",
        source_url="https://www.cbr.ru/", source_hash="a" * 64, last_seen_at=datetime(2026, 10, 1),
        event_key=key, importance=1,
        metadata_json={"provenance": {"details": {"feed": "cbr_ics", "raw_summary": summary}}},
    )


def test_stored_events_are_rebound_once_and_then_confirmed_from_monthly_load(auth_env):
    from app.services.calendar_sources.enrichment import confirm_releases_from_loads
    from app.services.calendar_sources.official_calendar import rebind_stored_cbr_ics_events

    goods = "Внешняя торговля Российской Федерации товарами (по методологии платежного баланса)*"

    async def scenario():
        async with auth_env["session_maker"]() as db:
            for code, freq in (("exports", "quarterly"), ("exports-monthly", "monthly"),
                               ("current-account", "quarterly"), ("external-debt", "quarterly")):
                db.add(_indicator(code, freq))
            await db.commit()
            ids = {i.code: i.id for i in (await db.execute(select(Indicator))).scalars()}
            db.add_all([
                # Ключ старого формата (до 14.11.2026).
                _stored(ids["exports"], "cbr:exports:sha256:f136b486", date(2026, 10, 12), goods),
                _stored(ids["current-account"], "cbr:ics:current-account:data_release:2026-10-15",
                        date(2026, 10, 15), "Платежный баланс – оценка"),
                # Квартальный выпуск счёта текущих операций остаётся на квартальном ряду.
                _stored(ids["current-account"], "cbr:ics:current-account:data_release:2026-09-30",
                        date(2026, 9, 30), "Счет текущих операций платежного баланса Российской Федерации "
                                           "с сезонной корректировкой"),
                _stored(ids["external-debt"], "cbr:ics:external-debt:data_release:2026-10-07",
                        date(2026, 10, 7), "Информационно-аналитический комментарий «Платежный баланс, "
                                           "международная инвестиционная позиция и внешний долг Российской Федерации»"),
                # Точка за сентябрь пришла вечером в день выпуска.
                IndicatorData(indicator_id=ids["exports-monthly"], date=date(2026, 8, 1), value=41100.0,
                              created_at=datetime(2026, 9, 11, 17)),
                IndicatorData(indicator_id=ids["exports-monthly"], date=date(2026, 9, 1), value=42600.0,
                              created_at=datetime(2026, 10, 12, 17)),
            ])
            await db.commit()

            assert await rebind_stored_cbr_ics_events(db) == 3
            assert await rebind_stored_cbr_ics_events(db) == 0
            rows = {r.event_key: r for r in (await db.execute(select(EconomicEvent))).scalars()}
            assert set(rows) == {
                "cbr:ics:exports-monthly:data_release:2026-10-12",
                "cbr:ics:balance-of-payments-estimate:data_release:2026-10-15",
                "cbr:ics:current-account:data_release:2026-09-30",
            }
            assert rows["cbr:ics:exports-monthly:data_release:2026-10-12"].indicator_id == ids["exports-monthly"]
            assert rows["cbr:ics:balance-of-payments-estimate:data_release:2026-10-15"].indicator_id is None
            assert rows["cbr:ics:current-account:data_release:2026-09-30"].indicator_id == ids["current-account"]

            assert await confirm_releases_from_loads(db, today=date(2026, 11, 20)) == 1
            goods_row = (await db.execute(select(EconomicEvent).where(
                EconomicEvent.event_key == "cbr:ics:exports-monthly:data_release:2026-10-12"))).scalar_one()
            assert goods_row.status == "released"
            assert goods_row.actual_value not in (None, "")

    asyncio.run(scenario())

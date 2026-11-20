"""Календарь сам остаётся актуальным (круг 14.11.2026).

Каждый тест закрывает дефект, найденный сверкой боевого календаря с официальными источниками:
перенос ИПЦ, застрявший на старой дате; даты резюме ЦБ; 2027 год; время UTC под видом МСК;
вечное «ожидает подтверждения» у событий ЦБ; предварительная оценка ВВП; .ics по RFC 5545.
"""
import asyncio
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from app.models import EconomicEvent, Indicator, IndicatorData
from app.services.calendar_sources.common import (
    CalendarCandidate,
    prune_legacy_keyless_estimates,
    sweep_unseen_feed_events,
    upsert_calendar_candidates,
)

FIXTURES = Path(__file__).parent / "fixtures" / "calendar"
PLAN_DOC = "https://rosstat.gov.ru/storage/mediabank/Grafik_srochn_2026.docx"


# --- Производственный календарь 2027 -------------------------------------------------------

def test_working_calendar_2027_matches_decree_1187():
    from app.services.calendar_sources.working_calendar import is_working_day, nth_working_day

    per_month = {}
    day = date(2027, 1, 1)
    while day.year == 2027:
        per_month[day.month] = per_month.get(day.month, 0) + int(is_working_day(day))
        day += timedelta(days=1)
    # КонсультантПлюс, производственный календарь 2027: 247 рабочих дней.
    assert per_month == {1: 15, 2: 19, 3: 22, 4: 22, 5: 19, 6: 21, 7: 22, 8: 22,
                         9: 22, 10: 21, 11: 20, 12: 22}
    assert is_working_day(date(2027, 2, 20))  # рабочая суббота по переносу
    assert not is_working_day(date(2027, 2, 22))
    assert not is_working_day(date(2027, 11, 5))
    assert nth_working_day(2027, 1, 1) == date(2027, 1, 11)


def test_daily_cbr_rule_continues_into_2027():
    from app.services.calendar_sources.official_calendar import build_cbr_daily_rule_candidates

    events = build_cbr_daily_rule_candidates(today=date(2026, 12, 20), months_ahead=1)
    days = {e.scheduled_date for e in events if e.indicator_code == "usd-rub"}
    assert date(2027, 1, 11) in days
    assert date(2027, 1, 8) not in days  # каникулы


# --- Календарь решений ЦБ по ключевой ставке ----------------------------------------------

def test_key_rate_page_parser_reads_both_years_and_official_summary_dates():
    from app.services.calendar_sources.cbr_key_rate import parse_key_rate_calendar

    html = (FIXTURES / "cbr_cal_mp_2026-11-14.html").read_text(encoding="utf-8")
    meetings = {m.date: m for m in parse_key_rate_calendar(html)}
    assert len(meetings) == 16
    oct_meeting = meetings[date(2026, 10, 23)]
    assert oct_meeting.has_forecast is True
    assert oct_meeting.summary_date == date(2026, 11, 5)  # было 04.11 в коде
    assert meetings[date(2026, 12, 18)].summary_date == date(2026, 12, 30)  # было 29.12
    assert meetings[date(2026, 4, 24)].summary_date == date(2026, 5, 7)  # было 12.05
    assert meetings[date(2027, 2, 12)].has_forecast is True
    assert meetings[date(2027, 3, 19)].has_forecast is False
    assert meetings[date(2027, 12, 17)].summary_date == date(2027, 12, 29)


def test_fallback_meetings_equal_parsed_page():
    from app.services.calendar_sources.cbr_key_rate import FALLBACK_MEETINGS, parse_key_rate_calendar

    html = (FIXTURES / "cbr_cal_mp_2026-11-14.html").read_text(encoding="utf-8")
    assert tuple(parse_key_rate_calendar(html)) == FALLBACK_MEETINGS


def test_summary_key_follows_the_meeting_so_a_move_is_a_reschedule():
    from app.services.calendar_sources.cbr_key_rate import KeyRateMeeting
    from app.services.calendar_sources.official_calendar import build_cbr_monetary_policy_candidates

    before = build_cbr_monetary_policy_candidates(
        today=date(2026, 10, 1), months_ahead=2,
        meetings=[KeyRateMeeting(date(2026, 10, 23), True, date(2026, 11, 4))])
    after = build_cbr_monetary_policy_candidates(
        today=date(2026, 10, 1), months_ahead=2,
        meetings=[KeyRateMeeting(date(2026, 10, 23), True, date(2026, 11, 5))])
    key = lambda events: {e.event_key for e in events if e.event_type == "report"}  # noqa: E731
    assert key(before) == key(after)


# --- Файл календаря ЦБ: время и дубли --------------------------------------------------------

ICS_UTC = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:{a}
DTSTART:20261119T130000Z
SUMMARY:Общий объем международных резервных активов, по состоянию на конец рабочей недели*
END:VEVENT
BEGIN:VEVENT
UID:{b}
DTSTART:20261113T130000Z
SUMMARY:Внешний долг Российской Федерации в национальной и иностранной валютах
END:VEVENT
BEGIN:VEVENT
UID:{c}
DTSTART:20261113T070000Z
SUMMARY:Внешний долг Российской Федерации
END:VEVENT
BEGIN:VEVENT
UID:{d}
DTSTART:20261231T220000Z
SUMMARY:Денежная масса М2 (национальное определение)
END:VEVENT
END:VCALENDAR
"""


def test_cbr_ics_time_is_moscow_and_one_event_per_indicator_day():
    from app.services.calendar_sources.official_calendar import parse_cbr_ics

    events = parse_cbr_ics(ICS_UTC, source_url="https://www.cbr.ru/x.ics",
                           today=date(2026, 11, 14), months_ahead=2)
    by = {(e.indicator_code, e.scheduled_date): e for e in events}
    assert by[("international-reserves", date(2026, 11, 19))].scheduled_time == "16:00"
    debt = [e for e in events if e.indicator_code == "external-debt"]
    assert len(debt) == 1 and debt[0].scheduled_time == "10:00"
    # 22:00 UTC 31 декабря — уже 1 января по Москве.
    assert by[("m2", date(2027, 1, 1))].scheduled_time == "01:00"


def test_cbr_ics_maps_monthly_balance_of_payments_estimate():
    from app.services.calendar_sources.official_calendar import parse_cbr_ics

    text = ICS_UTC.replace("Внешний долг Российской Федерации\n", "Платежный баланс – оценка\n")
    events = parse_cbr_ics(text, source_url="u", today=date(2026, 11, 14), months_ahead=2)
    # 20.11.2026: помесячной истории счёта текущих операций у ЦБ нет — выпуск идёт без ряда.
    estimate = [e for e in events if e.title == "Оценка платёжного баланса"]
    assert estimate and all(e.indicator_code is None for e in estimate)


# --- График Росстата -------------------------------------------------------------------------

def test_plan_page_lists_every_yearly_schedule():
    from app.services.calendar_sources.rosstat_plan import resolve_schedule_doc_urls

    html = (
        '<div>График размещения срочных информаций и справок на сайте Росстата</div>'
        '<a href="/storage/mediabank/Grafik_srochn_2027.docx">2027</a>'
        '<a href="/storage/mediabank/Grafik_srochn_2026.docx">2026</a>'
        '<a href="/storage/mediabank/Grafik_Srochn_2025.docx">2025</a>'
    )
    assert [y for y, _ in resolve_schedule_doc_urls(html)] == [2025, 2026, 2027]


def test_gdp_flash_estimate_gets_its_own_event_and_keeps_release_numbers():
    from app.services.calendar_sources import rosstat_plan

    rows = [
        (date(2026, 11, 13), "Справка о предварительной оценке динамики ВВП в III квартале 2026 года"),
        (date(2026, 12, 11), "О производстве валового внутреннего продукта в III квартале 2026 года"),
        (date(2026, 12, 30), "Об использовании валового внутреннего продукта в III квартале 2026 года"),
    ]
    original = rosstat_plan.parse_schedule_docx
    rosstat_plan.parse_schedule_docx = lambda content, year: rows
    try:
        events = rosstat_plan.build_rosstat_plan_candidates(
            b"", doc_url=PLAN_DOC, year=2026, today=date(2026, 11, 10), months_ahead=2)
    finally:
        rosstat_plan.parse_schedule_docx = original
    real = {e.event_key: e.scheduled_date for e in events if e.indicator_code == "gdp-real"}
    assert real == {
        "rosstat:plan:gdp-real:q3-2026:flash": date(2026, 11, 13),
        "rosstat:plan:gdp-real:q3-2026:r1": date(2026, 12, 11),
        "rosstat:plan:gdp-real:q3-2026:r2": date(2026, 12, 30),
    }


# --- Перенос, уборка, история ------------------------------------------------------------------

def _indicator(code: str, frequency: str = "monthly") -> Indicator:
    return Indicator(code=code, name=code, name_en=code, unit="%", frequency=frequency,
                     category="Test", source="fixture", source_url="https://example.test")


def _plan_candidate(code: str, day: date, ref: str = "октябрь 2026") -> CalendarCandidate:
    return CalendarCandidate(
        event_key=f"rosstat:plan:{code}:{ref.replace(' ', '-')}:r1", title="ИПЦ",
        event_type="data_release", source="rosstat", indicator_code=code, scheduled_date=day,
        date_confidence="official_explicit", reference_period=ref, importance=3,
        source_url=PLAN_DOC, metadata={"feed": "rosstat_plan", "schedule_year": 2026})


def test_cpi_moves_past_a_stale_keyless_estimate_and_api_shows_the_move(auth_env, auth_client):
    async def scenario():
        async with auth_env["session_maker"]() as db:
            db.add(_indicator("cpi"))
            await db.commit()
            ind = (await db.execute(select(Indicator))).scalar_one()
            await upsert_calendar_candidates(db, [_plan_candidate("cpi", date(2026, 11, 13))])
            # Старая скрытая оценка без ключа на новой дате — так было на боевом (id 454).
            db.add(EconomicEvent(title="ИПЦ", event_type="data_release", source="rosstat",
                                 indicator_id=ind.id, scheduled_date=date(2026, 11, 25),
                                 is_estimated=True, date_confidence="estimated", status="scheduled"))
            await db.commit()
            await upsert_calendar_candidates(db, [_plan_candidate("cpi", date(2026, 11, 25))])
            rows = (await db.execute(select(EconomicEvent))).scalars().all()
            assert [(r.event_key, r.scheduled_date) for r in rows] == [
                ("rosstat:plan:cpi:октябрь-2026:r1", date(2026, 11, 25))]
            return rows[0].id

    event_id = asyncio.run(scenario())
    body = auth_client.get(f"/api/v1/calendar/{event_id}").json()
    assert body["scheduled_date"] == "2026-11-25"
    assert body["rescheduled_from"] == "2026-11-13"


def test_prune_removes_only_keyless_estimates(auth_env):
    async def scenario():
        async with auth_env["session_maker"]() as db:
            db.add_all([
                EconomicEvent(title="old", event_type="data_release", source="rosstat",
                              scheduled_date=date(2026, 11, 18), is_estimated=True,
                              date_confidence="estimated"),
                EconomicEvent(title="rule", event_type="data_release", source="rosstat",
                              scheduled_date=date(2026, 11, 19), is_estimated=True,
                              date_confidence="estimated", event_key="rosstat:cpi:2026-10"),
            ])
            await db.commit()
            assert await prune_legacy_keyless_estimates(db) == 1
            keys = [r.event_key for r in (await db.execute(select(EconomicEvent))).scalars()]
            assert keys == ["rosstat:cpi:2026-10"]

    asyncio.run(scenario())


def test_sweep_drops_event_that_left_the_source_but_keeps_history(auth_env):
    async def scenario():
        async with auth_env["session_maker"]() as db:
            base = dict(event_type="report", source="cbr", date_confidence="official_explicit",
                        is_estimated=False, source_url="https://cbr.ru/dkp/cal_mp/", status="scheduled")
            db.add_all([
                EconomicEvent(title="old summary", scheduled_date=date(2026, 11, 4),
                              event_key="cbr:key-rate-summary:2026-11-04", **base),
                EconomicEvent(title="new summary", scheduled_date=date(2026, 11, 5),
                              event_key="cbr:key-rate-summary:meeting:2026-10-23", **base),
                EconomicEvent(title="released", scheduled_date=date(2026, 11, 6), actual_value="1",
                              event_key="cbr:key-rate-summary:2026-11-06", **base),
            ])
            await db.commit()
            removed = await sweep_unseen_feed_events(
                db, feed="cbr_key_rate", seen_keys={"cbr:key-rate-summary:meeting:2026-10-23"},
                start=date(2026, 10, 31), end=date(2027, 12, 31))
            assert removed == ["cbr:key-rate-summary:2026-11-04@2026-11-04"]

    asyncio.run(scenario())


# --- Факт выхода из нашей загрузки --------------------------------------------------------------

def _public_event(**kw) -> EconomicEvent:
    fields = dict(title="t", event_type="data_release", source="cbr", status="scheduled",
                  date_confidence="official_explicit", is_estimated=False,
                  source_url="https://www.cbr.ru/", source_hash="a" * 64,
                  last_seen_at=datetime(2026, 11, 1), importance=2)
    fields.update(kw)
    return EconomicEvent(**fields)


def test_cbr_events_are_confirmed_from_our_loads(auth_env):
    from app.services.calendar_sources.enrichment import confirm_releases_from_loads

    async def scenario():
        async with auth_env["session_maker"]() as db:
            for code, freq in (("key-rate", "daily"), ("international-reserves", "weekly"),
                               ("usd-rub", "daily"), ("m2", "monthly")):
                db.add(_indicator(code, freq))
            await db.commit()
            ids = {i.code: i.id for i in (await db.execute(select(Indicator))).scalars()}
            utc = lambda d, h: datetime(d.year, d.month, d.day, h)  # noqa: E731
            db.add_all([
                # Ключевая ставка: ряд по дням, решение 23.10 вступило в силу 26.10.
                IndicatorData(indicator_id=ids["key-rate"], date=date(2026, 10, 23), value=14.5,
                              created_at=utc(date(2026, 10, 23), 17)),
                IndicatorData(indicator_id=ids["key-rate"], date=date(2026, 10, 26), value=14.0,
                              created_at=utc(date(2026, 10, 26), 17)),
                # Резервы: точка за 06.11 загружена вечером 12.11.
                IndicatorData(indicator_id=ids["international-reserves"], date=date(2026, 10, 30),
                              value=721.6, created_at=utc(date(2026, 11, 6), 17)),
                IndicatorData(indicator_id=ids["international-reserves"], date=date(2026, 11, 6),
                              value=724.3, created_at=utc(date(2026, 11, 12), 17)),
                # Курс, установленный 13.11 (пятница), ряд хранит датой 14.11.
                IndicatorData(indicator_id=ids["usd-rub"], date=date(2026, 11, 14), value=81.5,
                              created_at=utc(date(2026, 11, 14), 0)),
            ])
            db.add_all([
                _public_event(event_type="rate_decision", indicator_id=ids["key-rate"],
                              scheduled_date=date(2026, 10, 23), event_key="cbr:key-rate-decision:2026-10-23"),
                _public_event(indicator_id=ids["international-reserves"],
                              scheduled_date=date(2026, 11, 12), event_key="cbr:ics:reserves"),
                _public_event(indicator_id=ids["usd-rub"], date_confidence="official_rule",
                              scheduled_date=date(2026, 11, 13), event_key="cbr:usd-rub:2026-11-13"),
                # M2 20.11 ещё не наступило — не трогаем; 20.10 без загрузки — остаётся без факта.
                _public_event(indicator_id=ids["m2"], scheduled_date=date(2026, 10, 20),
                              event_key="cbr:ics:m2"),
            ])
            await db.commit()
            assert await confirm_releases_from_loads(db, today=date(2026, 11, 14)) == 3
            rows = {r.event_key: r for r in (await db.execute(select(EconomicEvent))).scalars()}
            decision = rows["cbr:key-rate-decision:2026-10-23"]
            assert (decision.status, decision.actual_value, decision.previous_value) == ("released", "14", "14,5")
            assert rows["cbr:ics:reserves"].actual_value == "724,3"
            assert rows["cbr:ics:reserves"].metadata_json["release_fact"]["seen_on"] == "2026-11-12"
            assert rows["cbr:usd-rub:2026-11-13"].actual_value == "81,5"
            assert rows["cbr:ics:m2"].actual_value is None

    asyncio.run(scenario())


def test_second_release_is_not_marked_released_before_its_date(auth_env):
    from app.services.calendar_sources.enrichment import enrich_events_from_indicator_data

    async def scenario():
        async with auth_env["session_maker"]() as db:
            db.add(_indicator("gdp-real", "quarterly"))
            await db.commit()
            gid = (await db.execute(select(Indicator.id))).scalar_one()
            db.add(IndicatorData(indicator_id=gid, date=date(2026, 9, 1), value=36000,
                                 created_at=datetime(2026, 12, 11, 17)))
            common = dict(source="rosstat", indicator_id=gid, reference_period="Q3 2026")
            db.add_all([
                _public_event(scheduled_date=date(2026, 11, 13), event_key="rosstat:plan:gdp-real:q3-2026:flash", **common),
                _public_event(scheduled_date=date(2026, 12, 11), event_key="rosstat:plan:gdp-real:q3-2026:r1", **common),
                _public_event(scheduled_date=date(2026, 12, 30), event_key="rosstat:plan:gdp-real:q3-2026:r2", **common),
            ])
            await db.commit()
            await enrich_events_from_indicator_data(db, today=date(2026, 12, 12))
            status = {r.event_key.rsplit(":", 1)[-1]: r.status
                      for r in (await db.execute(select(EconomicEvent))).scalars()}
            assert status == {"flash": "scheduled", "r1": "released", "r2": "scheduled"}

    asyncio.run(scenario())


# --- Подписка .ics ------------------------------------------------------------------------------

def test_ical_export_is_rfc5545_with_stable_uid_and_moscow_time(auth_env, auth_client):
    from app.api.calendar import _ics_uid
    from app.services.display import today_msk

    day = today_msk() + timedelta(days=3)

    async def seed():
        async with auth_env["session_maker"]() as db:
            ev = _public_event(title="Международные резервы РФ, недельные; оценка", scheduled_date=day,
                               scheduled_time="16:00", event_key="cbr:ics:international-reserves",
                               importance=2, description="Очень длинное описание " * 8)
            db.add(ev)
            await db.commit()
            return ev

    ev = asyncio.run(seed())
    text = auth_client.get("/api/v1/calendar/export/ical").text
    assert all(len(line.encode("utf-8")) <= 75 for line in text.split("\r\n"))
    unfolded = text.replace("\r\n ", "")
    assert f"UID:{_ics_uid(ev)}" in unfolded
    assert "DTSTAMP:" in unfolded
    utc_start = datetime(day.year, day.month, day.day, 13).strftime("%Y%m%dT%H%M%SZ")
    assert f"DTSTART:{utc_start}" in unfolded
    assert "SUMMARY:Международные резервы РФ\\, недельные\\; оценка" in unfolded


def test_rule_builders_survive_short_january_2027():
    from app.services.calendar_sources.official_calendar import build_rule_candidates

    events = build_rule_candidates(today=date(2026, 11, 14), months_ahead=12)
    assert not any(e.indicator_code == "ppi" and e.scheduled_date.year == 2027
                   and e.scheduled_date.month == 1 for e in events)
    assert any(e.scheduled_date.year == 2027 for e in events)


def test_legacy_cbr_times_move_to_moscow_once(auth_env):
    from app.services.calendar_sources.common import repair_legacy_cbr_ics_times

    async def scenario():
        async with auth_env["session_maker"]() as db:
            db.add_all([
                _public_event(scheduled_date=date(2026, 10, 1), scheduled_time="13:00", event_key="cbr:old"),
                _public_event(scheduled_date=date(2026, 11, 19), scheduled_time="16:00", event_key="cbr:ics:new",
                              metadata_json={"provenance": {"details": {"feed": "cbr_ics"}}}),
                _public_event(event_type="rate_decision", scheduled_date=date(2026, 10, 23),
                              scheduled_time="13:30", event_key="cbr:key-rate-decision:2026-10-23"),
            ])
            await db.commit()
            assert await repair_legacy_cbr_ics_times(db) == 1
            assert await repair_legacy_cbr_ics_times(db) == 0
            times = {r.event_key: r.scheduled_time for r in (await db.execute(select(EconomicEvent))).scalars()}
            assert times == {"cbr:old": "16:00", "cbr:ics:new": "16:00",
                             "cbr:key-rate-decision:2026-10-23": "13:30"}

    asyncio.run(scenario())

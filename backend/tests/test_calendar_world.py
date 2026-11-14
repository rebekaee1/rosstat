"""Календарь, второй заход 14.11.2026 (утверждено владельцем): мировые выпуски, Минфин «не позднее»,
наш прогноз на карточке, строки календаря в утренней сводке."""
import asyncio
import json
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from app.models import (
    EconomicEvent, Forecast, ForecastValue, Indicator, IndicatorData, WorldCountry, WorldDataPoint, WorldIndicator,
)
from app.services.calendar_sources.common import CalendarCandidate, upsert_calendar_candidates
from app.services.display import today_msk

FIX = Path(__file__).parent / "fixtures" / "calendar"
TODAY = date(2026, 11, 14)


# --- Разбор источников --------------------------------------------------------------------------

def test_fomc_page_gives_both_years_and_moscow_time_with_us_dst():
    from app.services.calendar_sources.world_calendar import build_fomc_candidates, parse_fomc_calendar

    meetings = parse_fomc_calendar((FIX / "fomc_calendar_2026-11-14.html").read_text(encoding="utf-8"))
    days = [m.decision_date for m in meetings]
    assert len(meetings) == 16
    assert date(2026, 12, 9) in days and date(2027, 1, 27) in days
    assert next(m for m in meetings if m.decision_date == date(2026, 12, 9)).has_projections
    by_day = {c.scheduled_date: c for c in build_fomc_candidates(meetings, today=TODAY, months_ahead=12)}
    assert by_day[date(2026, 12, 9)].scheduled_time == "22:00"   # 14:00 EST
    assert by_day[date(2027, 6, 9)].scheduled_time == "21:00"    # 14:00 EDT
    assert by_day[date(2026, 12, 9)].metadata["world_code"] == "us-policy-rate"


def test_bea_schedule_maps_gdp_estimates_pce_and_trade():
    from app.services.calendar_sources.world_calendar import parse_bea_ics

    events = parse_bea_ics((FIX / "bea_schedule_2026-11-14.ics").read_text(encoding="utf-8"),
                           today=TODAY, months_ahead=3)
    keys = {e.event_key: (e.scheduled_date, e.scheduled_time) for e in events}
    assert keys["world:bea:us-gdp-real-growth:q3-2026:second"] == (date(2026, 11, 25), "16:30")
    assert keys["world:bea:us-pce-price:октябрь-2026:r1"] == (date(2026, 11, 25), "16:30")
    assert "world:bea:us-gdp-real-growth:q4-2026:advance" in keys
    assert not any("Super Intelligence" in (e.metadata.get("raw_summary") or "") for e in events)


def test_eurostat_euro_indicators_with_periods_and_update_release():
    from app.services.calendar_sources.world_calendar import parse_eurostat_events

    payload = json.loads((FIX / "eurostat_euroind_2026-11-14.json").read_text(encoding="utf-8"))
    events = parse_eurostat_events(payload, today=TODAY, months_ahead=3)
    by_key = {e.event_key: e for e in events}
    assert len(by_key) == len(events)  # ключи не повторяются
    flash = by_key["world:eurostat:hicp-flash:ноябрь-2026"]
    assert (flash.scheduled_date, flash.scheduled_time, flash.importance) == (date(2026, 12, 1), "14:00", 3)
    assert "world:eurostat:gdp-update:q3-2026" in by_key and "world:eurostat:gdp:q3-2026" in by_key


# --- База и API ----------------------------------------------------------------------------------

def _world(key, day, source="bea", code="us-pce-price", ref="октябрь 2026"):
    return CalendarCandidate(
        event_key=key, title="США: доходы", event_type="data_release", source=source, scheduled_date=day,
        date_confidence="official_explicit", importance=2, reference_period=ref,
        source_url="https://www.bea.gov/news/schedule",
        metadata={"feed": source, "world": True, "country_ru": "США", "country_en": "United States",
                  "world_country_slug": "united-states", "world_code": code})


def test_world_events_same_day_do_not_merge_and_stay_off_the_russia_page(auth_env, auth_client):
    day = today_msk() + timedelta(days=5)

    async def seed():
        async with auth_env["session_maker"]() as db:
            await upsert_calendar_candidates(db, [
                _world("world:bea:us-pce-price:r1", day),
                _world("world:bea:us-gdp:second", day, code="us-gdp-real-growth", ref="Q3 2026"),
            ])
            return len((await db.execute(select(EconomicEvent))).scalars().all())

    assert asyncio.run(seed()) == 2
    russia = auth_client.get("/api/v1/calendar").json()["events"]
    assert russia == []
    world = auth_client.get("/api/v1/calendar", params={"source": "fed,bea,eurostat"}).json()["events"]
    assert {e["link_path"] for e in world} == {"/united-states/us-pce-price", "/united-states/us-gdp-real-growth"}
    assert {e["country"] for e in world} == {"США"}


def test_minfin_deadline_is_public_and_released_early_from_our_load(auth_env, auth_client):
    from app.services.calendar_sources.enrichment import enrich_events_from_indicator_data
    from app.services.calendar_sources.official_calendar import build_minfin_rule_candidates

    async def seed():
        async with auth_env["session_maker"]() as db:
            db.add(Indicator(code="budget-revenue", name="Доходы", name_en="Revenue", unit="млрд руб.",
                             frequency="monthly", category="Бюджет", source="Минфин",
                             source_url="https://minfin.gov.ru"))
            await db.commit()
            ind = (await db.execute(select(Indicator))).scalar_one()
            cands = [c for c in build_minfin_rule_candidates(today=date(2026, 10, 1), months_ahead=1)
                     if c.indicator_code == "budget-revenue" and c.reference_period == "сентябрь 2026"]
            assert cands[0].scheduled_date == date(2026, 10, 20)
            await upsert_calendar_candidates(db, cands)
            db.add(IndicatorData(indicator_id=ind.id, date=date(2026, 9, 1), value=3000,
                                 created_at=datetime(2026, 10, 12, 9)))
            await db.commit()
            # 15.10 — до срока: данные уже пришли 12.10, значит выпуск вышел.
            await enrich_events_from_indicator_data(db, today=date(2026, 10, 15))
            ev = (await db.execute(select(EconomicEvent))).scalar_one()
            return ev.id, ev.status

    event_id, status = asyncio.run(seed())
    assert status == "released"
    body = auth_client.get(f"/api/v1/calendar/{event_id}").json()
    assert body["deadline"] is True and body["date_confidence"] == "official_deadline"


def test_our_point_forecast_fills_future_release_only(auth_env):
    from app.services.calendar_sources.enrichment import fill_event_forecasts

    async def scenario():
        async with auth_env["session_maker"]() as db:
            ind = Indicator(code="cpi", name="ИПЦ", name_en="CPI", unit="%", frequency="monthly",
                            category="Цены", source="Росстат", source_url="https://rosstat.gov.ru",
                            model_config_json={"forecast_steps": 6})
            db.add(ind)
            await db.commit()
            fc = Forecast(indicator_id=ind.id, model_name="SARIMA", is_current=True)
            db.add(fc)
            await db.commit()
            db.add_all([ForecastValue(forecast_id=fc.id, date=date(2026, 10, 1), value=100.4173,
                                      lower_bound=99.9, upper_bound=101.0),
                        # Факты ряда с двумя знаками — прогноз пишется так же, без «100,4173».
                        IndicatorData(indicator_id=ind.id, date=date(2026, 9, 1), value=100.25)])
            base = dict(event_type="data_release", source="rosstat", indicator_id=ind.id,
                        date_confidence="official_explicit", is_estimated=False, status="scheduled",
                        source_url="u", source_hash="a" * 64, last_seen_at=datetime(2026, 11, 14), importance=3)
            db.add_all([
                EconomicEvent(title="ИПЦ", scheduled_date=date(2026, 11, 25), reference_period="октябрь 2026",
                              event_key="future", **base),
                EconomicEvent(title="ИПЦ", scheduled_date=date(2026, 10, 9), reference_period="сентябрь 2026",
                              event_key="past", actual_value="100,2", **{**base, "status": "released"}),
            ])
            await db.commit()
            assert await fill_event_forecasts(db, today=TODAY) == 2
            rows = {e.event_key: e for e in (await db.execute(select(EconomicEvent))).scalars()}
            assert {k: e.forecast_value for k, e in rows.items()} == {"future": "100,42", "past": None}
            assert rows["future"].previous_value == "100,25"  # последний факт перед октябрём

    asyncio.run(scenario())


def test_world_event_released_from_world_series(auth_env):
    from app.services.calendar_sources.world_enrichment import enrich_world_events

    async def scenario():
        async with auth_env["session_maker"]() as db:
            country = WorldCountry(code="US", slug="united-states", name_ru="США", name_en="United States")
            db.add(country)
            await db.commit()
            wi = WorldIndicator(country_id=country.id, code="us-gdp-real-growth", dataset_id="A191RL1Q225SBEA",
                                slice_hash="x", name_ru="ВВП", unit="%", unit_ru="%", frequency="quarterly",
                                category_ru="ВВП", source="FRED", provider="fred")
            db.add(wi)
            await db.commit()
            db.add_all([WorldDataPoint(indicator_id=wi.id, date=date(2026, 4, 1), value=2.1),
                        WorldDataPoint(indicator_id=wi.id, date=date(2026, 7, 1), value=3.4)])
            await db.commit()
            await upsert_calendar_candidates(db, [_world("world:bea:gdp:q3:advance", date(2026, 10, 29),
                                                         code="us-gdp-real-growth", ref="Q3 2026")])
            assert await enrich_world_events(db, today=TODAY) == 1
            ev = (await db.execute(select(EconomicEvent))).scalar_one()
            return ev.actual_value, ev.previous_value

    assert asyncio.run(scenario()) == ("3,4", "2,1")


# --- Утренняя сводка ------------------------------------------------------------------------------

def test_watchdog_reports_silent_feed_and_missing_dates(auth_env):
    from app.services.calendar_digest import watchdog_lines

    async def scenario():
        async with auth_env["session_maker"]() as db:
            db.add(EconomicEvent(title="ИПЦ", event_type="data_release", source="rosstat",
                                 scheduled_date=date(2026, 11, 25), date_confidence="official_explicit",
                                 is_estimated=False, event_key="rosstat:plan:cpi:x", source_url="u",
                                 source_hash="a" * 64, last_seen_at=datetime(2026, 11, 10)))
            await db.commit()
            return await watchdog_lines(db, now=datetime(2026, 11, 14, 6), today=TODAY)

    lines = asyncio.run(scenario())
    assert len(lines) == 1
    assert "Росстат, график срочных публикаций — не отвечает 4 сут." in lines[0]
    assert "нет даты на 45 дней" in lines[0] and "ключевая ставка" in lines[0]


def test_today_line_lists_releases_and_moves(auth_env):
    from app.services.calendar_digest import today_lines

    now = datetime(2026, 11, 25, 6)

    async def scenario():
        async with auth_env["session_maker"]() as db:
            db.add(EconomicEvent(
                title="Индекс потребительских цен (ИПЦ)", event_type="data_release", source="rosstat",
                scheduled_date=date(2026, 11, 25), date_confidence="official_explicit", is_estimated=False,
                importance=3, reference_period="октябрь 2026", event_key="k", source_url="u",
                source_hash="a" * 64, last_seen_at=now, updated_at=now - timedelta(hours=2),
                metadata_json={"reschedule_audit": [{"previous_date": "2026-11-13", "new_date": "2026-11-25",
                                                     "fetched_at": (now - timedelta(hours=3)).isoformat()}]}))
            await db.commit()
            return await today_lines(db, now=now, today=date(2026, 11, 25))

    lines = asyncio.run(scenario())
    assert lines[0].startswith("<b>Сегодня в календаре:</b> Индекс потребительских цен")
    assert "13 ноября → 25 ноября" in lines[1]

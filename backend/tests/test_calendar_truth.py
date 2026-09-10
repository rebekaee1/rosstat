"""Calendar evidence survives ingestion and all public routes."""
import asyncio
from datetime import date, datetime, timedelta

from sqlalchemy import select

from app.api.calendar import _effective_status
from app.models import EconomicEvent
from app.services.calendar_sources.common import CalendarCandidate, upsert_calendar_candidates
from app.services.display import today_msk


def event(**overrides):
    fields = dict(title="Confirmed date", event_type="data_release", source="cbr",
                  scheduled_date=today_msk() - timedelta(days=1), status="scheduled",
                  date_confidence="official_explicit", is_estimated=False,
                  source_url="https://www.cbr.ru/statistics/indcalendar/",
                  event_key="test:confirmed", source_hash="a" * 64,
                  last_seen_at=datetime(2026, 9, 10), importance=3)
    fields.update(overrides)
    return EconomicEvent(**fields)


def test_passed_date_and_legacy_status_do_not_prove_publication():
    assert _effective_status(event()) == "awaiting_confirmation"
    assert _effective_status(event(status="released")) == "awaiting_confirmation"
    assert _effective_status(event(actual_value="0")) == "released"


def test_unverified_rules_hidden_from_list_detail_upcoming_and_ical(auth_env, auth_client):
    async def seed():
        async with auth_env["session_maker"]() as db:
            rows = [event(source="rosstat", date_confidence="official_rule", event_key="bad:rosstat"),
                    event(source="minfin", date_confidence="official_rule", event_key="bad:minfin"),
                    event(event_key="good:explicit"),
                    event(date_confidence="official_rule", event_key="good:cbr",
                          scheduled_date=today_msk() + timedelta(days=1))]
            db.add_all(rows)
            await db.commit()
            return [r.id for r in rows]
    ids = asyncio.run(seed())
    response = auth_client.get("/api/v1/calendar")
    assert response.status_code == 200
    assert {e["id"] for e in response.json()["events"]} == set(ids[2:])
    for id_ in ids[:2]:
        assert auth_client.get(f"/api/v1/calendar/{id_}").status_code == 404
    upcoming = auth_client.get("/api/v1/calendar/upcoming").json()["events"]
    assert {e["id"] for e in upcoming} == {ids[3]}
    ical = auth_client.get("/api/v1/calendar/export/ical", params={"from": str(today_msk()-timedelta(days=2))}).text
    assert all(f"fe-event-{id_}@" not in ical for id_ in ids[:2])
    assert all(f"fe-event-{id_}@" in ical for id_ in ids[2:])


def test_ingest_does_not_mark_elapsed_date_released(auth_env):
    async def check():
        async with auth_env["session_maker"]() as db:
            candidate = CalendarCandidate(event_key="past", title="Past schedule",
                event_type="data_release", source="cbr", scheduled_date=date(2026, 1, 1),
                date_confidence="official_explicit", importance=3,
                source_url="https://www.cbr.ru/statistics/indcalendar/")
            await upsert_calendar_candidates(db, [candidate])
            row = (await db.execute(select(EconomicEvent))).scalar_one()
            assert row.status == "scheduled"
            row.status = "released"  # Old ingestion used elapsed dates as evidence.
            await db.commit()
            await upsert_calendar_candidates(db, [candidate])
            assert row.status == "scheduled"
            row.actual_value = "0"
            await db.commit()
            await upsert_calendar_candidates(db, [candidate])
            assert row.status == "released"
    asyncio.run(check())


def test_scheduler_repairs_legacy_release_without_publication(auth_env, monkeypatch):
    from app.tasks import scheduler

    monkeypatch.setattr(scheduler, "async_session", auth_env["session_maker"])

    async def check():
        async with auth_env["session_maker"]() as db:
            db.add_all([event(status="released", event_key="unconfirmed"),
                        event(status="released", actual_value="0", event_key="confirmed")])
            await db.commit()
        await scheduler._promote_past_events()
        async with auth_env["session_maker"]() as db:
            rows = {r.event_key: r.status for r in (await db.execute(select(EconomicEvent))).scalars()}
            assert rows == {"unconfirmed": "scheduled", "confirmed": "released"}

    asyncio.run(check())


def test_temporary_plan_failure_cannot_downgrade_saved_official_date(auth_env):
    from dataclasses import replace

    async def check():
        async with auth_env["session_maker"]() as db:
            explicit = CalendarCandidate(event_key="plan:cpi", title="Official CPI date",
                event_type="data_release", source="rosstat", scheduled_date=date(2026, 9, 11),
                date_confidence="official_explicit", importance=3,
                source_url="https://rosstat.gov.ru/storage/mediabank/Grafik_srochn_2026.docx")
            await upsert_calendar_candidates(db, [explicit])
            estimate = replace(explicit, event_key="rule:cpi", date_confidence="estimated",
                               source_url="https://rosstat.gov.ru/statistics/price")
            assert await upsert_calendar_candidates(db, [estimate]) == 0
            row = (await db.execute(select(EconomicEvent))).scalar_one()
            assert row.date_confidence == "official_explicit"
            assert row.event_key == explicit.event_key
            assert row.is_estimated is False
            assert row.source_url == explicit.source_url

    asyncio.run(check())

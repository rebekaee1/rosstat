"""E1/E2/E7 (круг 11): окно Пульса по МСК, дозапись вечера, подсчёт на SQL."""
import asyncio
from datetime import date, datetime, timedelta

from app.models import FrontendEvent, User
from app.services import pulse

D = date(2026, 10, 8)
# МСК-сутки 2026-10-08 = [2026-10-07 21:00 UTC, 2026-10-08 21:00 UTC)


def test_day_bounds_are_moscow_day():
    start, end = pulse._day_bounds(D)
    assert start == datetime(2026, 10, 7, 21, 0)
    assert end == datetime(2026, 10, 8, 21, 0)


def _event(name, when, **kw):
    return FrontendEvent(event_name=name, occurred_at=when, **kw)


def test_event_at_01_00_msk_belongs_to_the_day(auth_env):
    """Событие в 01:00 МСК (= 22:00 UTC предыдущей даты) попадает в день МСК,
    а событие в 23:30 МСК (20:30 UTC) предыдущего дня — нет."""
    async def run():
        async with auth_env["session_maker"]() as db:
            db.add_all([
                _event("indicator_view", datetime(2026, 10, 7, 22, 0), params_json={"indicator": "cpi"},
                       session_id_hash="s1"),                      # 01:00 МСК 08.10 -> в дне
                _event("indicator_view", datetime(2026, 10, 7, 20, 30), params_json={"indicator": "cpi"},
                       session_id_hash="s0"),                      # 23:30 МСК 07.10 -> не в дне
                _event("indicator_view", datetime(2026, 10, 8, 20, 59), params_json={"indicator": "gdp"},
                       session_id_hash="s2"),                      # 23:59 МСК 08.10 -> в дне
                _event("indicator_view", datetime(2026, 10, 8, 21, 1), params_json={"indicator": "gdp"},
                       session_id_hash="s3"),                      # 00:01 МСК 09.10 -> не в дне
            ])
            await db.commit()
            start, end = pulse._day_bounds(D)
            return await pulse._events_snapshot(db, start, end)

    snap = asyncio.run(run())
    assert snap["events"]["total"] == 2
    assert snap["events"]["top_indicators"] == {"cpi": 1, "gdp": 1}
    assert snap["audience"]["guest_sessions"] == 2


def test_events_snapshot_counts_on_sql_like_the_old_loop(auth_env):
    async def run():
        async with auth_env["session_maker"]() as db:
            t = datetime(2026, 10, 8, 6, 0)
            db.add_all([
                _event("download_csv", t, authed=True, user_id="u1", session_id_hash="a"),
                _event("download_excel", t, authed=False, session_id_hash="b"),
                _event("download_limit", t, authed=False, session_id_hash="b"),
                _event("compare_csv_download", t, authed=False, session_id_hash="b"),  # несуществующее имя
                _event("error_reload", t, authed=False, session_id_hash="c"),
                _event("api_load_error", t, authed=False, session_id_hash="c"),
                _event("search_query", t, params_json={"q": "  ВВП ", "results": 0}, session_id_hash="d"),
                _event("search_query", t, params_json={"q": "ввп", "results": 5}, session_id_hash="d"),
                _event("search_query", t, params_json={"q": "mail me bob@example.com", "results": 0},
                       session_id_hash="d"),
                _event("region_indicator_view", t, params_json={"region": "moskva", "indicator": "cpi"},
                       session_id_hash="e"),
                _event("indicator_view", t, url="https://ru.forecasteconomy.com/region/tula/cpi?x=1",
                       session_id_hash="e"),
            ])
            await db.commit()
            start, end = pulse._day_bounds(D)
            return await pulse._events_snapshot(db, start, end)

    snap = asyncio.run(run())
    ev = snap["events"]
    assert ev["downloads"] == {"download_csv": 1, "download_excel": 1}
    assert ev["wall_hits"] == {"download_limit": 1}
    assert ev["errors"] == {"error_reload": 1, "api_load_error": 1}
    assert ev["downloads_by_audience"] == {"authed": 1, "guest": 1}
    assert ev["search_top"]["ввп"] == 2
    assert ev["search_zero_results"]["ввп"] == 1
    # почта в строке поиска не попадает в снимок
    assert not any("@" in key for key in ev["search_top"])
    assert ev["top_regions"] == {"moskva": 1, "tula": 1}
    assert ev["top_indicators"] == {"cpi": 1}
    assert snap["audience"]["authed_active"] == 1
    assert snap["audience"]["guest_sessions"] == 4  # b, c, d, e; сессия «a» — зарегистрированный


def test_snapshot_completeness_rules():
    """Снимок 23:57 и снимок без окна (до круга 11) неполны; полный — собран после конца суток."""
    day = date(2026, 10, 8)
    end = datetime(2026, 10, 8, 21, 0)
    legacy = {"date": "2026-10-08"}
    evening = {"date": "2026-10-08", "window": {"end_utc": end.isoformat()}, "complete": False}
    morning = {"date": "2026-10-08", "window": {"end_utc": end.isoformat()}, "complete": True}
    assert not pulse.snapshot_is_complete(None, day)
    assert not pulse.snapshot_is_complete(legacy, day)
    assert not pulse.snapshot_is_complete(evening, day)
    assert pulse.snapshot_is_complete(morning, day)


def test_get_or_build_rebuilds_evening_snapshot_of_a_finished_day(monkeypatch):
    stored = {}
    built = []

    async def load(d):
        return stored.get(d.isoformat())

    async def store(snap):
        stored[snap["date"]] = snap

    async def build(d):
        built.append(d)
        return {"date": d.isoformat(), "window": {"end_utc": "x"}, "complete": True, "events": {"total": 7}}

    monkeypatch.setattr(pulse, "load_snapshot", load)
    monkeypatch.setattr(pulse, "store_snapshot", store)
    monkeypatch.setattr(pulse, "build_snapshot", build)
    monkeypatch.setattr(pulse, "today_msk", lambda: date(2026, 10, 9))

    d = date(2026, 10, 8)
    stored["2026-10-08"] = {"date": "2026-10-08", "window": {"end_utc": "x"}, "complete": False,
                            "users": {"new_list": [{"name": "Иван", "contact": "i@x.ru"}]}}
    snap = asyncio.run(pulse.get_or_build_snapshot(d))
    assert built == [d]
    assert snap["events"]["total"] == 7
    # старый снимок с именами вытеснен
    assert "new_list" not in stored["2026-10-08"].get("users", {})

    # полный снимок второй раз не пересобирается
    asyncio.run(pulse.get_or_build_snapshot(d))
    assert built == [d]


def test_get_or_build_does_not_rebuild_incomplete_snapshot_of_today(monkeypatch):
    built = []

    async def load(d):
        return {"date": d.isoformat(), "window": {"end_utc": "x"}, "complete": False}

    async def build(d):
        built.append(d)
        return {}

    monkeypatch.setattr(pulse, "load_snapshot", load)
    monkeypatch.setattr(pulse, "build_snapshot", build)
    monkeypatch.setattr(pulse, "today_msk", lambda: date(2026, 10, 8))
    asyncio.run(pulse.get_or_build_snapshot(date(2026, 10, 8)))
    assert built == []

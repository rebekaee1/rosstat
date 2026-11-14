"""Сверка переходов из поисковиков с Метрикой -> строка утренней сводки (14.11.2026)."""
from datetime import date, datetime, timedelta

import fakeredis.aioredis

from app.models import BehaviorSession, RawMetrikaVisit, ServerSession
from app.services import analytics_alerts as alerts
from app.services.telegram_calm import HELD_KINDS, build_summary
from test_analytics2 import _run_with_db

DAY = date(2026, 11, 13)
START = datetime(2026, 11, 12, 21)


def test_threshold_needs_30_visits_and_three_times():
    assert alerts.engine_mismatches({"Google": 1957, "Яндекс": 327}, {"Google": 13, "Яндекс": 366}) == [
        ("Google", 1957, 13)]
    assert alerts.engine_mismatches({"Google": 29}, {"Google": 1}) == []  # меньше 30 - шум
    assert alerts.engine_mismatches({"Google": 89}, {"Google": 30}) == []  # меньше чем в 3 раза
    assert alerts.engine_mismatches({}, {"Яндекс": 90}) == [("Яндекс", 0, 90)]  # теряем сами


def test_kind_is_held_and_has_plain_label_in_morning_summary():
    assert "counter_mismatch" in HELD_KINDS
    text = alerts.counter_mismatch_text(DAY, [("Google", 1957, 13)])
    summary = build_summary([("counter_mismatch", text)], day=date(2026, 11, 14))
    assert "Статистика и поиск" in summary
    assert "наш счётчик и Метрика расходятся по поисковикам — 1 раз" in summary
    assert "Google: у нас 1957, в Метрике 13" in summary


def test_check_counts_humans_only_and_holds_one_note_per_day(monkeypatch):
    from app.core import cache as cache_mod

    sent: list[tuple[str, str]] = []

    async def fake_send(message, chat_id=None, reply_markup=None, kind="alert"):
        sent.append((kind, message))
        return True

    monkeypatch.setattr(cache_mod, "_state_redis", fakeredis.aioredis.FakeRedis(decode_responses=True))
    monkeypatch.setattr("app.services.alerting.send_telegram", fake_send)

    async def scenario(maker):
        monkeypatch.setattr(alerts, "analytics_session", maker)
        async with maker() as db:
            for n in range(40):  # люди из Google
                at = START + timedelta(hours=8, minutes=n)
                db.add(BehaviorSession(session_id_hash=f"h{n}", visitor_id_hash=f"hv{n}", started_at=at,
                                       channel="search", referrer_host="google.com"))
                db.add(ServerSession(day=DAY, visitor_id_hash=f"hv{n}", started_at=at, ended_at=at, is_bot=False))
            for n in range(60):  # ферма, признанная ботом, в счёт не идёт
                at = START + timedelta(hours=9, minutes=n)
                db.add(BehaviorSession(session_id_hash=f"f{n}", visitor_id_hash=f"fv{n}", started_at=at,
                                       channel="search", referrer_host="google.com"))
                db.add(ServerSession(day=DAY, visitor_id_hash=f"fv{n}", started_at=at, ended_at=at, is_bot=True,
                                     bot_score=80))
            for n in range(5):
                db.add(RawMetrikaVisit(counter_id=1, visit_id=n + 1, client_id_hash=f"m{n}", visit_date=DAY,
                                       traffic_source="organic", search_engine="google", raw_json={},
                                       row_hash=f"h{n}"))
            await db.commit()
        first = await alerts.check_engine_counter_mismatch(DAY)
        again = await alerts.check_engine_counter_mismatch(DAY)
        return first, again

    first, again = _run_with_db(scenario)
    assert first == [("Google", 40, 5)] and again == first
    assert [k for k, _ in sent] == ["counter_mismatch"]


def test_no_metrika_rows_means_no_comparison(monkeypatch):
    async def scenario(maker):
        monkeypatch.setattr(alerts, "analytics_session", maker)
        return await alerts.check_engine_counter_mismatch(DAY)

    assert _run_with_db(scenario) == []

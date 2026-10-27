"""Ферма с клонированным портретом и сверка с Метрикой по сопоставимой популяции (27.10.2026)."""

from datetime import date, datetime, timedelta

from sqlalchemy import select

from app.services import analytics_alerts as alerts
from app.services.bot_score import (
    BOT_THRESHOLD, PORTRAIT_CLUSTER_MIN, SessionSignals, portrait_fingerprint, score_session, signal_breakdown,
)

from tests.test_analytics2 import _run_with_db


def _sig(**kw):
    base = dict(pageviews=1, clicks=0, moves=0, active_ms=0, max_scroll_pct=0,
                synthetic_clicks=0, visitor_sessions=1, has_portrait=True, device_type="desktop")
    base.update(kw)
    return SessionSignals(**base)


def test_portrait_cluster_without_input_is_bot():
    s = _sig(portrait_cluster=PORTRAIT_CLUSTER_MIN)
    assert score_session(s) >= BOT_THRESHOLD
    assert "portrait_cluster" in signal_breakdown(s)


def test_portrait_cluster_with_any_input_is_not_bot():
    for traces in ({"clicks": 1}, {"moves": 3}, {"max_scroll_pct": 10}, {"active_ms": 500}):
        assert score_session(_sig(portrait_cluster=40, **traces)) < BOT_THRESHOLD


def test_small_cluster_is_not_bot():
    assert score_session(_sig(portrait_cluster=PORTRAIT_CLUSTER_MIN - 1)) < BOT_THRESHOLD


def test_fingerprint_skips_mobile_and_normalizes_numbers():
    from decimal import Decimal
    from types import SimpleNamespace
    base = dict(screen_w=1920, screen_h=1080, viewport_w=1920, viewport_h=959, dpr=Decimal("1.00"),
                cpu_cores=12, device_memory=Decimal("16.0"), conn_type="4g", color_scheme="light",
                language="en-US", timezone="Asia/Shanghai")
    desktop = SimpleNamespace(device_type="desktop", **base)
    assert portrait_fingerprint("2026-10-22", desktop) == portrait_fingerprint(
        "2026-10-22", SimpleNamespace(device_type="desktop", **{**base, "dpr": 1.0, "device_memory": 16.0}))
    assert portrait_fingerprint("2026-10-22", SimpleNamespace(device_type="mobile", **base)) is None
    assert portrait_fingerprint("2026-10-22", None) is None


def test_sessionize_marks_clone_farm_and_keeps_humans():
    from app.models import BehaviorEvent, BehaviorSession, ServerSession
    from app.tasks.analytics_rollups import sessionize

    base = datetime(2026, 10, 22, 8)  # 11:00 МСК

    def portrait(i, **kw):
        row = dict(session_id_hash=f"s{i}", visitor_id_hash=f"v{i}", started_at=base + timedelta(seconds=i),
                   device_type="desktop", screen_w=1920, screen_h=1080, viewport_w=1920, viewport_h=959,
                   dpr=1, cpu_cores=12, device_memory=16, conn_type="4g", color_scheme="light",
                   language="en-US", timezone="Asia/Shanghai", ua_raw="Mozilla/5.0 Chrome/130")
        row.update(kw)
        return BehaviorSession(**row)

    def pageview(i):
        return BehaviorEvent(event_type="pageview", visitor_id_hash=f"v{i}", session_id_hash=f"s{i}",
                             occurred_at=base + timedelta(seconds=i), page="/x", params_json={})

    async def scenario(maker):
        async with maker() as db:
            for i in range(PORTRAIT_CLUSTER_MIN + 2):          # ферма: клон без ввода
                db.add(portrait(i))
                db.add(pageview(i))
            # Человек с тем же портретом, но кликнул, — не бот.
            db.add(portrait(100))
            db.add(pageview(100))
            db.add(BehaviorEvent(event_type="click", visitor_id_hash="v100", session_id_hash="s100",
                                 occurred_at=base + timedelta(seconds=105), page="/x", params_json={}))
            # Одиночный портрет без ввода — не бот (одной «пустой» сессии мало).
            db.add(portrait(200, cpu_cores=4, viewport_h=900))
            db.add(pageview(200))
            await db.commit()
            await sessionize(db, base - timedelta(minutes=5), until=base + timedelta(hours=1))
            rows = {r.visitor_id_hash: r for r in (await db.execute(select(ServerSession))).scalars()}
            assert all(rows[f"v{i}"].is_bot for i in range(PORTRAIT_CLUSTER_MIN + 2))
            assert not rows["v100"].is_bot and not rows["v200"].is_bot
    _run_with_db(scenario)


def test_stackless_rejection_is_foreign_not_ours():
    assert alerts.js_error_counts_for_alert({
        "kind": "rejection", "msg": "Object Not Found Matching Id:2, MethodName:update, ParamCount:4",
        "stack": None}) is False
    assert alerts.js_error_counts_for_alert({
        "kind": "rejection", "msg": "x", "stack": "TypeError: x\n at https://forecasteconomy.com/assets/a.js:1"}) is True


DAY = date(2026, 10, 24)


def _metrika(db, start, source, count, browser="chrome"):
    from app.models import RawMetrikaVisit
    for i in range(count):
        db.add(RawMetrikaVisit(counter_id="c", visit_id=f"m{start}-{source}-{browser}-{i}", visit_date=DAY,
                               traffic_source=source, raw_json={"ym:s:browser": browser},
                               row_hash=f"h{start}-{source}-{browser}-{i}"))


def _ours(db, channel, count, **kw):
    from app.models import ServerSession
    t0 = datetime(2026, 10, 24, 5)
    for i in range(count):
        t = t0 + timedelta(seconds=i)
        db.add(ServerSession(day=DAY, visitor_id_hash=f"o-{channel}-{kw.get('is_bot', False)}-{i}",
                             started_at=t, ended_at=t, channel=channel, **kw))


def _patch_alerts(monkeypatch, maker):
    monkeypatch.setattr(alerts, "analytics_session", maker)
    sent = []

    async def fake_alert(key, text):
        sent.append(key)
    monkeypatch.setattr(alerts, "_alert", fake_alert)
    monkeypatch.setattr("app.services.analytics_period.msk_day", lambda _dt: date(2026, 10, 26))
    return sent


def test_calibration_uses_comparable_population(monkeypatch):
    async def scenario(maker):
        async with maker() as db:
            _metrika(db, 0, "organic", 60)
            _metrika(db, 0, "referral", 10)
            _metrika(db, 0, "direct", 900)                     # ферма: не сопоставимо
            _metrika(db, 0, "organic", 5, browser="headlesschrome")
            _ours(db, "search", 70)
            _ours(db, "referral", 10)
            _ours(db, "direct", 100)                           # direct вне сверки и у нас
            _ours(db, "search", 4, is_bot=True)
            await db.commit()
        sent = _patch_alerts(monkeypatch, maker)
        out = await alerts.check_bot_calibration()
        assert out["metrika"] == 70 and out["ours"] == 80 and out["ratio_pct"] == 114
        assert out["comparable_populations"] is True
        assert sent == []                                      # 114% в коридоре, ферма-direct не мешает

        from app.services.analytics_marts import mart_botness
        from app.services.analytics_period import resolve_period
        async with maker() as db:
            res = await mart_botness(db, resolve_period("custom", "2026-10-24", "2026-10-24"))
        row = res["days"][0]
        assert row["metrika_comparable"] == 70 and row["ours_comparable"] == 80
        assert row["comparable_ratio_pct"] == 114
        assert row["ratio_pct"] != 114                         # сырое отношение сохранено отдельным полем
    _run_with_db(scenario)


def test_calibration_alerts_when_we_lose_sessions(monkeypatch):
    async def scenario(maker):
        async with maker() as db:
            _metrika(db, 1, "organic", 100)
            _ours(db, "search", 40)
            await db.commit()
        sent = _patch_alerts(monkeypatch, maker)
        out = await alerts.check_bot_calibration()
        assert out["ratio_pct"] == 40 and sent == ["bot_calibration"]
    _run_with_db(scenario)


def test_calibration_skips_small_base(monkeypatch):
    async def scenario(maker):
        async with maker() as db:
            _metrika(db, 2, "organic", 30)
            _ours(db, "search", 5)
            await db.commit()
        sent = _patch_alerts(monkeypatch, maker)
        out = await alerts.check_bot_calibration()
        assert out["skipped"] is True and sent == []
    _run_with_db(scenario)

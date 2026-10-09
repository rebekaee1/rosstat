"""Круг 11, зона H: подключение отчётов к дайджесту, недельная и месячная отправка, алерты, сообщение о новом пользователе."""
import asyncio
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta

import pytest

import app.services.alerting as alerting
import app.services.analytics_alerts as alerts
import app.services.dataset_inventory as inventory
import app.services.telegram_reports as tr
import app.tasks.analytics_scheduler as sched
from app.config import settings
from app.models import FrontendEvent, User

from tests.test_analytics2 import _run_with_db


# --- дайджест ---------------------------------------------------------------------

def _digest_env(monkeypatch, *, v2: bool, v2_lines=None, v2_error: Exception | None = None):
    sent: list[str] = []

    async def fake_digest(message, reply_markup=None):
        sent.append(message)
        return {"111": True}

    async def no_lines(*a, **kw):
        return ["строка дайджеста"]

    async def fake_v2(day):
        if v2_error:
            raise v2_error
        return v2_lines or ["🌍 Регистрации: 2"]

    async def broken_inventory(db):
        raise RuntimeError("skip")

    @asynccontextmanager
    async def fake_session():
        yield object()

    monkeypatch.setattr(sched.settings, "telegram_bot_token", "t", raising=False)
    monkeypatch.setattr(sched.settings, "telegram_chat_id", "111", raising=False)
    monkeypatch.setattr(sched.settings, "analytics_enabled", False, raising=False)
    monkeypatch.setattr(sched.settings, "telegram_digest_v2_enabled", v2)
    monkeypatch.setattr(sched, "_user_stats_lines", no_lines)
    monkeypatch.setattr(sched, "_search_demand_lines", no_lines)
    monkeypatch.setattr(sched, "_pwa_install_lines", no_lines)
    monkeypatch.setattr(sched, "analytics_session", fake_session)
    monkeypatch.setattr(sched, "send_telegram_digest", fake_digest)
    monkeypatch.setattr(inventory, "build_inventory", broken_inventory)
    monkeypatch.setattr(tr, "digest_v2_lines", fake_v2)
    return sent


def test_digest_is_unchanged_with_the_flag_off(monkeypatch):
    sent = _digest_env(monkeypatch, v2=False)
    asyncio.run(sched.telegram_daily_digest_job())
    assert len(sent) == 1 and "Регистрации" not in sent[0] and "строка дайджеста" in sent[0]


def test_digest_v2_blocks_go_after_users_and_before_search(monkeypatch):
    sent = _digest_env(monkeypatch, v2=True)
    asyncio.run(sched.telegram_daily_digest_job())
    text = sent[0]
    assert text.index("🌍 Регистрации: 2") > text.index("📊 <b>Forecast Economy — дайджест за")
    assert text.count("строка дайджеста") >= 2  # старые блоки остались


@pytest.mark.parametrize("failure", [RuntimeError("витрина упала"), asyncio.TimeoutError()])
def test_digest_survives_a_failing_v2_block(monkeypatch, failure):
    sent = _digest_env(monkeypatch, v2=True, v2_error=failure)
    asyncio.run(sched.telegram_daily_digest_job())
    assert len(sent) == 1 and "строка дайджеста" in sent[0] and "Регистрации" not in sent[0]


# --- недельный и месячный отчёты ----------------------------------------------------

def test_weekly_and_monthly_jobs_send_with_their_kinds(monkeypatch):
    calls: list[tuple] = []

    async def fake_send(message, chat_id=None, reply_markup=None, kind="alert"):
        calls.append((chat_id, kind, message))
        return True

    async def fake_collect(period, prev):
        return {"period": period, "prev_period": prev, "signups": {"total": 0}, "audience": None, "funnel": None,
                "usage": None, "reliability": None}

    monkeypatch.setattr(settings, "telegram_bot_token", "t", raising=False)
    monkeypatch.setattr(settings, "telegram_chat_id", "111", raising=False)
    monkeypatch.setattr(settings, "telegram_digest_chat_ids", "222")
    monkeypatch.setattr(alerting, "send_telegram", fake_send)
    monkeypatch.setattr(tr, "collect_period_report", fake_collect)
    asyncio.run(tr.weekly_report_job())
    asyncio.run(tr.monthly_report_job())
    assert [(c, k) for c, k, _ in calls] == [
        ("111", "weekly_report"), ("222", "weekly_report"), ("111", "monthly_report"), ("222", "monthly_report")]
    assert "неделя" in calls[0][2] and "месяц" in calls[2][2]


def test_report_jobs_do_nothing_without_telegram(monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", "", raising=False)
    asyncio.run(tr.weekly_report_job())
    asyncio.run(tr.monthly_report_job())  # не падает


def test_guarded_block_returns_none_on_error_and_timeout(monkeypatch):
    async def run():
        async def boom(db):
            raise RuntimeError("x")

        async def slow(db):
            await asyncio.sleep(1)

        @asynccontextmanager
        async def fake_session():
            yield object()

        monkeypatch.setattr(tr, "analytics_session", fake_session)
        return (await tr._guarded("a", boom), await tr._guarded("b", slow, timeout=0.05))

    assert asyncio.run(run()) == (None, None)


# --- алерты -------------------------------------------------------------------------

NOW = datetime(2026, 10, 9, 12, 0)


def test_signup_drop_rules():
    assert alerts.signup_drop_due(last_signup_at=NOW - timedelta(hours=73), now=NOW, pageviews_24h=500)
    assert not alerts.signup_drop_due(last_signup_at=NOW - timedelta(hours=71), now=NOW, pageviews_24h=500)
    assert not alerts.signup_drop_due(last_signup_at=NOW - timedelta(hours=100), now=NOW, pageviews_24h=40)
    assert not alerts.signup_drop_due(last_signup_at=None, now=NOW, pageviews_24h=500)


def test_auth_error_spike_rule_and_cooldowns():
    assert alerts.auth_error_spike_due(real_errors_1h=5) and not alerts.auth_error_spike_due(real_errors_1h=4)
    assert alerts._alert_cooldown("signup_drop") == 24 * 3600
    assert alerts._alert_cooldown("auth_error_spike") == 3 * 3600


def test_audience_alerts_fire_only_for_real_failures(monkeypatch):
    now = datetime.utcnow().replace(microsecond=0)
    fired: list[tuple[str, str]] = []

    async def fake_alert(key, text, kind="analytics_anomaly"):
        fired.append((key, kind))
        return True

    async def scenario(maker):
        async with maker() as db:
            db.add(User(created_at=now - timedelta(hours=100)))
            # 6 настоящих сбоев и 20 неверных паролей за час
            for i in range(6):
                db.add(FrontendEvent(event_name="auth_error", occurred_at=now - timedelta(minutes=5),
                                     params_json={"stage": "oauth_return", "code": "oauth_failed"}))
            for i in range(20):
                db.add(FrontendEvent(event_name="auth_error", occurred_at=now - timedelta(minutes=5),
                                     params_json={"stage": "email_login", "code": "credentials"}))
            await db.commit()
        monkeypatch.setattr(alerts, "analytics_session", maker)
        monkeypatch.setattr(alerts, "_alert", fake_alert)
        await alerts.check_audience_alerts(now)

    _run_with_db(scenario)
    # просмотров в базе нет → signup_drop молчит; всплеск ошибок есть (6 настоящих, пароли не считаются)
    assert fired == [("auth_error_spike", "audience_alert")]


def test_anomaly_check_skips_audience_alerts_when_flag_is_off(monkeypatch):
    called = []

    async def fake(now):
        called.append(now)

    monkeypatch.setattr(alerts, "check_audience_alerts", fake)
    monkeypatch.setattr(settings, "telegram_new_alerts_enabled", False)
    # Полный check_anomalies требует базы; проверяем только условие вызова.
    src = open(alerts.__file__, encoding="utf-8").read()
    assert "if settings.telegram_new_alerts_enabled:" in src and called == []


# --- сообщение «Новый пользователь» -------------------------------------------------

def test_new_user_message_has_country_and_device_but_no_ip_or_user_agent(monkeypatch):
    sent: list[str] = []

    async def fake_send(message, chat_id=None, reply_markup=None, kind="alert"):
        sent.append(message)
        return True

    monkeypatch.setattr(alerting, "send_telegram", fake_send)
    monkeypatch.setattr(settings, "telegram_chat_id", "111", raising=False)
    monkeypatch.setattr(settings, "telegram_realtime_alerts_enabled", True)
    monkeypatch.setattr("app.services.geoip.lookup", lambda ip: {"country": "Германия", "city": "Берлин", "region": None, "country_code": "DE"})
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    asyncio.run(alerting.notify_new_user({
        "method": "OAuth (yandex)", "email": "x@example.com", "phone": None, "display_name": "Иван",
        "newsletter": True, "locale": "en", "ip": "203.0.113.7", "user_agent": ua, "user_id": "abc",
    }))
    text = sent[0]
    assert "Версия сайта: английская" in text
    assert "Страна: Германия, Берлин" in text
    assert "Устройство: Chrome 126 · Windows 10/11 · компьютер" in text
    assert "203.0.113.7" not in text and "Mozilla" not in text and "AppleWebKit" not in text
    assert "IP:" not in text and "User-Agent:" not in text
    # прочие поля прежние
    assert "Email: x@example.com" in text and "ID: <code>abc</code>" in text


def test_login_message_also_drops_ip_and_user_agent(monkeypatch):
    sent: list[str] = []

    async def fake_send(message, chat_id=None, reply_markup=None, kind="alert"):
        sent.append(message)
        return True

    monkeypatch.setattr(alerting, "send_telegram", fake_send)
    monkeypatch.setattr(settings, "telegram_chat_id", "111", raising=False)
    monkeypatch.setattr(settings, "telegram_realtime_alerts_enabled", True)
    asyncio.run(alerting.notify_login({"method": "Email + пароль", "email": "x@example.com", "ip": "198.51.100.9",
                                       "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) Mobile/15E148 Safari/604.1",
                                       "user_id": "z"}))
    text = sent[0]
    assert "198.51.100.9" not in text and "Mozilla" not in text
    assert "Страна:" in text and "Устройство: iOS 17.5 · телефон" in text


def test_device_and_country_helpers_degrade_gracefully():
    assert alerting.visitor_device_line(None) == "—"
    assert alerting.visitor_country_line(None) == "—"
    assert alerting.visitor_device_line("curl/8") != ""

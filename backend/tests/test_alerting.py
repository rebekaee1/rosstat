"""Маршрутизация Telegram-алертов (звонки 2026-06-21/22).

Инвариант: ETL-ошибки и сводки идут ТОЛЬКО на primary (`telegram_chat_id`,
= rebekaee1). Дайджест в 9:00 рассылается всем (`digest_recipients`, включая
skrakan). skrakan не должен получать ошибки ETL — этот тест ловит регрессию,
если кто-то переведёт `alert_etl_*` на broadcast.
"""

import asyncio

import app.services.alerting as alerting


def _capture_send(monkeypatch):
    calls: list = []

    async def fake_send(message, chat_id=None):
        calls.append(chat_id)
        return True

    monkeypatch.setattr(alerting, "send_telegram", fake_send)
    return calls


def test_etl_alerts_go_to_primary_only(monkeypatch):
    calls = _capture_send(monkeypatch)
    asyncio.run(alerting.alert_etl_failure("key-rate", "boom"))
    asyncio.run(alerting.alert_etl_summary(89, 7, ["key-rate"], 525.0))
    # chat_id=None → send_telegram уходит в settings.telegram_chat_id (primary).
    # Явный digest-получатель сюда никогда не подставляется.
    assert calls == [None, None]


def test_realtime_user_and_feedback_alerts_primary_only(monkeypatch):
    calls = _capture_send(monkeypatch)
    monkeypatch.setattr(alerting.settings, "telegram_realtime_alerts_enabled", True)
    asyncio.run(alerting.notify_new_user({"method": "email"}))
    asyncio.run(alerting.notify_feedback({"message": "hi"}))
    assert calls == [None, None]


def test_digest_broadcasts_to_all_recipients(monkeypatch):
    monkeypatch.setattr(alerting.settings, "telegram_bot_token", "x", raising=False)
    monkeypatch.setattr(alerting.settings, "telegram_chat_id", "111", raising=False)
    monkeypatch.setattr(alerting.settings, "telegram_digest_chat_ids", "222,333", raising=False)
    calls = _capture_send(monkeypatch)
    res = asyncio.run(alerting.send_telegram_digest("digest"))
    assert calls == ["111", "222", "333"]
    assert set(res) == {"111", "222", "333"}


def test_digest_recipients_dedup_and_order(monkeypatch):
    monkeypatch.setattr(alerting.settings, "telegram_chat_id", "111", raising=False)
    monkeypatch.setattr(
        alerting.settings, "telegram_digest_chat_ids", "111, 222 ,222,333", raising=False
    )
    assert alerting.digest_recipients() == ["111", "222", "333"]

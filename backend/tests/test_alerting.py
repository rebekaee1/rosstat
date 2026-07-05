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

    async def fake_send(message, chat_id=None, reply_markup=None, kind="alert"):
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


def test_interactive_authorized_includes_owner_and_report_recipients(monkeypatch):
    """Кнопки/CSV — владельцу + получателям отчёта (skrakan), не только владельцу."""
    monkeypatch.setattr(alerting.settings, "telegram_chat_id", "433221767", raising=False)
    monkeypatch.setattr(alerting.settings, "telegram_digest_chat_ids", "703822898", raising=False)
    monkeypatch.setattr(alerting.settings, "pulse_chat_id", "", raising=False)
    assert alerting.interactive_authorized_ids() == {"433221767", "703822898"}
    # pulse_chat_id тоже допускается (LLM-отчёт владельцу)
    monkeypatch.setattr(alerting.settings, "pulse_chat_id", "999", raising=False)
    assert alerting.interactive_authorized_ids() == {"433221767", "703822898", "999"}


def test_send_telegram_archives_to_outbox(monkeypatch):
    """Каждая отправка полностью архивируется в telegram_outbox (2026-07-04).

    Проверяем контракт: archive() вызывается с текстом как отправлен, kind,
    результатом и payload'ом (клавиатура). HTTP мокаем на успех.
    """
    import app.services.telegram_outbox as outbox

    archived: list[dict] = []

    async def fake_archive(**kwargs):
        archived.append(kwargs)

    monkeypatch.setattr(outbox, "archive", fake_archive)
    monkeypatch.setattr(alerting.settings, "telegram_bot_token", "t", raising=False)
    monkeypatch.setattr(alerting.settings, "telegram_chat_id", "111", raising=False)

    class _Resp:
        status_code = 200
        text = ""
        def json(self):
            return {"ok": True, "result": {"message_id": 42}}

    class _Client:
        def __init__(self, *a, **kw): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **kw): return _Resp()

    monkeypatch.setattr(alerting.httpx, "AsyncClient", _Client)

    ok = asyncio.run(alerting.send_telegram(
        "тест", reply_markup={"inline_keyboard": []}, kind="etl_summary"
    ))
    assert ok is True
    assert len(archived) == 1
    rec = archived[0]
    assert rec["chat_id"] == "111"
    assert rec["kind"] == "etl_summary"
    assert rec["text"] == "тест"
    assert rec["ok"] is True
    assert rec["telegram_message_id"] == 42
    assert "reply_markup" in rec["payload"]


def test_archive_never_breaks_send(monkeypatch):
    """Сбой архивации не роняет отправку (уведомление важнее записи о нём)."""
    import app.services.telegram_outbox as outbox

    async def broken_session():
        raise RuntimeError("db down")

    monkeypatch.setattr(outbox, "async_session", broken_session)
    # archive не должен бросить исключение
    asyncio.run(outbox.archive(chat_id="1", method="sendMessage", text="x", ok=True))

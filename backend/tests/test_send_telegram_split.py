"""E3 (круг 11): `send_telegram` режет длинный текст (дайджест уходил одним куском)."""
import asyncio

import app.services.alerting as alerting
import app.services.telegram_outbox as outbox


def _install(monkeypatch, status=200):
    posted: list[dict] = []
    archived: list[dict] = []

    class _Resp:
        status_code = status

        def json(self):
            return {"ok": True, "result": {"message_id": len(posted)}}

    class _Client:
        def __init__(self, *a, **kw): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

        async def post(self, url, **kw):
            posted.append(kw["json"])
            return _Resp()

    async def begin(**kwargs):
        archived.append(kwargs)
        return len(archived)

    async def finish(row_id, **kwargs):
        return None

    monkeypatch.setattr(alerting.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(alerting.settings, "telegram_bot_token", "t", raising=False)
    monkeypatch.setattr(alerting.settings, "telegram_chat_id", "111", raising=False)
    monkeypatch.setattr(outbox, "archive_begin", begin)
    monkeypatch.setattr(outbox, "archive_finish", finish)
    return posted, archived


def test_short_message_goes_in_one_piece(monkeypatch):
    posted, archived = _install(monkeypatch)
    assert asyncio.run(alerting.send_telegram("коротко", kind="digest")) is True
    assert len(posted) == 1 and posted[0]["text"] == "коротко"
    assert len(archived) == 1 and archived[0]["kind"] == "digest"


def test_long_digest_is_split_keeps_keyboard_on_last_and_archives_each_part(monkeypatch):
    posted, archived = _install(monkeypatch)
    lines = [f"• строка дайджеста номер {i} с подробностями" for i in range(300)]
    text = "📊 <b>дайджест</b>\n" + "\n".join(lines) + "\n<blockquote expandable>" + "\n".join(lines[:100]) + "</blockquote>"
    assert len(text) > 8000
    kb = {"inline_keyboard": [[{"text": "m", "callback_data": "menu"}]]}
    assert asyncio.run(alerting.send_telegram(text, reply_markup=kb, kind="digest")) is True
    assert len(posted) >= 3
    for part in posted:
        assert len(part["text"]) <= 4096
        assert part["text"].count("<blockquote") == part["text"].count("</blockquote>")
    assert [("reply_markup" in p) for p in posted] == [False] * (len(posted) - 1) + [True]
    assert len(archived) == len(posted)
    assert all(a["kind"] == "digest" for a in archived)


def test_split_return_is_false_if_any_part_fails(monkeypatch):
    posted, archived = _install(monkeypatch)
    calls = {"n": 0}

    async def flaky(token, payload, kind):
        calls["n"] += 1
        return calls["n"] != 2

    monkeypatch.setattr(alerting, "_send_one", flaky)
    text = "\n".join(f"строка {i} " + "x" * 80 for i in range(200))
    assert asyncio.run(alerting.send_telegram(text)) is False
    assert calls["n"] >= 3  # остальные части всё равно отправлены

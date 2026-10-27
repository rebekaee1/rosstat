"""Повтор без разметки, когда Telegram не разобрал HTML (400 «can't parse entities»).

Инцидент: pulse_digest 17.10 и 27.10 — в LLM-сводке «норма < 2500 мс» (сырой «<»),
Telegram отвергал весь текст, отчёт терялся. Проверка: повтор уходит текстом без тегов.
"""
import asyncio

import app.services.telegram_bot as tb
import app.services.telegram_outbox as outbox

_PARSE_ERR = (
    'HTTP 400: {"ok":false,"error_code":400,"description":"Bad Request: '
    'can\'t parse entities: Unsupported start tag \\"\\" at byte offset 2416"}'
)


def _install(monkeypatch, responses):
    sent: list[dict] = []
    items = list(responses)

    async def fake_api(method, payload, files=None):
        sent.append(dict(payload))
        item = items.pop(0)
        tb._last_api_error.set(item.get("error"))
        return item.get("data")

    async def begin(**kwargs):
        return 1

    async def finish(row_id, **kwargs):
        return None

    monkeypatch.setattr(tb, "_api", fake_api)
    monkeypatch.setattr(tb.settings, "telegram_bot_token", "t", raising=False)
    monkeypatch.setattr(outbox, "archive_begin", begin)
    monkeypatch.setattr(outbox, "archive_finish", finish)
    return sent


def test_plain_fallback_keeps_raw_less_than_and_strips_real_tags():
    text = "<b>Пульс</b>: норма < 2500 мс, <i>см. &amp; ниже</i>"
    assert tb._plain_fallback(text) == "Пульс: норма < 2500 мс, см. & ниже"


def test_parse_error_resends_as_plain_text(monkeypatch):
    sent = _install(
        monkeypatch,
        [{"data": None, "error": _PARSE_ERR}, {"data": {"ok": True, "result": {"message_id": 9}}}],
    )
    ok = asyncio.run(tb.send_message("111", "<b>Сводка</b>: норма < 2500 мс", kind="pulse_digest"))
    assert ok is True
    assert len(sent) == 2
    assert sent[0]["parse_mode"] == "HTML"
    assert "parse_mode" not in sent[1]
    assert sent[1]["text"] == "Сводка: норма < 2500 мс"


def test_other_errors_are_not_retried_as_plain(monkeypatch):
    sent = _install(monkeypatch, [{"data": None, "error": "HTTP 403: Forbidden"}])
    ok = asyncio.run(tb.send_message("111", "текст", kind="digest"))
    assert ok is False
    assert len(sent) == 1

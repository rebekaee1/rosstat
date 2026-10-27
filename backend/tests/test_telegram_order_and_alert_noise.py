"""Telegram: порядок частей при сбое, повтор файла без разметки, шум алертов (круг починки 27.10, №24).

Инциденты: pulse_digest 27.10 — часть 1 не ушла, часть 2 («Аудитория») пришла в 06:08, а
сводка в 06:22 досылкой; send_document терял файл при битой разметке подписи; алерты
«Timeout reading from redis-state», «всплеск JS-ошибок» и «цели Метрики разошлись»
приходили повторами.
"""
import asyncio

import pytest

import app.services.alerting as alerting
import app.services.telegram_bot as tb
import app.services.telegram_outbox as outbox
import app.services.telegram_resend as resend
from app.services import analytics_alerts as alerts

_PARSE_ERR = (
    'HTTP 400: {"ok":false,"error_code":400,"description":"Bad Request: '
    'can\'t parse entities: Unsupported start tag at byte offset 5"}'
)
_NET_ERR = "ReadTimeout: "


def _long_text(parts_min: int = 2) -> str:
    text = "\n".join(f"строка {i} " + "x" * 80 for i in range(200))
    assert len(tb._split_telegram_text(text)) >= parts_min
    return text


def _install_bot(monkeypatch, outcomes):
    """outcomes: список ('ok'|ошибка) по порядку вызовов _api."""
    sent: list[dict] = []
    unsent: list[tuple[str, dict]] = []
    items = list(outcomes)

    async def fake_api(method, payload, files=None):
        sent.append({"method": method, **payload})
        item = items.pop(0)
        if item == "ok":
            tb._last_api_error.set(None)
            return {"ok": True, "result": {"message_id": len(sent)}}
        tb._last_api_error.set(item)
        return None

    async def begin(**kwargs):
        return len(sent) + 1

    async def finish(row_id, **kwargs):
        return None

    async def fake_unsent(*, chat_id, method, kind, parts):
        unsent.extend(parts)

    monkeypatch.setattr(tb, "_api", fake_api)
    monkeypatch.setattr(tb.settings, "telegram_bot_token", "t", raising=False)
    monkeypatch.setattr(outbox, "archive_begin", begin)
    monkeypatch.setattr(outbox, "archive_finish", finish)
    monkeypatch.setattr(outbox, "archive_unsent_parts", fake_unsent)
    return sent, unsent


# --- порядок частей -------------------------------------------------------

def test_failed_first_part_holds_back_the_rest_for_ordered_resend(monkeypatch):
    sent, unsent = _install_bot(monkeypatch, [_NET_ERR])
    text = _long_text(3)
    kb = {"inline_keyboard": [[{"text": "m", "callback_data": "menu"}]]}
    assert asyncio.run(tb.send_message("111", text, reply_markup=kb, kind="pulse_digest")) is False
    chunks = tb._split_telegram_text(text)
    assert len(sent) == 1, "после упавшей части вперёд неё ничего не уходит"
    assert [t for t, _ in unsent] == chunks[1:]
    # клавиатура осталась на последней части
    assert ["reply_markup" in p for _, p in unsent] == [False] * (len(chunks) - 2) + [True]


def test_permanent_error_of_a_part_does_not_block_the_rest(monkeypatch):
    sent, unsent = _install_bot(monkeypatch, ["HTTP 403: Forbidden", "ok", "ok", "ok", "ok"])
    text = _long_text(2)
    n = len(tb._split_telegram_text(text))
    assert asyncio.run(tb.send_message("111", text, kind="pulse_digest")) is True
    assert len(sent) == n and unsent == []


def test_second_part_failure_keeps_first_delivered(monkeypatch):
    sent, unsent = _install_bot(monkeypatch, ["ok", _NET_ERR])
    text = _long_text(3)
    assert asyncio.run(tb.send_message("111", text, kind="pulse_digest")) is True
    assert len(sent) == 2 and len(unsent) == len(tb._split_telegram_text(text)) - 2


def test_outbox_hold_rule():
    assert outbox.should_hold_next_parts(_NET_ERR) is True
    assert outbox.should_hold_next_parts("HTTP 502: bad gateway") is True
    assert outbox.should_hold_next_parts("HTTP 429: retry") is True
    assert outbox.should_hold_next_parts(None) is True
    assert outbox.should_hold_next_parts("HTTP 400: nope") is False


def test_alerting_send_telegram_holds_rest_and_archives_unsent(monkeypatch):
    posted: list[str] = []
    unsent: list[tuple[str, dict]] = []

    async def one(token, payload, kind):
        posted.append(payload["text"])
        alerting._last_send_error.set(_NET_ERR)
        return False

    async def fake_unsent(*, chat_id, method, kind, parts):
        unsent.extend(parts)

    monkeypatch.setattr(alerting, "_send_one", one)
    monkeypatch.setattr(outbox, "archive_unsent_parts", fake_unsent)
    monkeypatch.setattr(alerting.settings, "telegram_bot_token", "t", raising=False)
    monkeypatch.setattr(alerting.settings, "telegram_chat_id", "111", raising=False)
    text = _long_text(3)
    assert asyncio.run(alerting.send_telegram(text, kind="digest")) is False
    chunks = tb._split_telegram_text(text)
    assert posted == [chunks[0]] and [t for t, _ in unsent] == chunks[1:]


def test_resend_does_not_send_later_part_when_earlier_one_fails(monkeypatch):
    sent_texts: list[str] = []

    async def fake_send(message, chat_id=None, reply_markup=None, kind="alert"):
        sent_texts.append(message)
        return False

    now = resend._utcnow()
    from datetime import timedelta

    def row(i, text):
        return resend.OutboxRow(
            id=i, sent_at=now - timedelta(minutes=30), chat_id="111", kind="pulse_digest",
            text=text, ok=False, error=_NET_ERR,
        )

    plan = resend.plan_resend(
        [row(1, "часть 1"), row(2, "часть 2")], now=now, min_age=timedelta(minutes=5),
        max_tries=3, limit=10,
    )
    assert [r.text for r, _ in plan] == ["часть 1", "часть 2"]

    monkeypatch.setattr(alerting, "send_telegram", fake_send)
    monkeypatch.setattr(resend.settings, "telegram_bot_token", "t", raising=False)
    monkeypatch.setattr(resend.settings, "telegram_chat_id", "111", raising=False)

    class _Result:
        def all(self):
            from types import SimpleNamespace

            return [
                SimpleNamespace(
                    id=r.id, sent_at=r.sent_at, chat_id=r.chat_id, kind=r.kind, text=r.text,
                    ok=r.ok, error=r.error, payload_json=None,
                )
                for r, _ in plan
            ]

    class _DB:
        async def execute(self, *a, **kw):
            return type("R", (), {"rowcount": 0, "all": _Result().all})()

        async def commit(self):
            return None

    class _Ctx:
        async def __aenter__(self):
            return _DB()

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(resend, "async_session", lambda: _Ctx())
    stats = asyncio.run(resend.telegram_resend_job())
    assert sent_texts == ["часть 1"], "часть 2 не должна обогнать упавшую часть 1"
    assert stats["failed"] == 1


# --- send_document ---------------------------------------------------------

def test_send_document_retries_without_markup_on_parse_error(monkeypatch):
    sent, _ = _install_bot(monkeypatch, [_PARSE_ERR, "ok"])
    ok = asyncio.run(tb.send_document("111", "a.csv", b"x", caption="<b>Файл</b>: норма < 5", kind="x"))
    assert ok is True
    assert sent[0]["parse_mode"] == "HTML"
    assert "parse_mode" not in sent[1] and sent[1]["caption"] == "Файл: норма < 5"


def test_send_document_does_not_retry_other_errors(monkeypatch):
    sent, _ = _install_bot(monkeypatch, ["HTTP 403: Forbidden"])
    assert asyncio.run(tb.send_document("111", "a.csv", b"x", caption="<b>Файл</b>")) is False
    assert len(sent) == 1


# --- _send_one: повтор без разметки ---------------------------------------

def test_alerting_send_one_retries_plain_on_parse_error(monkeypatch):
    attempts = {"n": 0}

    async def fake_retry(fn, **kw):
        # реально вызываем лямбду из _send_one, чтобы увидеть, что уходит в Telegram
        await fn()
        attempts["n"] += 1
        if attempts["n"] == 1:
            return None, _PARSE_ERR, 1

        class _Resp:
            def json(self):
                return {"result": {"message_id": 7}}

        return _Resp(), None, 1

    posted: list[dict] = []

    class _Client:
        def __init__(self, *a, **kw): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

        async def post(self, url, **kw):
            posted.append(kw["json"])

    async def begin(**kwargs):
        return 1

    async def finish(row_id, **kwargs):
        return None

    monkeypatch.setattr(alerting, "request_with_retry", fake_retry)
    monkeypatch.setattr(alerting.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(outbox, "archive_begin", begin)
    monkeypatch.setattr(outbox, "archive_finish", finish)

    payload = {"chat_id": "1", "text": "<b>сбой</b>: норма < 5", "parse_mode": "HTML"}
    assert asyncio.run(alerting._send_one("t", payload, "alert")) is True
    assert posted[0]["parse_mode"] == "HTML"
    assert "parse_mode" not in posted[1] and posted[1]["text"] == "сбой: норма < 5"


# --- redis-state: опрос и алерты планировщика ------------------------------

def test_poll_skips_cycle_when_state_redis_times_out_and_uses_memory_offset(monkeypatch):
    from redis.exceptions import TimeoutError as RedisTimeout

    class _Redis:
        def __init__(self):
            self.sets = []

        async def get(self, key):
            raise RedisTimeout("Timeout reading from redis-state:6379")

        async def set(self, key, value):
            raise RedisTimeout("Timeout reading from redis-state:6379")

    redis = _Redis()

    async def fake_state():
        return redis

    api_payloads: list[dict] = []

    async def fake_api(method, payload, files=None):
        api_payloads.append(payload)
        return {"result": []}

    monkeypatch.setattr(tb, "get_state_redis", fake_state)
    monkeypatch.setattr(tb, "_api", fake_api)
    monkeypatch.setattr(tb.settings, "telegram_bot_token", "t", raising=False)
    monkeypatch.setattr(tb, "interactive_authorized_ids", lambda: {"1"})

    monkeypatch.setattr(tb, "_offset_mem", None)
    asyncio.run(tb.telegram_poll_job())  # не бросает и не стучится в Telegram
    assert api_payloads == []

    monkeypatch.setattr(tb, "_offset_mem", "42")
    asyncio.run(tb.telegram_poll_job())
    assert api_payloads[0]["offset"] == 42


def test_poll_keeps_new_offset_in_memory_if_redis_write_fails(monkeypatch):
    from redis.exceptions import TimeoutError as RedisTimeout

    class _Redis:
        async def get(self, key):
            return "10"

        async def set(self, key, value):
            raise RedisTimeout("Timeout reading from redis-state:6379")

    async def fake_state():
        return _Redis()

    async def fake_api(method, payload, files=None):
        return {"result": [{"update_id": 10}]}

    async def fake_handle(msg):
        return None

    monkeypatch.setattr(tb, "get_state_redis", fake_state)
    monkeypatch.setattr(tb, "_api", fake_api)
    monkeypatch.setattr(tb.settings, "telegram_bot_token", "t", raising=False)
    monkeypatch.setattr(tb, "interactive_authorized_ids", lambda: {"1"})
    monkeypatch.setattr(tb, "_offset_mem", None)
    asyncio.run(tb.telegram_poll_job())
    assert tb._offset_mem == "11"


def test_scheduler_success_resets_transient_streak(monkeypatch):
    import app.main as main

    sent = []

    async def fake_send(msg, kind=None):
        sent.append(msg)

    monkeypatch.setattr("app.services.alerting.send_telegram", fake_send)
    monkeypatch.setattr(main, "_shutting_down", False)
    monkeypatch.setattr(main.scheduler, "get_job", lambda job_id: None)
    main._scheduler_alert_last.clear()
    main._scheduler_transient_streak.clear()

    class _Fail:
        job_id = "indexnow_drain"
        exception = TimeoutError("Timeout reading from redis-state:6379")

    class _Ok:
        job_id = "indexnow_drain"
        exception = None

    async def run(fn, ev):
        fn(ev)
        await asyncio.sleep(0)

    for _ in range(3):  # сбой, успех, сбой, успех, сбой — подряд ни разу дважды
        asyncio.run(run(main._scheduler_event_listener, _Fail()))
        asyncio.run(run(main._scheduler_job_succeeded_listener, _Ok()))
    assert sent == []
    asyncio.run(run(main._scheduler_event_listener, _Fail()))
    asyncio.run(run(main._scheduler_event_listener, _Fail()))
    assert len(sent) == 1


# --- шум analytics_anomaly --------------------------------------------------

def test_js_error_episode_alerts_once_until_it_subsides():
    assert alerts.js_error_episode(12, sticky=False) == "alert"
    assert alerts.js_error_episode(27, sticky=True) == "hold"
    assert alerts.js_error_episode(5, sticky=True) == "hold"
    assert alerts.js_error_episode(2, sticky=True) == "clear"
    assert alerts.js_error_episode(2, sticky=False) == "hold"
    assert alerts.js_error_episode(10, sticky=False) == "alert"


def test_js_error_top_messages_counts_only_own_errors():
    rows = [
        {"kind": "error", "msg": "Cannot read properties of undefined", "src": "https://forecasteconomy.com/a.js"},
        {"kind": "error", "msg": "Cannot read  properties of undefined"},
        {"kind": "error", "msg": "Other"},
        {"kind": "error", "msg": "ad", "src": "https://mc.yandex.ru/x.js"},
        {"kind": "resource", "msg": "img"},
    ]
    assert alerts.js_error_top_messages(rows) == [
        ("Cannot read properties of undefined", 2), ("Other", 1),
    ]


def test_chronic_alert_kinds_have_weekly_cooldown():
    week = 7 * 24 * 3600
    assert alerts._alert_cooldown("webmaster_data_missing:forecasteconomy.com:in_search") == week
    assert alerts._alert_cooldown("metrika_goals_stray:ab12cd34") == week


def test_stray_goals_alert_key_follows_the_set_of_events(monkeypatch):
    import hashlib

    keys: list[str] = []

    async def fake_alert(key, text, kind="analytics_anomaly"):
        keys.append(key)
        return True

    monkeypatch.setattr(alerts, "_alert", fake_alert)

    # ровно тот код, что в sync_metrika_goals: ключ строится из отсортированного набора
    def key_for(events):
        names = sorted(set(events))
        return "metrika_goals_stray:" + hashlib.sha1(",".join(names).encode("utf-8")).hexdigest()[:8]

    a = key_for(["pwa_app_launch", "api_interest_view"])
    assert a == key_for(["api_interest_view", "pwa_app_launch", "api_interest_view"])
    assert a != key_for(["api_interest_view", "pwa_app_launch", "new_event"])
    assert alerts._alert_cooldown(a) == 7 * 24 * 3600


@pytest.mark.parametrize("n_events", [3, 12])
def test_sync_metrika_goals_stray_alert_text_and_key(monkeypatch, n_events):
    """Сквозная проверка sync_metrika_goals: ключ с набором событий, текст с подсказкой."""
    from app.tasks import analytics_rollups as rollups

    events = [f"stray_event_{i:02d}" for i in range(n_events)]
    goals = [
        {"id": 1000 + i, "name": e, "type": "action", "conditions": [{"type": "exact", "url": e}]}
        for i, e in enumerate(events)
    ]

    class _Resp:
        data = {"goals": goals}

    class _Client:
        async def goals(self, counter_id):
            return _Resp()

    class _DB:
        def __init__(self):
            self.added = []

        async def get(self, model, pk):
            return None

        def add(self, obj):
            self.added.append(obj)

        async def execute(self, stmt):
            return None

        async def commit(self):
            return None

    captured: list[tuple[str, str]] = []

    async def fake_alert(key, text, kind="analytics_anomaly"):
        captured.append((key, text))
        return True

    monkeypatch.setattr(rollups.settings, "yandex_metrika_read_token", "t", raising=False)
    monkeypatch.setattr(rollups.settings, "analytics_allowed_counter_ids", "1", raising=False)
    monkeypatch.setattr("app.services.yandex_metrika_management.MetrikaManagementClient", lambda: _Client())
    monkeypatch.setattr(alerts, "_alert", fake_alert)
    monkeypatch.setattr(rollups, "is_conversion", lambda name: False)

    assert asyncio.run(rollups.sync_metrika_goals(_DB())) == n_events
    (key, text), = captured
    assert key.startswith("metrika_goals_stray:") and len(key.split(":")[1]) == 8
    assert "stray_event_00" in text and "macro/micro" in text
    assert ("и ещё 2" in text) is (n_events == 12)

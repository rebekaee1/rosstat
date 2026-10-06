"""Надёжность Telegram-уведомлений (2026-10-04): повтор, досылка, зависшие pending.

Архив за неделю: 115 из 409 сообщений не доставлено (`All connection attempts
failed`, `ConnectTimeout`), ~10 строк навсегда `pending`. Тесты фиксируют
контракт: временные сбои повторяются, постоянные (400/403/404) — нет, недоставленное
досылается без дублей, а зависший `pending` получает итоговый статус.
"""
import asyncio
import io
from datetime import datetime, timedelta, timezone

import httpx
import pytest

import app.services.alerting as alerting
import app.services.telegram_bot as tb
import app.services.telegram_outbox as outbox
import app.services.telegram_resend as resend
import app.services.telegram_retry as retry
from app.models import TelegramOutbox


# ---------------------------------------------------------------------------
# Общие подмены HTTP-клиента
# ---------------------------------------------------------------------------

class _Resp:
    def __init__(self, status_code=200, body=None, text=""):
        self.status_code = status_code
        self._body = body if body is not None else (
            {"ok": True, "result": {"message_id": 42}} if status_code == 200 else {"ok": False}
        )
        self.text = text or str(self._body)
        self.headers = {}

    def json(self):
        return self._body


def _install_client(monkeypatch, module, script):
    """AsyncClient.post отдаёт элементы script по очереди (исключение — бросается)."""
    calls: list[dict] = []
    items = list(script)

    class _Client:
        def __init__(self, *a, **kw): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

        async def post(self, url, **kw):
            calls.append(kw)
            item = items.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item

    monkeypatch.setattr(module.httpx, "AsyncClient", _Client)
    return calls


@pytest.fixture
def tg(monkeypatch):
    """Токен/чат заданы, архив подменён, паузы записываются, а не ждутся."""
    monkeypatch.setattr(alerting.settings, "telegram_bot_token", "t", raising=False)
    monkeypatch.setattr(alerting.settings, "telegram_chat_id", "111", raising=False)
    monkeypatch.setattr(alerting.settings, "telegram_send_max_attempts", 3)
    monkeypatch.setattr(alerting.settings, "telegram_send_retry_base_seconds", 1.0)
    monkeypatch.setattr(alerting.settings, "telegram_send_retry_budget_seconds", 45.0)
    state = {"finished": [], "sleeps": []}

    async def fake_begin(**kwargs):
        return 7

    async def fake_finish(row_id, **kwargs):
        state["finished"].append(kwargs)

    async def fake_sleep(seconds):
        state["sleeps"].append(seconds)

    monkeypatch.setattr(outbox, "archive_begin", fake_begin)
    monkeypatch.setattr(outbox, "archive_finish", fake_finish)
    monkeypatch.setattr(retry, "_sleep", fake_sleep)
    return state


# ---------------------------------------------------------------------------
# 1. Повтор отправки
# ---------------------------------------------------------------------------

def test_retry_on_connect_timeout_then_success(monkeypatch, tg):
    calls = _install_client(monkeypatch, alerting, [
        httpx.ConnectTimeout(""), httpx.ConnectError("All connection attempts failed"), _Resp(200),
    ])
    assert asyncio.run(alerting.send_telegram("hi", kind="digest")) is True
    assert len(calls) == 3
    assert tg["sleeps"] == [1.0, 2.0]  # растущая пауза
    # одна архивная строка на всю отправку, итог — успех с message_id
    assert len(tg["finished"]) == 1
    assert tg["finished"][0]["ok"] is True and tg["finished"][0]["telegram_message_id"] == 42


def test_retry_gives_up_after_max_attempts_and_names_error(monkeypatch, tg):
    calls = _install_client(monkeypatch, alerting, [httpx.ConnectTimeout("")] * 3)
    assert asyncio.run(alerting.send_telegram("hi")) is False
    assert len(calls) == 3
    err = tg["finished"][0]["error"]
    assert tg["finished"][0]["ok"] is False
    assert err.startswith("ConnectTimeout") and "попыток: 3" in err


def test_retry_on_server_error_5xx(monkeypatch, tg):
    calls = _install_client(monkeypatch, alerting, [_Resp(502, text="Bad Gateway"), _Resp(200)])
    assert asyncio.run(alerting.send_telegram("hi")) is True
    assert len(calls) == 2


@pytest.mark.parametrize("status", [400, 403, 404])
def test_no_retry_on_permanent_error(monkeypatch, tg, status):
    calls = _install_client(monkeypatch, alerting, [_Resp(status, text="Forbidden: bot was blocked")])
    assert asyncio.run(alerting.send_telegram("hi")) is False
    assert len(calls) == 1 and tg["sleeps"] == []
    assert tg["finished"][0]["error"].startswith(f"HTTP {status}")


def test_retry_after_on_429_is_respected(monkeypatch, tg):
    flood = _Resp(429, body={"ok": False, "error_code": 429,
                             "parameters": {"retry_after": 3}}, text="Too Many Requests")
    calls = _install_client(monkeypatch, alerting, [flood, _Resp(200)])
    assert asyncio.run(alerting.send_telegram("hi")) is True
    assert len(calls) == 2
    assert tg["sleeps"] == [3.0]  # ровно столько, сколько просит Telegram


def test_retry_after_longer_than_budget_defers_to_resend(monkeypatch, tg):
    flood = _Resp(429, body={"ok": False, "parameters": {"retry_after": 300}}, text="flood")
    calls = _install_client(monkeypatch, alerting, [flood, _Resp(200)])
    assert asyncio.run(alerting.send_telegram("hi")) is False
    assert len(calls) == 1 and tg["sleeps"] == []  # не ждём 5 минут в вызывающем
    assert tg["finished"][0]["error"].startswith("HTTP 429")


def test_send_still_works_when_archive_is_down(monkeypatch):
    """Архив недоступен — отправка и повтор не ломаются (archive_* не бросают)."""
    monkeypatch.setattr(alerting.settings, "telegram_bot_token", "t", raising=False)
    monkeypatch.setattr(alerting.settings, "telegram_chat_id", "111", raising=False)

    async def broken_session():
        raise RuntimeError("db down")

    async def fake_sleep(seconds):
        pass

    monkeypatch.setattr(outbox, "async_session", broken_session)
    monkeypatch.setattr(retry, "_sleep", fake_sleep)
    calls = _install_client(monkeypatch, alerting, [httpx.ConnectTimeout(""), _Resp(200)])
    assert asyncio.run(alerting.send_telegram("hi")) is True
    assert len(calls) == 2


def test_bot_api_retries_send_but_not_polling(monkeypatch, tg):
    monkeypatch.setattr(tb.settings, "telegram_bot_token", "t", raising=False)
    calls = _install_client(monkeypatch, tb, [httpx.ReadTimeout(""), _Resp(200)])
    assert asyncio.run(tb._api("sendMessage", {"chat_id": "1", "text": "x"})) is not None
    assert len(calls) == 2
    calls = _install_client(monkeypatch, tb, [httpx.ReadTimeout(""), _Resp(200)])
    assert asyncio.run(tb._api("getUpdates", {"timeout": 0})) is None
    assert len(calls) == 1  # поллер идёт по кругу сам


def test_bot_send_document_rewinds_file_on_retry(monkeypatch, tg):
    monkeypatch.setattr(tb.settings, "telegram_bot_token", "t", raising=False)
    positions: list[int] = []
    stream = io.BytesIO(b"csv-data")

    class _Client:
        def __init__(self, *a, **kw): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

        async def post(self, url, **kw):
            positions.append(kw["files"]["document"][1].tell())
            kw["files"]["document"][1].read()  # как это делает httpx
            if len(positions) == 1:
                raise httpx.ConnectError("All connection attempts failed")
            return _Resp(200)

    monkeypatch.setattr(tb.httpx, "AsyncClient", _Client)
    data = asyncio.run(tb._api("sendDocument", {"chat_id": "1"}, files={"document": ("a.csv", stream)}))
    assert data is not None
    assert positions == [0, 0]


def test_bot_send_message_archives_real_error(monkeypatch, tg):
    """В архив уходит причина (HTTP-код/класс), а не «send failed (см. логи)»."""
    monkeypatch.setattr(tb.settings, "telegram_bot_token", "t", raising=False)
    _install_client(monkeypatch, tb, [_Resp(403, text="Forbidden: bot was blocked by the user")])
    assert asyncio.run(tb.send_message("1", "hi", kind="pulse_digest")) is False
    assert tg["finished"][0]["error"].startswith("HTTP 403")


# ---------------------------------------------------------------------------
# 2. Досылка: чистое планирование
# ---------------------------------------------------------------------------

NOW = datetime(2026, 10, 4, 12, 0, 0)


def _row(id, minutes_ago, *, ok=False, error="ConnectTimeout: ", text="msg", chat="1", kind="digest"):
    return resend.OutboxRow(
        id=id, sent_at=NOW - timedelta(minutes=minutes_ago), chat_id=chat,
        kind=kind, text=text, ok=ok, error=error,
    )


def _plan(rows, **kw):
    params = dict(now=NOW, min_age=timedelta(minutes=10), max_tries=3, limit=10)
    params.update(kw)
    return resend.plan_resend(rows, **params)


def test_plan_resends_undelivered_old_message():
    plan = _plan([_row(1, 30)])
    assert [r.id for r, _ in plan] == [1]


def test_plan_dedup_skips_when_already_delivered():
    # Исходная попытка упала, досылка (позже) дошла — повторно не шлём.
    rows = [_row(1, 40), _row(2, 25, ok=True, error=None)]
    assert _plan(rows) == []


def test_plan_earlier_success_with_same_text_is_a_different_message():
    # Успех ДО неудачи — другое сообщение с тем же текстом: недоставленное шлём.
    rows = [_row(1, 120, ok=True, error=None), _row(2, 30)]
    assert [r.id for r, _ in _plan(rows)] == [2]


def test_plan_key_separates_chat_and_kind():
    rows = [_row(1, 30, chat="1"), _row(2, 25, chat="2", ok=True, error=None),
            _row(3, 30, kind="new_user")]
    assert sorted(r.id for r, _ in _plan(rows)) == [1, 3]


def test_plan_skips_fresh_permanent_and_exhausted():
    assert _plan([_row(1, 3)]) == []                                  # ещё в полёте
    assert _plan([_row(1, 30, error="HTTP 403: Forbidden: bot was blocked")]) == []
    assert _plan([_row(1, 30, error="HTTP 400: Bad Request")]) == []
    assert _plan([_row(1, 30, error="HTTP 429: Too Many Requests")]) != []
    # исходная отправка + 3 досылки провалились → хватит
    assert _plan([_row(i, 50 - i * 5) for i in range(1, 5)]) == []
    assert _plan([_row(i, 50 - i * 5) for i in range(1, 4)]) != []


def test_plan_respects_per_run_limit_oldest_first():
    rows = [_row(i, 60 - i, text=f"m{i}") for i in range(1, 6)]
    plan = _plan(rows, limit=2)
    assert [r.id for r, _ in plan] == [1, 2]


def test_plan_pending_is_candidate_only_after_min_age():
    assert _plan([_row(1, 5, error="pending")]) == []
    assert [r.id for r, _ in _plan([_row(1, 20, error="pending")])] == [1]


# ---------------------------------------------------------------------------
# 2b. Досылка и итоговый статус pending на реальной (SQLite) схеме
# ---------------------------------------------------------------------------

def _seed(auth_env, specs):
    """specs: [(minutes_ago, kwargs)] → id строк."""
    async def _run():
        ids = []
        async with auth_env["session_maker"]() as db:
            for minutes_ago, kw in specs:
                row = TelegramOutbox(
                    sent_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=minutes_ago),
                    chat_id=kw.get("chat_id", "111"), method=kw.get("method", "sendMessage"),
                    kind=kw.get("kind", "digest"), text=kw.get("text", "report"),
                    payload_json=kw.get("payload"), ok=kw.get("ok", False),
                    error=kw.get("error", "ConnectTimeout: "),
                )
                db.add(row)
                await db.flush()
                ids.append(row.id)
            await db.commit()
        return ids
    return asyncio.run(_run())


def _fetch(auth_env):
    from sqlalchemy import select

    async def _run():
        async with auth_env["session_maker"]() as db:
            return {r.id: r for r in (await db.execute(select(TelegramOutbox))).scalars().all()}
    return asyncio.run(_run())


@pytest.fixture
def job_env(auth_env, monkeypatch):
    monkeypatch.setattr(resend.settings, "telegram_bot_token", "t", raising=False)
    monkeypatch.setattr(resend.settings, "telegram_chat_id", "111", raising=False)
    monkeypatch.setattr(resend, "async_session", auth_env["session_maker"])
    sent: list[dict] = []

    async def fake_send(message, chat_id=None, reply_markup=None, kind="alert"):
        sent.append({"text": message, "chat_id": chat_id, "reply_markup": reply_markup, "kind": kind})
        # как настоящий send_telegram: успешная отправка оставляет строку ok=true
        async with auth_env["session_maker"]() as db:
            db.add(TelegramOutbox(
                chat_id=str(chat_id), method="sendMessage", kind=kind, text=message,
                ok=True, error=None,
            ))
            await db.commit()
        return True

    monkeypatch.setattr(alerting, "send_telegram", fake_send)
    auth_env["sent"] = sent
    return auth_env


def test_resend_job_sends_once_and_marks_redelivered(job_env):
    kb = {"inline_keyboard": [[{"text": "x", "callback_data": "y"}]]}
    ids = _seed(job_env, [
        (45, {"text": "digest-1", "payload": {"parse_mode": "HTML", "reply_markup": kb}}),
        # тот же текст/чат: исходный провал, потом успех — не слать
        (50, {"text": "digest-2", "chat_id": "222"}),
        (40, {"text": "digest-2", "chat_id": "222", "ok": True, "error": None}),
        # не важный вид, файл и постоянная ошибка — не слать
        (45, {"text": "reply", "kind": "bot_reply"}),
        (45, {"text": "file", "kind": "digest", "method": "sendDocument"}),
        (45, {"text": "blocked", "kind": "new_user", "error": "HTTP 403: Forbidden: bot was blocked"}),
        # старше окна в 6 часов — не слать
        (7 * 60, {"text": "ancient"}),
    ])
    stats = asyncio.run(resend.telegram_resend_job())
    sent = job_env["sent"]
    assert [(s["text"], s["chat_id"], s["kind"]) for s in sent] == [("digest-1", "111", "digest")]
    assert sent[0]["reply_markup"] == kb  # клавиатура сохранена
    assert stats["resent"] == 1 and stats["candidates"] == 1
    rows = _fetch(job_env)
    assert rows[ids[0]].error == resend.REDELIVERED_ERROR
    assert rows[ids[2]].ok is True
    # повторный запуск — дублей нет: ok=true строка закрывает логическое сообщение
    again = asyncio.run(resend.telegram_resend_job())
    assert again["candidates"] == 0 and len(job_env["sent"]) == 1


def test_resend_job_failed_resend_is_counted_not_duplicated(job_env, monkeypatch):
    _seed(job_env, [(30, {"text": "digest-1"})])

    async def failing_send(message, chat_id=None, reply_markup=None, kind="alert"):
        return False

    monkeypatch.setattr(alerting, "send_telegram", failing_send)
    stats = asyncio.run(resend.telegram_resend_job())
    assert stats["failed"] == 1 and stats["resent"] == 0


def test_stale_pending_gets_final_status_and_fresh_pending_is_left(job_env):
    ids = _seed(job_env, [
        (90, {"text": "dead", "kind": "bot_reply", "error": "pending"}),
        (20, {"text": "slow", "kind": "bot_reply", "error": "pending"}),
    ])
    stats = asyncio.run(resend.telegram_resend_job())
    rows = _fetch(job_env)
    assert stats["finalized"] == 1
    assert rows[ids[0]].error == resend.PENDING_FINAL_ERROR and rows[ids[0]].ok is False
    assert rows[ids[1]].error == "pending"


def test_pending_digest_older_than_hour_is_finalized_then_resent(job_env):
    ids = _seed(job_env, [(90, {"text": "digest-x", "error": "pending"})])
    stats = asyncio.run(resend.telegram_resend_job())
    assert stats["finalized"] == 1 and stats["resent"] == 1
    assert [s["text"] for s in job_env["sent"]] == ["digest-x"]
    assert _fetch(job_env)[ids[0]].error == resend.REDELIVERED_ERROR


def test_resend_job_is_noop_without_telegram_config(monkeypatch):
    monkeypatch.setattr(resend.settings, "telegram_bot_token", "", raising=False)
    assert asyncio.run(resend.telegram_resend_job())["candidates"] == 0


# ---------------------------------------------------------------------------
# 3. Дайджест без блока инвентаризации при сбое
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("failure", [
    RuntimeError("canceling statement due to statement timeout"),
    asyncio.TimeoutError(),
])
def test_digest_is_sent_without_inventory_block_on_failure(monkeypatch, failure):
    from contextlib import asynccontextmanager

    import app.services.dataset_inventory as inventory
    import app.tasks.analytics_scheduler as sched

    sent: list[str] = []

    async def fake_digest(message, reply_markup=None):
        sent.append(message)
        return {"111": True}

    async def no_lines(*a, **kw):
        return ["строка дайджеста"]

    async def broken_inventory(db):
        raise failure

    @asynccontextmanager
    async def fake_session():
        yield object()

    monkeypatch.setattr(sched.settings, "telegram_bot_token", "t", raising=False)
    monkeypatch.setattr(sched.settings, "telegram_chat_id", "111", raising=False)
    monkeypatch.setattr(sched.settings, "analytics_enabled", False, raising=False)
    monkeypatch.setattr(sched, "_user_stats_lines", no_lines)
    monkeypatch.setattr(sched, "_search_demand_lines", no_lines)
    monkeypatch.setattr(sched, "_pwa_install_lines", no_lines)
    monkeypatch.setattr(sched, "analytics_session", fake_session)
    monkeypatch.setattr(sched, "send_telegram_digest", fake_digest)
    monkeypatch.setattr(inventory, "build_inventory", broken_inventory)

    asyncio.run(sched.telegram_daily_digest_job())
    assert len(sent) == 1
    assert "дайджест за" in sent[0] and "строка дайджеста" in sent[0]
    assert "Датасет" not in sent[0]


def test_digest_pwa_line_format(monkeypatch):
    """Одна строка про приложение: установки (люди) и запуски из значка."""
    from contextlib import asynccontextmanager
    from datetime import date

    import app.services.analytics_marts as marts
    import app.tasks.analytics_scheduler as sched

    @asynccontextmanager
    async def fake_session():
        yield object()

    async def fake_mart(db, period):
        assert period.start_date == period.end_date == date(2026, 10, 5)
        return {"totals": {"installs": 3, "launch_visitors": 7}}

    monkeypatch.setattr(sched, "analytics_session", fake_session)
    monkeypatch.setattr(marts, "mart_pwa_installs", fake_mart)
    lines = asyncio.run(sched._pwa_install_lines(date(2026, 10, 5)))
    assert len(lines) == 1
    assert "Установок приложения вчера: 3 (запусков из иконки: 7)" in lines[0]

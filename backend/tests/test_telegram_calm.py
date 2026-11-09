"""Спокойный режим Telegram (решение владельца 08.11.2026): срочное сразу, техническое — утренней сводкой."""
import asyncio
from datetime import date

import fakeredis.aioredis
import pytest

import app.core.cache as cache_mod
import app.services.alerting as alerting
import app.services.telegram_outbox as outbox
from app.services import http_error_monitor as monitor
from app.services import telegram_calm as calm


@pytest.fixture
def tg(monkeypatch):
    """Включённый спокойный режим, фальшивые Telegram и архив."""
    posted: list[dict] = []
    archived: list[dict] = []

    class _Resp:
        status_code = 200

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
        archived.append({**kwargs, "stage": "begin"})
        return len(archived)

    async def finish(row_id, **kwargs):
        return None

    async def one_step(**kwargs):
        archived.append({**kwargs, "stage": "archive"})

    monkeypatch.setattr(alerting.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(alerting.settings, "telegram_bot_token", "t", raising=False)
    monkeypatch.setattr(alerting.settings, "telegram_chat_id", "111", raising=False)
    monkeypatch.setattr(alerting.settings, "telegram_calm_mode", True, raising=False)
    monkeypatch.setattr(outbox, "archive_begin", begin)
    monkeypatch.setattr(outbox, "archive_finish", finish)
    monkeypatch.setattr(outbox, "archive", one_step)
    return posted, archived


def test_technical_alert_is_held_not_sent(tg):
    posted, archived = tg
    assert asyncio.run(alerting.send_telegram("🔴 <b>ETL Failed</b>\nIndicator: cpi", kind="etl_failure")) is True
    assert posted == []
    assert archived == [{
        "chat_id": "111", "method": calm.HELD_METHOD, "kind": "etl_failure",
        "text": "🔴 <b>ETL Failed</b>\nIndicator: cpi", "ok": False, "error": calm.HELD_ERROR, "stage": "archive",
    }]


@pytest.mark.parametrize("kind", ["site_down", "site_up", "disk_space", "prod_config_alert",
                                  "new_user", "feedback", "digest", "pulse_digest", "weekly_report"])
def test_urgent_people_and_reports_go_now(tg, kind):
    posted, _ = tg
    assert asyncio.run(alerting.send_telegram("текст", kind=kind)) is True
    assert len(posted) == 1


def test_calm_mode_off_sends_everything(tg, monkeypatch):
    posted, _ = tg
    monkeypatch.setattr(alerting.settings, "telegram_calm_mode", False, raising=False)
    asyncio.run(alerting.send_telegram("x", kind="http_5xx_spike"))
    assert len(posted) == 1


def test_other_chat_is_not_held(tg):
    posted, _ = tg
    asyncio.run(alerting.send_telegram("x", chat_id="222", kind="etl_summary"))
    assert len(posted) == 1


def test_held_rows_are_invisible_to_resend():
    """Досылка выбирает только `method == "sendMessage"`: отложенное не уйдёт повтором."""
    import inspect

    from app.services import telegram_resend

    assert 'TelegramOutbox.method == "sendMessage"' in inspect.getsource(telegram_resend.telegram_resend_job)
    assert calm.HELD_METHOD != "sendMessage"


# --- «сайт не открывается» -------------------------------------------------

@pytest.fixture
def down(monkeypatch):
    monkeypatch.setattr(alerting.settings, "telegram_calm_mode", True, raising=False)
    monkeypatch.setattr(cache_mod, "_state_redis", fakeredis.aioredis.FakeRedis(decode_responses=True))
    monkeypatch.setattr(monitor, "_local_hits", {monitor.KIND_ERROR: [], monitor.KIND_SHED: []})
    monkeypatch.setattr(monitor, "_local_last_alert", {monitor.KIND_ERROR: float("-inf"), monitor.KIND_SHED: float("-inf")})
    monkeypatch.setattr(monitor, "_inflight", 0)
    calls: list[tuple[str, str]] = []

    async def fake_send(message, chat_id=None, reply_markup=None, kind="alert"):
        calls.append((kind, message))
        return True

    monkeypatch.setattr(alerting, "send_telegram", fake_send)
    return calls


def _errors(start: float, seconds: int, every: float = 5.0):
    async def run():
        t = start
        while t < start + seconds:
            await monitor.note(monitor.KIND_ERROR, "/ru/russia", now=t)
            t += every
    asyncio.run(run())


def test_short_burst_is_not_site_down(down):
    _errors(1_000.0, 300)  # 5 минут ошибок
    assert [k for k, _ in down] == ["http_5xx_spike"]


def test_long_outage_sends_site_down_once(down):
    _errors(1_000.0, 900)  # 15 минут без перерыва
    kinds = [k for k, _ in down]
    assert kinds.count("site_down") == 1
    text = next(t for k, t in down if k == "site_down")
    assert "Сайт не открывается" in text and "Что сделать" in text


def test_gap_restarts_the_clock(down):
    _errors(1_000.0, 420)          # 7 минут
    _errors(1_000.0 + 420 + 240, 420)  # перерыв 4 минуты, ещё 7 минут
    assert "site_down" not in [k for k, _ in down]


def test_recovery_message_after_site_down(down):
    async def run():
        r = await cache_mod.get_state_redis()
        await r.set("fe:site_down:alerted", "0")
        await calm.check_site_recovered()
        await calm.check_site_recovered()  # второй раз — тишина
    asyncio.run(run())
    assert [k for k, _ in down] == ["site_up"]


def test_no_recovery_while_errors_continue(down):
    async def run():
        r = await cache_mod.get_state_redis()
        await r.set("fe:site_down:alerted", "0")
        await r.set("fe:site_down:since", "0")
        await calm.check_site_recovered()
    asyncio.run(run())
    assert down == []


# --- утренняя сводка --------------------------------------------------------

def test_empty_summary_is_calm():
    text = calm.build_summary([], day=date(2026, 11, 9))
    assert "Утренняя сводка, 9 ноября" in text
    assert "Тебе ничего делать не нужно" in text
    assert "🔴" not in text


def test_summary_groups_in_plain_words_without_red():
    rows = [
        ("http_5xx_spike", "🔴 <b>Всплеск ошибок сервера (5xx)</b>\n12 ответов 5xx за 5 мин (последний путь: /x)"),
        ("load_shed", "🟡 <b>Сервер сбрасывает нагрузку</b>\n60 страниц"),
        ("host_pressure", "🟠 <b>Диск хоста тормозит</b>\n..."),
        ("host_pressure", "🟢 <b>Диск хоста снова в норме</b>\nДлилось около 7 мин."),
        ("etl_summary", "🔴 <b>Ежедневная выгрузка</b>\nВсего: 143\nобновлено: 6\nисточник недоступен: 45"),
        ("etl_failure", "🔴 <b>ETL Failed</b>\nIndicator: <code>cpi</code>"),
        ("scheduler_alert", "🔴 <b>Job failed</b>\nJob: sitemap_build"),
    ]
    text = calm.build_summary(rows, day=date(2026, 11, 9))
    head = text.split("<blockquote", 1)[0]
    assert "🔴" not in head and "🟠" not in head
    assert "Тебе ничего делать не нужно" in head
    assert "короткие всплески ошибок сервера — 1 раз" in head
    assert "диск сервера притормаживал — 1 раз" in head  # «снова в норме» не считается проблемой
    assert "обновлено 6 из 143" in head and "45 ждут, пока источник снова откроется" in head
    assert "показатели не обновились — 1 раз" in head
    assert "сбои фоновых задач — 1 раз" in head
    assert "ETL" not in head and "5xx" not in head
    assert "<blockquote expandable>" in text
    assert len(text) <= calm.MESSAGE_LIMIT


def test_summary_mentions_urgent_and_does_not_claim_calm_site():
    text = calm.build_summary([], day=date(2026, 11, 9), urgent_sent=1)
    assert "Срочное за сутки: 1" in text
    assert "Сайт работал" not in text


def test_held_and_urgent_kinds_do_not_overlap():
    assert not calm.HELD_KINDS & calm.URGENT_KINDS
    assert set(calm.KIND_LABELS) >= calm.HELD_KINDS


def test_summary_does_not_say_nothing_to_do_when_action_is_waiting():
    # 09.11.2026: сводка начиналась с «Тебе ничего делать не нужно», а ниже лежало «напиши Claude «почисти битые точки»».
    rows = [
        ("data_sanity", "🟡 <b>В базе есть точки, которых не может быть</b>\n192 точек у 27 рядов"),
        ("token_expired", "🟠 <b>Истёк доступ к Яндекс Вебмастеру</b>\nПока токен не обновлён…"),
        ("load_shed", "🟡 <b>Сервер сбрасывает нагрузку</b>\n50 страниц"),
    ]
    text = calm.build_summary(rows, day=date(2026, 11, 9))
    assert "ничего делать не нужно" not in text
    assert "Нужно от тебя:" in text and "почисти битые точки" in text
    # токен Вебмастера владелец обновить не может (09.11.2026): в «нужно от тебя» его нет
    assert "токен" not in text.split("\n")[1]


def test_action_kinds_are_held():
    assert set(calm.ACTION_KINDS) <= calm.HELD_KINDS

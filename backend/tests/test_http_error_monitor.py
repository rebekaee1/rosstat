"""Алерт «Всплеск ошибок сервера (5xx)»: общий счёт процессов и разделение настоящих ошибок и сброса очереди рендера.

Инцидент 2026-11-02: 325 ответов 503 за сутки (намеренный сброс очереди холодного рендера на фоне стопоров диска хоста)
давали по три алерта подряд (три воркера uvicorn, у каждого свой счётчик и свой cooldown) и выглядели как поломка сервера.
"""

import asyncio

import fakeredis.aioredis
import pytest

import app.core.cache as cache_mod
import app.services.alerting as alerting
from app.services import http_error_monitor as monitor


@pytest.fixture
def sent(monkeypatch):
    """Подменяет state-Redis на fakeredis, сбрасывает память процесса и собирает отправленные алерты."""
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


def _forget_process(monkeypatch):
    """Как другой воркер uvicorn: общий Redis тот же, память процесса чистая."""
    monkeypatch.setattr(monitor, "_local_hits", {monitor.KIND_ERROR: [], monitor.KIND_SHED: []})
    monkeypatch.setattr(monitor, "_local_last_alert", {monitor.KIND_ERROR: float("-inf"), monitor.KIND_SHED: float("-inf")})


def test_real_errors_alert_once_across_processes(sent, monkeypatch):
    async def run():
        for i in range(12):
            if i % 4 == 0:
                _forget_process(monkeypatch)  # три «воркера» по четыре ответа: по отдельности порога нет
            await monitor.note(monitor.KIND_ERROR, f"/api/v1/x/{i}", now=1_000.0 + i)

    asyncio.run(run())
    assert [kind for kind, _ in sent] == ["http_5xx_spike"]
    assert "10 ответов 5xx за 5 мин" in sent[0][1]
    assert "последний путь: /api/v1/x/9" in sent[0][1]


def test_below_threshold_is_silent(sent):
    async def run():
        for i in range(9):
            await monitor.note(monitor.KIND_ERROR, "/api/v1/x", now=1_000.0 + i)

    asyncio.run(run())
    assert sent == []


def test_old_hits_leave_the_window(sent):
    async def run():
        for i in range(9):
            await monitor.note(monitor.KIND_ERROR, "/api/v1/x", now=1_000.0 + i)
        await monitor.note(monitor.KIND_ERROR, "/api/v1/x", now=1_000.0 + 400)  # прежние ответы старше 5 минут

    asyncio.run(run())
    assert sent == []


def test_shed_has_own_higher_threshold_and_kind(sent):
    async def run():
        for i in range(49):
            await monitor.note(monitor.KIND_SHED, "/seo/world-indicator-year/x/y/2010", now=2_000.0 + i)
        before = list(sent)
        await monitor.note(monitor.KIND_SHED, "/seo/world-indicator-year/x/y/2011", now=2_049.0)
        return before

    before = asyncio.run(run())
    assert before == []
    assert [kind for kind, _ in sent] == ["load_shed"]
    text = sent[0][1]
    assert "🟡" in text and "защита, а не поломка" in text and "/2011" in text


def test_shed_does_not_trigger_the_error_alert(sent):
    async def run():
        for i in range(30):
            await monitor.note(monitor.KIND_SHED, "/seo/world-indicator-year/x/y/2010", now=3_000.0 + i)

    asyncio.run(run())
    assert sent == []


def test_cooldown_blocks_second_alert(sent):
    async def run():
        for i in range(30):
            await monitor.note(monitor.KIND_ERROR, "/api/v1/x", now=4_000.0 + i)

    asyncio.run(run())
    assert [kind for kind, _ in sent] == ["http_5xx_spike"]


def test_falls_back_to_process_window_when_redis_is_down(sent, monkeypatch):
    async def broken():
        raise ConnectionError("redis-state is down")

    monkeypatch.setattr(cache_mod, "get_state_redis", broken)

    async def run():
        for i in range(12):
            await monitor.note(monitor.KIND_ERROR, "/api/v1/x", now=5_000.0 + i)

    asyncio.run(run())
    # Redis недоступен: считаем внутри процесса, шлём один раз (антиспам fail-open, но местный cooldown держит)
    assert [kind for kind, _ in sent] == ["http_5xx_spike"]


def test_path_is_html_escaped(sent):
    async def run():
        for i in range(10):
            await monitor.note(monitor.KIND_ERROR, "/seo/<script>", now=6_000.0 + i)

    asyncio.run(run())
    assert "&lt;script&gt;" in sent[0][1] and "<script>" not in sent[0][1]


def test_shed_response_is_marked_and_counted_apart():
    """503 очереди рендера несёт метку `X-FE-Cache: shed`; middleware ведёт его отдельный счётчик."""
    from app.api.seo_pages import _html_response
    from app.main import HttpStatusCounterMiddleware as M

    assert _html_response(503, "busy").headers["x-fe-cache"] == "shed"
    assert _html_response(404, "<html>nf</html>").headers.get("x-fe-cache") is None

    shed_before, five_before = M.shed_total, M.counters["5xx"]
    M._record(503, "/seo/world-indicator-year/a/b/2010", shed=True)
    M._record(500, "/api/v1/x")
    assert M.shed_total == shed_before + 1
    assert M.counters["5xx"] == five_before + 2

"""Серверные всплески 5xx: общий счёт всех процессов backend и один Telegram-алерт.

Раньше `HttpStatusCounterMiddleware` считал 5xx внутри процесса: при трёх воркерах uvicorn один всплеск давал
три алерта подряд (02.11.2026 в 00:00 пришли в 00:00:36, :46 и :54), а сумма ошибок, разложенная по процессам, порога
не достигала. Кроме того, намеренный сброс очереди холодного рендера (`X-FE-Cache: shed`, 503 + Retry-After) считался
такой же «ошибкой сервера», как настоящая 500, хотя это работающая защита от перегрузки (см. `seo_pages._acquire_render_slot`).

Теперь ответы делятся на два вида, у каждого свой порог и свой алерт:

* `error` — настоящие 5xx (500, 502, 504, 503 не из сброса: нехватка соединений БД, недоступный каталог);
* `shed` — намеренный сброс очереди рендера: порог выше, алерт жёлтый и редкий.

Счёт — минутные корзины в state-Redis (одна цепочка команд за ответ), антиспам — общий ключ `alert_muted`. Если Redis
недоступен или занят, работает прежнее окно внутри процесса: слепота хуже дубля.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from html import escape
from typing import Callable

logger = logging.getLogger(__name__)

KIND_ERROR = "error"
KIND_SHED = "shed"

WINDOW_SECONDS = 300
_BUCKET_SECONDS = 60
_BUCKETS = WINDOW_SECONDS // _BUCKET_SECONDS
_KEY_TTL = WINDOW_SECONDS + 2 * _BUCKET_SECONDS
# Redis не должен задерживать обработку ошибок: при его стопоре (инцидент 02.11.2026) задачи не копятся.
_REDIS_TIMEOUT = 2.0
_MAX_INFLIGHT = 64


def _error_text(count: int, path: str) -> str:
    return (
        f"🔴 <b>Всплеск ошибок сервера (5xx)</b>\n{count} ответов 5xx "
        f"за {WINDOW_SECONDS // 60} мин (последний путь: {escape(path[:120])})"
    )


def _shed_text(count: int, path: str) -> str:
    return (
        f"🟡 <b>Сервер сбрасывает нагрузку</b>\n{count} страниц за {WINDOW_SECONDS // 60} мин получили «занято» (503): "
        f"очередь рендера переполнена. Это защита, а не поломка; причину ищите в нагрузке на диск и память "
        f"хоста (последний путь: {escape(path[:120])})"
    )


@dataclass(frozen=True)
class _Rule:
    threshold: int
    cooldown_seconds: int
    outbox_kind: str  # `telegram_outbox.kind` и ключ антиспама
    text: Callable[[int, str], str]


_RULES = {
    KIND_ERROR: _Rule(threshold=10, cooldown_seconds=900, outbox_kind="http_5xx_spike", text=_error_text),
    KIND_SHED: _Rule(threshold=50, cooldown_seconds=3600, outbox_kind="load_shed", text=_shed_text),
}

# Запасной счёт внутри процесса (когда Redis недоступен) и местный антиспам.
_local_hits: dict[str, list[float]] = {KIND_ERROR: [], KIND_SHED: []}
_local_last_alert: dict[str, float] = {KIND_ERROR: float("-inf"), KIND_SHED: float("-inf")}
_inflight = 0
_tasks: set[asyncio.Task] = set()


def _local_total(kind: str, now: float) -> int:
    hits = [t for t in _local_hits[kind] if now - t < WINDOW_SECONDS]
    hits.append(now)
    _local_hits[kind] = hits
    return len(hits)


async def _shared_total(kind: str, now: float) -> int | None:
    """Сумма ответов вида за окно по всем процессам; None — Redis не ответил."""
    from app.core.cache import get_state_redis

    bucket = int(now // _BUCKET_SECONDS)
    prefix = f"fe:http_spike:{kind}:"
    try:
        r = await get_state_redis()
        async with r.pipeline(transaction=False) as pipe:
            pipe.incr(f"{prefix}{bucket}")
            pipe.expire(f"{prefix}{bucket}", _KEY_TTL)
            pipe.mget([f"{prefix}{bucket - i}" for i in range(_BUCKETS)])
            _, _, values = await asyncio.wait_for(pipe.execute(), timeout=_REDIS_TIMEOUT)
        return sum(int(v) for v in values if v)
    except Exception:  # noqa: BLE001
        logger.warning("http spike counter: Redis недоступен, считаю внутри процесса", exc_info=True)
        return None


async def note(kind: str, path: str, *, now: float | None = None) -> None:
    """Учесть один ответ 5xx и, если порог пройден, отправить алерт (один на все процессы). Не бросает исключений."""
    global _inflight
    rule = _RULES[kind]
    ts = time.time() if now is None else now
    try:
        total: int | None = None
        if _inflight < _MAX_INFLIGHT:
            _inflight += 1
            try:
                total = await _shared_total(kind, ts)
            finally:
                _inflight -= 1
        if total is None:
            total = _local_total(kind, ts)
        if total < rule.threshold or ts - _local_last_alert[kind] <= rule.cooldown_seconds:
            return
        _local_last_alert[kind] = ts
        from app.services.alerting import alert_muted, send_telegram

        if await alert_muted(rule.outbox_kind, rule.cooldown_seconds):
            return
        await send_telegram(rule.text(total, path), kind=rule.outbox_kind)
    except Exception:  # noqa: BLE001
        logger.exception("5xx spike alert failed")


def schedule(kind: str, path: str) -> None:
    """Запустить `note` в фоне; без работающего цикла событий — ничего."""
    try:
        task = asyncio.get_running_loop().create_task(note(kind, path))
    except RuntimeError:
        return
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)

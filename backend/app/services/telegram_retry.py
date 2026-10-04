"""Повтор HTTP-запроса к Bot API при временных сбоях (2026-10-04).

Раньше `send_telegram` и `telegram_bot._api` делали ровно одну попытку: за
неделю 115 из 409 сообщений не дошли (`All connection attempts failed`,
`ConnectTimeout`), при том что Telegram обычно отвечает со второй попытки.

Правила:
- повторяем: сетевые сбои (ConnectError/таймауты/NetworkError/RemoteProtocolError),
  HTTP 429 (пауза = `parameters.retry_after` Bot API / заголовок Retry-After),
  HTTP 5xx;
- НЕ повторяем: прочие 4xx (400 — битый текст, 403 — бот заблокирован,
  404 — неверный токен/чат) — повтор ничего не изменит;
- до `telegram_send_max_attempts` попыток, пауза растёт (base·2^(n-1));
  общий потолок `telegram_send_retry_budget_seconds` — вызывающий (регистрация,
  дайджест) не ждёт дольше. Если пауза не помещается в остаток бюджета — сдаёмся,
  недоставленное подберёт `telegram_resend_job`.

Модуль ничего не пишет в БД и не бросает исключений (кроме отмены задачи).
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Awaitable, Callable

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    httpx.ConnectError,        # «All connection attempts failed»
    httpx.TimeoutException,    # Connect/Read/Write/Pool timeout
    httpx.NetworkError,
    httpx.RemoteProtocolError,
)


async def _sleep(seconds: float) -> None:  # отдельная точка для тестов
    await asyncio.sleep(seconds)


def is_retryable_status(status_code: int) -> bool:
    return status_code == 429 or 500 <= status_code <= 599


def retry_after_seconds(resp) -> float | None:
    """Пауза, которую просит Telegram при 429: `parameters.retry_after` или заголовок."""
    value = None
    try:
        value = ((resp.json() or {}).get("parameters") or {}).get("retry_after")
    except Exception:  # noqa: BLE001 — тело может быть не JSON
        value = None
    if value is None:
        headers = getattr(resp, "headers", None) or {}
        try:
            value = headers.get("Retry-After")
        except Exception:  # noqa: BLE001
            value = None
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    return seconds if seconds >= 0 else None


async def request_with_retry(
    make_request: Callable[[], Awaitable[httpx.Response]],
    *,
    max_attempts: int | None = None,
    budget_seconds: float | None = None,
    base_delay: float | None = None,
) -> tuple[httpx.Response | None, str | None, int]:
    """Выполняет `make_request` с повтором. Возвращает (resp, error, attempts).

    `error is None` ⇔ получен HTTP 200. `resp` — последний полученный ответ
    (None, если все попытки закончились исключением). `make_request` вызывается
    заново на каждой попытке — тело запроса (файлы) он обязан собрать сам.
    """
    attempts_limit = max(1, int(max_attempts if max_attempts is not None
                                else settings.telegram_send_max_attempts))
    budget = float(budget_seconds if budget_seconds is not None
                   else settings.telegram_send_retry_budget_seconds)
    base = float(base_delay if base_delay is not None
                 else settings.telegram_send_retry_base_seconds)
    started = time.monotonic()
    resp: httpx.Response | None = None
    error: str | None = None
    attempt = 0

    while attempt < attempts_limit:
        attempt += 1
        delay = base * (2 ** (attempt - 1))
        try:
            resp = await make_request()
        except RETRYABLE_EXCEPTIONS as exc:
            resp = None
            # str(httpx.ConnectTimeout()) пустая — без имени класса архив молчит.
            error = f"{type(exc).__name__}: {exc}"[:230]
            logger.warning("Telegram request attempt %d/%d failed: %s",
                           attempt, attempts_limit, error)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — непредвиденное: не повторяем
            resp = None
            error = f"{type(exc).__name__}: {exc}"[:230]
            logger.warning("Telegram request failed (not retryable)", exc_info=True)
            break
        else:
            if resp.status_code == 200:
                if attempt > 1:
                    logger.info("Telegram request succeeded on attempt %d", attempt)
                return resp, None, attempt
            error = f"HTTP {resp.status_code}: {(resp.text or '')[:200]}"
            logger.warning("Telegram request attempt %d/%d failed: %s",
                           attempt, attempts_limit, error)
            if not is_retryable_status(resp.status_code):
                break  # 400/403/404 — повтор бессмыслен
            if resp.status_code == 429:
                asked = retry_after_seconds(resp)
                if asked is not None:
                    delay = asked

        if attempt >= attempts_limit:
            break
        remaining = budget - (time.monotonic() - started)
        if delay >= remaining:
            # Не помещаемся в потолок (в т.ч. длинный retry_after): отдаём досылке.
            error = f"{error} [пауза {delay:.0f}с не укладывается в {budget:.0f}с]"[:290]
            break
        await _sleep(delay)

    if attempt > 1 and error:
        error = f"{error} [попыток: {attempt}]"[:295]
    return resp, error, attempt

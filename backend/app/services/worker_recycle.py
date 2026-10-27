"""Плановый перезапуск разросшегося web-воркера uvicorn (backend, 3 воркера) — по одному и без простоя.

Факты 27.10.2026 (прод, девять суток без рестарта): воркеры по ~670–730 МБ RSS и ещё 160–185 МБ в свопе при
350–450 МБ после старта; cgroup backend 2,25 ГиБ упирается в потолок, и всплеск уникальных страниц превращается в
своп-шторм. Причину роста (утечка или фрагментация) в коде не нашли, поэтому — предохранитель: воркер, чей вес
(RSS + своп) перешёл порог, шлёт себе SIGTERM; супервизор uvicorn поднимает новый, а запросы в полёте
дорабатываются (graceful shutdown). Два воркера одновременно не уходят: перед выходом берётся замок в state-Redis
на ``min_gap_seconds``; при недоступном Redis воркер остаётся на месте (fail-safe).

Выключено, пока ``RUSTATS_WORKER_RECYCLE_MB`` равен 0 (по умолчанию). Работает только при UVICORN_WORKERS > 1:
у единственного процесса SIGTERM остановил бы контейнер.
"""
from __future__ import annotations

import asyncio
import logging
import os
import random
import signal
import time

from app.services.memory_trim import process_footprint_bytes

logger = logging.getLogger(__name__)

RECYCLE_LOCK_KEY = "fe:worker-recycle:lock"
CHECK_INTERVAL_SECONDS = 60.0
# Свежий воркер не уходит сразу: после старта вес падает/растёт ступенями, а перезапуск «по кругу» хуже роста.
MIN_UPTIME_SECONDS = 1800.0


def recycle_threshold_bytes(limit_mb: int, jitter_ratio: float) -> int:
    """Порог веса в байтах; ``jitter_ratio`` (0…0,2) разводит воркеры, чтобы они не доходили до порога одновременно."""
    if limit_mb <= 0:
        return 0
    return int(limit_mb * 1024 * 1024 * (1.0 + max(0.0, jitter_ratio)))


def should_recycle(footprint_bytes: int, threshold_bytes: int, uptime_seconds: float) -> bool:
    if threshold_bytes <= 0 or footprint_bytes <= 0:
        return False
    return uptime_seconds >= MIN_UPTIME_SECONDS and footprint_bytes >= threshold_bytes


async def _take_lock(min_gap_seconds: int) -> bool:
    try:
        from app.core.cache import get_state_redis

        redis = await get_state_redis()
        return bool(await redis.set(RECYCLE_LOCK_KEY, str(os.getpid()), nx=True, ex=max(30, int(min_gap_seconds))))
    except Exception:  # noqa: BLE001 — нет Redis: воркер остаётся (лучше рост, чем одновременный выход всех)
        logger.warning("worker recycle: замок недоступен, перезапуск отложен", exc_info=True)
        return False


async def recycle_check_once(
    *, threshold_bytes: int, started_monotonic: float, min_gap_seconds: int,
    footprint=process_footprint_bytes, take_lock=_take_lock, send_signal=os.kill, now=time.monotonic,
) -> bool:
    """Один шаг проверки. True — воркер попросил завершиться (SIGTERM себе)."""
    footprint_bytes = footprint()
    if not should_recycle(footprint_bytes, threshold_bytes, now() - started_monotonic):
        return False
    if not await take_lock(min_gap_seconds):
        return False
    logger.warning(
        "worker recycle: pid=%s вес %.0f МБ ≥ порога %.0f МБ — плавный перезапуск воркера",
        os.getpid(), footprint_bytes / 1048576, threshold_bytes / 1048576,
    )
    send_signal(os.getpid(), signal.SIGTERM)
    return True


async def recycle_loop(*, limit_mb: int, min_gap_seconds: int, workers: int) -> None:
    """Фоновая задача web-воркера. Ничего не делает при limit_mb <= 0 или единственном воркере."""
    if limit_mb <= 0 or workers < 2:
        return
    threshold = recycle_threshold_bytes(limit_mb, random.uniform(0.0, 0.15))
    started = time.monotonic()
    logger.info(
        "worker recycle включён: порог %.0f МБ (RSS+своп), замок %s с, воркеров %s",
        threshold / 1048576, min_gap_seconds, workers,
    )
    while True:
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
        try:
            if await recycle_check_once(
                threshold_bytes=threshold, started_monotonic=started, min_gap_seconds=min_gap_seconds,
            ):
                return
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — сторож памяти не должен ронять воркер
            logger.exception("worker recycle: сбой проверки")

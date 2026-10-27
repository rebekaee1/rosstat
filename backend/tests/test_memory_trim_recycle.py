"""Возврат памяти и плановый перезапуск воркера (27.10.2026, лимиты cgroup backend/scheduler)."""
from __future__ import annotations

import asyncio
import signal

from app.services import memory_trim, worker_recycle

STATUS = "Name:\tpython\nVmRSS:\t  669504 kB\nVmSwap:\t  164820 kB\nThreads:\t19\n"


def test_parse_status_counts_rss_and_swap():
    rss, swap = memory_trim.parse_status_memory(STATUS)
    assert rss == 669504 * 1024 and swap == 164820 * 1024
    assert memory_trim.parse_status_memory("Name:\tx\n") == (0, 0)


def test_trim_memory_never_raises_and_is_non_negative():
    assert memory_trim.trim_memory() >= 0


def test_threshold_and_jitter():
    assert worker_recycle.recycle_threshold_bytes(0, 0.1) == 0
    assert worker_recycle.recycle_threshold_bytes(750, 0.0) == 750 * 1024 * 1024
    assert worker_recycle.recycle_threshold_bytes(750, 0.1) > 750 * 1024 * 1024


def test_should_recycle_needs_threshold_and_uptime():
    mb = 1024 * 1024
    thr = 750 * mb
    up = worker_recycle.MIN_UPTIME_SECONDS
    assert not worker_recycle.should_recycle(900 * mb, 0, up)            # выключено
    assert not worker_recycle.should_recycle(0, thr, up)                 # вес неизвестен
    assert not worker_recycle.should_recycle(900 * mb, thr, up - 1)      # свежий воркер
    assert not worker_recycle.should_recycle(700 * mb, thr, up)          # ниже порога
    assert worker_recycle.should_recycle(900 * mb, thr, up)


def _check(footprint_mb: int, *, lock: bool, uptime: float = 4000.0):
    sent: list[tuple[int, int]] = []

    async def take(_gap):
        return lock

    result = asyncio.run(worker_recycle.recycle_check_once(
        threshold_bytes=750 * 1024 * 1024, started_monotonic=0.0, min_gap_seconds=300,
        footprint=lambda: footprint_mb * 1024 * 1024, take_lock=take,
        send_signal=lambda pid, sig: sent.append((pid, sig)), now=lambda: uptime,
    ))
    return result, sent


def test_recycle_sends_sigterm_to_self_only_with_lock():
    done, sent = _check(900, lock=True)
    assert done and len(sent) == 1 and sent[0][1] == signal.SIGTERM


def test_peer_holding_lock_keeps_worker_alive():
    done, sent = _check(900, lock=False)
    assert not done and not sent


def test_below_threshold_does_not_touch_lock():
    touched = []

    async def take(_gap):
        touched.append(1)
        return True

    done = asyncio.run(worker_recycle.recycle_check_once(
        threshold_bytes=750 * 1024 * 1024, started_monotonic=0.0, min_gap_seconds=300,
        footprint=lambda: 400 * 1024 * 1024, take_lock=take, send_signal=lambda *_: None, now=lambda: 4000.0,
    ))
    assert not done and not touched


def test_loop_is_noop_when_disabled_or_single_worker():
    asyncio.run(worker_recycle.recycle_loop(limit_mb=0, min_gap_seconds=300, workers=3))
    asyncio.run(worker_recycle.recycle_loop(limit_mb=750, min_gap_seconds=300, workers=1))

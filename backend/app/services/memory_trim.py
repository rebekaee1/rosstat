"""Возврат памяти ОС и подсчёт «веса» процесса (RSS + своп) — боевые замеры 27.10.2026.

Контейнеры backend и scheduler на проде упираются в лимит cgroup и живут в свопе (memory.events max у backend
224 тыс., в свопе ~0,9 ГиБ; scheduler 91–97 % лимита в окна обучения мировых прогнозов). glibc не отдаёт ОС
освобождённые куски кучи после numpy/statsmodels-циклов, поэтому RSS растёт ступенями. ``trim_memory`` — это
``gc.collect()`` плюс ``malloc_trim(0)``; вызывать между рядами длинных джоб, не на пути запроса.
"""
from __future__ import annotations

import ctypes
import gc
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_libc: ctypes.CDLL | None | bool = None  # None — не пробовали, False — недоступна (не glibc/не Linux)


def _load_libc() -> ctypes.CDLL | None:
    global _libc
    if _libc is None:
        try:
            lib = ctypes.CDLL("libc.so.6")
            lib.malloc_trim.argtypes = [ctypes.c_size_t]
            lib.malloc_trim.restype = ctypes.c_int
            _libc = lib
        except (OSError, AttributeError):
            _libc = False
    return _libc or None


def parse_status_memory(status_text: str) -> tuple[int, int]:
    """(VmRSS, VmSwap) в байтах из текста /proc/<pid>/status; 0 для отсутствующих строк."""
    rss = swap = 0
    for line in status_text.splitlines():
        if line.startswith("VmRSS:"):
            rss = int(line.split()[1]) * 1024
        elif line.startswith("VmSwap:"):
            swap = int(line.split()[1]) * 1024
    return rss, swap


def process_footprint_bytes() -> int:
    """RSS + своп текущего процесса, байты; 0, если /proc недоступен.

    Своп учитывается намеренно: у процесса под давлением cgroup часть страниц уже выгружена, RSS один занижает
    рабочий набор (воркер backend: RSS 670 МБ + своп 160–185 МБ).
    """
    try:
        rss, swap = parse_status_memory(Path("/proc/self/status").read_text(encoding="utf-8"))
    except (OSError, ValueError, IndexError):
        return 0
    return rss + swap


def trim_memory() -> int:
    """gc.collect() и malloc_trim(0). Возвращает число освобождённых в куче байт по RSS (0, если неизвестно)."""
    before = process_footprint_bytes()
    gc.collect()
    lib = _load_libc()
    if lib is not None:
        try:
            lib.malloc_trim(0)
        except Exception:  # noqa: BLE001 — освобождение памяти никогда не должно ронять джобу
            logger.debug("malloc_trim failed", exc_info=True)
    after = process_footprint_bytes()
    return max(before - after, 0)

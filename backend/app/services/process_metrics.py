"""RSS процесса, открытые fd и память cgroup — для /metrics и алертов."""
from __future__ import annotations

import os
from pathlib import Path

_FD_PRESSURE_RATIO = 0.8


def process_rss_bytes() -> int:
    """Текущий RSS текущего процесса, байты. 0 если неизвестно."""
    status = Path("/proc/self/status")
    if status.is_file():
        try:
            for line in status.read_text(encoding="utf-8").splitlines():
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) * 1024
        except (OSError, ValueError, IndexError):
            pass
    try:
        import resource

        rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        # Linux — килобайты, macOS — байты.
        return rss if rss > 10_000_000 else rss * 1024
    except Exception:
        return 0


def cgroup_memory() -> tuple[int, int]:
    """(usage_bytes, limit_bytes). 0,0 если не в cgroup."""
    pairs = (
        (Path("/sys/fs/cgroup/memory.current"), Path("/sys/fs/cgroup/memory.max")),
        (
            Path("/sys/fs/cgroup/memory/memory.usage_in_bytes"),
            Path("/sys/fs/cgroup/memory/memory.limit_in_bytes"),
        ),
    )
    for usage_p, limit_p in pairs:
        if not usage_p.is_file():
            continue
        try:
            usage = int(usage_p.read_text().strip())
            raw_limit = limit_p.read_text().strip() if limit_p.is_file() else "max"
            limit = 0 if raw_limit in ("max", "") else int(raw_limit)
            return usage, limit
        except (OSError, ValueError):
            continue
    return 0, 0


def _inactive_file_bytes(stat_text: str) -> int:
    """Неактивный файловый кэш из memory.stat (cgroup v2 / v1); ядро вернёт его первым."""
    for line in stat_text.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] in ("inactive_file", "total_inactive_file"):
            try:
                return int(parts[1])
            except ValueError:
                return 0
    return 0


def cgroup_working_set() -> tuple[int, int]:
    """(working_set_bytes, limit_bytes): usage минус неактивный page cache.

    memory.current включает файловый кэш, который ядро освобождает без OOM;
    алерт «память 94%» по сырому usage срабатывал на кэше, а не на утечке.
    """
    usage, limit = cgroup_memory()
    if usage <= 0 or limit <= 0:
        return usage, limit
    for stat_p in (Path("/sys/fs/cgroup/memory.stat"), Path("/sys/fs/cgroup/memory/memory.stat")):
        if stat_p.is_file():
            try:
                return max(usage - _inactive_file_bytes(stat_p.read_text()), 0), limit
            except OSError:
                break
    return usage, limit


def memory_pressure_ratio() -> float | None:
    usage, limit = cgroup_working_set()
    if usage <= 0 or limit <= 0:
        return None
    return usage / limit


def process_open_fds() -> int:
    """Число открытых дескрипторов текущего процесса. 0 если неизвестно.

    На Linux канон — ``/proc/self/fd`` (то, что видит ulimit контейнера).
    ``/dev/fd`` на macOS не полный снимок сокетов; для метрик прода это
    запасной путь.
    """
    proc_fd = Path("/proc/self/fd")
    if proc_fd.is_dir():
        try:
            return len(os.listdir(proc_fd))
        except OSError:
            pass
    try:
        return len(os.listdir("/dev/fd"))
    except OSError:
        return 0


def fd_soft_limit() -> int:
    """Soft RLIMIT_NOFILE. 0 если нет лимита или неизвестен."""
    try:
        import resource

        soft, _hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        if soft <= 0 or soft == resource.RLIM_INFINITY:
            return 0
        return int(soft)
    except Exception:
        return 0


def fd_pressure_ratio() -> float | None:
    n = process_open_fds()
    limit = fd_soft_limit()
    if n <= 0 or limit <= 0:
        return None
    return n / limit


def fd_pressure_high(*, ratio: float | None = None) -> bool:
    value = fd_pressure_ratio() if ratio is None else ratio
    return value is not None and value > _FD_PRESSURE_RATIO

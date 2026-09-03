"""RSS процесса и память cgroup — для /metrics и алертов (инцидент 2026-09-03)."""
from __future__ import annotations

from pathlib import Path


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


def memory_pressure_ratio() -> float | None:
    usage, limit = cgroup_memory()
    if usage <= 0 or limit <= 0:
        return None
    return usage / limit

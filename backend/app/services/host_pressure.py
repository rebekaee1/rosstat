"""Давление на хост (Linux PSI) и место на диске: сигнал режима экономии и причина в алертах (ADR-0026, 05.11.2026).

05.11.2026 с 06:10 UTC диск виртуальной машины отвечал по 0,5–1,5 с на операцию, PSI io `full` держался на 70–80%,
а владелец получал только пачку «Всплеск ошибок сервера (5xx)» без причины. Теперь:

* `io_degraded()` — дешёвый (файл `/proc/pressure/io`, кэш 2 с) признак «диск хоста захлёбывается»; по нему холодный
  рендер для низкоприоритетного трафика сразу отвечает «занято», не занимая слот и соединение БД;
* `describe()` — одна строка о хосте для алертов 5xx и сброса нагрузки;
* `host_health_job()` — раз в минуту в scheduler: алерт «Диск хоста тормозит» (и «снова в норме») и «Мало места на диске».

`/proc/pressure/*` в Linux не разделён по контейнерам: внутри контейнера виден весь хост (сверено на боевом 05.11.2026).
`shutil.disk_usage("/")` в контейнере отдаёт файловую систему под overlay, то есть корневой диск хоста. Нет PSI (macOS,
старое ядро) — признаки выключены, ничего не ломается.
"""

from __future__ import annotations

import logging
import shutil
import time
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger(__name__)

_PSI_DIR = "/proc/pressure"
_CACHE_SECONDS = 2.0


@dataclass(frozen=True)
class Snapshot:
    io_some10: float | None
    io_full10: float | None
    io_full60: float | None
    mem_full60: float | None
    disk_free: int | None
    disk_total: int | None

    @property
    def disk_free_pct(self) -> float | None:
        if not self.disk_free or not self.disk_total:
            return None
        return 100.0 * self.disk_free / self.disk_total


def _parse_psi(text: str) -> dict[str, dict[str, float]]:
    """`some avg10=1.00 avg60=2.00 avg300=3.00 total=…` → {"some": {"avg10": 1.0, …}, "full": {…}}."""
    out: dict[str, dict[str, float]] = {}
    for line in text.splitlines():
        parts = line.split()
        if not parts:
            continue
        values = {}
        for item in parts[1:]:
            key, _, raw = item.partition("=")
            if key.startswith("avg"):
                try:
                    values[key] = float(raw)
                except ValueError:
                    pass
        out[parts[0]] = values
    return out


def _read_psi(kind: str) -> dict[str, dict[str, float]] | None:
    try:
        with open(f"{_PSI_DIR}/{kind}", encoding="ascii") as fh:
            return _parse_psi(fh.read())
    except OSError:
        return None


def _read_snapshot() -> Snapshot:
    io = _read_psi("io") or {}
    mem = _read_psi("memory") or {}
    try:
        usage = shutil.disk_usage("/")
        free, total = usage.free, usage.total
    except OSError:
        free = total = None
    return Snapshot(
        io_some10=io.get("some", {}).get("avg10"),
        io_full10=io.get("full", {}).get("avg10"),
        io_full60=io.get("full", {}).get("avg60"),
        mem_full60=mem.get("full", {}).get("avg60"),
        disk_free=free,
        disk_total=total,
    )


_cached: tuple[float, Snapshot] | None = None


def snapshot(*, fresh: bool = False) -> Snapshot:
    global _cached
    now = time.monotonic()
    if not fresh and _cached is not None and now - _cached[0] < _CACHE_SECONDS:
        return _cached[1]
    snap = _read_snapshot()
    _cached = (now, snap)
    return snap


def io_degraded() -> bool:
    """Диск хоста захлёбывается: доля времени, когда ВСЕ задачи ждали ввода-вывода, за 10 с не ниже порога."""
    threshold = settings.host_brownout_io_full_pct
    if threshold <= 0:
        return False
    full10 = snapshot().io_full10
    return full10 is not None and full10 >= threshold


def _gb(n: int) -> str:
    return f"{n / 1024 ** 3:.1f}".replace(".", ",")


def describe(snap: Snapshot | None = None) -> str:
    """«Диск хоста: ожидание ввода-вывода 72% (1 мин), память 3%, свободно 4,1 из 77 ГБ (5%)»; пусто, если данных нет."""
    s = snap or snapshot()
    parts = []
    if s.io_full60 is not None:
        parts.append(f"ожидание ввода-вывода {s.io_full60:.0f}% (1 мин)")
    if s.mem_full60 is not None:
        parts.append(f"нехватка памяти {s.mem_full60:.0f}%")
    if s.disk_free_pct is not None:
        parts.append(f"свободно {_gb(s.disk_free)} из {_gb(s.disk_total)} ГБ ({s.disk_free_pct:.0f}%)")
    return ("Хост: " + ", ".join(parts)) if parts else ""


# --- монитор хоста (scheduler, раз в минуту) ---------------------------------------------------------------------

_IO_BAD_STREAK = 3  # минут подряд выше порога, прежде чем алертить (короткие всплески не будят владельца)
_IO_OK_STREAK = 5  # минут подряд ниже половины порога, прежде чем сказать «в норме»
_IO_COOLDOWN = 3600
_DISK_COOLDOWN = 6 * 3600

_bad = 0
_ok = 0
_alerted_at: float | None = None


async def host_health_job() -> None:
    """Алерты о хосте: диск захлёбывается / снова в норме, мало места. Состояние в процессе scheduler."""
    global _bad, _ok, _alerted_at
    from app.services.alerting import alert_muted, send_telegram

    snap = snapshot(fresh=True)
    threshold = settings.host_alert_io_full_pct
    full60 = snap.io_full60
    if threshold > 0 and full60 is not None:
        if full60 >= threshold:
            _bad, _ok = _bad + 1, 0
        elif full60 < threshold / 2:
            _ok, _bad = _ok + 1, 0
        else:
            _bad = _ok = 0
        if _bad >= _IO_BAD_STREAK and _alerted_at is None:
            _alerted_at = time.time()
            if not await alert_muted("host_pressure", _IO_COOLDOWN):
                brownout = settings.host_brownout_io_full_pct
                await send_telegram(
                    "🟠 <b>Диск хоста тормозит</b>\n"
                    f"{describe(snap)}.\n"
                    "Сайт в режиме экономии: страницы из кэша отдаются как обычно, холодные страницы без Referer "
                    f"(обходчики) получают «занято», пока ожидание выше {brownout:.0f}%. Люди из поиска и поисковые "
                    "роботы идут первыми. Если держится больше часа — вопрос к провайдеру (хранилище ВМ).",
                    kind="host_pressure",
                )
        elif _ok >= _IO_OK_STREAK and _alerted_at is not None:
            minutes = max(1, round((time.time() - _alerted_at) / 60))
            _alerted_at = None
            await send_telegram(
                f"🟢 <b>Диск хоста снова в норме</b>\nТормоза длились около {minutes} мин. {describe(snap)}.",
                kind="host_pressure",
            )

    min_free = settings.host_alert_disk_free_pct
    pct = snap.disk_free_pct
    if min_free > 0 and pct is not None and pct < min_free and not await alert_muted("disk_space", _DISK_COOLDOWN):
        await send_telegram(
            "🟠 <b>Мало места на диске хоста</b>\n"
            f"{describe(snap)}. При заполнении диска останавливаются Postgres и сборка при выкладке; "
            "кандидаты на чистку: кэш сборки docker, журналы systemd, старые логи fail2ban и syslog.",
            kind="disk_space",
        )

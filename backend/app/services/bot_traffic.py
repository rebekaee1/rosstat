"""Сводка по роботам и ферме за сутки (08.11.2026, дополнение ADR-0026).

Откуда цифры. nginx пишет в `security.log` каждую строку с классом трафика в конце (`cls=...`, карта
`$fe_traffic_class` в frontend/nginx.conf). Файл смонтирован в backend/scheduler только на чтение. Раз в 10 минут
`collect_job` дочитывает новые строки с запомненного места (ротация - переход на новый inode, хвост старого файла
дочитывается из `security.log.1`) и складывает счётчики в state-Redis по суткам UTC: класс × исход (ok, 403, 429, 5xx,
other) и самые частые адреса «самозванцев» (`fake`: UA называет Googlebot/Applebot/... не из его сети).

Что видит владелец. `summary_lines(day)` - несколько строк для утренней сводки: сколько пришло от фермы и сколько
отрезано, получили ли поисковики и полезные роботы ошибки, сколько людей прошли по пропуску. Для самозванцев -
обратная и прямая проверка DNS у самых частых адресов: если среди них настоящий робот (новая сеть, которой ещё нет
в search-crawlers.conf), строка просит обновить списки (`scripts/refresh-search-crawler-ranges.py`).

Ошибки чтения/Redis не роняют задачу: нет файла (локально, тесты) - сводка просто пустая.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import socket
from dataclasses import dataclass, field
from datetime import date

from app.config import settings

logger = logging.getLogger(__name__)

CLASSES = ("anon", "human", "referred", "crawler", "goodbot", "robot", "fake", "preview", "internal")
OUTCOMES = ("ok", "403", "429", "5xx", "other")
_KEY_PREFIX = "bot_traffic"
_TTL_SECONDS = 9 * 86400
_MAX_READ_BYTES = 64 * 1024 * 1024
_FAKE_IPS_KEEP = 200
_RDNS_CHECK = 20

# 2026-11-08T00:06:09+00:00 1.2.3.4 200 "GET / HTTP/1.1" "UA" cls=anon
_LINE_RE = re.compile(
    r'^(?P<day>\d{4}-\d{2}-\d{2})T\S+ (?P<ip>\S+) (?P<status>\d{3}) "(?:[^"\\]|\\.)*" "(?:[^"\\]|\\.)*" cls=(?P<cls>[a-z]+)\s*$'
)
# Настоящие роботы по обратному DNS (официальные способы проверки Google, Bing, Яндекса, Apple, DuckDuckGo).
_GENUINE_HOST_RE = re.compile(
    r"\.(?:googlebot\.com|google\.com|googleusercontent\.com|search\.msn\.com|yandex\.(?:ru|net|com)|"
    r"applebot\.apple\.com|duckduckgo\.com)$",
    re.IGNORECASE,
)


def outcome(status: int) -> str:
    if status < 400:
        return "ok"
    if status == 403:
        return "403"
    if status == 429:
        return "429"
    if status >= 500:
        return "5xx"
    return "other"


@dataclass
class Batch:
    """Счётчики из прочитанного куска лога."""

    counts: dict[str, dict[str, int]] = field(default_factory=dict)  # day -> "cls:outcome" -> n
    fake_ips: dict[str, dict[str, int]] = field(default_factory=dict)  # day -> ip -> n

    def add_line(self, line: str) -> bool:
        m = _LINE_RE.match(line)
        if not m or m["cls"] not in CLASSES:
            return False
        day, cls = m["day"], m["cls"]
        key = f"{cls}:{outcome(int(m['status']))}"
        bucket = self.counts.setdefault(day, {})
        bucket[key] = bucket.get(key, 0) + 1
        if cls == "fake":
            ips = self.fake_ips.setdefault(day, {})
            ips[m["ip"]] = ips.get(m["ip"], 0) + 1
        return True


def read_new(path: str, state: str | None, max_bytes: int = _MAX_READ_BYTES) -> tuple[list[str], str | None]:
    """Прочитать новые полные строки лога с места `state` ("inode:offset"); вернуть строки и новое место.

    Ротация (logrotate переименовывает файл): если inode сменился, а у `path + '.1'` прежний inode, сначала дочитывается
    его хвост. Первый запуск (state нет) начинает с конца файла: старое не пересчитывается.
    """
    try:
        st = os.stat(path)
    except OSError:
        return [], state
    inode, size = st.st_ino, st.st_size
    old_inode, old_offset = None, 0
    if state:
        try:
            a, b = state.split(":", 1)
            old_inode, old_offset = int(a), int(b)
        except ValueError:
            old_inode = None
    if old_inode is None:
        return [], f"{inode}:{size}"
    lines: list[str] = []
    budget = max_bytes
    if old_inode != inode:
        try:
            rotated = path + ".1"
            if os.stat(rotated).st_ino == old_inode:
                chunk, _ = _read_from(rotated, old_offset, budget)
                lines += chunk
                budget -= sum(len(x) + 1 for x in chunk)
        except OSError:
            pass
        old_offset = 0
    if old_offset > size:  # файл обрезан на месте (copytruncate)
        old_offset = 0
    chunk, new_offset = _read_from(path, old_offset, max(budget, 0))
    lines += chunk
    return lines, f"{inode}:{new_offset}"


def _read_from(path: str, offset: int, max_bytes: int) -> tuple[list[str], int]:
    if max_bytes <= 0:
        return [], offset
    with open(path, "rb") as fh:
        fh.seek(offset)
        data = fh.read(max_bytes)
    end = data.rfind(b"\n")
    if end < 0:
        return [], offset
    data = data[: end + 1]
    return data.decode("utf-8", "replace").splitlines(), offset + len(data)


def _day_key(day: str) -> str:
    return f"{_KEY_PREFIX}:{day}"


async def collect_job() -> int:
    """Дочитать security.log и сложить счётчики в state-Redis; вернуть число учтённых строк."""
    try:
        from app.core.cache import get_state_redis

        redis = await get_state_redis()
        state = await redis.get(f"{_KEY_PREFIX}:offset")
        lines, new_state = await asyncio.to_thread(read_new, settings.bot_traffic_log_path, state)
        batch = Batch()
        counted = sum(1 for line in lines if batch.add_line(line))
        pipe = redis.pipeline()
        for day, bucket in batch.counts.items():
            for key, n in bucket.items():
                pipe.hincrby(_day_key(day), key, n)
            pipe.expire(_day_key(day), _TTL_SECONDS)
        for day, ips in batch.fake_ips.items():
            zkey = f"{_day_key(day)}:fake_ips"
            for ip, n in ips.items():
                pipe.zincrby(zkey, n, ip)
            pipe.zremrangebyrank(zkey, 0, -_FAKE_IPS_KEEP - 1)
            pipe.expire(zkey, _TTL_SECONDS)
        if new_state:
            pipe.set(f"{_KEY_PREFIX}:offset", new_state)
        await pipe.execute()
        return counted
    except Exception:  # noqa: BLE001 - сводка не должна мешать остальному планировщику
        logger.warning("bot_traffic collect failed", exc_info=True)
        return 0


def _genuine_robot(ip: str) -> str | None:
    """Имя хоста, если адрес - настоящий робот по обратному и прямому DNS; иначе None."""
    try:
        host = socket.gethostbyaddr(ip)[0]
        if not _GENUINE_HOST_RE.search(host):
            return None
        if ip in socket.gethostbyname_ex(host)[2]:
            return host
    except OSError:
        return None
    return None


def check_genuine(ips: list[str], timeout: float = 3.0) -> list[tuple[str, str]]:
    previous = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        found = []
        for ip in ips:
            host = _genuine_robot(ip)
            if host:
                found.append((ip, host))
        return found
    finally:
        socket.setdefaulttimeout(previous)


def _n(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def _req(value: int) -> str:
    n = value % 100
    word = "запросов" if 11 <= n <= 14 else {1: "запрос", 2: "запроса", 3: "запроса", 4: "запроса"}.get(n % 10, "запросов")
    return f"{_n(value)} {word}"


def _pct(part: int, whole: int) -> str:
    if whole <= 0:
        return "0 %"
    share = 100 * part / whole
    return f"{share:.1f} %".replace(".", ",") if share < 10 else f"{round(share)} %"


def format_lines(counts: dict[str, int], genuine_fakes: list[tuple[str, str]], day: date) -> list[str]:
    """Строки для владельца по счётчикам суток (без технических слов)."""
    def get(cls: str, out: str | None = None) -> int:
        if out:
            return int(counts.get(f"{cls}:{out}", 0))
        return sum(int(counts.get(f"{cls}:{o}", 0)) for o in OUTCOMES)

    if not counts:
        return []
    lines = [f"Роботы за {day:%d.%m}:"]
    farm = get("anon")
    if farm:
        cut = get("anon", "429") + get("anon", "403")
        lines.append(f"• без источника перехода (так ходит ферма): {_req(farm)}, отрезано {_pct(cut, farm)}")
    for cls, title in (("crawler", "поисковики Google, Яндекс, Bing"), ("goodbot", "полезные роботы (Apple, OpenAI, Perplexity, DuckDuckGo, Telegram)")):
        total = get(cls)
        if not total:
            continue
        bad = get(cls, "429") + get(cls, "5xx")
        tail = "без отказов" if bad == 0 else f"отказов {_n(bad)} ({_pct(bad, total)})"
        lines.append(f"• {title}: {_req(total)}, {tail}")
    humans = get("human")
    if humans:
        lines.append(f"• люди по пропуску (страница отказа сама пропустила): {_req(humans)}")
    robots = get("robot") + get("fake") + get("preview")
    if robots:
        cut = sum(get(c, "429") for c in ("robot", "fake", "preview"))
        lines.append(f"• прочие роботы и самозванцы: {_req(robots)}, придержано {_pct(cut, robots)}")
    if genuine_fakes:
        lines.append(
            f"⚠ {len(genuine_fakes)} адрес(ов) настоящих роботов пришли не из известных сетей - нужно обновить списки сетей"
        )
    return lines


async def summary_lines(day: date) -> list[str]:
    """Строки сводки за сутки `day` (UTC) для утреннего сообщения; пусто, если данных нет."""
    try:
        from app.core.cache import get_state_redis

        redis = await get_state_redis()
        counts = await redis.hgetall(_day_key(day.isoformat()))
        top = await redis.zrevrange(f"{_day_key(day.isoformat())}:fake_ips", 0, _RDNS_CHECK - 1)
    except Exception:  # noqa: BLE001
        logger.warning("bot_traffic summary failed", exc_info=True)
        return []
    genuine = await asyncio.to_thread(check_genuine, list(top)) if top else []
    if genuine:
        logger.warning("bot_traffic: genuine robots outside known networks: %s", genuine)
    return format_lines({k: int(v) for k, v in counts.items()}, genuine, day)

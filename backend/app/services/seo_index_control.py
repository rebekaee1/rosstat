"""Контроль индексации для недельного SEO-отчёта (круг 13).

Два источника, без ручной проверки владельцем:

* Яндекс: снимки ``webmaster_indexing_daily`` (страниц в поиске, исключено,
  обход по кодам ответа) — тренд за неделю по хостам;
* Google: URL Inspection API по ФИКСИРОВАННОЙ контрольной выборке из 20
  адресов (10 путей на двух хостах). Лимит Google — 2 000 проверок в сутки на
  ресурс, наш — один прогон в неделю по 20 адресов, повторный запуск в тот же
  день берёт сохранённый результат и в API не ходит. Результат хранится в
  Redis состояния (переживает сброс кэша), 200 дней истории, миграций нет.
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta

from sqlalchemy import text

from app.config import settings

logger = logging.getLogger(__name__)

# Фиксированная выборка: те же десять путей на обоих хостах (20 проверок = лимит
# одного прогона inspect_sample). Только канонические адреса: /calendar и
# /regions отвечают 301, Google их «не знает» по определению.
CONTROL_PATHS = (
    "/",
    "/russia",
    "/russia/indicator/key-rate",
    "/russia/indicator/cpi",
    "/russia/calendar",
    "/russia/region",
    "/russia/today",
    "/germany",
    "/world/rating/gdp-usd",
    "/compare",
)
CONTROL_HOSTS = ("forecasteconomy.com", "ru.forecasteconomy.com")

_HISTORY_KEY = "seo:gsc-inspect:history"
_HISTORY_TTL_S = 200 * 24 * 3600
_INDEXED_PREFIXES = ("submitted and indexed", "indexed, not submitted")


def control_urls() -> list[str]:
    urls = []
    for host in CONTROL_HOSTS:
        for path in CONTROL_PATHS:
            urls.append(f"https://{host}" + ("" if path == "/" else path))
    return urls


def parse_inspection(report: dict) -> dict:
    """Короткая запись из ответа URL Inspection: состояние, вердикт, дата обхода."""
    status = ((report.get("result") or {}).get("inspectionResult") or {}).get("indexStatusResult") or {}
    state = str(status.get("coverageState") or "unknown")
    return {
        "url": report.get("url"),
        "state": state,
        "verdict": status.get("verdict"),
        "crawled": (status.get("lastCrawlTime") or "")[:10] or None,
        "indexed": state.lower().startswith(_INDEXED_PREFIXES),
        "canonical_differs": bool(
            status.get("googleCanonical")
            and status.get("userCanonical")
            and status["googleCanonical"] != status["userCanonical"]
        ),
    }


def _n(value) -> str:
    return f"{int(value):,}".replace(",", " ")


def _host(url: str) -> str:
    return url.split("//", 1)[-1].split("/", 1)[0]


async def _load_history(redis) -> dict[str, list[dict]]:
    raw = await redis.hgetall(_HISTORY_KEY)
    history: dict[str, list[dict]] = {}
    for key, value in (raw or {}).items():
        key = key.decode() if isinstance(key, bytes) else key
        value = value.decode() if isinstance(value, bytes) else value
        try:
            history[key] = json.loads(value)
        except ValueError:
            continue
    return history


async def run_control_inspection(today: date, *, client_factory=None) -> dict:
    """Результат сегодняшней проверки + предыдущей (если была раньше).

    Возвращает ``{"day", "current": [...], "previous_day", "previous": [...]}``;
    при любой ошибке API — ``{"error": "..."}`` (отчёт всё равно уходит).
    """
    import httpx

    from app.core.cache import get_state_redis
    from app.services.gsc_client import GscClient, configured_site

    if client_factory is None and not (settings.gsc_access_token or settings.gsc_credentials_file):
        return {"error": "учётные данные Search Console не настроены"}
    redis = await get_state_redis()
    history = await _load_history(redis)
    day_key = today.isoformat()
    earlier = sorted(day for day in history if day < day_key)
    previous_day = earlier[-1] if earlier else None
    result = {
        "day": day_key,
        "previous_day": previous_day,
        "previous": history.get(previous_day, []) if previous_day else [],
    }
    if day_key in history:  # повторный запуск в тот же день: API не трогаем
        result["current"] = history[day_key]
        return result
    try:
        async with httpx.AsyncClient(timeout=60) as http:
            client = client_factory(http) if client_factory else GscClient.from_settings(http)
            reports = await client.inspect_sample(configured_site(), control_urls())
    except Exception as exc:  # noqa: BLE001 — отчёт важнее одной недоступной проверки
        logger.warning("GSC control inspection failed: %s", type(exc).__name__)
        return {"error": f"URL Inspection недоступен ({type(exc).__name__})"}
    current = [parse_inspection(report) for report in reports]
    await redis.hset(_HISTORY_KEY, day_key, json.dumps(current, ensure_ascii=False))
    await redis.expire(_HISTORY_KEY, _HISTORY_TTL_S)
    result["current"] = current
    return result


def summarize_inspection(data: dict) -> list[str]:
    """Строки для Telegram: проиндексировано N из M по хостам, что изменилось."""
    if not data:
        return []
    if data.get("error"):
        return [f"Google, контрольная выборка: {data['error']}"]
    current: list[dict] = data.get("current") or []
    previous = {item["url"]: item for item in data.get("previous") or []}
    lines = [f"Google, контрольная выборка ({data['day'][8:]}.{data['day'][5:7]})"]
    for host in CONTROL_HOSTS:
        items = [item for item in current if _host(item["url"]) == host]
        if not items:
            continue
        indexed = sum(1 for item in items if item["indexed"])
        lines.append(f"{host}: в индексе {indexed} из {len(items)}")
        states: dict[str, int] = {}
        for item in items:
            if not item["indexed"]:
                states[item["state"]] = states.get(item["state"], 0) + 1
        if states:
            lines.append("  не в индексе: " + "; ".join(f"{name} — {count}" for name, count in sorted(states.items())))
    if previous:
        gained = [i for i in current if i["indexed"] and not (previous.get(i["url"]) or {}).get("indexed", False)]
        lost = [i for i in current if not i["indexed"] and (previous.get(i["url"]) or {}).get("indexed", False)]
        pd = data.get("previous_day") or ""
        label = f"{pd[8:]}.{pd[5:7]}" if pd else "прошлой проверки"
        lines.append(f"С {label}: стало в индексе {len(gained)}, выпало {len(lost)}")
        for item in lost[:5]:
            lines.append(f"  выпало: {item['url']}")
    else:
        lines.append("Предыдущей проверки нет: сравнение появится со следующей недели.")
    return lines


def summarize_yandex_indexing(rows: list[dict]) -> list[str]:
    """Тренд «страниц в поиске» по хостам и доля 4xx/5xx среди обходов Яндекса.

    ``rows`` — снимки одного хоста по возрастанию дня (минимум два для тренда).
    """
    lines: list[str] = []
    by_host: dict[str, list[dict]] = {}
    for row in rows:
        by_host.setdefault(row["host"], []).append(row)
    for host, items in sorted(by_host.items()):
        items.sort(key=lambda row: row["day"])
        last = items[-1]
        label = host.replace("https:", "").replace(":443", "")
        week_ago = [row for row in items if row["day"] <= last["day"] - timedelta(days=7)]
        base = week_ago[-1] if week_ago else None
        in_search = last.get("in_search")
        if in_search is None:
            continue
        trend = ""
        if base and base.get("in_search") is not None:
            diff = in_search - base["in_search"]
            trend = f" ({'+' if diff >= 0 else '−'}{_n(abs(diff))} за неделю)"
        line = f"{label}: в поиске {_n(in_search)}{trend} на {last['day']:%d.%m}"
        if last.get("excluded") is not None:
            line += f", исключено {_n(last['excluded'])}"
        lines.append(line)
        crawled = sum(int(last.get(key) or 0) for key in ("crawled_2xx", "crawled_3xx", "crawled_4xx", "crawled_5xx"))
        bad = int(last.get("crawled_4xx") or 0) + int(last.get("crawled_5xx") or 0)
        if crawled:
            lines.append(f"  обход за сутки {_n(crawled)}, из них 4xx/5xx — {100.0 * bad / crawled:.1f}%")
    return lines


async def collect_yandex_indexing(db, today: date) -> list[dict]:
    rows = (await db.execute(text(
        "SELECT host, day, in_search, excluded, crawled_2xx, crawled_3xx, crawled_4xx, crawled_5xx "
        "FROM webmaster_indexing_daily WHERE day >= :since AND in_search IS NOT NULL ORDER BY host, day"
    ), {"since": today - timedelta(days=21)})).mappings().all()
    return [dict(row) for row in rows]

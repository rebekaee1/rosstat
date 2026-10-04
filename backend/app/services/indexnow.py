"""IndexNow — мгновенное уведомление поисковиков об обновлённых URL.

Протокол: https://www.indexnow.org/ (Яндекс — участник, Bing — участник;
Google не поддерживает, но узнаёт обновления через sitemap lastmod).

Схема: после daily ETL scheduler кладёт URL обновлённых индикаторов в очередь;
общий drainer отправляет их в пределах единой дневной квоты для всех хостов.
Ключ подтверждается файлом
`frontend/public/{key}.txt` (отдаётся nginx как `https://host/{key}.txt`).

Fire-and-forget: ошибка пинга никогда не валит ETL — только warning в лог.

Языковой сплит (ADR-0013 §F): ``origin`` / ``host`` параметризованы — после
cutover можно пинговать ``ru.`` отдельно. Дефолт = ``settings.public_origin``
(текущий прод). Не вызывать второй хост, пока DNS/Caddy/ключ на нём не готовы.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import date, datetime, time, timedelta, timezone
from math import ceil
from urllib.parse import urlparse

import httpx
from redis.exceptions import WatchError

from app.config import settings

logger = logging.getLogger(__name__)


# Лимит протокола IndexNow — 10 000 URL на один POST.
# Рабочий батч очереди меньше: 500–1000, чтобы 429 не сжигал весь реестр.
_BATCH_LIMIT = 10_000
_QUEUE_BATCH = 800
_DEBOUNCE_TTL = 24 * 3600
_QUEUE_PREFIX = "in:queue:"
_DEBOUNCE_PREFIX = "in:sent:"
# Надёжная очередь (F12, 2026-10-04): партия не «снимается» SPOP-ом, а атомарно
# переносится SMOVE в processing-set `in:proc:{host}:{batch_id}`; её id и время
# взятия лежат в zset `in:proc-idx:{host}`. ACK (после успешного ping или
# возврата в очередь) удаляет оба. Партии, зависшие дольше таймаута (процесс
# упал между взятием и ACK), следующий drain возвращает в очередь.
_PROCESSING_PREFIX = "in:proc:"
_PROCESSING_INDEX_PREFIX = "in:proc-idx:"
# Drain идёт раз в 10 минут (max_instances=1); ping_urls — до 30 с на POST плюс
# пауза 429 до 60 с. 30 минут с запасом: повторная доставка безопасна
# (IndexNow идемпотентен, debounce-ключи отсекают уже отправленное).
_PROCESSING_TIMEOUT = 30 * 60
# Страховочный TTL содержимого партии: возврат идёт каждые 10 минут, так что до
# него дело доходит только если очередь не обслуживалась неделю (URL устарели).
_PROCESSING_TTL = 7 * 24 * 3600
_HISTORY_CURSOR_KEY = "in:history:cursor"
_HISTORY_LOCK_KEY = "in:history:lock"
# v3 stores an independent (phase, section, offset) cursor per sitemap family.
_HISTORY_CURSOR_VERSION = 3
_HISTORY_RESTART_DAYS = 14
_HISTORY_DEMAND_LIMIT = 300
_HISTORY_CAP_MIN = 1_000
_HISTORY_CAP_MAX = 50_000
_DAILY_SEND_KEY_PREFIX = "in:daily-send:"
_DAILY_SEND_CAP_MAX = 30_000

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def daily_send_cap() -> int:
    """Effective hard ceiling: configuration may lower, never raise 30k/day."""
    try:
        return min(max(int(settings.indexnow_daily_send_cap), 0), _DAILY_SEND_CAP_MAX)
    except (TypeError, ValueError):
        return 0


def _daily_send_counter_key(now: datetime | None = None) -> tuple[str, int]:
    now = now or _utc_now()
    next_midnight = datetime.combine(
        now.date() + timedelta(days=1), time.min, tzinfo=timezone.utc
    )
    # Keep yesterday's number briefly for operations, while the date in the key
    # makes the quota switch atomically at 00:00 UTC.
    ttl = max(60, ceil((next_midnight - now).total_seconds()) + 24 * 3600)
    key = f"{_DAILY_SEND_KEY_PREFIX}global:{now:%Y%m%d}"
    return key, ttl


async def daily_send_remaining(host: str, *, redis=None) -> int:
    """Remaining global URL-list budget shared by all public hosts today (UTC)."""
    cap = daily_send_cap()
    if cap <= 0:
        return 0
    if redis is None:
        from app.core.cache import get_state_redis

        redis = await get_state_redis()
    key, _ttl = _daily_send_counter_key()
    used = int(await redis.get(key) or 0)
    return max(0, cap - used)


async def reserve_daily_send_quota(
    host: str, url_count: int, *, redis=None
) -> bool:
    """Atomically charge one POST attempt against the global UTC-day ceiling.

    Reservation happens before HTTP. A timeout or 429 still consumes quota,
    because the remote service may have received the request before the client
    lost the response. Apex and ru requests share one counter across workers.
    """
    count = int(url_count)
    if count <= 0:
        return True
    cap = daily_send_cap()
    if cap <= 0 or count > cap:
        return False
    if redis is None:
        from app.core.cache import get_state_redis

        redis = await get_state_redis()
    key, ttl = _daily_send_counter_key()
    # WATCH + MULTI/EXEC makes the check-and-increment one conditional atomic
    # reservation. Concurrent workers retry after a conflicting transaction;
    # over-limit requests never create a transient over-count.
    while True:
        pipe = redis.pipeline(transaction=True)
        try:
            await pipe.watch(key)
            used = int(await pipe.get(key) or 0)
            if used + count > cap:
                await pipe.unwatch()
                return False
            pipe.multi()
            pipe.incrby(key, count)
            pipe.expire(key, ttl)
            await pipe.execute()
            return True
        except WatchError:
            continue
        finally:
            await pipe.reset()


async def ping_urls(
    paths: list[str],
    *,
    origin: str | None = None,
    host: str | None = None,
) -> bool:
    """Отправить batch обновлённых путей (`/russia/indicator/cpi`, …) в IndexNow.

    ``origin`` / ``host`` — для второго языкового хоста (``ru.``). По умолчанию
    берётся ``settings.public_origin`` (apex / текущий прод). Не пинговать
    ``ru.`` на прод, пока хост не живёт с TLS и key-файлом.

    Возвращает True, если все батчи приняты (HTTP 200/202). Списки длиннее
    лимита протокола (10 000 URL/запрос) разбиваются на последовательные POST.
    """
    if not settings.indexnow_enabled or not settings.indexnow_key or not paths:
        return False
    base = (origin or settings.public_origin).rstrip("/")
    if host:
        ping_host = host.split(":", 1)[0].strip().lower()
    else:
        ping_host = urlparse(base).hostname or settings.public_host
    unique_urls = [f"{base}{p}" for p in dict.fromkeys(paths)]
    ok = True
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            for i in range(0, len(unique_urls), _BATCH_LIMIT):
                batch = unique_urls[i : i + _BATCH_LIMIT]
                if not await reserve_daily_send_quota(ping_host, len(batch)):
                    ok = False
                    logger.info(
                        "IndexNow: global daily send cap reached host=%s; defer %d URL(s)",
                        ping_host,
                        len(unique_urls) - i,
                    )
                    break
                payload = {
                    "host": ping_host,
                    "key": settings.indexnow_key,
                    "keyLocation": f"{base}/{settings.indexnow_key}.txt",
                    "urlList": batch,
                }
                response = await client.post(settings.indexnow_endpoint, json=payload)
                if response.status_code in (200, 202):
                    logger.info(
                        "IndexNow: pinged %d URL(s) host=%s (batch %d), status %d",
                        len(batch),
                        ping_host,
                        i // _BATCH_LIMIT + 1,
                        response.status_code,
                    )
                elif response.status_code == 429:
                    retry_after = (getattr(response, "headers", None) or {}).get("Retry-After", "")
                    ok = False
                    logger.warning(
                        "IndexNow: 429 host=%s Retry-After=%s batch=%d",
                        ping_host, retry_after, i // _BATCH_LIMIT + 1,
                    )
                    # Вежливая пауза перед следующим батчем/drain: делим
                    # Remaining на 2 (не ждём дольше минуты — хвост дозальёт
                    # следующий drain через 10 минут).
                    try:
                        delay = min(int(float(retry_after)), 60)
                    except (TypeError, ValueError):
                        delay = 30
                    await asyncio.sleep(max(delay, 5))
                    break
                else:
                    ok = False
                    logger.warning(
                        "IndexNow: unexpected status %d for %d URL(s) host=%s: %s",
                        response.status_code,
                        len(batch),
                        ping_host,
                        response.text[:200],
                    )
        return ok
    except Exception as exc:
        logger.warning("IndexNow ping failed (host=%s): %s", ping_host, exc)
        return False


async def ping_updated_indicators(updated_codes: list[str]) -> bool:
    """Поставить обновлённые карточки в очередь общей дневной квоты."""
    if not updated_codes:
        return False
    from app.services import site_paths as paths
    from app.services.display import today_msk
    from app.services.seo_today import TODAY_CODES

    year = today_msk().year
    url_paths = ["/"] + [paths.today()] + [
        paths.russia_indicator(code) for code in updated_codes
    ]
    url_paths += [
        paths.russia_indicator_year(code, year) for code in updated_codes
    ]
    url_paths += [
        paths.russia_indicator_year(code, year - 1) for code in updated_codes
    ]
    url_paths += [
        paths.today(code) for code in updated_codes if code in TODAY_CODES
    ]
    queued = []
    for origin, host in _indexnow_targets():
        queued.append(await enqueue_paths(url_paths, origin=origin, host=host))
    return all(count > 0 for count in queued)


async def ping_full_site(db, *, origin: str | None = None, host: str | None = None) -> int:
    """Приоритетные секции (хабы/карточки), не слепой проход всех URL.

    Все чанковые секции (карточки и периоды) кладёт
    ``indexnow_history_job`` в ту же очередь с дневным потолком.
    ``origin``/``host`` — второй хост после cutover.
    """
    return await ping_sections(db, origin=origin, host=host)


async def ping_sections(db, *, origin: str | None = None, host: str | None = None) -> int:
    """Стриминг простых секций ``site_urls.section_names_static`` в очередь IndexNow."""
    from app.services.site_urls import resolve_section, section_names_static

    total = 0
    for name in section_names_static():
        urls = await resolve_section(db, name)
        if not urls:
            continue
        paths = [
            (u.path if hasattr(u, "path") else u.get("loc") or u.get("path"))
            for u in urls
        ]
        paths = [p for p in paths if p]
        total += await enqueue_paths(paths, origin=origin, host=host)
    return total


def _ping_host(origin: str | None, host: str | None) -> str:
    base = (origin or settings.public_origin).rstrip("/")
    if host:
        return host.split(":", 1)[0].strip().lower()
    return urlparse(base).hostname or settings.public_host


def _indexnow_targets() -> list[tuple[str, str]]:
    """(origin, host) для очереди: apex и, после cutover, ru."""
    from app.services.locale import ru_public_origin

    targets = [(settings.public_origin, settings.public_host)]
    if settings.apex_locale_en:
        targets.append((ru_public_origin(), "ru.forecasteconomy.com"))
    return targets


def path_year(path: str) -> int | None:
    """Год из хвоста пути: ``/…/2018`` или ``/…/2018-01``."""
    tail = (path or "").rstrip("/").rsplit("/", 1)[-1]
    if len(tail) < 4 or not tail[:4].isdigit():
        return None
    if len(tail) not in (4, 7) or (len(tail) == 7 and tail[4] != "-"):
        return None
    year = int(tail[:4])
    if year < 1900 or year > 2100:
        return None
    return year


def _history_daily_cap() -> int:
    cap = int(settings.indexnow_history_daily_cap)
    if cap < 1:
        return _HISTORY_CAP_MIN
    return min(cap, _HISTORY_CAP_MAX)


def _matches_history_phase(path: str, *, phase: int, year_min: int) -> bool:
    year = path_year(path)
    if phase == 0:
        return year is None or year >= year_min
    return year is not None and year < year_min


def _section_paths(urls) -> list[str]:
    paths: list[str] = []
    for item in urls or []:
        if hasattr(item, "path"):
            path = item.path
        elif isinstance(item, dict):
            path = item.get("loc") or item.get("path")
        else:
            path = None
        if path:
            paths.append(path)
    return paths


def _load_history_cursor(raw: str | None) -> dict:
    try:
        data = json.loads(raw or "")
    except (TypeError, json.JSONDecodeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    if data.get("version") != _HISTORY_CURSOR_VERSION:
        data = {}
    families = data.get("families")
    if not isinstance(families, dict):
        families = {}
    normalized: dict[str, dict] = {}
    for prefix, state in families.items():
        if not isinstance(state, dict):
            state = {}
        normalized[str(prefix)] = {
            "phase": min(2, max(0, int(state.get("phase") or 0))),
            "i": max(0, int(state.get("i") or 0)),
            "skip": max(0, int(state.get("skip") or 0)),
            "processed": max(0, int(state.get("processed") or 0)),
        }
    return {
        "version": _HISTORY_CURSOR_VERSION,
        "phase": 0,
        "families": normalized,
        "done_on": str(data.get("done_on") or ""),
    }


def _history_family_quotas(budget: int, weights: dict[str, int]) -> dict[str, int]:
    """Split one day's remaining URLs proportionally with stable tie-breaking."""
    active = [(name, max(0, int(weight))) for name, weight in weights.items()]
    active = [(name, weight) for name, weight in active if weight > 0]
    total = sum(weight for _name, weight in active)
    if budget <= 0 or total <= 0:
        return {}
    floor = 1 if budget >= len(active) else 0
    distributable = budget - floor * len(active)
    quotas: dict[str, int] = {}
    fractions: list[tuple[float, int, str]] = []
    assigned = 0
    for order, (name, weight) in enumerate(active):
        exact = distributable * weight / total
        quota = floor + int(exact)
        quotas[name] = quota
        assigned += quota
        fractions.append((exact - int(exact), -order, name))
    for _fraction, _order, name in sorted(fractions, reverse=True)[: budget - assigned]:
        quotas[name] += 1
    return quotas


async def _enqueue_history_family(
    db,
    *,
    prefix: str,
    sections: list[str],
    cursor: dict,
    budget: int,
    year_min: int,
    targets: list[tuple[str, str]],
) -> tuple[int, str]:
    """Advance one family through fresh then older pages up to its share."""
    queued = 0
    last_section = ""
    while budget > 0 and cursor["phase"] < 2:
        if cursor["i"] >= len(sections):
            if cursor["phase"] == 0:
                cursor.update(phase=1, i=0, skip=0)
            else:
                cursor["phase"] = 2
            continue

        section = sections[cursor["i"]]
        last_section = section
        filtered = [
            path for path in await _history_section_paths(db, section, targets)
            if _matches_history_phase(path, phase=cursor["phase"], year_min=year_min)
        ]
        skip = min(cursor["skip"], len(filtered))
        take = filtered[skip : skip + budget]
        if take:
            for origin, host in targets:
                await enqueue_paths(take, origin=origin, host=host)
            queued += len(take)
            cursor["processed"] += len(take)
            budget -= len(take)
            cursor["skip"] = skip + len(take)

        if cursor["skip"] >= len(filtered) or not filtered:
            cursor.update(i=cursor["i"] + 1, skip=0)
    while cursor["phase"] < 2 and cursor["i"] >= len(sections):
        if cursor["phase"] == 0:
            cursor.update(phase=1, i=0, skip=0)
        else:
            cursor["phase"] = 2
    return queued, last_section


def _published_origin(targets: list[tuple[str, str]] | None = None) -> str | None:
    """Origin с опубликованной ночной генерацией sitemap (пути у хостов общие)."""
    from app.services.sitemap_static import has_published_generation

    for origin, _host in targets or _indexnow_targets():
        if has_published_generation(origin):
            return origin
    return None


async def _history_section_names(db) -> list[str]:
    from app.services.site_urls import _chunked_prefix_for, section_names
    from app.services.sitemap_static import published_sections

    # Ночная генерация уже знает группы и число чанков: пересчёт из БД
    # (count/оконные границы по 16 млн world_data_points) не укладывался в
    # statement_timeout 30 с — indexnow_history падал 2026-09-27/29.
    origin = _published_origin()
    names = published_sections(origin) if origin else None
    if names is None:
        names = await section_names(db)
    # Sitemap сам определяет опубликованные группы и число чанков. Отдельный
    # allowlist здесь терял базовые мировые и региональные карточки.
    return [name for name in names if _chunked_prefix_for(name) is not None]


async def _history_section_paths(db, section: str, targets) -> list[str]:
    """Пути чанка: файл опубликованной генерации, без неё — сборка из БД."""
    from app.services.site_urls import resolve_section
    from app.services.sitemap_static import published_section_paths

    origin = _published_origin(targets)
    if origin:
        paths = await asyncio.to_thread(published_section_paths, section, origin)
        if paths is not None:
            return paths
    return _section_paths(await resolve_section(db, section))


async def _queue_backed_up(redis, hosts: list[str], cap: int) -> bool:
    for host in hosts:
        if await redis.scard(f"{_QUEUE_PREFIX}{host}") >= cap:
            return True
    return False


def _fair_drain_budgets(
    hosts: list[str], queue_sizes: dict[str, int], budget: int
) -> dict[str, int]:
    """Split this drain's global send budget across nonempty host queues.

    A host with no queued URLs receives no share. If a smaller queue fills its
    share, the unused part is redistributed among the still-active hosts.
    """
    allocations = {host: 0 for host in hosts}
    active = [host for host in hosts if queue_sizes.get(host, 0) > 0]
    remaining = max(0, int(budget))
    while active and remaining > 0:
        base, extra = divmod(remaining, len(active))
        distributed = 0
        for index, host in enumerate(active):
            share = base + (1 if index < extra else 0)
            capacity = max(0, int(queue_sizes.get(host, 0)) - allocations[host])
            take = min(share, capacity)
            allocations[host] += take
            distributed += take
        if distributed == 0:
            break
        remaining -= distributed
        active = [
            host for host in active
            if allocations[host] < max(0, int(queue_sizes.get(host, 0)))
        ]
    return allocations


async def enqueue_paths(
    paths: list[str],
    *,
    origin: str | None = None,
    host: str | None = None,
) -> int:
    """Положить пути в Redis-очередь (дедуп, debounce 24ч на drain)."""
    if not settings.indexnow_enabled or not settings.indexnow_key or not paths:
        return 0
    from app.core.cache import get_state_redis

    ping_host = _ping_host(origin, host)
    redis = await get_state_redis()
    unique = list(dict.fromkeys(paths))
    await redis.sadd(f"{_QUEUE_PREFIX}{ping_host}", *unique)
    return len(unique)


async def enqueue_history_urls(db) -> dict:
    """Дневная порция длинного хвоста в очередь IndexNow, без прямого POST.

    Сначала спрос Вебмастера, затем семейства чанков с долей по числу URL.
    У каждого семейства свой курсор: новые страницы не блокируют старые,
    а крупные US/state years получают пропорциональную долю каждый день.
    """
    from app.core.cache import get_state_redis
    from app.services.demand_router import priority_recrawl_paths
    from app.services.display import today_msk
    from app.services.site_urls import _chunked_prefix_for, chunk_item_counts

    if not settings.indexnow_enabled or not settings.indexnow_key:
        return {"queued": 0, "skipped": "disabled"}

    redis = await get_state_redis()
    cap = _history_daily_cap()
    year_min = int(settings.indexnow_history_year_min)
    targets = _indexnow_targets()
    hosts = [host for _, host in targets]
    queued = 0

    for origin, host in targets:
        demand = [
            path
            for path, _lost in await priority_recrawl_paths(
                db, days=30, limit=_HISTORY_DEMAND_LIMIT, host=host
            )
            if path
        ][:cap]
        queued = max(queued, await enqueue_paths(demand, origin=origin, host=host))

    remaining = max(0, cap - queued)
    stats = {
        "queued": queued,
        "backed_up": False,
        "resting": False,
        "phase": 0,
        "section": "",
        "families": {},
    }
    if remaining <= 0:
        return stats
    if await _queue_backed_up(redis, hosts, cap):
        stats["backed_up"] = True
        logger.info("IndexNow history: drain queue still full, skip chunks")
        return stats

    names = await _history_section_names(db)
    sections_by_family: dict[str, list[str]] = {}
    for name in names:
        chunked = _chunked_prefix_for(name)
        if chunked is not None:
            prefix, _index = chunked
            sections_by_family.setdefault(prefix, []).append(name)

    cursor = _load_history_cursor(await redis.get(_HISTORY_CURSOR_KEY))
    today = today_msk()
    if cursor["done_on"]:
        try:
            done_on = date.fromisoformat(cursor["done_on"])
        except ValueError:
            done_on = date(1970, 1, 1)
        if (today - done_on).days < _HISTORY_RESTART_DAYS:
            stats["resting"] = True
            stats["phase"] = 2
            return stats
        cursor = _load_history_cursor(None)

    for prefix in sections_by_family:
        cursor["families"].setdefault(
            prefix, {"phase": 0, "i": 0, "skip": 0, "processed": 0}
        )

    item_counts = await chunk_item_counts(db)
    weights = {
        prefix: max(1, int(item_counts.get(prefix, 0)) - state["processed"])
        for prefix, state in cursor["families"].items()
        if prefix in sections_by_family and state["phase"] < 2
    }
    last_section = ""

    # Redistribute unused share when a small family finishes its full catalog.
    while remaining > 0 and weights:
        shares = _history_family_quotas(remaining, weights)
        if not shares:
            break
        progressed = 0
        for prefix in sections_by_family:
            share = shares.get(prefix, 0)
            if share <= 0:
                continue
            state = cursor["families"][prefix]
            added, section = await _enqueue_history_family(
                db,
                prefix=prefix,
                sections=sections_by_family[prefix],
                cursor=state,
                budget=share,
                year_min=year_min,
                targets=targets,
            )
            if section:
                last_section = section
            if added:
                queued += added
                remaining -= added
                progressed += added
            stats["families"][prefix] = stats["families"].get(prefix, 0) + added

        for prefix, state in cursor["families"].items():
            if prefix not in sections_by_family or state["phase"] >= 2:
                weights.pop(prefix, None)
                continue
            weights[prefix] = max(
                1, int(item_counts.get(prefix, 0)) - state["processed"]
            )
        if progressed == 0:
            break

    all_done = all(
        cursor["families"].get(prefix, {}).get("phase", 2) >= 2
        for prefix in sections_by_family
    )
    cursor["phase"] = 2 if all_done else min(
        (state["phase"] for state in cursor["families"].values()), default=2
    )
    if all_done and not cursor.get("done_on"):
        cursor["done_on"] = today.isoformat()
    await redis.set(_HISTORY_CURSOR_KEY, json.dumps(cursor))
    stats["queued"] = queued
    stats["phase"] = cursor["phase"]
    stats["section"] = last_section
    return stats


def _processing_key(ping_host: str, batch_id: str) -> str:
    return f"{_PROCESSING_PREFIX}{ping_host}:{batch_id}"


def _as_text(items) -> list[str]:
    if isinstance(items, (bytes, str)):
        items = [items]
    return [p.decode() if isinstance(p, bytes) else p for p in (items or [])]


async def _claim_batch(redis, ping_host: str, count: int) -> tuple[str | None, list[str]]:
    """Атомарно перенести до `count` URL из очереди в processing (MULTI/EXEC).

    В отличие от SPOP, падение процесса после взятия не теряет партию: она
    остаётся в `in:proc:*` и вернётся в очередь через `_recover_stale_batches`.
    """
    queue_key = f"{_QUEUE_PREFIX}{ping_host}"
    members = _as_text(await redis.srandmember(queue_key, count))
    if not members:
        return None, []
    batch_id = uuid.uuid4().hex
    proc_key = _processing_key(ping_host, batch_id)
    index_key = f"{_PROCESSING_INDEX_PREFIX}{ping_host}"
    pipe = redis.pipeline(transaction=True)
    pipe.zadd(index_key, {batch_id: _utc_now().timestamp()})
    for member in members:
        pipe.smove(queue_key, proc_key, member)
    pipe.expire(proc_key, _PROCESSING_TTL)
    results = await pipe.execute()
    # Параллельный drain мог забрать часть URL раньше: в партии только перенесённые.
    moved = [member for member, ok in zip(members, results[1:1 + len(members)]) if ok]
    if not moved:
        await redis.zrem(index_key, batch_id)
        return None, []
    return batch_id, moved


async def _ack_batch(redis, ping_host: str, batch_id: str, *, requeue=()) -> None:
    """Снять партию с учёта; `requeue` (не отправленные) — вернуть в очередь в той же транзакции."""
    pipe = redis.pipeline(transaction=True)
    if requeue:
        pipe.sadd(f"{_QUEUE_PREFIX}{ping_host}", *requeue)
    pipe.delete(_processing_key(ping_host, batch_id))
    pipe.zrem(f"{_PROCESSING_INDEX_PREFIX}{ping_host}", batch_id)
    await pipe.execute()


async def _recover_stale_batches(redis, ping_host: str) -> int:
    """Вернуть в очередь партии, зависшие в processing дольше таймаута."""
    index_key = f"{_PROCESSING_INDEX_PREFIX}{ping_host}"
    cutoff = _utc_now().timestamp() - _PROCESSING_TIMEOUT
    stale = _as_text(await redis.zrangebyscore(index_key, "-inf", cutoff))
    returned = 0
    for batch_id in stale:
        proc_key = _processing_key(ping_host, batch_id)
        members = _as_text(await redis.smembers(proc_key))
        await _ack_batch(redis, ping_host, batch_id, requeue=members)
        returned += len(members)
        logger.warning(
            "IndexNow drain: returned stale batch %s (%d URL(s)) to %s%s",
            batch_id, len(members), _QUEUE_PREFIX, ping_host,
        )
    return returned


async def drain_indexnow_queue(*, limit: int = _QUEUE_BATCH) -> int:
    """Снять батч из очереди каждого известного хоста и пингануть."""
    from app.core.cache import get_state_redis
    from app.services.locale import ru_public_origin

    redis = await get_state_redis()
    hosts = [settings.public_host]
    origins = {settings.public_host: settings.public_origin}
    if settings.apex_locale_en:
        ru_host = "ru.forecasteconomy.com"
        hosts.append(ru_host)
        origins[ru_host] = ru_public_origin()
    # Партии, зависшие после падения процесса между взятием и ACK, — обратно в очередь
    # до расчёта размеров (при старте scheduler это первый же drain).
    for ping_host in hosts:
        try:
            await _recover_stale_batches(redis, ping_host)
        except Exception as exc:  # noqa: BLE001 — возврат подождёт следующего drain
            logger.warning("IndexNow drain: stale batch recovery failed host=%s: %s", ping_host, exc)
    daily_remaining = await daily_send_remaining(hosts[0], redis=redis)
    queue_sizes = {
        host: int(await redis.scard(f"{_QUEUE_PREFIX}{host}"))
        for host in hosts
    }
    drain_budget = min(max(0, int(limit)), daily_remaining)
    budgets = _fair_drain_budgets(hosts, queue_sizes, drain_budget)
    sent = 0
    for ping_host in hosts:
        host_budget = budgets.get(ping_host, 0)
        if host_budget <= 0:
            if daily_remaining <= 0:
                logger.info("IndexNow drain: global daily send cap reached")
            continue
        queue_key = f"{_QUEUE_PREFIX}{ping_host}"
        batch_id, batch = await _claim_batch(redis, ping_host, host_budget)
        if not batch_id:
            continue
        try:
            # Один round-trip на весь батч: 800 последовательных EXISTS
            # каждые 10 минут — 800 шансов поймать таймаут state-Redis.
            pipe = redis.pipeline(transaction=False)
            for path in batch:
                pipe.exists(f"{_DEBOUNCE_PREFIX}{ping_host}:{path}")
            seen = await pipe.execute()
            fresh = [path for path, hit in zip(batch, seen) if not hit]
            if not fresh:
                await _ack_batch(redis, ping_host, batch_id)
                continue
            ok = await ping_urls(fresh, origin=origins.get(ping_host), host=ping_host)
            if ok:
                pipe = redis.pipeline(transaction=False)
                for path in fresh:
                    pipe.set(
                        f"{_DEBOUNCE_PREFIX}{ping_host}:{path}",
                        "1",
                        ex=_DEBOUNCE_TTL,
                    )
                await pipe.execute()
                # ACK после debounce: падение между ними даёт повторную доставку,
                # которую debounce-ключи отсекают; обратного порядка (потеря) нет.
                await _ack_batch(redis, ping_host, batch_id)
                sent += len(fresh)
            else:
                await _ack_batch(redis, ping_host, batch_id, requeue=fresh)
        except Exception:
            # Партия лежит в processing: возвращаем сразу, а если и это не вышло —
            # её вернёт _recover_stale_batches после таймаута.
            try:
                await _ack_batch(redis, ping_host, batch_id, requeue=batch)
            except Exception:
                logger.warning(
                    "IndexNow drain: %d URL(s) stay in processing batch %s of %s until timeout",
                    len(batch), batch_id, queue_key,
                )
            raise
    return sent


async def indexnow_drain_job() -> None:
    n = await drain_indexnow_queue()
    if n:
        logger.info("IndexNow drain: pinged %d URL(s)", n)


async def indexnow_warm_job() -> None:
    """Еженедельная warm-подпитка очереди (dual-host план, Фаза B/C).

    Кладёт в очередь IndexNow: (1) статические секции-хабы (core/today/
    ratings/regions/world — без years-чанков), (2) demand-URL из
    webmaster_search_queries (потерянные показы). Debounce 24ч на URL
    отсекает уже отправленное; drain */10 мин раздаёт батчи по хостам.
    """
    from app.core.cache import get_state_redis
    from app.services.demand_router import priority_recrawl_paths

    if not settings.indexnow_enabled or not settings.indexnow_key:
        return
    redis = await get_state_redis()
    lock = await redis.set("in:warm:lock", "1", nx=True, ex=6 * 3600)
    if not lock:
        return  # другой воркер уже греет

    try:
        from app.database import async_session

        async with async_session() as db:
            for origin, host in _indexnow_targets():
                await ping_sections(db, origin=origin, host=host)
                demand_paths = [
                    path for path, _lost in await priority_recrawl_paths(
                        db, days=30, limit=150, host=host
                    )
                ]
                if demand_paths:
                    await enqueue_paths(demand_paths, origin=origin, host=host)
        logger.info("IndexNow warm: hubs + demand-URL queued")
    finally:
        await redis.delete("in:warm:lock")


async def indexnow_history_job() -> None:
    """Ежедневная порция длинного хвоста sitemap в очередь IndexNow."""
    from app.core.cache import get_state_redis

    if not settings.indexnow_enabled or not settings.indexnow_key:
        return
    redis = await get_state_redis()
    lock = await redis.set(_HISTORY_LOCK_KEY, "1", nx=True, ex=6 * 3600)
    if not lock:
        return
    try:
        from app.database import async_session

        async with async_session() as db:
            stats = await enqueue_history_urls(db)
        logger.info("IndexNow history: %s", stats)
    finally:
        await redis.delete(_HISTORY_LOCK_KEY)

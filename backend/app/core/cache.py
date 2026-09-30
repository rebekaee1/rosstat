import asyncio
from contextlib import asynccontextmanager
from collections.abc import Awaitable, Callable, Iterable
import hashlib
import json
import logging
import re
import time
import zlib
from typing import Any, Optional
from urllib.parse import urlparse, urlunparse

from redis.asyncio import Redis
from app.config import settings

logger = logging.getLogger(__name__)
_redis: Optional[Redis] = None
_state_redis: Optional[Redis] = None
# Бинарный клиент к тому же cache-Redis: SSR HTML хранится zlib-сжатым
# (decode_responses=True не пропустил бы байты).
_redis_bin: Optional[Redis] = None
_redis_lock = asyncio.Lock()
_REDIS_CONNECT_TIMEOUT = 1.5
_REDIS_READ_TIMEOUT = 1.5


async def get_redis() -> Redis:
    global _redis
    if _redis is not None:
        return _redis
    async with _redis_lock:
        if _redis is None:
            _redis = Redis.from_url(
                settings.redis_url, decode_responses=True,
                socket_connect_timeout=_REDIS_CONNECT_TIMEOUT,
                socket_timeout=_REDIS_READ_TIMEOUT,
            )
        return _redis


async def get_redis_bin() -> Redis:
    global _redis_bin
    if _redis_bin is not None:
        return _redis_bin
    async with _redis_lock:
        if _redis_bin is None:
            _redis_bin = Redis.from_url(
                settings.redis_url, decode_responses=False,
                socket_connect_timeout=_REDIS_CONNECT_TIMEOUT,
                socket_timeout=_REDIS_READ_TIMEOUT,
            )
        return _redis_bin


def _state_redis_url() -> str:
    """URL Redis для долгоживущего состояния (сессии, lockout, гостевые лимиты).

    Отдельный logical DB (по умолчанию /1 при кэше в /0): деплойный
    `redis-cli FLUSHDB` чистит ТОЛЬКО кэш и не разлогинивает пользователей.
    До этого фикса (2026-07-02) каждый FLUSHDB сносил и сессии — «авторизация
    слетала» после любого деплоя с derived-правками.
    """
    if settings.state_redis_url:
        return settings.state_redis_url
    parsed = urlparse(settings.redis_url)
    path = parsed.path or "/0"
    try:
        db = int(path.lstrip("/") or "0")
    except ValueError:
        db = 0
    return urlunparse(parsed._replace(path=f"/{db + 1}"))


async def get_state_redis() -> Redis:
    """Подключение к state-DB (сессии/lockout/квоты) — переживает FLUSHDB кэша."""
    global _state_redis
    if _state_redis is not None:
        return _state_redis
    async with _redis_lock:
        if _state_redis is None:
            _state_redis = Redis.from_url(
                _state_redis_url(), decode_responses=True,
                socket_connect_timeout=_REDIS_CONNECT_TIMEOUT,
                socket_timeout=_REDIS_READ_TIMEOUT,
            )
        return _state_redis


_sync_state_redis = None


def get_state_redis_sync():
    """Синхронный клиент state-Redis для ETL в `asyncio.to_thread`.

    Ленивый singleton; при ошибке транспорта вызывающий код должен fail-open.
    Не путать с async `get_state_redis` — event loop из thread не трогаем.
    """
    global _sync_state_redis
    if _sync_state_redis is not None:
        return _sync_state_redis
    import redis as redis_sync

    _sync_state_redis = redis_sync.Redis.from_url(
        _state_redis_url(),
        decode_responses=True,
        socket_connect_timeout=_REDIS_CONNECT_TIMEOUT,
        socket_timeout=_REDIS_READ_TIMEOUT,
    )
    return _sync_state_redis


async def close_redis():
    global _redis, _state_redis, _sync_state_redis, _redis_bin
    if _redis:
        await _redis.aclose()
        _redis = None
    if _redis_bin:
        await _redis_bin.aclose()
        _redis_bin = None
    if _state_redis:
        await _state_redis.aclose()
        _state_redis = None
    if _sync_state_redis is not None:
        try:
            _sync_state_redis.close()
        except Exception:
            pass
        _sync_state_redis = None


# Н-17: fail-open кэша считаем — единичный сбой это warning, всплеск (Redis
# лежит) должен быть виден как метрика (/metrics) и error-лог каждые N сбоев.
failure_counters: dict[str, int] = {"cache_get": 0, "cache_set": 0, "cache_invalidate": 0}
_ESCALATE_EVERY = 100


def _note_cache_failure(op: str, detail: str) -> None:
    failure_counters[op] += 1
    if failure_counters[op] % _ESCALATE_EVERY == 0:
        logger.error(
            "Redis cache degraded: %s failed %d times total (%s)",
            op, failure_counters[op], detail,
        )
    else:
        logger.warning("Redis %s failed for '%s', proceeding without cache", op, detail)


async def cache_get(key: str) -> Optional[Any]:
    try:
        r = await get_redis()
        val = await r.get(key)
        if val is not None:
            return json.loads(val)
    except Exception:
        _note_cache_failure("cache_get", key)
    return None


async def cache_set(key: str, value: Any, ttl: int | None = None):
    try:
        r = await get_redis()
        ttl = ttl or settings.cache_ttl_data
        await r.set(key, json.dumps(value, default=str), ex=ttl)
    except Exception:
        _note_cache_failure("cache_set", key)


# --- SSR HTML: zlib-сжатие значений (perf batch 2) --------------------------
#
# Готовый SSR HTML — 60–300 КБ текста; zlib level 6 сжимает его в ~6,3 раза за
# ~0,7 мс на страницу. При maxmemory 256mb это ~6x больше страниц в кэше,
# т.е. выше hit-rate под бот-прожигом уникальных URL.
# Формат: b"\x00z1" + zlib(html utf-8). Префикс с NUL не может начинать
# JSON-текст, поэтому старые (до релиза) несжатые значения `json.dumps(html)`
# читаются как раньше — обратная совместимость без миграции/флаша.
_SSR_ZLIB_PREFIX = b"\x00z1"
_SSR_ZLIB_LEVEL = 6


def encode_ssr_html(html: str) -> bytes:
    return _SSR_ZLIB_PREFIX + zlib.compress(html.encode("utf-8"), _SSR_ZLIB_LEVEL)


def decode_ssr_value(raw: bytes | str | None) -> Optional[Any]:
    if raw is None:
        return None
    if isinstance(raw, bytes) and raw.startswith(_SSR_ZLIB_PREFIX):
        return zlib.decompress(raw[len(_SSR_ZLIB_PREFIX):]).decode("utf-8")
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return json.loads(raw)  # legacy: несжатый json.dumps(html)


async def ssr_cache_get(key: str) -> Optional[Any]:
    """Чтение SSR HTML: сжатое (новое) или legacy-JSON значение."""
    try:
        r = await get_redis_bin()
        return decode_ssr_value(await r.get(key))
    except Exception:
        _note_cache_failure("cache_get", key)
    return None


async def ssr_cache_set(key: str, value: Any, ttl: int | None = None):
    """Запись SSR HTML (str) zlib-сжатым; не-строки — legacy JSON."""
    try:
        r = await get_redis_bin()
        ttl = ttl or settings.cache_ttl_data
        if isinstance(value, str):
            payload: bytes = encode_ssr_html(value)
        else:
            payload = json.dumps(value, default=str).encode("utf-8")
        await r.set(key, payload, ex=ttl)
    except Exception:
        _note_cache_failure("cache_set", key)


# --- П-11: версионированные namespace вместо pattern-delete -----------------
#
# Инвалидация раньше делала 6 SCAN-проходов по всему keyspace на КАЖДЫЙ
# обновившийся индикатор — массовый derived-апдейт (сотни кодов) = тысячи SCAN.
# Теперь ключ включает версию namespace (`fe:{ns}:v{N}:{rest}`), инвалидация —
# один INCR `fe:ver:{ns}`: старые ключи мгновенно перестают читаться и
# протухают по своему TTL или вытесняются volatile-lru; fe:ver:* без TTL
# должен оставаться в памяти, иначе старые версии ключей могут воскреснуть.
#
# Версию каждого namespace держим в per-process кэше на _VER_LOCAL_TTL секунд,
# чтобы не платить лишний Redis-GET на каждое чтение; цена — до 5 секунд
# устаревания после инвалидации из ДРУГОГО процесса (TTL данных был 300–3600с,
# это заведомо приемлемо). Свой bump сбрасывает локальную запись сразу.

_VER_LOCAL_TTL = 5.0
_ver_local: dict[str, tuple[float, str]] = {}
_WORLD_CATALOG_VERSION_KEY = "fe:ver:world-catalog"


class WorldCatalogInvalidationError(RuntimeError):
    """A committed catalogue change could not invalidate public cache keys."""


async def _ns_version(ns: str) -> str:
    now = time.monotonic()
    hit = _ver_local.get(ns)
    if hit and now - hit[0] < _VER_LOCAL_TTL:
        return hit[1]
    try:
        # DB 0 can be flushed during manual recovery. The country-catalog
        # generation lives with its durable mirror in state Redis so a flush
        # can warm DB 0 without rebuilding the expensive SQL catalogue.
        r = await (get_state_redis() if ns == "world-catalog" else get_redis())
        ver = await r.get(f"fe:ver:{ns}") or "0"
    except Exception:
        # Other namespaces are best-effort. Public world-catalogue keys must
        # never fall back to a guessed generation when state Redis is down.
        if ns == "world-catalog":
            raise
        ver = hit[1] if hit else "0"
    _ver_local[ns] = (now, ver)
    return ver


async def versioned_key(ns: str, rest: str) -> str:
    """Ключ кэша в инвалидируемом namespace: `fe:{ns}:v{N}:{rest}`."""
    ver = await _ns_version(ns)
    if ns == "world-catalog":
        # g2 isolates the state-Redis generation from legacy DB0 vN keys.
        return f"fe:{ns}:g2:v{ver}:{rest}"
    return f"fe:{ns}:v{ver}:{rest}"


async def fresh_world_catalog_key(rest: str) -> str:
    """Build an API cache key from state Redis without the five-second memo.

    A catalogue API response is publicly cacheable for up to five minutes,
    so its key must reflect an ingest bump before we emit that response.
    State Redis errors propagate: serving a guessed generation could promote
    stale catalogue data into the public cache.
    """
    r = await get_state_redis()
    ver = await r.get(_WORLD_CATALOG_VERSION_KEY) or "0"
    return f"fe:world-catalog:g2:v{ver}:{rest}"


async def bump_namespaces(*namespaces: str) -> None:
    """Invalidate DB0 namespaces and atomically advance durable catalogue state."""
    cache_namespaces = [ns for ns in namespaces if ns != "world-catalog"]
    try:
        if cache_namespaces:
            r = await get_redis()
            async with r.pipeline(transaction=False) as pipe:
                for ns in cache_namespaces:
                    pipe.incr(f"fe:ver:{ns}")
                await pipe.execute()
    except Exception:
        _note_cache_failure("cache_invalidate", ",".join(cache_namespaces))
    if "world-catalog" in namespaces:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                r = await get_state_redis()
                await r.eval(
                    _BUMP_WORLD_CATALOG_SCRIPT, 5,
                    _WORLD_CATALOG_VERSION_KEY,
                    _world_countries_pointer_key("ru"),
                    _world_countries_pointer_key("en"),
                    _world_countries_stale_key("ru"),
                    _world_countries_stale_key("en"),
                    _WORLD_COUNTRIES_STALE_SECONDS,
                )
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(0.1 * (attempt + 1))
        if last_error is not None:
            failure_counters["cache_invalidate"] += 1
            logger.error("Redis world-catalog invalidation failed after three attempts")
            raise WorldCatalogInvalidationError(
                "world-catalog generation was not advanced in state Redis"
            ) from last_error
    for ns in namespaces:
        _ver_local.pop(ns, None)
    if "world-catalog" in namespaces:
        await clear_durable_world_countries()




# --- Durable world-countries catalogue (survives manual DB 0 FLUSHDB) ---
# Cold build of /world/countries can take tens of seconds. State-Redis keeps a
# locale-keyed mirror so home SSR #fe-bootstrap and the API stay fast. Normal
# deploys purge SSR keys rather than flushing DB 0; the mirror also protects
# manual recovery or a Redis cache restart.
_DURABLE_WORLD_COUNTRIES_PREFIX = "fe:durable:world-countries:"
_DURABLE_WORLD_COUNTRIES_TTL = 30 * 24 * 3600  # 30 days; old generations expire


def durable_world_countries_key(locale: str) -> str:
    return f"{_DURABLE_WORLD_COUNTRIES_PREFIX}{locale}"


async def get_durable_world_countries(locale: str) -> Optional[Any]:
    try:
        r = await get_state_redis()
        val = await r.get(durable_world_countries_key(locale))
        if val is not None:
            return json.loads(val)
    except Exception:
        _note_cache_failure("cache_get", f"durable-countries:{locale}")
    return None


async def set_durable_world_countries(locale: str, payload: Any) -> None:
    try:
        r = await get_state_redis()
        await r.set(
            durable_world_countries_key(locale),
            json.dumps(payload, default=str),
            ex=_DURABLE_WORLD_COUNTRIES_TTL,
        )
    except Exception:
        _note_cache_failure("cache_set", f"durable-countries:{locale}")


async def clear_durable_world_countries() -> None:
    """Drop legacy unversioned mirrors after a world-catalog bump.

    Versioned mirrors are retained: the last successfully built generation
    can be served stale for a fixed five-minute grace after the first bump.
    """
    try:
        r = await get_state_redis()
        keys = [durable_world_countries_key(loc) for loc in ("ru", "en")]
        if keys:
            await r.delete(*keys)
    except Exception:
        _note_cache_failure("cache_invalidate", "durable-countries")


# Versioned mirror for the world catalogue. The key includes the *complete*
# DB 0 cache key (including response schema and locale), so a late pre-bump
# builder cannot repopulate the current generation with an older payload.
_WORLD_COUNTRIES_V2_PREFIX = "fe:durable:world-countries:g2:"
_WORLD_COUNTRIES_KEY_RE = re.compile(
    r"^fe:world-catalog:g2:v(?P<version>\d+):countries:v\d+:(?P<locale>ru|en)$"
)
_WORLD_COUNTRIES_STALE_SECONDS = 300
_WORLD_COUNTRIES_LOCK_SECONDS = 180
# A missed ingest invalidation must not leave a durable response fresh forever.
# At most one cross-worker cold build per locale is needed every 26 hours in
# the no-bump case; DB0's 600s TTL can extend this bound by at most 10 minutes.
_WORLD_COUNTRIES_MAX_FRESH_SECONDS = 26 * 3600

# All generation, pointer and grace changes happen in state Redis atomically.
# The pointer always names the last *successfully published* country cache key.
# A second bump before a successful build must keep the original deadline.
_BUMP_WORLD_CATALOG_SCRIPT = """
local old = tonumber(redis.call('GET', KEYS[1]) or '0')
local new = redis.call('INCR', KEYS[1])
for i = 2, 3 do
  local pointer = redis.call('GET', KEYS[i])
  local pointer_version = pointer and string.match(pointer, '^fe:world%-catalog:g2:v(%d+):countries:v%d+:')
  if pointer_version and tonumber(pointer_version) == old then
    local deadline = tonumber(redis.call('TIME')[1]) + tonumber(ARGV[1])
    redis.call('SET', KEYS[i + 2], tostring(deadline), 'EX', tonumber(ARGV[1]))
  end
end
return new
"""

_PUBLISH_WORLD_COUNTRIES_SCRIPT = """
if tonumber(redis.call('GET', KEYS[1]) or '0') ~= tonumber(ARGV[1]) then
  return 0
end
redis.call('SET', KEYS[2], ARGV[2], 'EX', tonumber(ARGV[3]))
redis.call('SET', KEYS[3], ARGV[4])
redis.call('DEL', KEYS[4])
return 1
"""


def _world_countries_key_parts(locale: str, cache_key: str) -> int:
    match = _WORLD_COUNTRIES_KEY_RE.fullmatch(cache_key)
    if match is None or match.group("locale") != locale:
        raise ValueError("invalid world-countries cache key")
    return int(match.group("version"))


def _versioned_durable_world_countries_key(locale: str, cache_key: str) -> str:
    _world_countries_key_parts(locale, cache_key)
    digest = hashlib.sha256(cache_key.encode()).hexdigest()[:24]
    return f"{_WORLD_COUNTRIES_V2_PREFIX}{locale}:{digest}"


def _world_countries_pointer_key(locale: str) -> str:
    return f"{_WORLD_COUNTRIES_V2_PREFIX}last-good:{locale}"


def _world_countries_stale_key(locale: str) -> str:
    return f"{_WORLD_COUNTRIES_V2_PREFIX}stale:{locale}"


def _world_countries_payload(raw: str | None) -> Optional[Any]:
    if raw is None:
        return None
    envelope = json.loads(raw)
    built_at = envelope.get("built_at")
    if not isinstance(built_at, (int, float)):
        return None
    age = time.time() - built_at
    if age < -60 or age > _WORLD_COUNTRIES_MAX_FRESH_SECONDS:
        return None
    return envelope.get("payload")


async def get_versioned_durable_world_countries(
    locale: str, cache_key: str, *, allow_stale: bool = False,
) -> tuple[Optional[Any], bool]:
    """Return (payload, is_stale) from the state-Redis mirror.

    A stale payload is the last successfully published generation, even if two
    ingests bump before a build finishes. Its five-minute grace starts on the
    first bump and is never renewed by subsequent bumps without a good build.
    The caller must send ``Cache-Control: no-store`` for a stale response so a
    browser or shared proxy cannot extend that freshness bound.
    """
    version = _world_countries_key_parts(locale, cache_key)
    try:
        r = await get_state_redis()
        current_raw, raw, pointer, grace = await r.mget(
            _WORLD_CATALOG_VERSION_KEY,
            _versioned_durable_world_countries_key(locale, cache_key),
            _world_countries_pointer_key(locale),
            _world_countries_stale_key(locale),
        )
        current = int(current_raw or "0")
        if current != version:
            return None, False
        payload = _world_countries_payload(raw)
        if payload is not None:
            return payload, False
        if (
            not allow_stale or grace is None or time.time() >= int(grace)
            or not pointer or pointer == cache_key
        ):
            return None, False
        # Keep the same response schema and locale across generations.
        old_version = _world_countries_key_parts(locale, pointer)
        if old_version >= version or pointer.split(":", 4)[4] != cache_key.split(":", 4)[4]:
            return None, False
        payload = _world_countries_payload(
            await r.get(_versioned_durable_world_countries_key(locale, pointer))
        )
        if payload is not None:
            return payload, True
    except Exception:
        _note_cache_failure("cache_get", f"durable-countries-v2:{locale}")
    return None, False


async def set_versioned_durable_world_countries(
    locale: str, cache_key: str, payload: Any,
) -> bool:
    """Atomically publish a successful SQL build only for its generation."""
    version = _world_countries_key_parts(locale, cache_key)
    try:
        r = await get_state_redis()
        published = await r.eval(
            _PUBLISH_WORLD_COUNTRIES_SCRIPT, 4,
            _WORLD_CATALOG_VERSION_KEY,
            _versioned_durable_world_countries_key(locale, cache_key),
            _world_countries_pointer_key(locale),
            _world_countries_stale_key(locale),
            version,
            json.dumps({"built_at": time.time(), "payload": payload}, default=str),
            _DURABLE_WORLD_COUNTRIES_TTL,
            cache_key,
        )
        return published == 1
    except Exception:
        _note_cache_failure("cache_set", f"durable-countries-v2:{locale}")
        return False


async def is_current_world_countries_key(locale: str, cache_key: str) -> bool:
    """Read the durable generation directly, bypassing the five-second memo.

    Call after a cold SQL build and before publishing it. A bump in the
    meantime means the result must be retried or discarded, not cached under
    a newly computed key.
    """
    version = _world_countries_key_parts(locale, cache_key)
    try:
        r = await get_state_redis()
        return int(await r.get(_WORLD_CATALOG_VERSION_KEY) or "0") == version
    except Exception:
        _note_cache_failure("cache_get", "world-catalog-version")
        return False


@asynccontextmanager
async def world_countries_build_lock(
    locale: str, *, wait_seconds: float = 12.0,
):
    """Cross-worker singleflight for a cold country-catalog SQL build.

    Redis-state is required on a double miss; callers should return 503 if
    acquiring the lock fails and no bounded stale mirror is available.
    Recheck DB 0 and the durable mirror *inside* the lock before building.
    """
    if locale not in ("ru", "en"):
        raise ValueError("invalid world-countries locale")
    r = await get_state_redis()
    lock = r.lock(
        f"fe:lock:world-countries:{locale}",
        timeout=_WORLD_COUNTRIES_LOCK_SECONDS,
        blocking_timeout=wait_seconds,
        sleep=0.1,
    )
    acquired = await lock.acquire()
    if not acquired:
        yield False
        return
    try:
        yield True
    finally:
        try:
            await lock.release()
        except Exception:
            _note_cache_failure("cache_invalidate", f"world-countries-lock:{locale}")

async def cache_invalidate_indicator(code: str):
    """После ETL/derived-апдейта: сам код (detail/data/SSR/embed живут в
    namespace кода), общий листинг и dashboard-спарклайны."""
    await bump_namespaces(code, "indicators", "dashboard")


async def publish_committed_indicator_changes(
    codes: Iterable[str], *,
    invalidate: Callable[[str], Awaitable[None]] | None = None,
) -> None:
    """Publish *already committed* SQL changes; a cache error cannot undo them.

    SQL transaction owners call this after commit, passing changed source and
    derived codes. Ordinary Redis failures remain best effort (existing TTL is
    the fallback), and each code is attempted independently. Cancellation waits
    for the bounded publication attempt, then propagates to the owner; this is
    not a distributed transaction or a durable retry queue.
    """
    changed = tuple(dict.fromkeys(codes))
    if not changed:
        return
    publisher = invalidate or cache_invalidate_indicator

    async def publish() -> None:
        for code in changed:
            try:
                await publisher(code)
            except Exception:
                logger.exception("Committed indicator '%s': cache publication failed", code)

    publication = asyncio.create_task(asyncio.wait_for(publish(), timeout=15))
    cancelled = False
    try:
        while not publication.done():
            try:
                await asyncio.shield(publication)
            except asyncio.CancelledError:
                cancelled = True
        publication.result()
    except Exception:
        logger.exception("Committed indicator changes: cache publication did not finish")
    if cancelled:
        raise asyncio.CancelledError

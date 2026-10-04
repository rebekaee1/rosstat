"""Распределённая блокировка фоновых задач: lease с владельцем и heartbeat (F07).

Было (О-13): `SET NX EX ttl` без продления. Задача, прожившая дольше TTL
(sitemap_build ~15+ мин, ETL, прогнозы), теряла ключ, второй процесс запускал
ту же работу параллельно, а первый об этом не знал; daily и evening ETL имели
разные ключи и могли пересечься.

Стало:
* значение ключа — токен владельца (pid + uuid запуска);
* heartbeat раз в TTL/3 продлевает ключ Lua-скриптом «только если владелец я»;
* освобождение — compare-and-delete (чужой ключ не трогаем);
* продление вернуло 0 (ключ пропал или принадлежит другому) → lease потерян:
  выставляется флаг (`job_lease_lost()`), корутина задачи отменяется, wrapper
  бросает `JobLeaseLostError` — APScheduler получит EVENT_JOB_ERROR и штатный
  алерт сработает. Ошибка транспорта Redis при продлении потерей НЕ считается
  (Redis недоступен — поведение как раньше, не падаем), следующий heartbeat
  проверит владение;
* группы взаимоисключения (`JOB_LOCK_GROUPS`): задачи одной группы делят ключ.

Ограничение: отмена — это `task.cancel()`, она срабатывает на ближайшем `await`.
Синхронный код в `to_thread`/executor дорабатывает сам; долгие задачи могут
опрашивать `job_lease_lost()` между шагами.
"""
from __future__ import annotations

import asyncio
import contextlib
import contextvars
import logging
import os
import uuid

logger = logging.getLogger(__name__)

# Группы взаимоисключения: job_id -> имя группы. Задачи одной группы берут ОДИН
# ключ `sched:lock:{группа}` и потому не идут параллельно. Задача вне словаря
# блокируется по собственному job_id.
#
# "etl": daily_etl и evening_etl — один и тот же daily_update_job; late_minfin_etl
# и late_fred_etl вызывают run_etl_for_parser_type и пишут в те же таблицы
# (data_points/etl_runs/кэш карточек), поэтому с полным ETL не пересекаются.
# Следствие: если полный ETL ещё идёт, позднее окно (15:00/23:30) пропускается
# с логом «lock held» — полный прогон и так обновит те же источники.
JOB_LOCK_GROUPS: dict[str, str] = {
    "daily_etl": "etl",
    "evening_etl": "etl",
    "late_minfin_etl": "etl",
    "late_fred_etl": "etl",
}

LOCK_KEY_PREFIX = "sched:lock:"
# Продлеваем раз в TTL/3: два подряд сорванных heartbeat всё ещё укладываются в TTL.
HEARTBEAT_DIVISOR = 3

_RELEASE_LUA = (
    "if redis.call('GET', KEYS[1]) == ARGV[1] then "
    "return redis.call('DEL', KEYS[1]) else return 0 end"
)
# PEXPIRE возвращает 1, если ключ существует. Чужой токен / нет ключа -> 0.
_RENEW_LUA = (
    "if redis.call('GET', KEYS[1]) == ARGV[1] then "
    "return redis.call('PEXPIRE', KEYS[1], ARGV[2]) else return 0 end"
)


class JobLeaseLostError(RuntimeError):
    """Блокировка задачи потеряна (ключ истёк или перехвачен), задача остановлена."""


class _LeaseState:
    __slots__ = ("job_id", "key", "token", "lost")

    def __init__(self, job_id: str, key: str, token: str):
        self.job_id = job_id
        self.key = key
        self.token = token
        self.lost = False


_current_lease: contextvars.ContextVar[_LeaseState | None] = contextvars.ContextVar(
    "job_lease", default=None
)


def job_lease_lost() -> bool:
    """True, если lease текущей задачи потерян (для долгих циклов внутри задачи)."""
    state = _current_lease.get()
    return bool(state and state.lost)


def lock_key_for(job_id: str) -> str:
    return f"{LOCK_KEY_PREFIX}{JOB_LOCK_GROUPS.get(job_id, job_id)}"


async def _heartbeat(redis, state: _LeaseState, ttl_ms: int, interval: float,
                     job_task: "asyncio.Future") -> None:
    while True:
        await asyncio.sleep(interval)
        try:
            renewed = await redis.eval(_RENEW_LUA, 1, state.key, state.token, ttl_ms)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Redis моргнул: не знаем, потеряли ли ключ. Не отменяем — проверим
            # владение на следующем тике.
            logger.warning("Job %s: lease renewal failed (Redis error), will retry",
                           state.job_id)
            continue
        if not renewed:
            state.lost = True
            logger.error(
                "Job %s: lease LOST (key %s expired or taken by another owner); "
                "cancelling the job", state.job_id, state.key,
            )
            if not job_task.done():
                job_task.cancel()
            return


def locked_job(fn, job_id: str, ttl_seconds: float):
    """О-13/F07: распределённая блокировка задачи (state-Redis lease с heartbeat).

    Занято другим владельцем — запуск пропускается (лог). Redis недоступен —
    fail-open: задача идёт без блокировки (single-instance допущение важнее
    пропуска прогона).
    """
    ttl_ms = max(1, int(ttl_seconds * 1000))
    interval = ttl_seconds / HEARTBEAT_DIVISOR

    async def wrapper(*args, **kwargs):
        from app.core.cache import get_state_redis

        key = lock_key_for(job_id)
        token = f"{os.getpid()}:{uuid.uuid4().hex}"
        redis = None
        try:
            redis = await get_state_redis()
            acquired = await redis.set(key, token, nx=True, px=ttl_ms)
            if not acquired:
                logger.info(
                    "Job %s: lock %s held by another run, skipping", job_id, key
                )
                return None
        except Exception:
            logger.warning("Job %s: lock check failed (Redis down), running unlocked", job_id)
            redis = None

        if redis is None:
            return await fn(*args, **kwargs)

        state = _LeaseState(job_id, key, token)
        reset = _current_lease.set(state)
        try:
            # Отдельная Task, чтобы heartbeat мог её отменить; контекст
            # (с _current_lease) копируется при создании.
            job_task = asyncio.ensure_future(fn(*args, **kwargs))
        finally:
            _current_lease.reset(reset)
        hb_task = asyncio.create_task(_heartbeat(redis, state, ttl_ms, interval, job_task))
        try:
            try:
                result = await job_task
            except asyncio.CancelledError:
                me = asyncio.current_task()
                outer_cancelled = me is not None and me.cancelling() > 0
                if state.lost and not outer_cancelled:
                    raise JobLeaseLostError(
                        f"job {job_id}: lock {key} lost, job cancelled"
                    ) from None
                raise
            if state.lost:
                # Успела закончиться между потерей lease и отменой.
                logger.error("Job %s: finished although its lease was lost "
                             "(possible overlap with another run)", job_id)
                _alert_lost(job_id)
            return result
        finally:
            hb_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await hb_task
            try:
                # compare-and-delete: чужой/истёкший ключ не трогаем.
                await redis.eval(_RELEASE_LUA, 1, key, token)
            except Exception:
                pass  # TTL добьёт ключ сам

    wrapper.__name__ = f"locked_{getattr(fn, '__name__', job_id)}"
    return wrapper


def _alert_lost(job_id: str) -> None:
    try:
        from html import escape

        from app.services.alerting import send_telegram

        asyncio.get_running_loop().create_task(send_telegram(
            f"🔴 <b>Потеряна блокировка задачи</b>\n{escape(job_id)}: задача дошла до "
            "конца, но её lease пропал — возможен параллельный запуск.",
            kind="job_lease_lost",
        ))
    except Exception:
        logger.exception("lease-lost alert failed")

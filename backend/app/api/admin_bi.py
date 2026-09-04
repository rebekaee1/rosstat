"""Админ-BI: /api/v1/admin/bi/* (директива владельца 2026-07-05).

Доступ — только пользователям из settings.admin_emails (вход обычной
сессией /auth/login; email сверяется по способам входа). Обычные
пользователи и гости получают 404 (не раскрываем существование раздела).

Кэш дашборда — Redis 15 минут: фронт поллит каждые 15 минут и получает
свежий срез без пересчёта витрин на каждый запрос.

Инцидент 2026-09-03: Depends(get_current_user)+get_db держали public-пул
на весь расчёт дашборда (минуты) → витрина ждала соединение → SSL timeout.
Админ-проверка открывает public-сессию на миллисекунды и закрывает её
до тяжёлой работы. Расчёт — только analytics_session, и только на cache-miss.

Инцидент 2026-09-04: сборка 7d ≈ 36 с на проде, таймаут axios 15 с. Клиент
рвал запрос (nginx 499), ретраил, а оборванные корутины продолжали строить
дашборд под замком — очередь сканов behavior_events на минуты, диск встал,
публичные API (тикер, рейтинг стран) ушли в таймауты. Дашборд при холодном
кэше не мог загрузиться в принципе. Теперь расчёт живёт в фоне и никогда не
привязан к времени жизни HTTP-запроса:

- cache-miss → single-flight фоновая задача на ключ, ответ 202 «считаем»,
  фронт опрашивает раз в несколько секунд;
- stale-while-revalidate: снимок хранится сутки, после «свежего» окна отдаётся
  сразу с пометкой stale, пересчёт стартует в фоне;
- повторные/оборванные запросы не порождают новых сборок — они присоединяются
  к уже идущей;
- `wait=N` — дождаться результата до N секунд (тесты, CLI).
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_analytics_db, get_db
from app.models import EmailCredential, OAuthIdentity, User
from app.security.auth import current_session
from app.services.api_i18n import api_detail

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/bi", tags=["admin-bi"])

_BI_CACHE_TTL = 15 * 60  # владелец: «подтягивала данные раз в 15 минут»
_BI_CACHE_TTL_LIVE = 5 * 60  # окно, включающее сегодня, растёт в реальном времени
# Сколько живёт снимок как «устаревший, но показываемый» (SWR).
_BI_SNAPSHOT_TTL = 24 * 3600
# Сколько помним ошибку сборки, чтобы не крутить «считаем» вечно.
_BI_ERROR_TTL = 60
# Один расчёт на воркер: два параллельных cache-miss удваивали RAM и пул.
_DASHBOARD_LOCK = asyncio.Lock()


@dataclass
class _Build:
    """Идущая фоновая сборка одного ключа кэша (single-flight)."""

    task: asyncio.Task
    started_at: float = field(default_factory=time.monotonic)


_INFLIGHT: dict[str, _Build] = {}
_LAST_ERROR: dict[str, tuple[float, str]] = {}


def _snapshot_key(p) -> str:
    return f"fe:admin:bi:dashboard:v2:{p.preset}:{p.start_date}:{p.end_date}"


def _fresh_ttl(p) -> int:
    from app.services.analytics_period import resolve_period

    live = p.end_date >= resolve_period("today").start_date
    return _BI_CACHE_TTL_LIVE if live else _BI_CACHE_TTL


def _with_meta(snap: dict[str, Any], *, refreshing: bool) -> dict[str, Any]:
    """Данные дашборда + служебный блок о возрасте снимка."""
    built_at = float(snap.get("built_at") or 0)
    fresh_for = int(snap.get("fresh_for") or _BI_CACHE_TTL)
    age = max(0, int(time.time() - built_at))
    data = dict(snap["data"])
    data["cache_meta"] = {
        "built_at": snap.get("built_at_iso"),
        "age_sec": age,
        "stale": age > fresh_for,
        "refreshing": refreshing,
    }
    return data


async def _run_build(app, key: str, p) -> dict[str, Any]:
    """Фоновая сборка: своя analytics-сессия, кэш на сутки, метаданные снимка."""
    from datetime import datetime, timezone

    from app.core.cache import cache_set
    from app.services.admin_bi import build_bi_dashboard

    try:
        async with _DASHBOARD_LOCK:
            dep = app.dependency_overrides.get(get_analytics_db, get_analytics_db)
            agen = dep()
            db = await agen.__anext__()
            try:
                data = await build_bi_dashboard(db, p)
            finally:
                await agen.aclose()
        now = time.time()
        snap = {
            "data": data,
            "built_at": now,
            "built_at_iso": datetime.fromtimestamp(now, tz=timezone.utc)
            .replace(tzinfo=None).isoformat(timespec="seconds"),
            "fresh_for": _fresh_ttl(p),
        }
        await cache_set(key, snap, ttl=_BI_SNAPSHOT_TTL)
        _LAST_ERROR.pop(key, None)
        return snap
    except Exception as exc:
        logger.exception("BI dashboard build failed (%s)", key)
        _LAST_ERROR[key] = (time.monotonic(), f"{type(exc).__name__}: {exc}"[:200])
        raise
    finally:
        _INFLIGHT.pop(key, None)


def _ensure_build(app, key: str, p) -> _Build:
    """Запустить сборку, если по ключу ещё не идёт; вернуть текущую."""
    build = _INFLIGHT.get(key)
    if build is None or build.task.done():
        task = asyncio.get_running_loop().create_task(
            _run_build(app, key, p), name=f"bi-build:{key}"
        )
        build = _Build(task=task)
        _INFLIGHT[key] = build
    return build


def _building_response(build: _Build, queued: int) -> JSONResponse:
    return JSONResponse(
        status_code=202,
        content={
            "status": "building",
            "elapsed_sec": int(time.monotonic() - build.started_at),
            "queued_builds": queued,
        },
    )


@asynccontextmanager
async def _override_aware_session(request: Request, dep):
    """Короткая сессия: чтит FastAPI dependency_overrides (sqlite-тесты)."""
    fn = request.app.dependency_overrides.get(dep, dep)
    agen = fn()
    session = await agen.__anext__()
    try:
        yield session
    finally:
        await agen.aclose()


async def user_is_admin(db: AsyncSession, user: User) -> bool:
    from app.config import settings

    allowed = {
        e.strip().lower() for e in settings.admin_emails.split(",") if e.strip()
    }
    if not allowed:
        return False
    emails = set()
    cred = await db.scalar(
        select(EmailCredential.email).where(EmailCredential.user_id == user.id)
    )
    if cred:
        emails.add(cred.lower())
    for row in (await db.execute(
        select(OAuthIdentity.email).where(OAuthIdentity.user_id == user.id)
    )).scalars():
        if row:
            emails.add(row.lower())
    return bool(emails & allowed)


async def require_admin(request: Request) -> User:
    """Админ-гейт без удержания public-пула на время дашборда/среза."""
    sess = await current_session(request)
    if not sess:
        raise HTTPException(
            status_code=401,
            detail=api_detail("Не авторизован", "Not authenticated"),
        )
    async with _override_aware_session(request, get_db) as db:
        from app.services.identity.service import get_user

        user = await get_user(db, sess["user_id"])
        if user is None or user.status != "active":
            raise HTTPException(
                status_code=401,
                detail=api_detail("Не авторизован", "Not authenticated"),
            )
        if not await user_is_admin(db, user):
            raise HTTPException(status_code=404, detail="Not found")
        db.expunge(user)
        return user


@router.get("/dashboard")
async def bi_dashboard(
    request: Request,
    period: str = Query("30d", description="Пресет: today/yesterday/7d/30d/90d/custom"),
    date_from: str | None = Query(None, alias="from", description="МСК-дата начала (custom)"),
    date_to: str | None = Query(None, alias="to", description="МСК-дата конца (custom)"),
    days: int | None = Query(None, ge=1, le=365, description="Легаси-параметр: N последних дней"),
    fresh: bool = Query(False, description="Принудительный пересчёт (в фоне; пока идёт — отдаём прошлый снимок)"),
    wait: float = Query(0, ge=0, le=300, description="Ждать результат до N секунд вместо 202"),
    _admin: User = Depends(require_admin),
):
    from app.core.cache import cache_get
    from app.services.analytics_period import as_period, resolve_period

    if days is not None and period == "30d" and not date_from:
        p = as_period(days)  # легаси-вызовы ?days=N продолжают работать
    else:
        p = resolve_period(period, date_from, date_to)

    key = _snapshot_key(p)
    snap = await cache_get(key)
    age = time.time() - float(snap.get("built_at") or 0) if snap else None
    stale = snap is None or age > int(snap.get("fresh_for") or _BI_CACHE_TTL)

    build = _INFLIGHT.get(key)
    if build is not None and build.task.done():
        build = None
    err = _LAST_ERROR.get(key)
    recent_error = err is not None and time.monotonic() - err[0] < _BI_ERROR_TTL
    # После падения сборки не перезапускаем её каждым опросом фронта — минуту
    # отвечаем 503 с причиной; `fresh` позволяет форсировать повтор.
    if build is None and (fresh or (stale and not recent_error)):
        build = _ensure_build(request.app, key, p)

    if build is not None and wait:
        try:
            snap = await asyncio.wait_for(asyncio.shield(build.task), timeout=wait)
            build = None
        except asyncio.TimeoutError:
            pass
        except Exception:
            build = None
            if snap is None:
                raise HTTPException(
                    status_code=503, detail="Витрины временно недоступны"
                ) from None

    if snap is not None:
        # SWR: устаревший снимок показываем сразу, пересчёт идёт в фоне.
        return _with_meta(snap, refreshing=build is not None)

    if build is None:
        raise HTTPException(
            status_code=503,
            detail=f"Витрины временно недоступны: {err[1] if err else 'сборка не удалась'}",
        )
    return _building_response(build, queued=len(_INFLIGHT))


@router.get("/slices/meta")
async def slices_meta(_admin: User = Depends(require_admin)):
    """Справочник конструктора «Срезы»: доступные метрики и измерения."""
    from app.config import settings
    from app.services.clickhouse_sync import SLICE_DIMENSIONS, SLICE_METRICS, last_sync_age_minutes

    if not settings.clickhouse_enabled:
        return {"available": False, "reason": "Слой ClickHouse выключен"}
    return {
        "available": True,
        "sync_age_minutes": await last_sync_age_minutes(),
        "metrics": {m: table for m, (table, _) in SLICE_METRICS.items()},
        "dimensions": {t: list(d.keys()) for t, d in SLICE_DIMENSIONS.items()},
    }


@router.get("/slices")
async def slices_query(
    metric: str,
    dims: str = Query("", description="Измерения через запятую (максимум 2)"),
    days: int = Query(30, ge=1, le=365),
    _admin: User = Depends(require_admin),
):
    """Произвольный срез по OLAP-слою: метрика × до двух измерений × период.

    Только ClickHouse, без Postgres-синка на запросе. Таймаут и 503 —
    витрина сайта не участвует.
    """
    from app.config import settings
    from app.services.clickhouse_sync import run_slice

    if not settings.clickhouse_enabled:
        raise HTTPException(status_code=503, detail="Слой ClickHouse выключен")
    try:
        return await run_slice(
            metric, [d.strip() for d in dims.split(",") if d.strip()], days
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 — CH недоступен: мягкая деградация
        logger.warning("Slice query failed: %s", exc)
        raise HTTPException(
            status_code=503, detail="Слой недоступен, синк догонит после подъёма"
        )

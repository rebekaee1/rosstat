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
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_analytics_db, get_db
from app.models import EmailCredential, OAuthIdentity, User
from app.security.auth import current_session
from app.services.api_i18n import api_detail

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/bi", tags=["admin-bi"])

_BI_CACHE_TTL = 15 * 60  # владелец: «подтягивала данные раз в 15 минут»
# Один расчёт на воркер: два параллельных cache-miss удваивали RAM и пул.
_DASHBOARD_LOCK = asyncio.Lock()


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
    fresh: bool = Query(False, description="Принудительный пересчёт мимо кэша"),
    _admin: User = Depends(require_admin),
):
    from app.core.cache import cache_get, cache_set
    from app.services.admin_bi import build_bi_dashboard
    from app.services.analytics_period import as_period, resolve_period

    if days is not None and period == "30d" and not date_from:
        p = as_period(days)  # легаси-вызовы ?days=N продолжают работать
    else:
        p = resolve_period(period, date_from, date_to)

    # Окно, включающее сегодня, растёт в реальном времени — кэш короче.
    ttl = 5 * 60 if p.end_date >= resolve_period("today").start_date else _BI_CACHE_TTL
    cache_key = f"fe:admin:bi:dashboard:{p.preset}:{p.start_date}:{p.end_date}"
    if not fresh:
        cached = await cache_get(cache_key)
        if cached:
            return cached
    async with _DASHBOARD_LOCK:
        if not fresh:
            cached = await cache_get(cache_key)
            if cached:
                return cached
        try:
            async with _override_aware_session(request, get_analytics_db) as db:
                data = await build_bi_dashboard(db, p)
        except HTTPException:
            raise
        except Exception:
            logger.exception("BI dashboard build failed")
            raise HTTPException(
                status_code=503, detail="Витрины временно недоступны"
            ) from None
        await cache_set(cache_key, data, ttl=ttl)
        return data


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

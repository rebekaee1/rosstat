"""Админ-BI: /api/v1/admin/bi/* (директива владельца 2026-07-05).

Доступ — только пользователям из settings.admin_emails (вход обычной
сессией /auth/login; email сверяется по способам входа). Обычные
пользователи и гости получают 404 (не раскрываем существование раздела).

Кэш дашборда — Redis 15 минут: фронт поллит каждые 15 минут и получает
свежий срез без пересчёта витрин на каждый запрос.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import EmailCredential, OAuthIdentity, User
from app.security.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/bi", tags=["admin-bi"])

_BI_CACHE_TTL = 15 * 60  # владелец: «подтягивала данные раз в 15 минут»


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


async def require_admin(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> User:
    if not await user_is_admin(db, user):
        # 404, а не 403: раздел невидим для обычных пользователей.
        raise HTTPException(status_code=404, detail="Not found")
    return user


@router.get("/dashboard")
async def bi_dashboard(
    days: int = Query(30, ge=1, le=365),
    fresh: bool = Query(False, description="Принудительный пересчёт мимо кэша"),
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.core.cache import cache_get, cache_set
    from app.services.admin_bi import build_bi_dashboard

    cache_key = f"fe:admin:bi:dashboard:{days}"
    if not fresh:
        cached = await cache_get(cache_key)
        if cached:
            return cached
    data = await build_bi_dashboard(db, days)
    await cache_set(cache_key, data, ttl=_BI_CACHE_TTL)
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
    Белый список измерений в clickhouse_sync — произвольный SQL исключён."""
    from app.config import settings
    from app.services.clickhouse_sync import run_slice

    if not settings.clickhouse_enabled:
        raise HTTPException(status_code=503, detail="Слой ClickHouse выключен")
    try:
        return await run_slice(metric, [d.strip() for d in dims.split(",") if d.strip()], days)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 — CH недоступен: мягкая деградация
        logger.warning("Slice query failed: %s", exc)
        raise HTTPException(status_code=503, detail="Слой недоступен, синк догонит после подъёма")

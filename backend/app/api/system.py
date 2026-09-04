import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select, func, desc, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis, get_state_redis
from app.database import get_db
from app.models import Indicator, IndicatorData, FetchLog, Forecast
from app.schemas import SystemStatus
from app.config import settings

router = APIRouter(tags=["system"])

_START_TIME = time.time()

# Возраст последнего успешного ETL, после которого readiness помечает
# деградацию (не роняя 503: рестарт контейнера мёртвый источник не чинит).
_ETL_FRESH_HOURS = 36

# Н-25: возраст heartbeat pg-backup (cron 04:00 + запас). Ключ пишет
# scripts/pg-backup.sh; отсутствие ключа (dev, свежий Redis) — не деградация,
# только просроченный существующий heartbeat.
_PG_BACKUP_FRESH_HOURS = 30
_PG_BACKUP_HEARTBEAT_KEY = "fe:ops:pg_backup_last_ok"


@router.get("/health")
@router.get("/health/live")
async def health():
    """Liveness: процесс жив и отвечает. Ничего внешнего не проверяет."""
    return {"status": "ok"}


@router.post("/scrape-challenge")
async def scrape_challenge(request: Request):
    """JS-ворота: кука fe_bind только после проверки ядер/WebGL."""
    from app.main import pick_client_ip
    from app.services.scrape_guard import (
        attach_bind_cookie,
        automation_reason,
        is_search_bot_ua,
    )

    if not settings.scrape_challenge_enabled:
        return Response(status_code=204)
    ua = request.headers.get("user-agent")
    if is_search_bot_ua(ua):
        return Response(status_code=204)
    ip = pick_client_ip(
        request.headers.get("x-forwarded-for", ""),
        request.client.host if request.client else "",
    )
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            payload = {}
    except Exception:  # noqa: BLE001
        payload = {}
    if automation_reason(payload, ua):
        return Response(
            status_code=403,
            content="Forbidden",
            media_type="text/plain",
            headers={"X-Robots-Tag": "noindex"},
        )
    resp = Response(status_code=204)
    attach_bind_cookie(resp, ip)
    return resp


@router.get("/health/ready")
async def health_ready(response: Response, db: AsyncSession = Depends(get_db)):
    """Readiness (Н-1): БД, оба Redis, планировщик, свежесть ETL.

    503 — только при отказе жёстких зависимостей (БД / Redis / планировщик):
    их рестарт или алерт чинит. Устаревший ETL — мягкая деградация
    (`degraded: true`): источник может быть мёртв неделями, рестартовать
    backend бессмысленно; за алерт отвечает staleness-job (Н-3).
    """
    checks: dict[str, str] = {}
    hard_ok = True

    try:
        await db.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception:
        checks["db"] = "fail"
        hard_ok = False

    try:
        await (await get_redis()).ping()
        checks["cache_redis"] = "ok"
    except Exception:
        checks["cache_redis"] = "fail"
        hard_ok = False

    # state-Redis (DB 1): сессии/lockout/квоты (Н-12) — его отказ ломает auth.
    try:
        await (await get_state_redis()).ping()
        checks["state_redis"] = "ok"
    except Exception:
        checks["state_redis"] = "fail"
        hard_ok = False

    if settings.scheduler_enabled:
        from app.main import scheduler  # noqa: PLC0415 — против циклического импорта
        checks["scheduler"] = "ok" if scheduler.running else "fail"
        if not scheduler.running:
            hard_ok = False

    degraded = False
    if checks["db"] == "ok":
        try:
            last_ok = await db.scalar(
                select(func.max(FetchLog.completed_at))
                .where(FetchLog.status.in_(("success", "no_new_data")))
            )
            if last_ok is not None:
                age_h = (
                    datetime.now(timezone.utc).replace(tzinfo=None) - last_ok
                ).total_seconds() / 3600
                checks["etl_last_ok_age_hours"] = f"{age_h:.1f}"
                if age_h > _ETL_FRESH_HOURS:
                    degraded = True
            else:
                checks["etl_last_ok_age_hours"] = "never"
        except Exception:
            checks["etl_last_ok_age_hours"] = "unknown"

    # Н-25: heartbeat pg-backup (пишется cron-скриптом в cache-Redis).
    if checks["cache_redis"] == "ok":
        try:
            raw = await (await get_redis()).get(_PG_BACKUP_HEARTBEAT_KEY)
            if raw is not None:
                backup_age_h = (time.time() - float(raw)) / 3600
                checks["pg_backup_age_hours"] = f"{backup_age_h:.1f}"
                if backup_age_h > _PG_BACKUP_FRESH_HOURS:
                    degraded = True
            else:
                checks["pg_backup_age_hours"] = "never"
        except Exception:
            checks["pg_backup_age_hours"] = "unknown"

    if not hard_ok:
        response.status_code = 503
    return {
        "status": "ok" if hard_ok and not degraded else ("fail" if not hard_ok else "degraded"),
        "degraded": degraded,
        "checks": checks,
    }


def _check_metrics_token(token: str = Query("", alias="token")):
    if not settings.metrics_token or token != settings.metrics_token:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/metrics", include_in_schema=False)
async def prometheus_metrics(db: AsyncSession = Depends(get_db), _=Depends(_check_metrics_token)):
    """Prometheus-compatible metrics endpoint."""
    ind_count = (await db.execute(select(func.count(Indicator.id)))).scalar() or 0
    active_count = (await db.execute(
        select(func.count(Indicator.id)).where(Indicator.is_active.is_(True))
    )).scalar() or 0
    data_count = (await db.execute(select(func.count(IndicatorData.id)))).scalar() or 0

    fetch_success = (await db.execute(
        select(func.count(FetchLog.id)).where(FetchLog.status == "success")
    )).scalar() or 0
    fetch_failed = (await db.execute(
        select(func.count(FetchLog.id)).where(FetchLog.status == "failed")
    )).scalar() or 0

    uptime = time.time() - _START_TIME

    lines = [
        "# HELP fe_indicators_total Total number of indicators",
        "# TYPE fe_indicators_total gauge",
        f"fe_indicators_total {ind_count}",
        "# HELP fe_indicators_active Active indicators",
        "# TYPE fe_indicators_active gauge",
        f"fe_indicators_active {active_count}",
        "# HELP fe_data_points_total Total data points stored",
        "# TYPE fe_data_points_total gauge",
        f"fe_data_points_total {data_count}",
        "# HELP fe_etl_success_total Successful ETL runs",
        "# TYPE fe_etl_success_total counter",
        f"fe_etl_success_total {fetch_success}",
        "# HELP fe_etl_failed_total Failed ETL runs",
        "# TYPE fe_etl_failed_total counter",
        f"fe_etl_failed_total {fetch_failed}",
        "# HELP fe_uptime_seconds Backend uptime in seconds",
        "# TYPE fe_uptime_seconds gauge",
        f"fe_uptime_seconds {uptime:.0f}",
    ]

    # Н-13: серверный error-rate по классам статусов (in-process, с рестарта).
    from app.main import HttpStatusCounterMiddleware  # noqa: PLC0415 — против цикла
    lines += [
        "# HELP fe_http_responses_total HTTP responses by status class",
        "# TYPE fe_http_responses_total counter",
    ]
    lines += [
        f'fe_http_responses_total{{class="{cls}"}} {n}'
        for cls, n in HttpStatusCounterMiddleware.counters.items()
    ]

    # Н-17/Н-18: деградация Redis — fail-open счётчики кэша и rate-лимитера.
    from app.core.cache import failure_counters
    from app.main import RateLimitMiddleware
    lines += [
        "# HELP fe_cache_failures_total Redis cache fail-open operations",
        "# TYPE fe_cache_failures_total counter",
    ]
    lines += [
        f'fe_cache_failures_total{{op="{op}"}} {n}'
        for op, n in failure_counters.items()
    ]
    lines += [
        "# HELP fe_rate_limit_fail_open_total Requests allowed without rate limit (Redis down)",
        "# TYPE fe_rate_limit_fail_open_total counter",
        f"fe_rate_limit_fail_open_total {RateLimitMiddleware.fail_open_count}",
    ]

    # Н-29: свежесть GeoIP-базы (аудитория без гео при протухшем файле).
    from app.services.geoip import db_age_days
    age = db_age_days()
    lines += [
        "# HELP fe_geoip_db_age_days GeoIP database file age in days (-1 = missing)",
        "# TYPE fe_geoip_db_age_days gauge",
        f"fe_geoip_db_age_days {age if age is not None else -1:.1f}",
    ]

    from app.database import pool_stats
    from app.services.process_metrics import cgroup_memory, process_rss_bytes

    pub = pool_stats("public")
    an = pool_stats("analytics")
    rss = process_rss_bytes()
    cgroup_usage, cgroup_limit = cgroup_memory()
    lines += [
        "# HELP fe_db_pool_checked_out SQLAlchemy connections checked out",
        "# TYPE fe_db_pool_checked_out gauge",
        f'fe_db_pool_checked_out{{pool="public"}} {pub["checkedout"]}',
        f'fe_db_pool_checked_out{{pool="analytics"}} {an["checkedout"]}',
        "# HELP fe_db_pool_overflow SQLAlchemy overflow connections",
        "# TYPE fe_db_pool_overflow gauge",
        f'fe_db_pool_overflow{{pool="public"}} {pub["overflow"]}',
        f'fe_db_pool_overflow{{pool="analytics"}} {an["overflow"]}',
        "# HELP fe_process_rss_bytes Backend process RSS",
        "# TYPE fe_process_rss_bytes gauge",
        f"fe_process_rss_bytes {rss}",
        "# HELP fe_cgroup_memory_bytes Cgroup memory usage and limit",
        "# TYPE fe_cgroup_memory_bytes gauge",
        f'fe_cgroup_memory_bytes{{kind="usage"}} {cgroup_usage}',
        f'fe_cgroup_memory_bytes{{kind="limit"}} {cgroup_limit}',
    ]
    return Response(content="\n".join(lines) + "\n", media_type="text/plain")


@router.get("/system/status", response_model=SystemStatus)
async def system_status(db: AsyncSession = Depends(get_db), _=Depends(_check_metrics_token)):
    ind_count = await db.execute(select(func.count(Indicator.id)))
    data_count = await db.execute(select(func.count(IndicatorData.id)))

    last_fetch_q = await db.execute(
        select(FetchLog).order_by(desc(FetchLog.started_at)).limit(1)
    )
    last_fetch = last_fetch_q.scalar_one_or_none()

    last_forecast_q = await db.execute(
        select(Forecast).where(Forecast.is_current.is_(True)).order_by(desc(Forecast.created_at)).limit(1)
    )
    last_forecast = last_forecast_q.scalar_one_or_none()

    return SystemStatus(
        status="ok",
        indicators_count=ind_count.scalar() or 0,
        total_data_points=data_count.scalar() or 0,
        last_fetch={
            "status": last_fetch.status,
            "records_added": last_fetch.records_added,
            "started_at": str(last_fetch.started_at),
            "source_url": last_fetch.source_url,
        } if last_fetch else None,
        last_forecast={
            "model": last_forecast.model_name,
            "aic": float(last_forecast.aic) if last_forecast.aic is not None else None,
            "created_at": str(last_forecast.created_at),
        } if last_forecast else None,
    )

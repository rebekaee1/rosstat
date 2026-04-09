import time

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Indicator, IndicatorData, FetchLog, Forecast
from app.schemas import SystemStatus

router = APIRouter(tags=["system"])

_START_TIME = time.time()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/metrics", include_in_schema=False)
async def prometheus_metrics(db: AsyncSession = Depends(get_db)):
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
    return Response(content="\n".join(lines) + "\n", media_type="text/plain")


@router.get("/system/status", response_model=SystemStatus)
async def system_status(db: AsyncSession = Depends(get_db)):
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
            "aic": float(last_forecast.aic) if last_forecast.aic else None,
            "created_at": str(last_forecast.created_at),
        } if last_forecast else None,
    )

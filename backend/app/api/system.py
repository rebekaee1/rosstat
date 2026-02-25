from fastapi import APIRouter, Depends
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Indicator, IndicatorData, FetchLog, Forecast
from app.schemas import SystemStatus

router = APIRouter(tags=["system"])


@router.get("/health")
async def health():
    return {"status": "ok"}


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

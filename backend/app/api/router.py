from fastapi import APIRouter

from app.api.indicators import router as indicators_router
from app.api.forecasts import router as forecasts_router
from app.api.system import router as system_router
from app.api.calendar import router as calendar_router
from app.api.embed import router as embed_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(indicators_router)
api_router.include_router(forecasts_router)
api_router.include_router(system_router)
api_router.include_router(calendar_router)
api_router.include_router(embed_router)

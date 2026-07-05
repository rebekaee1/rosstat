from fastapi import APIRouter

from app.api.indicators import router as indicators_router
from app.api.forecasts import router as forecasts_router
from app.api.system import router as system_router
from app.api.calendar import router as calendar_router
from app.api.embed import router as embed_router
from app.api.dashboard import router as dashboard_router
from app.api.demographics import router as demographics_router
from app.api.analytics import router as analytics_router
from app.api.ticker import router as ticker_router
from app.api.auth import router as auth_router
from app.api.oauth import router as oauth_router
from app.api.export import router as export_router
from app.api.regions import router as regions_router
from app.api.admin_bi import router as admin_bi_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(indicators_router)
api_router.include_router(forecasts_router)
api_router.include_router(system_router)
api_router.include_router(calendar_router)
api_router.include_router(embed_router)
api_router.include_router(dashboard_router)
api_router.include_router(demographics_router)
api_router.include_router(analytics_router)
api_router.include_router(ticker_router)
api_router.include_router(auth_router)
api_router.include_router(oauth_router)
api_router.include_router(export_router)
api_router.include_router(regions_router)
api_router.include_router(admin_bi_router)

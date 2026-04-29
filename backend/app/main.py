import json
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.api.router import api_router
from app.config import settings
from app.core.cache import close_redis, get_redis
from app.database import engine

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            log_obj["exc"] = self.formatException(record.exc_info)
        return json.dumps(log_obj, ensure_ascii=False)


_handler = logging.StreamHandler()
_handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[_handler])
logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-based rate limiter with separate limits for main API and embed endpoints."""

    LIMIT = 120
    EMBED_LIMIT = 600
    WINDOW = 60

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        is_embed = request.url.path.startswith("/api/v1/embed/")
        limit = self.EMBED_LIMIT if is_embed else self.LIMIT

        forwarded = request.headers.get("x-forwarded-for", "")
        client_ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
        key = f"rle:{client_ip}" if is_embed else f"rl:{client_ip}"
        try:
            redis = await get_redis()
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, self.WINDOW)
            if count > limit:
                return Response(
                    content=json.dumps({"detail": "Rate limit exceeded"}),
                    status_code=429,
                    media_type="application/json",
                    headers={"Retry-After": str(self.WINDOW)},
                )
        except Exception:
            logger.warning("Rate limit check failed (Redis unavailable), allowing request from %s", client_ip)
        return await call_next(request)

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting %s...", settings.app_name)

    if settings.scheduler_enabled:
        from app.tasks.scheduler import daily_update_job
        scheduler.add_job(
            daily_update_job,
            trigger=CronTrigger(
                hour=settings.scheduler_cron_hour,
                minute=settings.scheduler_cron_minute,
                timezone="Europe/Moscow",
            ),
            id="daily_etl",
            name="Daily ETL (all active indicators: Rosstat, CBR, …)",
            replace_existing=True,
        )
        scheduler.start()
        logger.info(
            "Scheduler started: daily ETL at %02d:%02d MSK (Europe/Moscow), all is_active indicators",
            settings.scheduler_cron_hour,
            settings.scheduler_cron_minute,
        )
        if settings.analytics_scheduler_enabled:
            from app.tasks.analytics_scheduler import analytics_daily_job, analytics_hourly_job
            scheduler.add_job(
                analytics_hourly_job,
                trigger=CronTrigger(minute=15, timezone="Europe/Moscow"),
                id="analytics_hourly",
                name="Forecast Analytics OS hourly reporting sync",
                replace_existing=True,
            )
            scheduler.add_job(
                analytics_daily_job,
                trigger=CronTrigger(
                    hour=settings.analytics_scheduler_cron_hour,
                    minute=settings.analytics_scheduler_cron_minute,
                    timezone="Europe/Moscow",
                ),
                id="analytics_daily",
                name="Forecast Analytics OS daily management snapshot",
                replace_existing=True,
            )
            logger.info(
                "Analytics scheduler enabled: hourly at :15 and daily at %02d:%02d MSK",
                settings.analytics_scheduler_cron_hour,
                settings.analytics_scheduler_cron_minute,
            )

    yield

    # Shutdown
    if scheduler.running:
        scheduler.shutdown(wait=False)
    await engine.dispose()
    await close_redis()
    logger.info("Shutdown complete.")


app = FastAPI(
    title=settings.app_name,
    description="API для экономических индикаторов России",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.debug else None,
    redoc_url="/api/redoc" if settings.debug else None,
    openapi_url="/api/openapi.json" if settings.debug else None,
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://forecasteconomy.com",
        "https://www.forecasteconomy.com",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(api_router)

from app.api.sitemap import router as sitemap_router
app.include_router(sitemap_router)

from app.api.seo_pages import router as seo_pages_router
app.include_router(seo_pages_router)

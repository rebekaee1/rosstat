import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.api.router import api_router
from app.config import settings
from app.core.cache import close_redis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

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
            name="Daily Rosstat ETL",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("Scheduler started (daily at %02d:%02d MSK)",
                     settings.scheduler_cron_hour, settings.scheduler_cron_minute)

    yield

    # Shutdown
    if scheduler.running:
        scheduler.shutdown(wait=False)
    await close_redis()
    logger.info("Shutdown complete.")


app = FastAPI(
    title=settings.app_name,
    description="API для экономических индикаторов России",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

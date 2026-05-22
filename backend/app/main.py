import asyncio
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
from apscheduler.triggers.interval import IntervalTrigger

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


async def _catch_up_empty_indicators() -> None:
    """Подтянуть данные для is_active source-индикаторов с 0 точек.

    Закрывает «New indicator initial ETL trap»: после deploy с новым
    индикатором в seed_data он стоит пустой, пока daily-job не отработает
    (06:00 МСК). Эта функция запускается **один раз при startup** и тригерит
    `run_etl_for_indicator` только для тех, у кого `data_count = 0` и
    `parser_type != 'derived'`. Derived подхватятся cascade'ом после source.

    Чтобы не задержать uvicorn ready на 30-90 секунд (10+ парсеров × 1-5с),
    запускаем как background task. ETL_TIMEOUT_SECONDS защищает от
    зависших источников.
    """
    try:
        from sqlalchemy import select, func
        from app.database import async_session
        from app.models import Indicator, IndicatorData
        from app.tasks.scheduler import run_etl_for_indicator

        async with async_session() as db:
            q = await db.execute(
                select(Indicator.code, Indicator.parser_type)
                .outerjoin(IndicatorData, IndicatorData.indicator_id == Indicator.id)
                .where(Indicator.is_active.is_(True))
                .group_by(Indicator.id)
                .having(func.count(IndicatorData.id) == 0)
            )
            empty = [(code, ptype) for code, ptype in q.all() if ptype != "derived"]

        if not empty:
            logger.info("Startup catch-up: no empty source indicators, all good")
            return

        logger.info(
            "Startup catch-up: %d source indicator(s) with 0 points, triggering ETL: %s",
            len(empty), ", ".join(c for c, _ in empty),
        )
        for code, _ in empty:
            try:
                updated = await run_etl_for_indicator(code)
                logger.info("Startup catch-up: %s — updated=%s", code, updated)
            except Exception as e:
                logger.warning("Startup catch-up: %s failed: %s", code, e)
    except Exception as e:
        logger.warning("Startup catch-up aborted: %s", e)


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
        from app.services.calendar_seed import seed_calendar

        async def _calendar_refresh_job():
            try:
                inserted = await seed_calendar(months_ahead=12)
                logger.info("Calendar refresh job: %d new events", inserted)
            except Exception:
                logger.exception("Calendar refresh job failed")

        scheduler.add_job(
            _calendar_refresh_job,
            trigger=CronTrigger(
                hour=3, minute=0, timezone="Europe/Moscow",
            ),
            id="calendar_refresh",
            name="Daily official calendar refresh (rolling 12-month window)",
            replace_existing=True,
        )

        from app.tasks.scheduler import late_minfin_etl_job

        scheduler.add_job(
            late_minfin_etl_job,
            trigger=CronTrigger(
                hour=15, minute=0, timezone="Europe/Moscow",
            ),
            id="late_minfin_etl",
            name="Late Minfin ETL pass (catches in-place CSV content updates)",
            replace_existing=True,
        )
        from app.tasks.ticker_worker import ticker_pull_job

        scheduler.add_job(
            ticker_pull_job,
            trigger=IntervalTrigger(seconds=settings.ticker_pull_interval_seconds),
            id="ticker_live_pull",
            name="Live ticker pull (MOEX ISS + Binance) → Redis",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )

        scheduler.start()
        logger.info(
            "Scheduler started: daily ETL at %02d:%02d MSK (Europe/Moscow), all is_active indicators; "
            "official calendar refresh at 03:00 MSK; late Minfin pass at 15:00 MSK; "
            "live ticker every %ds",
            settings.scheduler_cron_hour,
            settings.scheduler_cron_minute,
            settings.ticker_pull_interval_seconds,
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

        # «New indicator initial ETL trap» — закрытие. После seed_data
        # любые новые source-индикаторы могут стоять с 0 точек, пока
        # daily-job не отработает (06:00 МСК). Триггерим catch-up для них
        # сразу при startup — в фоновой задаче, чтобы не блокировать
        # uvicorn ready. См. CONTEXT.md::Operational invariants.
        asyncio.create_task(_catch_up_empty_indicators())

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

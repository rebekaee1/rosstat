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

    # Инвариант ADR-0007: fake OAuth-провайдер допустим только не в проде.
    # «Прод» = debug выключен. В тестах/деве fake включают вместе с debug.
    if settings.auth_fake_provider_enabled and not settings.debug:
        raise RuntimeError(
            "auth_fake_provider_enabled must be false in production (RUSTATS_DEBUG=false)"
        )

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
        # Вечерний полный прогон — данные, опубликованные источниками в течение
        # дня (после утреннего 06:00). Тот же job (ETL + IndexNow-пинг по
        # изменившимся карточкам), идемпотентный upsert — повторный прогон без
        # изменений не трогает БД.
        scheduler.add_job(
            daily_update_job,
            trigger=CronTrigger(
                hour=settings.scheduler_evening_hour,
                minute=settings.scheduler_evening_minute,
                timezone="Europe/Moscow",
            ),
            id="evening_etl",
            name="Evening ETL pass (intraday source updates)",
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
            "Scheduler started: daily ETL at %02d:%02d and %02d:%02d MSK (Europe/Moscow), all is_active indicators; "
            "official calendar refresh at 03:00 MSK; late Minfin pass at 15:00 MSK; "
            "live ticker every %ds",
            settings.scheduler_cron_hour,
            settings.scheduler_cron_minute,
            settings.scheduler_evening_hour,
            settings.scheduler_evening_minute,
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

        # Слой привлечения (фразы/источники/рефереры/повизитное сырьё Метрики).
        # Привязан к analytics_enabled + read-token, НЕ к analytics_scheduler_enabled:
        # это часть накопительного DS-датасета, а не экспериментальный OS-синк.
        if settings.analytics_enabled and settings.yandex_metrika_read_token:
            from app.tasks.analytics_scheduler import acquisition_daily_job
            # Три прогона в день: утренний до Пульса + дневной и вечерний
            # (подстраховка от сбоя и дозапись позднего лога). Синк идемпотентен
            # по (counter_id, visit_id); Logs API отдаёт данные только до вчера,
            # «сегодня» в BI закрывает live-слой behavior_events.
            scheduler.add_job(
                acquisition_daily_job,
                trigger=CronTrigger(hour="8,14,20", minute=20,
                                    timezone="Europe/Moscow"),
                id="acquisition_daily",
                name="Metrika acquisition sync (phrases/sources/visits log)",
                replace_existing=True,
            )
            logger.info("Acquisition sync enabled: 08:20/14:20/20:20 MSK")

        # Автоподача переобхода Яндекс.Вебмастера: каждое утро выбираем
        # дневную квоту (~150 URL) приоритетными страницами из единого
        # реестра site_urls (регионы, рейтинги, годовые landing'и).
        if settings.webmaster_recrawl_enabled and settings.yandex_webmaster_token:
            from app.services.webmaster_recrawl import recrawl_daily_job
            scheduler.add_job(
                recrawl_daily_job,
                trigger=CronTrigger(hour=9, minute=10, timezone="Europe/Moscow"),
                id="webmaster_recrawl",
                name="Yandex.Webmaster recrawl queue (daily quota drain)",
                replace_existing=True,
            )
            logger.info("Webmaster recrawl auto-submit enabled: daily at 09:10 MSK")

        if settings.telegram_digest_enabled:
            from app.tasks.analytics_scheduler import telegram_daily_digest_job
            scheduler.add_job(
                telegram_daily_digest_job,
                trigger=CronTrigger(
                    hour=settings.telegram_digest_cron_hour,
                    minute=settings.telegram_digest_cron_minute,
                    timezone="Europe/Moscow",
                ),
                id="telegram_daily_digest",
                name="Telegram daily digest (users + Metrika goals)",
                replace_existing=True,
            )
            logger.info(
                "Telegram digest enabled: daily at %02d:%02d MSK",
                settings.telegram_digest_cron_hour,
                settings.telegram_digest_cron_minute,
            )

        if settings.pulse_enabled:
            from app.services.pulse_report import pulse_report_job, pulse_snapshot_job
            scheduler.add_job(
                pulse_snapshot_job,
                trigger=CronTrigger(hour=23, minute=57, timezone="Europe/Moscow"),
                id="pulse_snapshot",
                name="Pulse daily snapshot (users/events/etl/data)",
                replace_existing=True,
            )
            scheduler.add_job(
                pulse_report_job,
                trigger=CronTrigger(
                    hour=settings.pulse_report_cron_hour,
                    minute=settings.pulse_report_cron_minute,
                    timezone="Europe/Moscow",
                ),
                id="pulse_report",
                name="Pulse LLM report to owner (OpenRouter → Telegram)",
                replace_existing=True,
            )
            logger.info(
                "Pulse enabled: snapshot 23:57, report %02d:%02d MSK",
                settings.pulse_report_cron_hour,
                settings.pulse_report_cron_minute,
            )

        if settings.behavior_events_enabled:
            from app.tasks.analytics_scheduler import behavior_retention_job
            scheduler.add_job(
                behavior_retention_job,
                trigger=CronTrigger(hour=4, minute=30, timezone="Europe/Moscow"),
                id="behavior_retention",
                name="Behavior raw stream retention cleanup",
                replace_existing=True,
            )

        # Вычислительный фундамент аналитики (ADR-0010): каждые 15 минут —
        # серверная сессионизация (30-мин правило Метрики) + инкремент
        # rollup'ов последних 2 суток + пороговые алерты-аномалии; раз в сутки
        # ночью — пересчёт хвоста истории.
        from app.tasks.analytics_rollups import rollups_15min_job, rollups_daily_job
        scheduler.add_job(
            rollups_15min_job,
            trigger=IntervalTrigger(minutes=15),
            id="analytics_rollups_15min",
            name="Analytics: sessionize + rollups (last 2 days) + anomaly alerts",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        scheduler.add_job(
            rollups_daily_job,
            trigger=CronTrigger(hour=4, minute=50, timezone="Europe/Moscow"),
            id="analytics_rollups_daily",
            name="Analytics: full rollup history recompute + goals dict sync",
            replace_existing=True,
        )

        # Гео-база DB-IP: фоновая загрузка при старте (если файла нет) и
        # ежемесячное обновление — сайт стартует и без неё (гео = NULL).
        if settings.geoip_auto_download:
            from app.services.geoip import download_geoip_db
            asyncio.create_task(download_geoip_db())
            scheduler.add_job(
                download_geoip_db,
                trigger=CronTrigger(day=3, hour=5, minute=0, timezone="Europe/Moscow"),
                id="geoip_monthly_update",
                name="GeoIP DB-IP Lite monthly refresh",
                replace_existing=True,
            )

        # OLAP-слой ClickHouse: производная копия Postgres, курсорный синк
        # каждые 15 минут. Деградация мягкая: CH упал → сайт не замечает.
        if settings.clickhouse_enabled:
            from app.services.clickhouse_sync import clickhouse_sync_job
            scheduler.add_job(
                clickhouse_sync_job,
                trigger=IntervalTrigger(minutes=15),
                id="clickhouse_sync",
                name="ClickHouse OLAP sync (derived copy of PG, cursor batches)",
                replace_existing=True,
                coalesce=True,
                max_instances=1,
            )
            logger.info("ClickHouse sync enabled: every 15 min")

        if settings.telegram_poller_enabled:
            from app.services.telegram_bot import telegram_poll_job
            scheduler.add_job(
                telegram_poll_job,
                trigger=IntervalTrigger(seconds=30),
                id="telegram_poll",
                name="Telegram bot getUpdates poller (owner buttons)",
                replace_existing=True,
                coalesce=True,
                max_instances=1,
            )
            logger.info("Telegram poller enabled: every 30s")

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

from app.api.oauth import compat_router as oauth_compat_router
app.include_router(oauth_compat_router)

from app.api.sitemap import router as sitemap_router
app.include_router(sitemap_router)

from app.api.seo_pages import router as seo_pages_router
app.include_router(seo_pages_router)

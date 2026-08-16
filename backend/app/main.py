import asyncio
import ipaddress
import json
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_MISSED
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


# Приватные/loopback-сети — это наши прокси-хопы (Caddy на хосте, nginx в
# docker-сети), а не клиенты. Публичные порты наружу не смотрят (всё на
# 127.0.0.1 в compose), внешний путь один: Caddy:443 → nginx → backend.
_TRUSTED_PROXY_NETS = tuple(
    ipaddress.ip_network(n)
    for n in ("127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "::1/128", "fc00::/7")
)


def pick_client_ip(forwarded_for: str, fallback: str) -> str:
    """Реальный клиентский IP из X-Forwarded-For.

    Заголовок append-only (nginx делает $proxy_add_x_forwarded_for), поэтому
    ЛЕВЫЕ элементы может подделать клиент. Идём справа налево, пропуская наши
    доверенные прокси-хопы; первый недоверенный ВАЛИДНЫЙ адрес — клиент.
    Брать первый слева (как раньше) нельзя: ротация фейковых XFF давала обход
    rate-limit. Невалидные токены не могут стать ключом лимита — иначе ротация
    мусорных строк открывала бы тот же обход.
    """
    chain = []
    for part in forwarded_for.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            chain.append((part, ipaddress.ip_address(part)))
        except ValueError:
            continue  # мусор — не хоп и не клиент
    for raw, addr in reversed(chain):
        if not any(addr in net for net in _TRUSTED_PROXY_NETS):
            return raw
    # Вся цепочка из приватных адресов (dev за локальным прокси) — берём
    # ближайший к клиенту, иначе fallback на peer-адрес сокета.
    return chain[0][0] if chain else fallback


# Атомарный INCR+EXPIRE: между incr и expire нет окна, в котором сбой оставил
# бы ключ без TTL (= вечный 429 для IP). Ветка TTL<0 лечит legacy-ключи,
# созданные старым неатомарным кодом.
_RATE_LIMIT_LUA = """
local c = redis.call('INCR', KEYS[1])
if c == 1 or redis.call('TTL', KEYS[1]) < 0 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return c
"""


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-based rate limiter with separate limits for main API and embed endpoints."""

    LIMIT = 120
    EMBED_LIMIT = 600
    WINDOW = 60

    # Н-18: fail-open осознан (доступность > лимит), но при лежащем Redis
    # защита исчезает у ВСЕХ запросов — это должно алертиться, не только
    # per-request warning. Порог: >= 30 fail-open за минуту.
    fail_open_count = 0
    _fail_open_recent: list[float] = []
    _fail_open_last_alert: float = 0.0
    FAIL_OPEN_THRESHOLD = 30
    FAIL_OPEN_WINDOW = 60
    FAIL_OPEN_COOLDOWN = 1800

    @classmethod
    def _note_fail_open(cls, client_ip: str) -> None:
        import time as _time

        cls.fail_open_count += 1
        now = _time.monotonic()
        cls._fail_open_recent = [t for t in cls._fail_open_recent
                                 if now - t < cls.FAIL_OPEN_WINDOW]
        cls._fail_open_recent.append(now)
        logger.warning(
            "Rate limit check failed (Redis unavailable), allowing request from %s", client_ip)
        if (len(cls._fail_open_recent) >= cls.FAIL_OPEN_THRESHOLD
                and now - cls._fail_open_last_alert > cls.FAIL_OPEN_COOLDOWN):
            cls._fail_open_last_alert = now
            try:
                from app.services.alerting import send_telegram
                asyncio.get_running_loop().create_task(send_telegram(
                    "🔴 <b>Rate limiter fail-open</b>\n"
                    f"{len(cls._fail_open_recent)} запросов прошли без лимита за "
                    f"{cls.FAIL_OPEN_WINDOW}с — Redis недоступен, защита от флуда отключена.",
                    kind="rate_limit_alert",
                ))
            except Exception:
                logger.exception("Rate limiter fail-open alert failed")

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        is_embed = request.url.path.startswith("/api/v1/embed/")
        limit = self.EMBED_LIMIT if is_embed else self.LIMIT

        client_ip = pick_client_ip(
            request.headers.get("x-forwarded-for", ""),
            request.client.host if request.client else "unknown",
        )
        key = f"rle:{client_ip}" if is_embed else f"rl:{client_ip}"
        try:
            redis = await get_redis()
            count = await redis.eval(_RATE_LIMIT_LUA, 1, key, self.WINDOW)
            if count > limit:
                return Response(
                    content=json.dumps({"detail": "Rate limit exceeded"}),
                    status_code=429,
                    media_type="application/json",
                    headers={"Retry-After": str(self.WINDOW)},
                )
        except Exception:
            self._note_fail_open(client_ip)
        return await call_next(request)

class HttpStatusCounterMiddleware(BaseHTTPMiddleware):
    """Н-13: серверный error-rate. Считаем ответы по классам статусов
    (in-process, отдаются в /metrics) и алертим на всплеск 5xx.

    Спайк-детектор — скользящее окно: >= SPIKE_THRESHOLD ответов 5xx за
    SPIKE_WINDOW секунд → один Telegram-алерт, дальше молчим COOLDOWN.
    """

    SPIKE_THRESHOLD = 10
    SPIKE_WINDOW = 300
    COOLDOWN = 900

    counters: dict[str, int] = {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0}
    _recent_5xx: list[float] = []
    _last_alert_ts: float = 0.0

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception:
            self._record(500, request.url.path)
            raise
        self._record(status, request.url.path)
        return response

    @classmethod
    def _record(cls, status: int, path: str) -> None:
        bucket = f"{status // 100}xx"
        if bucket in cls.counters:
            cls.counters[bucket] += 1
        if status >= 500:
            now = time.time()
            cls._recent_5xx = [t for t in cls._recent_5xx if now - t < cls.SPIKE_WINDOW]
            cls._recent_5xx.append(now)
            if (len(cls._recent_5xx) >= cls.SPIKE_THRESHOLD
                    and now - cls._last_alert_ts > cls.COOLDOWN):
                cls._last_alert_ts = now
                try:
                    from app.services.alerting import send_telegram
                    asyncio.get_running_loop().create_task(send_telegram(
                        f"🔴 <b>5xx spike</b>\n{len(cls._recent_5xx)} ответов 5xx "
                        f"за {cls.SPIKE_WINDOW // 60} мин (последний путь: {path[:120]})",
                        kind="http_5xx_spike",
                    ))
                except Exception:
                    logger.exception("5xx spike alert failed")


# О-14: глобальные дефолты — пропущенный запуск схлопывается в один (coalesce),
# job не дублируется при overlap, misfire до часа исполняется, старше — skip.
scheduler = AsyncIOScheduler(
    job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 3600}
)


def locked_job(fn, job_id: str, ttl_seconds: int):
    """О-13: распределённый лок на исполнение job (state-Redis SET NX EX).

    Планировщик in-process: два инстанса backend (UVICORN_WORKERS=2 или
    overlap при рестарте) исполнили бы ETL/derived/retrain дважды. Лок с TTL
    гарантирует одного исполнителя; при недоступном Redis — fail-open
    (single-instance допущение важнее, чем пропуск прогона).
    """
    import uuid

    _RELEASE_LUA = (
        "if redis.call('GET', KEYS[1]) == ARGV[1] then "
        "return redis.call('DEL', KEYS[1]) else return 0 end"
    )

    async def wrapper(*args, **kwargs):
        from app.core.cache import get_state_redis

        key = f"sched:lock:{job_id}"
        token = uuid.uuid4().hex
        redis = None
        try:
            redis = await get_state_redis()
            acquired = await redis.set(key, token, nx=True, ex=ttl_seconds)
            if not acquired:
                logger.info("Job %s: lock held by another instance, skipping", job_id)
                return None
        except Exception:
            logger.warning("Job %s: lock check failed (Redis down), running unlocked", job_id)
            redis = None
        try:
            return await fn(*args, **kwargs)
        finally:
            if redis is not None:
                try:
                    await redis.eval(_RELEASE_LUA, 1, key, token)
                except Exception:
                    pass  # TTL добьёт ключ сам

    wrapper.__name__ = f"locked_{getattr(fn, '__name__', job_id)}"
    return wrapper


def _scheduler_event_listener(event) -> None:
    """Н-2: упавшая/пропущенная job планировщика — алерт, а не только строка в логах."""
    try:
        from html import escape

        from app.services.alerting import send_telegram

        if getattr(event, "exception", None):
            kind = "🔴 <b>Scheduler job failed</b>"
            detail = escape(str(event.exception)[:300])
        else:
            kind = "🟡 <b>Scheduler job missed</b>"
            detail = "misfire (job не запустилась в срок)"
        job = scheduler.get_job(event.job_id)
        next_run = getattr(job, "next_run_time", None)
        msg = (
            f"{kind}\nJob: <code>{escape(str(event.job_id))}</code>\n"
            f"{detail}\nNext run: {next_run or '—'}"
        )
        logger.error("Scheduler event: job=%s exc=%s", event.job_id,
                     getattr(event, "exception", None))
        asyncio.get_running_loop().create_task(send_telegram(msg, kind="scheduler_alert"))
    except Exception:  # алерт не должен ронять loop планировщика
        logger.exception("Scheduler event listener failed")


scheduler.add_listener(_scheduler_event_listener, EVENT_JOB_ERROR | EVENT_JOB_MISSED)


async def _cleanup_stuck_fetch_logs() -> None:
    """О-9: OOM-kill/рестарт посреди ETL оставляет fetch_log в `running` навсегда.

    При старте помечаем зависшие записи (running > 6 часов) как `interrupted` —
    иначе они вечно висят «выполняется» в мониторинге и Пульсе.
    """
    try:
        from datetime import datetime, timedelta, timezone

        from sqlalchemy import update

        from app.database import async_session
        from app.models import FetchLog

        # naive-UTC — как хранятся колонки (Р-16)
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=6)
        async with async_session() as db:
            result = await db.execute(
                update(FetchLog)
                .where(FetchLog.status == "running", FetchLog.started_at < cutoff)
                .values(status="interrupted", error_message="stale running (startup cleanup)")
            )
            await db.commit()
        if result.rowcount:
            logger.warning("Startup cleanup: %d stuck fetch_log rows -> interrupted", result.rowcount)
    except Exception as e:
        logger.warning("Stuck fetch_log cleanup failed: %s", e)


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
        catch_up_failed: list[str] = []
        for code, _ in empty:
            try:
                updated = await run_etl_for_indicator(code)
                logger.info("Startup catch-up: %s — updated=%s", code, updated)
            except Exception as e:
                logger.warning("Startup catch-up: %s failed: %s", code, e)
                catch_up_failed.append(code)
        # Н-9: новый индикатор, который не смог наполниться при старте, —
        # это пустая карточка на проде; молчаливый warning недостаточен.
        if catch_up_failed:
            from html import escape

            from app.services.alerting import send_telegram
            await send_telegram(
                "🔴 <b>Startup catch-up failed</b>\n"
                f"Пустые индикаторы не наполнились: <code>{escape(', '.join(catch_up_failed))}</code>",
                kind="etl_failure",
            )
    except Exception as e:
        logger.warning("Startup catch-up aborted: %s", e)


async def _startup_data_catch_up() -> None:
    """Startup: пустые source-ряды → ETL; затем gap-fill пустых прогнозов.

    Порядок важен: без факта retrain бессмысленен. Forecast gap-fill закрывает
    «включили strategy в seed, забыли ручной retrain» без ручных команд.
    """
    await _catch_up_empty_indicators()
    try:
        from app.tasks.scheduler import _catch_up_empty_forecasts_safe

        await _catch_up_empty_forecasts_safe("startup")
    except Exception as e:
        logger.warning("Startup forecast catch-up aborted: %s", e)


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

    # О-19/Р-10: prod-конфиг с dev-дефолтами — предвестник инцидента (cookie без
    # Secure, http base URL, пароли из .env.example). Пока warn-режим: CRITICAL
    # в лог + Telegram, БЕЗ остановки старта — enforcement после подтверждения
    # владельцем, что прод-.env полон.
    if not settings.debug:
        prod_config_issues: list[str] = []
        if not settings.auth_cookie_secure:
            prod_config_issues.append("auth_cookie_secure=False (session cookie без Secure)")
        if settings.auth_public_base_url.startswith("http://"):
            prod_config_issues.append(f"auth_public_base_url не https: {settings.auth_public_base_url}")
        if "rustats_dev" in settings.database_url:
            prod_config_issues.append("database_url содержит dev-пароль rustats_dev")
        if ":changeme@" in settings.redis_url:
            prod_config_issues.append("redis_url содержит дефолтный пароль changeme")
        if prod_config_issues:
            for issue in prod_config_issues:
                logger.critical("PROD CONFIG: %s", issue)
            try:
                from html import escape

                from app.services.alerting import send_telegram
                asyncio.create_task(send_telegram(
                    "🔴 <b>Небезопасный prod-конфиг</b>\n"
                    + "\n".join(f"— {escape(i)}" for i in prod_config_issues),
                    kind="prod_config_alert",
                ))
            except Exception:
                logger.exception("Prod config alert failed")

    if settings.scheduler_enabled:
        from app.tasks.scheduler import daily_update_job
        # О-13: мутационные джобы (ETL/derived/retrain) — под распределённым
        # локом: overlap инстансов не должен дублировать записи и retrain.
        _locked_daily = locked_job(daily_update_job, "daily_etl", ttl_seconds=3 * 3600)
        scheduler.add_job(
            _locked_daily,
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
            locked_job(daily_update_job, "evening_etl", ttl_seconds=3 * 3600),
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
            locked_job(late_minfin_etl_job, "late_minfin_etl", ttl_seconds=3600),
            trigger=CronTrigger(
                hour=15, minute=0, timezone="Europe/Moscow",
            ),
            id="late_minfin_etl",
            name="Late Minfin ETL pass (catches in-place CSV content updates)",
            replace_existing=True,
        )

        # World Eurostat — отдельный TOC-driven контур, по умолчанию выключен.
        # В shadow режиме журналирует changed-set без записи data points.
        if settings.world_eurostat_ingest_enabled:
            from app.services.world_eurostat_ingest import world_eurostat_ingest_job

            scheduler.add_job(
                locked_job(
                    world_eurostat_ingest_job,
                    "world_eurostat_ingest",
                    ttl_seconds=6 * 3600,
                ),
                trigger=CronTrigger(
                    hour=settings.world_eurostat_ingest_hour,
                    minute=settings.world_eurostat_ingest_minute,
                    timezone="Europe/Moscow",
                ),
                id="world_eurostat_ingest",
                name="World Eurostat TOC-driven ingest",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )

        if settings.world_forecast_enabled:
            from app.services.world_forecast_pipeline import world_forecast_job

            scheduler.add_job(
                locked_job(
                    world_forecast_job,
                    "world_forecast",
                    ttl_seconds=3 * 3600,
                ),
                trigger=CronTrigger(
                    hour=settings.world_forecast_hour,
                    minute=settings.world_forecast_minute,
                    timezone="Europe/Moscow",
                ),
                id="world_forecast",
                name="World quality-gated monthly/quarterly forecasts",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )

        # Н-3: «источник молча умер» (вечный no_new_data) — ежедневная сверка
        # max(data.date) против SLA частоты каждого индикатора, после утреннего ETL.
        from app.tasks.scheduler import staleness_check_job
        scheduler.add_job(
            staleness_check_job,
            trigger=CronTrigger(hour=10, minute=0, timezone="Europe/Moscow"),
            id="staleness_check",
            name="Indicator staleness check (max(data.date) vs frequency SLA)",
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

        # Доход РСЯ (Partner Statistics) → BI «Привлечение». Окно 30 дней,
        # upsert по дню; включается только при наличии partner-токена.
        from app.services.yandex_partner_stats import partner_configured
        if partner_configured():
            from app.tasks.analytics_scheduler import partner_revenue_daily_job
            scheduler.add_job(
                partner_revenue_daily_job,
                trigger=CronTrigger(hour=8, minute=30, timezone="Europe/Moscow"),
                id="partner_revenue_daily",
                name="Yandex.Partner RSYa revenue sync (shows/hits/partner_wo_nds)",
                replace_existing=True,
            )
            logger.info("Partner revenue sync enabled: daily at 08:30 MSK")

        # Запросы Яндекс-поиска (Вебмастер) → BI «Спрос и SEO». Окно 7 дней
        # с учётом лага API 2–3 дня; идемпотентно дозаполняет пропуски.
        if settings.yandex_webmaster_token:
            from app.tasks.analytics_scheduler import webmaster_queries_daily_job
            scheduler.add_job(
                webmaster_queries_daily_job,
                trigger=CronTrigger(hour=8, minute=40, timezone="Europe/Moscow"),
                id="webmaster_queries_daily",
                name="Yandex.Webmaster search queries sync (demand vs coverage)",
                replace_existing=True,
            )
            logger.info("Webmaster queries sync enabled: daily at 08:40 MSK")

        # А-5: еженедельный отчёт индексации — «страницы в поиске» и динамика,
        # компас ступени «10k визитов/день». Понедельник, после утреннего ETL.
        if settings.yandex_webmaster_token:
            from app.services.webmaster_indexing_report import indexing_report_job
            scheduler.add_job(
                indexing_report_job,
                trigger=CronTrigger(day_of_week="mon", hour=9, minute=30,
                                    timezone="Europe/Moscow"),
                id="indexing_report_weekly",
                name="Yandex indexing weekly report (searchable pages + dynamics)",
                replace_existing=True,
            )
            logger.info("Weekly indexing report enabled: Mon 09:30 MSK")

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

        asyncio.create_task(_cleanup_stuck_fetch_logs())

        # «New indicator initial ETL trap» + forecast gap-fill (steps>0 без
        # текущего прогноза). Фоном, чтобы не блокировать uvicorn ready.
        asyncio.create_task(_startup_data_catch_up())

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
app.add_middleware(HttpStatusCounterMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.public_origin,
        f"https://www.{settings.public_host}",
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

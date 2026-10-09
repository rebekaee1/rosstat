"""«Пульс» — дневной снапшот всей активности платформы (П9б, 2026-07-02).

Каждый день собираем в один JSON всё, что произошло: пользователи, входы,
события фронта (просмотры, скачивания, поиск, ошибки), ETL-прогоны, приток
точек данных. Снапшоты живут в state-Redis (`fe:pulse:{date}`, TTL 8 дней —
самоочистка «недельного» окна), компактная память по дням — `fe:pulse:memory:*`
(TTL 30 дней). Память — это однострочные LLM-сводки + ядро чисел: именно её,
а не полные снапшоты, подаём модели за прошлые дни, чтобы не раздувать
контекстное окно.

Потребитель — `pulse_report.py` (LLM-отчёт в Telegram).
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, or_, select

from app.config import settings
from app.core.cache import get_state_redis
from app.database import analytics_session
from app.services.analytics_period import MSK_OFFSET, msk_day_start_utc
from app.services.display import today_msk
from app.services.goal_taxonomy import (
    GROUP_DOWNLOAD,
    GROUP_FRONT_ERROR,
    GROUP_WALL,
    events_in_group,
)
from app.services.identity.consents import newsletter_subscriber_count_query
from app.services.pii_scrub import scrub_text
from app.models import (
    AnalyticsSyncRun,
    AuthAudit,
    BehaviorEvent,
    BehaviorSession,
    EmailCredential,
    FetchLog,
    FrontendEvent,
    IndicatorData,
    MetrikaReportSnapshot,
    MetrikaSearchPhrase,
    OAuthIdentity,
    RawMetrikaVisit,
    User,
    WebmasterSearchQuery,
)

logger = logging.getLogger(__name__)

SNAPSHOT_TTL = 8 * 86400   # полный снапшот — неделя + буфер
MEMORY_TTL = 30 * 86400    # компактная память — месяц

_SNAP_KEY = "fe:pulse:snap:{d}"
_MEM_KEY = "fe:pulse:memory:{d}"

# E4/E5 (круг 11): единые группы событий из goal_taxonomy вместо локальных
# списков с несуществующими именами (`compare_csv_download`, `api_error`).
# `download_limit` — упор в стену регистрации, а не скачивание: считается отдельно.
_DOWNLOAD_EVENTS = events_in_group(GROUP_DOWNLOAD)
_WALL_EVENTS = events_in_group(GROUP_WALL)
_ERROR_EVENTS = events_in_group(GROUP_FRONT_ERROR)

# Статусы FetchLog, означающие ошибку прогона. Источник истины — что реально
# пишут base_parser.py ("failed") и tasks/scheduler.py ("failed"/"timeout").
# Статуса "error" в системе не существует: фильтр по нему делал Пульс слепым
# к ошибкам ETL (владелец видел «0 ошибок» при реальных провалах).
ETL_ERROR_STATUSES = ("failed", "timeout")


def _day_bounds(d: date) -> tuple[datetime, datetime]:
    """Границы МСК-суток `d` в UTC naive (как хранятся `occurred_at`/`created_at`).

    E1 (круг 11): раньше `datetime.combine(d, time.min)` трактовалось как UTC,
    хотя «день» везде в системе — московский (BI, rollup'ы, расписание). Из-за
    этого Пульс терял ~3 часа каждых суток и расходился с BI за «вчера».
    """
    start = msk_day_start_utc(d)
    return start, start + timedelta(days=1)


async def _etl_snapshot(db, start: datetime, end: datetime) -> dict[str, Any]:
    """ETL-срез дня: прогоны по статусам + индикаторы с ошибочными прогонами."""
    etl_rows = (await db.execute(
        select(FetchLog.status, func.count(), func.coalesce(func.sum(FetchLog.records_added), 0))
        .where(FetchLog.started_at >= start, FetchLog.started_at < end)
        .group_by(FetchLog.status)
    )).all()
    failed_codes = (await db.execute(
        select(func.distinct(FetchLog.indicator_id))
        .where(
            FetchLog.started_at >= start,
            FetchLog.started_at < end,
            FetchLog.status.in_(ETL_ERROR_STATUSES),
        )
    )).scalars().all()
    return {
        "by_status": {s: {"runs": n, "records": int(r)} for s, n, r in etl_rows},
        "failed_indicator_ids": [int(i) for i in failed_codes][:20],
    }


async def _acquisition_from_warehouse(db, d: date) -> dict[str, Any]:
    """Привлечение и происхождение данных из хранилища основного счётчика.

    Статусы описывают сохранённые отчёты, а не доступность живого API.
    Отчёт за другой день не подставляется вместо отсутствующих данных.
    """
    def _snapshot_rows(response_json: dict | None) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for row in (response_json or {}).get("data", []):
            dims = row.get("dimensions") or []
            metrics = row.get("metrics") or []
            name = str(dims[0].get("name")) if dims else "?"
            out[name] = {
                "id": dims[0].get("id") if dims else None,
                "visits": int(metrics[0]) if metrics and metrics[0] is not None else None,
                "users": int(metrics[1]) if len(metrics) > 1 and metrics[1] is not None else None,
            }
        return out

    counter_id = settings.analytics_allowed_counter_ids.split(",")[0].strip()
    runs = (await db.execute(
        select(AnalyticsSyncRun)
        .where(AnalyticsSyncRun.source == "yandex_metrika",
               AnalyticsSyncRun.job_type == "daily_acquisition_reports",
               AnalyticsSyncRun.date_from == d, AnalyticsSyncRun.date_to == d)
        .order_by(AnalyticsSyncRun.started_at.desc(), AnalyticsSyncRun.id.desc())
    )).scalars().all()
    run = next((r for r in runs if (r.metadata_json or {}).get("counter_id", counter_id)
                == counter_id), None)
    metadata: dict[str, Any] = {"counter_id": counter_id, "reports": {}, "sync": None}
    if run is not None:
        metadata["sync"] = {
            "status": run.status, "started_at": run.started_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        }
    acq: dict[str, Any] = {"metadata": metadata}
    for report_type in ("traffic_sources", "search_engines", "referrers", "ad_campaigns"):
        row = (await db.execute(
            select(MetrikaReportSnapshot)
            .where(MetrikaReportSnapshot.counter_id == counter_id,
                   MetrikaReportSnapshot.report_type == report_type,
                   MetrikaReportSnapshot.date_from == MetrikaReportSnapshot.date_to,
                   MetrikaReportSnapshot.date_to <= d)
            .order_by(MetrikaReportSnapshot.date_to.desc(),
                      MetrikaReportSnapshot.captured_at.desc(), MetrikaReportSnapshot.id.desc())
            .limit(1)
        )).scalar_one_or_none()
        info: dict[str, Any] = {"status": "missing"}
        if row is not None:
            info.update({
                "date_from": row.date_from.isoformat(), "date_to": row.date_to.isoformat(),
                "captured_at": row.captured_at.isoformat(), "sampled": row.sampled,
                "sample_share": float(row.sample_share) if row.sample_share is not None else None,
                "status": "stale" if row.date_to != d else "available",
            })
            response = row.response_json or {}
            if row.date_to == d:
                if isinstance(response.get("data"), list):
                    acq[report_type] = _snapshot_rows(response)
                    info["total_rows"] = response.get("total_rows")
                    info["returned_rows"] = len(response["data"])
                    info["sampled"] = response.get("sampled", row.sampled)
                else:
                    info["status"] = "invalid"
        if run is not None and run.status == "failed" and info["status"] != "available":
            info["status"] = "failed"
        metadata["reports"][report_type] = info

    phrases = (await db.execute(
        select(MetrikaSearchPhrase.phrase, MetrikaSearchPhrase.search_engine,
               MetrikaSearchPhrase.visits)
        .where(MetrikaSearchPhrase.date == d, MetrikaSearchPhrase.counter_id == counter_id)
        .order_by(MetrikaSearchPhrase.visits.desc()).limit(25)
    )).all()
    if phrases:
        acq["search_phrases_top"] = [
            {"phrase": p, "engine": e, "visits": v} for p, e, v in phrases
        ]

    from app.services.analytics_marts import metrika_visit_not_headless

    # Без headless-роботов: иначе ферма 2026-09 давала LLM «20k прямых визитов».
    human = metrika_visit_not_headless()
    visits_total = await db.scalar(
        select(func.count(RawMetrikaVisit.id)).where(
            RawMetrikaVisit.visit_date == d, RawMetrikaVisit.counter_id == counter_id, human)
    ) or 0
    if visits_total:
        by_source = dict((await db.execute(
            select(RawMetrikaVisit.traffic_source, func.count())
            .where(RawMetrikaVisit.visit_date == d, RawMetrikaVisit.counter_id == counter_id, human)
            .group_by(RawMetrikaVisit.traffic_source)
        )).all())
        acq["raw_visits"] = {"total": visits_total, "by_source": by_source}
    return acq


async def _seo_snapshot(db=None) -> dict[str, Any]:
    """Индексация в Яндексе + спрос без покрытия — ежедневно в снапшот Пульса.

    HTTP к Вебмастеру выполняется без открытой PG-сессии. Число URL —
    из `/sitemap-stats.json` (ночной билд), не полный проход реестра.
    """
    if not settings.yandex_webmaster_token:
        return {"available": False, "reason": "webmaster token not configured"}
    try:
        from app.services.sitemap_static import url_count_from_stats
        from app.services.webmaster_indexing_report import _report_host_ids
        from app.services.yandex_webmaster_client import YandexWebmasterClient

        client = YandexWebmasterClient()
        user = await client.user()
        user_id = user.data["user_id"]

        summary_by_host: dict[str, dict[str, Any]] = {}
        host_ids = _report_host_ids()
        primary = None
        for host_id in host_ids:
            try:
                data = (await client.summary(user_id, host_id)).data
            except Exception:
                logger.warning("Pulse SEO snapshot: summary failed host=%s", host_id, exc_info=True)
                continue
            label = host_id.replace("https:", "").replace(":443", "")
            summary_by_host[label] = {
                "searchable_pages": data.get("searchable_pages_count"),
                "excluded_pages": data.get("excluded_pages_count"),
                "sqi": data.get("sqi"),
                "site_problems": data.get("site_problems") or {},
            }
            if primary is None:
                primary = data
        if primary is None or not summary_by_host:
            return {"available": False, "reason": "summary fetch failed"}
        summary = primary
        searchable = summary.get("searchable_pages_count")
        total_urls = url_count_from_stats()

        exclusion_reasons: list[dict[str, Any]] = []
        try:
            events = (await client.search_events_samples(
                user_id, host_ids[0], limit=100
            )).data
            reasons: dict[str, int] = {}
            for sample in events.get("samples") or []:
                if sample.get("event") != "REMOVED_FROM_SEARCH":
                    continue
                reason = sample.get("excluded_url_status") or "UNKNOWN"
                reasons[reason] = reasons.get(reason, 0) + 1
            exclusion_reasons = [
                {"reason": r, "count": n}
                for r, n in sorted(reasons.items(), key=lambda kv: -kv[1])[:5]
            ]
        except Exception:
            logger.warning("Pulse SEO snapshot: exclusion reasons unavailable", exc_info=True)

        last_date = None
        top_demand: list[dict[str, Any]] = []
        demand_by_host: list[dict[str, Any]] = []
        indexing_daily: dict[str, Any] | None = None
        async with analytics_session() as seo_db:
            last_date = await seo_db.scalar(select(func.max(WebmasterSearchQuery.date)))
            if last_date:
                rows = (await seo_db.execute(
                    select(
                        WebmasterSearchQuery.query,
                        func.sum(WebmasterSearchQuery.impressions),
                        func.sum(WebmasterSearchQuery.clicks),
                        func.avg(WebmasterSearchQuery.position),
                    )
                    .where(WebmasterSearchQuery.date == last_date)
                    .group_by(WebmasterSearchQuery.query)
                    .order_by(func.sum(WebmasterSearchQuery.impressions).desc())
                    .limit(10)
                )).all()
                top_demand = [
                    {
                        "query": q, "impressions": int(i or 0), "clicks": int(c or 0),
                        "avg_position": round(float(p), 1) if p is not None else None,
                    }
                    for q, i, c, p in rows
                ]
                host_rows = (await seo_db.execute(
                    select(
                        WebmasterSearchQuery.host,
                        func.sum(WebmasterSearchQuery.impressions),
                        func.sum(WebmasterSearchQuery.clicks),
                    )
                    .where(WebmasterSearchQuery.date == last_date)
                    .group_by(WebmasterSearchQuery.host)
                    .order_by(func.sum(WebmasterSearchQuery.impressions).desc())
                )).all()
                demand_by_host = [
                    {
                        "host": h,
                        "impressions": int(i or 0),
                        "clicks": int(c or 0),
                    }
                    for h, i, c in host_rows
                ]
            try:
                from app.models import WebmasterIndexingDaily
                from app.services.display import today_msk
                row = await seo_db.scalar(
                    select(WebmasterIndexingDaily).where(
                        WebmasterIndexingDaily.host == "forecasteconomy.com",
                        WebmasterIndexingDaily.day == today_msk(),
                    )
                )
                if row:
                    indexing_daily = {
                        "in_search": row.in_search,
                        "crawled_2xx": row.crawled_2xx,
                        "crawled_5xx": row.crawled_5xx,
                        "sitemap_errors": row.sitemap_errors,
                    }
            except Exception:
                indexing_daily = None
        return {
            "available": True,
            "sitemap_urls_total": total_urls,
            "searchable_pages": searchable,
            "excluded_pages": summary.get("excluded_pages_count"),
            "sqi": summary.get("sqi"),
            "indexed_share_pct": (
                round(100 * searchable / total_urls, 1) if searchable and total_urls else None
            ),
            "site_problems": summary.get("site_problems") or {},
            "summary_by_host": summary_by_host,
            "exclusion_reasons_sample": exclusion_reasons,
            "top_search_queries_date": last_date.isoformat() if last_date else None,
            "top_search_queries": top_demand,
            "demand_by_host": demand_by_host,
            "indexing_daily": indexing_daily,
        }
    except Exception:
        logger.warning("Pulse SEO snapshot failed", exc_info=True)
        return {"available": False, "reason": "fetch failed"}


async def _bot_signals(d: date) -> dict[str, Any]:
    """Агрегат бот-признаков behavior_sessions за день (план 2026-09-03)."""
    start, end = _day_bounds(d)
    async with analytics_session() as db:
        total = int(await db.scalar(
            select(func.count()).select_from(BehaviorSession).where(
                BehaviorSession.started_at >= start, BehaviorSession.started_at < end,
            )
        ) or 0)
        webdriver = int(await db.scalar(
            select(func.count()).select_from(BehaviorSession).where(
                BehaviorSession.started_at >= start, BehaviorSession.started_at < end,
                BehaviorSession.is_webdriver.is_(True),
            )
        ) or 0)
        by_country_rows = (await db.execute(
            select(BehaviorSession.country, func.count())
            .where(BehaviorSession.started_at >= start, BehaviorSession.started_at < end)
            .group_by(BehaviorSession.country)
            .order_by(func.count().desc())
            .limit(8)
        )).all()
    share = round(100 * webdriver / total, 1) if total else 0
    sg_n = 0
    for k, v in by_country_rows:
        name = (k or "").casefold()
        if name in {"sg", "singapore", "сингапур"}:
            sg_n += int(v)
    sg_share = round(100 * sg_n / total, 1) if total else 0
    if webdriver >= 30 and share >= 20:
        try:
            from app.services.analytics_alerts import _alert
            await _alert(
                "bot_wave",
                f"Волна webdriver-сессий: {webdriver} из {total} ({share}%) за {d}.",
            )
        except Exception:  # noqa: BLE001
            logger.warning("bot_wave alert failed", exc_info=True)
    if sg_n >= 50 and sg_share >= 25:
        try:
            from app.services.analytics_alerts import _alert
            await _alert(
                "sg_scrape",
                f"Скрейп из Сингапура: {sg_n} сессий ({sg_share}% от {total}) за {d}. "
                "Bind-cookie fe_bind (кросс-IP) + хостинговые ASN, не страны.",
            )
        except Exception:  # noqa: BLE001
            logger.warning("sg_scrape alert failed", exc_info=True)
    return {
        "available": True,
        "sessions": total,
        "webdriver": webdriver,
        "webdriver_share_pct": share,
        "singapore": sg_n,
        "singapore_share_pct": sg_share,
        "top_countries": {str(k or "unknown"): int(v) for k, v in by_country_rows},
    }


async def _signup_dims(db, user_ids: list) -> dict[str, dict[str, Any]]:
    """Язык сайта и страна первого визита новых пользователей (без ПДн).

    Таблица `user_signups` появилась в круге 11; на базе без миграции или в
    тестовой схеме без неё функция возвращает пусто и не роняет снимок.
    """
    try:
        from app.models import UserSignup

        # SAVEPOINT: отсутствие таблицы на базе без миграции не должно
        # отравить внешнюю транзакцию снимка (PostgreSQL: aborted transaction).
        async with db.begin_nested():
            rows = (await db.execute(
                select(UserSignup.user_id, UserSignup.site_locale, UserSignup.country)
                .where(UserSignup.user_id.in_(list(user_ids)))
            )).all()
    except Exception:  # noqa: BLE001
        logger.debug("signup dims unavailable", exc_info=True)
        return {}
    out: dict[str, dict[str, Any]] = {}
    for uid, locale, country in rows:
        item: dict[str, Any] = {}
        if locale:
            item["site_locale"] = locale
        if country:
            item["country"] = country
        out[str(uid)] = item
    return out


_REGION_MARKERS = ("/region/", "/regions/")


def _region_from_url(url: str | None) -> str | None:
    if not url:
        return None
    u = str(url)
    for marker in _REGION_MARKERS:
        if marker in u:
            return u.split(marker, 1)[1].split("/")[0].split("?")[0] or None
    return None


async def _events_snapshot(db, start: datetime, end: datetime) -> dict[str, Any]:
    """Бизнес-события суток агрегатами SQL (E7). Результат совместим по форме с
    прежним построчным подсчётом: те же ключи `events` и `audience`."""
    window = (FrontendEvent.occurred_at >= start, FrontendEvent.occurred_at < end)

    # 1) счёт по имени и аудитории: одна выборка по индексу имя+время.
    name_rows = (await db.execute(
        select(FrontendEvent.event_name, FrontendEvent.authed, func.count())
        .where(*window)
        .group_by(FrontendEvent.event_name, FrontendEvent.authed)
    )).all()
    by_name: Counter[str] = Counter()
    downloads: Counter[str] = Counter()
    walls: Counter[str] = Counter()
    errors: Counter[str] = Counter()
    events_by_audience = {"guest": 0, "authed": 0}
    downloads_by_audience = {"guest": 0, "authed": 0}
    for name, authed, n in name_rows:
        n = int(n)
        bucket = "authed" if authed else "guest"
        by_name[name] += n
        events_by_audience[bucket] += n
        if name in _DOWNLOAD_EVENTS:
            downloads[name] += n
            downloads_by_audience[bucket] += n
        if name in _WALL_EVENTS:
            walls[name] += n
        if name in _ERROR_EVENTS:
            errors[name] += n

    # 2) аудитория: зарегистрированные по user_id, гости по хэшу сессии.
    is_user = (FrontendEvent.authed.is_(True)) & (FrontendEvent.user_id.is_not(None))
    authed_active = int(await db.scalar(
        select(func.count(func.distinct(FrontendEvent.user_id))).where(*window, is_user)
    ) or 0)
    guest_sessions = int(await db.scalar(
        select(func.count(func.distinct(FrontendEvent.session_id_hash)))
        .where(*window, ~is_user, FrontendEvent.session_id_hash.is_not(None))
    ) or 0)

    # 3) показатели: параметр `indicator` только у двух событий просмотра.
    indicator_col = FrontendEvent.params_json["indicator"].as_string()
    indicators: Counter[str] = Counter()
    for ind, n in (await db.execute(
        select(indicator_col, func.count())
        .where(*window, FrontendEvent.event_name.in_(("indicator_view", "region_indicator_view")),
               indicator_col.is_not(None), indicator_col != "")
        .group_by(indicator_col).order_by(func.count().desc()).limit(200)
    )).all():
        indicators[str(ind)] += int(n)

    # 4) поиск: группируем по строке запроса и числу результатов, чистим в Python.
    q_col = FrontendEvent.params_json["q"].as_string()
    res_col = FrontendEvent.params_json["results"].as_string()
    searches: Counter[str] = Counter()
    zero_search: Counter[str] = Counter()
    for q, results, n in (await db.execute(
        select(q_col, res_col, func.count())
        .where(*window, FrontendEvent.event_name == "search_query", q_col.is_not(None))
        .group_by(q_col, res_col).order_by(func.count().desc()).limit(3000)
    )).all():
        q = scrub_text(str(q or "").strip().lower())
        if not q:
            continue
        searches[q] += int(n)
        try:
            if int(results if results is not None else -1) == 0:
                zero_search[q] += int(n)
        except (TypeError, ValueError):
            pass

    # 5) регионы: параметр события, иначе сегмент пути `/region/{slug}`. Берём
    # только события с регионом в параметре или в пути и группируем по паре,
    # поэтому в Python попадают уникальные пары, а не каждое событие.
    region_col = FrontendEvent.params_json["region"].as_string()
    regions: Counter[str] = Counter()
    for region_param, url, n in (await db.execute(
        select(region_col, FrontendEvent.url, func.count())
        .where(*window, or_(region_col.is_not(None),
                            FrontendEvent.url.like("%/region/%"),
                            FrontendEvent.url.like("%/regions/%")))
        .group_by(region_col, FrontendEvent.url)
        .order_by(func.count().desc()).limit(5000)
    )).all():
        slug = region_param or _region_from_url(url)
        if slug:
            regions[str(slug)] += int(n)

    return {
        "events": {
            "total": sum(by_name.values()),
            "by_name": dict(by_name.most_common(40)),
            "by_audience": events_by_audience,
            "downloads_by_audience": downloads_by_audience,
            "top_indicators": dict(indicators.most_common(10)),
            "top_regions": dict(regions.most_common(10)),
            "downloads": dict(downloads),
            "wall_hits": dict(walls),
            "errors": dict(errors),
            "search_top": dict(searches.most_common(10)),
            "search_zero_results": dict(zero_search.most_common(10)),
        },
        "audience": {
            "authed_active": authed_active,
            "guest_sessions": guest_sessions,
        },
    }


async def build_snapshot(d: date) -> dict[str, Any]:
    """Собрать снапшот дня из БД. Чистое чтение, без побочных эффектов."""
    start, end = _day_bounds(d)
    built_at = datetime.now(timezone.utc).replace(tzinfo=None)
    snap: dict[str, Any] = {
        "date": d.isoformat(),
        # E2 (круг 11): окно и момент сборки. Снимок, собранный до конца МСК-суток
        # (23:57), неполон; `get_or_build_snapshot` пересоберёт его утром.
        "window": {
            "start_utc": start.isoformat(), "end_utc": end.isoformat(),
            "built_at_utc": built_at.isoformat(), "tz": "Europe/Moscow",
        },
        "complete": built_at >= end,
    }

    async with analytics_session() as db:
        # --- Пользователи -------------------------------------------------
        total_users = await db.scalar(select(func.count(User.id))) or 0
        new_users = (await db.execute(
            select(User).where(User.created_at >= start, User.created_at < end)
        )).scalars().all()
        newsletter = await db.scalar(
            newsletter_subscriber_count_query()
        ) or 0

        # 152-ФЗ (круг 11): имена и почты новых пользователей в снимок не кладём —
        # снимок целиком уходит в LLM (OpenRouter, зарубежный прокси). Остаются
        # способ входа, язык сайта и страна первого визита, если они известны.
        new_list = []
        if new_users:
            ids = [u.id for u in new_users]
            emails = {uid for (uid,) in (await db.execute(
                select(EmailCredential.user_id).where(EmailCredential.user_id.in_(ids))
            )).all()}
            oauth = {}
            for uid, provider in (await db.execute(
                select(OAuthIdentity.user_id, OAuthIdentity.provider)
                .where(OAuthIdentity.user_id.in_(ids))
            )).all():
                oauth.setdefault(uid, []).append(provider)
            signup_info = await _signup_dims(db, ids)
            for u in new_users:
                methods = (["email"] if u.id in emails else []) + oauth.get(u.id, [])
                entry = {"method": "/".join(methods) or "—"}
                entry.update(signup_info.get(str(u.id), {}))
                new_list.append(entry)
        snap["users"] = {
            "total": total_users,
            "new": len(new_users),
            "new_list": new_list[:20],
            "newsletter": newsletter,
        }

        # --- Аутентификация -----------------------------------------------
        auth_rows = (await db.execute(
            select(AuthAudit.event, func.count())
            .where(AuthAudit.ts >= start, AuthAudit.ts < end)
            .group_by(AuthAudit.event)
        )).all()
        snap["auth"] = {ev: n for ev, n in auth_rows}

        # --- События фронта -----------------------------------------------
        # E7 (круг 11): считаем на SQL, а не читаем в память все строки суток с
        # params_json и url (при росте к сотням тысяч событий это съедало
        # контейнер на 1 ГиБ). Тяжёлый JSON читаем только у малых групп событий.
        snap_events = await _events_snapshot(db, start, end)
        snap["events"] = snap_events["events"]
        # Активная аудитория дня: уникальные зарегистрированные (по user_id) и
        # гости (по хэшу сессии). Даёт «сколько живых людей», а не только хиты.
        snap["audience"] = snap_events["audience"]

        # --- Поведенческий поток (behavior.js: сырые клики/мышь/скролл) ------
        # Агрегируем на SQL, сырые строки в снапшот не тянем (их могут быть
        # сотни тысяч в день). Дневной агрегат — это и есть долгосрочная
        # память потока после retention-чистки сырья.
        b_by_type = dict((await db.execute(
            select(BehaviorEvent.event_type, func.count())
            .where(BehaviorEvent.occurred_at >= start, BehaviorEvent.occurred_at < end)
            .group_by(BehaviorEvent.event_type)
        )).all())
        b_pageviews = dict((await db.execute(
            select(BehaviorEvent.page, func.count())
            .where(BehaviorEvent.occurred_at >= start, BehaviorEvent.occurred_at < end,
                   BehaviorEvent.event_type == "pageview")
            .group_by(BehaviorEvent.page)
            .order_by(func.count().desc()).limit(15)
        )).all())
        b_clicks = (await db.execute(
            select(BehaviorEvent.element_path, BehaviorEvent.element_text, func.count())
            .where(BehaviorEvent.occurred_at >= start, BehaviorEvent.occurred_at < end,
                   BehaviorEvent.event_type == "click")
            .group_by(BehaviorEvent.element_path, BehaviorEvent.element_text)
            .order_by(func.count().desc()).limit(15)
        )).all()
        b_dead = (await db.execute(
            select(BehaviorEvent.element_path, BehaviorEvent.element_text, func.count())
            .where(BehaviorEvent.occurred_at >= start, BehaviorEvent.occurred_at < end,
                   BehaviorEvent.event_type == "click", BehaviorEvent.is_dead.is_(True))
            .group_by(BehaviorEvent.element_path, BehaviorEvent.element_text)
            .order_by(func.count().desc()).limit(10)
        )).all()
        b_rage = (await db.execute(
            select(BehaviorEvent.page, BehaviorEvent.element_path, func.count())
            .where(BehaviorEvent.occurred_at >= start, BehaviorEvent.occurred_at < end,
                   BehaviorEvent.event_type == "click", BehaviorEvent.is_rage.is_(True))
            .group_by(BehaviorEvent.page, BehaviorEvent.element_path)
            .order_by(func.count().desc()).limit(10)
        )).all()
        # dwell: среднее время и глубина скролла по страницам (из params_json)
        dwell_rows = (await db.execute(
            select(BehaviorEvent.page, BehaviorEvent.params_json)
            .where(BehaviorEvent.occurred_at >= start, BehaviorEvent.occurred_at < end,
                   BehaviorEvent.event_type == "dwell")
        )).all()
        dwell_by_page: dict[str, list] = {}
        for page, params in dwell_rows:
            p = params or {}
            if page and isinstance(p.get("ms"), (int, float)):
                dwell_by_page.setdefault(page, []).append((p["ms"], p.get("scroll_pct") or 0))
        b_dwell = {
            page: {
                "visits": len(vals),
                "avg_seconds": round(sum(v[0] for v in vals) / len(vals) / 1000, 1),
                "avg_scroll_pct": round(sum(v[1] for v in vals) / len(vals)),
            }
            for page, vals in sorted(dwell_by_page.items(), key=lambda kv: -len(kv[1]))[:15]
        }
        b_copy = (await db.execute(
            select(BehaviorEvent.params_json)
            .where(BehaviorEvent.occurred_at >= start, BehaviorEvent.occurred_at < end,
                   BehaviorEvent.event_type == "copy")
            .limit(300)
        )).scalars().all()
        copy_counter: Counter[str] = Counter()
        for p in b_copy:
            t = (p or {}).get("text")
            if t:
                copy_counter[scrub_text(str(t)[:60])] += 1
        snap["behavior"] = {
            "by_type": b_by_type,
            "pageviews_top": b_pageviews,
            "clicks_top": [
                {"element": path, "text": scrub_text(text) if text else text, "n": n}
                for path, text, n in b_clicks
            ],
            "dead_clicks_top": [
                {"element": path, "text": text, "n": n} for path, text, n in b_dead
            ],
            "rage_clicks_top": [
                {"page": page, "element": path, "n": n} for page, path, n in b_rage
            ],
            "dwell_by_page": b_dwell,
            "copied_top": dict(copy_counter.most_common(10)),
        }

        # --- Привлечение (Метрика-хранилище) --------------------------------
        # Читаем из СВОЕЙ БД (metrika_acquisition.py наполняет её по утрам),
        # не из живого API — детерминированно и работает при сбоях Яндекса.
        snap["acquisition"] = await _acquisition_from_warehouse(db, d)

        # --- ETL ------------------------------------------------------------
        snap["etl"] = await _etl_snapshot(db, start, end)

        # --- Приток данных ---------------------------------------------------
        # (у region_data нет created_at — региональный приток пришёл бы из ETL-логов)
        new_points = await db.scalar(
            select(func.count(IndicatorData.id))
            .where(IndicatorData.created_at >= start, IndicatorData.created_at < end)
        ) or 0
        snap["data"] = {"new_points": new_points}

    # HTTP Вебмастера и витрины — вне основной сессии (idle in transaction).
    snap["seo"] = await _seo_snapshot()
    try:
        from app.services.analytics_marts import build_marts_daily_context
        async with analytics_session() as db:
            snap["marts"] = await build_marts_daily_context(db)
    except Exception:  # noqa: BLE001 — Пульс не падает из-за витрин
        logger.exception("Pulse marts context failed")
        snap["marts"] = {"error": "marts context unavailable"}

    try:
        snap["bots"] = await _bot_signals(d)
    except Exception:  # noqa: BLE001
        logger.exception("Pulse bot signals failed")
        snap["bots"] = {"available": False}

    return snap


async def build_acquisition(d: date) -> dict[str, Any]:
    """Свежий срез привлечения из хранилища (для обновления снапшота,
    зафиксированного в 23:57, — утренний синк Метрики приходит позже)."""
    async with analytics_session() as db:
        return await _acquisition_from_warehouse(db, d)


async def store_snapshot(snap: dict[str, Any]) -> None:
    r = await get_state_redis()
    await r.set(_SNAP_KEY.format(d=snap["date"]), json.dumps(snap, ensure_ascii=False), ex=SNAPSHOT_TTL)


async def load_snapshot(d: date) -> dict[str, Any] | None:
    r = await get_state_redis()
    raw = await r.get(_SNAP_KEY.format(d=d.isoformat()))
    return json.loads(raw) if raw else None


def snapshot_is_complete(snap: dict[str, Any] | None, d: date) -> bool:
    """Снимок дня `d` собран после конца МСК-суток и по МСК-окну.

    Снимки до круга 11 (без ключа `window`) построены по окну UTC и без
    последних часов суток; снимок, зафиксированный в 23:57, не видит 3 минуты
    до полуночи МСК. Оба считаются неполными, пока день закончился.
    """
    if not snap or not isinstance(snap.get("window"), dict):
        return False
    return bool(snap.get("complete"))


async def get_or_build_snapshot(d: date) -> dict[str, Any]:
    """Снимок дня: из Redis, если он полон; иначе пересобираем (E2).

    Для сегодняшнего (ещё не закончившегося) дня сохранённый снимок не
    пересобираем: он по определению неполон, пересчёт по запросу делает
    вызывающий код (`build_snapshot`).
    """
    snap = await load_snapshot(d)
    day_over = d < today_msk()
    if snap is None or (day_over and not snapshot_is_complete(snap, d)):
        snap = await build_snapshot(d)
        await store_snapshot(snap)
    return snap


def acquisition_metrics(acq: dict[str, Any]) -> dict[str, Any]:
    """Числа сохранённых отчётов; отсутствие отчёта не является нулём."""
    reports = (acq.get("metadata") or {}).get("reports") or {}

    def visits(report_type: str, channel: str | None = None) -> int | None:
        rows = acq.get(report_type)
        info = reports.get(report_type) or {}
        if not isinstance(rows, dict) or info.get("status", "available") != "available":
            return None
        matching = [v for v in rows.values() if channel is None or v.get("id") == channel]
        partial = (info.get("total_rows") is not None and info.get("returned_rows") is not None
                   and info["total_rows"] > info["returned_rows"])
        if not matching and (partial or info.get("sampled")):
            return None
        if any(v.get("visits") is None for v in matching):
            return None
        return sum(v["visits"] for v in matching)

    campaigns = acq.get("ad_campaigns")
    return {
        "metrika_visits": visits("traffic_sources"),
        "metrika_ad_visits": visits("traffic_sources", "ad"),
        "metrika_organic_visits": visits("traffic_sources", "organic"),
        "metrika_campaign_rows": len(campaigns) if isinstance(campaigns, dict) else None,
        "metrika_campaign_visits": visits("ad_campaigns"),
    }


def memory_core(snap: dict[str, Any]) -> dict[str, Any]:
    """Компактное числовое ядро дня для памяти (десятки байт, не килобайты)."""
    ev = snap.get("events", {})
    aud = snap.get("audience", {})
    dl_aud = ev.get("downloads_by_audience", {})
    return {
        "date": snap["date"],
        "users_total": snap.get("users", {}).get("total", 0),
        "users_new": snap.get("users", {}).get("new", 0),
        "events": ev.get("total", 0),
        "downloads": sum(ev.get("downloads", {}).values()),
        "downloads_authed": dl_aud.get("authed", 0),
        "downloads_guest": dl_aud.get("guest", 0),
        "authed_active": aud.get("authed_active", 0),
        "guest_sessions": aud.get("guest_sessions", 0),
        "errors": sum(ev.get("errors", {}).values()),
        "etl_failed": len(snap.get("etl", {}).get("failed_indicator_ids", [])),
        "new_points": snap.get("data", {}).get("new_points", 0),
        "behavior_clicks": snap.get("behavior", {}).get("by_type", {}).get("click", 0),
        "behavior_dead": sum(d.get("n", 0) for d in snap.get("behavior", {}).get("dead_clicks_top", [])),
        "behavior_rage": sum(d.get("n", 0) for d in snap.get("behavior", {}).get("rage_clicks_top", [])),
        **acquisition_metrics(snap.get("acquisition") or {}),
        "acquisition_metadata": (snap.get("acquisition") or {}).get("metadata"),
        "seo_indexed_share_pct": snap.get("seo", {}).get("indexed_share_pct"),
        "seo_searchable_pages": snap.get("seo", {}).get("searchable_pages"),
    }


async def store_memory(d: date, core: dict[str, Any], summary: str) -> None:
    """Память дня: ядро чисел + однострочная LLM-сводка."""
    r = await get_state_redis()
    entry = {**core, "summary": summary[:400]}
    await r.set(_MEM_KEY.format(d=d.isoformat()), json.dumps(entry, ensure_ascii=False), ex=MEMORY_TTL)


async def load_memory(days: int = 7, before: date | None = None) -> list[dict[str, Any]]:
    """Память за последние `days` дней (до `before` исключительно), старые → новые."""
    before = before or today_msk()
    r = await get_state_redis()
    out: list[dict[str, Any]] = []
    for i in range(days, 0, -1):
        d = before - timedelta(days=i)
        raw = await r.get(_MEM_KEY.format(d=d.isoformat()))
        if raw:
            try:
                out.append(json.loads(raw))
            except ValueError:
                continue
    return out

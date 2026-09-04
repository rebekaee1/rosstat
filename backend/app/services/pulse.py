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
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, select

from app.config import settings
from app.core.cache import get_state_redis
from app.database import analytics_session
from app.models import (
    AuthAudit,
    BehaviorEvent,
    BehaviorSession,
    Consent,
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

_DOWNLOAD_EVENTS = {
    "download_csv", "download_excel", "chart_image_download",
    "compare_image_download", "compare_csv_download", "download_limit",
}
_ERROR_EVENTS = {"error_reload", "api_retry", "api_error"}

# Статусы FetchLog, означающие ошибку прогона. Источник истины — что реально
# пишут base_parser.py ("failed") и tasks/scheduler.py ("failed"/"timeout").
# Статуса "error" в системе не существует: фильтр по нему делал Пульс слепым
# к ошибкам ETL (владелец видел «0 ошибок» при реальных провалах).
ETL_ERROR_STATUSES = ("failed", "timeout")


def _day_bounds(d: date) -> tuple[datetime, datetime]:
    start = datetime.combine(d, time.min)
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
    """Привлечение за день из Метрика-хранилища: источники трафика, поисковики,
    фразы, рефереры, рекламные кампании, повизитное сырьё. Пусто = синк ещё
    не отработал (наполняется `metrika_acquisition.sync_acquisition_for_day`,
    08:20 МСК за вчера)."""
    def _snapshot_rows(response_json: dict | None) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for row in (response_json or {}).get("data", []):
            dims = row.get("dimensions") or []
            metrics = row.get("metrics") or []
            name = str(dims[0].get("name")) if dims else "?"
            out[name] = {
                "id": dims[0].get("id") if dims else None,
                "visits": int(metrics[0] or 0) if len(metrics) > 0 else 0,
                "users": int(metrics[1] or 0) if len(metrics) > 1 else 0,
            }
        return out

    acq: dict[str, Any] = {}
    snap_rows = (await db.execute(
        select(MetrikaReportSnapshot.report_type, MetrikaReportSnapshot.response_json)
        .where(MetrikaReportSnapshot.date_from == d, MetrikaReportSnapshot.date_to == d,
               MetrikaReportSnapshot.report_type.in_(
                   ["traffic_sources", "search_engines", "referrers", "ad_campaigns"]))
        .order_by(MetrikaReportSnapshot.captured_at)
    )).all()
    for report_type, response_json in snap_rows:  # последний снапшот дня побеждает
        acq[report_type] = _snapshot_rows(response_json)

    phrases = (await db.execute(
        select(MetrikaSearchPhrase.phrase, MetrikaSearchPhrase.search_engine,
               MetrikaSearchPhrase.visits)
        .where(MetrikaSearchPhrase.date == d)
        .order_by(MetrikaSearchPhrase.visits.desc()).limit(25)
    )).all()
    if phrases:
        acq["search_phrases_top"] = [
            {"phrase": p, "engine": e, "visits": v} for p, e, v in phrases
        ]

    visits_total = await db.scalar(
        select(func.count(RawMetrikaVisit.id)).where(RawMetrikaVisit.visit_date == d)
    ) or 0
    if visits_total:
        by_source = dict((await db.execute(
            select(RawMetrikaVisit.traffic_source, func.count())
            .where(RawMetrikaVisit.visit_date == d)
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
                "Bind-cookie fe_bind (кросс-IP) + опциональный гео-блок.",
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


async def build_snapshot(d: date) -> dict[str, Any]:
    """Собрать снапшот дня из БД. Чистое чтение, без побочных эффектов."""
    start, end = _day_bounds(d)
    snap: dict[str, Any] = {"date": d.isoformat()}

    async with analytics_session() as db:
        # --- Пользователи -------------------------------------------------
        total_users = await db.scalar(select(func.count(User.id))) or 0
        new_users = (await db.execute(
            select(User).where(User.created_at >= start, User.created_at < end)
        )).scalars().all()
        newsletter = await db.scalar(
            select(func.count(func.distinct(Consent.user_id))).where(Consent.kind == "newsletter")
        ) or 0

        new_list = []
        if new_users:
            ids = [u.id for u in new_users]
            emails = dict((await db.execute(
                select(EmailCredential.user_id, EmailCredential.email)
                .where(EmailCredential.user_id.in_(ids))
            )).all())
            oauth = {}
            for uid, provider in (await db.execute(
                select(OAuthIdentity.user_id, OAuthIdentity.provider)
                .where(OAuthIdentity.user_id.in_(ids))
            )).all():
                oauth.setdefault(uid, []).append(provider)
            for u in new_users:
                methods = (["email"] if u.id in emails else []) + oauth.get(u.id, [])
                new_list.append({
                    "name": u.display_name or "—",
                    "contact": emails.get(u.id) or "—",
                    "method": "/".join(methods) or "—",
                })
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
        ev_rows = (await db.execute(
            select(
                FrontendEvent.event_name,
                FrontendEvent.params_json,
                FrontendEvent.url,
                FrontendEvent.authed,
                FrontendEvent.user_id,
                FrontendEvent.session_id_hash,
            )
            .where(FrontendEvent.occurred_at >= start, FrontendEvent.occurred_at < end)
        )).all()

        by_name: Counter[str] = Counter()
        indicators: Counter[str] = Counter()
        regions: Counter[str] = Counter()
        searches: Counter[str] = Counter()
        zero_search: Counter[str] = Counter()
        downloads: Counter[str] = Counter()
        errors: Counter[str] = Counter()
        # Разрез «гость vs зарегистрированный»: события, скачивания, аудитория.
        events_by_audience = {"guest": 0, "authed": 0}
        downloads_by_audience = {"guest": 0, "authed": 0}
        authed_user_ids: set[str] = set()
        guest_sessions: set[str] = set()
        for name, params, url, authed, user_id, sess_hash in ev_rows:
            by_name[name] += 1
            bucket = "authed" if authed else "guest"
            events_by_audience[bucket] += 1
            if authed and user_id:
                authed_user_ids.add(str(user_id))
            elif sess_hash:
                guest_sessions.add(str(sess_hash))
            params = params or {}
            if name in ("indicator_view", "region_indicator_view") and params.get("indicator"):
                indicators[str(params["indicator"])] += 1
            if name in _DOWNLOAD_EVENTS:
                downloads[name] += 1
                downloads_by_audience[bucket] += 1
            if name in _ERROR_EVENTS:
                errors[name] += 1
            if name == "search_query":
                q = str(params.get("q") or "").strip().lower()
                if q:
                    searches[q] += 1
                    try:
                        if int(params.get("results", -1)) == 0:
                            zero_search[q] += 1
                    except (TypeError, ValueError):
                        pass
            # Регион: сначала из параметра события (region_indicator_view,
            # region_compare_add и т.п.), иначе из URL (/region/{slug}/... или
            # /regions/{slug}). Детальная карточка живёт на /region/ (ед. число).
            slug = params.get("region")
            if not slug and url:
                u = str(url)
                for marker in ("/region/", "/regions/"):
                    if marker in u:
                        slug = u.split(marker, 1)[1].split("/")[0].split("?")[0]
                        break
            if slug:
                regions[str(slug)] += 1

        snap["events"] = {
            "total": sum(by_name.values()),
            "by_name": dict(by_name.most_common(40)),
            "by_audience": events_by_audience,
            "downloads_by_audience": downloads_by_audience,
            "top_indicators": dict(indicators.most_common(10)),
            "top_regions": dict(regions.most_common(10)),
            "downloads": dict(downloads),
            "errors": dict(errors),
            "search_top": dict(searches.most_common(10)),
            "search_zero_results": dict(zero_search.most_common(10)),
        }
        # Активная аудитория дня: уникальные зарегистрированные (по user_id) и
        # гости (по хэшу сессии). Даёт «сколько живых людей», а не только хиты.
        snap["audience"] = {
            "authed_active": len(authed_user_ids),
            "guest_sessions": len(guest_sessions),
        }

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
                copy_counter[str(t)[:60]] += 1
        snap["behavior"] = {
            "by_type": b_by_type,
            "pageviews_top": b_pageviews,
            "clicks_top": [
                {"element": path, "text": text, "n": n} for path, text, n in b_clicks
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


async def get_or_build_snapshot(d: date) -> dict[str, Any]:
    snap = await load_snapshot(d)
    if snap is None:
        snap = await build_snapshot(d)
        await store_snapshot(snap)
    return snap


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
        # Привлечение: суммарные визиты дня по Метрике и сколько из них реклама —
        # главный KPI владельца (трафик и его состав) в трендовой памяти.
        "metrika_visits": sum(
            v.get("visits", 0)
            for v in snap.get("acquisition", {}).get("traffic_sources", {}).values()
        ),
        "metrika_ad_visits": sum(
            v.get("visits", 0)
            for v in snap.get("acquisition", {}).get("traffic_sources", {}).values()
            if v.get("id") == "ad"
        ),
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
    before = before or date.today()
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

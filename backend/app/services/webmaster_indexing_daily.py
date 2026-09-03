"""Ежедневный снимок индексации Яндекс.Вебмастера.

Таблица webmaster_indexing_daily + алерты (5xx роботу, ошибки sitemap,
падение in-search, обход 2xx).
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.database import analytics_session
from app.models import WebmasterIndexingDaily
from app.services.display import today_msk
from app.services.webmaster_indexing_report import _http_breakdown, _report_host_ids

logger = logging.getLogger(__name__)


def _host_label(host_id: str) -> str:
    return host_id.replace("https:", "").replace(":443", "")


async def sync_webmaster_indexing_daily(day: date | None = None) -> int:
    if not settings.yandex_webmaster_token:
        return 0
    day = day or (today_msk() - timedelta(days=1))
    from app.services.yandex_webmaster_client import YandexWebmasterClient

    client = YandexWebmasterClient()
    user = await client.user()
    user_id = user.data["user_id"]
    stored = 0
    async with analytics_session() as db:
        for host_id in _report_host_ids():
            host = _host_label(host_id)
            payload: dict = {"host_id": host_id}
            in_search = crawled = appeared = excluded = sitemap_errors = None
            c2 = c3 = c4 = c5 = None
            try:
                hist = (await client.in_search_history(
                    user_id, host_id, date_from=day.isoformat(), date_to=day.isoformat(),
                )).data
                payload["in_search"] = hist
                in_search = _latest_indicator(hist, "SEARCHABLE") or _latest_value(hist)
            except Exception:
                logger.warning("in-search/history failed host=%s", host, exc_info=True)
            try:
                idx = (await client.indexing_history(
                    user_id, host_id, date_from=day.isoformat(), date_to=day.isoformat(),
                )).data
                payload["indexing"] = idx
                codes = _http_breakdown(idx)
                c2 = sum(v for k, v in codes.items() if k.startswith("2"))
                c3 = sum(v for k, v in codes.items() if k.startswith("3"))
                c4 = sum(v for k, v in codes.items() if k.startswith("4"))
                c5 = sum(v for k, v in codes.items() if k.startswith("5"))
            except Exception:
                logger.warning("indexing/history failed host=%s", host, exc_info=True)
            try:
                events = (await client.search_events_history(
                    user_id, host_id, date_from=day.isoformat(), date_to=day.isoformat(),
                )).data
                payload["events"] = events
                appeared, excluded = _events_counts(events)
            except Exception:
                logger.warning("events/history failed host=%s", host, exc_info=True)
            try:
                sm = (await client.sitemaps(user_id, host_id)).data
                payload["sitemaps"] = sm
                sitemap_errors = _sitemap_error_count(sm)
            except Exception:
                logger.warning("sitemaps failed host=%s", host, exc_info=True)

            stmt = insert(WebmasterIndexingDaily).values(
                host=host,
                day=day,
                in_search=in_search,
                crawled_2xx=c2,
                crawled_3xx=c3,
                crawled_4xx=c4,
                crawled_5xx=c5,
                appeared=appeared,
                excluded=excluded,
                sitemap_errors=sitemap_errors,
                raw_json=payload,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_webmaster_indexing_daily",
                set_={
                    "in_search": stmt.excluded.in_search,
                    "crawled_2xx": stmt.excluded.crawled_2xx,
                    "crawled_3xx": stmt.excluded.crawled_3xx,
                    "crawled_4xx": stmt.excluded.crawled_4xx,
                    "crawled_5xx": stmt.excluded.crawled_5xx,
                    "appeared": stmt.excluded.appeared,
                    "excluded": stmt.excluded.excluded,
                    "sitemap_errors": stmt.excluded.sitemap_errors,
                    "raw_json": stmt.excluded.raw_json,
                },
            )
            await db.execute(stmt)
            stored += 1
        await db.commit()
    await _alerting(day)
    return stored


def _latest_value(payload: dict) -> int | None:
    indicators = payload.get("indicators")
    if isinstance(indicators, dict):
        for series in indicators.values():
            if series:
                return int(series[-1].get("value") or 0)
    if isinstance(indicators, list) and indicators:
        hist = indicators[0].get("history") or []
        if hist:
            return int(hist[-1].get("value") or 0)
    return None


def _latest_indicator(payload: dict, name: str) -> int | None:
    indicators = payload.get("indicators")
    if isinstance(indicators, dict) and name in indicators:
        series = indicators[name] or []
        if series:
            return int(series[-1].get("value") or 0)
    if isinstance(indicators, list):
        for series in indicators:
            if series.get("indicator") == name:
                hist = series.get("history") or []
                if hist:
                    return int(hist[-1].get("value") or 0)
    return None


def _events_counts(payload: dict) -> tuple[int | None, int | None]:
    appeared = excluded = 0
    found = False
    for sample in payload.get("indicators") or payload.get("samples") or []:
        found = True
        event = (sample.get("event") or sample.get("indicator") or "").upper()
        value = int(sample.get("value") or sample.get("count") or 0)
        if "APPEAR" in event or event == "ADDED_TO_SEARCH":
            appeared += value
        elif "REMOV" in event or event == "REMOVED_FROM_SEARCH":
            excluded += value
    if not found:
        return None, None
    return appeared, excluded


def _sitemap_error_count(payload: dict) -> int:
    n = 0
    sitemaps = payload.get("sitemaps") or payload.get("user_added_sitemaps") or []
    if isinstance(sitemaps, dict):
        sitemaps = sitemaps.get("sitemaps") or []
    for item in sitemaps:
        problems = item.get("problems") or item.get("error_count") or 0
        if isinstance(problems, int):
            n += problems
        elif isinstance(problems, list):
            n += len(problems)
        elif item.get("last_access_error"):
            n += 1
    return n


async def _alerting(day: date) -> None:
    from app.services.analytics_alerts import _alert

    async with analytics_session() as db:
        row = (await db.execute(
            select(WebmasterIndexingDaily).where(
                WebmasterIndexingDaily.host == "forecasteconomy.com",
                WebmasterIndexingDaily.day == day,
            )
        )).scalar_one_or_none()
        if row is None:
            return
        if (row.crawled_5xx or 0) > 20:
            await _alert(
                "webmaster_5xx",
                f"Вебмастер: {row.crawled_5xx} ответов 5xx роботу за {day}.",
            )
        if (row.sitemap_errors or 0) > 0:
            await _alert(
                "webmaster_sitemap_errors",
                f"Вебмастер: {row.sitemap_errors} ошибок sitemap за {day}.",
            )
        prev = (await db.execute(
            select(WebmasterIndexingDaily).where(
                WebmasterIndexingDaily.host == row.host,
                WebmasterIndexingDaily.day == day - timedelta(days=1),
            )
        )).scalar_one_or_none()
        if (
            prev and prev.in_search and row.in_search is not None
            and prev.in_search > 0
            and row.in_search < prev.in_search * 0.95
        ):
            await _alert(
                "webmaster_in_search_drop",
                f"В поиске {row.in_search} против {prev.in_search} вчера "
                f"({round(100 * row.in_search / prev.in_search)}%).",
            )
        week = (await db.execute(
            select(WebmasterIndexingDaily.crawled_2xx).where(
                WebmasterIndexingDaily.host == row.host,
                WebmasterIndexingDaily.day >= day - timedelta(days=7),
                WebmasterIndexingDaily.day < day,
            )
        )).scalars().all()
        vals = [int(v) for v in week if v is not None]
        if vals and row.crawled_2xx is not None:
            avg = sum(vals) / len(vals)
            if avg >= 50 and row.crawled_2xx < avg * 0.5:
                await _alert(
                    "webmaster_crawl_drop",
                    f"Обход 2xx {row.crawled_2xx} против среднего {round(avg)} за неделю.",
                )


async def webmaster_indexing_daily_job() -> None:
    try:
        n = await sync_webmaster_indexing_daily()
        logger.info("Webmaster indexing daily: %d hosts", n)
    except Exception:
        logger.exception("Webmaster indexing daily failed")

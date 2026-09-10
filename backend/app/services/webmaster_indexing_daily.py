"""Ежедневный снимок индексации Яндекс.Вебмастера.

Таблица webmaster_indexing_daily + алерты (5xx роботу, ошибки sitemap,
падение in-search, обход 2xx).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.database import analytics_session
from app.models import WebmasterIndexingDaily
from app.services.display import today_msk
from app.services.webmaster_indexing_report import _http_breakdown, _report_host_ids

logger = logging.getLogger(__name__)



def _host_label(host_id: str) -> str:
    return host_id.replace("https:", "").replace(":443", "")


async def sync_webmaster_indexing_daily(day: date | None = None, *, alert: bool = True, include_sitemaps: bool = True) -> int:
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
            payload: dict = {"host_id": host_id, "fetched_at": datetime.now(timezone.utc).isoformat(), "errors": {}}
            in_search = appeared = excluded = sitemap_errors = None
            c2 = c3 = c4 = c5 = None
            try:
                # Sparse search history can disconnect on a narrow interval without
                # observations. Request a short lookback, then keep only this day.
                hist = (await client.in_search_history(
                    user_id, host_id, date_from=(day - timedelta(days=7)).isoformat(), date_to=(day + timedelta(days=1)).isoformat(),
                )).data
                payload["in_search"] = hist
                in_search = _latest_value(_history_for_day(hist, day))
            except Exception:
                payload["errors"]["in-search/history"] = "fetch_or_parse_failed"
                logger.warning("in-search/history failed host=%s", host, exc_info=True)
            try:
                idx = (await client.indexing_history(
                    user_id, host_id, date_from=day.isoformat(), date_to=(day + timedelta(days=1)).isoformat(), indexing_indicator="DOWNLOADED",
                )).data
                payload["indexing"] = idx
                codes = _http_breakdown(_history_for_day(idx, day))
                c2, c3, c4, c5 = _http_classes(codes)
            except Exception:
                payload["errors"]["indexing/history"] = "fetch_or_parse_failed"
                logger.warning("indexing/history failed host=%s", host, exc_info=True)
            try:
                events = (await client.search_events_history(
                    user_id, host_id, date_from=(day - timedelta(days=7)).isoformat(), date_to=(day + timedelta(days=1)).isoformat(),
                )).data
                payload["events"] = events
                appeared, excluded = _events_counts(_history_for_day(events, day))
            except Exception:
                payload["errors"]["events/history"] = "fetch_or_parse_failed"
                logger.warning("events/history failed host=%s", host, exc_info=True)
            if include_sitemaps:
                try:
                    sm = (await client.sitemaps(user_id, host_id)).data
                    payload["sitemaps"] = sm
                    children = await _all_sitemap_children(client, user_id, host_id, sm)
                    payload["sitemap_children"] = children
                    sitemap_errors = _sitemap_error_count(sm) + _sitemap_error_count({"sitemaps": children})
                except Exception:
                    payload["errors"]["sitemaps"] = "fetch_or_parse_failed"
                    logger.warning("sitemaps failed host=%s", host, exc_info=True)

            if not include_sitemaps:
                previous_raw = await db.scalar(select(WebmasterIndexingDaily.raw_json).where(
                    WebmasterIndexingDaily.host == host, WebmasterIndexingDaily.day == day))
                for key in ("sitemaps", "sitemap_children"):
                    if previous_raw and key in previous_raw:
                        payload[key] = previous_raw[key]

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
                    **({"sitemap_errors": stmt.excluded.sitemap_errors} if include_sitemaps else {}),
                    "raw_json": stmt.excluded.raw_json,
                },
            )
            await db.execute(stmt)
            await db.commit()  # release connection before the next host network calls
            stored += 1
    if alert:
        await _alerting(day)
    return stored


def _history_for_day(payload: dict, day: date) -> dict:
    """Provider dates bound timestamps, not inclusive calendar dates.

    Request [day, day+1), then retain only observations belonging to this MSK
    date. This also prevents double counting if endpoint boundary rules differ.
    """
    def on_day(point):
        try:
            ts = datetime.fromisoformat(str(point["date"]).replace("Z", "+00:00"))
            if ts.tzinfo is not None:
                ts = ts.astimezone(timezone(timedelta(hours=3)))
            return ts.date() == day
        except (KeyError, TypeError, ValueError):
            return False

    result = dict(payload)
    if "history" in result:
        result["history"] = [p for p in result["history"] or [] if on_day(p)]
    indicators = result.get("indicators")
    if isinstance(indicators, dict):
        result["indicators"] = {key: [p for p in points or [] if on_day(p)]
                                for key, points in indicators.items()}
    elif isinstance(indicators, list):
        result["indicators"] = [{**series, "history": [p for p in series.get("history", []) if on_day(p)]}
                                for series in indicators]
    return result


def _latest_value(payload: dict) -> int | None:
    """Real API has a sparse top-level history; zero is an observation too."""
    history = payload.get("history")
    if history is None:
        return _latest_indicator(payload, "SEARCHABLE")
    points = [p for p in history if p.get("value") is not None]
    return int(max(points, key=lambda p: p.get("date", ""))["value"]) if points else None


def _latest_indicator(payload: dict, name: str) -> int | None:
    indicators = payload.get("indicators") or {}
    history = indicators.get(name, []) if isinstance(indicators, dict) else next(
        (s.get("history", []) for s in indicators if s.get("indicator") == name), [])
    return _latest_value({"history": history})


def _http_classes(codes: dict) -> tuple:
    # An empty provider response is unknown, never four reassuring zeros.
    if not codes:
        return None, None, None, None
    return tuple(sum(v for k, v in codes.items() if k.removeprefix("HTTP_").startswith(c))
                 for c in ("2", "3", "4", "5"))


def _events_counts(payload: dict) -> tuple[int | None, int | None]:
    indicators = payload.get("indicators") or {}
    if isinstance(indicators, dict):
        series = indicators.items()
    else:
        series = ((s.get("event") or s.get("indicator", ""), s.get("history") or [s])
                  for s in indicators)
    appeared = excluded = None
    for event, points in series:
        values = [int(p["value"]) for p in points if p.get("value") is not None]
        if not values:
            continue
        if "APPEAR" in event or event == "ADDED_TO_SEARCH":
            appeared = sum(values)
        elif "REMOV" in event:
            excluded = sum(values)
    return appeared, excluded


def _sitemap_error_count(payload: dict) -> int:
    n = 0
    for item in payload.get("sitemaps") or payload.get("user_added_sitemaps") or []:
        errors = item.get("errors_count", item.get("error_count", item.get("problems", 0)))
        n += len(errors) if isinstance(errors, list) else int(errors or 0)
        if not errors and item.get("last_access_error"):
            n += 1
    return n


async def _all_sitemap_children(client, user_id, host_id, payload) -> list[dict]:
    """Fetch every child page, with a bounded traversal and no repeated IDs."""
    queue = list(payload.get("sitemaps") or [])
    seen = {s.get("sitemap_id") for s in queue}
    children = []
    requests = 0
    for parent in queue:
        expected = int(parent.get("children_count") or 0)
        offset = 0
        cursor = None
        while offset < expected:
            requests += 1
            if requests > 100:
                raise ValueError("sitemap children traversal exceeded safety limit")
            data = (await client.sitemap_children(user_id, host_id, parent["sitemap_id"],
                                                 **({"limit": 100, "from": cursor} if cursor else {"limit": 100}))).data
            batch = data.get("sitemaps") or []
            if not batch:
                raise ValueError("incomplete sitemap children response")
            for child in batch:
                sid = child.get("sitemap_id")
                if sid not in seen:
                    seen.add(sid)
                    children.append(child)
                    queue.append(child)
            next_cursor = batch[-1].get("sitemap_id")
            if not next_cursor or next_cursor == cursor:
                raise ValueError("sitemap pagination did not advance")
            cursor = next_cursor
            offset += len(batch)
    return children


async def _alerting(day: date) -> None:
    for host_id in _report_host_ids():
        await _alert_host(day, _host_label(host_id))


async def _alert_host(day: date, host: str) -> None:
    from app.services.analytics_alerts import _alert

    async with analytics_session() as db:
        row = (await db.execute(
            select(WebmasterIndexingDaily).where(
                WebmasterIndexingDaily.host == host,
                WebmasterIndexingDaily.day == day,
            )
        )).scalar_one_or_none()
        if row is None:
            return
        # History is sparse and delayed: alert on stale observations, not every empty day.
        for field, max_age in ((WebmasterIndexingDaily.in_search, 7),
                               (WebmasterIndexingDaily.crawled_2xx, 3)):
            last_day = await db.scalar(select(func.max(WebmasterIndexingDaily.day)).where(
                WebmasterIndexingDaily.host == host, WebmasterIndexingDaily.day <= day,
                field.isnot(None)))
            if last_day is None or (day - last_day).days > max_age:
                await _alert(f"webmaster_data_missing:{host}:{field.key}",
                             f"{host}: нет свежего наблюдения {field.key}; последнее {last_day}. "
                             "Отсутствие данных не означает ноль.")
        if (row.crawled_5xx or 0) > 20:
            await _alert(
                f"webmaster_5xx:{host}",
                f"{host}, Вебмастер: {row.crawled_5xx} ответов 5xx роботу за {day}.",
            )
        if (row.sitemap_errors or 0) > 0:
            await _alert(
                f"webmaster_sitemap_errors:{host}",
                f"{host}, Вебмастер: {row.sitemap_errors} ошибок sitemap за {day}.",
            )
        prev = (await db.execute(
            select(WebmasterIndexingDaily).where(
                WebmasterIndexingDaily.host == row.host,
                WebmasterIndexingDaily.day < day,
                WebmasterIndexingDaily.in_search.isnot(None),
            ).order_by(WebmasterIndexingDaily.day.desc()).limit(1)
        )).scalar_one_or_none()
        if (
            prev and prev.in_search and row.in_search is not None
            and prev.in_search > 0
            and row.in_search < prev.in_search * 0.95
        ):
            await _alert(
                f"webmaster_in_search_drop:{host}",
                f"{host}: В поиске {row.in_search} против {prev.in_search} за {prev.day} "
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
                    f"webmaster_crawl_drop:{host}",
                    f"{host}: Обход 2xx {row.crawled_2xx} против среднего {round(avg)} за неделю.",
                )


async def webmaster_indexing_daily_job() -> None:
    try:
        end = today_msk() - timedelta(days=1)
        n = 0
        for offset in range(6, -1, -1):
            n += await sync_webmaster_indexing_daily(end - timedelta(days=offset), alert=offset == 0, include_sitemaps=offset == 0)
        logger.info("Webmaster indexing daily: %d host-day rows", n)
    except Exception:
        logger.exception("Webmaster indexing daily failed")

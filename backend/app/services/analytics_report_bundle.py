"""Сбор first-party + складского слоя для дневного PDF-отчёта.

Запуск (из контейнера backend):
    python -m app.services.analytics_report_bundle 2026-07-03

Печатает JSON в stdout: инвентаризация датасета, события фронта, поведение,
склад Метрики (Logs API, снапшоты, фразы, страницы), гипотезы.
"""
from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, select

from app.database import async_session
from app.models import (
    BehaviorEvent,
    FrontendEvent,
    Hypothesis,
    MetrikaDailyPageMetric,
    MetrikaReportSnapshot,
    MetrikaSearchPhrase,
    RawMetrikaVisit,
    User,
)
from app.services.dataset_inventory import build_inventory

_DOWNLOAD_EVENTS = {
    "download_csv", "download_excel", "chart_image_download",
    "compare_image_download", "compare_csv_download", "download_limit",
}
_ERROR_EVENTS = {"error_reload", "api_retry", "api_error"}


def _day_bounds(d: date) -> tuple[datetime, datetime]:
    start = datetime.combine(d, time.min)
    return start, start + timedelta(days=1)


def _snapshot_to_rows(response_json: dict | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in (response_json or {}).get("data", []):
        dims = row.get("dimensions") or []
        metrics = row.get("metrics") or []
        name = str(dims[0].get("name")) if dims else "?"
        rows.append({
            "name": name,
            "id": dims[0].get("id") if dims else None,
            "visits": int(metrics[0] or 0) if len(metrics) > 0 else 0,
            "users": int(metrics[1] or 0) if len(metrics) > 1 else 0,
        })
    rows.sort(key=lambda x: x["visits"], reverse=True)
    return rows


async def build_day_bundle(d: date, period_start: date | None = None) -> dict[str, Any]:
    start, end = _day_bounds(d)
    bundle: dict[str, Any] = {"day": d.isoformat()}

    async with async_session() as db:
        bundle["inventory"] = await build_inventory(db)

        # --- Frontend (бизнес-события) --------------------------------------
        ev_rows = (await db.execute(
            select(
                FrontendEvent.event_name,
                FrontendEvent.params_json,
                FrontendEvent.url,
                FrontendEvent.authed,
                FrontendEvent.user_id,
                FrontendEvent.session_id_hash,
            ).where(FrontendEvent.occurred_at >= start, FrontendEvent.occurred_at < end)
        )).all()

        by_name: Counter[str] = Counter()
        indicators: Counter[str] = Counter()
        regions: Counter[str] = Counter()
        searches: Counter[str] = Counter()
        zero_search: Counter[str] = Counter()
        downloads: Counter[str] = Counter()
        errors: Counter[str] = Counter()
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
                q = str(params.get("q") or "").strip()
                if q:
                    searches[q] += 1
                    try:
                        if int(params.get("results", -1)) == 0:
                            zero_search[q] += 1
                    except (TypeError, ValueError):
                        pass
            slug = params.get("region")
            if not slug and url:
                u = str(url)
                for marker in ("/region/", "/regions/"):
                    if marker in u:
                        slug = u.split(marker, 1)[1].split("/")[0].split("?")[0]
                        break
            if slug:
                regions[str(slug)] += 1

        search_rows = [
            {
                "query": q,
                "count": n,
                "zero_results": zero_search.get(q, 0),
            }
            for q, n in searches.most_common()
        ]
        bundle["frontend"] = {
            "total": sum(by_name.values()),
            "by_name": [{"name": k, "count": v} for k, v in by_name.most_common()],
            "search_queries": search_rows,
            "downloads": [{"name": k, "count": v} for k, v in downloads.most_common()],
            "errors": [{"name": k, "count": v} for k, v in errors.most_common()],
            "indicators": [{"code": k, "count": v} for k, v in indicators.most_common()],
            "regions": [{"slug": k, "count": v} for k, v in regions.most_common()],
            "by_audience": events_by_audience,
            "downloads_by_audience": downloads_by_audience,
            "audience": {
                "authed_active": len(authed_user_ids),
                "guest_sessions": len(guest_sessions),
            },
        }

        # --- Behavior (сырой поток) -----------------------------------------
        b_by_type = dict((await db.execute(
            select(BehaviorEvent.event_type, func.count())
            .where(BehaviorEvent.occurred_at >= start, BehaviorEvent.occurred_at < end)
            .group_by(BehaviorEvent.event_type)
        )).all())

        pageviews = [
            {"page": p, "count": int(n)}
            for p, n in (await db.execute(
                select(BehaviorEvent.page, func.count())
                .where(BehaviorEvent.occurred_at >= start, BehaviorEvent.occurred_at < end,
                       BehaviorEvent.event_type == "pageview")
                .group_by(BehaviorEvent.page)
                .order_by(func.count().desc())
            )).all()
            if p
        ]
        clicks = [
            {"element": path or "—", "text": (text or "")[:80], "count": int(n)}
            for path, text, n in (await db.execute(
                select(BehaviorEvent.element_path, BehaviorEvent.element_text, func.count())
                .where(BehaviorEvent.occurred_at >= start, BehaviorEvent.occurred_at < end,
                       BehaviorEvent.event_type == "click")
                .group_by(BehaviorEvent.element_path, BehaviorEvent.element_text)
                .order_by(func.count().desc())
            )).all()
        ]
        dead_clicks = [
            {"element": path or "—", "text": (text or "")[:80], "count": int(n)}
            for path, text, n in (await db.execute(
                select(BehaviorEvent.element_path, BehaviorEvent.element_text, func.count())
                .where(BehaviorEvent.occurred_at >= start, BehaviorEvent.occurred_at < end,
                       BehaviorEvent.event_type == "click", BehaviorEvent.is_dead.is_(True))
                .group_by(BehaviorEvent.element_path, BehaviorEvent.element_text)
                .order_by(func.count().desc())
            )).all()
        ]
        rage_clicks = [
            {"page": page or "—", "element": path or "—", "count": int(n)}
            for page, path, n in (await db.execute(
                select(BehaviorEvent.page, BehaviorEvent.element_path, func.count())
                .where(BehaviorEvent.occurred_at >= start, BehaviorEvent.occurred_at < end,
                       BehaviorEvent.event_type == "click", BehaviorEvent.is_rage.is_(True))
                .group_by(BehaviorEvent.page, BehaviorEvent.element_path)
                .order_by(func.count().desc())
            )).all()
        ]
        dwell_rows = (await db.execute(
            select(BehaviorEvent.page, BehaviorEvent.params_json)
            .where(BehaviorEvent.occurred_at >= start, BehaviorEvent.occurred_at < end,
                   BehaviorEvent.event_type == "dwell")
        )).all()
        dwell_by_page: dict[str, list[tuple[float, float]]] = {}
        for page, params in dwell_rows:
            p = params or {}
            if page and isinstance(p.get("ms"), (int, float)):
                dwell_by_page.setdefault(page, []).append((float(p["ms"]), float(p.get("scroll_pct") or 0)))
        dwell = [
            {
                "page": page,
                "visits": len(vals),
                "avg_seconds": round(sum(v[0] for v in vals) / len(vals) / 1000, 1),
                "avg_scroll_pct": round(sum(v[1] for v in vals) / len(vals)),
            }
            for page, vals in sorted(dwell_by_page.items(), key=lambda kv: -len(kv[1]))
        ]
        copy_rows = (await db.execute(
            select(BehaviorEvent.params_json)
            .where(BehaviorEvent.occurred_at >= start, BehaviorEvent.occurred_at < end,
                   BehaviorEvent.event_type == "copy")
        )).scalars().all()
        copy_counter: Counter[str] = Counter()
        for p in copy_rows:
            t = (p or {}).get("text")
            if t:
                copy_counter[str(t)[:120]] += 1
        copied = [{"text": t, "count": n} for t, n in copy_counter.most_common()]

        bundle["behavior"] = {
            "by_type": b_by_type,
            "pageviews": pageviews,
            "clicks": clicks,
            "dead_clicks": dead_clicks,
            "rage_clicks": rage_clicks,
            "dwell": dwell,
            "copied": copied,
        }

        # --- Склад Метрики --------------------------------------------------
        wh: dict[str, Any] = {}
        snap_rows = (await db.execute(
            select(MetrikaReportSnapshot.report_type, MetrikaReportSnapshot.response_json)
            .where(MetrikaReportSnapshot.date_from == d, MetrikaReportSnapshot.date_to == d,
                   MetrikaReportSnapshot.report_type.in_(
                       ["traffic_sources", "search_engines", "referrers", "ad_campaigns"]))
            .order_by(MetrikaReportSnapshot.captured_at)
        )).all()
        for report_type, response_json in snap_rows:
            wh[report_type] = _snapshot_to_rows(response_json)

        wh["search_phrases"] = [
            {
                "phrase": p,
                "search_engine": e,
                "landing_url": u,
                "visits": int(v),
            }
            for p, e, u, v in (await db.execute(
                select(
                    MetrikaSearchPhrase.phrase,
                    MetrikaSearchPhrase.search_engine,
                    MetrikaSearchPhrase.landing_url,
                    MetrikaSearchPhrase.visits,
                )
                .where(MetrikaSearchPhrase.date == d)
                .order_by(MetrikaSearchPhrase.visits.desc())
            )).all()
        ]
        wh["page_metrics"] = [
            {
                "url": url,
                "source": src,
                "visits": int(v),
                "users": int(u),
                "pageviews": int(pv),
            }
            for url, src, v, u, pv in (await db.execute(
                select(
                    MetrikaDailyPageMetric.url,
                    MetrikaDailyPageMetric.source,
                    MetrikaDailyPageMetric.visits,
                    MetrikaDailyPageMetric.users,
                    MetrikaDailyPageMetric.pageviews,
                )
                .where(MetrikaDailyPageMetric.date == d)
                .order_by(MetrikaDailyPageMetric.visits.desc())
            )).all()
        ]

        visits_total = await db.scalar(
            select(func.count(RawMetrikaVisit.id)).where(RawMetrikaVisit.visit_date == d)
        ) or 0
        raw: dict[str, Any] = {"total": visits_total}
        if visits_total:
            raw["by_source"] = dict((await db.execute(
                select(RawMetrikaVisit.traffic_source, func.count())
                .where(RawMetrikaVisit.visit_date == d)
                .group_by(RawMetrikaVisit.traffic_source)
            )).all())
            raw["phrases"] = [
                {"phrase": p, "search_engine": e, "visits": int(n)}
                for p, e, n in (await db.execute(
                    select(RawMetrikaVisit.search_phrase, RawMetrikaVisit.search_engine, func.count())
                    .where(RawMetrikaVisit.visit_date == d,
                           RawMetrikaVisit.search_phrase.isnot(None),
                           RawMetrikaVisit.search_phrase != "")
                    .group_by(RawMetrikaVisit.search_phrase, RawMetrikaVisit.search_engine)
                    .order_by(func.count().desc())
                )).all()
            ]
            raw["start_urls"] = [
                {"url": u, "visits": int(n)}
                for u, n in (await db.execute(
                    select(RawMetrikaVisit.start_url, func.count())
                    .where(RawMetrikaVisit.visit_date == d, RawMetrikaVisit.start_url.isnot(None))
                    .group_by(RawMetrikaVisit.start_url)
                    .order_by(func.count().desc())
                )).all()
            ]
            raw["referrers"] = [
                {"referer": r, "visits": int(n)}
                for r, n in (await db.execute(
                    select(RawMetrikaVisit.referer, func.count())
                    .where(RawMetrikaVisit.visit_date == d, RawMetrikaVisit.referer.isnot(None),
                           RawMetrikaVisit.referer != "")
                    .group_by(RawMetrikaVisit.referer)
                    .order_by(func.count().desc())
                )).all()
            ]
        wh["raw_visits"] = raw
        bundle["warehouse"] = wh

        # --- Гипотезы -------------------------------------------------------
        hy_rows = (await db.execute(
            select(Hypothesis.statement, Hypothesis.verdict, Hypothesis.confidence,
                   Hypothesis.updated_at)
            .order_by(Hypothesis.updated_at.desc())
        )).all()
        bundle["hypotheses"] = [
            {
                "statement": s,
                "verdict": None if v is None else bool(v),
                "confidence": float(c) if c is not None else None,
                "updated_at": (u.isoformat() if u else None),
            }
            for s, v, c, u in hy_rows
        ]

        new_users = (await db.execute(
            select(User).where(User.created_at >= start, User.created_at < end)
        )).scalars().all()
        bundle["users"] = {
            "total": await db.scalar(select(func.count(User.id))) or 0,
            "new": len(new_users),
            "new_names": [u.display_name or "—" for u in new_users[:30]],
        }

        if period_start and period_start <= d:
            pstart = datetime.combine(period_start, time.min)
            pend = end
            bundle["period"] = {
                "from": period_start.isoformat(),
                "to": d.isoformat(),
            }
            search_counter: Counter[str] = Counter()
            zero_counter: Counter[str] = Counter()
            for params in (await db.execute(
                select(FrontendEvent.params_json)
                .where(
                    FrontendEvent.event_name == "search_query",
                    FrontendEvent.occurred_at >= pstart,
                    FrontendEvent.occurred_at < pend,
                )
            )).scalars().all():
                p = params or {}
                q = str(p.get("q") or "").strip()
                if not q:
                    continue
                search_counter[q] += 1
                try:
                    if int(p.get("results", -1)) == 0:
                        zero_counter[q] += 1
                except (TypeError, ValueError):
                    pass
            bundle["period"]["internal_search"] = [
                {"query": q, "count": n, "zero_results": zero_counter.get(q, 0)}
                for q, n in search_counter.most_common()
            ]
            bundle["period"]["warehouse_phrases"] = [
                {"phrase": p, "search_engine": e, "visits": int(n)}
                for p, e, n in (await db.execute(
                    select(RawMetrikaVisit.search_phrase, RawMetrikaVisit.search_engine, func.count())
                    .where(
                        RawMetrikaVisit.visit_date >= period_start,
                        RawMetrikaVisit.visit_date <= d,
                        RawMetrikaVisit.search_phrase.isnot(None),
                        RawMetrikaVisit.search_phrase != "",
                    )
                    .group_by(RawMetrikaVisit.search_phrase, RawMetrikaVisit.search_engine)
                    .order_by(func.count().desc())
                )).all()
            ]
            bundle["period"]["metrika_search_phrases"] = [
                {
                    "phrase": p,
                    "search_engine": e,
                    "visits": int(v),
                    "days_seen": int(days),
                }
                for p, e, v, days in (await db.execute(
                    select(
                        MetrikaSearchPhrase.phrase,
                        MetrikaSearchPhrase.search_engine,
                        func.sum(MetrikaSearchPhrase.visits),
                        func.count(func.distinct(MetrikaSearchPhrase.date)),
                    )
                    .where(MetrikaSearchPhrase.date >= period_start, MetrikaSearchPhrase.date <= d)
                    .group_by(MetrikaSearchPhrase.phrase, MetrikaSearchPhrase.search_engine)
                    .order_by(func.sum(MetrikaSearchPhrase.visits).desc())
                )).all()
            ]

    return bundle


def main() -> None:
    d = date.fromisoformat(sys.argv[1])
    period_start = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else None
    bundle = asyncio.run(build_day_bundle(d, period_start=period_start))
    print(json.dumps(bundle, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()

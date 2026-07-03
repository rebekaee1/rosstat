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

from app.core.cache import get_state_redis
from app.database import async_session
from app.models import (
    AuthAudit,
    BehaviorEvent,
    Consent,
    EmailCredential,
    FetchLog,
    FrontendEvent,
    IndicatorData,
    OAuthIdentity,
    User,
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


def _day_bounds(d: date) -> tuple[datetime, datetime]:
    start = datetime.combine(d, time.min)
    return start, start + timedelta(days=1)


async def build_snapshot(d: date) -> dict[str, Any]:
    """Собрать снапшот дня из БД. Чистое чтение, без побочных эффектов."""
    start, end = _day_bounds(d)
    snap: dict[str, Any] = {"date": d.isoformat()}

    async with async_session() as db:
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

        # --- ETL ------------------------------------------------------------
        etl_rows = (await db.execute(
            select(FetchLog.status, func.count(), func.coalesce(func.sum(FetchLog.records_added), 0))
            .where(FetchLog.started_at >= start, FetchLog.started_at < end)
            .group_by(FetchLog.status)
        )).all()
        failed_codes = (await db.execute(
            select(func.distinct(FetchLog.indicator_id))
            .where(FetchLog.started_at >= start, FetchLog.started_at < end, FetchLog.status == "error")
        )).scalars().all()
        snap["etl"] = {
            "by_status": {s: {"runs": n, "records": int(r)} for s, n, r in etl_rows},
            "failed_indicator_ids": [int(i) for i in failed_codes][:20],
        }

        # --- Приток данных ---------------------------------------------------
        # (у region_data нет created_at — региональный приток пришёл бы из ETL-логов)
        new_points = await db.scalar(
            select(func.count(IndicatorData.id))
            .where(IndicatorData.created_at >= start, IndicatorData.created_at < end)
        ) or 0
        snap["data"] = {"new_points": new_points}

    return snap


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

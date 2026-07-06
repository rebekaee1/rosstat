"""Единый слой витрин аналитики (ADR-0010, этап 2.5 плана «Аналитика 2.0»).

Одна точка истины для каждой цифры: витрина = одна функция, потребители —
BI-дашборд (/admin/bi), Пульс-снапшот (LLM-контекст) и телеграм-бот. Раньше
pulse.py и admin_bi.py считали скачивания/поиски/dwell каждый по-своему —
цифры могли расходиться; теперь общие примитивы и витрины живут здесь.

Слои данных:
- server_sessions   — серверные сессии (30-мин правило) → воронка, вовлечение;
- daily_* rollup'ы  — трафик Метрики/цели/страницы без полного скана сырья;
- behavior_*        — сырьё для блочной аналитики, vitals, ошибок, гео;
- metrika_goals     — словарь целей: числа goals_json становятся именами.
"""
from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.bi_targets import NORTH_STAR_MILESTONES, TARGETS, next_milestone, status_for
from app.models import (
    BehaviorEvent,
    BehaviorSession,
    DailyGoal,
    DailyPage,
    DailyTraffic,
    DirectCost,
    FrontendEvent,
    IdentityLink,
    MetrikaGoal,
    RawMetrikaVisit,
    ServerSession,
    User,
)
from app.services.goal_taxonomy import (
    TIER_MACRO,
    TIER_MICRO,
    tier_for_event,
    weight_for_event,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Общие примитивы (single source: admin_bi/pulse/rollups импортируют отсюда)
# ---------------------------------------------------------------------------

# ym:s:deviceCategory в Logs API — числовой код, не слово.
METRIKA_DEVICE = {"1": "desktop", "2": "mobile", "3": "tablet", "4": "tv"}

# Машинные ярлыки Logs API → канонические имена нашего ua_parser: без этого
# сверка «наш слой vs Метрика» не сопоставляется по ключам.
METRIKA_BROWSER = {
    "yandex_browser": "Яндекс.Браузер",
    "yandexsearch": "Яндекс.Браузер",
    "yandexbrowsercorp": "Яндекс.Браузер",
    "chrome": "Chrome",
    "chromemobile": "Chrome",
    "safari": "Safari",
    "safari_mobile": "Safari",
    "mobile_safari": "Safari",
    "firefox": "Firefox",
    "firefox_mobile": "Firefox",
    "edge": "Edge",
    "edgin": "Edge",
    "opera": "Opera",
    "opera_mobile": "Opera",
    "samsung_internet": "Samsung Internet",
    "android_browser": "Android WebView",
    "mi_browser": "Mi Browser",
    "huawei_browser": "Huawei Browser",
}
METRIKA_OS = {
    "windows": "Windows",
    "android": "Android",
    "ios": "iOS",
    "ios_double": "iOS",
    "mac_os": "macOS",
    "macos": "macOS",
    "gnu_linux": "Linux",
    "linux": "Linux",
}

# Классификация путей по продуктовым разделам (порядок важен).
SECTION_RULES = [
    ("/indicator/", "Карточки индикаторов"),
    ("/region/", "Карточки регионов"),
    ("/regions", "Каталог и карта регионов"),
    ("/region-rating", "Рейтинги регионов"),
    ("/region-vs", "Сравнения регионов"),
    ("/calculator", "Калькуляторы"),
    ("/compare", "Сравнение индикаторов"),
    ("/category/", "Категории"),
    ("/calendar", "Календарь"),
    ("/today", "Страницы «сегодня»"),
    ("/about", "О проекте"),
    ("/methodology", "Методология"),
    ("/admin", "Служебные"),
]


def page_section(path: str) -> str:
    if not path or path == "/":
        return "Главная"
    for prefix, name in SECTION_RULES:
        if path.startswith(prefix):
            return name
    return "Прочее"


def visit_field(v: RawMetrikaVisit, key: str) -> str:
    return ((v.raw_json or {}).get(key) or "").strip()


def visit_device(v: RawMetrikaVisit) -> str:
    raw = visit_field(v, "ym:s:deviceCategory")
    return METRIKA_DEVICE.get(raw, raw)


def visit_browser(v: RawMetrikaVisit) -> str:
    raw = visit_field(v, "ym:s:browser").lower()
    return METRIKA_BROWSER.get(raw, raw)


def visit_os(v: RawMetrikaVisit) -> str:
    raw = visit_field(v, "ym:s:operatingSystemRoot").lower()
    return METRIKA_OS.get(raw, raw)


def visit_goal_ids(v: RawMetrikaVisit) -> list[int]:
    """Список id целей визита. goals_json: {"goals": "[123,456]"} | list | str."""
    gj = v.goals_json
    if not gj:
        return []
    if isinstance(gj, dict):
        gj = gj.get("goals")
    if isinstance(gj, str):
        try:
            gj = json.loads(gj)
        except (ValueError, TypeError):
            return []
    if isinstance(gj, (list, tuple)):
        out = []
        for x in gj:
            try:
                out.append(int(x))
            except (TypeError, ValueError):
                continue
        return out
    return []


def visit_has_goals(v: RawMetrikaVisit) -> bool:
    """Истинная проверка «визит достиг цели» (инцидент 91–100% 2026-07-05)."""
    return bool(visit_goal_ids(v))


def _since(days: int) -> datetime:
    return datetime.utcnow() - timedelta(days=days)


def _pctl(values: list[float], p: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    idx = min(len(xs) - 1, max(0, int(round(p * (len(xs) - 1)))))
    return round(xs[idx], 1)


# ---------------------------------------------------------------------------
# Витрина: дерево метрик (North Star + 4 драйвера)
# ---------------------------------------------------------------------------

async def mart_metric_tree(db: AsyncSession, days: int = 30) -> dict[str, Any]:
    """Экран-главная BI: North Star (визиты/день) против траектории к 10k,
    4 драйвера с таргетами из bi_targets.py и статус-цветом."""
    since_day = _since(days).date()

    # North Star: визиты Метрики по дням (наши сессии — сверка ниже).
    traffic = (await db.execute(
        select(DailyTraffic.day, func.sum(DailyTraffic.visits))
        .where(DailyTraffic.day >= since_day)
        .group_by(DailyTraffic.day).order_by(DailyTraffic.day)
    )).all()
    visits_by_day = [{"day": d.isoformat(), "visits": int(n or 0)} for d, n in traffic]
    last7 = [x["visits"] for x in visits_by_day[-7:]]
    prev7 = [x["visits"] for x in visits_by_day[-14:-7]]
    ns_value = round(sum(last7) / max(len(last7), 1), 1)
    ns_prev = round(sum(prev7) / max(len(prev7), 1), 1) if prev7 else 0.0

    # Каналы за 7 дней (уровень 2 драйвера «Привлечение»).
    ch_rows = (await db.execute(
        select(DailyTraffic.channel, func.sum(DailyTraffic.visits))
        .where(DailyTraffic.day >= _since(7).date())
        .group_by(DailyTraffic.channel)
    )).all()
    channels = {ch or "direct": int(n or 0) for ch, n in ch_rows}
    ch_total = sum(channels.values()) or 1

    # Собственные серверные сессии окна: вовлечение и конверсия.
    sess = (await db.execute(
        select(
            func.count().label("total"),
            func.sum(case((ServerSession.is_engaged.is_(True), 1), else_=0)).label("engaged"),
            func.sum(case((ServerSession.micro_goals > 0, 1), else_=0)).label("micro"),
            func.sum(case((ServerSession.macro_goals > 0, 1), else_=0)).label("macro"),
        ).where(ServerSession.day >= _since(7).date(), ServerSession.is_bot.is_(False))
    )).one()
    total_s = int(sess.total or 0)
    engaged = int(sess.engaged or 0)
    micro_s = int(sess.micro or 0)
    macro_s = int(sess.macro or 0)
    engagement_rate = engaged / total_s if total_s else 0.0
    micro_rate = micro_s / engaged if engaged else 0.0
    macro_rate = macro_s / engaged if engaged else 0.0

    # Удержание 7 дней: посетители с >1 днём активности за последние 14 дней.
    ret_rows = (await db.execute(
        select(ServerSession.visitor_id_hash, func.count(func.distinct(ServerSession.day)))
        .where(ServerSession.day >= _since(14).date(), ServerSession.is_bot.is_(False))
        .group_by(ServerSession.visitor_id_hash)
    )).all()
    visitors_n = len(ret_rows)
    returned = sum(1 for _, d in ret_rows if int(d or 0) > 1)
    retention = returned / visitors_n if visitors_n else 0.0

    search_share = channels.get("search", 0) / ch_total

    def node(key: str, label: str, value: float, target: float, fmt: str, detail: dict) -> dict:
        return {
            "key": key, "label": label, "value": value, "target": target,
            "format": fmt, "status": status_for(value, target), "detail": detail,
        }

    return {
        "north_star": {
            "label": "Визиты в день (среднее за 7 дней)",
            "value": ns_value,
            "prev7": ns_prev,
            "wow_pct": round((ns_value - ns_prev) / ns_prev * 100, 1) if ns_prev else None,
            "milestone": next_milestone(ns_value),
            "milestones": NORTH_STAR_MILESTONES,
            "target_final": 10_000,
            "status": status_for(ns_value, TARGETS["visits_per_day"]),
            "series": visits_by_day,
        },
        "drivers": [
            node("acquisition", "Привлечение", round(ns_value, 1), TARGETS["visits_per_day"], "visits", {
                "channels": channels,
                "search_share": round(search_share, 3),
                "search_share_target": TARGETS["acquisition_search_share"],
            }),
            node("engagement", "Вовлечение", round(engagement_rate * 100, 1), TARGETS["engagement_rate"] * 100, "pct", {
                "sessions": total_s, "engaged": engaged,
            }),
            node("conversion", "Конверсия", round(micro_rate * 100, 2), TARGETS["micro_conversion_rate"] * 100, "pct", {
                "micro_rate_pct": round(micro_rate * 100, 2),
                "macro_rate_pct": round(macro_rate * 100, 2),
                "macro_target_pct": TARGETS["macro_conversion_rate"] * 100,
                "micro_sessions": micro_s, "macro_sessions": macro_s,
            }),
            node("retention", "Удержание", round(retention * 100, 1), TARGETS["retention_7d"] * 100, "pct", {
                "visitors_14d": visitors_n, "returned": returned,
            }),
        ],
    }


# ---------------------------------------------------------------------------
# Витрина: истинная воронка (собственная realtime + Метрика-сверка)
# ---------------------------------------------------------------------------

async def mart_own_funnel(db: AsyncSession, days: int = 30) -> dict[str, Any]:
    """Собственная воронка на серверных сессиях: сессия → вовлечён →
    микро-цель → макро-цель. Реалтайм (сессионизация каждые 15 мин)."""
    since_day = _since(days).date()
    row = (await db.execute(
        select(
            func.count().label("sessions"),
            func.sum(case((ServerSession.is_engaged.is_(True), 1), else_=0)).label("engaged"),
            func.sum(case((ServerSession.micro_goals > 0, 1), else_=0)).label("micro"),
            func.sum(case((ServerSession.macro_goals > 0, 1), else_=0)).label("macro"),
            func.sum(case((ServerSession.is_bot.is_(True), 1), else_=0)).label("bots"),
        ).where(ServerSession.day >= since_day)
    )).one()
    sessions = int(row.sessions or 0) - int(row.bots or 0)
    return {
        "source": "own",
        "steps": [
            {"step": "Сессии", "count": sessions},
            {"step": "Вовлечённые", "count": int(row.engaged or 0)},
            {"step": "Микро-цель", "count": int(row.micro or 0)},
            {"step": "Макро-цель", "count": int(row.macro or 0)},
        ],
        "bots_excluded": int(row.bots or 0),
    }


async def mart_metrika_funnel(db: AsyncSession, days: int = 30) -> dict[str, Any]:
    """Истинная конверсия Метрики: «достиг цели» = только macro/micro цели
    по словарю metrika_goals (раньше целью считалась любая из 92, включая
    скролл и ошибку). Разложение по целям с человеческими именами."""
    goal_dict = {
        g.goal_id: g for g in (await db.execute(select(MetrikaGoal))).scalars()
    }
    business_ids = {
        gid for gid, g in goal_dict.items() if g.tier in (TIER_MACRO, TIER_MICRO)
    }
    visits = (await db.execute(
        select(RawMetrikaVisit).where(RawMetrikaVisit.visit_date >= _since(days).date())
    )).scalars().all()

    total = len(visits)
    any_goal = 0
    business_goal = 0
    per_goal: Counter = Counter()
    for v in visits:
        ids = visit_goal_ids(v)
        if not ids:
            continue
        any_goal += 1
        hit_business = False
        for gid in ids:
            g = goal_dict.get(gid)
            label = (g.name or g.event_name or str(gid)) if g else str(gid)
            per_goal[label] += 1
            if gid in business_ids or (g and g.tier in (TIER_MACRO, TIER_MICRO)):
                hit_business = True
        if hit_business or not goal_dict:
            # без словаря (токен не настроен) фолбэк — любая цель
            business_goal += 1

    return {
        "source": "metrika",
        "visits": total,
        "visits_any_goal": any_goal,
        "visits_business_goal": business_goal,
        "conversion_pct": round(business_goal / total * 100, 2) if total else 0.0,
        "goals_dict_size": len(goal_dict),
        "by_goal": [
            {"goal": name, "visits": cnt,
             "tier": next((g.tier for g in goal_dict.values() if (g.name or g.event_name) == name), None)}
            for name, cnt in per_goal.most_common(20)
        ],
    }


# ---------------------------------------------------------------------------
# Витрина: надёжность (ошибки + vitals + api_timing + лаги)
# ---------------------------------------------------------------------------

async def mart_reliability(db: AsyncSession, days: int = 7) -> dict[str, Any]:
    since = _since(days)
    rows = (await db.execute(
        select(BehaviorEvent.event_type, BehaviorEvent.page, BehaviorEvent.params_json)
        .where(BehaviorEvent.occurred_at >= since,
               BehaviorEvent.event_type.in_(("vital", "js_error", "api_timing")))
    )).all()

    vitals: dict[str, list[float]] = defaultdict(list)
    errors: Counter = Counter()
    error_pages: Counter = Counter()
    api: dict[str, list[float]] = defaultdict(list)
    api_fail = 0
    for etype, page, params in rows:
        p = params if isinstance(params, dict) else {}
        if etype == "vital" and p.get("m") is not None:
            try:
                vitals[str(p["m"])].append(float(p.get("v") or 0))
            except (TypeError, ValueError):
                pass
        elif etype == "js_error":
            errors[(p.get("msg") or p.get("src") or "unknown")[:160]] += 1
            if page:
                error_pages[page.split("?")[0]] += 1
        elif etype == "api_timing":
            u = str(p.get("u") or "")[:120]
            try:
                api[u].append(float(p.get("ms") or 0))
            except (TypeError, ValueError):
                pass
            if not p.get("ok"):
                api_fail += 1

    # Лаг Метрики: свежесть последнего повизитного сырья.
    last_visit_ingest = await db.scalar(select(func.max(RawMetrikaVisit.ingested_at)))
    metrika_lag_h = (
        round((datetime.utcnow() - last_visit_ingest).total_seconds() / 3600, 1)
        if last_visit_ingest else None
    )

    api_all = [ms for xs in api.values() for ms in xs]
    return {
        "vitals_p75": {m: _pctl(xs, 0.75) for m, xs in vitals.items()},
        "vitals_samples": {m: len(xs) for m, xs in vitals.items()},
        "js_errors_total": int(sum(errors.values())),
        "js_errors_top": [{"error": e, "count": c} for e, c in errors.most_common(12)],
        "js_error_pages": dict(error_pages.most_common(10)),
        "api_p75_ms": _pctl(api_all, 0.75),
        "api_slowest": sorted(
            ({"endpoint": u, "p75_ms": _pctl(xs, 0.75), "calls": len(xs)} for u, xs in api.items() if len(xs) >= 3),
            key=lambda x: -(x["p75_ms"] or 0),
        )[:10],
        "api_failed_sampled": api_fail,
        "metrika_lag_hours": metrika_lag_h,
    }


# ---------------------------------------------------------------------------
# Витрина: полнота сбора (мета-мониторинг качества данных)
# ---------------------------------------------------------------------------

async def mart_collection_quality(db: AsyncSession, days: int = 7) -> dict[str, Any]:
    since = _since(days)
    sessions = (await db.execute(
        select(
            func.count().label("total"),
            func.sum(case((BehaviorSession.visitor_id_hash.isnot(None), 1), else_=0)).label("with_visitor"),
            func.sum(case((BehaviorSession.country.isnot(None), 1), else_=0)).label("with_geo"),
            func.sum(case((BehaviorSession.ym_client_id.isnot(None), 1), else_=0)).label("with_ym"),
            func.sum(case((BehaviorSession.is_webdriver.is_(True), 1), else_=0)).label("bots"),
            func.sum(case((BehaviorSession.channel.isnot(None), 1), else_=0)).label("with_channel"),
        ).where(BehaviorSession.started_at >= since)
    )).one()
    total = int(sessions.total or 0)

    def share(x) -> float | None:
        return round(int(x or 0) / total * 100, 1) if total else None

    # Покрытие SSR-страниц собственным потоком: есть ли pageview с чистых
    # SSR-маршрутов (standalone-бандл жив).
    ssr_pv = await db.scalar(
        select(func.count()).select_from(BehaviorEvent).where(
            BehaviorEvent.occurred_at >= since,
            BehaviorEvent.event_type == "pageview",
            (BehaviorEvent.page.like("/today%")
             | BehaviorEvent.page.like("/region-rating%")
             | BehaviorEvent.page.like("/region-vs%")),
        )
    ) or 0

    last_event = await db.scalar(select(func.max(BehaviorEvent.ingested_at)))
    silence_min = (
        round((datetime.utcnow() - last_event).total_seconds() / 60)
        if last_event else None
    )
    return {
        "own_sessions": total,
        "portrait_share_pct": share(sessions.total),
        "visitor_id_share_pct": share(sessions.with_visitor),
        "geo_share_pct": share(sessions.with_geo),
        "ym_bridge_share_pct": share(sessions.with_ym),
        "channel_share_pct": share(sessions.with_channel),
        "bot_share_pct": share(sessions.bots),
        "ssr_pageviews": int(ssr_pv),
        "stream_silence_minutes": silence_min,
    }


# ---------------------------------------------------------------------------
# Витрина: гео и сегментация
# ---------------------------------------------------------------------------

async def mart_geo(db: AsyncSession, days: int = 30) -> dict[str, Any]:
    since = _since(days)
    rows = (await db.execute(
        select(BehaviorSession.country, BehaviorSession.geo_region, BehaviorSession.city, func.count())
        .where(BehaviorSession.started_at >= since)
        .group_by(BehaviorSession.country, BehaviorSession.geo_region, BehaviorSession.city)
    )).all()
    countries: Counter = Counter()
    cities: Counter = Counter()
    regions: Counter = Counter()
    for country, region, city, cnt in rows:
        if country:
            countries[country] += cnt
        if region:
            regions[region] += cnt
        if city:
            cities[city] += cnt
    return {
        "countries": dict(countries.most_common(15)),
        "regions": dict(regions.most_common(20)),
        "cities": dict(cities.most_common(30)),
    }


async def mart_segments(db: AsyncSession, days: int = 30) -> dict[str, Any]:
    """Сегментация на rollup'ах: канал × устройство × новизна (визиты Метрики)."""
    since_day = _since(days).date()
    rows = (await db.execute(
        select(
            DailyTraffic.channel, DailyTraffic.device, DailyTraffic.is_new,
            func.sum(DailyTraffic.visits), func.sum(DailyTraffic.goal_visits),
            func.sum(DailyTraffic.total_duration_sec), func.sum(DailyTraffic.bounces),
        )
        .where(DailyTraffic.day >= since_day)
        .group_by(DailyTraffic.channel, DailyTraffic.device, DailyTraffic.is_new)
    )).all()
    segments = []
    for ch, dev, is_new, visits, goals, dur, bounces in rows:
        v = int(visits or 0)
        segments.append({
            "channel": ch or "direct",
            "device": dev or "unknown",
            "is_new": bool(is_new),
            "visits": v,
            "goal_visits": int(goals or 0),
            "conversion_pct": round(int(goals or 0) / v * 100, 2) if v else 0.0,
            "avg_duration_sec": round(int(dur or 0) / v) if v else 0,
            "bounce_pct": round(int(bounces or 0) / v * 100, 1) if v else 0.0,
        })
    segments.sort(key=lambda s: -s["visits"])
    return {"segments": segments}


# ---------------------------------------------------------------------------
# Витрина: блочная аналитика
# ---------------------------------------------------------------------------

async def mart_blocks(db: AsyncSession, days: int = 30) -> dict[str, Any]:
    """Что реально смотрят: время видимости [data-block] по разделам сайта.
    Блоки с высоким вниманием — расширять; с нулевым — поднимать/переделывать."""
    since = _since(days)
    rows = (await db.execute(
        select(BehaviorEvent.page, BehaviorEvent.params_json)
        .where(BehaviorEvent.occurred_at >= since, BehaviorEvent.event_type == "block_view")
    )).all()
    agg: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: {"views": 0, "ms": 0})
    for page, params in rows:
        p = params if isinstance(params, dict) else {}
        block = str(p.get("block") or "")[:80]
        if not block:
            continue
        section = page_section((page or "").split("?")[0])
        a = agg[(section, block)]
        a["views"] += 1
        a["ms"] += int(p.get("ms") or 0)
    out = [
        {
            "section": sec, "block": block, "views": a["views"],
            "avg_visible_sec": round(a["ms"] / a["views"] / 1000, 1) if a["views"] else 0,
        }
        for (sec, block), a in agg.items()
    ]
    out.sort(key=lambda x: -x["views"])
    return {"blocks": out[:60]}


# ---------------------------------------------------------------------------
# Витрина: «Что менять» — контур продуктовых решений
# ---------------------------------------------------------------------------

async def mart_page_quadrants(db: AsyncSession, days: int = 30) -> dict[str, Any]:
    """Матрица «трафик × вовлечение» по разделам: квадрант = действие
    (продвигать / тиражировать / чинить / переработать)."""
    since_day = _since(days).date()
    rows = (await db.execute(
        select(
            DailyPage.page,
            func.sum(DailyPage.views), func.sum(DailyPage.total_active_ms),
            func.sum(DailyPage.total_dwell_ms), func.sum(DailyPage.dead_clicks),
        ).where(DailyPage.day >= since_day).group_by(DailyPage.page)
    )).all()
    by_section: dict[str, dict[str, int]] = defaultdict(lambda: {"views": 0, "active_ms": 0, "dwell_ms": 0, "dead": 0})
    for page, views, active, dwell, dead in rows:
        s = by_section[page_section((page or "").split("?")[0])]
        s["views"] += int(views or 0)
        s["active_ms"] += int(active or 0)
        s["dwell_ms"] += int(dwell or 0)
        s["dead"] += int(dead or 0)

    items = []
    for name, s in by_section.items():
        if name == "Служебные":
            continue
        eng = round(s["active_ms"] / s["views"] / 1000, 1) if s["views"] else 0
        items.append({
            "section": name, "views": s["views"], "avg_active_sec": eng,
            "dead_clicks": s["dead"],
        })
    if not items:
        return {"sections": [], "median_views": 0, "median_engagement": 0}
    views_med = sorted(x["views"] for x in items)[len(items) // 2]
    eng_med = sorted(x["avg_active_sec"] for x in items)[len(items) // 2]
    for x in items:
        hi_t = x["views"] >= views_med
        hi_e = x["avg_active_sec"] >= eng_med
        x["quadrant"] = (
            "Продвигать" if (hi_t and hi_e) else
            "Тиражировать" if (not hi_t and hi_e) else
            "Чинить" if (hi_t and not hi_e) else "Переработать"
        )
    items.sort(key=lambda x: -x["views"])
    return {"sections": items, "median_views": views_med, "median_engagement": eng_med}


async def mart_feature_adoption(db: AsyncSession, days: int = 30) -> dict[str, Any]:
    """Adoption фич по бизнес-событиям + сигналы «где ждут интерактив»
    (dead-клики) и «что уносят руками» (copy — кандидаты на share/embed)."""
    since_day = _since(days).date()
    rows = (await db.execute(
        select(DailyGoal.event_name, DailyGoal.tier, func.sum(DailyGoal.count), func.sum(DailyGoal.sessions))
        .where(DailyGoal.day >= since_day)
        .group_by(DailyGoal.event_name, DailyGoal.tier)
    )).all()
    features = [
        {"event": name, "tier": tier, "count": int(cnt or 0), "sessions": int(sess or 0),
         "weight": weight_for_event(name)}
        for name, tier, cnt, sess in rows
    ]
    features.sort(key=lambda x: -x["count"])

    since = _since(days)
    copies = (await db.execute(
        select(BehaviorEvent.element_text, func.count())
        .where(BehaviorEvent.occurred_at >= since, BehaviorEvent.event_type == "copy")
        .group_by(BehaviorEvent.element_text)
        .order_by(func.count().desc()).limit(15)
    )).all()
    return {
        "features": features[:50],
        "top_copied": [{"text": t, "count": c} for t, c in copies if t],
    }


# ---------------------------------------------------------------------------
# Витрина: «Люди» — досье посетителей со скорингом
# ---------------------------------------------------------------------------

async def mart_people(db: AsyncSession, days: int = 30, limit: int = 50) -> dict[str, Any]:
    """Список посетителей по visitor_id: портрет, сессии, интересы, скоринг
    ценности (веса goal_taxonomy). Для зарегистрированных — связка через
    identity_links (история до регистрации принадлежит человеку)."""
    since_day = _since(days).date()
    since = _since(days)

    sess_rows = (await db.execute(
        select(
            ServerSession.visitor_id_hash,
            func.count().label("sessions"),
            func.sum(ServerSession.pageviews).label("pageviews"),
            func.sum(ServerSession.active_ms).label("active_ms"),
            func.sum(ServerSession.micro_goals).label("micro"),
            func.sum(ServerSession.macro_goals).label("macro"),
            func.max(ServerSession.ended_at).label("last_seen"),
            func.min(ServerSession.started_at).label("first_seen"),
        )
        .where(ServerSession.day >= since_day, ServerSession.is_bot.is_(False))
        .group_by(ServerSession.visitor_id_hash)
        .order_by(func.count().desc())
        .limit(limit * 2)
    )).all()

    visitor_ids = [r.visitor_id_hash for r in sess_rows]
    # Портрет: последняя сессия с известным visitor.
    portraits: dict[str, BehaviorSession] = {}
    if visitor_ids:
        for p in (await db.execute(
            select(BehaviorSession)
            .where(BehaviorSession.visitor_id_hash.in_(visitor_ids))
            .order_by(BehaviorSession.started_at)
        )).scalars():
            portraits[p.visitor_id_hash] = p

    # Связка с аккаунтами.
    links: dict[str, str] = {}
    if visitor_ids:
        for link in (await db.execute(
            select(IdentityLink).where(IdentityLink.visitor_id_hash.in_(visitor_ids))
        )).scalars():
            links[link.visitor_id_hash] = link.user_id

    # Интересы + скоринг по бизнес-событиям.
    interests: dict[str, Counter] = defaultdict(Counter)
    scores: dict[str, int] = defaultdict(int)
    if visitor_ids:
        ev_rows = (await db.execute(
            select(FrontendEvent.visitor_id_hash, FrontendEvent.event_name, FrontendEvent.url, func.count())
            .where(FrontendEvent.occurred_at >= since, FrontendEvent.visitor_id_hash.in_(visitor_ids))
            .group_by(FrontendEvent.visitor_id_hash, FrontendEvent.event_name, FrontendEvent.url)
        )).all()
        for vid, name, url, cnt in ev_rows:
            scores[vid] += weight_for_event(name) * int(cnt)
            if url and "/indicator/" in url:
                code = url.split("/indicator/")[-1].split("?")[0].split("/")[0]
                if code:
                    interests[vid][code] += int(cnt)

    people = []
    for r in sess_rows:
        vid = r.visitor_id_hash
        p = portraits.get(vid)
        people.append({
            "visitor": vid[:12],
            "user_id": links.get(vid),
            "sessions": int(r.sessions or 0),
            "pageviews": int(r.pageviews or 0),
            "active_min": round(int(r.active_ms or 0) / 60000, 1),
            "micro_goals": int(r.micro or 0),
            "macro_goals": int(r.macro or 0),
            "score": scores.get(vid, 0),
            "first_seen": r.first_seen.isoformat() if r.first_seen else None,
            "last_seen": r.last_seen.isoformat() if r.last_seen else None,
            "device": p.device_type if p else None,
            "browser": p.browser if p else None,
            "os": p.os if p else None,
            "city": p.city if p else None,
            "channel": p.channel if p else None,
            "interests": [c for c, _ in interests.get(vid, Counter()).most_common(5)],
        })
    people.sort(key=lambda x: -x["score"])
    return {"people": people[:limit]}


# ---------------------------------------------------------------------------
# Витрина: расходы Директа (CPA/ROI — каркас до передачи токена)
# ---------------------------------------------------------------------------

async def mart_ad_costs(db: AsyncSession, days: int = 30) -> dict[str, Any]:
    since_day = _since(days).date()
    rows = (await db.execute(
        select(DirectCost.campaign, func.sum(DirectCost.cost_rub), func.sum(DirectCost.clicks))
        .where(DirectCost.day >= since_day).group_by(DirectCost.campaign)
    )).all()
    total_cost = float(sum(float(c or 0) for _, c, _ in rows))

    # Macro-цели окна для CPA (когда появятся расходы).
    macro_goals = await db.scalar(
        select(func.sum(DailyGoal.count)).where(
            DailyGoal.day >= since_day, DailyGoal.tier == TIER_MACRO,
        )
    ) or 0
    return {
        "connected": bool(rows),
        "total_cost_rub": round(total_cost, 2),
        "campaigns": [
            {"campaign": name, "cost_rub": float(cost or 0), "clicks": int(clicks or 0)}
            for name, cost, clicks in rows
        ],
        "macro_goals_window": int(macro_goals),
        "cpa_macro_rub": round(total_cost / macro_goals, 2) if rows and macro_goals else None,
        "note": None if rows else "Коннектор Директа включится после передачи API-токена владельцем",
    }


# ---------------------------------------------------------------------------
# Полный дневной контекст для Пульс-LLM (этап 6)
# ---------------------------------------------------------------------------

async def build_marts_daily_context(db: AsyncSession) -> dict[str, Any]:
    """ВСЕ витрины marts-слоя за окно «день» — уходит в снапшот Пульса.
    Директива владельца: LLM видит всё, что есть в аналитике за день; цифра
    в дайджесте и на экране BI по построению одна и та же (одни функции)."""
    return {
        "metric_tree": await mart_metric_tree(db, days=14),
        "own_funnel_today": await mart_own_funnel(db, days=1),
        "metrika_funnel_7d": await mart_metrika_funnel(db, days=7),
        "reliability": await mart_reliability(db, days=1),
        "collection_quality": await mart_collection_quality(db, days=1),
        "geo_today": await mart_geo(db, days=1),
        "segments_7d": await mart_segments(db, days=7),
        "blocks_today": await mart_blocks(db, days=1),
        "page_quadrants_7d": await mart_page_quadrants(db, days=7),
        "feature_adoption_7d": await mart_feature_adoption(db, days=7),
        "ad_costs": await mart_ad_costs(db, days=7),
    }

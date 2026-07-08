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
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import case, func, or_, select
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
    SCORE_EVENT_CAP,
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


def visit_is_robot(v: RawMetrikaVisit) -> bool:
    """True, если Метрика-Про пометила визит как роботный (isRobotPro=1).

    Поле доступно не на всех тарифах — отсутствие в raw_json (обычный тариф,
    старые визиты до 2026-07-08) НЕ означает «не робот», означает «неизвестно»;
    вызывающий код должен это не путать с явным False."""
    return visit_field(v, "ym:s:isRobotPro") == "1"


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


async def business_goal_ids(db: AsyncSession) -> set[int]:
    """id business-tier целей Метрики (macro/micro по словарю metrika_goals).

    Этап 2б BI 2.1: «конверсия» во всех Метрика-витринах считается только по
    этим целям — авто-цели (скролл, показы, ошибки) конверсией не являются.
    """
    rows = (await db.execute(select(MetrikaGoal.goal_id, MetrikaGoal.tier))).all()
    return {int(gid) for gid, tier in rows if tier in (TIER_MACRO, TIER_MICRO)}


def visit_has_business_goal(v: RawMetrikaVisit, business_ids: set[int]) -> bool:
    """«Визит конвертировался»: достигнута хотя бы одна business-tier цель.
    Пустой словарь (токен Метрики не настроен) — фолбэк на любую цель."""
    ids = visit_goal_ids(v)
    if not business_ids:
        return bool(ids)
    return any(g in business_ids for g in ids)


def _since(days: int) -> datetime:
    return datetime.utcnow() - timedelta(days=days)


# Все витрины принимают period: Period (МСК-границы) либо int (легаси «за N
# дней») — as_period нормализует. Полуинтервал [start, end) режет datetime-
# колонки, [start_date, end_date] — day-колонки rollup'ов и Метрики.
from app.services.analytics_period import Period, as_period  # noqa: E402

# --- Самоисключение (BI 2.1, этап 3б) -------------------------------------
# Собственная активность пачкает данные: сессии владельца/админов и страницы
# /admin/* не должны попадать в поведенческие витрины, свой домен — в
# «Сайты-источники». Единая точка определения «своих» — здесь.

OWN_DOMAIN = "forecasteconomy.com"

# SQL-предикат «не служебная страница» для behavior_events-витрин.
def not_admin_page(col):
    return ~func.coalesce(col, "").like("/admin%")


async def admin_identity(db: AsyncSession) -> tuple[set[str], set[str]]:
    """(user_ids, visitor_id_hashes) владельца и админов: по admin_emails
    через способы входа + все visitor'ы этих людей из identity_links."""
    from app.config import settings
    from app.models import EmailCredential, IdentityLink, OAuthIdentity

    allowed = {e.strip().lower() for e in (settings.admin_emails or "").split(",") if e.strip()}
    if not allowed:
        return set(), set()
    user_ids: set[str] = set()  # str: identity_links/server_sessions хранят UUID строкой
    for uid, email in (await db.execute(select(EmailCredential.user_id, EmailCredential.email))).all():
        if email and email.lower() in allowed:
            user_ids.add(str(uid))
    for uid, email in (await db.execute(select(OAuthIdentity.user_id, OAuthIdentity.email))).all():
        if email and email.lower() in allowed:
            user_ids.add(str(uid))
    if not user_ids:
        return set(), set()
    visitors = set((await db.execute(
        select(IdentityLink.visitor_id_hash).where(IdentityLink.user_id.in_(user_ids))
    )).scalars())
    return user_ids, visitors


def _pctl(values: list[float], p: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    idx = min(len(xs) - 1, max(0, int(round(p * (len(xs) - 1)))))
    return round(xs[idx], 1)


# ---------------------------------------------------------------------------
# Витрина: дерево метрик (North Star + 4 драйвера)
# ---------------------------------------------------------------------------

async def mart_metric_tree(db: AsyncSession, period: Period | int = 30) -> dict[str, Any]:
    """Экран-главная BI: North Star против траектории к 10k, 4 драйвера с
    таргетами из bi_targets.py и статус-цветом. ВСЕ драйверы и их раскрытия
    считаются на выбранном периоде (BI 2.1) — цифра карточки и цифра
    разложения по построению из одного окна."""
    p = as_period(period)

    # North Star: НАШИ небот-сессии по дням (истина с BI 2.1), Метрика — в
    # сверке mart_metrika_funnel. Среднее за период против предыдущего
    # окна той же длины.
    traffic = (await db.execute(
        select(ServerSession.day, func.count(), func.count(func.distinct(ServerSession.visitor_id_hash)))
        .where(ServerSession.day >= p.start_date, ServerSession.day <= p.end_date,
               ServerSession.is_bot.is_(False), ServerSession.is_internal.is_(False))
        .group_by(ServerSession.day).order_by(ServerSession.day)
    )).all()
    visits_by_day = [
        {"day": d.isoformat(), "visits": int(n or 0), "visitors": int(u or 0)}
        for d, n, u in traffic
    ]
    span = p.days
    prev_from = p.start_date - timedelta(days=span)
    prev_to = p.start_date - timedelta(days=1)
    prev_total = await db.scalar(
        select(func.count()).select_from(ServerSession).where(
            ServerSession.day >= prev_from, ServerSession.day <= prev_to,
            ServerSession.is_bot.is_(False), ServerSession.is_internal.is_(False))
    ) or 0
    cur_total = sum(x["visits"] for x in visits_by_day)
    ns_value = round(cur_total / span, 1)
    ns_prev = round(int(prev_total) / span, 1)

    # Каналы за период (уровень 2 драйвера «Привлечение») — по НАШИМ
    # небот-сессиям (этап 2 BI 2.1); Метрика-каналы живут в mart_segments.
    ch_rows = (await db.execute(
        select(ServerSession.channel, func.count())
        .where(ServerSession.day >= p.start_date, ServerSession.day <= p.end_date,
               ServerSession.is_bot.is_(False), ServerSession.is_internal.is_(False))
        .group_by(ServerSession.channel)
    )).all()
    channels = {ch or "unknown": int(n or 0) for ch, n in ch_rows}
    ch_total = sum(channels.values()) or 1

    # Собственные серверные сессии периода: вовлечение и конверсия.
    sess = (await db.execute(
        select(
            func.count().label("total"),
            func.sum(case((ServerSession.is_engaged.is_(True), 1), else_=0)).label("engaged"),
            func.sum(case((ServerSession.micro_goals > 0, 1), else_=0)).label("micro"),
            func.sum(case((ServerSession.macro_goals > 0, 1), else_=0)).label("macro"),
        ).where(ServerSession.day >= p.start_date, ServerSession.day <= p.end_date,
                ServerSession.is_bot.is_(False), ServerSession.is_internal.is_(False))
    )).one()
    total_s = int(sess.total or 0)
    engaged = int(sess.engaged or 0)
    micro_s = int(sess.micro or 0)
    macro_s = int(sess.macro or 0)
    engagement_rate = engaged / total_s if total_s else 0.0
    micro_rate = micro_s / engaged if engaged else 0.0
    macro_rate = macro_s / engaged if engaged else 0.0

    # Удержание: посетители периода, активные более чем в одном МСК-дне
    # окна «период + такое же окно назад» (короткий период — короткая память).
    ret_rows = (await db.execute(
        select(ServerSession.visitor_id_hash, func.count(func.distinct(ServerSession.day)))
        .where(ServerSession.day >= prev_from, ServerSession.day <= p.end_date,
               ServerSession.is_bot.is_(False), ServerSession.is_internal.is_(False))
        .group_by(ServerSession.visitor_id_hash)
    )).all()
    visitors_n = len(ret_rows)
    returned = sum(1 for _, d in ret_rows if int(d or 0) > 1)
    retention = returned / visitors_n if visitors_n else 0.0

    # Раскрытие узла: классическое удержание 1/7/30 — доля вернувшихся в
    # окно после ПЕРВОГО дня (окно наблюдения 45 дней, дешёвый скан).
    day_rows = (await db.execute(
        select(ServerSession.visitor_id_hash, ServerSession.day)
        .where(ServerSession.day >= _since(45).date(), ServerSession.is_bot.is_(False), ServerSession.is_internal.is_(False))
        .distinct()
    )).all()
    days_by_visitor: dict[str, list] = defaultdict(list)
    for vid, day in day_rows:
        days_by_visitor[vid].append(day)
    ret_windows = {}
    for label, win in (("d1", 1), ("d7", 7), ("d30", 30)):
        # Когорта: первый визит достаточно давно, чтобы окно успело закрыться.
        cutoff = _since(win).date()
        cohort = [ds for ds in days_by_visitor.values() if min(ds) <= cutoff]
        came_back = sum(
            1 for ds in cohort
            if any(0 < (d - min(ds)).days <= win for d in ds)
        )
        ret_windows[label] = {
            "cohort": len(cohort),
            "returned": came_back,
            "rate_pct": round(came_back / len(cohort) * 100, 1) if cohort else 0.0,
        }

    search_share = channels.get("search", 0) / ch_total

    def node(key: str, label: str, value: float, target: float, fmt: str, detail: dict) -> dict:
        return {
            "key": key, "label": label, "value": value, "target": target,
            "format": fmt, "status": status_for(value, target), "detail": detail,
        }

    period_visitors = await db.scalar(
        select(func.count(func.distinct(ServerSession.visitor_id_hash))).where(
            ServerSession.day >= p.start_date, ServerSession.day <= p.end_date,
            ServerSession.is_bot.is_(False), ServerSession.is_internal.is_(False))
    ) or 0

    # Мягкая сверочная плашка «по Метрике: N визитов» (этап 2 BI 2.1).
    metrika_visits = await db.scalar(
        select(func.count()).select_from(RawMetrikaVisit).where(
            RawMetrikaVisit.visit_date >= p.start_date,
            RawMetrikaVisit.visit_date <= p.end_date)
    ) or 0

    # Календарь года: НАШИ небот-сессии за последние 365 дней — независимо от
    # выбранного периода (клетки всего года, палитра автоскейлится на фронте).
    year_ago = p.end_date - timedelta(days=364)
    cal_rows = (await db.execute(
        select(ServerSession.day, func.count())
        .where(ServerSession.day >= year_ago, ServerSession.day <= p.end_date,
               ServerSession.is_bot.is_(False), ServerSession.is_internal.is_(False))
        .group_by(ServerSession.day).order_by(ServerSession.day)
    )).all()
    calendar = [{"day": d.isoformat(), "visits": int(n or 0)} for d, n in cal_rows]

    return {
        "period": p.to_meta(),
        "north_star": {
            "label": f"Сессии в день ({p.label})",
            "value": ns_value,
            "sessions_total": cur_total,
            "visitors_total": int(period_visitors),
            "metrika_visits_total": int(metrika_visits),
            "prev7": ns_prev,
            "prev_label": f"{prev_from.strftime('%d.%m')}–{prev_to.strftime('%d.%m')}",
            "wow_pct": round((ns_value - ns_prev) / ns_prev * 100, 1) if ns_prev else None,
            "milestone": next_milestone(ns_value),
            "milestones": NORTH_STAR_MILESTONES,
            "target_final": 10_000,
            "status": status_for(ns_value, TARGETS["visits_per_day"]),
            "series": visits_by_day,
            "source": "own",
        },
        "calendar": calendar,
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
                "visitors_window": visitors_n, "returned": returned,
                "window_label": f"{prev_from.strftime('%d.%m')}–{p.end_date.strftime('%d.%m')}",
                "windows": ret_windows,
            }),
        ],
    }


# ---------------------------------------------------------------------------
# Витрина: истинная воронка (собственная realtime + Метрика-сверка)
# ---------------------------------------------------------------------------

async def mart_own_funnel(db: AsyncSession, period: Period | int = 30) -> dict[str, Any]:
    """Собственная воронка на серверных сессиях: сессия → вовлечён →
    микро-цель → макро-цель. Реалтайм (сессионизация каждые 15 мин)."""
    p = as_period(period)
    row = (await db.execute(
        select(
            func.count().label("sessions"),
            func.sum(case((ServerSession.is_engaged.is_(True), 1), else_=0)).label("engaged"),
            func.sum(case((ServerSession.micro_goals > 0, 1), else_=0)).label("micro"),
            func.sum(case((ServerSession.macro_goals > 0, 1), else_=0)).label("macro"),
        ).where(ServerSession.day >= p.start_date, ServerSession.day <= p.end_date,
                ServerSession.is_bot.is_(False), ServerSession.is_internal.is_(False))
    )).one()
    excluded = await db.scalar(
        select(func.count()).select_from(ServerSession).where(
            ServerSession.day >= p.start_date, ServerSession.day <= p.end_date,
            (ServerSession.is_bot.is_(True)) | (ServerSession.is_internal.is_(True)))
    ) or 0
    sessions = int(row.sessions or 0)
    return {
        "source": "own",
        "period": p.to_meta(),
        "steps": [
            {"step": "Сессии", "count": sessions},
            {"step": "Вовлечённые", "count": int(row.engaged or 0)},
            {"step": "Микро-цель", "count": int(row.micro or 0)},
            {"step": "Макро-цель", "count": int(row.macro or 0)},
        ],
        "bots_excluded": int(excluded),
    }


async def mart_metrika_funnel(db: AsyncSession, period: Period | int = 30) -> dict[str, Any]:
    """Истинная конверсия Метрики: «достиг цели» = только macro/micro цели
    по словарю metrika_goals (раньше целью считалась любая из 92, включая
    скролл и ошибку). Разложение по целям с человеческими именами; словарь
    включает soft-deleted цели — историческая goals_json резолвится всегда."""
    p = as_period(period)
    goal_dict = {
        g.goal_id: g for g in (await db.execute(select(MetrikaGoal))).scalars()
    }
    business_ids = {
        gid for gid, g in goal_dict.items() if g.tier in (TIER_MACRO, TIER_MICRO)
    }
    visits = (await db.execute(
        select(RawMetrikaVisit).where(RawMetrikaVisit.visit_date >= p.start_date,
                                      RawMetrikaVisit.visit_date <= p.end_date)
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
        "period": p.to_meta(),
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


async def mart_goal_reconciliation(db: AsyncSession, period: Period | int = 30) -> dict[str, Any]:
    """Сверка конверсий двух счётчиков строка-к-строке (волна 2, п. 6).

    Наши business-события (frontend_events, macro/micro по taxonomy) против
    достижений соответствующих целей Метрики (metrika_goals.event_name —
    маппинг цели на наше событие). Единицы разные и это честно показывается:
    у нас — события и сессии с событием, у Метрики — визиты с целью.
    Событие без цели в Метрике → metrika_visits = None (прочерк);
    цель Метрики без нашего события → отдельный список metrika_only.
    """
    from app.services.goal_taxonomy import _MACRO, _MICRO  # noqa: PLC2701

    p = as_period(period)

    our_rows = (await db.execute(
        select(
            FrontendEvent.event_name,
            func.count().label("n"),
            func.count(func.distinct(FrontendEvent.session_id_hash)).label("s"),
        )
        .where(FrontendEvent.occurred_at >= p.start, FrontendEvent.occurred_at < p.end)
        .group_by(FrontendEvent.event_name)
    )).all()
    ours = {name: (int(n or 0), int(s or 0)) for name, n, s in our_rows}

    goal_dict = {g.goal_id: g for g in (await db.execute(select(MetrikaGoal))).scalars()}
    mapped_events = {g.event_name for g in goal_dict.values() if g.event_name}

    visits = (await db.execute(
        select(RawMetrikaVisit.goals_json)
        .where(RawMetrikaVisit.visit_date >= p.start_date,
               RawMetrikaVisit.visit_date <= p.end_date,
               RawMetrikaVisit.goals_json.isnot(None))
    )).all()
    per_goal: Counter = Counter()
    for (gj,) in visits:
        stub = RawMetrikaVisit(goals_json=gj)
        for gid in set(visit_goal_ids(stub)):
            per_goal[gid] += 1

    metrika_by_event: Counter = Counter()
    metrika_only: Counter = Counter()
    for gid, cnt in per_goal.items():
        g = goal_dict.get(gid)
        if g and g.event_name:
            metrika_by_event[g.event_name] += cnt
        else:
            metrika_only[(g.name if g else None) or f"цель #{gid}"] += cnt

    # Строки: все business-события таксономии + всё замапленное в Метрике.
    tier_order = {TIER_MACRO: 0, TIER_MICRO: 1}
    events = sorted(
        set(_MACRO) | set(_MICRO) | mapped_events,
        key=lambda e: (tier_order.get(tier_for_event(e), 2), -ours.get(e, (0, 0))[0], e),
    )
    rows = []
    for ev in events:
        n, s = ours.get(ev, (0, 0))
        rows.append({
            "event": ev,
            "tier": tier_for_event(ev),
            "our_events": n,
            "our_sessions": s,
            # None = в Метрике нет цели под это событие (прочерк в UI);
            # 0 = цель есть, достижений за период нет.
            "metrika_visits": metrika_by_event.get(ev, 0) if ev in mapped_events else None,
        })

    return {
        "period": p.to_meta(),
        "rows": rows,
        "metrika_only": [
            {"goal": name, "visits": cnt} for name, cnt in metrika_only.most_common(10)
        ],
        "goals_dict_size": len(goal_dict),
        "mapped_events": len(mapped_events),
    }


# ---------------------------------------------------------------------------
# Витрина: надёжность (ошибки + vitals + api_timing + лаги)
# ---------------------------------------------------------------------------

async def mart_reliability(db: AsyncSession, period: Period | int = 7) -> dict[str, Any]:
    p = as_period(period)
    rows = (await db.execute(
        select(BehaviorEvent.event_type, BehaviorEvent.page, BehaviorEvent.params_json)
        .where(BehaviorEvent.occurred_at >= p.start, BehaviorEvent.occurred_at < p.end,
               BehaviorEvent.event_type.in_(("vital", "js_error", "api_timing")))
    )).all()

    vitals: dict[str, list[float]] = defaultdict(list)
    errors: Counter = Counter()
    own_errors: Counter = Counter()
    third_party_errors: Counter = Counter()
    error_pages: Counter = Counter()
    api: dict[str, list[float]] = defaultdict(list)
    api_fail = 0

    def _error_host(pr: dict) -> str:
        """Домен скрипта-виновника: из src (filename) либо первого URL стека."""
        src = str(pr.get("src") or "")
        m = re.search(r"https?://([^/\s):]+)", src) or re.search(r"https?://([^/\s):]+)", str(pr.get("stack") or ""))
        return m.group(1).lower() if m else ""

    for etype, page, params in rows:
        pr = params if isinstance(params, dict) else {}
        if etype == "vital" and pr.get("m") is not None:
            try:
                vitals[str(pr["m"])].append(float(pr.get("v") or 0))
            except (TypeError, ValueError):
                pass
        elif etype == "js_error":
            label = (pr.get("msg") or pr.get("src") or "unknown")[:160]
            errors[label] += 1
            # Свои vs сторонние (этап 4б): 10/10 топ-ошибок прода — счётчики
            # Метрики и РСЯ; без разделения свои регрессии тонут в чужом шуме.
            host = _error_host(pr)
            if not host or OWN_DOMAIN in host or host.startswith(("localhost", "127.")):
                own_errors[label] += 1
            else:
                third_party_errors[host] += 1
            if page:
                error_pages[page.split("?")[0]] += 1
        elif etype == "api_timing":
            u = str(pr.get("u") or "")[:120]
            try:
                api[u].append(float(pr.get("ms") or 0))
            except (TypeError, ValueError):
                pass
            if not pr.get("ok"):
                api_fail += 1

    # Лаг Метрики: свежесть последнего повизитного сырья.
    last_visit_ingest = await db.scalar(select(func.max(RawMetrikaVisit.ingested_at)))
    metrika_lag_h = (
        round((datetime.utcnow() - last_visit_ingest).total_seconds() / 3600, 1)
        if last_visit_ingest else None
    )

    api_all = [ms for xs in api.values() for ms in xs]
    return {
        "period": p.to_meta(),
        "vitals_p75": {m: _pctl(xs, 0.75) for m, xs in vitals.items()},
        "vitals_samples": {m: len(xs) for m, xs in vitals.items()},
        "js_errors_total": int(sum(errors.values())),
        "js_errors_top": [{"error": e, "count": c} for e, c in errors.most_common(12)],
        # Разделение свои/сторонние (этап 4б): свои — детально, чужие —
        # схлопнуты до домена скрипта.
        "js_errors_own": [{"error": e, "count": c} for e, c in own_errors.most_common(12)],
        "js_errors_third_party": [{"domain": h, "count": c} for h, c in third_party_errors.most_common(8)],
        "js_error_pages": dict(error_pages.most_common(10)),
        "api_p75_ms": _pctl(api_all, 0.75),
        # Таблица латентности (этап 4б): p50/p75/max/вызовы по endpoint'ам.
        "api_slowest": sorted(
            (
                {
                    "endpoint": u,
                    "p50_ms": _pctl(xs, 0.50),
                    "p75_ms": _pctl(xs, 0.75),
                    "max_ms": max(xs) if xs else None,
                    "calls": len(xs),
                }
                for u, xs in api.items() if len(xs) >= 3
            ),
            key=lambda x: -(x["p75_ms"] or 0),
        )[:60],
        "api_failed_sampled": api_fail,
        "metrika_lag_hours": metrika_lag_h,
    }


# ---------------------------------------------------------------------------
# Витрина: полнота сбора (мета-мониторинг качества данных)
# ---------------------------------------------------------------------------

async def mart_collection_quality(db: AsyncSession, period: Period | int = 7) -> dict[str, Any]:
    """Health-панель собственного счётчика: доля портретов, заполненность
    полей, аномалии времени, калибровка к Метрике (расширено по итогам
    CTO-аудита 2026-07-06)."""
    p = as_period(period)
    since, until = p.start, p.end
    sessions = (await db.execute(
        select(
            func.count().label("total"),
            func.sum(case((BehaviorSession.visitor_id_hash.isnot(None), 1), else_=0)).label("with_visitor"),
            func.sum(case((BehaviorSession.country.isnot(None), 1), else_=0)).label("with_geo"),
            func.sum(case((BehaviorSession.ym_client_id.isnot(None), 1), else_=0)).label("with_ym"),
            func.sum(case((BehaviorSession.is_webdriver.is_(True), 1), else_=0)).label("bots"),
            func.sum(case((BehaviorSession.channel.isnot(None), 1), else_=0)).label("with_channel"),
        ).where(BehaviorSession.started_at >= since, BehaviorSession.started_at < until)
    )).one()
    total = int(sessions.total or 0)

    def share(x) -> float | None:
        return round(int(x or 0) / total * 100, 1) if total else None

    # Реальное покрытие портретами: сколько активных сессий потока имеют
    # строку session_start (ретрай портрета в behavior.js чинит недобор).
    ev = (await db.execute(
        select(
            func.count(func.distinct(BehaviorEvent.session_id_hash)).label("stream_sessions"),
            func.count().label("events"),
            func.sum(case((BehaviorEvent.visitor_id_hash.isnot(None), 1), else_=0)).label("ev_with_visitor"),
        ).where(BehaviorEvent.occurred_at >= since, BehaviorEvent.occurred_at < until)
    )).one()
    stream_sessions = int(ev.stream_sessions or 0)
    events_total = int(ev.events or 0)

    # Аномалии dwell: события, где страница «читалась» дольше 4 часов
    # (клампится на инжесте с 2026-07-06 — счётчик должен идти к нулю).
    dwell_rows = (await db.execute(
        select(BehaviorEvent.params_json)
        .where(BehaviorEvent.occurred_at >= since, BehaviorEvent.occurred_at < until,
               BehaviorEvent.event_type == "dwell")
        .limit(50000)
    )).scalars().all()
    dwell_total = len(dwell_rows)
    dwell_over_4h = sum(
        1 for p in dwell_rows
        if isinstance(p, dict) and isinstance(p.get("ms"), (int, float)) and p["ms"] > 4 * 3600 * 1000
    )
    dwell_with_active = sum(
        1 for p in dwell_rows if isinstance(p, dict) and p.get("active_ms") is not None
    )

    # Калибровка к Метрике: небот-сессии vs визиты за последний ПОЛНЫЙ день
    # (Logs API отдаёт вчерашний день; сегодняшний сравнивать нечестно).
    from app.services.analytics_period import msk_day
    yesterday = msk_day(datetime.utcnow()) - timedelta(days=1)
    own_yesterday = await db.scalar(
        select(func.count()).select_from(ServerSession).where(
            ServerSession.day == yesterday, ServerSession.is_bot.is_(False), ServerSession.is_internal.is_(False))
    ) or 0
    metrika_yesterday = await db.scalar(
        select(func.count()).select_from(RawMetrikaVisit).where(
            RawMetrikaVisit.visit_date == yesterday)
    ) or 0
    calibration = (
        round(own_yesterday / metrika_yesterday, 2) if metrika_yesterday else None
    )

    # Покрытие SSR-страниц собственным потоком: есть ли pageview с чистых
    # SSR-маршрутов (standalone-бандл жив).
    ssr_pv = await db.scalar(
        select(func.count()).select_from(BehaviorEvent).where(
            BehaviorEvent.occurred_at >= since,
            BehaviorEvent.occurred_at < until,
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
        "period": p.to_meta(),
        "own_sessions": total,
        "stream_sessions": stream_sessions,
        "portrait_share_pct": (
            round(total / stream_sessions * 100, 1) if stream_sessions else None
        ),
        "visitor_id_share_pct": share(sessions.with_visitor),
        "event_visitor_id_share_pct": (
            round(int(ev.ev_with_visitor or 0) / events_total * 100, 1) if events_total else None
        ),
        "geo_share_pct": share(sessions.with_geo),
        "ym_bridge_share_pct": share(sessions.with_ym),
        "channel_share_pct": share(sessions.with_channel),
        "bot_share_pct": share(sessions.bots),
        "dwell_events": dwell_total,
        "dwell_over_4h": dwell_over_4h,
        "dwell_active_ms_share_pct": (
            round(dwell_with_active / dwell_total * 100, 1) if dwell_total else None
        ),
        "calibration_vs_metrika": calibration,
        "calibration_note": (
            f"небот-сессии {own_yesterday} / визиты Метрики {metrika_yesterday} за {yesterday.isoformat()}"
            if metrika_yesterday else "нет визитов Метрики за вчера (лаг Logs API)"
        ),
        "ssr_pageviews": int(ssr_pv),
        "stream_silence_minutes": silence_min,
    }


async def mart_botness(db: AsyncSession, period: Period | int = 7) -> dict[str, Any]:
    """Витрина роботности (BI 2.1, этап 3): сколько сессий отсеял антибот,
    распределение bot_score и по-дневная калибровка небот-сессий к визитам
    Метрики (целевой коридор ±15%). Живёт во вкладке «Надёжность»."""
    from app.services.bot_score import BOT_THRESHOLD

    p = as_period(period)
    rows = (await db.execute(
        select(
            ServerSession.day,
            func.count().label("total"),
            func.sum(case((ServerSession.is_bot.is_(True), 1), else_=0)).label("bots"),
        )
        .where(ServerSession.day >= p.start_date, ServerSession.day <= p.end_date)
        .group_by(ServerSession.day)
        .order_by(ServerSession.day)
    )).all()

    metrika_by_day = dict((await db.execute(
        select(RawMetrikaVisit.visit_date, func.count())
        .where(RawMetrikaVisit.visit_date >= p.start_date,
               RawMetrikaVisit.visit_date <= p.end_date)
        .group_by(RawMetrikaVisit.visit_date)
    )).all())

    days = []
    for day, total, bots in rows:
        total, bots = int(total or 0), int(bots or 0)
        humans = total - bots
        metrika = int(metrika_by_day.get(day, 0))
        days.append({
            "day": day.isoformat() if hasattr(day, "isoformat") else str(day),
            "sessions": total,
            "bots": bots,
            "humans": humans,
            "bot_share_pct": round(bots / total * 100, 1) if total else None,
            "metrika_visits": metrika or None,
            "ratio_pct": round(humans / metrika * 100) if metrika else None,
        })

    # Распределение счёта — видно, на чём срабатывает антибот.
    buckets = [("0", 0, 0), ("1–39", 1, 39), ("40–59", 40, 59),
               (f"{BOT_THRESHOLD}–99", BOT_THRESHOLD, 99), ("100", 100, 100)]
    histogram = []
    for label, lo, hi in buckets:
        cnt = await db.scalar(
            select(func.count()).select_from(ServerSession)
            .where(ServerSession.day >= p.start_date, ServerSession.day <= p.end_date,
                   ServerSession.bot_score >= lo, ServerSession.bot_score <= hi)
        ) or 0
        histogram.append({"bucket": label, "sessions": int(cnt)})

    total_all = sum(d["sessions"] for d in days)
    total_bots = sum(d["bots"] for d in days)
    return {
        "period": p.to_meta(),
        "threshold": BOT_THRESHOLD,
        "sessions": total_all,
        "bots": total_bots,
        "bot_share_pct": round(total_bots / total_all * 100, 1) if total_all else None,
        "days": days,
        "score_histogram": histogram,
        "note": "Коридор приёмки: небот-сессии в пределах ±15% к визитам Метрики за полный день.",
    }


# ---------------------------------------------------------------------------
# Витрина: гео и сегментация
# ---------------------------------------------------------------------------

async def mart_geo(db: AsyncSession, period: Period | int = 30) -> dict[str, Any]:
    p = as_period(period)
    rows = (await db.execute(
        select(BehaviorSession.country, BehaviorSession.geo_region, BehaviorSession.city, func.count())
        .where(BehaviorSession.started_at >= p.start, BehaviorSession.started_at < p.end)
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
            # DB-IP отдаёт округ в скобках («Moscow (Tsentralnyy ...)») —
            # схлопываем в город, иначе Москва дублируется в топе.
            cities[re.sub(r"\s*\(.+\)$", "", city)] += cnt
    return {
        "countries": dict(countries.most_common(15)),
        "regions": dict(regions.most_common(20)),
        "cities": dict(cities.most_common(30)),
    }


async def mart_segments(db: AsyncSession, period: Period | int = 30) -> dict[str, Any]:
    """Сегментация: канал × устройство × новизна.

    Основной слой — дневные агрегаты Метрики (DailyTraffic). Если за окно их
    нет (период «Сегодня»: Метрика отдаёт агрегаты за завершённый день) —
    fallback на собственные небот-сессии, чтобы карточка не была пустой.
    """
    p = as_period(period)
    rows = (await db.execute(
        select(
            DailyTraffic.channel, DailyTraffic.device, DailyTraffic.is_new,
            func.sum(DailyTraffic.visits), func.sum(DailyTraffic.goal_visits),
            func.sum(DailyTraffic.total_duration_sec), func.sum(DailyTraffic.bounces),
        )
        .where(DailyTraffic.day >= p.start_date, DailyTraffic.day <= p.end_date)
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
    if segments:
        segments.sort(key=lambda s: -s["visits"])
        return {"segments": segments, "source": "metrika"}

    own_rows = (await db.execute(
        select(
            ServerSession.channel, ServerSession.device, ServerSession.is_new_visitor,
            func.count(),
            func.sum(case((ServerSession.macro_goals > 0, 1), else_=0)),
            func.sum(ServerSession.duration_ms),
            func.sum(case((ServerSession.pageviews <= 1, 1), else_=0)),
        )
        .where(ServerSession.day >= p.start_date, ServerSession.day <= p.end_date,
               ServerSession.is_bot.is_(False), ServerSession.is_internal.is_(False))
        .group_by(ServerSession.channel, ServerSession.device, ServerSession.is_new_visitor)
    )).all()
    for ch, dev, is_new, n, goals, dur_ms, bounces in own_rows:
        v = int(n or 0)
        goal_sessions = int(goals or 0)
        segments.append({
            "channel": ch or "direct",
            "device": dev or "unknown",
            "is_new": bool(is_new),
            "visits": v,
            "goal_visits": goal_sessions,
            "conversion_pct": round(goal_sessions / v * 100, 2) if v else 0.0,
            "avg_duration_sec": round(int(dur_ms or 0) / 1000 / v) if v else 0,
            "bounce_pct": round(int(bounces or 0) / v * 100, 1) if v else 0.0,
        })
    segments.sort(key=lambda s: -s["visits"])
    return {"segments": segments, "source": "own"}


# ---------------------------------------------------------------------------
# Витрина: блочная аналитика
# ---------------------------------------------------------------------------

async def mart_blocks(db: AsyncSession, period: Period | int = 30) -> dict[str, Any]:
    """Что реально смотрят: время видимости [data-block] по разделам сайта.
    Блоки с высоким вниманием — расширять; с нулевым — поднимать/переделывать."""
    p = as_period(period)
    rows = (await db.execute(
        select(BehaviorEvent.page, BehaviorEvent.params_json)
        .where(BehaviorEvent.occurred_at >= p.start, BehaviorEvent.occurred_at < p.end,
               BehaviorEvent.event_type == "block_view",
               not_admin_page(BehaviorEvent.page))
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

async def mart_page_quadrants(db: AsyncSession, period: Period | int = 30) -> dict[str, Any]:
    """Матрица «трафик × вовлечение» по разделам: квадрант = действие
    (продвигать / тиражировать / чинить / переработать)."""
    p = as_period(period)
    rows = (await db.execute(
        select(
            DailyPage.page,
            func.sum(DailyPage.views), func.sum(DailyPage.total_active_ms),
            func.sum(DailyPage.total_dwell_ms), func.sum(DailyPage.dead_clicks),
        ).where(DailyPage.day >= p.start_date, DailyPage.day <= p.end_date)
        .group_by(DailyPage.page)
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


async def mart_feature_adoption(db: AsyncSession, period: Period | int = 30) -> dict[str, Any]:
    """Adoption фич по бизнес-событиям + сигналы «где ждут интерактив»
    (dead-клики) и «что уносят руками» (copy — кандидаты на share/embed)."""
    p = as_period(period)
    rows = (await db.execute(
        select(DailyGoal.event_name, DailyGoal.tier, func.sum(DailyGoal.count), func.sum(DailyGoal.sessions))
        .where(DailyGoal.day >= p.start_date, DailyGoal.day <= p.end_date)
        .group_by(DailyGoal.event_name, DailyGoal.tier)
    )).all()
    features = [
        {"event": name, "tier": tier, "count": int(cnt or 0), "sessions": int(sess or 0),
         "weight": weight_for_event(name)}
        for name, tier, cnt, sess in rows
    ]
    features.sort(key=lambda x: -x["count"])

    copies = (await db.execute(
        select(BehaviorEvent.element_text, func.count())
        .where(BehaviorEvent.occurred_at >= p.start, BehaviorEvent.occurred_at < p.end,
               BehaviorEvent.event_type == "copy",
               not_admin_page(BehaviorEvent.page))  # свои копии из BI — не сигнал
        .group_by(BehaviorEvent.element_text)
        .order_by(func.count().desc()).limit(15)
    )).all()
    return {
        "features": features[:50],
        "top_copied": [{"text": t, "count": c} for t, c in copies if t],
    }


async def mart_embed_distribution(_db: AsyncSession | None = None, period: Period | int = 30) -> dict[str, Any]:
    """Распространение виджетов: показы embed'ов на чужих сайтах.

    Источник — Redis-счётчики показов `fe:embed:imp:{day}` (поле
    `code:type:domain`), которые пишут пиксель и impression-endpoint
    embed API. Это недооценённый сигнал дистрибуции бренда: каждый показ —
    наш график на чужой странице со ссылкой на нас.
    """
    from app.core.cache import get_redis

    p = as_period(period)
    by_domain: Counter = Counter()
    by_code: Counter = Counter()
    by_type: Counter = Counter()
    daily: dict[str, int] = {}
    total = 0
    try:
        r = await get_redis()
        cursor_day = p.start_date
        days_list = []
        while cursor_day <= p.end_date and len(days_list) < 90:
            days_list.append(cursor_day.isoformat())
            cursor_day += timedelta(days=1)
        for day in days_list:
            h = await r.hgetall(f"fe:embed:imp:{day}")
            if not h:
                continue
            day_total = 0
            for field, cnt in h.items():
                key = field.decode() if isinstance(field, bytes) else str(field)
                n = int(cnt)
                parts = key.split(":")
                code = parts[0] if parts else "unknown"
                wtype = parts[1] if len(parts) > 1 else "unknown"
                domain = ":".join(parts[2:]) or "direct"
                by_code[code] += n
                by_type[wtype] += n
                by_domain[domain] += n
                day_total += n
            daily[day] = day_total
            total += day_total
    except Exception:  # noqa: BLE001 — Redis недоступен: карточка пустая, не 500
        logger.warning("mart_embed_distribution: Redis unavailable", exc_info=True)
    return {
        "total_impressions": total,
        "domains": [{"domain": d, "count": c} for d, c in by_domain.most_common(20)],
        "codes": [{"code": c, "count": n} for c, n in by_code.most_common(15)],
        "types": dict(by_type.most_common()),
        "daily": [{"date": d, "count": c} for d, c in sorted(daily.items())],
    }


# ---------------------------------------------------------------------------
# Витрина: «Люди» — досье посетителей со скорингом
# ---------------------------------------------------------------------------

async def mart_people(db: AsyncSession, period: Period | int = 30, limit: int = 300) -> dict[str, Any]:
    """Список посетителей по visitor_id: портрет, сессии, интересы, скоринг
    ценности (веса goal_taxonomy). Для зарегистрированных — связка через
    identity_links (история до регистрации принадлежит человеку)."""
    p = as_period(period)

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
        .where(ServerSession.day >= p.start_date, ServerSession.day <= p.end_date,
               ServerSession.is_bot.is_(False), ServerSession.is_internal.is_(False))
        .group_by(ServerSession.visitor_id_hash)
        .order_by(func.count().desc())
        .limit(limit * 2)
    )).all()

    visitor_ids = [r.visitor_id_hash for r in sess_rows if r.visitor_id_hash]
    # Портрет: последняя сессия с известным visitor. Попутно строим карту
    # session_id → visitor: события старых бандлов идут без visitor_id_hash,
    # и скоринг/интересы без этого моста были нулевыми (фикс 4б).
    portraits: dict[str, BehaviorSession] = {}
    session_to_visitor: dict[str, str] = {}
    if visitor_ids:
        for bs in (await db.execute(
            select(BehaviorSession)
            .where(BehaviorSession.visitor_id_hash.in_(visitor_ids))
            .order_by(BehaviorSession.started_at)
        )).scalars():
            portraits[bs.visitor_id_hash] = bs
            session_to_visitor[bs.session_id_hash] = bs.visitor_id_hash

    # Связка с аккаунтами.
    links: dict[str, str] = {}
    if visitor_ids:
        for link in (await db.execute(
            select(IdentityLink).where(IdentityLink.visitor_id_hash.in_(visitor_ids))
        )).scalars():
            links[link.visitor_id_hash] = link.user_id

    # Интересы + скоринг по бизнес-событиям. Событие резолвится в человека
    # по visitor_id_hash ЛИБО по session_id_hash (мост через behavior_sessions):
    # хвост старых бандлов шлёт события без visitor — без моста скоринг нулевой.
    interests: dict[str, Counter] = defaultdict(Counter)
    scores: dict[str, int] = defaultdict(int)
    if visitor_ids:
        ev_rows = (await db.execute(
            select(FrontendEvent.visitor_id_hash, FrontendEvent.session_id_hash,
                   FrontendEvent.event_name, FrontendEvent.url, func.count())
            .where(FrontendEvent.occurred_at >= p.start, FrontendEvent.occurred_at < p.end,
                   or_(FrontendEvent.visitor_id_hash.in_(visitor_ids),
                       FrontendEvent.session_id_hash.in_(list(session_to_visitor))))
            .group_by(FrontendEvent.visitor_id_hash, FrontendEvent.session_id_hash,
                      FrontendEvent.event_name, FrontendEvent.url)
        )).all()
        known = set(visitor_ids)
        per_event: dict[tuple[str, str], int] = defaultdict(int)
        for vid, sid, name, url, cnt in ev_rows:
            person = vid if vid in known else session_to_visitor.get(sid or "")
            if not person:
                continue
            per_event[(person, name)] += int(cnt)
            if url and "/indicator/" in url:
                code = url.split("/indicator/")[-1].split("?")[0].split("/")[0]
                if code:
                    interests[person][code] += int(cnt)
        # Кэп: одно событие даёт очки максимум SCORE_EVENT_CAP раз — иначе
        # scroll_depth/indicator_view делают «скроллера» ценнее конверсии.
        for (vid, name), cnt in per_event.items():
            scores[vid] += weight_for_event(name) * min(cnt, SCORE_EVENT_CAP)

    people = []
    for r in sess_rows:
        vid = r.visitor_id_hash
        if not vid:
            continue
        # Фильтр шума (этап 4б): случайный однократный заход без единой цели
        # не «человек в досье» — оставляем ≥2 сессий либо ≥1 цель/очко.
        if int(r.sessions or 0) < 2 and not int(r.micro or 0) and not int(r.macro or 0) and not scores.get(vid, 0):
            continue
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
# Витрина: A/B-эксперименты — автоанализ конверсии по вариантам
# ---------------------------------------------------------------------------

async def mart_experiments(db: AsyncSession, period: Period | int = 30) -> dict[str, Any]:
    """Автоанализ A/B: по каждому experiment_exposure (params: experiment,
    variant) — охват и конверсия варианта в micro/macro-цель тем же visitor'ом
    в окне эксперимента. Пусто, пока экспозиции не шлются — каркас готов."""
    p = as_period(period)
    since, until = p.start, p.end
    rows = (await db.execute(
        select(FrontendEvent.visitor_id_hash, FrontendEvent.params_json)
        .where(
            FrontendEvent.occurred_at >= since,
            FrontendEvent.occurred_at < until,
            FrontendEvent.event_name == "experiment_exposure",
            FrontendEvent.visitor_id_hash.isnot(None),
        )
    )).all()
    if not rows:
        return {"experiments": [], "note": "Экспозиций нет — карточки появятся с первым A/B"}

    # visitor → множество (experiment, variant)
    exposed: dict[tuple[str, str], set] = defaultdict(set)
    for vid, params in rows:
        p = params or {}
        exp = str(p.get("experiment") or p.get("exp") or "").strip()
        var = str(p.get("variant") or p.get("var") or "").strip()
        if exp and var:
            exposed[(exp, var)].add(vid)

    all_vids = set().union(*exposed.values()) if exposed else set()
    converted: set = set()
    if all_vids:
        conv_rows = (await db.execute(
            select(FrontendEvent.visitor_id_hash, FrontendEvent.event_name)
            .where(
                FrontendEvent.occurred_at >= since,
                FrontendEvent.occurred_at < until,
                FrontendEvent.visitor_id_hash.in_(all_vids),
            ).distinct()
        )).all()
        for vid, name in conv_rows:
            if tier_for_event(name) in (TIER_MACRO, TIER_MICRO):
                converted.add(vid)

    experiments: dict[str, list] = defaultdict(list)
    for (exp, var), vids in sorted(exposed.items()):
        conv = len(vids & converted)
        experiments[exp].append({
            "variant": var,
            "visitors": len(vids),
            "converted": conv,
            "conversion_pct": round(conv / len(vids) * 100, 2) if vids else 0.0,
        })
    return {
        "experiments": [{"experiment": exp, "variants": vs} for exp, vs in experiments.items()],
        "note": None,
    }


# ---------------------------------------------------------------------------
# Витрина: CH-срезы дня для Пульса (аномалии-кандидаты; мягкая деградация)
# ---------------------------------------------------------------------------

async def mart_ch_slices_of_day(_db: AsyncSession | None = None) -> dict[str, Any]:
    """2–3 стандартных OLAP-среза дня для LLM-контекста: канал×новизна,
    источник×устройство Метрики, страница-топ. CH недоступен → {'available':
    False} — Пульс собирается без срезов (инвариант «CH вторичен»)."""
    from app.config import settings
    if not settings.clickhouse_enabled:
        return {"available": False}
    try:
        from app.services.clickhouse_sync import run_slice
        return {
            "available": True,
            "sessions_by_channel": (await run_slice("sessions", ["channel", "is_new"], days=1))["rows"][:8],
            "metrika_by_source_device": (await run_slice("metrika_visits", ["traffic_source", "device"], days=1))["rows"][:8],
            "pageviews_by_page": (await run_slice("pageviews", ["page"], days=1))["rows"][:10],
        }
    except Exception as exc:  # noqa: BLE001 — деградация без падения снапшота
        logger.warning("CH slices for pulse unavailable: %s", exc)
        return {"available": False}


# ---------------------------------------------------------------------------
# Витрина: расходы Директа (CPA/ROI — каркас до передачи токена)
# ---------------------------------------------------------------------------

async def mart_ad_costs(db: AsyncSession, period: Period | int = 30) -> dict[str, Any]:
    p = as_period(period)
    rows = (await db.execute(
        select(DirectCost.campaign, func.sum(DirectCost.cost_rub), func.sum(DirectCost.clicks))
        .where(DirectCost.day >= p.start_date, DirectCost.day <= p.end_date)
        .group_by(DirectCost.campaign)
    )).all()
    total_cost = float(sum(float(c or 0) for _, c, _ in rows))

    # Macro-цели окна для CPA (когда появятся расходы).
    macro_goals = await db.scalar(
        select(func.sum(DailyGoal.count)).where(
            DailyGoal.day >= p.start_date, DailyGoal.day <= p.end_date,
            DailyGoal.tier == TIER_MACRO,
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
    from app.services.analytics_period import resolve_period

    today = resolve_period("today")
    week = resolve_period("7d")
    return {
        "metric_tree": await mart_metric_tree(db, as_period(14)),
        "own_funnel_today": await mart_own_funnel(db, today),
        "metrika_funnel_7d": await mart_metrika_funnel(db, week),
        "reliability": await mart_reliability(db, today),
        "collection_quality": await mart_collection_quality(db, today),
        "geo_today": await mart_geo(db, today),
        "segments_7d": await mart_segments(db, week),
        "blocks_today": await mart_blocks(db, today),
        "page_quadrants_7d": await mart_page_quadrants(db, week),
        "feature_adoption_7d": await mart_feature_adoption(db, week),
        "experiments_30d": await mart_experiments(db, resolve_period("30d")),
        "ad_costs": await mart_ad_costs(db, week),
        "ch_slices": await mart_ch_slices_of_day(db),
    }

"""BI-витрины для админ-кабинета /admin/bi (директива владельца 2026-07-05).

Один вызов `build_bi_dashboard(db, days)` собирает ВСЕ секции дашборда в один
JSON: KPI-ряды по дням, привлечение (источники/поисковики/кампании Директа),
воронка «источник → вовлечение → цель → регистрация», retention-когорты,
качество страниц (dwell/scroll/dead-клики × индексация), поисковый спрос
vs покрытие, внутренние поиски сайта, граф внутренней навигации, гипотезы
Пульс-аналитика и инвентаризация датасета.

Дизайн-принципы:
- Объёмы «человеческих» таблиц малы (визиты ~1–2k/мес): их тянем в память и
  агрегируем в Python — это даёт свободные срезы без SQL-акробатики.
- behavior_events (сотни тысяч строк) агрегируем только на SQL.
- Кэш — на уровне API-роутера (Redis, 15 минут): дашборд «самообновляется»
  каждые 15 минут без нагрузки на БД.
- Новые собираемые данные попадают сюда автоматически: внутренние поиски —
  единое событие search_query{context}; инвентаризация — dataset_inventory
  (перечисляет таблицы датасета целиком).

Экономика рекламы: расход/CPC по кампаниям требует коннектора Яндекс.Директа
(отдельный OAuth-scope). Пока расход недоступен, витрина ads считает визиты,
вовлечение и конверсию per-кампания — колонка расходов появится после
подключения Директа (см. docs/analytics_api_inventory/).
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    BehaviorEvent,
    FrontendEvent,
    Hypothesis,
    MetrikaDailyPageMetric,
    MetrikaSearchPhrase,
    RawMetrikaVisit,
    User,
    WebmasterSearchQuery,
)

logger = logging.getLogger(__name__)

# События-цели для воронки: что считаем «ценным действием» визита.
# Ревизия 2026-07-05: цель = конверсионное действие (аккаунт, подписка, экспорт
# данных, обратная связь). Вовлечение (compare_add, calc_*, chart_*) целью не
# считается — оно живёт в engaged-слое воронки. Список сверен с track.js.
_GOAL_EVENTS = {
    "signup", "login_success", "oauth_start", "newsletter_opt_in",
    "download_csv", "download_excel", "download_ical",
    "chart_image_download", "compare_image_download", "feedback_submit",
}
_DOWNLOAD_EVENTS = {
    "download_csv", "download_excel", "download_ical",
    "chart_image_download", "compare_image_download",
}
_ERROR_EVENTS = {"api_load_error", "error_reload", "api_retry"}

# Классификация путей по продуктовым разделам — для структуры потребления
# контента (treemap в BI). Порядок важен: первое совпадение выигрывает.
_SECTION_RULES = [
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


def _page_section(path: str) -> str:
    if not path or path == "/":
        return "Главная"
    for prefix, name in _SECTION_RULES:
        if path.startswith(prefix):
            return name
    return "Прочее"


def _day(dt: datetime | date | None) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.date().isoformat()
    return dt.isoformat()


def _visit_field(v: RawMetrikaVisit, key: str) -> str:
    raw = v.raw_json or {}
    return (raw.get(key) or "").strip()


# ym:s:deviceCategory в Logs API — числовой код, не слово.
_METRIKA_DEVICE = {"1": "desktop", "2": "mobile", "3": "tablet", "4": "tv"}

# Машинные ярлыки Logs API → те же канонические имена, что даёт наш ua_parser.
# Иначе сверка «наш слой vs Метрика» на витрине не сопоставляется по ключам.
_METRIKA_BROWSER = {
    "yandex_browser": "Яндекс.Браузер",
    "yandexsearch": "Яндекс.Браузер",
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
_METRIKA_OS = {
    "windows": "Windows",
    "android": "Android",
    "ios": "iOS",
    "mac_os": "macOS",
    "macos": "macOS",
    "gnu_linux": "Linux",
    "linux": "Linux",
}


def _visit_device(v: RawMetrikaVisit) -> str:
    raw = _visit_field(v, "ym:s:deviceCategory")
    return _METRIKA_DEVICE.get(raw, raw)


def _visit_browser(v: RawMetrikaVisit) -> str:
    raw = _visit_field(v, "ym:s:browser").lower()
    return _METRIKA_BROWSER.get(raw, raw)


def _visit_os(v: RawMetrikaVisit) -> str:
    raw = _visit_field(v, "ym:s:operatingSystemRoot").lower()
    return _METRIKA_OS.get(raw, raw)


def _has_goals(v: RawMetrikaVisit) -> bool:
    """Истинная проверка «визит достиг цели Метрики».

    goals_json хранится как {"goals": "[577576799,...]"} — строка со списком id
    внутри объекта, и объект есть у КАЖДОГО визита с непустым полем выгрузки.
    Наивный truthy-чек считал целью почти каждый визит (конверсия 91–100% —
    инцидент 2026-07-05). Цель есть только если внутри непустой список id.
    """
    gj = v.goals_json
    if not gj:
        return False
    if isinstance(gj, dict):
        gj = gj.get("goals")
    if isinstance(gj, str):
        stripped = gj.strip().strip("[]").strip()
        return bool(stripped)
    if isinstance(gj, (list, tuple)):
        return len(gj) > 0
    return False


async def _kpi_daily(db: AsyncSession, since: datetime) -> list[dict]:
    """Ряды по дням: визиты/посетители (Метрика), события, регистрации,
    скачивания, ошибки + live-слой из собственного потока behavior_events
    (pageviews и уникальные сессии). Метрика Logs API отдаёт данные с
    задержкой до суток — live-слой закрывает «сегодня и вчера» в реальном
    времени, график не обрывается нулями на свежих днях."""
    days: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "visits": 0, "visitors": set(), "ad_visits": 0, "events": 0,
        "registrations": 0, "downloads": 0, "errors": 0, "searches": 0,
        "live_pageviews": 0, "live_sessions": set(),
    })

    visits = (await db.execute(
        select(RawMetrikaVisit.visit_date, RawMetrikaVisit.client_id_hash,
               RawMetrikaVisit.traffic_source)
        .where(RawMetrikaVisit.visit_date >= since.date())
    )).all()
    for vd, client, source in visits:
        d = _day(vd)
        if not d:
            continue
        days[d]["visits"] += 1
        if client:
            days[d]["visitors"].add(client)
        if source == "ad":
            days[d]["ad_visits"] += 1

    ev_rows = (await db.execute(
        select(
            func.date(FrontendEvent.occurred_at),
            FrontendEvent.event_name,
            func.count(FrontendEvent.id),
        )
        .where(FrontendEvent.occurred_at >= since)
        .group_by(func.date(FrontendEvent.occurred_at), FrontendEvent.event_name)
    )).all()
    for d_raw, name, cnt in ev_rows:
        d = str(d_raw)
        days[d]["events"] += cnt
        if name in _DOWNLOAD_EVENTS:
            days[d]["downloads"] += cnt
        if name in _ERROR_EVENTS:
            days[d]["errors"] += cnt
        if name == "search_query":
            days[d]["searches"] += cnt

    reg_rows = (await db.execute(
        select(func.date(User.created_at), func.count(User.id))
        .where(User.created_at >= since)
        .group_by(func.date(User.created_at))
    )).all()
    for d_raw, cnt in reg_rows:
        days[str(d_raw)]["registrations"] = cnt

    # Live-слой: собственный поток behavior.js (без лага Метрики).
    live_rows = (await db.execute(
        select(func.date(BehaviorEvent.occurred_at),
               BehaviorEvent.session_id_hash)
        .where(BehaviorEvent.event_type == "pageview",
               BehaviorEvent.occurred_at >= since)
    )).all()
    for d_raw, session in live_rows:
        d = str(d_raw)
        days[d]["live_pageviews"] += 1
        if session:
            days[d]["live_sessions"].add(session)

    # Полный календарь окна: день без данных — явный ноль, а не дыра на оси
    # времени (иначе график сжимает пропуски и искажает динамику).
    cursor = since.date()
    today = datetime.utcnow().date()
    while cursor <= today:
        days[cursor.isoformat()]  # defaultdict дозаполняет нулевую строку
        cursor += timedelta(days=1)

    out = []
    for d in sorted(days):
        row = days[d]
        out.append({
            "date": d,
            "visits": row["visits"],
            "visitors": len(row["visitors"]),
            "ad_visits": row["ad_visits"],
            "events": row["events"],
            "registrations": row["registrations"],
            "downloads": row["downloads"],
            "errors": row["errors"],
            "searches": row["searches"],
            "live_pageviews": row["live_pageviews"],
            "live_sessions": len(row["live_sessions"]),
        })
    return out


def _acquisition(visits: list[RawMetrikaVisit]) -> dict:
    """Источники, поисковики, кампании, фразы, гео и устройства из сырых визитов."""
    sources: Counter = Counter()
    engines: Counter = Counter()
    campaigns: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "visits": 0, "goal_visits": 0, "bounce_like": 0, "duration_sum": 0,
    })
    phrases: Counter = Counter()
    cities: Counter = Counter()
    devices: Counter = Counter()
    referers: Counter = Counter()

    for v in visits:
        src = v.traffic_source or "unknown"
        sources[src] += 1
        if v.search_engine:
            engines[v.search_engine] += 1
        if v.search_phrase:
            phrases[v.search_phrase.strip().lower()[:80]] += 1
        city = _visit_field(v, "ym:s:regionCity")
        if city:
            cities[city] += 1
        dev = _visit_device(v)
        if dev:
            devices[dev] += 1
        if src in ("link", "referral") and v.referer:
            referers[v.referer[:100]] += 1
        if src == "ad":
            camp = _visit_field(v, "ym:s:UTMCampaign") or "(без метки)"
            c = campaigns[camp]
            c["visits"] += 1
            if _has_goals(v):
                c["goal_visits"] += 1
            if _visit_field(v, "ym:s:bounce") in ("1", "true"):
                c["bounce_like"] += 1
            c["duration_sum"] += v.duration_seconds or 0

    ads = []
    for camp, c in sorted(campaigns.items(), key=lambda kv: -kv[1]["visits"]):
        n = c["visits"] or 1
        ads.append({
            "campaign": camp,
            "visits": c["visits"],
            "goal_visits": c["goal_visits"],
            "goal_rate_pct": round(c["goal_visits"] / n * 100, 1),
            "bounce_pct": round(c["bounce_like"] / n * 100, 1),
            "avg_duration_sec": round(c["duration_sum"] / n),
            "cost": None,  # появится после коннектора Яндекс.Директа
        })

    return {
        "sources": dict(sources.most_common()),
        "search_engines": dict(engines.most_common(10)),
        "top_phrases": dict(phrases.most_common(25)),
        "top_cities": dict(cities.most_common(15)),
        "devices": dict(devices.most_common()),
        "top_referers": dict(referers.most_common(10)),
        "ad_campaigns": ads,
    }


def _funnel(visits: list[RawMetrikaVisit], registrations_by_day: dict[str, int]) -> dict:
    """Воронка «источник → вовлечение → цель» по каналам + сквозной счёт.

    Точного join'а «визит Метрики ↔ first-party событие» нет (нет общего id),
    поэтому воронка агрегатная: канал → визиты → визиты с >1 страницей →
    визиты с достигнутой целью Метрики. Регистрации — сквозной счётчик рядом.
    """
    by_source: dict[str, dict[str, int]] = defaultdict(lambda: {
        "visits": 0, "engaged": 0, "goal_visits": 0,
    })
    landings: dict[str, dict[str, int]] = defaultdict(lambda: {"visits": 0, "goal_visits": 0})

    for v in visits:
        src = v.traffic_source or "unknown"
        s = by_source[src]
        s["visits"] += 1
        try:
            pv = int(float(_visit_field(v, "ym:s:pageViews") or "0"))
        except ValueError:
            pv = 0
        goal = _has_goals(v)
        # Инвариант воронки: достигшие цели ⊆ вовлечённые — визит с целью
        # вовлечён по определению, даже если был короткий одностраничный.
        if goal or pv > 1 or (v.duration_seconds or 0) >= 30:
            s["engaged"] += 1
        if goal:
            s["goal_visits"] += 1
        if v.start_url:
            path = v.start_url.split("forecasteconomy.com")[-1].split("?")[0][:80] or "/"
            landings[path]["visits"] += 1
            if goal:
                landings[path]["goal_visits"] += 1

    steps = []
    for src, s in sorted(by_source.items(), key=lambda kv: -kv[1]["visits"]):
        n = s["visits"] or 1
        steps.append({
            "source": src,
            "visits": s["visits"],
            "engaged": s["engaged"],
            "engaged_pct": round(s["engaged"] / n * 100, 1),
            "goal_visits": s["goal_visits"],
            "goal_pct": round(s["goal_visits"] / n * 100, 1),
        })

    top_landings = [
        {"page": p, **c, "goal_pct": round(c["goal_visits"] / (c["visits"] or 1) * 100, 1)}
        for p, c in sorted(landings.items(), key=lambda kv: -kv[1]["visits"])[:20]
    ]
    return {
        "by_source": steps,
        "top_landings": top_landings,
        "registrations_total": sum(registrations_by_day.values()),
        "registrations_by_day": registrations_by_day,
    }


def _retention(all_visits: list[RawMetrikaVisit]) -> dict:
    """Возвращаемость аудитории в двух масштабах.

    Дневные когорты — рабочий инструмент, пока продукту недели (история
    визитов с 2026-06-30): когорта = день первого визита, столбцы = вернулся
    через N дней (1..14). Недельные когорты копятся параллельно и станут
    главными, когда истории будет больше месяца. Возвращаемость (returning) —
    посетитель активен более чем в одном КАЛЕНДАРНОМ ДНЕ (не неделе: внутри
    одной недели возврат на следующий день — тоже возврат).
    """
    first_seen: dict[str, date] = {}
    days_active: dict[str, set[date]] = defaultdict(set)

    for v in sorted(all_visits, key=lambda x: (x.visit_date or date.min)):
        if not v.client_id_hash or not v.visit_date:
            continue
        cid = v.client_id_hash
        if cid not in first_seen:
            first_seen[cid] = v.visit_date
        days_active[cid].add(v.visit_date)

    # Дневные когорты: день первого визита → размер + вернувшиеся через N дней.
    day_cohorts: dict[str, dict[str, Any]] = defaultdict(lambda: {"size": 0, "returned": Counter()})
    # Недельные когорты (задел на зрелость продукта).
    week_cohorts: dict[str, dict[str, Any]] = defaultdict(lambda: {"size": 0, "returned": Counter()})

    for cid, first in first_seen.items():
        dc = day_cohorts[first.isoformat()]
        dc["size"] += 1
        cohort_week = first - timedelta(days=first.weekday())
        wc = week_cohorts[cohort_week.isoformat()]
        wc["size"] += 1
        weeks_seen: set[int] = set()
        for d in days_active[cid]:
            day_offset = (d - first).days
            if 0 < day_offset <= 14:
                dc["returned"][day_offset] += 1
            week_offset = ((d - timedelta(days=d.weekday())) - cohort_week).days // 7
            if week_offset > 0 and week_offset not in weeks_seen:
                weeks_seen.add(week_offset)
                wc["returned"][min(week_offset, 8)] += 1

    day_rows = [
        {
            "cohort_day": day,
            "size": c["size"],
            "day_plus": {str(k): v for k, v in sorted(c["returned"].items())},
        }
        for day, c in sorted(day_cohorts.items(), reverse=True)[:21]
    ]
    week_rows = [
        {
            "cohort_week": week,
            "size": c["size"],
            "week_plus": {str(k): v for k, v in sorted(c["returned"].items())},
        }
        for week, c in sorted(week_cohorts.items(), reverse=True)[:12]
    ]
    returning = sum(1 for cid in first_seen if len(days_active[cid]) > 1)
    return {
        "cohorts": week_rows,
        "day_cohorts": day_rows,
        "unique_visitors": len(first_seen),
        "returning_visitors": returning,
        "returning_pct": round(returning / (len(first_seen) or 1) * 100, 1),
    }


async def _pages_quality(db: AsyncSession, since: datetime) -> list[dict]:
    """Качество страниц: pageviews + dwell + dead/rage из behavior,
    bounce из дневных агрегатов Метрики. «Тонкие» страницы — низкий dwell."""
    pv_rows = (await db.execute(
        select(BehaviorEvent.page, func.count(BehaviorEvent.id))
        .where(BehaviorEvent.event_type == "pageview",
               BehaviorEvent.occurred_at >= since)
        .group_by(BehaviorEvent.page)
        .order_by(func.count(BehaviorEvent.id).desc())
        .limit(40)
    )).all()

    pages = {p: {"page": p, "pageviews": cnt, "avg_dwell_sec": None,
                 "avg_scroll_pct": None, "dead_clicks": 0, "rage_clicks": 0,
                 "bounce_pct": None}
             for p, cnt in pv_rows if p}
    if not pages:
        return []
    page_list = list(pages)

    # dwell: params_json.ms и scroll-глубина. JSON-доступ различается между
    # Postgres и sqlite → агрегируем в Python по выборке (dwell-строк немного).
    dwell_rows = (await db.execute(
        select(BehaviorEvent.page, BehaviorEvent.params_json)
        .where(BehaviorEvent.event_type == "dwell",
               BehaviorEvent.occurred_at >= since,
               BehaviorEvent.page.in_(page_list))
        .limit(50000)
    )).all()
    dwell_acc: dict[str, list[float]] = defaultdict(list)
    scroll_acc: dict[str, list[float]] = defaultdict(list)
    for p, params in dwell_rows:
        if not isinstance(params, dict):
            continue
        ms = params.get("ms") or params.get("dwell_ms")
        if isinstance(ms, (int, float)) and ms > 0:
            dwell_acc[p].append(float(ms) / 1000)
        sc = params.get("scroll") or params.get("scroll_pct") or params.get("max_scroll")
        if isinstance(sc, (int, float)):
            scroll_acc[p].append(float(sc))
    for p, arr in dwell_acc.items():
        pages[p]["avg_dwell_sec"] = round(sum(arr) / len(arr), 1)
    for p, arr in scroll_acc.items():
        pages[p]["avg_scroll_pct"] = round(sum(arr) / len(arr), 1)

    for flag, key in ((BehaviorEvent.is_dead, "dead_clicks"), (BehaviorEvent.is_rage, "rage_clicks")):
        rows = (await db.execute(
            select(BehaviorEvent.page, func.count(BehaviorEvent.id))
            .where(BehaviorEvent.event_type == "click", flag.is_(True),
                   BehaviorEvent.occurred_at >= since,
                   BehaviorEvent.page.in_(page_list))
            .group_by(BehaviorEvent.page)
        )).all()
        for p, cnt in rows:
            pages[p][key] = cnt

    bounce_rows = (await db.execute(
        select(MetrikaDailyPageMetric.url,
               func.avg(MetrikaDailyPageMetric.bounce_rate))
        .where(MetrikaDailyPageMetric.date >= since.date())
        .group_by(MetrikaDailyPageMetric.url)
    )).all()
    bounce_by_path = {}
    for url, rate in bounce_rows:
        if url and rate is not None:
            path = url.split("forecasteconomy.com")[-1].split("?")[0] or "/"
            bounce_by_path[path] = round(float(rate), 1)
    for p in pages:
        if p in bounce_by_path:
            pages[p]["bounce_pct"] = bounce_by_path[p]

    return sorted(pages.values(), key=lambda r: -r["pageviews"])


async def _demand_vs_coverage(db: AsyncSession, since: datetime) -> dict:
    """Поисковый спрос против покрытия: фразы Метрики (пришли), запросы
    Вебмастера (показы/клики/позиция) и внутренние поиски без результата
    (пробелы каталога) — приоритизированная карта «что добавить»."""
    metrika = (await db.execute(
        select(MetrikaSearchPhrase.phrase,
               func.sum(MetrikaSearchPhrase.visits))
        .where(MetrikaSearchPhrase.date >= since.date())
        .group_by(MetrikaSearchPhrase.phrase)
        .order_by(func.sum(MetrikaSearchPhrase.visits).desc())
        .limit(30)
    )).all()

    webmaster = (await db.execute(
        select(WebmasterSearchQuery.query,
               func.sum(WebmasterSearchQuery.impressions),
               func.sum(WebmasterSearchQuery.clicks),
               func.avg(WebmasterSearchQuery.position))
        .where(WebmasterSearchQuery.date >= since.date())
        .group_by(WebmasterSearchQuery.query)
        .order_by(func.sum(WebmasterSearchQuery.impressions).desc())
        .limit(30)
    )).all()

    return {
        "metrika_phrases": [
            {"phrase": p, "visits": int(v or 0)} for p, v in metrika
        ],
        "webmaster_queries": [
            {
                "query": q,
                "impressions": int(i or 0),
                "clicks": int(c or 0),
                "avg_position": round(float(pos), 1) if pos is not None else None,
            }
            for q, i, c, pos in webmaster
        ],
    }


async def _onsite_search(db: AsyncSession, since: datetime) -> dict:
    """Все внутренние поиски сайта: единое событие search_query{q, results,
    context} + поиск сравнения. Zero-results = карта пробелов каталога."""
    rows = (await db.execute(
        select(FrontendEvent.event_name, FrontendEvent.params_json)
        .where(FrontendEvent.event_name.in_(("search_query", "compare_search")),
               FrontendEvent.occurred_at >= since)
        .order_by(FrontendEvent.occurred_at.desc())
        .limit(20000)
    )).all()

    by_context: dict[str, Counter] = defaultdict(Counter)
    zero: Counter = Counter()
    total = 0
    for name, params in rows:
        if not isinstance(params, dict):
            continue
        q = str(params.get("q") or params.get("query") or "").strip().lower()
        if not q:
            continue
        total += 1
        ctx = str(params.get("context") or ("compare-macro" if name == "compare_search" else "global"))
        by_context[ctx][q] += 1
        try:
            if int(params.get("results", -1)) == 0:
                zero[q] += 1
        except (TypeError, ValueError):
            pass

    return {
        "total_queries": total,
        "by_context": {
            ctx: dict(counter.most_common(15)) for ctx, counter in by_context.items()
        },
        "zero_results": dict(zero.most_common(25)),
    }


async def _navigation_graph(db: AsyncSession, since: datetime) -> dict:
    """Граф внутренней навигации из pageview-потока behavior.js: топ переходов
    страница → страница, входы и «тупики» (страницы без продолжения)."""
    rows = (await db.execute(
        select(BehaviorEvent.session_id_hash, BehaviorEvent.page,
               BehaviorEvent.occurred_at)
        .where(BehaviorEvent.event_type == "pageview",
               BehaviorEvent.occurred_at >= since,
               BehaviorEvent.session_id_hash.isnot(None))
        .order_by(BehaviorEvent.session_id_hash, BehaviorEvent.occurred_at)
        .limit(100000)
    )).all()

    transitions: Counter = Counter()
    entries: Counter = Counter()
    exits: Counter = Counter()
    prev_session, prev_page = None, None
    for session, page, _ts in rows:
        if not page:
            continue
        if session != prev_session:
            entries[page] += 1
            if prev_page is not None:
                exits[prev_page] += 1
        elif prev_page and prev_page != page:
            transitions[(prev_page, page)] += 1
        prev_session, prev_page = session, page
    if prev_page is not None:
        exits[prev_page] += 1

    return {
        "top_transitions": [
            {"from": a, "to": b, "count": c}
            for (a, b), c in transitions.most_common(30)
        ],
        "top_entries": dict(entries.most_common(15)),
        "top_exits": dict(exits.most_common(15)),
    }


async def _activity_heatmap(db: AsyncSession, since: datetime,
                            window_visits: list[RawMetrikaVisit] | None = None) -> list[dict]:
    """Пульс недели: активность по (день недели × час МСК) из ДВУХ слоёв.

    count — просмотры собственного потока behavior.js (живёт с 2026-07-04);
    visits — визиты Метрики по точному времени начала визита (история глубже).
    Вместе сетка заполнена даже там, куда собственный слой ещё не дотянулся.
    """
    rows = (await db.execute(
        select(BehaviorEvent.occurred_at)
        .where(BehaviorEvent.event_type == "pageview",
               BehaviorEvent.occurred_at >= since)
        .limit(200000)
    )).scalars().all()
    grid: Counter = Counter()
    for ts in rows:
        if ts is None:
            continue
        msk = ts + timedelta(hours=3)  # UTC → МСК
        grid[(msk.weekday(), msk.hour)] += 1

    # Слой Метрики: ym:s:dateTime уже в таймзоне счётчика (МСК).
    visits_grid: Counter = Counter()
    for v in window_visits or []:
        raw_dt = _visit_field(v, "ym:s:dateTime")
        if not raw_dt:
            continue
        try:
            dt = datetime.fromisoformat(raw_dt)
        except ValueError:
            continue
        visits_grid[(dt.weekday(), dt.hour)] += 1

    keys = sorted(set(grid) | set(visits_grid))
    return [
        {"dow": dow, "hour": hour, "count": grid.get((dow, hour), 0),
         "visits": visits_grid.get((dow, hour), 0)}
        for dow, hour in keys
    ]


async def _content_structure(db: AsyncSession, since: datetime) -> dict:
    """Структура потребления контента: раздел → просмотры + топ страниц внутри.
    Treemap-витрина: видно, какие продуктовые блоки несут трафик."""
    rows = (await db.execute(
        select(BehaviorEvent.page, func.count(BehaviorEvent.id))
        .where(BehaviorEvent.event_type == "pageview",
               BehaviorEvent.occurred_at >= since)
        .group_by(BehaviorEvent.page)
    )).all()
    sections: dict[str, dict[str, Any]] = defaultdict(lambda: {"views": 0, "pages": Counter()})
    for page, cnt in rows:
        if not page:
            continue
        sec = _page_section(page.split("?")[0])
        sections[sec]["views"] += cnt
        sections[sec]["pages"][page.split("?")[0]] += cnt
    return {
        "sections": [
            {
                "name": name,
                "views": s["views"],
                "top_pages": [
                    {"page": p, "views": v} for p, v in s["pages"].most_common(5)
                ],
            }
            for name, s in sorted(sections.items(), key=lambda kv: -kv[1]["views"])
        ],
    }


async def _audience(db: AsyncSession, since: datetime,
                    window_visits: list[RawMetrikaVisit]) -> dict:
    """Портрет аудитории из СОБСТВЕННЫХ данных (behavior_sessions) со сверкой
    с Метрикой. Директива владельца 2026-07-05: знать про посетителей всё —
    браузер, ОС, устройство, экран, язык, таймзону, источник — своими силами;
    Метрика — референс для сверки, не единственный источник.
    """
    from app.models import BehaviorSession

    sessions = (await db.execute(
        select(BehaviorSession).where(BehaviorSession.started_at >= since)
    )).scalars().all()

    browsers: Counter = Counter()
    browser_versions: Counter = Counter()
    oses: Counter = Counter()
    devices: Counter = Counter()
    screens: Counter = Counter()
    viewports: Counter = Counter()
    languages: Counter = Counter()
    timezones: Counter = Counter()
    ref_hosts: Counter = Counter()
    authed_count = 0

    for s in sessions:
        if s.device_type == "bot":
            continue
        browsers[s.browser or "Неизвестен"] += 1
        if s.browser and s.browser_version:
            browser_versions[f"{s.browser} {s.browser_version}"] += 1
        oses[(s.os or "Неизвестна") + (f" {s.os_version}" if s.os_version else "")] += 1
        devices[s.device_type or "unknown"] += 1
        if s.screen_w and s.screen_h:
            screens[f"{s.screen_w}×{s.screen_h}"] += 1
        if s.viewport_w:
            viewports[f"{s.viewport_w}px"] += 1
        if s.language:
            languages[s.language] += 1
        if s.timezone:
            timezones[s.timezone] += 1
        if s.referrer_host:
            ref_hosts[s.referrer_host] += 1
        if s.authed:
            authed_count += 1

    # Референс Метрики для сверки: устройства/браузеры из повизитного сырья.
    m_devices: Counter = Counter()
    m_browsers: Counter = Counter()
    m_os: Counter = Counter()
    for v in window_visits:
        dev = _visit_device(v)
        if dev:
            m_devices[dev] += 1
        br = _visit_browser(v)
        if br:
            m_browsers[br] += 1
        osr = _visit_os(v)
        if osr:
            m_os[osr] += 1

    total = sum(devices.values())
    return {
        "own_sessions_total": total,
        "own_authed_sessions": authed_count,
        "browsers": dict(browsers.most_common(12)),
        "browser_versions": dict(browser_versions.most_common(15)),
        "os": dict(oses.most_common(12)),
        "devices": dict(devices.most_common()),
        "screens": dict(screens.most_common(12)),
        "viewports": dict(viewports.most_common(10)),
        "languages": dict(languages.most_common(10)),
        "timezones": dict(timezones.most_common(10)),
        "referrer_hosts": dict(ref_hosts.most_common(12)),
        "metrika_reference": {
            "visits_total": len(window_visits),
            "devices": dict(m_devices.most_common()),
            "browsers": dict(m_browsers.most_common(12)),
            "os": dict(m_os.most_common(10)),
        },
    }


async def _behavior_issues(db: AsyncSession, since: datetime) -> dict:
    """Проблемные элементы UI: dead- и rage-клики по element_path."""
    out = {}
    for flag, key in ((BehaviorEvent.is_dead, "dead"), (BehaviorEvent.is_rage, "rage")):
        rows = (await db.execute(
            select(BehaviorEvent.page, BehaviorEvent.element_path,
                   func.count(BehaviorEvent.id))
            .where(BehaviorEvent.event_type == "click", flag.is_(True),
                   BehaviorEvent.occurred_at >= since)
            .group_by(BehaviorEvent.page, BehaviorEvent.element_path)
            .order_by(func.count(BehaviorEvent.id).desc())
            .limit(20)
        )).all()
        out[key] = [
            {"page": p, "element": e, "count": c} for p, e, c in rows
        ]
    return out


async def _events_breakdown(db: AsyncSession, since: datetime) -> dict:
    """Все бизнес-события за окно: имя → счётчик, разрез гость/зарегистрированный."""
    rows = (await db.execute(
        select(FrontendEvent.event_name, FrontendEvent.authed,
               func.count(FrontendEvent.id))
        .where(FrontendEvent.occurred_at >= since)
        .group_by(FrontendEvent.event_name, FrontendEvent.authed)
    )).all()
    agg: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "authed": 0, "guest": 0})
    for name, authed, cnt in rows:
        agg[name]["total"] += cnt
        agg[name]["authed" if authed else "guest"] += cnt
    return {
        name: v for name, v in sorted(agg.items(), key=lambda kv: -kv[1]["total"])
    }


async def _hypotheses(db: AsyncSession) -> list[dict]:
    rows = (await db.execute(
        select(Hypothesis).order_by(Hypothesis.updated_at.desc()).limit(50)
    )).scalars().all()
    return [
        {
            "id": h.id,
            "statement": h.statement,
            "rationale": h.rationale,
            "verdict": h.verdict,
            "confidence": float(h.confidence) if h.confidence is not None else None,
            "source": h.source,
            "updated_at": h.updated_at.isoformat() if h.updated_at else None,
        }
        for h in rows
    ]


async def _users_summary(db: AsyncSession, since: datetime) -> dict:
    total = await db.scalar(select(func.count(User.id))) or 0
    new = await db.scalar(
        select(func.count(User.id)).where(User.created_at >= since)
    ) or 0
    return {"total": total, "new_in_window": new}


async def build_bi_dashboard(db: AsyncSession, days: int = 30) -> dict[str, Any]:
    """Полный BI-снапшот. Тяжёлая функция — вызывать только через кэш (15 мин)."""
    days = max(1, min(days, 365))
    since = datetime.utcnow() - timedelta(days=days)

    # Сырые визиты окна — общая основа привлечения и воронки.
    window_visits = list((await db.execute(
        select(RawMetrikaVisit).where(RawMetrikaVisit.visit_date >= since.date())
    )).scalars().all())
    # Retention считаем по всей истории визитов (когорты глубже окна).
    all_visits = list((await db.execute(select(RawMetrikaVisit))).scalars().all())

    reg_rows = (await db.execute(
        select(func.date(User.created_at), func.count(User.id))
        .where(User.created_at >= since)
        .group_by(func.date(User.created_at))
    )).all()
    registrations_by_day = {str(d): c for d, c in reg_rows}

    from app.services.dataset_inventory import build_inventory

    dashboard: dict[str, Any] = {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
        "window_days": days,
        "users": await _users_summary(db, since),
        "kpi_daily": await _kpi_daily(db, since),
        "acquisition": _acquisition(window_visits),
        "funnel": _funnel(window_visits, registrations_by_day),
        "retention": _retention(all_visits),
        "pages": await _pages_quality(db, since),
        "demand": await _demand_vs_coverage(db, since),
        "onsite_search": await _onsite_search(db, since),
        "navigation": await _navigation_graph(db, since),
        "activity_heatmap": await _activity_heatmap(db, since, window_visits),
        "content_structure": await _content_structure(db, since),
        "audience": await _audience(db, since, window_visits),
        "behavior_issues": await _behavior_issues(db, since),
        "events": await _events_breakdown(db, since),
        "hypotheses": await _hypotheses(db),
        "dataset": await build_inventory(db),
    }
    return dashboard

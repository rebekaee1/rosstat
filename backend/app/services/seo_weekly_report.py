"""Недельный SEO-отчёт в Telegram (круг 13, SEO6). Выключен флагом ``seo_weekly_report_enabled``.

Показывает за последнюю полную неделю данных против предыдущей: показы, клики,
долю кликов и среднюю позицию (Яндекс по хостам, Google), ошибки sitemap и
состояние данных Вебмастера, долю ответов 5xx поисковым роботам.

Данные поисковых систем приходят с лагом 2–3 суток, поэтому окно считается от
последнего дня, за который они есть, а не от сегодняшнего. Если последний день
старше трёх суток, отчёт прямо говорит об этом: молчащий API не должен выглядеть
как «всё без изменений».

Ответы роботам считает приложение (``record_bot_status`` из middleware) и
видит только то, что дошло до backend: 429 и 502/504, которые отдал nginx, сюда
не попадают (их показывает ``deploy/crawler-status.sh`` на хосте).
"""
from __future__ import annotations

import logging
import re
from datetime import date, timedelta

from sqlalchemy import text

from app.config import settings
from app.database import analytics_session
from app.services.display import today_msk

logger = logging.getLogger(__name__)

_BOT_RE = (
    ("googlebot", re.compile(r"googlebot|google-inspectiontool|googleother", re.I)),
    ("yandex", re.compile(r"yandex(?:bot|mobilebot|images|renderresourcesbot|webmaster)", re.I)),
    ("bing", re.compile(r"bingbot", re.I)),
)
BOT_KEYS_TTL_S = 45 * 24 * 3600
STALE_AFTER_DAYS = 3


def bot_family(ua: str | None) -> str | None:
    if not ua:
        return None
    for name, rx in _BOT_RE:
        if rx.search(ua):
            return name
    return None


def bot_redis_key(day: date) -> str:
    return f"seo:bots:{day.isoformat()}"


async def record_bot_status(ua: str | None, status: int) -> None:
    """Счётчик ответов поисковым роботам по дням (hash: «семейство:класс» → число)."""
    if not settings.seo_weekly_report_enabled:
        return
    family = bot_family(ua)
    if family is None:
        return
    try:
        from app.core.cache import get_redis

        redis = await get_redis()
        key = bot_redis_key(today_msk())
        await redis.hincrby(key, f"{family}:{status // 100}xx", 1)
        await redis.expire(key, BOT_KEYS_TTL_S)
    except Exception:
        logger.debug("bot status counter failed", exc_info=True)


def pct(part: float, whole: float) -> float:
    return 100.0 * part / whole if whole else 0.0


def delta_text(cur: float, prev: float, *, digits: int = 0, suffix: str = "") -> str:
    if prev in (None, 0):
        return ""
    ch = 100.0 * (cur - prev) / prev
    sign = "+" if ch >= 0 else "−"
    return f" ({sign}{abs(ch):.0f}%)"


def _fmt_int(n) -> str:
    return f"{int(round(n or 0)):,}".replace(",", " ")


def week_windows(last_day: date) -> tuple[tuple[date, date], tuple[date, date]]:
    cur_to = last_day
    cur_from = last_day - timedelta(days=6)
    prev_to = cur_from - timedelta(days=1)
    prev_from = prev_to - timedelta(days=6)
    return (cur_from, cur_to), (prev_from, prev_to)


async def _query_window(db, table: str, host_clause: str, window: tuple[date, date]) -> dict:
    sql = text(
        f"SELECT COALESCE(SUM(impressions),0) AS imp, COALESCE(SUM(clicks),0) AS clk, "
        f"COALESCE(SUM(position*impressions)/NULLIF(SUM(impressions),0),0) AS pos "
        f"FROM {table} WHERE date BETWEEN :a AND :b {host_clause}"
    )
    row = (await db.execute(sql, {"a": window[0], "b": window[1]})).one()
    return {"imp": float(row.imp), "clk": float(row.clk), "pos": float(row.pos)}


async def collect_seo_week(today: date | None = None) -> dict:
    today = today or today_msk()
    out: dict = {"today": today, "yandex": {}, "google": None, "sitemap": {}, "bots": {}}
    async with analytics_session() as db:
        last_ya = (await db.execute(text("SELECT MAX(date) FROM webmaster_search_queries"))).scalar()
        last_g = (await db.execute(text("SELECT MAX(date) FROM gsc_search_queries"))).scalar()
        out["last_yandex_day"], out["last_google_day"] = last_ya, last_g
        if last_ya:
            cur_w, prev_w = week_windows(last_ya)
            out["yandex_window"] = cur_w
            for label, like in (("ru.", "%ru.forecasteconomy.com%"), (".com", None)):
                if like:
                    clause = "AND host LIKE '%ru.forecasteconomy.com%'"
                else:
                    clause = "AND host NOT LIKE '%ru.forecasteconomy.com%'"
                out["yandex"][label] = (
                    await _query_window(db, "webmaster_search_queries", clause, cur_w),
                    await _query_window(db, "webmaster_search_queries", clause, prev_w),
                )
        if last_g:
            cur_w, prev_w = week_windows(last_g)
            out["google_window"] = cur_w
            out["google"] = (
                await _query_window(db, "gsc_search_queries", "", cur_w),
                await _query_window(db, "gsc_search_queries", "", prev_w),
            )
        rows = (await db.execute(text(
            "SELECT DISTINCT ON (host) host, day, sitemap_errors, in_search FROM webmaster_indexing_daily "
            "WHERE sitemap_errors IS NOT NULL ORDER BY host, day DESC"
        ))).all()
        out["sitemap"] = {r.host: (r.day, int(r.sitemap_errors), r.in_search) for r in rows}
        last_run = (await db.execute(text(
            "SELECT status, started_at, left(coalesce(error_message,''),120) AS err FROM analytics_sync_runs "
            "WHERE source='yandex_webmaster' ORDER BY id DESC LIMIT 1"
        ))).first()
        out["webmaster_last_run"] = tuple(last_run) if last_run else None
    try:
        from app.core.cache import get_redis

        redis = await get_redis()
        for offset in range(7):
            raw = await redis.hgetall(bot_redis_key(today - timedelta(days=offset)))
            for k, v in (raw or {}).items():
                k = k.decode() if isinstance(k, bytes) else k
                fam, cls = k.split(":", 1)
                out["bots"].setdefault(fam, {}).setdefault(cls, 0)
                out["bots"][fam][cls] += int(v)
    except Exception:
        logger.warning("bot counters unavailable", exc_info=True)
    return out


def _engine_line(label: str, cur: dict, prev: dict) -> str:
    ctr = pct(cur["clk"], cur["imp"])
    ctr_prev = pct(prev["clk"], prev["imp"])
    pos = f", позиция {cur['pos']:.1f}" if cur["pos"] else ""
    return (
        f"{label}: показы {_fmt_int(cur['imp'])}{delta_text(cur['imp'], prev['imp'])}, "
        f"клики {_fmt_int(cur['clk'])}{delta_text(cur['clk'], prev['clk'])}, "
        f"доля кликов {ctr:.2f}% (было {ctr_prev:.2f}%){pos}"
    )


def format_seo_week(data: dict) -> str:
    today: date = data["today"]
    lines = ["<b>SEO за неделю</b>"]
    stale_notes: list[str] = []
    ya_day, g_day = data.get("last_yandex_day"), data.get("last_google_day")
    if data.get("yandex"):
        a, b = data["yandex_window"]
        lines.append(f"\n<b>Яндекс</b> ({a:%d.%m}–{b:%d.%m})")
        for label, (cur, prev) in data["yandex"].items():
            lines.append(_engine_line(label, cur, prev))
    if ya_day is None or (today - ya_day).days > STALE_AFTER_DAYS:
        stale_notes.append(f"данные запросов Яндекса последние за {ya_day:%d.%m}" if ya_day else "данных запросов Яндекса нет")
    if data.get("google"):
        a, b = data["google_window"]
        cur, prev = data["google"]
        lines.append(f"\n<b>Google</b> ({a:%d.%m}–{b:%d.%m})")
        lines.append(_engine_line("Все страницы", cur, prev))
    if g_day is None or (today - g_day).days > STALE_AFTER_DAYS:
        stale_notes.append(f"данные Google последние за {g_day:%d.%m}" if g_day else "данных Google нет")
    if data.get("sitemap"):
        lines.append("\n<b>Ошибки sitemap (Вебмастер)</b>")
        for host, (day, errors, in_search) in sorted(data["sitemap"].items()):
            label = host.replace("https:", "").replace(":443", "")
            ins = f", в поиске {_fmt_int(in_search)}" if in_search else ""
            lines.append(f"{label}: {_fmt_int(errors)} на {day:%d.%m}{ins}")
    run = data.get("webmaster_last_run")
    if run and run[0] == "failed":
        stale_notes.append(f"последний синк Вебмастера {run[1]:%d.%m} упал: {run[2]}")
    bots = data.get("bots") or {}
    if bots:
        lines.append("\n<b>Ответы роботам (по данным приложения)</b>")
        for fam in ("googlebot", "yandex", "bing"):
            c = bots.get(fam)
            if not c:
                continue
            total = sum(c.values())
            err = c.get("5xx", 0)
            lines.append(f"{fam}: {_fmt_int(total)} ответов, 5xx — {err} ({pct(err, total):.2f}%)")
        lines.append("429 и 502/504 уровня nginx здесь не видны: deploy/crawler-status.sh на хосте.")
    if stale_notes:
        lines.append("\n⚠️ " + "; ".join(stale_notes) + ". Отсутствие данных не означает ноль.")
    return "\n".join(lines)


async def build_seo_weekly_report(today: date | None = None) -> str:
    return format_seo_week(await collect_seo_week(today))


async def seo_weekly_report_job() -> None:
    """Понедельник, после индексного отчёта. Выключен флагом ``seo_weekly_report_enabled``."""
    if not settings.seo_weekly_report_enabled:
        return
    if not (settings.telegram_bot_token and settings.telegram_chat_id):
        return
    from app.services.alerting import send_telegram

    text_ = await build_seo_weekly_report()
    await send_telegram(text_, kind="weekly_report")
    logger.info("SEO weekly report sent")

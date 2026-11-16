"""Счётчик Telegram-канала: подписчики по дням и просмотры постов (17.11.2026, ADR-0035).

До этого числа канала нигде не записывались: 16.11.2026 их снимали руками. Здесь — раз в сутки и только чтение:

* подписчики — `getChatMemberCount` (Bot API отдаёт число открытого канала любому боту, права администратора не нужны);
* просмотры — открытая страница `https://t.me/<канал>/<номер>?embed=1`, счётчик в `tgme_widget_message_views`
  (в Bot API поля с просмотрами нет). Лента `t.me/s/<канал>` у маленького канала не открывается, поэтому идём по
  номерам: заново снимаем последние известные посты и пробуем следующие номера, пока подряд не встретим пустые.

Счётчик Telegram приблизительный и считает повторные просмотры примерно через 4 дня (telegram.org/faq_channels),
поэтому просмотров бывает больше, чем подписчиков. Сбой сети ничего не ломает: строка в сводке просто не выводится.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import date, datetime, timedelta, timezone

import httpx
from sqlalchemy import func, select, text

from app.config import settings

logger = logging.getLogger(__name__)

MSK = timezone(timedelta(hours=3))
KIND = "channel_stats"
_VIEWS_RE = re.compile(r'tgme_widget_message_views">([^<]+)<')
_TIME_RE = re.compile(r'<time[^>]*datetime="([^"]+)"')
_MISSING = "tgme_widget_message_error"
RECHECK_LAST = 15       # столько последних известных постов снимаем заново (просмотры растут несколько дней)
PROBE_MISSES = 6        # столько пустых номеров подряд означают конец канала (в истории были дыры в 1–2 номера)
PROBE_MAX = 60          # потолок новых номеров за один запуск
PAUSE_S = 0.7


def channel_username() -> str | None:
    """Имя канала без @ — для адреса t.me. Числовой id открытой страницы не даёт."""
    cid = (settings.channel_chat_id or "").strip()
    return cid[1:] if cid.startswith("@") and len(cid) > 1 else None


def channel_token() -> str:
    return settings.channel_bot_token or settings.telegram_bot_token


def parse_views(raw: str) -> int | None:
    """«28», «1.2K», «3.4M» → число."""
    s = (raw or "").strip().replace(",", ".").upper()
    m = re.fullmatch(r"(\d+(?:\.\d+)?)([KM]?)", s)
    if not m:
        return None
    return int(round(float(m.group(1)) * {"": 1, "K": 1_000, "M": 1_000_000}[m.group(2)]))


def parse_embed(html: str) -> tuple[int, datetime | None] | None:
    """Страница поста → (просмотры, время публикации UTC). None — поста с таким номером нет или счётчика нет
    (служебное сообщение канала)."""
    if not html or _MISSING in html:
        return None
    m = _VIEWS_RE.search(html)
    if not m:
        return None
    views = parse_views(m.group(1))
    if views is None:
        return None
    posted = None
    t = _TIME_RE.search(html)
    if t:
        try:
            posted = datetime.fromisoformat(t.group(1)).astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError:
            posted = None
    return views, posted


async def fetch_subscribers() -> int | None:
    from app.services.telegram_bot import _api

    if not (channel_token() and settings.channel_chat_id):
        return None
    data = await _api("getChatMemberCount", {"chat_id": settings.channel_chat_id}, token=channel_token())
    try:
        return int(data["result"]) if data else None
    except (KeyError, TypeError, ValueError):
        return None


async def _fetch_post(client: httpx.AsyncClient, username: str, message_id: int) -> tuple[int, datetime | None] | None | bool:
    """(просмотры, время) — пост есть; None — номера нет; False — страница не ответила (не считать пустым номером)."""
    try:
        resp = await client.get(f"https://t.me/{username}/{message_id}", params={"embed": "1"})
    except httpx.HTTPError as exc:
        logger.info("channel stats: t.me не ответил на %s: %s", message_id, exc)
        return False
    if resp.status_code != 200:
        return False
    return parse_embed(resp.text)


async def collect_views(known_ids: list[int]) -> dict[int, tuple[int, datetime | None]]:
    """Просмотры последних известных постов и новых номеров после них."""
    username = channel_username()
    if not username:
        return {}
    out: dict[int, tuple[int, datetime | None]] = {}
    known = sorted(set(known_ids))
    start = (known[-1] + 1) if known else 1
    async with httpx.AsyncClient(
        timeout=15, proxy=settings.telegram_proxy_url or None, trust_env=False,
        headers={"User-Agent": "Mozilla/5.0 (compatible; ForecastEconomyBot/1.0)"}, follow_redirects=False,
    ) as client:
        for mid in known[-RECHECK_LAST:]:
            got = await _fetch_post(client, username, mid)
            if got is False:
                return out  # сеть не отвечает — не тратим время на остальные номера
            if got:
                out[mid] = got
            await asyncio.sleep(PAUSE_S)
        misses = 0
        for mid in range(start, start + PROBE_MAX):
            got = await _fetch_post(client, username, mid)
            if got is False:
                break
            if got:
                out[mid] = got
                misses = 0
            else:
                misses += 1
                if misses >= PROBE_MISSES:
                    break
            await asyncio.sleep(PAUSE_S)
    return out


async def channel_stats_job(today: date | None = None) -> dict:
    """Раз в сутки: число подписчиков и просмотры постов в таблицы счётчика."""
    from app.database import async_session
    from app.models import ChannelPost, ChannelPostView, ChannelStatsDaily

    if not settings.channel_stats_enabled:
        return {"skipped": "disabled"}
    today = today or datetime.now(MSK).date()
    result: dict = {"day": today.isoformat()}
    subs = await fetch_subscribers()
    async with async_session() as db:
        if subs is not None:
            row = await db.get(ChannelStatsDaily, today)
            if row is None:
                db.add(ChannelStatsDaily(day=today, subscribers=subs))
            else:
                row.subscribers = subs
                row.taken_at = datetime.now(timezone.utc).replace(tzinfo=None)
            result["subscribers"] = subs
        known = [r[0] for r in (await db.execute(select(ChannelPostView.message_id).distinct())).all()]
        known += [r[0] for r in (await db.execute(
            select(ChannelPost.telegram_message_id).where(ChannelPost.telegram_message_id.is_not(None)))).all()]
        await db.commit()
    views = await collect_views(known)
    if views:
        async with async_session() as db:
            for mid, (count, posted) in views.items():
                row = (await db.execute(select(ChannelPostView).where(
                    ChannelPostView.message_id == mid, ChannelPostView.day == today))).scalar_one_or_none()
                if row is None:
                    db.add(ChannelPostView(message_id=mid, day=today, views=count, posted_at=posted))
                else:
                    row.views = count
            await db.commit()
    result["posts"] = len(views)
    logger.info("channel stats: %s", result)
    return result


async def latest_views(db, limit: int = 12) -> list[dict]:
    """Последние посты канала с самым свежим снятием просмотров: [{message_id, views, posted_at}] от нового к старому."""
    from app.models import ChannelPostView

    last_day = (
        select(ChannelPostView.message_id, func.max(ChannelPostView.day).label("day"))
        .group_by(ChannelPostView.message_id).subquery()
    )
    rows = (await db.execute(
        select(ChannelPostView.message_id, ChannelPostView.views, ChannelPostView.posted_at)
        .join(last_day, (last_day.c.message_id == ChannelPostView.message_id) & (last_day.c.day == ChannelPostView.day))
        .order_by(ChannelPostView.message_id.desc()).limit(limit)
    )).all()
    return [{"message_id": r[0], "views": r[1], "posted_at": r[2]} for r in rows]


async def subscribers_trend(db, today: date) -> tuple[int, int | None] | None:
    """(подписчиков сейчас, изменение за 7 дней или None, если недели наблюдений ещё нет)."""
    from app.models import ChannelStatsDaily

    last = (await db.execute(
        select(ChannelStatsDaily.day, ChannelStatsDaily.subscribers)
        .where(ChannelStatsDaily.day >= today - timedelta(days=3))
        .order_by(ChannelStatsDaily.day.desc()).limit(1))).first()
    if last is None:
        return None
    before = (await db.execute(
        select(ChannelStatsDaily.subscribers)
        .where(ChannelStatsDaily.day <= last[0] - timedelta(days=7))
        .order_by(ChannelStatsDaily.day.desc()).limit(1))).scalar_one_or_none()
    return last[1], (last[1] - before) if before is not None else None


async def site_visits_from_channel(db, days: int = 7) -> int | None:
    """Заходы на сайт по ссылкам с меткой канала (`utm_medium=channel`) за N дней; None — посчитать не удалось."""
    try:
        if db.get_bind().dialect.name != "postgresql":
            return None
        return int((await db.execute(text(
            "select count(*) from server_sessions where day >= current_date - :d and not is_bot "
            "and not coalesce(is_internal, false) and entry_page like '%utm_medium=channel%'"
        ), {"d": days})).scalar() or 0)
    except Exception:  # noqa: BLE001 — счётчик не должен ронять сводку
        logger.info("channel stats: заходы из канала не посчитаны", exc_info=True)
        return None


def _plural(n: int, one: str, few: str, many: str) -> str:
    n10, n100 = abs(n) % 10, abs(n) % 100
    if n10 == 1 and n100 != 11:
        return one
    if 2 <= n10 <= 4 and not 12 <= n100 <= 14:
        return few
    return many


def summary_line(trend: tuple[int, int | None] | None, views: list[dict], visits: int | None) -> str | None:
    """Одна строка для утренней сводки владельца. Без технических слов."""
    if trend is None:
        return None
    subs, delta = trend
    bits = [f"{subs} {_plural(subs, 'подписчик', 'подписчика', 'подписчиков')}"
            + (f" ({'+' if delta > 0 else ''}{delta} за неделю)" if delta else
               (" (за неделю без изменений)" if delta == 0 else ""))]
    if views:
        v = views[0]["views"]
        bits.append(f"последний пост — {v} {_plural(v, 'просмотр', 'просмотра', 'просмотров')}")
    if visits:
        bits.append(f"на сайт из канала за неделю — {visits} {_plural(visits, 'заход', 'захода', 'заходов')}")
    return "<b>Канал:</b> " + "; ".join(bits) + "."


async def morning_line() -> str | None:
    """Строка канала для утренней сводки; при выключенном счётчике или сбое — ничего."""
    from app.database import async_session

    if not settings.channel_stats_enabled:
        return None
    try:
        today = datetime.now(MSK).date()
        async with async_session() as db:
            trend = await subscribers_trend(db, today)
            views = await latest_views(db, limit=1)
            visits = await site_visits_from_channel(db)
        return summary_line(trend, views, visits)
    except Exception:  # noqa: BLE001
        logger.warning("channel stats: строка сводки не собрана", exc_info=True)
        return None

from __future__ import annotations

import logging
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from html import escape

from sqlalchemy import delete, func, select

from app.config import settings
from app.database import async_session
from app.models import BehaviorEvent, Consent, EmailCredential, FrontendEvent, OAuthIdentity, User
from app.services.alerting import send_telegram_digest
from app.services.analytics_ingestion import (
    finish_sync_run,
    start_sync_run,
    store_counter_snapshot,
    store_metrika_report_snapshot,
)
from app.services.yandex_metrika_management import MetrikaManagementClient
from app.services.yandex_metrika_reporting import MetrikaReportingClient

logger = logging.getLogger(__name__)


def _primary_counter_id() -> str:
    return settings.analytics_allowed_counter_ids.split(",")[0].strip()


async def analytics_hourly_job() -> None:
    if not settings.analytics_enabled:
        logger.info("Analytics hourly sync skipped: analytics disabled")
        return
    counter_id = _primary_counter_id()
    yesterday = date.today() - timedelta(days=1)
    async with async_session() as db:
        run = await start_sync_run(
            db,
            source="yandex_metrika",
            job_type="hourly_reporting_top_pages",
            date_from=yesterday,
            date_to=yesterday,
            metadata={"counter_id": counter_id},
        )
        await db.commit()
        try:
            client = MetrikaReportingClient()
            response = await client.table(
                counter_id=counter_id,
                metrics=["ym:s:visits", "ym:s:users", "ym:s:pageviews"],
                dimensions=["ym:s:startURL"],
                date_from=yesterday,
                date_to=yesterday,
                limit=100,
            )
            await store_metrika_report_snapshot(
                db,
                counter_id=counter_id,
                report_type="top_pages",
                query={"metrics": ["ym:s:visits", "ym:s:users", "ym:s:pageviews"], "dimensions": ["ym:s:startURL"]},
                response=response,
                date_from=yesterday,
                date_to=yesterday,
            )
            rows = len(response.data.get("data", [])) if isinstance(response.data, dict) else 0
            await finish_sync_run(db, run, records_processed=rows, request_hash=response.request_hash)
            await db.commit()
        except Exception as exc:
            logger.exception("Analytics hourly sync failed")
            await db.rollback()
            await finish_sync_run(db, run, status="failed", error_message=str(exc)[:500])
            await db.commit()


async def _user_stats_lines() -> list[str]:
    async with async_session() as db:
        total = await db.scalar(select(func.count(User.id))) or 0
        since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
        new_users = (await db.execute(
            select(User).where(User.created_at >= since).order_by(User.created_at.desc())
        )).scalars().all()
        newsletter = await db.scalar(
            select(func.count(func.distinct(Consent.user_id))).where(Consent.kind == "newsletter")
        ) or 0

        lines = [
            f"👤 Пользователи: всего {total}, +{len(new_users)} за сутки, "
            f"подписка на рассылку {newsletter}"
        ]
        if not new_users:
            return lines

        ids = [u.id for u in new_users]
        emails = dict((await db.execute(
            select(EmailCredential.user_id, EmailCredential.email)
            .where(EmailCredential.user_id.in_(ids))
        )).all())
        oauth_by_user: dict = {}
        for uid, provider, phone, oemail in (await db.execute(
            select(OAuthIdentity.user_id, OAuthIdentity.provider, OAuthIdentity.phone, OAuthIdentity.email)
            .where(OAuthIdentity.user_id.in_(ids))
        )).all():
            oauth_by_user.setdefault(uid, []).append((provider, phone, oemail))

    lines.append("🆕 <b>Новые за сутки:</b>")
    for u in new_users[:20]:
        oa = oauth_by_user.get(u.id) or []
        phone = next((ph for _, ph, _ in oa if ph), None)
        oemail = next((em for _, _, em in oa if em), None)
        providers = [p for p, _, _ in oa]
        contact = emails.get(u.id) or oemail or phone or "—"
        methods = (["почта"] if u.id in emails else []) + providers
        method = "/".join(methods) if methods else "—"
        name = u.display_name or "—"
        lines.append(f"• {escape(name)} — {escape(str(contact)[:48])} ({escape(method)})")
    return lines


async def _search_demand_lines(report_date: date) -> list[str]:
    """Спрос-аналитика поиска за день из FrontendEvent: что искали (введённое,
    выбранное, брошенное) + запросы с 0 результатов = пробелы в каталоге."""
    start = datetime.combine(report_date, time.min)
    end = start + timedelta(days=1)
    async with async_session() as db:
        rows = (await db.execute(
            select(FrontendEvent.event_name, FrontendEvent.params_json).where(
                FrontendEvent.event_name.in_(["search_query", "search_select", "search_abandon"]),
                FrontendEvent.occurred_at >= start,
                FrontendEvent.occurred_at < end,
            )
        )).all()

    queries: Counter[str] = Counter()
    no_results: Counter[str] = Counter()
    n_query = n_select = n_abandon = 0
    for name, params in rows:
        params = params or {}
        q = str(params.get("q") or "").strip().lower()
        if name == "search_select":
            n_select += 1
        elif name == "search_abandon":
            n_abandon += 1
        elif name == "search_query":
            n_query += 1
            if not q:
                continue
            queries[q] += 1
            try:
                if int(params.get("results", 0)) == 0:
                    no_results[q] += 1
            except (TypeError, ValueError):
                pass

    if not (n_query or n_select or n_abandon):
        return ["🔎 Поиск: запросов за день нет"]

    def _fmt(counter: Counter[str], limit: int = 10) -> str:
        return ", ".join(f"«{escape(q[:40])}» ×{c}" for q, c in counter.most_common(limit))

    lines = [f"🔎 <b>Поиск:</b> ввод {n_query}, выбрано {n_select}, брошено {n_abandon}"]
    if queries:
        lines.append("🔝 Топ запросов: " + _fmt(queries))
    if no_results:
        lines.append("🕳 Без результатов: " + _fmt(no_results))
    return lines


async def _metrika_goal_lines(report_date: date) -> list[str]:
    """Достижения всех целей счётчика за указанный день (для дайджеста CTA).

    Метрика /stat/v1/data принимает максимум 20 метрик на запрос, а целей у нас
    уже под 30 — поэтому цели запрашиваем батчами по 20 (иначе HTTP 400).
    """
    counter_id = _primary_counter_id()
    mgmt = MetrikaManagementClient()
    goals_resp = await mgmt.goals(counter_id)
    goals = (goals_resp.data or {}).get("goals") or []
    rep = MetrikaReportingClient()

    async def _totals(metrics: list[str]) -> list:
        r = await rep.table(
            counter_id=counter_id, metrics=metrics,
            date_from=report_date, date_to=report_date, limit=1,
        )
        # Метрика отдаёт totals плоским списком [m1, m2, ...] (одно число на метрику);
        # на всякий случай разворачиваем и вариант [[...]].
        totals = (r.data or {}).get("totals") or []
        if totals and isinstance(totals[0], list):
            totals = totals[0]
        return totals

    def _int(vals: list, i: int) -> int:
        return int(vals[i]) if len(vals) > i and vals[i] is not None else 0

    base = await _totals(["ym:s:visits", "ym:s:users"])
    lines = [f"🌐 Визиты {_int(base, 0)}, посетители {_int(base, 1)}"]

    goal_lines: list[str] = []
    CHUNK = 20  # лимит метрик Метрики на один запрос
    for start in range(0, len(goals), CHUNK):
        chunk = goals[start:start + CHUNK]
        tvals = await _totals([f"ym:s:goal{g['id']}reaches" for g in chunk])
        for i, g in enumerate(chunk):
            reaches = _int(tvals, i)
            if reaches:
                goal_lines.append(f"• {escape(str(g.get('name') or g['id']))}: {reaches}")
    if goal_lines:
        lines.append("🎯 <b>Цели (достижения за день):</b>")
        lines.extend(goal_lines)
    else:
        lines.append("🎯 Достижений целей за день нет")
    return lines


async def acquisition_daily_job() -> None:
    """Ежедневный сбор привлечения за вчера (08:20 МСК): агрегаты Reporting API
    (источники/поисковики/рефереры/кампании/фразы/страницы) + повизитная
    выгрузка Logs API в raw_metrika_visits. До Пульс-отчёта 09:05 — свежие
    данные привлечения уже в хранилище."""
    if not (settings.analytics_enabled and settings.yandex_metrika_read_token):
        logger.info("Acquisition sync skipped: analytics disabled or no token")
        return
    from app.services.metrika_acquisition import sync_acquisition_for_day
    yesterday = date.today() - timedelta(days=1)
    async with async_session() as db:
        out = await sync_acquisition_for_day(db, yesterday)
    logger.info("Acquisition sync %s: %s", yesterday, out)


async def webmaster_queries_daily_job() -> None:
    """Ежедневный синк популярных запросов Вебмастера (08:40 МСК).

    Тянем окно последних 7 дней: у API лаг 2–3 дня, повторный прогон
    идемпотентно дозаполняет дни, которые вчера ещё не отдавались.
    Кормит блок «Спрос и SEO» (webmaster_queries) в BI.
    """
    if not settings.yandex_webmaster_token:
        return
    from app.services.analytics_backfill import backfill_webmaster_search_queries
    today = date.today()
    async with async_session() as db:
        n = await backfill_webmaster_search_queries(
            db, date_from=today - timedelta(days=7), date_to=today - timedelta(days=1))
    logger.info("Webmaster search queries sync: %s rows", n)


async def behavior_retention_job() -> None:
    """Аварийный клапан по диску для сырого поведенческого потока (04:30 МСК).

    Стратегия владельца (2026-07-03): датасет накопительный, по умолчанию
    `behavior_raw_retention_days = 0` — НИЧЕГО не удаляем, копим под Big
    Data/ML. Ненулевое значение включает чистку только если диск начнёт
    заканчиваться (осознанное решение, не дефолт).
    """
    days = settings.behavior_raw_retention_days
    if not days:
        return
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    async with async_session() as db:
        res = await db.execute(delete(BehaviorEvent).where(BehaviorEvent.occurred_at < cutoff))
        await db.commit()
    logger.info("Behavior retention: deleted %s rows older than %s days", res.rowcount, days)


async def telegram_daily_digest_job() -> None:
    """Ежедневный Telegram-дайджест: пользователи БД + агрегированная статистика
    Метрики (визиты/посетители + достижения всех целей-CTA). ADR-0007 Phase 2."""
    if not (settings.telegram_bot_token and settings.telegram_chat_id):
        logger.info("Telegram digest skipped: bot token/chat not configured")
        return
    yesterday = date.today() - timedelta(days=1)
    parts = [f"📊 <b>Forecast Economy — дайджест за {yesterday.isoformat()}</b>"]
    try:
        parts += await _user_stats_lines()
    except Exception:
        logger.warning("Telegram digest: user stats failed", exc_info=True)
    try:
        parts += await _search_demand_lines(yesterday)
    except Exception:
        logger.warning("Telegram digest: search demand failed", exc_info=True)
    if settings.analytics_enabled and settings.yandex_metrika_read_token:
        try:
            parts += await _metrika_goal_lines(yesterday)
        except Exception:
            logger.warning("Telegram digest: Metrika part failed", exc_info=True)
            parts.append("⚠️ Статистика Метрики недоступна")
    else:
        parts.append("ℹ️ Метрика отключена (нет токена) — только статистика БД")
    try:
        from app.services.dataset_inventory import build_inventory, format_inventory_html
        async with async_session() as db:
            inv = await build_inventory(db)
        parts.append(format_inventory_html(inv))
    except Exception:
        logger.warning("Telegram digest: dataset inventory failed", exc_info=True)
    from app.services.telegram_bot import main_menu_keyboard
    results = await send_telegram_digest("\n".join(parts), reply_markup=main_menu_keyboard())
    logger.info("Telegram digest delivered: %s", results)


async def analytics_daily_job() -> None:
    if not settings.analytics_enabled:
        logger.info("Analytics daily sync skipped: analytics disabled")
        return
    counter_id = _primary_counter_id()
    async with async_session() as db:
        run = await start_sync_run(
            db,
            source="yandex_metrika",
            job_type="daily_management_snapshot",
            metadata={"counter_id": counter_id},
        )
        await db.commit()
        try:
            client = MetrikaManagementClient()
            response = await client.counter(counter_id, field=["goals", "filters", "operations", "grants"])
            await store_counter_snapshot(db, counter_id=counter_id, response=response)
            await finish_sync_run(db, run, records_processed=1, request_hash=response.request_hash)
            await db.commit()
        except Exception as exc:
            logger.exception("Analytics daily sync failed")
            await db.rollback()
            await finish_sync_run(db, run, status="failed", error_message=str(exc)[:500])
            await db.commit()

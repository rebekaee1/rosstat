"""Задачи планировщика персонального выпуска (ADR-0033). Регистрируются в `main.py` за флагами.

* `aggregates_job` — ночью (00:40 МСК): обезличенные таблицы «запрос → ряд» и «связанные ряды»,
  удаление снимков старше 180 дней;
* `build_job` — в четверг 07:40 МСК (после утреннего окна ETL 05:30–07:30): снимки личных выпусков
  по файлу выпуска редакции (`RUSTATS_NEWSLETTER_PERSONAL_ISSUE_PATH`), пакетами, с паузой при
  тормозящем диске; не успели к 08:20 — остальные получат сборку на лету или общий выпуск.
Ничего не отправляют.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from app.config import settings

logger = logging.getLogger(__name__)


async def aggregates_job() -> None:
    from app.database import async_session
    from app.services.newsletter_personal import store
    from app.services.newsletter_personal.build import _utcnow

    now = _utcnow()
    async with async_session() as db:
        if not await store.tables_ready(db):
            logger.info("newsletter aggregates: tables missing (migration not applied)")
            return
        q = await store.rebuild_query_map(db, now=now)
        r = await store.rebuild_related(db, now=now)
        purged = await store.purge_old(db, now=now)
        await db.commit()
    logger.info("newsletter aggregates: query_map=%d related=%d purged=%d", q, r, purged)


async def build_job() -> None:
    from app.database import async_session
    from app.services.mail import campaign
    from app.services.newsletter_personal.build import _utcnow, build_campaign

    paths = [p.strip() for p in (settings.newsletter_personal_issue_path or "").split(",") if p.strip()]
    if not paths:
        logger.info("newsletter build: no issue file configured")
        return
    try:
        issue = campaign.load_issue(*paths)
    except Exception as exc:  # noqa: BLE001
        logger.warning("newsletter build: issue file unreadable: %s", type(exc).__name__)
        return
    deadline = _utcnow() + timedelta(minutes=40)
    async with async_session() as db:
        report = await build_campaign(db, issue, persist=True, deadline=deadline)
    logger.info("newsletter build %s: %s", issue.key, report.as_dict())

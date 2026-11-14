"""Хранение персонального выпуска (ADR-0033): профили, снимки, обезличенные таблицы.

* `tables_ready` — таблицы миграции `20261115_newsletter_personal` есть (до миграции предпросмотр
  работает без них: история пустая, ничего не сохраняется);
* `save_profile` / `save_issue` — upsert по человеку и по (выпуск, человек);
* `rebuild_query_map` / `rebuild_related` — ночной пересчёт обезличенных таблиц по событиям всех
  посетителей (без связи с людьми, текст запросов не сохраняется);
* `purge_old` — снимки старше `SNAPSHOT_RETENTION_DAYS`.
"""
from __future__ import annotations

import logging
import math
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from itertools import combinations

from sqlalchemy import and_, delete, exists, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    BehaviorSession, FrontendEvent, NewsletterPersonalIssue, NewsletterProfile, NewsletterQueryMap,
    NewsletterRelated,
)

logger = logging.getLogger(__name__)

SNAPSHOT_RETENTION_DAYS = 180
QUERY_MAP_DAYS = 120
QUERY_MAP_MIN_SELECTS = 2
QUERY_MAP_MIN_SHARE = 0.5
RELATED_DAYS = 45
RELATED_MIN_VISITORS = 5
RELATED_PER_SUBJECT = 10
RELATED_MAX_PER_VISITOR = 30
MAX_ROWS = 300_000

_READY: dict[str, bool] = {}


async def tables_ready(db: AsyncSession) -> bool:
    url = str(db.bind.url) if db.bind is not None else ""
    if url in _READY:
        return _READY[url]

    def _check(conn) -> bool:
        names = set(inspect(conn).get_table_names())
        return {"newsletter_profiles", "newsletter_personal_issues", "newsletter_related",
                "newsletter_query_map"} <= names

    conn = await db.connection()
    ready = await conn.run_sync(_check)
    if ready:  # отсутствие не кэшируем: миграция может прийти во время работы процесса
        _READY[url] = True
    return ready


def reset_ready_cache() -> None:
    _READY.clear()


async def save_profile(db: AsyncSession, user_id: uuid.UUID, row: dict, *, version: int, now: datetime) -> None:
    obj = await db.get(NewsletterProfile, user_id)
    if obj is None:
        obj = NewsletterProfile(user_id=user_id)
        db.add(obj)
    obj.version = version
    obj.computed_at = now
    obj.tier = row["tier"]
    obj.locale = row["locale"]
    obj.timezone = row.get("timezone")
    obj.topics = row.get("topics")
    obj.subjects = row.get("subjects")
    obj.geo = row.get("geo")
    obj.stats = row.get("stats")


async def save_issue(db: AsyncSession, *, campaign: str, user_id: uuid.UUID, locale: str, arm: str,
                     subject_arm: str | None, tier: str, status: str, payload: dict | None,
                     blocks_meta: list | None, data_as_of, error: str | None, now: datetime) -> NewsletterPersonalIssue:
    obj = await db.scalar(select(NewsletterPersonalIssue).where(
        NewsletterPersonalIssue.campaign == campaign, NewsletterPersonalIssue.user_id == user_id))
    if obj is None:
        obj = NewsletterPersonalIssue(campaign=campaign, user_id=user_id)
        db.add(obj)
    obj.locale, obj.arm, obj.subject_arm, obj.tier, obj.status = locale, arm, subject_arm, tier, status
    obj.payload, obj.blocks_meta, obj.data_as_of, obj.error, obj.built_at = payload, blocks_meta, data_as_of, error, now
    return obj


async def load_issue(db: AsyncSession, campaign: str, user_id: uuid.UUID) -> NewsletterPersonalIssue | None:
    if not await tables_ready(db):
        return None
    return await db.scalar(select(NewsletterPersonalIssue).where(
        NewsletterPersonalIssue.campaign == campaign, NewsletterPersonalIssue.user_id == user_id))


async def purge_old(db: AsyncSession, *, now: datetime) -> int:
    res = await db.execute(delete(NewsletterPersonalIssue).where(
        NewsletterPersonalIssue.built_at < now - timedelta(days=SNAPSHOT_RETENTION_DAYS)))
    return int(res.rowcount or 0)


def _no_robot():
    return ~exists().where(and_(BehaviorSession.session_id_hash == FrontendEvent.session_id_hash,
                                BehaviorSession.is_webdriver.is_(True)))


async def rebuild_query_map(db: AsyncSession, *, now: datetime) -> int:
    """Хэш запроса → ряд, который по нему выбирают чаще всего (≥2 выбора и ≥половины выборов)."""
    from app.services.newsletter_personal.signals import q_hash
    from app.services.newsletter_personal.subjects import subjects_from_event

    rows = (await db.execute(
        select(FrontendEvent.params_json).where(
            FrontendEvent.event_name == "search_select",
            FrontendEvent.occurred_at >= now - timedelta(days=QUERY_MAP_DAYS), _no_robot())
        .limit(MAX_ROWS))).all()
    by_q: dict[str, Counter] = defaultdict(Counter)
    for (params,) in rows:
        if not isinstance(params, dict) or not isinstance(params.get("q"), str):
            continue
        _kind, subs = subjects_from_event("search_select", params)
        series = [s for s in subs if s.is_series] or subs
        if series:
            by_q[q_hash(params["q"])][series[0].key] += 1
    await db.execute(delete(NewsletterQueryMap))
    n = 0
    for h, cnt in by_q.items():
        total = sum(cnt.values())
        subject, top = cnt.most_common(1)[0]
        if top >= QUERY_MAP_MIN_SELECTS and top / total >= QUERY_MAP_MIN_SHARE:
            db.add(NewsletterQueryMap(q_hash=h, subject=subject, selects=top, share=round(top / total, 4),
                                      computed_at=now))
            n += 1
    return n


async def rebuild_related(db: AsyncSession, *, now: datetime) -> int:
    """Связанные ряды: косинус совместных просмотров разных посетителей (пара — от 5 посетителей)."""
    from app.services.newsletter_personal.subjects import subjects_from_event

    rows = (await db.execute(
        select(FrontendEvent.visitor_id_hash, FrontendEvent.event_name, FrontendEvent.params_json).where(
            FrontendEvent.event_name.in_(("indicator_view", "region_indicator_view", "download_excel", "download_csv")),
            FrontendEvent.occurred_at >= now - timedelta(days=RELATED_DAYS),
            FrontendEvent.visitor_id_hash.is_not(None), _no_robot())
        .limit(MAX_ROWS))).all()
    per_visitor: dict[str, set[str]] = defaultdict(set)
    for vid, name, params in rows:
        _kind, subs = subjects_from_event(name, params)
        for s in subs:
            if s.kind in ("ru", "w") and len(per_visitor[vid]) < RELATED_MAX_PER_VISITOR:
                per_visitor[vid].add(s.key)
    single: Counter = Counter()
    pair: Counter = Counter()
    for keys in per_visitor.values():
        single.update(keys)
        for a, b in combinations(sorted(keys), 2):
            pair[(a, b)] += 1
    scored: dict[str, list[tuple[float, str, int]]] = defaultdict(list)
    for (a, b), n in pair.items():
        if n < RELATED_MIN_VISITORS:
            continue
        score = n / math.sqrt(single[a] * single[b])
        scored[a].append((score, b, n))
        scored[b].append((score, a, n))
    await db.execute(delete(NewsletterRelated))
    total = 0
    for subj, lst in scored.items():
        for score, other, n in sorted(lst, reverse=True)[:RELATED_PER_SUBJECT]:
            db.add(NewsletterRelated(subject=subj, related=other, score=round(score, 4), visitors=n, computed_at=now))
            total += 1
    return total


async def related_for(db: AsyncSession, keys: list[str], limit: int = 5) -> dict[str, list[str]]:
    if not keys or not await tables_ready(db):
        return {}
    out: dict[str, list[tuple[float, str]]] = defaultdict(list)
    for subj, rel, score in (await db.execute(
            select(NewsletterRelated.subject, NewsletterRelated.related, NewsletterRelated.score)
            .where(NewsletterRelated.subject.in_(keys)))).all():
        out[subj].append((float(score), rel))
    return {k: [r for _s, r in sorted(v, reverse=True)[:limit]] for k, v in out.items()}


async def account_export(db: AsyncSession, user_id: uuid.UUID) -> dict:
    """Раздел «Мои данные» (152-ФЗ): профиль интересов и что было в личных выпусках (без текста писем)."""
    if not await tables_ready(db):
        return {"profile": None, "issues": []}
    prof = await db.get(NewsletterProfile, user_id)
    issues = (await db.scalars(select(NewsletterPersonalIssue).where(NewsletterPersonalIssue.user_id == user_id)
                               .order_by(NewsletterPersonalIssue.built_at))).all()
    return {
        "profile": None if prof is None else {
            "computed_at": prof.computed_at.isoformat() if prof.computed_at else None, "tier": prof.tier,
            "topics": prof.topics, "subjects": prof.subjects, "geo": prof.geo, "timezone": prof.timezone,
        },
        "issues": [{"campaign": i.campaign, "built_at": i.built_at.isoformat() if i.built_at else None,
                    "status": i.status, "blocks": [{k: m.get(k) for k in ("pos", "gen", "subject", "reason", "as_of")}
                                                   for m in (i.blocks_meta or []) if m.get("origin") == "personal"]}
                   for i in issues],
    }


async def account_erase(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Удаление с аккаунтом явно (в SQLite каскад выключен; в PostgreSQL сработал бы и он)."""
    if not await tables_ready(db):
        return
    await db.execute(delete(NewsletterPersonalIssue).where(NewsletterPersonalIssue.user_id == user_id))
    await db.execute(delete(NewsletterProfile).where(NewsletterProfile.user_id == user_id))

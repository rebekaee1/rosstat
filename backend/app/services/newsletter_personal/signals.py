"""Сбор сигналов о подписчике из базы сайта (ADR-0033). Только данные нашего сайта.

Источники (пакетом на `batch_size` человек, без чтения всей таблицы):
* кабинет — избранное и сохранённое (`user_saved_items`), колокольчик (`user_watches`), настройки
  (`user_preferences`: темы рассылки, главная страна, валюта), история выгрузок (`user_exports`);
* события сайта (`frontend_events`) за `WINDOW_DAYS`: под аккаунтом и до регистрации — по
  постоянным посетителям аккаунта (`identity_links`); сессии с признаком автоматизации
  (`behavior_sessions.is_webdriver`) отбрасываются;
* регистрация (`user_signups`): язык, страна, посадочная страница и что подтолкнуло;
* переходы из писем (`behavior_sessions.utm_*` с меткой блока) и показы прошлых выпусков
  (`newsletter_personal_issues.blocks_meta`) — для усталости и «Сверки».

Текст поисковых запросов не выходит за пределы этого модуля: запрос сразу превращается в хэш и
ищется в обезличенной таблице `newsletter_query_map`; запрос без результата — «пробел» (хэш).
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    BehaviorSession, Consent, FrontendEvent, IdentityLink, NewsletterPersonalIssue, NewsletterQueryMap,
    User, UserExport, UserPreference, UserSavedItem, UserSignup, UserWatch,
)
from app.services.newsletter_personal import store
from app.services.newsletter_personal.profile import Signal
from app.services.newsletter_personal.subjects import (
    TOPICS, Subject, normalize_query, parse_key, subjects_from_event, subjects_from_path,
)

logger = logging.getLogger(__name__)

WINDOW_DAYS = 180
EVENT_NAMES = (
    "indicator_view", "region_indicator_view", "download_csv", "download_excel", "chart_image_download",
    "regions_map_gif_download", "download_limit", "forecast_view", "search_select", "search_query",
    "compare_open", "related_indicator_click", "category_tile_click", "home_indicator_click",
    "home_category_click", "nav_category_open", "regions_map_metric", "calc_mortgage", "calc_use",
    "calc_compound",
)
# Журнал согласий: отказ от персональной подборки — общий с почтой (ADR-0032/0033, 15.11.2026).
PERSONAL_KINDS = ("mail_personal", "mail_personal_revoked")


def q_hash(q: str) -> str:
    return hashlib.sha256(("fe-nl-q|" + normalize_query(q)).encode("utf-8")).hexdigest()


@dataclass
class UserSignals:
    user_id: str
    created_at: datetime | None = None
    locale: str | None = None
    country_code: str | None = None
    signals: list[Signal] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)          # хэши запросов без результата
    home_country: str | None = None
    timezone: str | None = None
    last_visit: datetime | None = None
    events: int = 0
    explicit: int = 0
    personal_off: bool = False
    history: list[dict] = field(default_factory=list)      # прошлые снимки: {campaign, built_at, blocks_meta}
    clicks: list[dict] = field(default_factory=list)       # {campaign, content, at}
    watch_notified: dict[str, str] = field(default_factory=dict)  # ключ → дата последнего письма колокольчика


async def personal_off(db: AsyncSession, user_id: uuid.UUID) -> bool:
    last = await db.scalar(
        select(Consent.kind).where(Consent.user_id == user_id, Consent.kind.in_(PERSONAL_KINDS))
        .order_by(Consent.granted_at.desc(), Consent.id.desc()).limit(1))
    return last == "mail_personal_revoked"


async def set_mail_personalization(db: AsyncSession, user_id: uuid.UUID, enabled: bool, request=None,
                                   source: str = "account") -> bool:
    """Включить/выключить персональную подборку: запись в журнал согласий (append-only) и аудит.

    True — запись добавлена; False — состояние уже такое. Коммит — у вызывающего.
    """
    if (not await personal_off(db, user_id)) == enabled:
        return False
    ip = ua = None
    if request is not None:
        try:
            from app.api.auth import _client_ip

            ip = _client_ip(request)
        except Exception:  # noqa: BLE001
            ip = None
        ua = (request.headers.get("user-agent") or "")[:500] or None
    db.add(Consent(user_id=user_id, kind="mail_personal" if enabled else "mail_personal_revoked",
                   version="1", ip=ip, user_agent=ua))
    if request is not None:
        try:
            from app.api.auth import audit

            await audit(db, user_id, "mail_personal_on" if enabled else "mail_personal_off", request, detail=source)
        except Exception:  # noqa: BLE001 — аудит не должен мешать отказу
            logger.warning("personalization audit failed")
    await db.flush()
    return True


def _watch_subject(kind: str, key: str, world_country: dict[str, str]) -> Subject | None:
    if kind == "indicator":
        return parse_key(f"ru:{key}")
    if kind == "world":
        slug = world_country.get(key)
        return parse_key(f"w:{slug}:{key}") if slug else None
    if kind == "region":
        return parse_key(f"ri:{key}")
    return None


def _saved_subjects(kind: str, key: str, payload: dict | None, world_country: dict[str, str]) -> list[Subject]:
    path = (payload or {}).get("path") if isinstance(payload, dict) else None
    if isinstance(path, str):
        subs = subjects_from_path(path)
        if subs:
            return subs
    if kind == "indicator":
        s = parse_key(f"ru:{key}")
        return [s] if s else []
    if kind == "world":
        s = _watch_subject("world", key, world_country)
        return [s] if s else []
    if kind == "country":
        s = parse_key(f"c:{key}")
        return [s] if s else []
    if kind == "region":
        s = parse_key(f"reg:{key}")
        return [s] if s else []
    if kind == "comparison":
        out = []
        for part in key.replace("codes=", "").replace("&", ",").split(","):
            s = parse_key(part.strip()) if ":" in part else parse_key(f"ru:{part.strip()}")
            if s:
                out.append(s)
        return out[:8]
    return []


async def collect(db: AsyncSession, user_ids: list[uuid.UUID], *, now: datetime,
                  behavior: bool = True) -> dict[str, UserSignals]:
    """Сигналы пакета людей. `behavior=False` — только кабинет и регистрация (без событий сайта)."""
    since = now - timedelta(days=WINDOW_DAYS)
    out: dict[str, UserSignals] = {str(u): UserSignals(user_id=str(u)) for u in user_ids}
    if not user_ids:
        return out
    ids = list(user_ids)
    sids = [str(u) for u in ids]

    for uid, created in (await db.execute(select(User.id, User.created_at).where(User.id.in_(ids)))).all():
        out[str(uid)].created_at = created
    for row in (await db.scalars(select(UserSignup).where(UserSignup.user_id.in_(ids)))).all():
        us = out[str(row.user_id)]
        us.locale, us.country_code = row.site_locale, row.country_code
        at = row.created_at or us.created_at or now
        for sub in subjects_from_path(row.landing_page):
            us.signals.append(Signal("landing_gate" if (row.trigger or "").startswith("gate_") else "landing", sub, at))

    # Отказ от подборки (журнал согласий): последняя запись решает.
    latest: dict[str, tuple] = {}
    for uid, kind, at, cid in (await db.execute(
            select(Consent.user_id, Consent.kind, Consent.granted_at, Consent.id)
            .where(Consent.user_id.in_(ids), Consent.kind.in_(PERSONAL_KINDS)))).all():
        key = str(uid)
        if key not in latest or (at, cid) > latest[key][:2]:
            latest[key] = (at, cid, kind)
    for key, (_a, _c, kind) in latest.items():
        out[key].personal_off = kind == "mail_personal_revoked"

    # Кабинет.
    watches = (await db.scalars(select(UserWatch).where(UserWatch.user_id.in_(ids)))).all()
    saved = (await db.scalars(select(UserSavedItem).where(UserSavedItem.user_id.in_(ids)))).all()
    world_codes = [w.subject_key for w in watches if w.subject_kind == "world"]
    world_codes += [s.item_key for s in saved if s.kind == "world"]
    world_country: dict[str, str] = {}
    if world_codes:
        from app.models import WorldCountry, WorldIndicator

        world_country = {code: slug for code, slug in (await db.execute(
            select(WorldIndicator.code, WorldCountry.slug).join(WorldCountry, WorldCountry.id == WorldIndicator.country_id)
            .where(WorldIndicator.code.in_(world_codes)))).all()}
    for w in watches:
        sub = _watch_subject(w.subject_kind, w.subject_key, world_country)
        if sub is not None:
            us = out[str(w.user_id)]
            us.signals.append(Signal("watch", sub, w.created_at))
            us.explicit += 1
            if w.last_notified_date:
                us.watch_notified[sub.key] = w.last_notified_date.isoformat()
    for s in saved:
        us = out[str(s.user_id)]
        kind = "saved_compare" if s.kind == "comparison" else "favorite"
        for sub in _saved_subjects(s.kind, s.item_key, s.payload, world_country):
            us.signals.append(Signal(kind, sub, s.updated_at or s.created_at))
            us.explicit += 1
        if s.kind == "calc":
            us.signals.append(Signal("pref_topic", Subject("t", "rates"), s.updated_at or s.created_at))
    for e in (await db.scalars(select(UserExport).where(UserExport.user_id.in_(ids), UserExport.created_at >= since))).all():
        subs = subjects_from_path(e.subject_key) or (
            [parse_key(f"ru:{e.subject_key}")] if e.subject_key and ":" not in e.subject_key else [])
        if e.subject_key and e.subject_key.startswith(("w:", "r:", "ru:")):
            subs = [parse_key(e.subject_key)]
        for sub in subs:
            if sub is not None:
                out[str(e.user_id)].signals.append(Signal("export", sub, e.created_at))
                out[str(e.user_id)].explicit += 1
    for p in (await db.scalars(select(UserPreference).where(UserPreference.user_id.in_(ids)))).all():
        us = out[str(p.user_id)]
        data = p.data or {}
        for topic in data.get("newsletter_topics") or []:
            if topic in TOPICS:
                us.signals.append(Signal("pref_topic", Subject("t", topic), p.updated_at))
                us.explicit += 1
        if isinstance(data.get("home_country"), str):
            us.home_country = data["home_country"]
        if data.get("currency") and data.get("currency") != "RUB":
            us.signals.append(Signal("pref_topic", Subject("t", "currencies"), p.updated_at))

    # Постоянные посетители аккаунта (история до регистрации и с других устройств).
    visitor_owner: dict[str, str] = {}
    for uid, vid in (await db.execute(
            select(IdentityLink.user_id, IdentityLink.visitor_id_hash).where(IdentityLink.user_id.in_(sids)))).all():
        visitor_owner.setdefault(vid, uid)
    # Устройство, привязанное к двум и более аккаунтам (общий компьютер), никому не приписывается:
    # действия без входа с него неизвестно чьи (16.11.2026: 3 таких устройства у подписчиков).
    if visitor_owner:
        from sqlalchemy import func

        shared = {vid for (vid,) in (await db.execute(
            select(IdentityLink.visitor_id_hash).where(IdentityLink.visitor_id_hash.in_(list(visitor_owner)))
            .group_by(IdentityLink.visitor_id_hash).having(func.count(func.distinct(IdentityLink.user_id)) > 1))).all()}
        for vid in shared:
            visitor_owner.pop(vid, None)

    # Пояс и последний визит.
    sess_filter = [BehaviorSession.user_id.in_(sids)]
    if visitor_owner:
        sess_filter.append(BehaviorSession.visitor_id_hash.in_(list(visitor_owner)))
    tz_counter: dict[str, Counter] = defaultdict(Counter)
    for uid, vid, tz, started, medium, campaign, content in (await db.execute(
            select(BehaviorSession.user_id, BehaviorSession.visitor_id_hash, BehaviorSession.timezone,
                   BehaviorSession.started_at, BehaviorSession.utm_medium, BehaviorSession.utm_campaign,
                   BehaviorSession.utm_content)
            .where(or_(*sess_filter), BehaviorSession.started_at >= since,
                   or_(BehaviorSession.is_webdriver.is_(None), BehaviorSession.is_webdriver.is_(False))))).all():
        owner = uid if uid in out else visitor_owner.get(vid)
        if owner not in out:
            continue
        us = out[owner]
        if tz:
            tz_counter[owner][tz] += 1
        if us.last_visit is None or started > us.last_visit:
            us.last_visit = started
        if medium == "newsletter" and campaign and content:
            us.clicks.append({"campaign": campaign, "content": content, "at": started})
    for owner, cnt in tz_counter.items():
        out[owner].timezone = cnt.most_common(1)[0][0]

    # Прошлые выпуски (усталость, «Сверка», частота), если таблица уже есть.
    if await store.tables_ready(db):
        for row in (await db.scalars(
                select(NewsletterPersonalIssue).where(NewsletterPersonalIssue.user_id.in_(ids))
                .order_by(NewsletterPersonalIssue.built_at.desc()))).all():
            us = out[str(row.user_id)]
            if len(us.history) < 8:
                us.history.append({"campaign": row.campaign, "built_at": row.built_at, "status": row.status,
                                   "blocks_meta": row.blocks_meta or []})
    # Переход по блоку письма → сигнал предмету этого блока.
    for us in out.values():
        for click in us.clicks:
            for h in us.history:
                if h["campaign"] != click["campaign"]:
                    continue
                for meta in h["blocks_meta"]:
                    if meta.get("utm_content") == click["content"] and meta.get("subject"):
                        sub = parse_key(meta["subject"])
                        if sub is not None:
                            us.signals.append(Signal("mail_click", sub, click["at"]))

    if not behavior:
        return out

    # События сайта.
    no_robot = ~exists().where(and_(BehaviorSession.session_id_hash == FrontendEvent.session_id_hash,
                                    BehaviorSession.is_webdriver.is_(True)))
    ev_filter = [FrontendEvent.user_id.in_(sids)]
    if visitor_owner:
        ev_filter.append(and_(FrontendEvent.user_id.is_(None), FrontendEvent.visitor_id_hash.in_(list(visitor_owner))))
    rows = (await db.execute(
        select(FrontendEvent.user_id, FrontendEvent.visitor_id_hash, FrontendEvent.event_name,
               FrontendEvent.params_json, FrontendEvent.occurred_at)
        .where(or_(*ev_filter), FrontendEvent.occurred_at >= since, FrontendEvent.event_name.in_(EVENT_NAMES),
               no_robot)
    )).all()
    pending_queries: dict[str, list[tuple[str, datetime, bool]]] = defaultdict(list)
    for uid, vid, name, params, at in rows:
        owner = uid if uid in out else visitor_owner.get(vid)
        if owner not in out:
            continue
        us = out[owner]
        us.events += 1
        pre = bool(us.created_at and at < us.created_at)
        if name == "search_query":
            q = (params or {}).get("q") if isinstance(params, dict) else None
            if isinstance(q, str) and len(q.strip()) >= 2:
                results = (params or {}).get("results")
                h = q_hash(q)
                if str(results) == "0":
                    us.gaps.append(h)
                else:
                    pending_queries[owner].append((h, at, pre))
            continue
        kind, subs = subjects_from_event(name, params)
        if not kind:
            continue
        for sub in subs:
            us.signals.append(Signal(kind, sub, at, pre_signup=pre))
    # Запрос → ряд по обезличенной таблице (текст запроса не хранится).
    hashes = sorted({h for lst in pending_queries.values() for h, _a, _p in lst})
    if hashes and await store.tables_ready(db):
        qmap = {h: s for h, s in (await db.execute(
            select(NewsletterQueryMap.q_hash, NewsletterQueryMap.subject).where(NewsletterQueryMap.q_hash.in_(hashes)))).all()}
        for owner, lst in pending_queries.items():
            for h, at, pre in lst:
                sub = parse_key(qmap.get(h))
                if sub is not None:
                    out[owner].signals.append(Signal("search_query", sub, at, pre_signup=pre))
    return out

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import AgentActionAudit, AnalyticsSyncRun, BehaviorEvent, Experiment, FrontendEvent
from app.security.auth import current_session
from app.services.action_policy import evaluate_action
from app.services.action_executor import execute_approved_action
from app.services.analytics_features import detect_page_opportunities, sync_run_impact, top_pages, top_search_phrases
from app.services.scrape_guard import is_noise_client_ua
from app.services.yandex_metrika_reporting import MetrikaReportingClient

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _require_analytics_token(x_analytics_token: str | None = Header(default=None)) -> None:
    if settings.analytics_api_token and x_analytics_token == settings.analytics_api_token:
        return
    raise HTTPException(status_code=403, detail="Analytics API token required")


class MetrikaQueryRequest(BaseModel):
    counter_id: str = Field(default="107136069")
    report_type: str = Field(default="data")
    metrics: list[str]
    dimensions: list[str] = Field(default_factory=list)
    date_from: date | None = None
    date_to: date | None = None
    filters: str | None = None
    limit: int = 100


class ActionProposal(BaseModel):
    action_type: str
    target: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
    diff: dict[str, Any] | None = None
    reason: str | None = None


class FrontendEventIn(BaseModel):
    event_name: str
    session_id: str | None = None
    visitor_id: str | None = None
    url: str | None = None
    referrer: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None


class BehaviorBatchIn(BaseModel):
    """Батч сырых поведенческих событий от behavior.js (буфер → sendBeacon)."""
    session_id: str | None = None
    visitor_id: str | None = None
    authed: int = 0
    batch_id: str | None = None  # клиентский UUID батча — дедуп повторной доставки
    events: list[dict[str, Any]] = Field(default_factory=list)


def _hash_id(value: str | None) -> str | None:
    return hashlib.sha256(value.encode("utf-8")).hexdigest() if value else None


async def _upsert_identity_link(db: AsyncSession, user_id: str, visitor_hash: str) -> None:
    """Граф идентичности: связка user × visitor обновляется при каждом
    авторизованном батче. История visitor'а до регистрации ретроспективно
    принадлежит человеку (join по visitor_id_hash)."""
    from app.models import IdentityLink

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        stmt = pg_insert(IdentityLink.__table__).values(
            user_id=user_id, visitor_id_hash=visitor_hash, first_seen=now, last_seen=now,
        ).on_conflict_do_update(
            constraint="uq_identity_user_visitor", set_={"last_seen": now},
        )
        await db.execute(stmt)
    else:  # sqlite в тестах
        existing = await db.scalar(
            select(IdentityLink).where(
                IdentityLink.user_id == user_id, IdentityLink.visitor_id_hash == visitor_hash
            )
        )
        if existing:
            existing.last_seen = now
        else:
            db.add(IdentityLink(user_id=user_id, visitor_id_hash=visitor_hash, first_seen=now, last_seen=now))


@router.get("/health", dependencies=[Depends(_require_analytics_token)])
async def analytics_health(db: AsyncSession = Depends(get_db)):
    last_runs_q = await db.execute(
        select(AnalyticsSyncRun).order_by(desc(AnalyticsSyncRun.started_at)).limit(10)
    )
    last_runs = last_runs_q.scalars().all()
    failed_count_q = await db.execute(
        select(func.count()).select_from(AnalyticsSyncRun).where(AnalyticsSyncRun.status == "failed")
    )
    return {
        "enabled": settings.analytics_enabled,
        "scheduler_enabled": settings.analytics_scheduler_enabled,
        "allowed_counter_ids": settings.analytics_allowed_counter_ids,
        "allowed_hosts": settings.analytics_allowed_hosts,
        "failed_sync_runs": failed_count_q.scalar_one(),
        "last_runs": [
            {
                "id": run.id,
                "source": run.source,
                "job_type": run.job_type,
                "status": run.status,
                "started_at": run.started_at,
                "completed_at": run.completed_at,
                "records_processed": run.records_processed,
                "error_message": run.error_message,
            }
            for run in last_runs
        ],
    }


@router.post("/query/metrika", dependencies=[Depends(_require_analytics_token)])
async def query_metrika(payload: MetrikaQueryRequest):
    client = MetrikaReportingClient()
    response = await client.report(
        payload.report_type,  # type: ignore[arg-type]
        counter_id=payload.counter_id,
        metrics=payload.metrics,
        dimensions=payload.dimensions,
        date_from=payload.date_from,
        date_to=payload.date_to,
        filters=payload.filters,
        limit=payload.limit,
    )
    return {
        "request_hash": response.request_hash,
        "sampled": response.sampled,
        "sample_share": response.sample_share,
        "contains_sensitive_data": response.contains_sensitive_data,
        "data": response.data,
    }


@router.get("/pages", dependencies=[Depends(_require_analytics_token)])
async def analytics_pages(
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=50, le=500),
    db: AsyncSession = Depends(get_db),
):
    return {"pages": await top_pages(db, date_from=date_from, date_to=date_to, limit=limit)}


@router.get("/search-phrases", dependencies=[Depends(_require_analytics_token)])
async def analytics_search_phrases(
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
):
    return {"phrases": await top_search_phrases(db, date_from=date_from, date_to=date_to, limit=limit)}


@router.get("/anomalies", dependencies=[Depends(_require_analytics_token)])
async def analytics_anomalies(db: AsyncSession = Depends(get_db)):
    opportunities = await detect_page_opportunities(db)
    return {"opportunities": [item.__dict__ for item in opportunities]}


@router.get("/deploy-impact", dependencies=[Depends(_require_analytics_token)])
async def analytics_deploy_impact(db: AsyncSession = Depends(get_db)):
    return {"recent_sync_runs": await sync_run_impact(db)}


@router.get("/experiments/bootstrap")
async def experiments_bootstrap(db: AsyncSession = Depends(get_db)):
    if not settings.analytics_enabled:
        return {"experiments": [], "flags": {}}
    rows = (
        await db.execute(select(Experiment).where(Experiment.status == "active"))
    ).scalars().all()
    flags: dict[str, Any] = {}
    experiments = []
    for experiment in rows:
        variants = experiment.variants_json or {}
        split = experiment.traffic_split_json or {}
        experiments.append({
            "key": experiment.key,
            "variants": variants,
            "traffic_split": split,
        })
        flags[experiment.key] = variants.get("default") if isinstance(variants, dict) else None
    return {"experiments": experiments, "flags": flags}


@router.post("/actions/propose", dependencies=[Depends(_require_analytics_token)])
async def propose_action(payload: ActionProposal, db: AsyncSession = Depends(get_db)):
    decision = evaluate_action(payload.action_type, {**payload.target, **payload.payload}, approved=False)
    action = AgentActionAudit(
        action_type=payload.action_type,
        safety_class=decision.safety_class.value,
        status="proposed",
        target_json=payload.target,
        payload_json=payload.payload,
        diff_json=payload.diff,
        reason=payload.reason or decision.reason,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(action)
    await db.commit()
    await db.refresh(action)
    return {
        "action_id": action.id,
        "allowed_now": decision.allowed,
        "requires_approval": decision.requires_approval,
        "safety_class": decision.safety_class,
        "reason": decision.reason,
    }


@router.post("/actions/{action_id}/apply", dependencies=[Depends(_require_analytics_token)])
async def apply_action(action_id: int, approval_token: str, db: AsyncSession = Depends(get_db)):
    action = await db.get(AgentActionAudit, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    expected = settings.analytics_api_token
    if not expected or approval_token != expected:
        raise HTTPException(status_code=403, detail="Invalid approval token")
    decision = evaluate_action(action.action_type, {**(action.target_json or {}), **(action.payload_json or {})}, approved=True)
    if not decision.allowed:
        raise HTTPException(status_code=409, detail=decision.reason)
    try:
        result = await execute_approved_action(action, approval_token=approval_token)
    except Exception as exc:
        action.status = "failed"
        action.error_message = str(exc)[:500]
        db.add(action)
        await db.commit()
        raise HTTPException(status_code=409, detail=str(exc))
    action.status = "approved"
    action.approval_token_hash = hashlib.sha256(approval_token.encode("utf-8")).hexdigest()
    action.response_json = result
    action.applied_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(action)
    await db.commit()
    return {"action_id": action.id, "status": action.status, "reason": decision.reason}


@router.post("/events")
async def collect_event(request: Request, payload: FrontendEventIn, db: AsyncSession = Depends(get_db)):
    # First-party телеметрия развязана с внешней Метрика-интеграцией: пишем
    # события всегда (питает «Пульс»), даже если analytics_enabled=false.
    if not settings.frontend_events_enabled:
        return {"accepted": False, "reason": "frontend events disabled"}
    if is_noise_client_ua(request.headers.get("user-agent")):
        return {"accepted": False, "reason": "ignored"}
    session_hash = hashlib.sha256(payload.session_id.encode("utf-8")).hexdigest() if payload.session_id else None
    visitor_hash = _hash_id(payload.visitor_id)
    # Атрибуция аудитории. Эндпоинт — POST (не кэшируется), поэтому чтение
    # сессионной куки безопасно и не нарушает инвариант «не варьировать кэш по
    # куке». Резолв через state-Redis, без похода в БД: сессия несёт user_id.
    sess = await current_session(request)
    user_id = sess.get("user_id") if sess else None
    if user_id and visitor_hash:
        await _upsert_identity_link(db, str(user_id), visitor_hash)
    event = FrontendEvent(
        event_name=payload.event_name,
        session_id_hash=session_hash,
        visitor_id_hash=visitor_hash,
        user_id=str(user_id) if user_id else None,
        authed=bool(user_id),
        url=payload.url,
        referrer=payload.referrer or request.headers.get("referer"),
        params_json=payload.params,
        occurred_at=(payload.occurred_at or datetime.now(timezone.utc)).replace(tzinfo=None),
        ingested_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(event)
    await db.commit()
    return {"accepted": True, "authed": bool(user_id)}


# Горячие поля батч-события, выносимые в колонки behavior_events; остальное
# уходит в params_json. Ключи совпадают с полями, которые шлёт behavior.js.
_BEHAVIOR_COLUMN_KEYS = {"t", "ts", "url", "pl", "path", "text", "x", "y", "dead", "rage"}
# vital/js_error/api_timing — слой скорости и надёжности; block_view — блочная
# аналитика (IntersectionObserver); form — воронка форм без снятия текста.
_BEHAVIOR_TYPES = {
    "pageview", "click", "move", "dwell", "copy",
    "vital", "js_error", "api_timing", "block_view", "form",
}


def _int_or_none(v: Any) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _str_or_none(v: Any, limit: int) -> str | None:
    s = str(v or "")
    return s[:limit] if s else None


def _num_or_none(v: Any) -> float | None:
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


async def _upsert_behavior_session(
    db: AsyncSession, ev: dict, *, session_hash: str, visitor_hash: str | None,
    user_id: str | None, authed: bool, occurred: datetime, client_ip: str | None,
) -> None:
    """session_start → строка в behavior_sessions (портрет сессии/аудитории).

    Идемпотентно по PK session_id_hash — повторная отправка (например, после
    restore вкладки) не перетирает первый НАСТОЯЩИЙ портрет. Исключение:
    синтетическую строку (собранную сервером из батча без session_start)
    настоящий портрет апгрейдит полными данными (волна 2, п. 1/4).
    Здесь же: гео по IP (сам IP не сохраняется) и классификация канала.
    """
    from app.services.geoip import lookup as geo_lookup
    from app.services.traffic_channel import classify_channel, referrer_host
    from app.services.ua_parser import parse_user_agent
    from app.services.yandex_client import stable_hash

    # _ym_uid хэшируем тем же stable_hash, что client_id_hash Метрики:
    # прямой join behavior_sessions × raw_metrika_visits (ретро-мост).
    ym_raw = _str_or_none(ev.get("ymuid"), 40)
    ua = _str_or_none(ev.get("ua"), 500)
    parsed = parse_user_agent(ua)
    referrer = _str_or_none(ev.get("ref"), 1000)
    utm_source = _str_or_none(ev.get("us"), 120)
    utm_medium = _str_or_none(ev.get("um"), 120)
    yclid = _str_or_none(ev.get("yclid"), 64)
    ysclid = _str_or_none(ev.get("ysclid"), 64)
    utm_referrer = _str_or_none(ev.get("ur"), 1000)
    geo = geo_lookup(client_ip)

    values = {
        "session_id_hash": session_hash,
        "visitor_id_hash": visitor_hash,
        "ym_client_id": stable_hash(ym_raw)[:80] if ym_raw else None,
        "user_id": user_id,
        "authed": authed,
        "started_at": occurred,
        "entry_page": _normalize_page(ev.get("url")),
        "referrer": referrer,
        "referrer_host": referrer_host(referrer),
        "channel": classify_channel(
            referrer=referrer,
            utm_source=utm_source,
            utm_medium=utm_medium,
            yclid=yclid,
            ysclid=ysclid,
            utm_referrer=utm_referrer,
        ),
        "utm_source": utm_source,
        "utm_medium": utm_medium,
        "utm_campaign": _str_or_none(ev.get("uc"), 200),
        "utm_term": _str_or_none(ev.get("ut"), 200),
        "utm_content": _str_or_none(ev.get("uco"), 200),
        "yclid": yclid,
        "country": geo["country"] and geo["country"][:60],
        "geo_region": geo["region"] and geo["region"][:120],
        "city": geo["city"] and geo["city"][:120],
        "ua_raw": ua,
        "browser": parsed["browser"],
        "browser_version": parsed["browser_version"],
        "os": parsed["os"],
        "os_version": parsed["os_version"],
        "device_type": parsed["device_type"],
        "screen_w": _int_or_none(ev.get("sw")),
        "screen_h": _int_or_none(ev.get("sh")),
        "viewport_w": _int_or_none(ev.get("vw")),
        "viewport_h": _int_or_none(ev.get("vh")),
        "dpr": _num_or_none(ev.get("dpr")),
        "language": _str_or_none(ev.get("lang"), 16),
        "timezone": _str_or_none(ev.get("tz"), 60),
        "touch": bool(ev.get("touch")) if ev.get("touch") is not None else None,
        "conn_type": _str_or_none(ev.get("conn"), 16),
        "downlink": _num_or_none(ev.get("dl")),
        "device_memory": _num_or_none(ev.get("dm")),
        "cpu_cores": _int_or_none(ev.get("hc")),
        "color_scheme": _str_or_none(ev.get("theme"), 10),
        "orientation": _str_or_none(ev.get("orient"), 12),
        "is_webdriver": bool(ev.get("wd")) if ev.get("wd") is not None else None,
        "is_synthetic": False,
    }
    await _insert_portrait(db, values, upgrade_synthetic=True)


async def _insert_portrait(
    db: AsyncSession, values: dict, *, upgrade_synthetic: bool
) -> None:
    """Вставка портрета: конфликт по PK — no-op; настоящий портрет
    (upgrade_synthetic=True) перезаписывает синтетическую строку."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.models import BehaviorSession

    table = BehaviorSession.__table__
    if db.bind.dialect.name == "postgresql":
        stmt = pg_insert(table).values(**values)
        if upgrade_synthetic:
            stmt = stmt.on_conflict_do_update(
                index_elements=["session_id_hash"],
                set_={k: v for k, v in values.items() if k != "session_id_hash"},
                where=table.c.is_synthetic.is_(True),
            )
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=["session_id_hash"])
        await db.execute(stmt)
    else:  # sqlite в тестах
        from sqlalchemy import select as sa_select, update as sa_update
        existing = (await db.execute(
            sa_select(BehaviorSession.session_id_hash, BehaviorSession.is_synthetic)
            .where(BehaviorSession.session_id_hash == values["session_id_hash"])
        )).first()
        if existing is None:
            await db.execute(table.insert().values(**values))
        elif upgrade_synthetic and existing.is_synthetic:
            await db.execute(
                sa_update(BehaviorSession)
                .where(BehaviorSession.session_id_hash == values["session_id_hash"])
                .values(**{k: v for k, v in values.items() if k != "session_id_hash"})
            )


async def _upsert_synthetic_portrait(
    db: AsyncSession, ev: dict, *, session_hash: str, visitor_hash: str | None,
    user_id: str | None, authed: bool, occurred: datetime, client_ip: str | None,
    ua: str | None,
) -> None:
    """Частичный портрет из батча БЕЗ session_start (волна 2, п. 1/4).

    session_start иногда теряется (beacon, ад-блокеры) — тогда сессия
    оставалась без канала/браузера/устройства и выпадала из срезов аудитории.
    Собираем портрет из того, что знает сервер на любом батче: User-Agent
    запроса, гео по IP, referrer/viewport/touch первого pageview. Настоящий
    session_start, дошедший позже (клиент ретраит), апгрейдит строку полным
    портретом — см. `_upsert_behavior_session`.
    """
    from urllib.parse import parse_qs, urlsplit

    from app.services.geoip import lookup as geo_lookup
    from app.services.traffic_channel import classify_channel, referrer_host
    from app.services.ua_parser import parse_user_agent

    ua = _str_or_none(ua, 500)
    parsed = parse_user_agent(ua)
    referrer = _str_or_none(ev.get("ref"), 1000)
    geo = geo_lookup(client_ip)

    # UTM/yclid из сырого URL pageview (behavior.js шлёт pathname + search;
    # в колонку page query уже отрезан — рекламные метки берём здесь).
    q: dict = {}
    try:
        q = parse_qs(urlsplit(str(ev.get("url") or "")).query)
    except ValueError:
        pass
    qp = lambda k, n: _str_or_none((q.get(k) or [None])[0], n)  # noqa: E731
    utm_source, utm_medium, yclid = qp("utm_source", 120), qp("utm_medium", 120), qp("yclid", 64)
    ysclid, utm_referrer = qp("ysclid", 64), qp("utm_referrer", 1000)

    values = {
        "session_id_hash": session_hash,
        "visitor_id_hash": visitor_hash,
        "user_id": user_id,
        "authed": authed,
        "started_at": occurred,
        "entry_page": _normalize_page(ev.get("url")),
        "referrer": referrer,
        "referrer_host": referrer_host(referrer),
        "channel": classify_channel(
            referrer=referrer,
            utm_source=utm_source,
            utm_medium=utm_medium,
            yclid=yclid,
            ysclid=ysclid,
            utm_referrer=utm_referrer,
        ),
        "utm_source": utm_source,
        "utm_medium": utm_medium,
        "utm_campaign": qp("utm_campaign", 200),
        "utm_term": qp("utm_term", 200),
        "utm_content": qp("utm_content", 200),
        "yclid": yclid,
        "country": geo["country"] and geo["country"][:60],
        "geo_region": geo["region"] and geo["region"][:120],
        "city": geo["city"] and geo["city"][:120],
        "ua_raw": ua,
        "browser": parsed["browser"],
        "browser_version": parsed["browser_version"],
        "os": parsed["os"],
        "os_version": parsed["os_version"],
        "device_type": parsed["device_type"],
        "viewport_w": _int_or_none(ev.get("vw")),
        "viewport_h": _int_or_none(ev.get("vh")),
        "dpr": _num_or_none(ev.get("dpr")),
        "touch": bool(ev.get("touch")) if ev.get("touch") is not None else None,
        "is_synthetic": True,
    }
    await _insert_portrait(db, values, upgrade_synthetic=False)


# Гигиена времени на инжесте: расхождение клиентских часов и ретраи beacon
# не должны раскидывать события по чужим дням (аудит 2026-07-06).
_CLOCK_PAST_LIMIT = timedelta(days=7)
_CLOCK_FUTURE_LIMIT = timedelta(minutes=5)
_DWELL_MAX_MS = 4 * 3600 * 1000  # вкладка, забытая на ночь, — не 19 часов чтения


def _clamp_occurred(occurred: datetime, now: datetime) -> datetime:
    if occurred > now + _CLOCK_FUTURE_LIMIT:
        return now
    if occurred < now - _CLOCK_PAST_LIMIT:
        return now
    return occurred


def _normalize_page(url: Any) -> str | None:
    """Страница без query-string: /indicator/cpi?mode=weekly и без него —
    одна строка в витринах. Сырой query при необходимости остаётся в
    params_json события pageview (title/ref), для маркетинга есть UTM портрета."""
    s = str(url or "")
    if not s:
        return None
    return s.split("?", 1)[0].split("#", 1)[0][:500] or "/"


async def _is_duplicate_batch(batch_id: str | None) -> bool:
    """Дедуп повторной доставки батча (sendBeacon ретраит): SETNX с TTL.
    Redis недоступен — принимаем батч (лучше редкий дубль, чем потеря)."""
    if not batch_id:
        return False
    try:
        from app.core.cache import get_state_redis
        r = await get_state_redis()
        fresh = await r.set(f"fe:beh:batch:{batch_id[:64]}", "1", nx=True, ex=3600)
        return not fresh
    except Exception:  # noqa: BLE001
        return False


@router.post("/behavior")
async def collect_behavior_batch(
    request: Request, payload: BehaviorBatchIn, db: AsyncSession = Depends(get_db)
):
    """Приём батча поведенческого потока (behavior.js). Bulk-insert одним
    executemany — при 100k посетителей/день вставка остаётся дешёвой."""
    if not settings.behavior_events_enabled:
        return {"accepted": False, "reason": "behavior events disabled"}
    if is_noise_client_ua(request.headers.get("user-agent")):
        return {"accepted": False, "reason": "ignored"}
    events = payload.events[: settings.behavior_batch_max_events]
    if any(ev.get("wd") for ev in events):
        return {"accepted": False, "reason": "ignored"}
    if not events:
        return {"accepted": True, "stored": 0}
    if await _is_duplicate_batch(payload.batch_id):
        return {"accepted": True, "stored": 0, "duplicate": True}

    session_hash = (
        hashlib.sha256(payload.session_id.encode("utf-8")).hexdigest()
        if payload.session_id else None
    )
    visitor_hash = _hash_id(payload.visitor_id)
    sess = await current_session(request)
    user_id = sess.get("user_id") if sess else None
    if user_id and visitor_hash:
        await _upsert_identity_link(db, str(user_id), visitor_hash)
    from app.services.geoip import client_ip_from_headers
    client_ip = client_ip_from_headers(
        request.headers.get("x-forwarded-for"),
        request.client.host if request.client else None,
    )
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    rows = []
    sessions_stored = 0
    first_pageview: tuple[dict, datetime] | None = None
    for ev in events:
        etype = str(ev.get("t") or "")[:20]
        try:
            occurred = datetime.fromtimestamp(int(ev["ts"]) / 1000, tz=timezone.utc).replace(tzinfo=None)
        except (KeyError, TypeError, ValueError, OSError):
            occurred = now
        occurred = _clamp_occurred(occurred, now)
        if etype == "pageview" and first_pageview is None:
            first_pageview = (ev, occurred)
        if etype == "session_start" and session_hash:
            await _upsert_behavior_session(
                db, ev, session_hash=session_hash, visitor_hash=visitor_hash,
                user_id=str(user_id) if user_id else None,
                authed=bool(user_id) or bool(payload.authed),
                occurred=occurred, client_ip=client_ip,
            )
            sessions_stored += 1
            continue
        if etype not in _BEHAVIOR_TYPES:
            continue
        extra = {k: v for k, v in ev.items() if k not in _BEHAVIOR_COLUMN_KEYS}
        # Гигиена dwell: старые клиентские бандлы из кэша не клампят ms —
        # страхуемся на инжесте, иначе «19 часов на странице» портит витрины.
        if etype == "dwell":
            for key in ("ms", "active_ms"):
                v = extra.get(key)
                if isinstance(v, (int, float)) and v > _DWELL_MAX_MS:
                    extra[key] = _DWELL_MAX_MS
        rows.append({
            "event_type": etype,
            "session_id_hash": session_hash,
            "visitor_id_hash": visitor_hash,
            "page_load_id": (str(ev.get("pl") or "") or None) and str(ev.get("pl"))[:40],
            "user_id": str(user_id) if user_id else None,
            "authed": bool(user_id) or bool(payload.authed),
            "page": _normalize_page(ev.get("url")),
            "element_path": (str(ev.get("path") or "") or None) and str(ev.get("path"))[:400],
            "element_text": (str(ev.get("text") or "") or None) and str(ev.get("text"))[:120],
            "x": ev.get("x") if isinstance(ev.get("x"), int) else None,
            "y": ev.get("y") if isinstance(ev.get("y"), int) else None,
            "is_dead": bool(ev.get("dead")),
            "is_rage": bool(ev.get("rage")),
            "params_json": extra or None,
            "occurred_at": occurred,
            "ingested_at": now,
        })
    if rows:
        await db.execute(BehaviorEvent.__table__.insert(), rows)
    # Батч с pageview, но без session_start: гарантируем портрет сессии
    # синтетической строкой (DO NOTHING — существующий портрет не трогаем).
    if session_hash and first_pageview is not None and not sessions_stored:
        pv_ev, pv_occurred = first_pageview
        await _upsert_synthetic_portrait(
            db, pv_ev, session_hash=session_hash, visitor_hash=visitor_hash,
            user_id=str(user_id) if user_id else None,
            authed=bool(user_id) or bool(payload.authed),
            occurred=pv_occurred, client_ip=client_ip,
            ua=request.headers.get("user-agent"),
        )
    if rows or sessions_stored or (user_id and visitor_hash):
        await db.commit()
    return {"accepted": True, "stored": len(rows)}

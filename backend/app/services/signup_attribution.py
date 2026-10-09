"""Атрибуция регистраций: как пришёл человек (круг 11, зона H).

Три части:
1. `record_signup` — пишется В САМОМ запросе регистрации (метод, язык сайта, страна,
   рассылка). Не может потеряться и не роняет регистрацию.
2. `ensure_signup_attribution` — задача (хвост `rollups_15min_job`): когда у человека
   появился `identity_links` (первое авторизованное событие), добирает из первой
   сессии посетителя канал, устройство, посадочную страницу, число сессий и дней до
   регистрации и «что подтолкнуло» (стена, нудж, шапка).
3. `backfill_from_outbox` — разовое восстановление истории из архива Telegram
   (`telegram_outbox`, сообщения «Новый пользователь» содержат версию сайта).

IP не хранится нигде: страна и регион берутся из геобазы в момент запроса.
Нет данных ≠ ноль: если посетитель отказался от аналитики, остаются только
серверные поля.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    BehaviorEvent,
    BehaviorSession,
    FrontendEvent,
    IdentityLink,
    TelegramOutbox,
    User,
    UserSignup,
)

logger = logging.getLogger(__name__)

SIGNUP_METHODS = ("email", "yandex", "vk", "google")

# Названия России в геобазе (русский и английский варианты, как в behavior_sessions.country).
_RUSSIA_NAMES = frozenset({"россия", "russia", "российская федерация", "russian federation", "рф"})

# Что подтолкнуло: событие-«упор» или кнопка → значение `trigger`.
TRIGGER_BY_EVENT: dict[str, str] = {
    "download_limit": "gate_download",
    "chart_image_blocked": "gate_chart_image",
    "compare_image_blocked": "gate_compare",
    "compare_limit_hit": "gate_compare",
    "regions_map_gif_blocked": "gate_gif",
    "register_nudge_cta": "nudge",
    "header_register_click": "header",
}
TRIGGER_VALUES = frozenset(set(TRIGGER_BY_EVENT.values()) | {"direct"})
# Окно «подталкивающего» события до регистрации.
_TRIGGER_LOOKBACK = timedelta(minutes=45)
_TRIGGER_LOOKAHEAD = timedelta(minutes=5)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def is_russia(country: str | None, country_code: str | None = None) -> bool | None:
    """Страна первого визита — Россия? None, если страна неизвестна."""
    if country_code:
        return country_code.strip().upper() == "RU"
    if country:
        return country.strip().casefold() in _RUSSIA_NAMES
    return None


def normalize_method(provider: str | None) -> str | None:
    value = (provider or "").strip().lower()
    if value in SIGNUP_METHODS:
        return value
    if value.startswith("email") or "пароль" in value:
        return "email"
    match = re.search(r"\(([a-z]+)\)", value)
    if match and match.group(1) in SIGNUP_METHODS:
        return match.group(1)
    return None


def normalize_locale(value: str | None) -> str | None:
    token = (value or "").strip().lower()
    return token if token in ("ru", "en") else None


# ---------------------------------------------------------------------------
# 1. Запись в запросе регистрации
# ---------------------------------------------------------------------------

async def record_signup(
    db: AsyncSession,
    *,
    user_id,
    method: str | None,
    site_locale: str | None,
    newsletter: bool | None,
    ip: str | None,
    created_at: datetime | None = None,
) -> bool:
    """Серверные поля регистрации. Никогда не бросает: регистрация важнее статистики.

    Возвращает True, если строка создана. Повторный вызов для того же аккаунта
    ничего не меняет (PK по `user_id`).
    """
    try:
        from app.services.geoip import lookup as geo_lookup

        geo = geo_lookup(ip) if ip else {}
        row = UserSignup(
            user_id=user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id)),
            created_at=created_at or _utcnow(),
            method=normalize_method(method),
            site_locale=normalize_locale(site_locale),
            newsletter=None if newsletter is None else bool(newsletter),
            country=(geo.get("country") or None) and geo["country"][:60],
            country_code=(geo.get("country_code") or None) and geo["country_code"][:2],
            geo_region=(geo.get("region") or None) and geo["region"][:120],
            source="request",
        )
        async with db.begin_nested():
            db.add(row)
            await db.flush()
        await db.commit()
        return True
    except IntegrityError:
        # уже есть строка (повторный вызов) — не ошибка
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return False
    except Exception:  # noqa: BLE001
        logger.warning("record_signup failed", exc_info=True)
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return False


# ---------------------------------------------------------------------------
# 2. Дополнение из первой сессии (задача)
# ---------------------------------------------------------------------------

def trigger_from_events(events: Iterable[tuple[str, dict | None, datetime]], signup_at: datetime) -> str | None:
    """«Что подтолкнуло» по событиям посетителя вокруг регистрации.

    `events` — (имя, параметры, время). Если клиент сам прислал `signup.trigger`
    (или другое событие с `trigger` в параметрах), берём его; иначе — ближайшее
    ДО регистрации событие из `TRIGGER_BY_EVENT`.
    """
    best: tuple[datetime, str] | None = None
    for name, params, ts in events:
        client_value = (params or {}).get("trigger") if isinstance(params, dict) else None
        if name == "signup" and client_value in TRIGGER_VALUES:
            return str(client_value)
        mapped = TRIGGER_BY_EVENT.get(name)
        if mapped and ts <= signup_at + _TRIGGER_LOOKAHEAD:
            if best is None or ts > best[0]:
                best = (ts, mapped)
    return best[1] if best else None


async def _fill_one(db: AsyncSession, signup: UserSignup) -> bool:
    """Добирает поля одной регистрации. True — что-то нашли."""
    links = (await db.execute(
        select(IdentityLink.visitor_id_hash).where(IdentityLink.user_id == str(signup.user_id))
    )).scalars().all()
    visitors = list(dict.fromkeys(links))
    found = False
    if visitors:
        first = (await db.execute(
            select(BehaviorSession)
            .where(BehaviorSession.visitor_id_hash.in_(visitors), BehaviorSession.is_synthetic.is_(False))
            .order_by(BehaviorSession.started_at.asc()).limit(1)
        )).scalars().first()
        if first is None:
            first = (await db.execute(
                select(BehaviorSession)
                .where(BehaviorSession.visitor_id_hash.in_(visitors))
                .order_by(BehaviorSession.started_at.asc()).limit(1)
            )).scalars().first()
        if first is not None:
            found = True
            signup.channel = signup.channel or first.channel
            signup.referrer_host = signup.referrer_host or first.referrer_host
            signup.utm_source = signup.utm_source or first.utm_source
            signup.utm_medium = signup.utm_medium or first.utm_medium
            signup.utm_campaign = signup.utm_campaign or first.utm_campaign
            signup.device_type = signup.device_type or first.device_type
            signup.browser = signup.browser or first.browser
            signup.os = signup.os or first.os
            signup.browser_lang = signup.browser_lang or first.language
            signup.landing_page = signup.landing_page or first.entry_page
            if not signup.country and first.country:
                signup.country = first.country[:60]
            if not signup.geo_region and first.geo_region:
                signup.geo_region = first.geo_region[:120]
            if not signup.site_locale:
                signup.site_locale = normalize_locale(first.site_locale)
            signup.days_to_signup = max(0, (signup.created_at.date() - first.started_at.date()).days)

        signup.sessions_before = int(await db.scalar(
            select(func.count(BehaviorSession.session_id_hash))
            .where(BehaviorSession.visitor_id_hash.in_(visitors),
                   BehaviorSession.started_at <= signup.created_at)
        ) or 0)
        signup.pageviews_before = int(await db.scalar(
            select(func.count(BehaviorEvent.id))
            .where(BehaviorEvent.visitor_id_hash.in_(visitors),
                   BehaviorEvent.event_type == "pageview",
                   BehaviorEvent.occurred_at <= signup.created_at)
        ) or 0)

        names = list(TRIGGER_BY_EVENT) + ["signup"]
        rows = (await db.execute(
            select(FrontendEvent.event_name, FrontendEvent.params_json, FrontendEvent.occurred_at)
            .where(FrontendEvent.event_name.in_(names),
                   FrontendEvent.occurred_at >= signup.created_at - _TRIGGER_LOOKBACK,
                   FrontendEvent.occurred_at <= signup.created_at + _TRIGGER_LOOKAHEAD,
                   FrontendEvent.visitor_id_hash.in_(visitors))
        )).all()
        trigger = trigger_from_events(rows, signup.created_at)
        if trigger:
            found = True
            signup.trigger = signup.trigger or trigger
        elif not signup.trigger:
            signup.trigger = "direct"
    signup.filled_at = _utcnow()
    return found


async def ensure_signup_attribution(
    db: AsyncSession,
    *,
    since: datetime | None = None,
    limit: int = 200,
    min_age: timedelta = timedelta(minutes=15),
) -> int:
    """Дополняет регистрации с `filled_at IS NULL`.

    `since` — нижняя граница `created_at` (по умолчанию трое суток: `identity_links`
    возникают при первом авторизованном событии, поэтому первые минуты рано).
    Раз в сутки (ночной прогон) вызывается с большой границей и добирает остаток.
    Пустой результат тоже помечается `filled_at`, чтобы не гонять строку по кругу;
    поздняя `identity_links` добирается повторным вызовом с `refill_empty`.
    """
    since = since or (_utcnow() - timedelta(days=3))
    cutoff = _utcnow() - min_age
    rows = (await db.execute(
        select(UserSignup)
        .where(UserSignup.filled_at.is_(None), UserSignup.created_at >= since,
               UserSignup.created_at <= cutoff)
        .order_by(UserSignup.created_at.asc()).limit(limit)
    )).scalars().all()
    done = 0
    for signup in rows:
        try:
            async with db.begin_nested():
                await _fill_one(db, signup)
            done += 1
        except Exception:  # noqa: BLE001
            logger.warning("signup attribution failed for %s", signup.user_id, exc_info=True)
    if rows:
        await db.commit()
    return done


async def refill_empty_attribution(db: AsyncSession, *, since: datetime, limit: int = 200) -> int:
    """Повторная попытка для регистраций, у которых тогда не нашлось ни одной сессии."""
    rows = (await db.execute(
        select(UserSignup)
        .where(UserSignup.filled_at.is_not(None), UserSignup.channel.is_(None),
               UserSignup.device_type.is_(None), UserSignup.created_at >= since)
        .order_by(UserSignup.created_at.asc()).limit(limit)
    )).scalars().all()
    changed = 0
    for signup in rows:
        try:
            async with db.begin_nested():
                if await _fill_one(db, signup):
                    changed += 1
        except Exception:  # noqa: BLE001
            logger.warning("signup attribution refill failed for %s", signup.user_id, exc_info=True)
    if rows:
        await db.commit()
    return changed


# ---------------------------------------------------------------------------
# 3. Восстановление истории из telegram_outbox
# ---------------------------------------------------------------------------

_LOCALE_LABELS = {"русская": "ru", "английская": "en"}
_VERSION_RE = re.compile(r"Версия сайта:\s*([^\n<]+)")
_METHOD_RE = re.compile(r"Способ входа:\s*([^\n<]+)")
_NEWSLETTER_RE = re.compile(r"Рассылка:\s*(да|нет)")
_ID_RE = re.compile(r"ID:\s*(?:<code>)?\s*([0-9a-fA-F\-]{32,36})")


def parse_new_user_message(text: str | None) -> dict[str, Any]:
    """Разбор текста сообщения «Новый пользователь» (без почты и телефона).

    Возвращает ключи, которые удалось найти: `user_id`, `site_locale`, `method`,
    `newsletter`. Старые сообщения без строки «Версия сайта» дают пустой язык.
    """
    out: dict[str, Any] = {}
    if not text:
        return out
    match = _ID_RE.search(text)
    if match:
        try:
            out["user_id"] = uuid.UUID(match.group(1))
        except ValueError:
            pass
    match = _VERSION_RE.search(text)
    if match:
        locale = _LOCALE_LABELS.get(match.group(1).strip().lower())
        if locale:
            out["site_locale"] = locale
    match = _METHOD_RE.search(text)
    if match:
        method = normalize_method(match.group(1))
        if method:
            out["method"] = method
    match = _NEWSLETTER_RE.search(text)
    if match:
        out["newsletter"] = match.group(1) == "да"
    return out


async def backfill_from_outbox(db: AsyncSession, *, create_missing_users: bool = True) -> dict[str, int]:
    """Создаёт `user_signups(source='backfill')` по архиву и по таблице `users`.

    - сообщения `kind='new_user'` дают язык сайта, способ и рассылку;
    - аккаунты, о которых в архиве нет сообщения, получают строку без языка
      (честная пустота) с `created_at` из `users`;
    - уже существующие строки не перезаписываются.
    Идемпотентно: повторный прогон ничего не дублирует.
    """
    parsed: dict[uuid.UUID, dict[str, Any]] = {}
    outbox = (await db.execute(
        select(TelegramOutbox.text).where(TelegramOutbox.kind == "new_user", TelegramOutbox.method == "sendMessage")
        .order_by(TelegramOutbox.sent_at.asc())
    )).scalars().all()
    for text in outbox:
        info = parse_new_user_message(text)
        uid = info.pop("user_id", None)
        if uid is None:
            continue
        merged = parsed.setdefault(uid, {})
        for key, value in info.items():
            merged.setdefault(key, value)

    existing = set((await db.execute(select(UserSignup.user_id))).scalars().all())
    users = (await db.execute(select(User.id, User.created_at))).all()
    created = skipped = without_locale = 0
    for uid, created_at in users:
        if uid in existing:
            skipped += 1
            continue
        info = parsed.get(uid)
        if info is None and not create_missing_users:
            continue
        info = info or {}
        if not info.get("site_locale"):
            without_locale += 1
        db.add(UserSignup(
            user_id=uid, created_at=created_at, method=info.get("method"),
            site_locale=info.get("site_locale"), newsletter=info.get("newsletter"),
            source="backfill",
        ))
        created += 1
    await db.commit()
    return {"users": len(users), "created": created, "already_present": skipped,
            "without_locale": without_locale, "outbox_messages": len(outbox)}

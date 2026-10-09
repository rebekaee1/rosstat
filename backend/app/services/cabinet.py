"""Личный кабинет: избранное, слежения, история выгрузок, настройки (круг 11, 2026-10-09).

Здесь вся логика без HTTP: проверки допустимых значений, лимиты, upsert, подсчёт
ленты «что вышло нового», токен личного календаря. Маршруты — app/api/cabinet.py.

Ничего не отправляется: слежение («сообщить, когда выйдет значение») в этом круге
только хранится, а «новое» считается при открытии кабинета сравнением последней
даты ряда с `last_seen_date` (никаких заданий планировщика и писем).

Данные кабинета — персональные: не пишем их в логи, `frontend_events` и аналитику.
Таблицы — models.UserSavedItem / UserWatch / UserExport / UserPreference.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Iterable

from sqlalchemy import delete, func, select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    EconomicEvent, Indicator, IndicatorData, RegionIndicator, UserExport,
    UserPreference, UserSavedItem, UserWatch, WorldCountry, WorldDataPoint,
    WorldIndicator, _utcnow_naive,
)
from app.services.locale import get_locale

logger = logging.getLogger(__name__)

# ── Белые списки и лимиты (проверяет API, не БД) ────────────────────────────

SAVED_KINDS = ("indicator", "world", "country", "region", "comparison", "calc", "rating_view")
WATCH_KINDS = ("indicator", "world", "region")
WATCH_CHANNELS = ("inapp",)  # позже: email / telegram / push (требуют отправки и решения владельца)

SAVED_LIMIT = 200
WATCH_LIMIT = 50
EXPORT_HISTORY_LIMIT = 200
IMPORT_BATCH_LIMIT = 100

PAYLOAD_MAX_BYTES = 8192
EXPORT_PARAMS_MAX_BYTES = 4096
PREFS_MAX_BYTES = 2048
_PAYLOAD_MAX_DEPTH = 5
# Принцип 8: в прогнозах никогда диапазон. Кабинет не принимает границы интервала.
FORBIDDEN_KEYS = frozenset({"lower", "upper"})

_CTRL_RE = re.compile(r"[\x00-\x1f\x7f]")
_SOURCE_RE = re.compile(r"^[a-z][a-z0-9_]{0,23}$")


class CabinetError(Exception):
    """Ошибка предметной проверки: `code` стабильный, `status` — HTTP-код."""

    def __init__(self, code: str, status: int = 422, **extra: Any):
        super().__init__(code)
        self.code = code
        self.status = status
        self.extra = extra


# ── Очистка входных значений ────────────────────────────────────────────────

def clean_text(value: str | None, max_len: int, *, required: bool = False) -> str | None:
    text = _CTRL_RE.sub(" ", value or "").strip()
    if not text:
        if required:
            raise CabinetError("invalid_value")
        return None
    return text[:max_len]


def clean_key(value: str | None) -> str:
    key = (value or "").strip()
    if not key or len(key) > 300 or _CTRL_RE.search(key):
        raise CabinetError("invalid_key")
    return key


def _scan(obj: Any, depth: int = 0) -> None:
    if depth > _PAYLOAD_MAX_DEPTH:
        raise CabinetError("payload_too_deep")
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not isinstance(k, str) or len(k) > 64:
                raise CabinetError("invalid_payload")
            if k.lower() in FORBIDDEN_KEYS:
                raise CabinetError("range_not_allowed")
            _scan(v, depth + 1)
    elif isinstance(obj, list):
        if len(obj) > 100:
            raise CabinetError("invalid_payload")
        for v in obj:
            _scan(v, depth + 1)
    elif obj is None or isinstance(obj, (str, int, float, bool)):
        return
    else:
        raise CabinetError("invalid_payload")


def clean_json(obj: Any, max_bytes: int) -> dict | None:
    """JSON-объект параметров: размер, глубина, без границ интервала."""
    if obj is None:
        return None
    if not isinstance(obj, dict):
        raise CabinetError("invalid_payload")
    _scan(obj)
    if len(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) > max_bytes:
        raise CabinetError("payload_too_large")
    return obj


def iso_utc(dt: datetime | None) -> str | None:
    return dt.isoformat() + "Z" if dt else None


# ── Избранное и сохранённое ─────────────────────────────────────────────────

def saved_out(row: UserSavedItem) -> dict:
    return {
        "id": str(row.id),
        "kind": row.kind,
        "item_key": row.item_key,
        "title": row.title,
        "payload": row.payload,
        "created_at": iso_utc(row.created_at),
        "updated_at": iso_utc(row.updated_at),
    }


async def count_saved(db: AsyncSession, user_id: uuid.UUID) -> int:
    return int(await db.scalar(
        select(func.count()).select_from(UserSavedItem).where(UserSavedItem.user_id == user_id)
    ) or 0)


async def find_saved(db: AsyncSession, user_id: uuid.UUID, kind: str, key: str) -> UserSavedItem | None:
    return await db.scalar(select(UserSavedItem).where(
        UserSavedItem.user_id == user_id, UserSavedItem.kind == kind, UserSavedItem.item_key == key,
    ))


async def upsert_saved(
    db: AsyncSession, user_id: uuid.UUID, *, kind: str, item_key: str,
    title: str | None, payload: dict | None, replace_existing: bool = True,
) -> tuple[UserSavedItem, bool]:
    """Создать или обновить запись. Возвращает (строка, создана_ли).

    `replace_existing=False` (перенос избранного гостя при входе): уже сохранённое
    не затираем. Лимит считается только для новых записей.
    """
    if kind not in SAVED_KINDS:
        raise CabinetError("invalid_kind")
    item_key = clean_key(item_key)
    title = clean_text(title, 200)
    payload = clean_json(payload, PAYLOAD_MAX_BYTES)

    existing = await find_saved(db, user_id, kind, item_key)
    if existing is not None:
        if replace_existing:
            if title is not None:
                existing.title = title
            if payload is not None:
                existing.payload = payload
            existing.updated_at = _utcnow_naive()
            await db.flush()
        return existing, False

    if await count_saved(db, user_id) >= SAVED_LIMIT:
        raise CabinetError("limit_reached", 409, limit=SAVED_LIMIT)
    row = UserSavedItem(user_id=user_id, kind=kind, item_key=item_key, title=title, payload=payload)
    try:
        async with db.begin_nested():
            db.add(row)
            await db.flush()
    except IntegrityError:
        # Параллельный запрос успел сохранить тот же ключ: возвращаем его.
        again = await find_saved(db, user_id, kind, item_key)
        if again is None:
            raise
        return again, False
    return row, True


# ── Поиск последней даты ряда (слежения, лента) ─────────────────────────────

@dataclass
class SeriesInfo:
    kind: str
    key: str
    title: str
    unit: str | None
    frequency: str | None
    latest_date: date | None
    latest_value: float | None = None
    country_slug: str | None = None
    country_name: str | None = None


def _pick(ru: str | None, en: str | None) -> str:
    return (en if get_locale() == "en" and en else ru) or en or ru or ""


async def resolve_series(db: AsyncSession, pairs: Iterable[tuple[str, str]]) -> dict[tuple[str, str], SeriesInfo]:
    """Название и последняя дата рядов одним запросом на тип (не по запросу на слежение).

    Видны только публичные ряды (is_listed / is_active): ключ, которого нет в
    результате, считается несуществующим.
    """
    by_kind: dict[str, set[str]] = {}
    for kind, key in pairs:
        by_kind.setdefault(kind, set()).add(key)
    out: dict[tuple[str, str], SeriesInfo] = {}

    if keys := by_kind.get("indicator"):
        rows = (await db.execute(
            select(Indicator.id, Indicator.code, Indicator.name, Indicator.name_en,
                   Indicator.unit, Indicator.frequency, func.max(IndicatorData.date))
            .outerjoin(IndicatorData, IndicatorData.indicator_id == Indicator.id)
            .where(Indicator.code.in_(keys), Indicator.is_active.is_(True), Indicator.is_listed.is_(True))
            .group_by(Indicator.id, Indicator.code, Indicator.name, Indicator.name_en,
                      Indicator.unit, Indicator.frequency)
        )).all()
        ids_dates = [(r[0], r[6]) for r in rows if r[6] is not None]
        values: dict[int, float] = {}
        if ids_dates:
            for iid, val in (await db.execute(
                select(IndicatorData.indicator_id, IndicatorData.value)
                .where(tuple_(IndicatorData.indicator_id, IndicatorData.date).in_(ids_dates))
            )).all():
                values[iid] = float(val)
        for iid, code, name, name_en, unit, freq, latest in rows:
            out[("indicator", code)] = SeriesInfo(
                "indicator", code, _pick(name, name_en), unit, freq, latest, values.get(iid))

    if keys := by_kind.get("world"):
        rows = (await db.execute(
            select(WorldIndicator.id, WorldIndicator.code, WorldIndicator.name_ru, WorldIndicator.name_en,
                   WorldIndicator.unit_ru, WorldIndicator.unit, WorldIndicator.frequency,
                   WorldIndicator.history_end, WorldCountry.slug, WorldCountry.name_ru, WorldCountry.name_en)
            .join(WorldCountry, WorldCountry.id == WorldIndicator.country_id)
            .where(WorldIndicator.code.in_(keys), WorldIndicator.is_listed.is_(True))
        )).all()
        ids_dates = [(r[0], r[7]) for r in rows if r[7] is not None]
        values = {}
        if ids_dates:
            for iid, val in (await db.execute(
                select(WorldDataPoint.indicator_id, WorldDataPoint.value)
                .where(tuple_(WorldDataPoint.indicator_id, WorldDataPoint.date).in_(ids_dates))
            )).all():
                values[iid] = float(val)
        for iid, code, name_ru, name_en, unit_ru, unit, freq, latest, slug, c_ru, c_en in rows:
            out[("world", code)] = SeriesInfo(
                "world", code, _pick(name_ru, name_en), (unit_ru or unit) or None, freq, latest,
                values.get(iid), slug, _pick(c_ru, c_en))

    if keys := by_kind.get("region"):
        rows = (await db.execute(
            select(RegionIndicator.code, RegionIndicator.name, RegionIndicator.unit, RegionIndicator.year_max)
            .where(RegionIndicator.code.in_(keys), RegionIndicator.is_listed.is_(True))
        )).all()
        for code, name, unit, year_max in rows:
            out[("region", code)] = SeriesInfo(
                "region", code, name, unit or None, "annual",
                date(year_max, 1, 1) if year_max else None)
    return out


# ── Слежения и лента ────────────────────────────────────────────────────────

def is_new(latest: date | None, seen: date | None) -> bool:
    return latest is not None and (seen is None or latest > seen)


def watch_out(row: UserWatch, info: SeriesInfo | None) -> dict:
    latest = info.latest_date if info else None
    return {
        "id": str(row.id),
        "subject_kind": row.subject_kind,
        "subject_key": row.subject_key,
        "channel": row.channel,
        "title": info.title if info else None,
        "unit": info.unit if info else None,
        "frequency": info.frequency if info else None,
        "country_slug": info.country_slug if info else None,
        "country_name": info.country_name if info else None,
        "available": info is not None,
        "latest_date": latest.isoformat() if latest else None,
        "latest_value": info.latest_value if info else None,
        "last_seen_date": row.last_seen_date.isoformat() if row.last_seen_date else None,
        "is_new": bool(info) and is_new(latest, row.last_seen_date),
        "created_at": iso_utc(row.created_at),
    }


async def list_watches(db: AsyncSession, user_id: uuid.UUID) -> list[UserWatch]:
    return list((await db.scalars(
        select(UserWatch).where(UserWatch.user_id == user_id).order_by(UserWatch.created_at.desc())
    )).all())


async def watches_with_info(db: AsyncSession, user_id: uuid.UUID) -> list[tuple[UserWatch, SeriesInfo | None]]:
    watches = await list_watches(db, user_id)
    infos = await resolve_series(db, [(w.subject_kind, w.subject_key) for w in watches])
    return [(w, infos.get((w.subject_kind, w.subject_key))) for w in watches]


async def add_watch(db: AsyncSession, user_id: uuid.UUID, kind: str, key: str, channel: str = "inapp") -> tuple[UserWatch, SeriesInfo, bool]:
    if kind not in WATCH_KINDS:
        raise CabinetError("invalid_kind")
    if channel not in WATCH_CHANNELS:
        raise CabinetError("invalid_channel")
    key = clean_key(key)
    info = (await resolve_series(db, [(kind, key)])).get((kind, key))
    if info is None:
        raise CabinetError("subject_not_found", 404)

    existing = await db.scalar(select(UserWatch).where(
        UserWatch.user_id == user_id, UserWatch.subject_kind == kind,
        UserWatch.subject_key == key, UserWatch.channel == channel))
    if existing is not None:
        return existing, info, False
    count = int(await db.scalar(
        select(func.count()).select_from(UserWatch).where(UserWatch.user_id == user_id)) or 0)
    if count >= WATCH_LIMIT:
        raise CabinetError("limit_reached", 409, limit=WATCH_LIMIT)
    # «Новым» станет только значение, вышедшее ПОСЛЕ слежения.
    row = UserWatch(user_id=user_id, subject_kind=kind, subject_key=key, channel=channel,
                    last_seen_date=info.latest_date)
    try:
        async with db.begin_nested():
            db.add(row)
            await db.flush()
    except IntegrityError:
        again = await db.scalar(select(UserWatch).where(
            UserWatch.user_id == user_id, UserWatch.subject_kind == kind,
            UserWatch.subject_key == key, UserWatch.channel == channel))
        if again is None:
            raise
        return again, info, False
    return row, info, True


async def mark_seen(db: AsyncSession, user_id: uuid.UUID, ids: list[uuid.UUID] | None) -> int:
    """Отметить увиденным: last_seen_date = последняя дата ряда. ids=None — все слежения."""
    pairs = await watches_with_info(db, user_id)
    n = 0
    for watch, info in pairs:
        if ids is not None and watch.id not in ids:
            continue
        if info is not None and info.latest_date and watch.last_seen_date != info.latest_date:
            watch.last_seen_date = info.latest_date
            n += 1
    await db.flush()
    return n


# ── История выгрузок ────────────────────────────────────────────────────────

def export_out(row: UserExport) -> dict:
    return {
        "id": str(row.id),
        "source": row.source,
        "subject_key": row.subject_key,
        "format": row.format,
        "params": row.params,
        "rows_count": row.rows_count,
        "created_at": iso_utc(row.created_at),
    }


async def record_export(
    db: AsyncSession, user_id: uuid.UUID, *, source: str, subject_key: str | None,
    fmt: str, params: dict | None, rows_count: int | None,
) -> None:
    """Записать выгрузку в историю и оставить последние EXPORT_HISTORY_LIMIT.

    Вызывающий обязан обернуть в try/except: сбой истории не ломает выгрузку.
    Хранятся параметры, не файл.
    """
    source = source if _SOURCE_RE.match(source or "") else "table"
    try:
        params = clean_json(params, EXPORT_PARAMS_MAX_BYTES)
    except CabinetError:
        params = None  # плохие параметры не должны отменять запись факта выгрузки
    db.add(UserExport(
        user_id=user_id, source=source, subject_key=(clean_text(subject_key, 300) or ""),
        format=fmt[:8], params=params, rows_count=rows_count,
    ))
    await db.flush()
    stale = (await db.scalars(
        select(UserExport.id).where(UserExport.user_id == user_id)
        .order_by(UserExport.created_at.desc(), UserExport.id.desc())
        .offset(EXPORT_HISTORY_LIMIT)
    )).all()
    if stale:
        await db.execute(delete(UserExport).where(UserExport.id.in_(stale)))
    await db.commit()


# ── Настройки ───────────────────────────────────────────────────────────────

async def get_prefs_row(db: AsyncSession, user_id: uuid.UUID) -> UserPreference | None:
    return await db.get(UserPreference, user_id)


async def put_prefs(db: AsyncSession, user_id: uuid.UUID, data: dict) -> UserPreference:
    clean_json(data, PREFS_MAX_BYTES)
    row = await db.get(UserPreference, user_id)
    if row is None:
        row = UserPreference(user_id=user_id, data=data)
        db.add(row)
    else:
        row.data = data
        row.updated_at = _utcnow_naive()
    await db.flush()
    return row


# ── Личная лента календаря (.ics) ───────────────────────────────────────────

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def rotate_feed_token(db: AsyncSession, user_id: uuid.UUID) -> str:
    """Выпустить новый токен ленты (старый перестаёт работать). Токен показываем один раз."""
    token = secrets.token_urlsafe(32)
    row = await db.get(UserPreference, user_id)
    if row is None:
        row = UserPreference(user_id=user_id, data={}, feed_token_hash=hash_token(token))
        db.add(row)
    else:
        row.feed_token_hash = hash_token(token)
        row.updated_at = _utcnow_naive()
    await db.flush()
    return token


async def revoke_feed_token(db: AsyncSession, user_id: uuid.UUID) -> bool:
    row = await db.get(UserPreference, user_id)
    if row is None or row.feed_token_hash is None:
        return False
    row.feed_token_hash = None
    row.updated_at = _utcnow_naive()
    await db.flush()
    return True


async def user_id_by_feed_token(db: AsyncSession, token: str) -> uuid.UUID | None:
    if not token or len(token) > 128:
        return None
    return await db.scalar(
        select(UserPreference.user_id).where(UserPreference.feed_token_hash == hash_token(token)))


def _ics_escape(text: str) -> str:
    return (text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n"))


def _ics_fold(line: str) -> str:
    """RFC 5545: строка не длиннее 75 октетов, продолжение — CRLF + пробел."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line + "\r\n"
    parts: list[str] = []
    cur = b""
    limit = 75
    for ch in line:
        b = ch.encode("utf-8")
        if len(cur) + len(b) > limit:
            parts.append(cur.decode("utf-8"))
            cur = b
            limit = 74  # ведущий пробел продолжения тоже считается
        else:
            cur += b
    parts.append(cur.decode("utf-8"))
    return "\r\n ".join(parts) + "\r\n"


async def build_personal_ics(db: AsyncSession, user_id: uuid.UUID, *, today: date) -> str:
    """Календарь выходов значений по рядам, за которыми следит человек.

    Только публично подтверждённые события (те же условия, что у общего
    /calendar/export/ical) и только федеральные показатели (EconomicEvent
    привязан к `indicators`). Отправки нет: календарь телефона сам читает ленту.
    """
    from app.api.calendar import _public_calendar_conditions  # единое определение «публичного» события

    codes = list((await db.scalars(
        select(UserWatch.subject_key).where(
            UserWatch.user_id == user_id, UserWatch.subject_kind == "indicator")
    )).all())
    events = []
    if codes:
        events = list((await db.execute(
            select(EconomicEvent, Indicator.code)
            .join(Indicator, Indicator.id == EconomicEvent.indicator_id)
            .where(
                Indicator.code.in_(codes),
                EconomicEvent.scheduled_date >= today - timedelta(days=7),
                EconomicEvent.scheduled_date <= today + timedelta(days=180),
                *_public_calendar_conditions(),
            )
            .order_by(EconomicEvent.scheduled_date)
            .limit(500)
        )).all())

    en = get_locale() == "en"
    name = "Forecast Economy: my releases" if en else "Forecast Economy: мои выходы данных"
    stamp = _utcnow_naive().strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Forecast Economy//My releases//RU",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_ics_escape(name)}", "X-WR-TIMEZONE:Europe/Moscow",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H", "X-PUBLISHED-TTL:PT12H",
    ]
    for ev, _code in events:
        title = (ev.title_en if en and ev.title_en else ev.title) or ""
        if ev.reference_period:
            title += f" ({ev.reference_period})"
        desc = [("Source: " if en else "Источник: ") + (ev.source or "").upper()]
        if ev.previous_value:
            desc.append(("Previous: " if en else "Предыдущее: ") + ev.previous_value)
        if ev.scheduled_time:
            desc.append(("Time: " if en else "Время: ") + f"{ev.scheduled_time} " + ("MSK" if en else "МСК"))
        lines += [
            "BEGIN:VEVENT",
            f"UID:fe-event-{ev.id}@forecasteconomy.com",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{ev.scheduled_date.strftime('%Y%m%d')}",
            f"SUMMARY:{_ics_escape(title)}",
            f"DESCRIPTION:{_ics_escape(chr(10).join(desc))}",
        ]
        if ev.source_url:
            lines.append(f"URL:{ev.source_url}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "".join(_ics_fold(line) for line in lines)

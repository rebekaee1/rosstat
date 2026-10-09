"""API личного кабинета (круг 11, 2026-10-09): избранное, слежения, лента, история
выгрузок, настройки, личный календарь .ics.

Всё за флагом `cabinet_enabled` (по умолчанию выключен): при выключенном все ручки,
кроме публичного `GET /cabinet/config`, отвечают 404, остальное поведение сайта не
меняется. Доступ только вошедшему (cookie-сессия), мутации с CSRF (double-submit),
чужие записи недоступны (всегда фильтр по `user_id`, чужой id = 404). Ответы
`Cache-Control: private, no-store`; данные кабинета не пишутся в логи, аналитику и
frontend_events. Ничего не отправляется: слежение даёт только значок «Новое», ленту
и личный календарь (docs/data-contracts.md::Личный кабинет).
"""
from __future__ import annotations

import logging
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import User, UserExport, UserSavedItem, UserWatch
from app.security.auth import get_current_user, require_csrf
from app.services import cabinet as svc
from app.services.api_i18n import api_detail
from app.services.display import today_msk

logger = logging.getLogger(__name__)

# Публичный флаг для фронта (по образцу /api-interest/config и /pwa/config): всегда 200.
config_router = APIRouter(prefix="/cabinet", tags=["cabinet"])


def _require_enabled() -> None:
    if not settings.cabinet_enabled:
        raise HTTPException(status_code=404, detail="Not found")


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


router = APIRouter(
    prefix="/cabinet", tags=["cabinet"],
    dependencies=[Depends(_require_enabled), Depends(_no_store)],
)

_MESSAGES = {
    "invalid_kind": ("Неизвестный тип записи", "Unknown item type"),
    "invalid_key": ("Некорректный ключ записи", "Invalid item key"),
    "invalid_value": ("Некорректное значение", "Invalid value"),
    "invalid_payload": ("Некорректные параметры записи", "Invalid item parameters"),
    "invalid_channel": ("Этот способ уведомления пока недоступен", "This notification channel is not available yet"),
    "payload_too_large": ("Слишком большой объём параметров", "Parameters are too large"),
    "payload_too_deep": ("Слишком сложные параметры", "Parameters are too nested"),
    "range_not_allowed": ("Границы диапазона не принимаются", "Range bounds are not accepted"),
    "limit_reached": ("Достигнут предел количества записей", "The limit of entries is reached"),
    "subject_not_found": ("Показатель не найден", "Indicator not found"),
}


def _raise(err: svc.CabinetError):
    ru, en = _MESSAGES.get(err.code, ("Некорректный запрос", "Invalid request"))
    raise HTTPException(
        status_code=err.status,
        detail={"code": err.code, "message": api_detail(ru, en), **err.extra},
    )


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={"code": "not_found", "message": api_detail("Не найдено", "Not found")})


# ── Конфиг ───────────────────────────────────────────────────────────────────

@config_router.get("/config")
async def cabinet_config(response: Response):
    """Публичный флаг и пределы для фронта (читается без пересборки)."""
    response.headers["Cache-Control"] = "no-store"
    if not settings.cabinet_enabled:
        return {"enabled": False, "features": {}, "limits": {}}
    return {
        "enabled": True,
        "features": {
            "saved": True,
            "watches": True,
            "feed": True,
            "exports": True,
            "prefs": True,
            "calendar_feed": True,
            # В этом круге ничего не отправляется: единственный канал слежения — «в кабинете».
            "watch_channels": list(svc.WATCH_CHANNELS),
            "saved_kinds": list(svc.SAVED_KINDS),
            "watch_kinds": list(svc.WATCH_KINDS),
        },
        "limits": {
            "saved": svc.SAVED_LIMIT,
            "watches": svc.WATCH_LIMIT,
            "exports": svc.EXPORT_HISTORY_LIMIT,
            "import_batch": svc.IMPORT_BATCH_LIMIT,
        },
    }


# ── Избранное и сохранённое ──────────────────────────────────────────────────

class SavedIn(BaseModel):
    kind: str
    item_key: str
    title: str | None = None
    payload: dict | None = None


class SavedRename(BaseModel):
    title: str

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        try:
            return svc.clean_text(v, 200, required=True) or ""
        except svc.CabinetError:
            raise ValueError("title is empty") from None


class SavedImportIn(BaseModel):
    items: list[SavedIn] = Field(max_length=svc.IMPORT_BATCH_LIMIT)


def _check_kind(kind: str | None) -> str | None:
    if kind is not None and kind not in svc.SAVED_KINDS:
        _raise(svc.CabinetError("invalid_kind"))
    return kind


@router.get("/saved")
async def list_saved(
    kind: str | None = Query(None, max_length=24),
    key: str | None = Query(None, max_length=300),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Список сохранённого (новые сверху). `kind` и `key` — необязательные фильтры."""
    _check_kind(kind)
    stmt = select(UserSavedItem).where(UserSavedItem.user_id == user.id)
    if kind:
        stmt = stmt.where(UserSavedItem.kind == kind)
    if key:
        stmt = stmt.where(UserSavedItem.item_key == key)
    rows = (await db.scalars(stmt.order_by(UserSavedItem.created_at.desc(), UserSavedItem.id))).all()
    return {
        "items": [svc.saved_out(r) for r in rows],
        "count": len(rows),
        "total": await svc.count_saved(db, user.id) if (kind or key) else len(rows),
        "limit": svc.SAVED_LIMIT,
    }


@router.post("/saved", dependencies=[Depends(require_csrf)])
async def save_item(
    body: SavedIn, response: Response,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Сохранить (upsert по kind+item_key). 201 — новая запись, 200 — обновлена существующая."""
    try:
        row, created = await svc.upsert_saved(
            db, user.id, kind=body.kind, item_key=body.item_key, title=body.title, payload=body.payload)
        await db.commit()
    except svc.CabinetError as err:
        await db.rollback()
        _raise(err)
    response.status_code = 201 if created else 200
    return {"item": svc.saved_out(row), "created": created}


@router.post("/saved/import", dependencies=[Depends(require_csrf)])
async def import_saved(
    body: SavedImportIn,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Перенос избранного гостя при входе: до лимита, уже сохранённое не затирается.

    Некорректные записи пропускаются по одной (не валят весь перенос).
    """
    imported = skipped = 0
    limit_reached = False
    for item in body.items:
        try:
            _row, created = await svc.upsert_saved(
                db, user.id, kind=item.kind, item_key=item.item_key, title=item.title,
                payload=item.payload, replace_existing=False)
        except svc.CabinetError as err:
            skipped += 1
            if err.code == "limit_reached":
                limit_reached = True
                break
            continue
        imported += 1 if created else 0
        skipped += 0 if created else 1
    await db.commit()
    return {"imported": imported, "skipped": skipped, "limit_reached": limit_reached,
            "total": await svc.count_saved(db, user.id), "limit": svc.SAVED_LIMIT}


@router.patch("/saved/{item_id}", dependencies=[Depends(require_csrf)])
async def rename_saved(
    item_id: uuid.UUID, body: SavedRename,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    row = await db.scalar(select(UserSavedItem).where(
        UserSavedItem.id == item_id, UserSavedItem.user_id == user.id))
    if row is None:
        raise _not_found()
    row.title = body.title
    row.updated_at = svc._utcnow_naive()
    await db.commit()
    return {"item": svc.saved_out(row)}


@router.delete("/saved/{item_id}", dependencies=[Depends(require_csrf)])
async def delete_saved(
    item_id: uuid.UUID,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    res = await db.execute(delete(UserSavedItem).where(
        UserSavedItem.id == item_id, UserSavedItem.user_id == user.id))
    await db.commit()
    if not res.rowcount:
        raise _not_found()
    return {"ok": True}


@router.delete("/saved", dependencies=[Depends(require_csrf)])
async def delete_saved_by_key(
    kind: str = Query(..., max_length=24), key: str = Query(..., min_length=1, max_length=300),
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Снять звёздочку по (kind, key) без знания id. Повторное снятие — 200 (`removed: false`)."""
    _check_kind(kind)
    res = await db.execute(delete(UserSavedItem).where(
        UserSavedItem.user_id == user.id, UserSavedItem.kind == kind, UserSavedItem.item_key == key))
    await db.commit()
    return {"ok": True, "removed": bool(res.rowcount)}


# ── Слежения и лента ─────────────────────────────────────────────────────────

class WatchIn(BaseModel):
    subject_kind: str
    subject_key: str
    channel: str = "inapp"


class SeenIn(BaseModel):
    ids: list[uuid.UUID] | None = Field(default=None, max_length=svc.WATCH_LIMIT)


@router.get("/watches")
async def list_watches(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    pairs = await svc.watches_with_info(db, user.id)
    items = [svc.watch_out(w, info) for w, info in pairs]
    return {"items": items, "count": len(items), "limit": svc.WATCH_LIMIT,
            "new_count": sum(1 for i in items if i["is_new"])}


@router.post("/watches", dependencies=[Depends(require_csrf)])
async def add_watch(
    body: WatchIn, response: Response,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Следить за рядом (канал `inapp`; письма и push в этом круге не отправляются)."""
    try:
        row, info, created = await svc.add_watch(
            db, user.id, body.subject_kind, body.subject_key, body.channel)
        await db.commit()
    except svc.CabinetError as err:
        await db.rollback()
        _raise(err)
    response.status_code = 201 if created else 200
    return {"item": svc.watch_out(row, info), "created": created}


@router.delete("/watches/{watch_id}", dependencies=[Depends(require_csrf)])
async def delete_watch(
    watch_id: uuid.UUID,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    res = await db.execute(delete(UserWatch).where(
        UserWatch.id == watch_id, UserWatch.user_id == user.id))
    await db.commit()
    if not res.rowcount:
        raise _not_found()
    return {"ok": True}


@router.delete("/watches", dependencies=[Depends(require_csrf)])
async def delete_watch_by_key(
    subject_kind: str = Query(..., max_length=24), subject_key: str = Query(..., min_length=1, max_length=300),
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Снять слежение по (subject_kind, subject_key). Повторное снятие — 200 (`removed: false`)."""
    res = await db.execute(delete(UserWatch).where(
        UserWatch.user_id == user.id, UserWatch.subject_kind == subject_kind,
        UserWatch.subject_key == subject_key))
    await db.commit()
    return {"ok": True, "removed": bool(res.rowcount)}


@router.get("/feed")
async def feed(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """«Что вышло с вашего последнего визита»: слежения, у которых последняя дата ряда
    новее `last_seen_date`. Один пакетный запрос на тип ряда, не запрос на слежение."""
    pairs = await svc.watches_with_info(db, user.id)
    items = [svc.watch_out(w, info) for w, info in pairs]
    new_items = sorted((i for i in items if i["is_new"]), key=lambda i: i["latest_date"], reverse=True)
    return {"new_count": len(new_items), "items": new_items, "watching": len(items)}


@router.post("/feed/seen", dependencies=[Depends(require_csrf)])
async def feed_seen(
    body: SeenIn | None = None,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Отметить увиденным (все слежения или `ids`). Возвращает обновлённую ленту."""
    await svc.mark_seen(db, user.id, body.ids if body else None)
    await db.commit()
    return await feed(user=user, db=db)


# ── История выгрузок ─────────────────────────────────────────────────────────

@router.get("/exports")
async def list_exports(
    limit: int = Query(50, ge=1, le=svc.EXPORT_HISTORY_LIMIT),
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Последние выгрузки: параметры, формат, дата (файлы не хранятся)."""
    rows = (await db.scalars(
        select(UserExport).where(UserExport.user_id == user.id)
        .order_by(UserExport.created_at.desc(), UserExport.id.desc()).limit(limit)
    )).all()
    total = int(await db.scalar(
        select(func.count()).select_from(UserExport).where(UserExport.user_id == user.id)) or 0)
    return {"items": [svc.export_out(r) for r in rows], "count": len(rows), "total": total}


@router.delete("/exports/{export_id}", dependencies=[Depends(require_csrf)])
async def delete_export(
    export_id: uuid.UUID,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    res = await db.execute(delete(UserExport).where(
        UserExport.id == export_id, UserExport.user_id == user.id))
    await db.commit()
    if not res.rowcount:
        raise _not_found()
    return {"ok": True}


@router.delete("/exports", dependencies=[Depends(require_csrf)])
async def clear_exports(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Очистить всю историю выгрузок."""
    res = await db.execute(delete(UserExport).where(UserExport.user_id == user.id))
    await db.commit()
    return {"ok": True, "removed": int(res.rowcount or 0)}


# ── Настройки ────────────────────────────────────────────────────────────────

_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,32}$")
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,79}$")


class PrefsIn(BaseModel):
    """Белый список полей настроек; неизвестное поле — 422. Все поля необязательны."""
    model_config = ConfigDict(extra="forbid")

    locale: str | None = None            # язык по умолчанию: ru | en
    units: str | None = None             # единицы: токен, значения определяет интерфейс
    number_format: str | None = None     # формат чисел: токен
    currency: str | None = None          # валюта по умолчанию: ISO-код из трёх букв
    home_country: str | None = None      # главная страна: slug
    newsletter_topics: list[str] | None = Field(default=None, max_length=12)  # темы рассылки (хранение; не согласие)

    @field_validator("locale")
    @classmethod
    def _locale(cls, v):
        if v is not None and v not in ("ru", "en"):
            raise ValueError("locale")
        return v

    @field_validator("units", "number_format")
    @classmethod
    def _token(cls, v):
        if v is not None and not _TOKEN_RE.match(v):
            raise ValueError("token")
        return v

    @field_validator("currency")
    @classmethod
    def _currency(cls, v):
        if v is not None and not re.fullmatch(r"[A-Z]{3}", v):
            raise ValueError("currency")
        return v

    @field_validator("home_country")
    @classmethod
    def _country(cls, v):
        if v is not None and not _SLUG_RE.match(v):
            raise ValueError("country")
        return v

    @field_validator("newsletter_topics")
    @classmethod
    def _topics(cls, v):
        if v is not None:
            if any(not _TOKEN_RE.match(t) for t in v):
                raise ValueError("topics")
            v = list(dict.fromkeys(v))
        return v


def _prefs_out(row) -> dict:
    return {"data": (row.data if row else {}) or {}, "updated_at": svc.iso_utc(row.updated_at) if row else None}


@router.get("/prefs")
async def get_prefs(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return _prefs_out(await svc.get_prefs_row(db, user.id))


@router.put("/prefs", dependencies=[Depends(require_csrf)])
async def put_prefs(
    body: PrefsIn,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Заменяет настройки целиком (поля без значения не сохраняются)."""
    try:
        row = await svc.put_prefs(db, user.id, body.model_dump(exclude_none=True))
        await db.commit()
    except svc.CabinetError as err:
        await db.rollback()
        _raise(err)
    return _prefs_out(row)


# ── Личный календарь .ics ────────────────────────────────────────────────────

@router.get("/calendar-feed")
async def calendar_feed_status(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row = await svc.get_prefs_row(db, user.id)
    return {"active": bool(row and row.feed_token_hash)}


@router.post("/calendar-feed", dependencies=[Depends(require_csrf)])
async def calendar_feed_rotate(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Выпустить (или перевыпустить) личную ссылку календаря. Токен показывается ОДИН раз;
    старая ссылка перестаёт работать. Ссылку строит фронт: `{origin}{path}`, для
    подписки в календаре телефона — со схемой webcal://."""
    token = await svc.rotate_feed_token(db, user.id)
    await db.commit()
    return {"active": True, "token": token, "path": f"/api/v1/cabinet/calendar.ics?token={token}"}


@router.delete("/calendar-feed", dependencies=[Depends(require_csrf)])
async def calendar_feed_revoke(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    removed = await svc.revoke_feed_token(db, user.id)
    await db.commit()
    return {"active": False, "removed": removed}


@router.get("/calendar.ics")
async def calendar_ics(
    token: str = Query(..., min_length=16, max_length=128),
    db: AsyncSession = Depends(get_db),
):
    """Личная лента календаря по токену (без cookie-сессии: её читает календарь телефона).

    Токен — 256 бит случайности, в БД только его SHA-256. Неверный токен = 404.
    Лента содержит только даты публикаций рядов, за которыми следит человек."""
    user_id = await svc.user_id_by_feed_token(db, token)
    if user_id is None:
        raise HTTPException(status_code=404, detail="Not found")
    user = await db.get(User, user_id)
    if user is None or user.status != "active":
        raise HTTPException(status_code=404, detail="Not found")
    body = await svc.build_personal_ics(db, user_id, today=today_msk())
    return Response(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={"Cache-Control": "private, no-store", "X-Robots-Tag": "noindex",
                 "Referrer-Policy": "no-referrer"},
    )

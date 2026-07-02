"""Интерактивный Telegram-бот владельца (П9б, 2026-07-02).

Два контура:
1. Отправка сообщений с inline-кнопками (`send_message`, `send_document`) —
   современное оформление Bot API: HTML + <blockquote expandable>.
2. Поллер `telegram_poll_job` (APScheduler, каждые 30 с): getUpdates с offset
   в state-Redis (`fe:tg:offset`). Обрабатывает ТОЛЬКО чат владельца
   (`settings.pulse_chat_id`) — чужие апдейты подтверждаются и игнорируются.

Кнопки главного меню:
- «Пользователи» — таблица всех пользователей (expandable blockquote);
- «CSV пользователей» — файл-выгрузка sendDocument;
- «Пульс сегодня» — снапшот текущего дня на лету;
- под таблицей пользователей — кнопка на каждого → карточка-аналитика
  (identity, консенты, история входов из auth_audit).

Здесь нет вебхука сознательно: бэкенд за NAT, поллинг раз в 30 с достаточен
для админ-бота и не требует публичного HTTPS-эндпоинта.
"""
from __future__ import annotations

import io
import json
import logging
from datetime import date, datetime, timezone
from html import escape

import httpx
from sqlalchemy import func, select

from app.config import settings
from app.core.cache import get_state_redis
from app.database import async_session
from app.models import AuthAudit, Consent, EmailCredential, OAuthIdentity, User

logger = logging.getLogger(__name__)

_API = "https://api.telegram.org/bot{token}/{method}"
_OFFSET_KEY = "fe:tg:offset"


# ---------------------------------------------------------------------------
# Отправка
# ---------------------------------------------------------------------------

def main_menu_keyboard() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "👥 Пользователи", "callback_data": "users"},
                {"text": "📄 CSV пользователей", "callback_data": "users_csv"},
            ],
            [{"text": "🛰 Пульс сегодня", "callback_data": "pulse_today"}],
        ]
    }


async def _api(method: str, payload: dict, files: dict | None = None) -> dict | None:
    token = settings.telegram_bot_token
    if not token:
        return None
    url = _API.format(token=token, method=method)
    try:
        async with httpx.AsyncClient(timeout=35) as client:
            if files:
                resp = await client.post(url, data=payload, files=files)
            else:
                resp = await client.post(url, json=payload)
        data = resp.json()
        if not data.get("ok"):
            logger.warning("Telegram %s failed: %s", method, str(data)[:300])
            return None
        return data
    except Exception:
        logger.warning("Telegram %s failed", method, exc_info=True)
        return None


async def send_message(chat_id: str, text: str, reply_markup: dict | None = None) -> bool:
    payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await _api("sendMessage", payload) is not None


async def send_document(chat_id: str, filename: str, content: bytes, caption: str = "") -> bool:
    payload = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
    files = {"document": (filename, io.BytesIO(content))}
    return await _api("sendDocument", payload, files=files) is not None


# ---------------------------------------------------------------------------
# Данные о пользователях
# ---------------------------------------------------------------------------

async def _users_overview() -> tuple[str, dict]:
    """Таблица пользователей + клавиатура с кнопкой на каждого."""
    async with async_session() as db:
        users = (await db.execute(
            select(User).order_by(User.created_at.desc())
        )).scalars().all()
        emails = dict((await db.execute(
            select(EmailCredential.user_id, EmailCredential.email)
        )).all())
        oauth: dict = {}
        for uid, provider in (await db.execute(
            select(OAuthIdentity.user_id, OAuthIdentity.provider)
        )).all():
            oauth.setdefault(uid, []).append(provider)

    if not users:
        return "Пользователей пока нет.", main_menu_keyboard()

    rows = []
    buttons = []
    for i, u in enumerate(users, 1):
        contact = emails.get(u.id) or "—"
        methods = (["email"] if u.id in emails else []) + oauth.get(u.id, [])
        created = u.created_at.strftime("%d.%m.%Y") if u.created_at else "—"
        rows.append(
            f"{i}. {escape(u.display_name or '—')} — {escape(str(contact)[:40])} "
            f"({escape('/'.join(methods) or '—')}), с {created}"
        )
        if len(buttons) < 30:  # телеграм-лимит на размер клавиатуры
            label = (u.display_name or str(contact))[:28]
            buttons.append([{"text": f"👤 {label}", "callback_data": f"user:{u.id}"}])

    text = (
        f"👥 <b>Пользователи: {len(users)}</b>\n"
        f"<blockquote expandable>{chr(10).join(rows)}</blockquote>\n"
        "Кнопка ниже — подробная карточка."
    )
    buttons.append([{"text": "⬅️ Меню", "callback_data": "menu"}])
    return text, {"inline_keyboard": buttons}


async def _user_card(user_id: str) -> str:
    async with async_session() as db:
        user = await db.get(User, user_id)
        if user is None:
            return "Пользователь не найден (удалён?)."
        email = await db.scalar(
            select(EmailCredential.email).where(EmailCredential.user_id == user.id)
        )
        oauth = (await db.execute(
            select(OAuthIdentity.provider, OAuthIdentity.email, OAuthIdentity.phone)
            .where(OAuthIdentity.user_id == user.id)
        )).all()
        consents = (await db.execute(
            select(Consent.kind, Consent.granted).where(Consent.user_id == user.id)
        )).all()
        audit = (await db.execute(
            select(AuthAudit.event, AuthAudit.ip, AuthAudit.ts)
            .where(AuthAudit.user_id == user.id)
            .order_by(AuthAudit.ts.desc()).limit(10)
        )).all()
        n_logins = await db.scalar(
            select(func.count(AuthAudit.id))
            .where(AuthAudit.user_id == user.id, AuthAudit.event == "login")
        ) or 0

    lines = [
        f"👤 <b>{escape(user.display_name or 'Без имени')}</b>",
        f"ID: <code>{user.id}</code>",
        f"Статус: {escape(user.status)}",
        f"Email: {escape(email or '—')}",
    ]
    for provider, oemail, phone in oauth:
        extra = oemail or phone or ""
        lines.append(f"OAuth ({escape(provider)}): {escape(str(extra) or '—')}")
    if user.created_at:
        lines.append(f"Зарегистрирован: {user.created_at.strftime('%d.%m.%Y %H:%M')} UTC")
    lines.append(f"Всего входов: {n_logins}")
    if consents:
        cs = ", ".join(f"{k}: {'да' if g else 'нет'}" for k, g in consents)
        lines.append(f"Согласия: {escape(cs)}")
    if audit:
        rows = [
            f"{ts.strftime('%d.%m %H:%M')} {escape(ev)} ({escape(ip or '—')})"
            for ev, ip, ts in audit
        ]
        lines.append(f"<blockquote expandable>Последние события:\n{chr(10).join(rows)}</blockquote>")
    return "\n".join(lines)


async def _users_csv() -> bytes:
    async with async_session() as db:
        users = (await db.execute(select(User).order_by(User.created_at))).scalars().all()
        emails = dict((await db.execute(
            select(EmailCredential.user_id, EmailCredential.email)
        )).all())
        oauth: dict = {}
        for uid, provider, phone in (await db.execute(
            select(OAuthIdentity.user_id, OAuthIdentity.provider, OAuthIdentity.phone)
        )).all():
            oauth.setdefault(uid, []).append((provider, phone))

    out = io.StringIO()
    out.write("id;name;email;phone;methods;status;created_at\n")
    for u in users:
        methods = (["email"] if u.id in emails else []) + [p for p, _ in oauth.get(u.id, [])]
        phone = next((ph for _, ph in oauth.get(u.id, []) if ph), "")
        created = u.created_at.isoformat() if u.created_at else ""
        name = (u.display_name or "").replace(";", ",")
        out.write(f"{u.id};{name};{emails.get(u.id, '')};{phone};{'/'.join(methods)};{u.status};{created}\n")
    # BOM — чтобы Excel открыл кириллицу без танцев
    return ("\ufeff" + out.getvalue()).encode("utf-8")


# ---------------------------------------------------------------------------
# Поллер
# ---------------------------------------------------------------------------

async def _handle_callback(cq: dict) -> None:
    """Обработка нажатия кнопки. Только чат владельца."""
    await _api("answerCallbackQuery", {"callback_query_id": cq["id"]})
    chat_id = str(cq.get("message", {}).get("chat", {}).get("id", ""))
    if chat_id != str(settings.pulse_chat_id):
        return
    data = cq.get("data", "")

    if data == "users":
        text, kb = await _users_overview()
        await send_message(chat_id, text, reply_markup=kb)
    elif data == "users_csv":
        csv_bytes = await _users_csv()
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        await send_document(chat_id, f"users-{stamp}.csv", csv_bytes, caption="👥 Все пользователи")
    elif data == "pulse_today":
        from app.services import pulse  # локальный импорт против цикла
        snap = await pulse.build_snapshot(date.today())
        ev = snap.get("events", {})
        text = (
            f"🛰 <b>Пульс на сейчас ({snap['date']})</b>\n"
            f"Событий: {ev.get('total', 0)}, "
            f"скачиваний: {sum(ev.get('downloads', {}).values())}, "
            f"ошибок: {sum(ev.get('errors', {}).values())}\n"
            f"Пользователей всего: {snap.get('users', {}).get('total', 0)} "
            f"(+{snap.get('users', {}).get('new', 0)} сегодня)\n"
            f"<blockquote expandable>{escape(json.dumps(ev.get('by_name', {}), ensure_ascii=False))}</blockquote>"
        )
        await send_message(chat_id, text, reply_markup=main_menu_keyboard())
    elif data.startswith("user:"):
        text = await _user_card(data.split(":", 1)[1])
        await send_message(chat_id, text, reply_markup=main_menu_keyboard())
    elif data == "menu":
        await send_message(chat_id, "Меню:", reply_markup=main_menu_keyboard())


async def _handle_message(msg: dict) -> None:
    chat_id = str(msg.get("chat", {}).get("id", ""))
    if chat_id != str(settings.pulse_chat_id):
        return
    text = (msg.get("text") or "").strip().lower()
    if text in ("/start", "/menu", "меню"):
        await send_message(chat_id, "🛰 <b>Forecast Economy — пульс</b>\nВыберите раздел:", reply_markup=main_menu_keyboard())
    elif text == "/users":
        t, kb = await _users_overview()
        await send_message(chat_id, t, reply_markup=kb)


async def telegram_poll_job() -> None:
    """Разовый цикл getUpdates (запускается APScheduler'ом каждые 30 с)."""
    if not (settings.telegram_bot_token and settings.pulse_chat_id):
        return
    r = await get_state_redis()
    offset = await r.get(_OFFSET_KEY)
    payload: dict = {"timeout": 20, "allowed_updates": ["message", "callback_query"]}
    if offset:
        payload["offset"] = int(offset)
    data = await _api("getUpdates", payload)
    if not data:
        return
    updates = data.get("result", [])
    for upd in updates:
        try:
            if "callback_query" in upd:
                await _handle_callback(upd["callback_query"])
            elif "message" in upd:
                await _handle_message(upd["message"])
        except Exception:
            logger.warning("Telegram update %s failed", upd.get("update_id"), exc_info=True)
    if updates:
        await r.set(_OFFSET_KEY, str(updates[-1]["update_id"] + 1))

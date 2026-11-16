"""Учёт открытий и переходов из писем (ADR-0034, 16.11.2026).

Что делает:
* перед отправкой (готовый HTML, шаблон не меняется) добавляет пиксель открытия и метку человека
  `utm_term=r<…>` на ссылки рассылки, ведущие на наш сайт;
* по запросу пикселя пишет событие `open` и итог в строку журнала письма;
* задачей переносит переходы из сессий сайта (`behavior_sessions`, `utm_medium=newsletter`) в события
  `click` письма.

Решение по переходам: ссылка в письме ведёт сразу на страницу сайта, без промежуточного адреса.
Свой редирект ловил бы и переходы без JavaScript, но при любом сбое API (перегрузка, выпуск) ссылки
всех уже отправленных писем перестали бы открываться. Здесь при сбое учёта теряется только учёт.

Чего учёт не знает и не выдаёт за знание:
* Apple Mail (защита приватности), сканеры почтовых шлюзов и предзагрузка открывают пиксель сами —
  такие открытия помечаются `machine=True` и в «открыли люди» не входят;
* почта с выключенными картинками не открывает пиксель вовсе — доля открытий занижена;
* Gmail и Яндекс показывают картинки через свой прокси: видно, что письмо открыто, но не чем.

Приватность: учёт идёт только при `RUSTATS_MAIL_TRACKING_ENABLED=true` и только у людей, которые
не отказались от персональной подборки (журнал согласий `mail_personal_revoked`). IP и строка
User-Agent не сохраняются. Адрес получателя в события не попадает.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import BehaviorSession, IdentityLink, MailEvent, MailMessage
from app.services.mail import tokens

logger = logging.getLogger(__name__)

TRACKED_KINDS = frozenset({"newsletter", "watch_digest", "reconfirm"})
# Открытие раньше этого срока после отправки — проверка письма почтовым сервером, не человек.
FAST_OPEN_SECONDS = 20
CLICK_SYNC_DAYS = 35
# Прозрачная точка 1×1 (GIF, 43 байта).
PIXEL = (b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,"
         b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")

_PROVIDERS = (
    ("gmail", ("gmail.com", "googlemail.com")),
    ("yandex", ("yandex.ru", "ya.ru", "yandex.com", "yandex.by", "yandex.kz", "narod.ru")),
    ("mailru", ("mail.ru", "list.ru", "bk.ru", "inbox.ru", "internet.ru", "vk.com")),
    ("outlook", ("outlook.com", "hotmail.com", "live.com", "live.ru", "msn.com")),
    ("icloud", ("icloud.com", "me.com", "mac.com")),
    ("rambler", ("rambler.ru", "lenta.ru", "ro.ru")),
)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def enabled() -> bool:
    return bool(settings.mail_tracking_enabled)


def provider_of(addr: str | None) -> str:
    """Группа почтового сервиса по домену адреса (сам адрес никуда не пишется)."""
    domain = (addr or "").rsplit("@", 1)[-1].strip().lower()
    for name, domains in _PROVIDERS:
        if domain in domains:
            return name
    return "other" if domain else "unknown"


def classify_open(user_agent: str | None, seconds_since_sent: float | None) -> tuple[str, bool]:
    """(класс почтовой программы, открыла ли программа сама). Строка User-Agent не сохраняется."""
    ua = (user_agent or "").strip()
    low = ua.lower()
    if "googleimageproxy" in low or "ggpht.com" in low:
        return "gmail_proxy", bool(seconds_since_sent is not None and seconds_since_sent < FAST_OPEN_SECONDS)
    if "yandex" in low and ("image" in low or "resizer" in low or "bot" in low or "proxy" in low):
        return "yandex_proxy", bool(seconds_since_sent is not None and seconds_since_sent < FAST_OPEN_SECONDS)
    if not ua or any(w in low for w in ("bot", "scanner", "curl", "python", "wget", "barracuda", "proofpoint",
                                         "mimecast", "symantec", "headless", "preview", "spider", "http-client")):
        return "scanner", True
    if ua == "Mozilla/5.0":
        # Так представляется защита приватности Apple Mail: письмо загружается заранее, без человека.
        return "apple_privacy", True
    if seconds_since_sent is not None and seconds_since_sent < FAST_OPEN_SECONDS:
        return "scanner", True
    return "mail_client", False


def open_token(mail_id: int) -> str:
    return tokens.issue("open", str(int(mail_id)))


def pixel_url(row: MailMessage) -> str:
    from app.services.mail import service

    return service.api_link(row.locale or "ru", f"/mail/o/{open_token(row.id)}.gif")


_HREF_RE = re.compile(r'href="(https?://[^"]+)"')
_TEXT_URL_RE = re.compile(r"https?://[^\s<>\"]+")


def _with_term(url: str, term: str, *, html: bool) -> str:
    """Метка человека на ссылке рассылки, ведущей на наш сайт (у которой её ещё нет)."""
    probe = url.replace("&amp;", "&") if html else url
    if "utm_medium=newsletter" not in probe or "utm_term=" in probe:
        return url
    return f"{url}{'&amp;' if html else '&'}utm_term={term}"


def instrument(html: str, text: str, row: MailMessage, *, click_term: str | None) -> tuple[str, str]:
    """Готовое письмо → письмо с пикселем открытия и метками переходов. Ошибка = письмо как было."""
    try:
        out_html, out_text = html, text
        if click_term:
            out_html = _HREF_RE.sub(lambda m: f'href="{_with_term(m.group(1), click_term, html=True)}"', out_html)
            out_text = _TEXT_URL_RE.sub(lambda m: _with_term(m.group(0), click_term, html=False), out_text)
        pixel = (f'<img src="{pixel_url(row)}" width="1" height="1" alt="" '
                 'style="display:block;width:1px;height:1px;border:0;opacity:0" />')
        if "</body>" in out_html:
            head, _sep, tail = out_html.rpartition("</body>")
            out_html = f"{head}{pixel}</body>{tail}"
        else:
            out_html += pixel
        return out_html, out_text
    except Exception:  # noqa: BLE001 — учёт не должен мешать письму
        logger.warning("mail tracking instrument failed kind=%s", row.kind, exc_info=True)
        return html, text


async def allowed_for(db: AsyncSession, row: MailMessage) -> bool:
    """Учитывать ли это письмо: флаг, вид письма, есть человек и он не отказался от подборки."""
    if not enabled() or row.kind not in TRACKED_KINDS or row.user_id is None or row.id is None:
        return False
    try:
        tokens._secret()
    except tokens.TokenSecretMissing:
        return False
    from app.services.newsletter_personal.signals import personal_off

    return not await personal_off(db, row.user_id)


async def prepare(db: AsyncSession, row: MailMessage, html: str, text: str) -> tuple[str, str]:
    """Вызывается из `service.attempt` перед отправкой: разрезы строки журнала и учёт."""
    row.provider = row.provider or provider_of(row.to_email)
    try:
        ok = await allowed_for(db, row)
    except Exception:  # noqa: BLE001
        logger.warning("mail tracking check failed", exc_info=True)
        ok = False
    row.tracked = bool(ok)
    if not ok:
        return html, text
    term = None
    if row.campaign:
        from app.services.newsletter_personal import ab

        term = ab.click_token(str(row.user_id), row.campaign)
    return instrument(html, text, row, click_term=term)


async def record_open(db: AsyncSession, token: str, user_agent: str | None, *, now: datetime | None = None) -> bool:
    """Запрос пикселя → событие открытия. False — ссылка не наша или учёт у человека выключен."""
    if not enabled():
        return False
    try:
        tok = tokens.verify("open", token)
        mail_id = int(tok.user_id)
    except (tokens.TokenError, tokens.TokenSecretMissing, ValueError):
        return False
    row = await db.get(MailMessage, mail_id)
    if row is None or row.status not in ("sent", "bounced") or not row.tracked:
        return False
    if row.user_id is not None:
        from app.services.newsletter_personal.signals import personal_off

        if await personal_off(db, row.user_id):
            return False   # человек отказался от подборки после отправки — дальше не учитываем
    at = now or _now()
    since = (at - row.sent_at).total_seconds() if row.sent_at else None
    client, machine = classify_open(user_agent, since)
    db.add(MailEvent(mail_id=row.id, user_id=row.user_id, campaign=row.campaign, kind="open", machine=machine,
                     client=client, occurred_at=at))
    row.opens = (row.opens or 0) + 1
    if machine:
        row.machine_opened_at = row.machine_opened_at or at
    else:
        if row.opened_at is None:
            row.opened_at, row.open_client = at, client
    return True


async def sync_clicks(db: AsyncSession, *, now: datetime | None = None) -> int:
    """Переходы из писем: сессии сайта с метками рассылки → события `click` письма. Сколько добавлено."""
    at = now or _now()
    since = at - timedelta(days=CLICK_SYNC_DAYS)
    mails = (await db.scalars(select(MailMessage).where(
        MailMessage.campaign.is_not(None), MailMessage.status.in_(("sent", "bounced")),
        MailMessage.sent_at >= since, MailMessage.user_id.is_not(None)))).all()
    if not mails:
        return 0
    from app.services.newsletter_personal import ab

    by_key: dict[tuple[str, str], MailMessage] = {(m.campaign, str(m.user_id)): m for m in mails}
    campaigns = sorted({m.campaign for m in mails})
    users = sorted({str(m.user_id) for m in mails})
    terms: dict[tuple[str, str], str] = {}
    for m in mails:
        if m.tracked:
            term = ab.click_token(str(m.user_id), m.campaign)
            if term:
                terms[(m.campaign, term)] = str(m.user_id)
    visitors: dict[str, str | None] = {}
    for uid, vid in (await db.execute(select(IdentityLink.user_id, IdentityLink.visitor_id_hash)
                                      .where(IdentityLink.user_id.in_(users)))).all():
        # Устройство двух аккаунтов никому не приписываем.
        visitors[vid] = None if vid in visitors and visitors[vid] != uid else uid
    sessions = (await db.execute(
        select(BehaviorSession.session_id_hash, BehaviorSession.user_id, BehaviorSession.visitor_id_hash,
               BehaviorSession.utm_campaign, BehaviorSession.utm_content, BehaviorSession.utm_term,
               BehaviorSession.started_at, BehaviorSession.is_webdriver)
        .where(BehaviorSession.utm_medium == "newsletter", BehaviorSession.utm_campaign.in_(campaigns),
               BehaviorSession.started_at >= since))).all()
    if not sessions:
        return 0
    known = {s for s, in (await db.execute(select(MailEvent.session_id_hash).where(
        MailEvent.kind == "click", MailEvent.session_id_hash.in_([s[0] for s in sessions])))).all()}
    added = 0
    for sid, uid, vid, campaign, content, term, started, webdriver in sessions:
        if sid in known:
            continue
        who = uid if (campaign, str(uid)) in by_key else terms.get((campaign, term or "")) or visitors.get(vid)
        row = by_key.get((campaign, str(who))) if who else None
        if row is None or (row.sent_at and started < row.sent_at):
            continue
        if not row.tracked and str(uid) != str(row.user_id):
            continue   # человек без учёта: считаем только переход под его собственным входом
        machine = bool(webdriver)
        db.add(MailEvent(mail_id=row.id, user_id=row.user_id, campaign=campaign, kind="click", machine=machine,
                         client="site", block=(content or None) and content[:40], session_id_hash=sid,
                         occurred_at=started))
        known.add(sid)
        if not machine:
            row.clicks = (row.clicks or 0) + 1
            if row.clicked_at is None or started < row.clicked_at:
                row.clicked_at = started
        added += 1
    return added


async def click_sync_job() -> None:
    """Планировщик: перенос переходов в события писем (чтение сессий, запись только в свои таблицы)."""
    from app.database import async_session

    async with async_session() as db:
        n = await sync_clicks(db)
        await db.commit()
    if n:
        logger.info("mail click sync: %d new", n)


def is_uuid(value: str | None) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError):
        return False

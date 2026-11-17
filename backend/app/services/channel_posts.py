"""Черновики канала: утверждение владельцем в служебном боте и публикация по его кнопке (17.11.2026, ADR-0035).

Правило владельца: в канал ничего не уходит без него. Поэтому путь поста такой:

1. Автор (`channel_author`) сдаёт черновик → строка `channel_posts` со статусом `draft`.
2. Проверяющим (`channel_review_chat_ids`, по умолчанию только владелец) приходят два сообщения: сам пост — ровно
   в том виде, в каком он выйдет в канале (с картинкой, если она есть), — и под ним панель с кнопками.
3. Кнопки: «Опубликовать <когда>», «Сейчас», «Поправить» (владелец пишет пожелание словами — автор переписывает),
   «Другой вариант», «Откуда числа», «Не надо» (с необязательной причиной — автор учится на ней).
   Если сторож нашёл число без основания, кнопок публикации нет вовсе.
4. Одобренный пост уходит в канал в свой срок задачей `channel_publish_job` — и только при `channel_publish_enabled`.
   До срока одобрение можно отменить.

Если проверяющих двое (владелец и партнёр), решает первое нажатие; панель у второго обновляется: что решено и кем.
Черновики не технические алерты, в спокойном режиме они не откладываются: это сообщение, которое ждёт человека,
и приходит оно предсказуемо — после утренней сводки и в день выхода данных, с 9 до 21 по Москве.
Повторов отправки в канал нет: при сбое пост получает статус `failed`, владелец видит причину и кнопку «Ещё раз».
"""
from __future__ import annotations

import asyncio
import io
import logging
import re
from datetime import datetime, timedelta, timezone
from html import escape

from sqlalchemy import func, select

from app.config import settings
from app.services.channel_facts import MSK, WEEKDAYS_SHORT, fmt_day, plain_text

logger = logging.getLogger(__name__)

CB_PREFIX = "ch:"
KIND_DRAFT = "channel_draft"
KIND_POST = "channel_post"
CAPTION_LIMIT = 1000
SKIP_REASONS = {"dull": "скучно", "topic": "не та тема", "wrong": "неточно", "later": "не сейчас", "tone": "не тот тон"}
_EDIT_KEY = "fe:channel:edit:"
_EDIT_TTL = 1800
_edit_mem: dict[str, tuple[int, datetime]] = {}
_tasks: set[asyncio.Task] = set()
STATUS_NUM = {"data": "база сайта", "derived": "расчёт из базы", "forecast": "наш расчёт (прогноз сайта)",
              "tool": "база сайта (запрос редактора)", "report": "отчёт раздела «Исследования»", "calc": "расчёт редактора, пересчитан", "assumption": "условное допущение",
              "web": "страница в интернете", "small": "не сверялось", "unmatched": "НЕ СОШЛОСЬ",
              "date": "дата", "date_unknown": "даты нет в данных", "year": "год"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def reviewers() -> list[str]:
    """Кому приходят черновики. Пусто в настройке — только владелец."""
    ids = [c.strip() for c in (settings.channel_review_chat_ids or "").split(",") if c.strip()]
    if not ids and settings.telegram_chat_id:
        ids = [str(settings.telegram_chat_id)]
    seen: set[str] = set()
    return [c for c in ids if not (c in seen or seen.add(c))]


def publish_token() -> str:
    return settings.channel_bot_token or settings.telegram_bot_token


async def notify_reviewers(text: str, kind: str = "channel_note") -> None:
    from app.services.telegram_bot import send_message

    for chat_id in reviewers():
        await send_message(chat_id, text, kind=kind, link_preview=False)


# ---------------------------------------------------------------------------
# Срок выхода
# ---------------------------------------------------------------------------

MAX_POSTS_PER_DAY = 3


def plan_time(when: str, now_msk: datetime, *, busy_days: dict, rubric: str, short: bool = False) -> datetime:
    """Когда пост выйдет, если одобрить его сейчас. Время — по Москве.

    Обычный пост — в `channel_post_hour_msk`; «цифра вышла» — сразу. Ночью (21–9) ничего не выходит.
    `busy_days` — {день: (всего постов, из них средних и больших)}, уже вышедших или запланированных.
    Средний или большой пост — один в сутки («цифра вышла» может стать вторым: ради неё канал и существует).
    Короткая строка может выйти рядом с ним, но всего в день — не больше трёх постов.
    """
    hour = int(settings.channel_post_hour_msk)
    slot = now_msk.replace(hour=hour, minute=0, second=0, microsecond=0)
    if when == "now":
        t = now_msk
    else:
        t = slot if now_msk <= slot else now_msk
    if t.hour >= 21:
        t = (t + timedelta(days=1)).replace(hour=hour, minute=0, second=0, microsecond=0)
    elif t.hour < 9:
        t = t.replace(hour=9, minute=0, second=0, microsecond=0)
    for _ in range(7):
        total, big = busy_days.get(t.date(), (0, 0))
        free = total < MAX_POSTS_PER_DAY and (short or rubric == "release" or big == 0)
        if free:
            break
        t = (t + timedelta(days=1)).replace(hour=hour, minute=0, second=0, microsecond=0)
    return t


def when_label(t: datetime, now_msk: datetime) -> str:
    if abs((t - now_msk).total_seconds()) < 90:
        return "сейчас"
    if t.date() == now_msk.date():
        return f"сегодня в {t:%H:%M}"
    if t.date() == (now_msk + timedelta(days=1)).date():
        return f"завтра в {t:%H:%M}"
    return f"в {WEEKDAYS_SHORT[t.weekday()]}, {fmt_day(t.date(), year=False)}, в {t:%H:%M}"


def post_size(post) -> str:
    from app.services.channel_author import SIZES, size_of

    size = (post.audit or {}).get("size")
    return size if size in SIZES else size_of(plain_text((post.audit or {}).get("body") or post.text))


async def _busy_days(db, exclude_id: int | None = None) -> dict:
    """{день по Москве: (всего постов, из них средних и больших)} — вышедшие и одобренные."""
    from app.models import ChannelPost

    rows = (await db.execute(
        select(ChannelPost)
        .where(ChannelPost.status.in_(("approved", "publishing", "published")),
               func.coalesce(ChannelPost.published_at, ChannelPost.planned_at) >= _utcnow() - timedelta(days=2)))).scalars().all()
    days: dict = {}
    for p in rows:
        at = p.published_at or p.planned_at
        if p.id == exclude_id or not at:
            continue
        day = at.replace(tzinfo=timezone.utc).astimezone(MSK).date()
        total, big = days.get(day, (0, 0))
        days[day] = (total + 1, big + (0 if post_size(p) == "short" else 1))
    return days


# ---------------------------------------------------------------------------
# Сообщения проверяющим
# ---------------------------------------------------------------------------

def keyboard(post, label: str) -> dict:
    pid = post.id
    if post.status == "draft" and post.blocked:
        rows = [[{"text": "✏️ Поправить", "callback_data": f"ch:edit:{pid}"},
                 {"text": "🔁 Переписать", "callback_data": f"ch:alt:{pid}"}],
                [{"text": "🔎 Что не сошлось", "callback_data": f"ch:src:{pid}"}],
                [{"text": "✖️ Не надо", "callback_data": f"ch:no:{pid}"}]]
    elif post.status == "draft":
        rows = [[{"text": f"✅ Опубликовать {label}", "callback_data": f"ch:ok:{pid}"}]]
        second = [{"text": "✏️ Поправить", "callback_data": f"ch:edit:{pid}"}]
        if label != "сейчас":
            second.insert(0, {"text": "⚡ Сейчас", "callback_data": f"ch:now:{pid}"})
        rows.append(second)
        rows.append([{"text": "🔁 Другой вариант", "callback_data": f"ch:alt:{pid}"},
                     {"text": "🔎 Откуда числа", "callback_data": f"ch:src:{pid}"}])
        rows.append([{"text": "✖️ Не надо", "callback_data": f"ch:no:{pid}"}])
    elif post.status == "approved":
        rows = [[{"text": "↩️ Отменить", "callback_data": f"ch:undo:{pid}"},
                 {"text": "🔎 Откуда числа", "callback_data": f"ch:src:{pid}"}]]
    elif post.status == "skipped" and not post.feedback:
        rows = [[{"text": t.capitalize(), "callback_data": f"ch:why:{pid}:{k}"} for k, t in list(SKIP_REASONS.items())[:3]],
                [{"text": t.capitalize(), "callback_data": f"ch:why:{pid}:{k}"} for k, t in list(SKIP_REASONS.items())[3:]]]
    elif post.status == "failed":
        rows = [[{"text": "🔁 Отправить ещё раз", "callback_data": f"ch:retry:{pid}"},
                 {"text": "✖️ Не надо", "callback_data": f"ch:no:{pid}"}]]
    else:
        rows = []
    return {"inline_keyboard": rows}


def panel_text(post, label: str, who: str | None = None) -> str:
    """Панель под черновиком: что это, почему сегодня, что проверено, что решено. Обычными словами."""
    from app.services.channel_author import RUBRIC_TITLES

    audit = post.audit or {}
    nums = [n for n in audit.get("numbers") or [] if n.get("status") not in ("date", "date_unknown", "year", "small")]
    bad = [n for n in nums if n.get("status") == "unmatched"]
    lines = [f"✍️ <b>Черновик для канала</b> · {escape(RUBRIC_TITLES.get(post.rubric, post.rubric))}"]
    if post.why:
        lines.append(f"<i>{escape(post.why)}</i>")
    if audit.get("issues"):
        lines.append("⚠️ <b>Публиковать нельзя, пока не поправлено:</b> " + escape("; ".join(audit["issues"][:4])) + ".")
    elif nums:
        lines.append(f"Числа сверены с базой: {len(nums) - len(bad)} из {len(nums)}.")
    if audit.get("warnings"):
        lines.append("Обратите внимание: " + escape("; ".join(audit["warnings"][:3])) + ".")
    checks = audit.get("checks") or []
    if checks:
        lines.append("Редактор перепроверил: " + escape("; ".join(
            f"{c.get('what', '')} — {c.get('result', '')}"[:180] for c in checks[:3])) + ".")
    if audit.get("concerns"):
        lines.append("Сомнения редактора: " + escape(audit["concerns"][:500]))
    from app.services.channel_author import SIZE_TITLES

    bits = [SIZE_TITLES[post_size(post)]]
    if post.chart_topic:
        bits.append("с графиком")
    bits.append("без звука" if post.silent else "со звуком")
    lines.append("Вид: " + ", ".join(bits) + ".")
    state = {
        "approved": f"✅ <b>Одобрено</b>{' — ' + escape(who) if who else ''}. Выйдет {label}."
                    + ("" if settings.channel_publish_enabled else " Публикация в канал пока выключена — пост сохранён."),
        "publishing": "⏳ Отправляется в канал.",
        "published": "📣 <b>Опубликовано</b>" + (f": {escape(post_link(post))}" if post_link(post) else "") + ".",
        "skipped": "✖️ <b>Не публикуем.</b>" + (f" Причина: {escape(post.feedback)}." if post.feedback
                                               else " Если не трудно, отметьте почему — редактор учтёт."),
        "replaced": "✏️ Заменён новой версией ниже.",
        "failed": "⚠️ <b>Не ушло в канал.</b> " + escape(post.error or "") ,
    }.get(post.status)
    if state:
        lines.append(state)
    return "\n".join(lines)


def post_link(post) -> str | None:
    from app.services.channel_stats import channel_username

    name = channel_username()
    return f"t.me/{name}/{post.telegram_message_id}" if name and post.telegram_message_id else None


_last_once_error: str | None = None


async def _tg_once(method: str, payload: dict, files: dict | None = None, token: str | None = None) -> dict | None:
    """Один вызов Bot API без повторов — для отправки в канал.

    Общий `telegram_bot._api` повторяет sendMessage при таймауте чтения; если Telegram уже принял сообщение,
    повтор дал бы второй такой же пост в канале. Для канала действует «не больше одного раза»: при сбое пост
    получает статус `failed`, и ещё раз его отправляет только человек кнопкой.
    """
    import httpx

    global _last_once_error
    _last_once_error = None
    token = token or settings.telegram_bot_token
    if not token:
        _last_once_error = "нет токена бота"
        return None
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        async with httpx.AsyncClient(timeout=40, proxy=settings.telegram_proxy_url or None, trust_env=False) as client:
            resp = await (client.post(url, data=payload, files=files) if files else client.post(url, json=payload))
        data = resp.json()
        if not data.get("ok"):
            _last_once_error = str(data)[:250]
            logger.warning("channel: Telegram %s отказал: %s", method, _last_once_error)
            return None
        return data
    except Exception as exc:  # noqa: BLE001
        _last_once_error = f"{type(exc).__name__}: {exc}"[:250]
        logger.warning("channel: Telegram %s не ответил", method, exc_info=True)
        return None


async def _send_post(chat_id: str, post, *, token: str | None, kind: str, silent: bool, once: bool = False) -> int | None:
    """Отправить пост как он есть: картинка с подписью или текст. Возвращает номер сообщения.
    `once` — отправка в канал: без повторов (см. `_tg_once`)."""
    from app.services import public_bot, telegram_bot
    from app.services.telegram_outbox import archive_begin, archive_finish

    async def call(method: str, payload: dict, files: dict | None = None) -> dict | None:
        if once:
            return await _tg_once(method, payload, files, token)
        return await telegram_bot._api(method, payload, **({"files": files} if files else {}),
                                       **({"token": token} if token else {}))

    png = None
    if post.chart_topic and len(plain_text(post.text)) <= CAPTION_LIMIT:
        try:
            png = await public_bot.render_topic_chart(post.chart_topic)
        except Exception:  # noqa: BLE001 — без картинки пост всё равно уйдёт текстом
            logger.warning("channel: картинка %s не построена", post.chart_topic, exc_info=True)
    if png:
        payload = {"chat_id": str(chat_id), "caption": post.text, "parse_mode": "HTML",
                   "disable_notification": "true" if silent else "false"}
        row = await archive_begin(chat_id=str(chat_id), method="sendPhoto", kind=kind, text=post.text, payload=payload,
                                  file_name=f"{post.chart_topic}.png")
        data = await call("sendPhoto", payload, {"photo": ("chart.png", io.BytesIO(png))})
    else:
        payload = {"chat_id": str(chat_id), "text": post.text, "parse_mode": "HTML",
                   "disable_notification": silent, "link_preview_options": {"is_disabled": True}}
        row = await archive_begin(chat_id=str(chat_id), method="sendMessage", kind=kind, text=post.text, payload=payload)
        data = await call("sendMessage", payload)
    mid = (data or {}).get("result", {}).get("message_id")
    error = None if data is not None else ((_last_once_error if once else telegram_bot._last_api_error.get()) or "не отправлено")
    await archive_finish(row, ok=data is not None, telegram_message_id=mid, error=error)
    return mid


async def _now_label(db, post) -> tuple[datetime, str]:
    now = datetime.now(MSK)
    when = (post.audit or {}).get("when") or "slot"
    t = plan_time(when, now, busy_days=await _busy_days(db, exclude_id=post.id), rubric=post.rubric,
                  short=post_size(post) == "short")
    return t, when_label(t, now)


async def send_for_review(post_id: int) -> bool:
    """Разослать черновик проверяющим: пост как он выйдет + панель с кнопками."""
    from app.database import async_session
    from app.models import ChannelPost
    from app.services import telegram_bot

    async with async_session() as db:
        post = await db.get(ChannelPost, post_id)
        if post is None:
            return False
        _t, label = await _now_label(db, post)
        sent = []
        for chat_id in reviewers():
            preview_id = await _send_post(chat_id, post, token=None, kind=KIND_DRAFT, silent=True)
            payload = {"chat_id": chat_id, "text": panel_text(post, label), "parse_mode": "HTML",
                       "reply_markup": keyboard(post, label), "link_preview_options": {"is_disabled": True}}
            if preview_id:
                payload["reply_parameters"] = {"message_id": preview_id, "allow_sending_without_reply": True}
            data = await telegram_bot._api("sendMessage", payload)
            panel_id = (data or {}).get("result", {}).get("message_id")
            if preview_id or panel_id:
                sent.append({"chat_id": chat_id, "preview_id": preview_id, "panel_id": panel_id})
        post.review_messages = sent
        await db.commit()
        return bool(sent)


async def refresh_panels(post_id: int, who: str | None = None) -> None:
    """Обновить панели у всех проверяющих: статус и кнопки одинаковы у обоих."""
    from app.database import async_session
    from app.models import ChannelPost
    from app.services import telegram_bot

    async with async_session() as db:
        post = await db.get(ChannelPost, post_id)
        if post is None:
            return
        if post.status == "approved" and post.planned_at:
            t = post.planned_at.replace(tzinfo=timezone.utc).astimezone(MSK)
            label = when_label(t, datetime.now(MSK))
        else:
            _t, label = await _now_label(db, post)
        for m in post.review_messages or []:
            if not m.get("panel_id"):
                continue
            await telegram_bot._api("editMessageText", {
                "chat_id": m["chat_id"], "message_id": m["panel_id"], "text": panel_text(post, label, who),
                "parse_mode": "HTML", "reply_markup": keyboard(post, label),
                "link_preview_options": {"is_disabled": True}})


async def create_and_send(draft, *, run_id: int | None = None, parent_id: int | None = None) -> int | None:
    """Записать черновик автора и отправить его на утверждение."""
    from app.database import async_session
    from app.models import ChannelPost

    audit = dict(draft.audit or {})
    audit["when"] = draft.when
    audit["body"] = draft.body
    async with async_session() as db:
        post = ChannelPost(
            rubric=draft.rubric, status="draft", text=draft.text, chart_topic=draft.chart_topic, link_url=draft.link_url,
            silent=draft.silent, why=draft.why or None, parent_id=parent_id, run_id=run_id, blocked=draft.blocked,
            audit=audit)
        db.add(post)
        await db.commit()
        pid = post.id
    if reviewers() and settings.telegram_bot_token:
        await send_for_review(pid)
    return pid


# ---------------------------------------------------------------------------
# Кнопки и ответы владельца
# ---------------------------------------------------------------------------

def _who(cq_or_msg: dict) -> str:
    u = cq_or_msg.get("from") or {}
    return (u.get("first_name") or "").strip()[:40]


def sources_text(post) -> str:
    """«Откуда числа»: каждое число поста и его основание, что автор перепроверил и где."""
    audit = post.audit or {}
    lines = ["🔎 <b>Откуда числа в этом посте</b>"]
    for n in audit.get("numbers") or []:
        if n.get("status") in ("year",):
            continue
        mark = "⚠️" if n.get("status") in ("unmatched", "date_unknown") else "•"
        lines.append(f"{mark} <b>{escape(str(n.get('shown')))}</b> — {escape(STATUS_NUM.get(n.get('status'), ''))}: "
                     f"{escape(str(n.get('basis') or ''))}")
    for c in audit.get("checks") or []:
        lines.append(f"✓ Перепроверено: {escape(str(c.get('what')))} — {escape(str(c.get('result')))} "
                     f"({escape(str(c.get('where')))})")
    web = audit.get("web") or []
    if web:
        lines.append("Страницы, которые редактор нашёл в интернете: "
                     + "; ".join(escape(re.sub(r'^https?://(www\.)?', '', w.get("url", ""))[:70]) for w in web[:6]))
    if audit.get("concerns"):
        lines.append("Сомнения редактора: " + escape(audit["concerns"]))
    return "\n".join(lines)


async def _answer(cq: dict, text: str = "") -> None:
    from app.services import telegram_bot

    await telegram_bot._api("answerCallbackQuery", {"callback_query_id": cq["id"], "text": text[:180]})


async def handle_callback(cq: dict) -> None:
    """Нажатие кнопки под черновиком. Только чаты проверяющих."""
    from app.database import async_session
    from app.models import ChannelPost
    from app.services.telegram_bot import send_message

    chat_id = str(cq.get("message", {}).get("chat", {}).get("id", ""))
    if chat_id not in reviewers():
        await _answer(cq)
        return
    parts = (cq.get("data") or "").split(":")
    action = parts[1] if len(parts) > 1 else ""
    try:
        pid = int(parts[2])
    except (IndexError, ValueError):
        await _answer(cq)
        return
    who = _who(cq)
    toast = ""
    follow: tuple | None = None
    async with async_session() as db:
        post = await db.get(ChannelPost, pid)
        if post is None:
            await _answer(cq, "Черновик не найден")
            return
        if action in ("ok", "now"):
            if post.status != "draft":
                toast = "Уже решено"
            elif post.blocked:
                toast = "Сначала поправьте: число не сошлось"
            else:
                now = datetime.now(MSK)
                when = "now" if action == "now" else ((post.audit or {}).get("when") or "slot")
                t = plan_time(when, now, busy_days=await _busy_days(db, exclude_id=post.id), rubric=post.rubric,
                              short=post_size(post) == "short")
                post.status, post.planned_at = "approved", t.astimezone(timezone.utc).replace(tzinfo=None)
                post.decided_at, post.decided_by = _utcnow(), chat_id
                toast = "Одобрено: выйдет " + when_label(t, now)
        elif action == "undo":
            if post.status == "approved":
                post.status, post.planned_at, post.decided_at = "draft", None, None
                toast = "Отменено — пост снова ждёт решения"
            else:
                toast = "Уже опубликовано" if post.status in ("publishing", "published") else "Нечего отменять"
        elif action == "no":
            if post.status in ("draft", "approved", "failed"):
                post.status, post.planned_at = "skipped", None
                post.decided_at, post.decided_by = _utcnow(), chat_id
                toast = "Не публикуем"
        elif action == "why":
            reason = SKIP_REASONS.get(parts[3] if len(parts) > 3 else "")
            if reason and post.status == "skipped":
                post.feedback = reason
                toast = "Спасибо, редактор учтёт"
        elif action == "retry":
            if post.status == "failed":
                post.status, post.planned_at, post.error = "approved", _utcnow(), None
                toast = "Отправляю ещё раз"
        elif action == "src":
            follow = ("src", sources_text(post))
        elif action == "edit":
            if post.status in ("draft", "approved"):
                await _set_pending_edit(chat_id, pid)
                follow = ("edit", "✏️ Напишите одним сообщением, что поправить: «короче», «без вкладов», «заголовок спокойнее». "
                                  "Редактор перепишет и пришлёт новую версию.\n"
                                  "Чтобы поставить свой текст целиком, начните сообщение со слова <b>Текст:</b>")
            else:
                toast = "Этот пост уже нельзя править"
        elif action == "alt":
            if post.status == "draft":
                follow = ("alt", "🔁 Пишу другой вариант — придёт через минуту.")
            else:
                toast = "Этот пост уже решён"
        await db.commit()
    await _answer(cq, toast)
    if action in ("ok", "now", "undo", "no", "why", "retry"):
        await refresh_panels(pid, who if action in ("ok", "now") else None)
    if follow:
        await send_message(chat_id, follow[1], kind="bot_reply", link_preview=False)
        if follow[0] == "alt":
            _spawn(_revise(pid, "Напиши другой вариант этого поста: другой заход или другая подмеченная деталь. "
                                "Факты и рубрика те же.", chat_id))


def _spawn(coro) -> None:
    task = asyncio.get_running_loop().create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def _set_pending_edit(chat_id: str, pid: int) -> None:
    _edit_mem[chat_id] = (pid, _utcnow())
    try:
        from app.core.cache import get_state_redis

        await (await get_state_redis()).set(_EDIT_KEY + chat_id, str(pid), ex=_EDIT_TTL)
    except Exception:  # noqa: BLE001 — память процесса остаётся
        logger.info("channel: ожидание правки не записано в Redis", exc_info=True)


async def _pop_pending_edit(chat_id: str) -> int | None:
    pid = None
    try:
        from app.core.cache import get_state_redis

        r = await get_state_redis()
        raw = await r.get(_EDIT_KEY + chat_id)
        if raw:
            pid = int(raw)
            await r.delete(_EDIT_KEY + chat_id)
    except Exception:  # noqa: BLE001
        pass
    mem = _edit_mem.pop(chat_id, None)
    if pid is None and mem and (_utcnow() - mem[1]).total_seconds() < _EDIT_TTL:
        pid = mem[0]
    return pid


async def _post_by_message(db, chat_id: str, message_id: int):
    from app.models import ChannelPost

    rows = (await db.execute(
        select(ChannelPost).where(ChannelPost.created_at >= _utcnow() - timedelta(days=14))
        .order_by(ChannelPost.id.desc()).limit(60))).scalars().all()
    for p in rows:
        for m in p.review_messages or []:
            if str(m.get("chat_id")) == chat_id and message_id in (m.get("preview_id"), m.get("panel_id")):
                return p
    return None


async def handle_message(msg: dict) -> bool:
    """Сообщение проверяющего: ответ на черновик или текст после кнопки «Поправить». True — сообщение разобрано здесь."""
    from app.database import async_session
    from app.models import ChannelPost
    from app.services.telegram_bot import send_message

    chat_id = str(msg.get("chat", {}).get("id", ""))
    raw = (msg.get("text") or "").strip()
    if chat_id not in reviewers() or not raw or raw.startswith("/"):
        return False
    reply_to = (msg.get("reply_to_message") or {}).get("message_id")
    async with async_session() as db:
        post = await _post_by_message(db, chat_id, int(reply_to)) if reply_to else None
        if post is None:
            pid = await _pop_pending_edit(chat_id)
            post = await db.get(ChannelPost, pid) if pid else None
        else:
            await _pop_pending_edit(chat_id)
        if post is None:
            return False
        if post.status == "skipped":
            post.feedback = raw[:600]
            await db.commit()
            await send_message(chat_id, "Записал, почему не подошло: редактор учтёт в следующих постах.", kind="bot_reply")
            await refresh_panels(post.id)
            return True
        if post.status not in ("draft", "approved"):
            await send_message(chat_id, "Этот пост уже опубликован или заменён — правка не применена.", kind="bot_reply")
            return True
        pid = post.id
    manual = re.match(r"^\s*текст\s*:\s*", raw, re.I)
    if manual:
        await send_message(chat_id, "Ставлю ваш текст и сверяю числа с базой.", kind="bot_reply")
        _spawn(_manual_text(pid, raw[manual.end():], chat_id))
    else:
        await send_message(chat_id, "✏️ Переписываю — новая версия придёт через минуту.", kind="bot_reply")
        _spawn(_revise(pid, raw, chat_id))
    return True


async def _replace(pid: int, draft, note: str, run_id: int | None) -> int | None:
    from app.database import async_session
    from app.models import ChannelPost

    async with async_session() as db:
        old = await db.get(ChannelPost, pid)
        if old is None:
            return None
        old.status, old.feedback, old.planned_at = "replaced", note[:600], None
        await db.commit()
    await refresh_panels(pid)
    return await create_and_send(draft, run_id=run_id, parent_id=pid)


async def _revise(pid: int, note: str, chat_id: str) -> None:
    """Правка словами: автор переписывает пост по пожеланию владельца."""
    from app.database import async_session
    from app.models import ChannelPost
    from app.services import channel_author
    from app.services.telegram_bot import send_message

    try:
        async with async_session() as db:
            post = await db.get(ChannelPost, pid)
            if post is None:
                return
            body = (post.audit or {}).get("body") or re.sub(r"\n\n(<i>Источник:.*|<a href=.*)$", "", post.text, flags=re.S)
            revise = {"rubric": post.rubric, "body": body, "note": note}
        result = await channel_author.run_author("revise", revise=revise, trigger=f"правка поста {pid}")
        if result.drafts:
            await _replace(pid, result.drafts[0], note, result.run_id)
        else:
            await send_message(chat_id, "Переписать не получилось — прежний черновик остался как был. Попробуйте ещё раз позже.",
                               kind="bot_reply")
    except Exception:  # noqa: BLE001
        logger.warning("channel: правка поста %s не удалась", pid, exc_info=True)


async def _manual_text(pid: int, text: str, chat_id: str) -> None:
    """Свой текст владельца: модель не участвует, сторож сверяет числа с сегодняшними данными."""
    from app.database import async_session
    from app.models import ChannelPost
    from app.services import channel_author
    from app.services.channel_facts import build_briefing, check_post

    try:
        async with async_session() as db:
            post = await db.get(ChannelPost, pid)
            if post is None:
                return
            briefing = await build_briefing(db)
            body = channel_author.clean_body(text)
            audit = check_post(body, briefing.corpus, (post.audit or {}).get("declared") or [], banned=briefing.banned,
                               reports=post.rubric == "research")
            info = audit.as_dict()
            info["concerns"] = "Текст написан владельцем; числа сверены со сводкой данных на сегодня."
            info["size"] = channel_author.size_of(plain_text(body))
            draft = channel_author.Draft(
                rubric=post.rubric, size=info["size"], body=body,
                text=channel_author.compose_post(body, audit.sources or (post.audit or {}).get("sources") or [],
                                                 post.link_url, None),
                chart_topic=post.chart_topic, link_url=post.link_url, when=(post.audit or {}).get("when") or "slot",
                silent=post.silent, why="Текст владельца.", audit=info, blocked=audit.blocked)
        await _replace(pid, draft, "свой текст владельца", None)
    except Exception:  # noqa: BLE001
        logger.warning("channel: свой текст для поста %s не поставлен", pid, exc_info=True)


# ---------------------------------------------------------------------------
# Публикация
# ---------------------------------------------------------------------------

def _plain_error(raw: str | None) -> str:
    """Причина отказа Telegram обычными словами."""
    s = (raw or "").lower()
    if "not enough rights" in s or "need administrator" in s or "chat_write_forbidden" in s or "forbidden" in s:
        return "У бота нет права публиковать в канале: его нужно добавить администратором с правом «Публикация сообщений»."
    if "chat not found" in s:
        return "Канал не найден: проверьте его имя в настройках."
    if "parse entities" in s:
        return "Telegram не принял оформление текста. Нажмите «Поправить» и попросите переписать."
    return "Telegram не принял сообщение. Попробуйте ещё раз позже."


async def channel_publish_job() -> dict:
    """Раз в минуту: одобренный пост, срок которого настал, уходит в канал. Один пост за запуск."""
    from app.database import async_session
    from app.models import ChannelPost

    if not settings.channel_publish_enabled:
        return {"skipped": "disabled"}
    if not (publish_token() and settings.channel_chat_id):
        return {"skipped": "not_configured"}
    async with async_session() as db:
        post = (await db.execute(
            select(ChannelPost).where(ChannelPost.status == "approved", ChannelPost.planned_at <= _utcnow())
            .order_by(ChannelPost.planned_at).limit(1))).scalar_one_or_none()
        if post is None:
            return {"skipped": "nothing_due"}
        if post.blocked:
            post.status, post.error = "failed", "Число в тексте не сошлось с базой."
            await db.commit()
            return {"failed": post.id}
        # Отметка до отправки: если процесс упадёт посередине, пост не уйдёт второй раз сам.
        post.status = "publishing"
        await db.commit()
        pid = post.id
        mid = await _send_post(settings.channel_chat_id, post, token=settings.channel_bot_token or None,
                               kind=KIND_POST, silent=post.silent, once=True)
        if mid:
            post.status, post.telegram_message_id, post.published_at = "published", int(mid), _utcnow()
        else:
            post.status, post.error = "failed", _plain_error(_last_once_error)
        await db.commit()
        ok = bool(mid)
    await refresh_panels(pid)
    return {"published" if ok else "failed": pid}


async def pending_count(db) -> int:
    from app.models import ChannelPost

    return int((await db.execute(
        select(func.count(ChannelPost.id)).where(ChannelPost.status == "draft",
                                                 ChannelPost.created_at >= _utcnow() - timedelta(days=3)))).scalar() or 0)

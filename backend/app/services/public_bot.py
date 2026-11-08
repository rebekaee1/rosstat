"""Публичный режим Telegram-бота (решение владельца 08.11.2026: «делаем бота»).

Зачем: дверь из роликов Instagram, где ссылка не нажимается. Ролик просит написать боту
слово («ДИЗЕЛЬ») или ведёт по ссылке `t.me/<бот>?start=<код>` из сторис и шапки профиля.
Бот отвечает свежей цифрой с сайта и предлагает присылать новые данные. Так видно,
какой ролик кого привёл (код или слово), что человек спросил и вернулся ли он.

Границы:
- тот же бот и тот же поллер, что у админ-меню (`telegram_bot.telegram_poll_job`);
  публичный режим включает `settings.public_bot_enabled`, выключенный флаг = прежнее поведение;
- только личные чаты; группы и каналы игнорируются;
- номер чата хранится только в `public_bot_chats` (нужен для ответа и подписки), события —
  с HMAC номера (`chat_hash`); `/stop` удаляет чат, подписки и архив публичных ответов;
- бот не видит, прочитано ли сообщение (в Bot API нет отметок прочтения): «вернулся» —
  это новое сообщение/нажатие человека или переход на сайт по ссылке с метками;
- прогноз показывается одной точкой, без диапазона (правило владельца).
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from html import escape
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select

from app.config import settings
from app.database import async_session
from app.services.locale import ru_public_origin
from app.models import (
    EconomicEvent, Forecast, ForecastValue, Indicator, IndicatorData,
    PublicBotChat, PublicBotEvent, PublicBotSubscription, TelegramOutbox,
)

logger = logging.getLogger(__name__)

KIND_REPLY = "public_bot"
KIND_NOTIFY = "public_bot_notify"
CB_PREFIX = "pb:"
_MSK = ZoneInfo("Europe/Moscow")
_CODE_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_MAX_TEXT = 200


@dataclass(frozen=True)
class Topic:
    key: str
    indicator: str          # code в indicators
    title: str
    unit: str
    stems: tuple[str, ...]  # начала слов, по которым узнаём тему
    tokens: tuple[str, ...] = ()  # точные слова (92, 95)
    is_rate: bool = False   # проценты: изменение в п.п., а не в %
    notify: str = "new_point"  # new_point | weekly | on_change


TOPICS: dict[str, Topic] = {t.key: t for t in (
    Topic("diesel", "fuel-diesel", "Дизель", "₽ за литр", ("дизел", "солярк"), ("дт",)),
    Topic("ai92", "fuel-ai92", "Бензин АИ-92", "₽ за литр", ("бензин",), ("92", "аи92", "аи-92")),
    Topic("ai95", "fuel-ai95", "Бензин АИ-95", "₽ за литр", (), ("95", "аи95", "аи-95")),
    Topic("gold", "gold-price", "Золото", "₽ за грамм", ("золот",), notify="weekly"),
    Topic("inflation", "cpi-yoy", "Инфляция", "% за год", ("инфляц", "ипц"), ("цены",), is_rate=True),
    Topic("keyrate", "key-rate", "Ключевая ставка", "%", ("ключев", "ставк"), is_rate=True, notify="on_change"),
    Topic("deposit", "deposit-rate", "Ставки по вкладам", "%", ("вклад", "депозит"), is_rate=True),
    Topic("mortgage", "mortgage-rate", "Ставка по ипотеке", "%", ("ипотек",), is_rate=True),
    Topic("usd", "usd-rub", "Доллар", "₽", ("доллар", "бакс"), ("usd",), notify="weekly"),
    Topic("eur", "eur-rub", "Евро", "₽", ("евро",), ("eur",), notify="weekly"),
)}
_MATCH_ORDER = ("diesel", "ai95", "ai92", "gold", "deposit", "mortgage", "keyrate", "usd", "eur", "inflation")
# Порядок кнопок меню.
MENU = (("diesel", "ai92"), ("inflation", "keyrate"), ("gold", "usd"), ("deposit", "mortgage"))

SOURCES = (("instagram", "Instagram"), ("telegram", "Telegram"), ("search", "Поиск"),
           ("friends", "Знакомые"), ("other", "Другое"))
_MONTHS = ("января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа",
           "сентября", "октября", "ноября", "декабря")
_MONTHS_NOM = ("январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август",
               "сентябрь", "октябрь", "ноябрь", "декабрь")
_FREQ_STEP = {"weekly": "За неделю", "monthly": "За месяц", "quarterly": "За квартал"}


# ---------------------------------------------------------------------------
# Разбор входа
# ---------------------------------------------------------------------------

def chat_hash(chat_id: str) -> str:
    key = (settings.telegram_bot_token or "fe-public-bot").encode("utf-8")
    return hmac.new(key, f"public-bot|{chat_id}".encode("utf-8"), hashlib.sha256).hexdigest()


def parse_start(text: str) -> tuple[str | None, str | None]:
    """`/start r014_diesel` → (код, тема). Код — как есть (до 64 знаков [A-Za-z0-9_-]),
    тема — если последняя часть кода после «_»/«-» или весь код совпадает с ключом темы."""
    parts = text.strip().split(maxsplit=1)
    if len(parts) < 2:
        return None, None
    code = parts[1].strip()
    if not _CODE_RE.match(code):
        return None, None
    tail = re.split(r"[_-]", code)[-1].lower()
    topic = code.lower() if code.lower() in TOPICS else (tail if tail in TOPICS else None)
    return code, topic


def _norm(text: str) -> str:
    return text.lower().replace("ё", "е")


def match_topic(text: str) -> tuple[str | None, str | None]:
    """Слово из ролика → (тема, нормализованное слово-код). Пусто, если тему не узнали."""
    t = _norm(text)[:_MAX_TEXT]
    words = re.findall(r"[a-zа-я0-9-]+", t)
    # Сначала частные темы: «ставки по вкладам» — вклады, «ставка по ипотеке» — ипотека,
    # «цены на бензин» — бензин; общее «ставка»/«цены» — последними.
    for key in _MATCH_ORDER:
        topic = TOPICS[key]
        for w in words:
            if w in topic.tokens or any(w.startswith(s) for s in topic.stems):
                return topic.key, w[:64]
    return None, None


# ---------------------------------------------------------------------------
# Цифры
# ---------------------------------------------------------------------------

def fmt_num(v: float, digits: int = 2) -> str:
    s = f"{v:,.{digits}f}".replace(",", " ").replace(".", ",")
    return s.replace("-", "−")


def fmt_date(d: date, freq: str) -> str:
    if freq in ("monthly",):
        return f"{_MONTHS_NOM[d.month - 1]} {d.year}"
    if freq in ("annual",):
        return f"{d.year} год"
    return f"{d.day} {_MONTHS[d.month - 1]} {d.year}"


@dataclass
class Figure:
    topic: Topic
    name: str
    source: str
    frequency: str
    last_date: date
    last_value: float
    prev_value: float | None
    year_ago_value: float | None
    forecast_date: date | None
    forecast_value: float | None
    next_release: date | None = None
    next_release_estimated: bool = False


async def load_figure(db, topic: Topic) -> Figure | None:
    ind = (await db.execute(select(Indicator).where(Indicator.code == topic.indicator))).scalar_one_or_none()
    if ind is None:
        return None
    rows = (await db.execute(
        select(IndicatorData.date, IndicatorData.value)
        .where(IndicatorData.indicator_id == ind.id)
        .order_by(IndicatorData.date.desc()).limit(2)
    )).all()
    if not rows:
        return None
    last_d, last_v = rows[0][0], float(rows[0][1])
    prev_v = float(rows[1][1]) if len(rows) > 1 else None
    target = last_d - timedelta(days=365)
    ya = (await db.execute(
        select(IndicatorData.date, IndicatorData.value)
        .where(IndicatorData.indicator_id == ind.id, IndicatorData.date <= target + timedelta(days=7))
        .order_by(IndicatorData.date.desc()).limit(1)
    )).first()
    # Точка «год назад» — ближайшая к дате минус 365 дней (у недельных рядов день недели сдвигается).
    year_ago = float(ya[1]) if ya is not None and abs((target - ya[0]).days) <= 40 else None
    fc = (await db.execute(
        select(ForecastValue.date, ForecastValue.value)
        .join(Forecast, Forecast.id == ForecastValue.forecast_id)
        .where(Forecast.indicator_id == ind.id, Forecast.is_current.is_(True), ForecastValue.date > last_d)
        .order_by(ForecastValue.date).limit(1)
    )).first()
    nxt = None
    rel_code = _RELEASE_CODE.get(topic.key)
    if rel_code:
        nxt = (await db.execute(
            select(EconomicEvent.scheduled_date, EconomicEvent.is_estimated)
            .join(Indicator, Indicator.id == EconomicEvent.indicator_id)
            .where(Indicator.code == rel_code, EconomicEvent.scheduled_date >= _now().date())
            .order_by(EconomicEvent.scheduled_date).limit(1)
        )).first()
    return Figure(
        topic=topic, name=ind.name, source=ind.source or "", frequency=ind.frequency or "",
        last_date=last_d, last_value=last_v, prev_value=prev_v, year_ago_value=year_ago,
        forecast_date=fc[0] if fc else None, forecast_value=float(fc[1]) if fc else None,
        next_release=nxt[0] if nxt else None, next_release_estimated=bool(nxt[1]) if nxt else False,
    )


def _change(now: float, before: float | None, is_rate: bool) -> str | None:
    if before is None:
        return None
    if is_rate:
        diff = now - before
        sign = "+" if diff > 0 else ""
        return f"{sign}{fmt_num(diff)} пункта"
    if before == 0:
        return None
    pct = (now / before - 1) * 100
    sign = "+" if pct > 0 else ""
    return f"{sign}{fmt_num(pct, 1)} %"


def site_url(topic: Topic, code: str | None) -> str:
    q = {"utm_source": "telegram", "utm_medium": "bot", "utm_campaign": topic.key}
    if code:
        q["utm_content"] = code
    # Русский хост: apex — английская версия сайта (проверено 08.11.2026 на живом боте).
    return f"{ru_public_origin()}/russia/indicator/{topic.indicator}?{urlencode(q)}"


# Сколько дней после даты точки ряд ещё считается свежим (выход данных с задержкой).
# Календарь сайта (economic_events) привязан к базовым рядам: для темы — код ряда с датами выхода.
_RELEASE_CODE = {"inflation": "cpi", "deposit": "deposit-rate", "mortgage": "mortgage-rate"}
# Средние по России: человек спрашивает «в Москве» — честно называем охват.
_RUSSIA_AVG = ("diesel", "ai92", "ai95", "deposit", "mortgage")
_FRESH_DAYS = {"daily": 6, "weekly": 12, "monthly": 75, "quarterly": 200}
_FUEL = ("diesel", "ai92", "ai95")
_TANK_L = 50


def _wallet_line(f: Figure, cpi: "Figure | None") -> str | None:
    """Одна строка «что это для кошелька» — простая арифметика из тех же рядов (итоги агентов 08.11.2026)."""
    t = f.topic
    if t.key in _FUEL:
        tank = f"Полный бак {_TANK_L} л: ≈{fmt_num(f.last_value * _TANK_L, 0)} ₽"
        if f.year_ago_value:
            tank += f", год назад ≈{fmt_num(f.year_ago_value * _TANK_L, 0)} ₽"
        return tank + "."
    if t.key == "inflation":
        return f"Что стоило 100 ₽ год назад, сейчас стоит ≈{fmt_num(100 + f.last_value)} ₽."
    if cpi is None:
        return None
    if t.key == "keyrate":
        gap = f.last_value - cpi.last_value
        side = "выше" if gap > 0 else "ниже"
        return f"Это на {fmt_num(abs(gap))} пункта {side} инфляции ({fmt_num(cpi.last_value)} %)."
    if t.key == "deposit":
        gap = f.last_value - cpi.last_value
        side = "выше" if gap > 0 else "ниже"
        return f"Это {side} инфляции ({fmt_num(cpi.last_value)} %) на {fmt_num(abs(gap))} пункта; налог на проценты не учтён."
    if t.key in ("gold", "usd", "eur") and f.year_ago_value:
        pct = (f.last_value / f.year_ago_value - 1) * 100
        side = "быстрее" if pct > cpi.last_value else "медленнее"
        return f"За год подорожало {side}, чем росли цены (инфляция {fmt_num(cpi.last_value)} %)."
    return None


def figure_text(f: Figure, header: str | None = None, cpi: "Figure | None" = None,
                today: date | None = None) -> str:
    t = f.topic
    unit = t.unit if t.unit != "%" else "%"
    lines = []
    if header:
        lines.append(header)
    scope = " — в среднем по России" if t.key in _RUSSIA_AVG else ""
    lines.append(f"<b>{escape(t.title)}</b>{scope}")
    lines.append(f"<b>{fmt_num(f.last_value)} {escape(unit)}</b> — {fmt_date(f.last_date, f.frequency)}")
    changes = []
    step = _FREQ_STEP.get(f.frequency)
    ch = _change(f.last_value, f.prev_value, t.is_rate)
    if step and ch:
        changes.append(f"{step}: {ch}")
    ch_y = _change(f.last_value, f.year_ago_value, t.is_rate)
    if ch_y:
        changes.append(f"За год: {ch_y}")
    if changes:
        lines.append(". ".join(changes) + ".")
    wallet = _wallet_line(f, cpi)
    if wallet:
        lines.append(wallet)
    if f.forecast_value is not None and f.forecast_date is not None:
        lines.append(f"Наш расчёт на {fmt_date(f.forecast_date, f.frequency)}: {fmt_num(f.forecast_value)} {escape(unit)} "
                     "(прогноз Forecast Economy)")
    today = today or _now().date()
    if (today - f.last_date).days > _FRESH_DAYS.get(f.frequency, 400):
        lines.append("Новее данных пока нет: это последние опубликованные.")
    if f.next_release and f.next_release >= today:
        when = f"{f.next_release.day} {_MONTHS[f.next_release.month - 1]}"
        lines.append(f"Следующие данные: {'ориентировочно ' if f.next_release_estimated else ''}{when}.")
    if f.source:
        lines.append(f"<i>Источник: {escape(f.source)}</i>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Клавиатуры и тексты
# ---------------------------------------------------------------------------

def menu_keyboard() -> dict:
    return {"inline_keyboard": [
        [{"text": TOPICS[k].title, "callback_data": f"{CB_PREFIX}t:{k}"} for k in row] for row in MENU
    ]}


def figure_keyboard(topic: Topic, code: str | None, subscribed: bool) -> dict:
    sub = ({"text": "🔕 Не присылать", "callback_data": f"{CB_PREFIX}u:{topic.key}"} if subscribed
           else {"text": "🔔 Присылать новые данные", "callback_data": f"{CB_PREFIX}s:{topic.key}"})
    return {"inline_keyboard": [
        [sub],
        [{"text": "📈 График и прогноз на сайте", "url": site_url(topic, code)}],
        [{"text": "Другие цифры", "callback_data": f"{CB_PREFIX}menu"}],
    ]}


def sources_keyboard() -> dict:
    return {"inline_keyboard": [
        [{"text": label, "callback_data": f"{CB_PREFIX}src:{key}"} for key, label in SOURCES[:3]],
        [{"text": label, "callback_data": f"{CB_PREFIX}src:{key}"} for key, label in SOURCES[3:]],
    ]}


def welcome_text() -> str:
    return (
        "Привет! Я бот <b>Forecast Economy</b>.\n"
        "Присылаю свежие цифры экономики России из официальных источников и наш прогноз — "
        "и напоминаю, когда выходят новые данные.\n\n"
        "Напишите слово, например <b>ДИЗЕЛЬ</b>, <b>ИНФЛЯЦИЯ</b> или <b>ЗОЛОТО</b>, или выберите ниже.\n\n"
        "Можно и просто спросить своими словами — отвечу по нашим данным.\n\n"
        + privacy_line()
    )


def privacy_line() -> str:
    privacy = f"{ru_public_origin()}/privacy"
    return (f"<i>Храню только номер этого чата, чтобы отвечать. Вопросы своими словами передаю ИИ-модели "
            f"для ответа и не храню — не пишите в них личные данные. /stop — удалить всё. "
            f"<a href=\"{privacy}\">Политика конфиденциальности</a></i>")


UNKNOWN_TEXT = ("Такой цифры у меня нет: беру только официальные данные. "
                "Ближе всего — темы ниже, или напишите, например, <b>ДИЗЕЛЬ</b> или <b>ИНФЛЯЦИЯ</b>.")
LIMIT_TEXT = "На сегодня вопросы закончились. Цифры по темам — кнопками ниже, они без ограничений."
LLM_FAIL_TEXT = "Не получилось ответить на вопрос. Попробуйте позже или выберите тему ниже."
SOURCE_QUESTION = "Один вопрос: откуда вы о нас узнали?"
WELCOME_BACK = "С возвращением! Выберите тему, напишите слово или спросите своими словами."
SHORT_INTRO = ("Это бот <b>Forecast Economy</b>: свежие цифры экономики России из официальных источников. "
               "Напишите слово или спросите своими словами.")
GREETING_TEXT = "Здравствуйте! Выберите тему кнопкой, напишите слово, например <b>БЕНЗИН</b>, или спросите своими словами."
THANKS_TEXT = "Пожалуйста! Если нужно ещё — выберите тему или спросите своими словами."
_GREETINGS = {"привет", "здравствуйте", "здравствуй", "добрый день", "добрый вечер", "доброе утро", "hi", "hello",
              "хай", "салют", "ку", "приветствую"}
_THANKS = {"спасибо", "спс", "благодарю", "спасибо большое", "thanks", "thx", "ок", "окей", "ok", "понятно", "ясно"}
STOP_TEXT = "Готово: удалил подписки и номер этого чата. Чтобы вернуться, нажмите /start."


# ---------------------------------------------------------------------------
# Хранение
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _touch_chat(db, chat_id: str, code: str | None = None) -> PublicBotChat:
    chat = await db.get(PublicBotChat, chat_id)
    now = _now()
    if chat is None:
        chat = PublicBotChat(chat_id=chat_id, chat_hash=chat_hash(chat_id), first_code=code,
                             first_seen_at=now, last_seen_at=now)
        db.add(chat)
    else:
        chat.last_seen_at = now
        chat.blocked_at = None
        if code and not chat.first_code:
            chat.first_code = code
    return chat


def _event(db, chat_id: str, kind: str, code: str | None = None, topic: str | None = None) -> None:
    db.add(PublicBotEvent(occurred_at=_now(), chat_hash=chat_hash(chat_id), kind=kind,
                          code=(code or None) and code[:64], topic=topic))


async def _is_subscribed(db, chat_id: str, topic: str) -> bool:
    return (await db.execute(select(PublicBotSubscription.id).where(
        PublicBotSubscription.chat_id == chat_id, PublicBotSubscription.topic == topic,
    ))).first() is not None


# ---------------------------------------------------------------------------
# Сценарии
# ---------------------------------------------------------------------------

async def _send(chat_id: str, text: str, kb: dict | None = None, kind: str = KIND_REPLY) -> bool:
    from app.services.telegram_bot import send_message  # локальный импорт против цикла
    # Без превью ссылок: иначе под приветствием встаёт большая карточка страницы политики.
    return await send_message(chat_id, text, reply_markup=kb, kind=kind, link_preview=False,
                              token=bot_token())


def bot_token() -> str:
    """Токен публичного бота: свой (@ForecastEconomyBot) или служебный в общей схеме."""
    return settings.public_bot_token or settings.telegram_bot_token


async def _reply_figure(chat_id: str, topic_key: str) -> None:
    topic = TOPICS[topic_key]
    async with async_session() as db:
        chat = await _touch_chat(db, chat_id)
        fig = await load_figure(db, topic)
        cpi = await load_figure(db, TOPICS["inflation"]) if topic_key != "inflation" else None
        subscribed = await _is_subscribed(db, chat_id, topic_key)
        # Пришёл по коду ролика — источник известен, не спрашиваем (итоги агентов 08.11.2026).
        ask_source = chat.heard_from is None and chat.asked_source_at is None and not chat.first_code
        if ask_source:
            chat.asked_source_at = _now()
        code = chat.first_code
        await db.commit()
    if fig is None:
        await _send(chat_id, f"По теме «{escape(topic.title)}» сейчас нет данных. Выберите другую:", menu_keyboard())
        return
    await _send(chat_id, figure_text(fig, cpi=cpi), figure_keyboard(topic, code, subscribed))
    if ask_source:
        await _send(chat_id, SOURCE_QUESTION, sources_keyboard())


async def handle_message(msg: dict) -> None:
    chat = msg.get("chat") or {}
    if chat.get("type") != "private":
        return
    chat_id = str(chat.get("id", ""))
    text = (msg.get("text") or "").strip()
    if not chat_id or not text:
        return
    low = _norm(text)
    if low.startswith("/start"):
        code, topic = parse_start(text)
        async with async_session() as db:
            returning = await db.get(PublicBotChat, chat_id) is not None
            await _touch_chat(db, chat_id, code)
            _event(db, chat_id, "start", code=code, topic=topic)
            subs = (await db.execute(select(PublicBotSubscription.topic).where(
                PublicBotSubscription.chat_id == chat_id))).scalars().all()
            await db.commit()
        if topic:
            # По ссылке из ролика: сразу цифра по теме ролика, потом короткая строка о боте.
            await _reply_figure(chat_id, topic)
            await _send(chat_id, (WELCOME_BACK if returning else SHORT_INTRO + "\n\n" + privacy_line()),
                        menu_keyboard())
        elif returning:
            names = ", ".join(TOPICS[s].title for s in subs if s in TOPICS)
            extra = f"\nПрисылаю новые данные: {escape(names)}." if names else ""
            await _send(chat_id, WELCOME_BACK + extra, menu_keyboard())
        else:
            await _send(chat_id, welcome_text(), menu_keyboard())
        return
    if low in ("/stop", "стоп"):
        await forget_chat(chat_id)
        await _send(chat_id, STOP_TEXT)
        return
    if low in ("/menu", "/help", "меню"):
        await _send(chat_id, "Выберите тему:", menu_keyboard())
        return
    bare = re.sub(r"[!.,?)( 🙂😊👋]+$", "", low).strip()
    if bare in _GREETINGS or bare in _THANKS:
        # Без модели: приветствие и «спасибо» не должны тратить лимит вопросов.
        async with async_session() as db:
            await _touch_chat(db, chat_id)
            await db.commit()
        await _send(chat_id, GREETING_TEXT if bare in _GREETINGS else THANKS_TEXT, menu_keyboard())
        return
    topic, word = match_topic(text)
    async with async_session() as db:
        await _touch_chat(db, chat_id, word if topic else None)
        _event(db, chat_id, "word" if topic else "unknown", code=word, topic=topic)
        await db.commit()
    if topic and len(text) <= 40:
        await _reply_figure(chat_id, topic)
    elif settings.public_bot_llm_enabled and settings.openrouter_api_key:
        await answer_question(chat_id, text)
    elif topic:
        await _reply_figure(chat_id, topic)
    else:
        await _send(chat_id, UNKNOWN_TEXT, menu_keyboard())


async def handle_callback(cq: dict) -> None:
    from app.services.telegram_bot import _api  # локальный импорт против цикла

    msg = cq.get("message") or {}
    chat_id = str((msg.get("chat") or {}).get("id", ""))
    data = cq.get("data") or ""
    await _api("answerCallbackQuery", {"callback_query_id": cq.get("id")}, token=bot_token())
    if not chat_id or not data.startswith(CB_PREFIX):
        return
    action, _, arg = data[len(CB_PREFIX):].partition(":")
    if action == "menu":
        await _send(chat_id, "Выберите тему:", menu_keyboard())
    elif action == "t" and arg in TOPICS:
        async with async_session() as db:
            await _touch_chat(db, chat_id)
            _event(db, chat_id, "topic", topic=arg)
            await db.commit()
        await _reply_figure(chat_id, arg)
    elif action == "s" and arg in TOPICS:
        await subscribe(chat_id, arg)
        await _send(chat_id, f"🔔 Пришлю, когда выйдут новые данные: <b>{escape(TOPICS[arg].title)}</b>. "
                             "Отключить — кнопкой под цифрой или /stop.")
    elif action == "u" and arg in TOPICS:
        await unsubscribe(chat_id, arg)
        await _send(chat_id, f"🔕 Больше не присылаю: {escape(TOPICS[arg].title)}.")
    elif action == "src" and arg in dict(SOURCES):
        async with async_session() as db:
            chat = await _touch_chat(db, chat_id)
            chat.heard_from = arg
            _event(db, chat_id, "source", code=arg)
            await db.commit()
        await _send(chat_id, "Спасибо!")


async def handle_member_update(upd: dict) -> None:
    """my_chat_member: человек остановил (заблокировал) бота или вернулся."""
    chat = upd.get("chat") or {}
    if chat.get("type") != "private":
        return
    chat_id = str(chat.get("id", ""))
    status = ((upd.get("new_chat_member") or {}).get("status")) or ""
    if status == "kicked":
        await mark_blocked(chat_id)


async def subscribe(chat_id: str, topic_key: str) -> None:
    topic = TOPICS[topic_key]
    async with async_session() as db:
        await _touch_chat(db, chat_id)
        fig = await load_figure(db, topic)
        sub = (await db.execute(select(PublicBotSubscription).where(
            PublicBotSubscription.chat_id == chat_id, PublicBotSubscription.topic == topic_key,
        ))).scalar_one_or_none()
        if sub is None:
            db.add(PublicBotSubscription(
                chat_id=chat_id, topic=topic_key, created_at=_now(),
                last_point_date=fig.last_date if fig else None,
                last_value=fig.last_value if fig else None, last_sent_at=_now(),
            ))
        _event(db, chat_id, "subscribe", topic=topic_key)
        await db.commit()


async def unsubscribe(chat_id: str, topic_key: str) -> None:
    async with async_session() as db:
        await db.execute(delete(PublicBotSubscription).where(
            PublicBotSubscription.chat_id == chat_id, PublicBotSubscription.topic == topic_key,
        ))
        _event(db, chat_id, "unsubscribe", topic=topic_key)
        await db.commit()


async def mark_blocked(chat_id: str) -> None:
    async with async_session() as db:
        chat = await db.get(PublicBotChat, chat_id)
        if chat is not None and chat.blocked_at is None:
            chat.blocked_at = _now()
            _event(db, chat_id, "blocked")
        await db.commit()


async def forget_chat(chat_id: str) -> None:
    """/stop: удалить номер чата, подписки и архив публичных ответов этому чату."""
    async with async_session() as db:
        _event(db, chat_id, "stop")
        await db.execute(delete(PublicBotSubscription).where(PublicBotSubscription.chat_id == chat_id))
        await db.execute(delete(PublicBotChat).where(PublicBotChat.chat_id == chat_id))
        await db.execute(delete(TelegramOutbox).where(
            TelegramOutbox.chat_id == chat_id, TelegramOutbox.kind.in_((KIND_REPLY, KIND_NOTIFY)),
        ))
        await db.commit()


# ---------------------------------------------------------------------------
# Рассылка новых данных
# ---------------------------------------------------------------------------

def _in_window(now_msk: datetime) -> bool:
    return settings.public_bot_notify_from_hour <= now_msk.hour < settings.public_bot_notify_to_hour


def _should_notify(topic: Topic, sub: PublicBotSubscription, fig: Figure, now: datetime) -> bool:
    if sub.last_point_date is not None and fig.last_date <= sub.last_point_date:
        return False
    if topic.notify == "on_change":
        return sub.last_value is None or abs(float(sub.last_value) - fig.last_value) > 1e-9
    if topic.notify == "weekly":
        return sub.last_sent_at is None or now - sub.last_sent_at >= timedelta(days=7)
    return True


async def public_bot_notify_job(now: datetime | None = None) -> dict:
    """Раз в 30 минут: подписчикам — новая точка ряда (днём по Москве, без ночных сообщений)."""
    from app.services import telegram_bot

    now = now or _now()
    stats = {"sent": 0, "blocked": 0, "skipped": 0}
    if not settings.public_bot_enabled:
        return stats
    if not _in_window(now.replace(tzinfo=timezone.utc).astimezone(_MSK)):
        return stats
    async with async_session() as db:
        subs = (await db.execute(
            select(PublicBotSubscription).join(PublicBotChat, PublicBotChat.chat_id == PublicBotSubscription.chat_id)
            .where(PublicBotChat.blocked_at.is_(None))
        )).scalars().all()
        figures: dict[str, Figure | None] = {}
        for key in {s.topic for s in subs} | {"inflation"}:
            if key in TOPICS:
                figures[key] = await load_figure(db, TOPICS[key])
        for sub in subs:
            topic = TOPICS.get(sub.topic)
            fig = figures.get(sub.topic)
            if topic is None or fig is None:
                continue
            if not _should_notify(topic, sub, fig, now):
                if sub.last_point_date is None or fig.last_date > sub.last_point_date:
                    # Новая точка без повода писать (ставка не изменилась; курс — не чаще раза в неделю):
                    # для on_change запоминаем точку, для weekly ждём недели.
                    if topic.notify == "on_change":
                        sub.last_point_date, sub.last_value = fig.last_date, fig.last_value
                stats["skipped"] += 1
                continue
            telegram_bot._last_api_error.set(None)
            ok = await _send(sub.chat_id, figure_text(fig, header="🔔 <b>Новые данные</b>",
                                                      cpi=figures.get("inflation")),
                             figure_keyboard(topic, None, True), kind=KIND_NOTIFY)
            if ok:
                sub.last_point_date, sub.last_value, sub.last_sent_at = fig.last_date, fig.last_value, now
                _event(db, sub.chat_id, "notify", topic=sub.topic)
                stats["sent"] += 1
            elif "403" in (telegram_bot._last_api_error.get() or ""):
                chat = await db.get(PublicBotChat, sub.chat_id)
                if chat is not None and chat.blocked_at is None:
                    chat.blocked_at = now
                    _event(db, sub.chat_id, "blocked")
                stats["blocked"] += 1
            await asyncio.sleep(0.05)  # ≤ 20 сообщений в секунду, лимит Bot API — 30
        await db.commit()
    if stats["sent"] or stats["blocked"]:
        logger.info("Public bot notify: %s", stats)
    return stats


# ---------------------------------------------------------------------------
# Отчёт для админ-меню
# ---------------------------------------------------------------------------

async def report_text(days: int = 7) -> str:
    since = _now() - timedelta(days=days)
    async with async_session() as db:
        total = (await db.execute(select(func.count()).select_from(PublicBotChat))).scalar_one()
        new = (await db.execute(select(func.count()).select_from(PublicBotChat)
                                .where(PublicBotChat.first_seen_at >= since))).scalar_one()
        blocked = (await db.execute(select(func.count()).select_from(PublicBotChat)
                                    .where(PublicBotChat.blocked_at.is_not(None)))).scalar_one()
        code_col = func.coalesce(PublicBotChat.first_code, "без кода")
        codes = (await db.execute(
            select(code_col, func.count())
            .where(PublicBotChat.first_seen_at >= since)
            .group_by(code_col).order_by(func.count().desc()).limit(15)
        )).all()
        topics = (await db.execute(
            select(PublicBotEvent.topic, func.count())
            .where(PublicBotEvent.occurred_at >= since, PublicBotEvent.topic.is_not(None),
                   PublicBotEvent.kind.in_(("start", "word", "topic")))
            .group_by(PublicBotEvent.topic).order_by(func.count().desc())
        )).all()
        subs = (await db.execute(
            select(PublicBotSubscription.topic, func.count()).group_by(PublicBotSubscription.topic).order_by(func.count().desc())
        )).all()
        heard = (await db.execute(
            select(PublicBotChat.heard_from, func.count())
            .where(PublicBotChat.heard_from.is_not(None)).group_by(PublicBotChat.heard_from).order_by(func.count().desc())
        )).all()
        returned = (await db.execute(
            select(func.count(func.distinct(PublicBotEvent.chat_hash)))
            .where(PublicBotEvent.occurred_at >= since,
                   PublicBotEvent.kind.in_(("word", "topic", "start", "subscribe")))
            .where(PublicBotEvent.chat_hash.in_(
                select(PublicBotChat.chat_hash).where(PublicBotChat.first_seen_at < since)
            ))
        )).scalar_one()

    def _line(rows, names=None) -> str:
        if not rows:
            return "—"
        return ", ".join(f"{escape(str((names or {}).get(k, k)))} {n}" for k, n in rows)

    titles = {k: t.title for k, t in TOPICS.items()}
    return (
        f"🤖 <b>Публичный бот</b> — за {days} дн.\n"
        f"Новых людей: <b>{new}</b> (всего {total}, остановили бота {blocked})\n"
        f"Вернулись (пришли раньше, писали за период): <b>{returned}</b>\n"
        f"С какого кода пришли: {_line(codes)}\n"
        f"Что спрашивали: {_line(topics, titles)}\n"
        f"Подписки сейчас: {_line(subs, titles)}\n"
        f"Откуда узнали: {_line(heard, dict(SOURCES))}"
    )


# ---------------------------------------------------------------------------
# Ответы ИИ-модели (OpenRouter) по данным сайта — решение владельца 08.11.2026
# ---------------------------------------------------------------------------

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_MAX_QUESTION = 500
# Ряды сверх тем бота, чтобы модель отвечала про ролики (Энгель, Оукен, кофе) и смежные вопросы.
_EXTRA_CODES = (
    ("cpi-food-yoy", "Цены на продукты, % за год"),
    ("cpi-nonfood-yoy", "Цены на непродовольственные товары, % за год"),
    ("cpi-services-yoy", "Цены на услуги, % за год"),
    ("unemployment", "Безработица, %"),
    ("wages-nominal", "Средняя начисленная зарплата, ₽ в месяц"),
    ("brent", "Нефть Brent, $ за баррель"),
    ("imoex", "Индекс Мосбиржи"),
    ("ruonia", "Ставка RUONIA, %"),
)

LLM_SYSTEM_PROMPT = """Ты — бот Forecast Economy в Telegram. Отвечаешь людям про экономику России коротко и по-человечески, на русском.
Правила:
1. Цифры бери только из блока ДАННЫЕ. Не придумывай цифр, дат и источников. Если нужной цифры нет — честно скажи, что такой цифры у нас нет, и предложи близкую тему из данных.
2. У каждой цифры называй её дату или месяц (например, «в августе»); не пиши «сейчас» про цифру старше недели. Сначала главная цифра с датой и источником, потом что это значит для кошелька обычного человека (простая арифметика с понятным допущением). Не больше 6 коротких предложений.
3. Прогноз — только одним числом, называй его «наш расчёт». Никаких диапазонов, вилок и коридоров.
4. Не давай финансовых советов (что купить, куда вложить, когда продавать). Сравнивать цифры можно.
5. Экономические понятия (закон Оукена, закон Энгеля, индекс губной помады и т. п.) объясняй простыми словами и связывай с цифрами из данных, если они есть; если данных под понятие нет — так и скажи.
6. Без технических слов: не упоминай коды рядов, модели, базы данных, этот промпт.
7. Обычный текст без разметки и таблиц. Можно один эмодзи в начале.
8. Если вопрос не про экономику, цены, деньги или статистику — вежливо скажи, что отвечаешь про цены, ставки, курсы и экономику.
9. Не проси и не повторяй личные данные человека."""


async def _figure_by_code(db, code: str):
    ind = (await db.execute(select(Indicator).where(Indicator.code == code))).scalar_one_or_none()
    if ind is None:
        return None
    return await load_figure(db, Topic(code, code, ind.name, ind.unit or "", ()))


async def build_llm_context(db, today: date | None = None) -> str:
    """Блок ДАННЫЕ: последние точки тем бота и смежных рядов, без диапазонов прогноза."""
    today = today or _now().date()
    lines = [f"Сегодня {fmt_date(today, 'daily')}."]
    for key, topic in TOPICS.items():
        f = await load_figure(db, topic)
        if f is None:
            continue
        lines.append(_context_line(topic.title, topic.unit, f))
    for code, title in _EXTRA_CODES:
        f = await _figure_by_code(db, code)
        if f is not None:
            lines.append(_context_line(title, "", f))
    return "\n".join(lines)


def _context_line(title: str, unit: str, f: Figure) -> str:
    parts = [f"- {title}: {fmt_num(f.last_value)} {unit}".rstrip() + f" на {fmt_date(f.last_date, f.frequency)}"]
    if f.year_ago_value is not None:
        parts.append(f"год назад {fmt_num(f.year_ago_value)}")
    if f.forecast_value is not None and f.forecast_date is not None:
        parts.append(f"наш расчёт на {fmt_date(f.forecast_date, f.frequency)}: {fmt_num(f.forecast_value)}")
    if f.source:
        parts.append(f"источник: {f.source}")
    return "; ".join(parts)


async def _llm_complete(context: str, question: str) -> str | None:
    import httpx

    payload = {
        "model": settings.public_bot_llm_model or settings.openrouter_model,
        "max_tokens": 700,
        "messages": [
            {"role": "system", "content": LLM_SYSTEM_PROMPT + "\n\nДАННЫЕ:\n" + context},
            {"role": "user", "content": question[:_MAX_QUESTION]},
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=60, proxy=settings.openrouter_proxy_url or None) as client:
            resp = await client.post(
                _OPENROUTER_URL, json=payload,
                headers={"Authorization": f"Bearer {settings.openrouter_api_key}",
                         "X-Title": "Forecast Economy bot"},
            )
        if resp.status_code != 200:
            logger.warning("Public bot LLM: HTTP %s", resp.status_code)
            return None
        content = (resp.json().get("choices") or [{}])[0].get("message", {}).get("content")
        return content.strip() if isinstance(content, str) and content.strip() else None
    except Exception:  # noqa: BLE001
        logger.warning("Public bot LLM failed", exc_info=True)
        return None


async def answer_question(chat_id: str, text: str) -> None:
    """Вопрос своими словами → ответ модели по блоку ДАННЫЕ. Текст вопроса не хранится."""
    from app.services.telegram_bot import _api

    day_start = datetime.combine(_now().date(), datetime.min.time())
    async with async_session() as db:
        used = (await db.execute(select(func.count()).select_from(PublicBotEvent).where(
            PublicBotEvent.chat_hash == chat_hash(chat_id), PublicBotEvent.kind == "ask",
            PublicBotEvent.occurred_at >= day_start,
        ))).scalar_one()
        if used >= settings.public_bot_llm_daily_limit:
            await db.commit()
            await _send(chat_id, LIMIT_TEXT, menu_keyboard())
            return
        _event(db, chat_id, "ask")
        context = await build_llm_context(db)
        await db.commit()
    answer = await _with_typing(chat_id, _llm_complete(context, text))
    if not answer:
        await _send(chat_id, LLM_FAIL_TEXT, menu_keyboard())
        return
    await _send(chat_id, escape(answer), {"inline_keyboard": [
        [{"text": "Все темы", "callback_data": f"{CB_PREFIX}menu"}],
    ]})


# ---------------------------------------------------------------------------
# Свой поллер отдельного бота (@ForecastEconomyBot)
# ---------------------------------------------------------------------------

_OFFSET_KEY = "fe:tg:public_offset"
_offset_mem: str | None = None
# Одна задача планировщика в минуту держит опросы подряд ~35 с (+ до 20 с последнего long-poll),
# чтобы не было наложений: при задаче раз в 2 с журнал каждые 2 с писал «skipped: maximum number of
# running instances» (живой прогон 08.11.2026), а диск сервера заполнен на 88 %.
_POLL_BUDGET_S = 35.0


async def handle_update(upd: dict) -> None:
    if "callback_query" in upd:
        await handle_callback(upd["callback_query"])
    elif "message" in upd:
        await handle_message(upd["message"])
    elif "my_chat_member" in upd:
        await handle_member_update(upd["my_chat_member"])


async def public_bot_poll_job() -> None:
    """Задача раз в минуту: подряд long-poll getUpdates публичного бота около _POLL_BUDGET_S секунд."""
    if not (settings.public_bot_enabled and settings.public_bot_token):
        return
    import time

    deadline = time.monotonic() + _POLL_BUDGET_S
    while True:
        if not await _poll_once() or time.monotonic() >= deadline:
            break
    if _inflight:
        # Дождаться начатых ответов (модель до 60 с), чтобы следующая задача не наложилась на них.
        await asyncio.wait(set(_inflight), timeout=75)


async def _poll_once() -> bool:
    """Один getUpdates (держится до 20 с). False — Telegram не ответил, задача заканчивается."""
    global _offset_mem
    from app.core.cache import get_state_redis
    from app.services.telegram_bot import _api

    r = await get_state_redis()
    try:
        offset = await r.get(_OFFSET_KEY)
    except Exception as exc:  # noqa: BLE001 — Redis недоступен: смещение из памяти процесса
        logger.warning("Public bot poll: state-Redis не ответил: %s", exc)
        offset = _offset_mem
    if _offset_mem and (not offset or int(_offset_mem) > int(offset)):
        offset = _offset_mem
    payload: dict = {"timeout": 20, "allowed_updates": ["message", "callback_query", "my_chat_member"]}
    if offset:
        payload["offset"] = int(offset)
    data = await _api("getUpdates", payload, token=settings.public_bot_token)
    if not data:
        return False
    updates = data.get("result", [])
    for upd in updates:
        task = asyncio.ensure_future(_handle_in_order(upd))
        _inflight.add(task)
        task.add_done_callback(_inflight.discard)
    if updates:
        _offset_mem = str(updates[-1]["update_id"] + 1)
        try:
            await r.set(_OFFSET_KEY, _offset_mem)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Public bot poll: смещение не записано в Redis: %s", exc)
    return True



async def _with_typing(chat_id: str, coro):
    """Пока модель думает, держим «печатает…» (статус гаснет через ~5 с, обновляем каждые 4 с)."""
    from app.services.telegram_bot import _api

    task = asyncio.ensure_future(coro)
    while not task.done():
        await _api("sendChatAction", {"chat_id": chat_id, "action": "typing"}, token=bot_token())
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=4)
        except asyncio.TimeoutError:
            continue
    return task.result()


# Разные люди не ждут друг друга: апдейты разных чатов идут параллельно, одного чата — по порядку.
_chat_locks: dict[str, asyncio.Lock] = {}
_inflight: set = set()


def _update_chat_id(upd: dict) -> str:
    for key in ("message", "my_chat_member"):
        if key in upd:
            return str((upd[key].get("chat") or {}).get("id", ""))
    if "callback_query" in upd:
        return str(((upd["callback_query"].get("message") or {}).get("chat") or {}).get("id", ""))
    return ""


async def _handle_in_order(upd: dict) -> None:
    lock = _chat_locks.setdefault(_update_chat_id(upd), asyncio.Lock())
    async with lock:
        try:
            await handle_update(upd)
        except Exception:  # noqa: BLE001
            logger.warning("Public bot update %s failed", upd.get("update_id"), exc_info=True)
    if len(_chat_locks) > 5000:
        _chat_locks.clear()

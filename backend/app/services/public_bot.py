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
import io
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
# Ролики (очередь контент-завода 08.11.2026): код из ссылки → тема ролика. Человек из ролика сразу получает
# ответ модели по теме ролика, а не общее приветствие.
REELS = {
    "r001": "индекс губной помады",
    "r002": "закон Энгеля: чем беднее семья, тем большая доля трат уходит на еду",
    "r003": "закон Оукена: связь безработицы и роста экономики",
    "r004": "куда деваются 5 рублей с чашки кофе",
    "r005": "почему бензин не дешевеет вместе с нефтью",
}
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


# Полные слова тем для опечаток («дизиль», «инфляцыя»): ближайшее по difflib, только для слов от 5 букв.
_FUZZY = {"дизель": "diesel", "солярка": "diesel", "бензин": "ai92", "инфляция": "inflation", "золото": "gold",
          "доллар": "usd", "ипотека": "mortgage", "вклады": "deposit", "депозит": "deposit", "ключевая": "keyrate"}


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
    if len(words) <= 3:
        import difflib
        for w in words:
            if len(w) >= 5:
                near = difflib.get_close_matches(w, list(_FUZZY), n=1, cutoff=0.75)
                if near:
                    return _FUZZY[near[0]], w[:64]
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
    if freq in ("quarterly",):
        return f"{(d.month - 1) // 3 + 1}-й квартал {d.year}"
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
                today: date | None = None, was: tuple[date | None, float | None] | None = None) -> str:
    t = f.topic
    unit = t.unit if t.unit != "%" else "%"
    lines = []
    if header:
        lines.append(header)
    scope = " — в среднем по России" if t.key in _RUSSIA_AVG else ""
    lines.append(f"<b>{escape(t.title)}</b>{scope}")
    lines.append(f"<b>{fmt_num(f.last_value)} {escape(unit)}</b> — {fmt_date(f.last_date, f.frequency)}")
    if was and was[1] is not None:
        when = f" ({fmt_date(was[0], f.frequency)})" if was[0] else ""
        lines.append(f"Было {fmt_num(was[1])} {escape(unit)}{when}.")
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
    if not header and (today - f.last_date).days > _FRESH_DAYS.get(f.frequency, 400):
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
    rows = [[{"text": TOPICS[k].title, "callback_data": f"{CB_PREFIX}t:{k}"} for k in row] for row in MENU]
    if settings.public_bot_llm_enabled and settings.openrouter_api_key:
        rows.append([{"text": "📰 Сводка", "callback_data": f"{CB_PREFIX}week"},
                     {"text": "❓ Что я умею", "callback_data": f"{CB_PREFIX}help"}])
    return {"inline_keyboard": rows}


WELCOME_EXAMPLES = ("Почему бензин дорожает?", "Сколько я теряю на инфляции?", "Выгодны ли сейчас вклады?")


def welcome_keyboard() -> dict:
    """Новичку — примеры вопросов (живой путь через модель) и темы карточками."""
    kb = menu_keyboard()
    if settings.public_bot_llm_enabled and settings.openrouter_api_key:
        kb["inline_keyboard"] = [[{"text": f"💬 {q}", "callback_data": f"{CB_PREFIX}q:{_question_id(q)}"}]
                                 for q in WELCOME_EXAMPLES] + kb["inline_keyboard"]
    return kb


def figure_keyboard(topic: Topic, code: str | None, subscribed: bool) -> dict:
    sub = ({"text": "🔕 Не присылать", "callback_data": f"{CB_PREFIX}u:{topic.key}"} if subscribed
           else {"text": "🔔 Присылать новые данные", "callback_data": f"{CB_PREFIX}s:{topic.key}"})
    return {"inline_keyboard": [
        [sub],
        ([{"text": "📊 График сюда", "callback_data": f"{CB_PREFIX}g:{topic.key}"},
          {"text": "📈 На сайте", "url": site_url(topic, code)}] if topic.key in CHART_TOPICS
         else [{"text": "📈 График и прогноз на сайте", "url": site_url(topic, code)}]),
        ([{"text": "💬 Почему так?", "callback_data": f"{CB_PREFIX}w:{topic.key}"}]
         if settings.public_bot_llm_enabled and settings.openrouter_api_key else []),
        [{"text": "Другие цифры", "callback_data": f"{CB_PREFIX}menu"}],
    ]}


def notify_keyboard(topic: Topic) -> dict:
    """Под рассылкой: спросить модель «что это значит» (если она включена), график, отписка."""
    kb = figure_keyboard(topic, None, True)
    if settings.public_bot_llm_enabled and settings.openrouter_api_key:
        q = f"Что значат свежие данные: {topic.title.lower()}?"
        kb["inline_keyboard"].insert(0, [{"text": "💬 Что это значит для меня?",
                                          "callback_data": f"{CB_PREFIX}q:{_question_id(q)}"}])
    return kb


def sources_keyboard() -> dict:
    return {"inline_keyboard": [
        [{"text": label, "callback_data": f"{CB_PREFIX}src:{key}"} for key, label in SOURCES[:3]],
        [{"text": label, "callback_data": f"{CB_PREFIX}src:{key}"} for key, label in SOURCES[3:]],
    ]}


def welcome_text() -> str:
    return (
        "Привет! Я <b>Forecast Economy</b> 👋\n"
        "Спрашивайте своими словами — про бензин, цены, ставки, вклады, курс. "
        "Отвечу по свежим официальным цифрам и объясню, что они значат для кошелька.\n\n"
        "Кнопки ниже — быстрые карточки с графиком и подпиской на новые данные.\n\n"
        + privacy_line()
    )


def privacy_line() -> str:
    privacy = f"{ru_public_origin()}/privacy"
    return (f"<i>Храню только номер этого чата, чтобы отвечать. Вопросы своими словами передаю ИИ-модели "
            f"для ответа и не храню — не пишите в них личные данные. /stop — удалить всё. "
            f"<a href=\"{privacy}\">Политика конфиденциальности</a></i>")


UNKNOWN_TEXT = ("Такой цифры у меня нет: беру только официальные данные. "
                "Ближе всего — темы ниже, или напишите, например, <b>ДИЗЕЛЬ</b> или <b>ИНФЛЯЦИЯ</b>.")
LIMIT_TEXT = ("На сегодня мои ответы закончились — продолжим завтра 🙂 "
              "Карточки тем, графики и подписки кнопками ниже работают без ограничений.")
LLM_FAIL_TEXT = "Не получилось ответить на вопрос. Попробуйте позже или выберите тему ниже."
SOURCE_QUESTION = "Один вопрос: откуда вы о нас узнали?"
WELCOME_BACK = "С возвращением! Спрашивайте своими словами или выберите тему."
SHORT_INTRO = ("Это <b>Forecast Economy</b>: свежие официальные цифры экономики России. "
               "Спрашивайте своими словами — отвечу и объясню.")
GREETING_TEXT = "Здравствуйте! Выберите тему кнопкой, напишите слово, например <b>БЕНЗИН</b>, или спросите своими словами."
THANKS_TEXT = "Пожалуйста! Если нужно ещё — выберите тему или спросите своими словами."
_GREETINGS = {"привет", "здравствуйте", "здравствуй", "добрый день", "добрый вечер", "доброе утро", "hi", "hello",
              "хай", "салют", "ку", "приветствую"}
_THANKS = {"спасибо", "спс", "благодарю", "спасибо большое", "thanks", "thx", "ок", "окей", "ok", "понятно", "ясно"}
GROUP_TEXT = ("Привет! Я отвечаю в личных сообщениях: t.me/ForecastEconomyBot 🙂\n"
              "А здесь можно делиться карточками: наберите <code>@ForecastEconomyBot дизель</code>.")
WELCOME_EN = ("Hi! I'm <b>Forecast Economy</b> 👋\nAsk in your own words about Russia's economy — fuel, prices, "
              "rates, deposits, the rouble. I answer with fresh official numbers.\n\n")
HELP_TEXT = ("<b>Что я умею</b>\n"
             "💬 Отвечаю на вопросы своими словами — про цены, бензин, ставки, вклады, ипотеку, курсы.\n"
             "📊 Присылаю график любой темы — просто попросите.\n"
             "📬 Скажите, что прислать, — пришлю: «присылай инфляцию», «напиши, когда изменится ставка». "
             "Список — /subs.\n"
             "📰 /week — короткая сводка: что изменилось и что это значит.\n"
             "↗️ В любом чате наберите <code>@ForecastEconomyBot дизель</code> — и отправьте карточку другу.\n"
             "🌱 А ещё я самоулучшаюсь: расскажите, чего не хватает, — передам команде, и это появится.\n"
             "🗑 /stop — удалить мои данные.")
MENU_TEXT = "Темы — или просто спросите своими словами:"
WEEK_TOPIC = "week"  # подписка на пятничную сводку (не тема-ряд)
WEEK_PROMPT = ("Сделай короткую сводку: что нового и важного в цифрах (бензин, цены, ставка, вклады, курсы) "
               "за последние неделю–месяц и что это значит для обычного кошелька. 4–6 пунктов, живо.")
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
    await _flush_questions()
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
        # Не на первой же карточке: спрашиваем, когда человек уже пользуется ботом дольше 10 минут.
        ask_source = (chat.heard_from is None and chat.asked_source_at is None and not chat.first_code
                      and _now() - chat.first_seen_at >= timedelta(minutes=10))
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
    text = (msg.get("text") or msg.get("caption") or "").strip()
    if not chat_id:
        return
    if not text:
        # Голосовое, фото, стикер без подписи: раньше бот молчал (проход 08.11.2026).
        if any(k in msg for k in ("voice", "audio", "video_note")):
            await _send(chat_id, "Голосовые пока не слушаю — напишите, пожалуйста, текстом 🙂", menu_keyboard())
        elif any(k in msg for k in ("photo", "document", "video", "sticker", "animation")):
            await _send(chat_id, "Картинки пока не разбираю. Напишите вопрос текстом — отвечу по цифрам.",
                        menu_keyboard())
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
        reel = REELS.get((code or "").split("_")[0].lower())
        if reel and settings.public_bot_llm_enabled and settings.openrouter_api_key:
            # Из ролика: модель встречает по теме ролика с нашими цифрами, затем строка о боте.
            await answer_question(chat_id, f"Я пришёл из вашего ролика «{reel}». Поздоровайся и коротко, живо "
                                           "объясни тему на наших цифрах.", hint_topic=topic)
            await _send(chat_id, (WELCOME_BACK if returning else SHORT_INTRO + "\n\n" + privacy_line()),
                        menu_keyboard())
        elif topic:
            # По ссылке из ролика: сразу цифра по теме ролика, потом короткая строка о боте.
            await _reply_figure(chat_id, topic)
            await _send(chat_id, (WELCOME_BACK if returning else SHORT_INTRO + "\n\n" + privacy_line()),
                        menu_keyboard())
        elif returning:
            names = ", ".join(TOPICS[s].title for s in subs if s in TOPICS)
            extra = f"\nПрисылаю новые данные: {escape(names)}." if names else ""
            await _send(chat_id, WELCOME_BACK + extra, menu_keyboard())
        elif str((msg.get("from") or {}).get("language_code", "")).startswith("en"):
            await _send(chat_id, WELCOME_EN + privacy_line(), welcome_keyboard())
        else:
            await _send(chat_id, welcome_text(), welcome_keyboard())
        return
    if low in ("/stop", "стоп"):
        await forget_chat(chat_id)
        await _send(chat_id, STOP_TEXT)
        return
    if low in ("/help", "помощь"):
        await _send(chat_id, HELP_TEXT, menu_keyboard())
        return
    if low in ("/menu", "меню"):
        await _send(chat_id, MENU_TEXT, menu_keyboard())
        return
    if low in ("/subs", "/подписки", "подписки"):
        async with async_session() as db:
            subs = (await db.execute(select(PublicBotSubscription.topic).where(
                PublicBotSubscription.chat_id == chat_id))).scalars().all()
        keys = [k for k in subs if k in TOPICS or k == WEEK_TOPIC]
        if not keys:
            await _send(chat_id, "Подписок пока нет. Под любой цифрой есть кнопка «🔔 Присылать новые данные».",
                        menu_keyboard())
        else:
            await _send(chat_id, "Присылаю новые данные по темам:", {"inline_keyboard": [
                [{"text": f"🔕 {TOPICS[k].title if k in TOPICS else 'Сводка по пятницам'}",
                  "callback_data": f"{CB_PREFIX}u:{k}"}] for k in keys
            ] + [[{"text": "Все темы", "callback_data": f"{CB_PREFIX}menu"}]]})
        return
    if low in ("/week", "/сводка", "сводка") and settings.public_bot_llm_enabled and settings.openrouter_api_key:
        async with async_session() as db:
            await _touch_chat(db, chat_id)
            _event(db, chat_id, "week")
            subscribed = await _is_subscribed(db, chat_id, WEEK_TOPIC)
            await db.commit()
        await answer_question(chat_id, WEEK_PROMPT)
        if not subscribed:
            await _send(chat_id, "Хотите получать такую сводку каждую пятницу утром?", {"inline_keyboard": [
                [{"text": "🔔 Да, по пятницам", "callback_data": f"{CB_PREFIX}s:{WEEK_TOPIC}"}]]})
        return
    topic, word = match_topic(text)
    # Кодом входа считаем только короткое слово из ролика (1–2 слова), а не слово внутри обычного вопроса:
    # в отчёте было «С какого кода пришли: ипотеку» из «стоит ли брать ипотеку?».
    keyword = word if topic and len(text.split()) <= 2 else None
    async with async_session() as db:
        await _touch_chat(db, chat_id, keyword)
        _event(db, chat_id, "word" if keyword else "unknown", code=keyword, topic=topic)
        await db.commit()
    if settings.public_bot_llm_enabled and settings.openrouter_api_key:
        # Модель главная (решение владельца 08.11.2026): любой текст, кроме команд, отвечает она.
        quoted = ((msg.get("reply_to_message") or {}).get("text") or "").strip()
        if quoted:
            # Ответ на конкретное сообщение бота: модель видит, о чём речь.
            text = f"(в ответ на сообщение: «{quoted[:400]}»)\n{text}"
        await answer_question(chat_id, text, hint_topic=topic, msg_id=msg.get("message_id"))
        return
    # Без модели — прежние скрипты: приветствие, тема по слову, подсказка.
    bare = re.sub(r"[!.,?)( 🙂😊👋]+$", "", low).strip()
    if not re.search(r"[a-zа-я0-9]", low):
        bare = "спасибо"
    if bare in _GREETINGS or bare in _THANKS:
        await _send(chat_id, GREETING_TEXT if bare in _GREETINGS else THANKS_TEXT, menu_keyboard())
    elif topic:
        await _reply_figure(chat_id, topic)
    else:
        await _send(chat_id, UNKNOWN_TEXT, menu_keyboard())


async def handle_callback(cq: dict) -> None:
    from app.services.telegram_bot import _api  # локальный импорт против цикла

    msg = cq.get("message") or {}
    chat_id = str((msg.get("chat") or {}).get("id", ""))
    data = cq.get("data") or ""
    data0 = cq.get("data") or ""
    toast = {"s": "🔔 Подписка включена", "u": "🔕 Подписка выключена", "g": "📊 Рисую график…",
             "q": "💬 Думаю…"}.get(data0[len(CB_PREFIX):].partition(":")[0]) if data0.startswith(CB_PREFIX) else None
    await _api("answerCallbackQuery", {"callback_query_id": cq.get("id"), **({"text": toast} if toast else {})},
               token=bot_token())
    if not chat_id or not data.startswith(CB_PREFIX):
        return
    action, _, arg = data[len(CB_PREFIX):].partition(":")
    if action == "week":
        await handle_message({"chat": {"id": int(chat_id) if chat_id.lstrip("-").isdigit() else chat_id,
                                       "type": "private"}, "text": "/week"})
        return
    if action == "help":
        await _send(chat_id, HELP_TEXT, menu_keyboard())
        return
    if action == "g" and arg in TOPICS:
        if not await send_chart(chat_id, arg):
            await _send(chat_id, "Не получилось прислать график — откройте его на сайте.",
                        {"inline_keyboard": [[{"text": "📈 На сайте", "url": site_url(TOPICS[arg], None)}]]})
        return
    if action == "w" and arg in TOPICS:
        # «Почему так?» под карточкой: тема в самой кнопке, память не нужна.
        if settings.public_bot_llm_enabled and settings.openrouter_api_key:
            await answer_question(chat_id, f"Почему так меняется: {TOPICS[arg].title.lower()}? Объясни простыми словами.",
                                  hint_topic=arg)
        return
    if action == "q":
        q = await _lookup_question(arg)
        if q and settings.public_bot_llm_enabled and settings.openrouter_api_key:
            await _send(chat_id, f"<i>{escape(q)}</i>")
            await answer_question(chat_id, q)
        else:
            await _send(chat_id, "Этот вопрос устарел — спросите своими словами 🙂", menu_keyboard())
        return
    if action == "menu":
        await _send(chat_id, MENU_TEXT, menu_keyboard())
    elif action == "t" and arg in TOPICS:
        async with async_session() as db:
            await _touch_chat(db, chat_id)
            _event(db, chat_id, "topic", topic=arg)
            await db.commit()
        await _reply_figure(chat_id, arg)
    elif action == "s" and arg == WEEK_TOPIC:
        async with async_session() as db:
            await _touch_chat(db, chat_id)
            if not await _is_subscribed(db, chat_id, WEEK_TOPIC):
                # last_sent_at пусто: первая сводка — в ближайшую пятницу.
                db.add(PublicBotSubscription(chat_id=chat_id, topic=WEEK_TOPIC, created_at=_now(), last_sent_at=None))
            _event(db, chat_id, "subscribe", topic=WEEK_TOPIC)
            await db.commit()
        await _send(chat_id, "🔔 Договорились: сводка — по пятницам утром. Отключить — /subs.")
    elif action == "u" and arg == WEEK_TOPIC:
        await unsubscribe(chat_id, WEEK_TOPIC)
        await _send(chat_id, "🔕 Пятничную сводку больше не присылаю.")
    elif action == "s" and arg in TOPICS:
        await subscribe(chat_id, arg)
        await _toggle_card_keyboard(msg, chat_id, arg, subscribed=True)
        async with async_session() as db:
            fig = await load_figure(db, TOPICS[arg])
        nxt = (f" Следующие ожидаются {fig.next_release.day} {_MONTHS[fig.next_release.month - 1]}."
               if fig and fig.next_release else "")
        await _send(chat_id, f"🔔 Пришлю, когда выйдут новые данные: <b>{escape(TOPICS[arg].title)}</b>.{nxt} "
                             "Все подписки — /subs.")
    elif action == "u" and arg in TOPICS:
        await unsubscribe(chat_id, arg)
        await _toggle_card_keyboard(msg, chat_id, arg, subscribed=False)
        await _send(chat_id, f"🔕 Больше не присылаю: {escape(TOPICS[arg].title)}.")
    elif action == "src" and arg in dict(SOURCES):
        async with async_session() as db:
            chat = await _touch_chat(db, chat_id)
            chat.heard_from = arg
            _event(db, chat_id, "source", code=arg)
            await db.commit()
        await _send(chat_id, "Спасибо!")


async def _toggle_card_keyboard(msg: dict, chat_id: str, topic_key: str, subscribed: bool) -> None:
    """После подписки кнопка под карточкой меняется на «Не присылать» и наоборот (живой прогон 08.11:
    после подписки под цифрой оставалось «Присылать»). Только у карточек темы, у ответа модели — нет."""
    from app.services.telegram_bot import _api

    rows = ((msg.get("reply_markup") or {}).get("inline_keyboard")) or []
    datas = [b.get("callback_data", "") for row in rows for b in row]
    if not any(d in (f"{CB_PREFIX}s:{topic_key}", f"{CB_PREFIX}u:{topic_key}") for d in datas):
        return
    is_card = any(d == f"{CB_PREFIX}menu" for d in datas) and any(b.get("url") for row in rows for b in row)
    if not is_card or not msg.get("message_id"):
        return
    await _api("editMessageReplyMarkup", {
        "chat_id": chat_id, "message_id": msg["message_id"],
        "reply_markup": figure_keyboard(TOPICS[topic_key], None, subscribed),
    }, token=bot_token(), timeout=10)


async def handle_member_update(upd: dict) -> None:
    """my_chat_member: человек остановил (заблокировал) бота или вернулся."""
    chat = upd.get("chat") or {}
    status = ((upd.get("new_chat_member") or {}).get("status")) or ""
    if chat.get("type") in ("group", "supergroup") and status in ("member", "administrator"):
        # Добавили в группу: вежливо зовём в личку (в группах бот не отвечает).
        await _send(str(chat.get("id", "")), GROUP_TEXT)
        return
    if chat.get("type") != "private":
        return
    chat_id = str(chat.get("id", ""))
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
    """/stop: удалить номер чата, подписки, архив публичных ответов этому чату и память разговора."""
    forget_history(chat_id)
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

async def _send_week_digest(now: datetime) -> int:
    """Пятница, с 10:00 МСК: одна сводка модели на всех подписчиков (кому не слали 6 дней)."""
    async with async_session() as db:
        due = (await db.execute(
            select(PublicBotSubscription).join(PublicBotChat, PublicBotChat.chat_id == PublicBotSubscription.chat_id)
            .where(PublicBotSubscription.topic == WEEK_TOPIC, PublicBotChat.blocked_at.is_(None))
        )).scalars().all()
        due = [d for d in due if d.last_sent_at is None or now - d.last_sent_at >= timedelta(days=6)]
        if not due:
            return 0
        context = await build_llm_context(db)
    answer = await _llm_complete(context, WEEK_PROMPT)
    if not answer:
        return 0
    clean, topics, _subs, _q, _c = split_actions(answer)
    sent = 0
    async with async_session() as db:
        for d in due:
            ok = await _send(d.chat_id, "📰 <b>Сводка недели</b>\n\n" + telegram_html(clean),
                             answer_keyboard(topics, []), kind=KIND_NOTIFY)
            if ok:
                row = await db.get(PublicBotSubscription, d.id)
                row.last_sent_at = now
                _event(db, d.chat_id, "notify", topic=WEEK_TOPIC)
                sent += 1
            await asyncio.sleep(0.05)
        await db.commit()
    return sent


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
    msk = now.replace(tzinfo=timezone.utc).astimezone(_MSK)
    if msk.weekday() == 4 and msk.hour >= 10 and settings.public_bot_llm_enabled and settings.openrouter_api_key:
        stats["week"] = await _send_week_digest(now)
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
            if sub.topic == WEEK_TOPIC:
                continue
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
            if sub.topic in CHART_TOPICS and TOPICS[sub.topic].indicator and fig.frequency != "daily":
                await send_chart(sub.chat_id, sub.topic)
            ok = await _send(sub.chat_id, figure_text(
                fig, header="🔔 <b>Новые данные</b>", cpi=figures.get("inflation"),
                was=(sub.last_point_date, float(sub.last_value) if sub.last_value is not None else None)),
                             notify_keyboard(topic), kind=KIND_NOTIFY)
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
        usage = dict((await db.execute(
            select(PublicBotEvent.kind, func.count())
            .where(PublicBotEvent.occurred_at >= since, PublicBotEvent.kind.in_(("ask", "week", "inline", "notify")))
            .group_by(PublicBotEvent.kind)
        )).all())
        lat = [float(c) for (c,) in (await db.execute(
            select(PublicBotEvent.code).where(PublicBotEvent.occurred_at >= since, PublicBotEvent.kind == "llm_time")
        )).all() if c]
        ideas = (await db.execute(
            select(PublicBotEvent.code, func.count())
            .where(PublicBotEvent.occurred_at >= since, PublicBotEvent.kind == "idea")
            .group_by(PublicBotEvent.code).order_by(func.count().desc()).limit(10)
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
        f"Откуда узнали: {_line(heard, dict(SOURCES))}\n"
        f"Ответов модели: {usage.get('ask', 0)} (из них /week {usage.get('week', 0)}), "
        f"карточек во встроенном режиме: {usage.get('inline', 0)}, рассылок: {usage.get('notify', 0)}"
        + (f"\nИдеи людей: {_line(ideas)}" if ideas else "")
        + (f"\nВремя ответа модели: в среднем {fmt_num(sum(lat) / len(lat), 1)} с, медленнее всего {fmt_num(max(lat), 1)} с"
           if lat else "")
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
    # Живой прогон 08.11: «какой курс юаня» — «нет в данных», хотя ряд на сайте есть.
    ("gdp-real-yoy", "Реальный ВВП, % к прошлому году"),
    ("cny-rub", "Юань, ₽"),
    ("btc-usd", "Биткоин, $"),
)

LLM_SYSTEM_PROMPT = """Ты — Forecast Economy, живой собеседник в Telegram, который разбирается в экономике России и умеет объяснять её по-человечески: просто, с теплом и уместным юмором, без канцелярита и воды. Подстраивайся под тон человека (обращайся на «ты» или «вы», как он сам), можешь задать встречный вопрос, если он поможет.

Опора — блок ДАННЫЕ: это официальная статистика с нашего сайта (у каждой цифры есть дата и источник). Цифры, даты и источники бери только оттуда и называй месяц цифры. Чего там нет — честно скажи и предложи близкое. ДАННЫЕ всегда свежее твоих прошлых реплик: если цифра там есть, используй её, даже если раньше говорил, что её нет. Общие знания об экономике и понятиях использовать можно, но без выдуманных чисел.

Три границы: прогноз — только одним числом («наш расчёт»), без диапазонов; не советуй, что покупать, куда вкладывать и когда продавать; не проси личных данных.

Оформление — HTML Telegram, умеренно: <b>, <i>, <u>, <s>, <code>, <blockquote>, <blockquote expandable> для подробностей, <tg-spoiler>, <a href="...">. Без Markdown, без таблиц и заголовков, без сокращений вроде «п.п.» (пиши «пункта»). Обычно хватает 2–6 коротких абзацев; длиннее — только если просят. Эмодзи — по вкусу, не в каждой строке. Отвечай на языке собеседника.

Если человеку пригодятся кнопки, добавь в самом конце отдельной строкой (её не увидят как текст):
[[темы: ключ, ключ]] — карточки тем с графиком и подпиской (не больше трёх);
[[подписка: ключ]] — предложить присылать новые данные по теме; если человек сам просит присылать — [[подписаться: ключ]] включит подписку сразу;
[[идея: суть до 60 знаков своими словами]] — если человеку не хватает темы, функции или данных: запиши суть, скажи, что передашь команде;
[[реакция: эмодзи]] — поставить реакцию на сообщение человека (одну из 👍 🔥 🤔 👏 😁 🤯 🎉 🙏 👌 💯 🏆 🤝 👀), если уместно;
[[график: ключ]] — график темы картинкой (последняя цифра, год назад, наш расчёт, сравнение по делу); он придёт перед твоим текстом;
[[вопросы: реплика | реплика]] — до трёх кнопок-реплик от лица человека (до 40 знаков): следующий вопрос, на который ответишь по ДАННЫМ (не просьбы о совете, куда вложить), а в игре или опросе — варианты ответа.
Ключи тем: diesel, ai92, ai95, inflation, keyrate, deposit, mortgage, gold, usd, eur.
Наш сайт ru.forecasteconomy.com: графики и прогнозы, регионы России (/russia/region), страны мира (например, /united-states), сравнение показателей (/compare), калькулятор инфляции (/calculator). Если цифры нет в ДАННЫХ — предложи нужный раздел нашего сайта ссылкой, а не чужие сайты."""


async def _figure_by_code(db, code: str):
    ind = (await db.execute(select(Indicator).where(Indicator.code == code))).scalar_one_or_none()
    if ind is None:
        return None
    return await load_figure(db, Topic(code, code, ind.name, ind.unit or "", ()))


async def build_llm_context(db, today: date | None = None) -> str:
    """Блок ДАННЫЕ: последние точки тем бота и смежных рядов, без диапазонов прогноза."""
    today = today or _now().date()
    lines = [f"Сегодня {fmt_date(today, 'daily')}."]
    cpi = await load_figure(db, TOPICS["inflation"])
    no_forecast: list[str] = []
    for key, topic in TOPICS.items():
        f = await load_figure(db, topic)
        if f is None:
            continue
        if f.forecast_value is None:
            no_forecast.append(topic.title)
        line = _context_line(topic.title, topic.unit, f)
        if (today - f.last_date).days > _FRESH_DAYS.get(f.frequency, 400):
            line += " (новее данных источник пока не публиковал)"
        lines.append(line)
        wallet = _wallet_line(f, cpi if key != "inflation" else None)
        if wallet:
            lines.append(f"  для кошелька: {wallet}")
    for code, title in _EXTRA_CODES:
        f = await _figure_by_code(db, code)
        if f is not None:
            lines.append(_context_line(title, "", f))
    yearly = await _series(db, "inflation-annual", date(today.year - 16, 1, 1), weekly=False)
    if yearly:
        # Для вопросов «сколько стоили бы мои деньги из 2015 года»: годовая инфляция по годам (Росстат).
        lines.append("Инфляция по годам, % (декабрь к декабрю): "
                     + ", ".join(f"{d.year} — {fmt_num(v, 1)}" for d, v in yearly[-15:]))
    if no_forecast:
        # Живой прогон 08.11: модель обещала «прогноз бензина на сайте», которого нет.
        lines.append("Нашего расчёта (прогноза) нет ни в боте, ни на сайте по темам: " + ", ".join(no_forecast)
                     + ". Не обещай его.")
    return "\n".join(lines)


def _context_line(title: str, unit: str, f: Figure) -> str:
    when = fmt_date(f.last_date, f.frequency)
    parts = [f"- {title}: {fmt_num(f.last_value)} {unit}".rstrip() + (f" за {when}" if f.frequency in ("monthly", "quarterly", "annual") else f" на {when}")]
    if f.prev_value is not None:
        parts.append(f"предыдущее значение {fmt_num(f.prev_value)}")
    if f.year_ago_value is not None:
        parts.append(f"год назад {fmt_num(f.year_ago_value)}")
    if f.forecast_value is not None and f.forecast_date is not None:
        parts.append(f"наш расчёт на {fmt_date(f.forecast_date, f.frequency)}: {fmt_num(f.forecast_value)}")
    if f.source:
        parts.append(f"источник: {f.source}")
    return "; ".join(parts)


async def _llm_complete(context: str, question: str, history: list[dict] | None = None) -> str | None:
    """Ответ модели; если основная не ответила — одна попытка запасной (openrouter_model)."""
    primary = settings.public_bot_llm_model or settings.openrouter_model
    answer = await _llm_call(primary, context, question, history)
    if answer is None and settings.public_bot_llm_model and settings.public_bot_llm_model != settings.openrouter_model:
        logger.warning("Public bot LLM: основная модель не ответила, пробую %s", settings.openrouter_model)
        answer = await _llm_call(settings.openrouter_model, context, question, history)
    return answer


async def _llm_call(model: str, context: str, question: str, history: list[dict] | None) -> str | None:
    import httpx

    payload = {
        "model": model,
        "max_tokens": 2000,
        "messages": [
            {"role": "system", "content": LLM_SYSTEM_PROMPT + "\n\nДАННЫЕ:\n" + context},
            *(history or []),
            {"role": "user", "content": question[:_MAX_QUESTION]
             + (" …(сообщение обрезано)" if len(question) > _MAX_QUESTION else "")},
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
        choice = (resp.json().get("choices") or [{}])[0]
        content = choice.get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            return None
        if choice.get("finish_reason") == "length":
            content = trim_to_paragraph(content)
        return content.strip()
    except Exception:  # noqa: BLE001
        logger.warning("Public bot LLM failed", exc_info=True)
        return None


# Короткая память разговора — только в памяти процесса (не в базе): последние реплики за 30 минут.
_HISTORY: dict[str, list[tuple[datetime, str, str]]] = {}
_HISTORY_TURNS = 6
_HISTORY_TTL = timedelta(minutes=30)


def _history(chat_id: str) -> list[dict]:
    now = _now()
    items = [h for h in _HISTORY.get(chat_id, []) if now - h[0] < _HISTORY_TTL][-_HISTORY_TURNS:]
    _HISTORY[chat_id] = items
    return [{"role": role, "content": content} for _, role, content in items]


def _remember(chat_id: str, role: str, content: str) -> None:
    _HISTORY.setdefault(chat_id, []).append((_now(), role, content[:1500]))
    if len(_HISTORY) > 5000:
        _HISTORY.clear()


def forget_history(chat_id: str) -> None:
    _HISTORY.pop(chat_id, None)


_ALLOWED_TAG = re.compile(
    r"&lt;(/?)(b|strong|i|em|u|ins|s|strike|del|code|pre|tg-spoiler)&gt;"
    r"|&lt;blockquote( expandable)?&gt;|&lt;/blockquote&gt;"
    r"|&lt;a href=&quot;(https?://[^\s&]+?)&quot;&gt;|&lt;/a&gt;"
)
_ACTIONS = re.compile(r"\[\[\s*(темы|подписка|подписаться|вопросы|график|реакция|идея)\s*:\s*([^\]]*)\]\]", re.I)
# Реакции, которые Telegram разрешает ботам (подмножество стандартных).
_REACTIONS = ("👍", "🔥", "🤔", "👏", "😁", "🤯", "🎉", "🙏", "👌", "💯", "🏆", "🤝", "👀")
# Кнопки-вопросы: callback_data ограничен 64 байтами, поэтому текст вопроса держим в памяти по короткому id.
_QUESTIONS: dict[str, str] = {}


def telegram_html(text: str) -> str:
    """Ответ модели → безопасный HTML Telegram: всё экранируется, разрешённые теги возвращаются.
    Markdown-жирный (**x**) превращается в <b>. Битая разметка всё равно дойдёт: send_message
    при «can't parse entities» шлёт текст без тегов."""
    out = escape(text, quote=True)

    def _back(m: re.Match) -> str:
        raw = m.group(0)
        if raw.startswith("&lt;a href="):
            return f'<a href="{m.group(4)}">'
        return raw.replace("&lt;", "<").replace("&gt;", ">")
    out = _ALLOWED_TAG.sub(_back, out)
    out = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", out)
    return out.strip()


def split_actions(answer: str) -> tuple[str, list[str], list[str], list[str], list[str]]:
    """Служебные строки модели [[темы|подписка|вопросы|график: …]] → (текст, темы, подписки, вопросы, графики)."""
    topics: list[str] = []
    subs: list[str] = []
    questions: list[str] = []
    charts: list[str] = []
    questions_meta: dict[str, str] = {}
    for kind, keys in _ACTIONS.findall(answer):
        kind = kind.lower()
        if kind == "идея":
            idea = re.sub(r"\s+", " ", keys).strip()[:64]
            if idea:
                questions_meta.setdefault("idea", idea)
            continue
        if kind == "подписаться":
            for k in re.split(r"[,\s]+", keys.strip().lower()):
                if k in TOPICS:
                    questions_meta.setdefault("subscribe_now", k)
            continue
        if kind == "реакция":
            emo = keys.strip()
            if emo in _REACTIONS:
                questions_meta.setdefault("reaction", emo)
            continue
        if kind == "вопросы":
            # Реплика от лица человека: вопрос или вариант ответа («80 ₽») — знак не дописываем.
            questions += [q.strip(" \"«»")[:60] for q in keys.split("|") if q.strip(" \"«»")]
            continue
        for k in re.split(r"[,\s]+", keys.strip().lower()):
            if k in TOPICS and (kind != "график" or k in CHART_TOPICS):
                {"подписка": subs, "график": charts}.get(kind, topics).append(k)
    clean = _ACTIONS.sub("", answer).strip()
    uniq = lambda xs: list(dict.fromkeys(xs))  # noqa: E731
    split_actions.last_reaction = questions_meta.get("reaction")  # type: ignore[attr-defined]
    split_actions.last_idea = questions_meta.get("idea")  # type: ignore[attr-defined]
    split_actions.last_subscribe = questions_meta.get("subscribe_now")  # type: ignore[attr-defined]
    return clean, uniq(topics)[:3], uniq(subs)[:2], uniq(questions)[:3], uniq(charts)[:1]


# Свой график (bot_chart.py) рисуется для всех тем: окно 3 года, у дневных рядов 18 месяцев.
CHART_TOPICS = tuple(TOPICS)
# С чем сравнивать по делу: (код ряда, подпись) или цель ЦБ.
_CHART_COMPARE = {"keyrate": ("cpi-yoy", "инфляция"), "deposit": ("cpi-yoy", "инфляция"),
                  "mortgage": ("key-rate", "ключевая ставка")}
_CHART_TARGET = {"inflation": ("цель ЦБ", 4.0)}


async def _series(db, code: str, since: date, weekly: bool) -> list[tuple[date, float]]:
    ind = (await db.execute(select(Indicator.id).where(Indicator.code == code))).scalar_one_or_none()
    if ind is None:
        return []
    rows = (await db.execute(
        select(IndicatorData.date, IndicatorData.value)
        .where(IndicatorData.indicator_id == ind, IndicatorData.date >= since)
        .order_by(IndicatorData.date)
    )).all()
    pts = [(r[0], float(r[1])) for r in rows]
    if weekly and len(pts) > 120:
        # Дневной ряд — последнее значение каждой недели: линия чище, смысл тот же.
        by_week: dict[tuple[int, int], tuple[date, float]] = {}
        for dt, v in pts:
            by_week[dt.isocalendar()[:2]] = (dt, v)
        pts = list(by_week.values())
        if pts and rows and pts[-1][0] != rows[-1][0]:
            pts.append((rows[-1][0], float(rows[-1][1])))
    return pts


_CHART_CACHE: dict[str, tuple[datetime, bytes]] = {}


async def render_topic_chart(topic_key: str) -> bytes | None:
    """PNG графика темы; кэш 10 минут (рассылка шлёт одну картинку многим подписчикам)."""
    hit = _CHART_CACHE.get(topic_key)
    if hit and _now() - hit[0] < timedelta(minutes=10):
        return hit[1]
    png = await _render_topic_chart(topic_key)
    if png:
        _CHART_CACHE[topic_key] = (_now(), png)
    return png


async def _render_topic_chart(topic_key: str) -> bytes | None:
    from app.services.bot_chart import Series, render_chart

    topic = TOPICS[topic_key]
    async with async_session() as db:
        fig = await load_figure(db, topic)
        if fig is None:
            return None
        daily = fig.frequency == "daily"
        since = date(fig.last_date.year - (1 if daily else 3), fig.last_date.month, 1)
        if daily:
            since = date(fig.last_date.year - 2, fig.last_date.month, 1) if fig.last_date.month <= 6 else \
                date(fig.last_date.year - 1, fig.last_date.month - 6, 1)
        pts = await _series(db, topic.indicator, since, weekly=daily)
        if len(pts) < 2:
            return None
        cmp_code, cmp_label = _CHART_COMPARE.get(topic_key, (None, None))
        cmp_pts = await _series(db, cmp_code, since, weekly=True) if cmp_code else None
    ya = None
    if fig.year_ago_value is not None:
        # То же значение «год назад», что в карточке (у дневных рядов график прорежен до недели).
        target = fig.last_date - timedelta(days=365)
        ya = (min(pts, key=lambda p: abs((p[0] - target).days))[0], fig.year_ago_value)
    unit = {"%": "%", "% за год": "%"}.get(topic.unit, topic.unit)
    series = Series(
        title=topic.title, unit=unit, source=fig.source, points=pts,
        forecast=(fig.forecast_date, fig.forecast_value) if fig.forecast_value is not None else None,
        year_ago=ya if ya and abs((ya[0] - (fig.last_date - timedelta(days=365))).days) <= 40 else None,
        compare_label=cmp_label, compare_points=cmp_pts, target=_CHART_TARGET.get(topic_key),
        is_rate=topic.is_rate, step=topic_key == "keyrate", unit_note=topic.unit,
        monthly=fig.frequency == "monthly",
    )
    return await asyncio.to_thread(render_chart, series)


def chart_url(topic: Topic) -> str:
    """Картинка-график показателя с сайта (та же, что OG-превью страницы)."""
    return f"{ru_public_origin()}/og/russia/{topic.indicator}.png"


async def send_chart(chat_id: str, topic_key: str) -> bool:
    from app.services.telegram_bot import _api

    topic = TOPICS[topic_key]
    caption = f"<b>{escape(topic.title)}</b> — <a href=\"{site_url(topic, None)}\">подробнее на сайте</a>"
    async with async_session() as db:
        fig = await load_figure(db, topic)
    if fig is not None:
        bits = [f"{fmt_num(fig.last_value)} {topic.unit} {('за ' if fig.frequency in ('monthly', 'quarterly') else 'на ')}"
                f"{fmt_date(fig.last_date, fig.frequency)}"]
        if fig.year_ago_value is not None:
            bits.append(f"год назад {fmt_num(fig.year_ago_value)}")
        if fig.forecast_value is not None:
            bits.append(f"наш расчёт {fmt_num(fig.forecast_value)}")
        caption = f"<b>{escape(topic.title)}</b>: " + escape(", ".join(bits)) + \
            f"\n<a href=\"{site_url(topic, None)}\">Подробнее на сайте</a>"
    try:
        png = await render_topic_chart(topic_key)
    except Exception:  # noqa: BLE001 — график не должен ронять ответ
        logger.warning("Public bot chart render failed: %s", topic_key, exc_info=True)
        png = None
    if png:
        res = await _api("sendPhoto", {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
                         files={"photo": (f"{topic_key}.png", io.BytesIO(png))}, token=bot_token(), timeout=30)
    else:
        res = await _api("sendPhoto", {"chat_id": chat_id, "photo": chart_url(topic), "caption": caption,
                                       "parse_mode": "HTML"}, token=bot_token(), timeout=30)
    return res is not None


_Q_KEY = "fe:pb:q:"
_Q_TTL = 30 * 24 * 3600


def _question_id(q: str) -> str:
    """Короткий id кнопки-вопроса. Текст — в памяти и в state-Redis на 30 дней: иначе после перезапуска
    (каждая выкладка) старые кнопки отвечали «вопрос устарел» (живой прогон 08.11.2026)."""
    qid = hashlib.sha1(q.encode("utf-8")).hexdigest()[:10]
    _QUESTIONS[qid] = q
    if len(_QUESTIONS) > 20000:
        _QUESTIONS.clear()
        _QUESTIONS[qid] = q
    _QUESTIONS_PENDING[qid] = q
    return qid


_QUESTIONS_PENDING: dict[str, str] = {}


async def _flush_questions() -> None:
    if not _QUESTIONS_PENDING:
        return
    items = dict(_QUESTIONS_PENDING)
    _QUESTIONS_PENDING.clear()
    try:
        from app.core.cache import get_state_redis
        r = await get_state_redis()
        for qid, q in items.items():
            await r.set(_Q_KEY + qid, q, ex=_Q_TTL)
    except Exception:  # noqa: BLE001 — Redis недоступен: кнопки живут до перезапуска
        logger.debug("question ids not stored", exc_info=True)


async def _lookup_question(qid: str) -> str | None:
    if qid in _QUESTIONS:
        return _QUESTIONS[qid]
    try:
        from app.core.cache import get_state_redis
        r = await get_state_redis()
        q = await r.get(_Q_KEY + qid)
        return q.decode() if isinstance(q, bytes) else q
    except Exception:  # noqa: BLE001
        return None


def answer_keyboard(topics: list[str], subs: list[str], questions: list[str] | None = None) -> dict:
    rows = [[{"text": f"💬 {q}", "callback_data": f"{CB_PREFIX}q:{_question_id(q)}"}] for q in (questions or [])]
    rows += [[{"text": TOPICS[k].title, "callback_data": f"{CB_PREFIX}t:{k}"} for k in topics]] if topics else []
    rows += [[{"text": f"🔔 Присылать: {TOPICS[k].title}", "callback_data": f"{CB_PREFIX}s:{k}"}] for k in subs]
    rows.append([{"text": "Все темы", "callback_data": f"{CB_PREFIX}menu"}])
    return {"inline_keyboard": rows}


def trim_to_paragraph(text: str) -> str:
    """Ответ упёрся в лимит длины (живой прогон 08.11: обрыв «Индекс Мосбиржи — 2 476,70»):
    режем до последнего целого абзаца и ставим многоточие."""
    cut = text.rstrip()
    para = cut.rfind("\n\n")
    if para > len(cut) // 3:
        cut = cut[:para]
    return cut.rstrip() + " …"


async def answer_question(chat_id: str, text: str, hint_topic: str | None = None,
                          msg_id: int | None = None) -> None:
    """Текст человека → ответ модели по блоку ДАННЫЕ и короткой памяти разговора. Текст в базе не хранится."""
    day_start = datetime.combine(_now().date(), datetime.min.time())
    async with async_session() as db:
        used = (await db.execute(select(func.count()).select_from(PublicBotEvent).where(
            PublicBotEvent.chat_hash == chat_hash(chat_id), PublicBotEvent.kind == "ask",
            PublicBotEvent.occurred_at >= day_start,
        ))).scalar_one()
        if used >= settings.public_bot_llm_daily_limit:
            await db.commit()
            if hint_topic:
                await _reply_figure(chat_id, hint_topic)
            else:
                await _send(chat_id, LIMIT_TEXT, menu_keyboard())
            return
        _event(db, chat_id, "ask", topic=hint_topic)
        context = await build_llm_context(db)
        subs = (await db.execute(select(PublicBotSubscription.topic).where(
            PublicBotSubscription.chat_id == chat_id))).scalars().all()
        await db.commit()
    names = ", ".join(TOPICS[k].title for k in subs if k in TOPICS)
    # Живой прогон 08.11: модель сказала «подписка уже у вас есть» сразу после отписки.
    context += f"\nПодписки этого человека на новые данные: {names or 'нет'}."
    history = _history(chat_id)
    import time
    started = time.monotonic()
    answer = await _with_typing(chat_id, _llm_complete(context, text, history))
    elapsed = time.monotonic() - started
    try:
        async with async_session() as db:
            _event(db, chat_id, "llm_time", code=f"{elapsed:.1f}")
            await db.commit()
    except Exception:  # noqa: BLE001 — замер не должен мешать ответу
        logger.debug("llm_time not stored", exc_info=True)
    if not answer:
        if hint_topic:
            await _reply_figure(chat_id, hint_topic)
        else:
            await _send(chat_id, LLM_FAIL_TEXT, menu_keyboard())
        return
    clean, topics, subs, questions, charts = split_actions(answer)
    reaction = getattr(split_actions, "last_reaction", None)
    idea = getattr(split_actions, "last_idea", None)
    subscribe_now = getattr(split_actions, "last_subscribe", None)
    if idea:
        # «Самоулучшаюсь»: суть пожелания своими словами модели (не текст человека) — в отчёт команде.
        async with async_session() as db:
            _event(db, chat_id, "idea", code=idea)
            await db.commit()
    if subscribe_now:
        # «Скажи, что прислать, — пришлю»: человек сам попросил — подписка сразу.
        await subscribe(chat_id, subscribe_now)
    if reaction and msg_id:
        from app.services.telegram_bot import _api
        asyncio.ensure_future(_api("setMessageReaction", {
            "chat_id": chat_id, "message_id": msg_id, "reaction": [{"type": "emoji", "emoji": reaction}],
        }, token=bot_token(), timeout=6))
    _remember(chat_id, "user", text[:_MAX_QUESTION])
    _remember(chat_id, "assistant", clean)
    for key in charts:
        await send_chart(chat_id, key)
    await _send(chat_id, telegram_html(clean), answer_keyboard(topics, subs, questions))


# ---------------------------------------------------------------------------
# Свой поллер отдельного бота (@ForecastEconomyBot)
# ---------------------------------------------------------------------------

_OFFSET_KEY = "fe:tg:public_offset"
_offset_mem: str | None = None
# Одна задача планировщика в минуту держит опросы подряд ~35 с (+ до 20 с последнего long-poll),
# чтобы не было наложений: при задаче раз в 2 с журнал каждые 2 с писал «skipped: maximum number of
# running instances» (живой прогон 08.11.2026), а диск сервера заполнен на 88 %.
_POLL_BUDGET_S = 35.0


async def handle_inline_query(iq: dict) -> None:
    """Встроенный режим: «@ForecastEconomyBot дизель» в любом чате → готовая карточка, чтобы поделиться.
    Пустой запрос — все темы. Без модели: карточки собираются скриптом из базы (быстро, без лимитов)."""
    from app.services.telegram_bot import _api

    query = (iq.get("query") or "").strip()
    topic, _ = match_topic(query) if query else (None, None)
    keys = [topic] if topic else [k for row in MENU for k in row]
    results = []
    async with async_session() as db:
        cpi = await load_figure(db, TOPICS["inflation"])
        for key in keys:
            fig = await load_figure(db, TOPICS[key])
            if fig is None:
                continue
            text = figure_text(fig, cpi=cpi if key != "inflation" else None)
            results.append({
                "type": "article", "id": key,
                "title": f"{TOPICS[key].title}: {fmt_num(fig.last_value)} {TOPICS[key].unit}",
                "description": f"{fmt_date(fig.last_date, fig.frequency)} · {fig.source}",
                **({"thumbnail_url": chart_url(TOPICS[key])} if key in CHART_TOPICS else {}),
                "input_message_content": {"message_text": text, "parse_mode": "HTML",
                                          "link_preview_options": {"is_disabled": True}},
                "reply_markup": {"inline_keyboard": [[
                    {"text": "Спросить бота", "url": f"https://t.me/{settings.public_bot_username}?start=share_{key}"},
                    {"text": "📈 На сайте", "url": site_url(TOPICS[key], "inline")},
                ]]},
            })
        _event(db, str((iq.get("from") or {}).get("id", "")), "inline", topic=topic)
        await db.commit()
    await _api("answerInlineQuery", {"inline_query_id": iq.get("id"), "results": results, "cache_time": 300,
                                     "is_personal": False,
                                     "button": {"text": "💬 Спросить бота своими словами", "start_parameter": "inline"}},
               token=bot_token(), timeout=10)


async def handle_update(upd: dict) -> None:
    if "inline_query" in upd:
        await handle_inline_query(upd["inline_query"])
        return
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
        await asyncio.wait(set(_inflight), timeout=20)


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
    payload: dict = {"timeout": 20,
                     "allowed_updates": ["message", "callback_query", "my_chat_member", "inline_query"]}
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
        # Не ждём: запрос к Telegram с российского сервера иногда висит до 35 с (проверено 08.11.2026).
        asyncio.ensure_future(_api("sendChatAction", {"chat_id": chat_id, "action": "typing"},
                                   token=bot_token(), timeout=6))
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=4)
        except asyncio.TimeoutError:
            continue
    return task.result()


# Разные люди не ждут друг друга: апдейты разных чатов идут параллельно, одного чата — по порядку.
_chat_locks: dict[str, asyncio.Lock] = {}
_inflight: set = set()


def _update_chat_id(upd: dict) -> str:
    if "inline_query" in upd:
        return "inline:" + str((upd["inline_query"].get("from") or {}).get("id", ""))
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

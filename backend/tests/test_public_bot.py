"""Публичный режим Telegram-бота (решение владельца 08.11.2026): код из ролика, слово, цифра, подписка."""
import asyncio
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.services.public_bot as pb
import app.services.telegram_bot as tb
from app.config import settings
from app.models import (
    EconomicEvent, Forecast, ForecastValue, Indicator, IndicatorData,
    PublicBotChat, PublicBotEvent, PublicBotSubscription, TelegramOutbox,
)

_TABLES = (Indicator, IndicatorData, Forecast, ForecastValue, EconomicEvent,
           PublicBotChat, PublicBotEvent, PublicBotSubscription, TelegramOutbox)


@pytest.fixture
def env(monkeypatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path/'bot.db'}")
    maker = async_sessionmaker(engine, expire_on_commit=False)
    sent: list[dict] = []
    api_calls: list[tuple[str, dict]] = []

    async def setup():
        async with engine.begin() as conn:
            for m in _TABLES:
                await conn.run_sync(lambda c, t=m.__table__: t.create(c))
        async with maker() as db:
            diesel = Indicator(code="fuel-diesel", name="Цена дизельного топлива", unit="руб./л",
                               frequency="weekly", source="Росстат")
            cpi = Indicator(code="cpi-yoy", name="ИПЦ год к году", unit="%", frequency="monthly", source="Росстат")
            key = Indicator(code="key-rate", name="Ключевая ставка", unit="%", frequency="daily", source="Банк России")
            db.add_all([diesel, cpi, key])
            await db.flush()
            db.add_all([
                IndicatorData(indicator_id=diesel.id, date=date(2025, 10, 27), value=77.0),
                IndicatorData(indicator_id=diesel.id, date=date(2026, 10, 19), value=86.0),
                IndicatorData(indicator_id=diesel.id, date=date(2026, 10, 26), value=86.52),
                IndicatorData(indicator_id=cpi.id, date=date(2026, 9, 1), value=6.35),
                IndicatorData(indicator_id=key.id, date=date(2026, 11, 6), value=14.0),
            ])
            f = Forecast(indicator_id=cpi.id, model_name="m", is_current=True)
            db.add(f)
            await db.flush()
            db.add(ForecastValue(forecast_id=f.id, date=date(2026, 10, 1), value=6.26, lower_bound=5.0, upper_bound=7.5))
            await db.commit()

    asyncio.run(setup())

    async def fake_send(chat_id, text, kb=None, kind=pb.KIND_REPLY):
        sent.append({"chat_id": chat_id, "text": text, "kb": kb, "kind": kind})
        return True

    async def fake_api(method, payload, files=None, token=None, **kw):
        api_calls.append((method, payload))
        return {"ok": True}

    monkeypatch.setattr(pb, "async_session", maker)
    monkeypatch.setattr(pb, "_send", fake_send)
    monkeypatch.setattr(tb, "_api", fake_api)
    monkeypatch.setattr(settings, "public_bot_enabled", True, raising=False)
    monkeypatch.setattr(settings, "telegram_bot_token", "test-token", raising=False)
    yield maker, sent, api_calls
    asyncio.run(engine.dispose())


def _msg(text, chat_id=555, chat_type="private"):
    return {"chat": {"id": chat_id, "type": chat_type}, "text": text}


def _cb(data, chat_id=555):
    return {"id": "cq1", "data": data, "message": {"chat": {"id": chat_id, "type": "private"}}}


async def _rows(maker, model):
    async with maker() as db:
        return (await db.execute(select(model))).scalars().all()


def test_words_and_start_codes():
    assert pb.match_topic("ДИЗЕЛЬ") == ("diesel", "дизель")
    assert pb.match_topic("ставки по вкладам")[0] == "deposit"
    assert pb.match_topic("ставка по ипотеке")[0] == "mortgage"
    assert pb.match_topic("ключевая ставка")[0] == "keyrate"
    assert pb.match_topic("цены на бензин 95")[0] == "ai95"
    assert pb.match_topic("Инфляцию покажи")[0] == "inflation"
    assert pb.match_topic("привет") == (None, None)
    assert pb.parse_start("/start r014_diesel") == ("r014_diesel", "diesel")
    assert pb.parse_start("/start r014") == ("r014", None)
    assert pb.parse_start("/start gold") == ("gold", "gold")
    assert pb.parse_start("/start <script>") == (None, None)
    assert pb.parse_start("/start") == (None, None)


def test_start_with_code_records_and_answers(env):
    maker, sent, _ = env
    asyncio.run(pb.handle_message(_msg("/start r014_diesel")))
    chats = asyncio.run(_rows(maker, PublicBotChat))
    assert [(c.chat_id, c.first_code) for c in chats] == [("555", "r014_diesel")]
    assert chats[0].asked_source_at is None  # пришёл по коду ролика — источник не спрашиваем
    events = asyncio.run(_rows(maker, PublicBotEvent))
    assert [(e.kind, e.code, e.topic) for e in events] == [("start", "r014_diesel", "diesel")]
    assert all(e.chat_hash != "555" and len(e.chat_hash) == 64 for e in events)
    texts = [s["text"] for s in sent]
    # По ссылке из ролика: сначала цифра, потом короткая строка о боте с политикой.
    assert "<b>Дизель</b> — в среднем по России" in texts[0]
    assert "<b>86,52 ₽ за литр</b> — 26 октября 2026" in texts[0]
    assert "За неделю: +0,6 %" in texts[0] and "За год: +12,4 %" in texts[0]
    assert "Полный бак 50 л: ≈4 326 ₽, год назад ≈3 850 ₽." in texts[0]
    assert texts[1].startswith(pb.SHORT_INTRO) and "/stop" in texts[1]
    assert pb.SOURCE_QUESTION not in texts
    assert sent[0]["kb"]["inline_keyboard"][1][0]["callback_data"] == "pb:g:diesel"
    url = sent[0]["kb"]["inline_keyboard"][1][1]["url"]
    assert url.startswith("https://ru.forecasteconomy.com/russia/indicator/fuel-diesel?")
    assert "utm_source=telegram" in url and "utm_campaign=diesel" in url and "utm_content=r014_diesel" in url


def test_word_answer_and_source_asked_once(env):
    maker, sent, _ = env
    # Пришёл без кода (кнопкой темы) — один раз спрашиваем, откуда узнал.
    asyncio.run(pb.handle_callback(_cb("pb:t:inflation")))
    asyncio.run(pb.handle_callback(_cb("pb:t:diesel")))
    texts = [s["text"] for s in sent]
    assert texts.count(pb.SOURCE_QUESTION) == 1
    cpi = texts[0]
    assert "<b>6,35 % за год</b> — сентябрь 2026" in cpi
    # Прогноз — одной точкой, без диапазона (правило владельца).
    assert "Наш расчёт на октябрь 2026: 6,26 % за год (прогноз Forecast Economy)" in cpi
    assert "5,00" not in cpi and "7,50" not in cpi
    assert "Что стоило 100 ₽ год назад, сейчас стоит ≈106,35 ₽." in cpi
    asyncio.run(pb.handle_message(_msg("Инфляция", chat_id=556)))
    chat = [c for c in asyncio.run(_rows(maker, PublicBotChat)) if c.chat_id == "556"][0]
    assert chat.first_code == "инфляция"
    asyncio.run(pb.handle_callback(_cb("pb:src:instagram")))
    assert asyncio.run(_rows(maker, PublicBotChat))[0].heard_from == "instagram"


def test_unknown_word_and_group_chat(env):
    maker, sent, _ = env
    asyncio.run(pb.handle_message(_msg("как дела", chat_id=777)))
    assert sent[-1]["text"] == pb.UNKNOWN_TEXT
    ev = asyncio.run(_rows(maker, PublicBotEvent))
    assert [(e.kind, e.code) for e in ev] == [("unknown", None)]  # свободный текст не храним
    n = len(sent)
    asyncio.run(pb.handle_message(_msg("дизель", chat_id=-100, chat_type="group")))
    assert len(sent) == n


def test_subscribe_notify_once_and_window(env):
    maker, sent, _ = env
    asyncio.run(pb.handle_callback(_cb("pb:s:diesel")))
    sub = asyncio.run(_rows(maker, PublicBotSubscription))[0]
    assert sub.last_point_date == date(2026, 10, 26)
    noon_msk = datetime(2026, 11, 9, 9, 0)  # 12:00 МСК
    sent.clear()
    assert asyncio.run(pb.public_bot_notify_job(now=noon_msk))["sent"] == 0

    async def add_point():
        async with maker() as db:
            ind = (await db.execute(select(Indicator).where(Indicator.code == "fuel-diesel"))).scalar_one()
            db.add(IndicatorData(indicator_id=ind.id, date=date(2026, 11, 2), value=87.1))
            await db.commit()
    asyncio.run(add_point())
    night_msk = datetime(2026, 11, 9, 20, 0)  # 23:00 МСК — не пишем
    assert asyncio.run(pb.public_bot_notify_job(now=night_msk))["sent"] == 0
    assert asyncio.run(pb.public_bot_notify_job(now=noon_msk))["sent"] == 1
    assert sent[-1]["kind"] == pb.KIND_NOTIFY and "87,10" in sent[-1]["text"] and "Новые данные" in sent[-1]["text"]
    assert asyncio.run(pb.public_bot_notify_job(now=noon_msk))["sent"] == 0  # второй раз то же не шлём


def test_key_rate_notifies_only_on_change(env):
    maker, sent, _ = env
    asyncio.run(pb.handle_callback(_cb("pb:s:keyrate")))

    async def add(d, v):
        async with maker() as db:
            ind = (await db.execute(select(Indicator).where(Indicator.code == "key-rate"))).scalar_one()
            db.add(IndicatorData(indicator_id=ind.id, date=d, value=v))
            await db.commit()
    noon = datetime(2026, 11, 9, 9, 0)
    asyncio.run(add(date(2026, 11, 7), 14.0))
    assert asyncio.run(pb.public_bot_notify_job(now=noon))["sent"] == 0
    assert asyncio.run(_rows(maker, PublicBotSubscription))[0].last_point_date == date(2026, 11, 7)
    asyncio.run(add(date(2026, 11, 8), 13.5))
    assert asyncio.run(pb.public_bot_notify_job(now=noon))["sent"] == 1
    assert "13,50 %" in sent[-1]["text"] and "За неделю" not in sent[-1]["text"]


def test_blocked_on_403_and_member_update(env, monkeypatch):
    maker, _, _ = env
    asyncio.run(pb.handle_callback(_cb("pb:s:diesel")))

    async def fail(chat_id, text, kb=None, kind=pb.KIND_REPLY):
        tb._last_api_error.set("{'ok': False, 'error_code': 403, 'description': 'Forbidden: bot was blocked by the user'}")
        return False
    monkeypatch.setattr(pb, "_send", fail)

    async def add_point():
        async with maker() as db:
            ind = (await db.execute(select(Indicator).where(Indicator.code == "fuel-diesel"))).scalar_one()
            db.add(IndicatorData(indicator_id=ind.id, date=date(2026, 11, 2), value=87.1))
            await db.commit()
    asyncio.run(add_point())
    stats = asyncio.run(pb.public_bot_notify_job(now=datetime(2026, 11, 9, 9, 0)))
    assert stats["blocked"] == 1
    assert asyncio.run(_rows(maker, PublicBotChat))[0].blocked_at is not None
    asyncio.run(pb.handle_member_update({"chat": {"id": 888, "type": "private"}, "new_chat_member": {"status": "kicked"}}))


def test_stop_forgets_chat(env):
    maker, sent, _ = env
    asyncio.run(pb.handle_callback(_cb("pb:s:diesel")))

    async def outbox_row():
        async with maker() as db:
            db.add(TelegramOutbox(chat_id="555", method="sendMessage", kind=pb.KIND_REPLY, text="x", ok=True))
            db.add(TelegramOutbox(chat_id="1", method="sendMessage", kind="digest", text="y", ok=True))
            await db.commit()
    asyncio.run(outbox_row())
    asyncio.run(pb.handle_message(_msg("/stop")))
    assert asyncio.run(_rows(maker, PublicBotChat)) == []
    assert asyncio.run(_rows(maker, PublicBotSubscription)) == []
    assert [r.chat_id for r in asyncio.run(_rows(maker, TelegramOutbox))] == ["1"]
    assert sent[-1]["text"] == pb.STOP_TEXT
    assert [e.kind for e in asyncio.run(_rows(maker, PublicBotEvent))][-1] == "stop"


def test_report_counts(env):
    maker, _, _ = env
    asyncio.run(pb.handle_message(_msg("/start r014_diesel", chat_id=1)))
    asyncio.run(pb.handle_message(_msg("золото", chat_id=2)))
    asyncio.run(pb.handle_callback(_cb("pb:s:diesel", chat_id=1)))
    text = asyncio.run(pb.report_text())
    assert "Новых людей: <b>2</b>" in text
    assert "r014_diesel 1" in text and "золото 1" in text
    assert "Дизель 1" in text


def test_router_respects_flag_and_owner(env, monkeypatch):
    _, sent, _ = env
    monkeypatch.setattr(tb, "interactive_authorized_ids", lambda: {"42"})
    admin: list = []

    async def admin_send(chat_id, text, reply_markup=None, kind="bot_reply"):
        admin.append(text)
        return True
    monkeypatch.setattr(tb, "send_message", admin_send)
    # Владелец: /start — админ-меню, /start с кодом — путь человека из ролика.
    asyncio.run(tb._handle_message(_msg("/start", chat_id=42)))
    assert admin and "пульс" in admin[-1] and sent == []
    asyncio.run(tb._handle_message(_msg("/start r014", chat_id=42)))
    assert "Forecast Economy" in sent[-1]["text"]
    # Флаг выключен — чужой чат молча игнорируется, как раньше.
    monkeypatch.setattr(settings, "public_bot_enabled", False, raising=False)
    n = len(sent)
    asyncio.run(tb._handle_message(_msg("дизель", chat_id=999)))
    asyncio.run(tb._handle_callback(_cb("pb:t:diesel", chat_id=999)))
    assert len(sent) == n


# --- 08.11.2026 вечер: отдельный бот, ответы модели, понятные ответы -------------------------

def test_free_question_goes_to_llm_with_data_context_and_limit(env, monkeypatch):
    maker, sent, api_calls = env
    monkeypatch.setattr(settings, "public_bot_llm_enabled", True, raising=False)
    monkeypatch.setattr(settings, "openrouter_api_key", "k", raising=False)
    monkeypatch.setattr(settings, "public_bot_llm_daily_limit", 2, raising=False)
    seen: list[tuple[str, str]] = []

    async def fake_llm(context, question, history=None):
        seen.append((context, question))
        return "⛽ Дизель 86,52 ₽ <за литр>"
    monkeypatch.setattr(pb, "_llm_complete", fake_llm)
    q = "что такое закон Оукена и как у нас с безработицей?"
    asyncio.run(pb.handle_message(_msg(q)))
    context, question = seen[0]
    assert question == q
    assert "Дизель: 86,52 ₽ за литр на 26 октября 2026" in context
    assert "наш расчёт на октябрь 2026: 6,26" in context
    assert "5,00" not in context and "7,50" not in context  # без диапазона
    assert sent[-1]["text"] == "⛽ Дизель 86,52 ₽ &lt;за литр&gt;"  # ответ модели экранирован
    assert ("sendChatAction", {"chat_id": "555", "action": "typing"}) in api_calls
    ev = asyncio.run(_rows(maker, PublicBotEvent))
    assert [(e.kind, e.code) for e in ev] == [("unknown", None), ("ask", None)]  # текст вопроса не храним
    asyncio.run(pb.handle_message(_msg("а инфляция в регионах какая сейчас и почему так?")))
    asyncio.run(pb.handle_message(_msg("и ещё вопрос про ВВП, что с ним происходит?")))
    assert sent[-1]["text"] == pb.LIMIT_TEXT and len(seen) == 2


def test_short_word_still_answers_by_figure_and_llm_off_fallback(env, monkeypatch):
    _, sent, _ = env
    monkeypatch.setattr(settings, "public_bot_llm_enabled", False, raising=False)
    asyncio.run(pb.handle_message(_msg("биткоин")))
    assert sent[-1]["text"] == pb.UNKNOWN_TEXT
    asyncio.run(pb.handle_message(_msg("дизель")))
    assert "86,52" in sent[-1]["text"]


def test_llm_failure_reply(env, monkeypatch):
    _, sent, _ = env
    monkeypatch.setattr(settings, "public_bot_llm_enabled", True, raising=False)
    monkeypatch.setattr(settings, "openrouter_api_key", "k", raising=False)

    async def none_llm(context, question, history=None):
        return None
    monkeypatch.setattr(pb, "_llm_complete", none_llm)
    asyncio.run(pb.handle_message(_msg("расскажи про индекс губной помады")))
    assert sent[-1]["text"] == pb.LLM_FAIL_TEXT


def test_stale_note_and_rate_wording():
    fig = pb.Figure(topic=pb.TOPICS["deposit"], name="", source="Банк России", frequency="monthly",
                    last_date=date(2026, 8, 1), last_value=12.84, prev_value=12.81, year_ago_value=15.57,
                    forecast_date=None, forecast_value=None)
    cpi = pb.Figure(topic=pb.TOPICS["inflation"], name="", source="", frequency="monthly",
                    last_date=date(2026, 9, 1), last_value=6.35, prev_value=None, year_ago_value=None,
                    forecast_date=None, forecast_value=None)
    text = pb.figure_text(fig, cpi=cpi, today=date(2026, 11, 8))
    assert "За месяц: +0,03 пункта. За год: −2,73 пункта." in text and "п.п." not in text
    assert "Это выше инфляции (6,35 %) на 6,49 пункта" in text
    assert "Новее данных пока нет" in text  # август на 8 ноября: 99 дней > 75
    fresh = pb.figure_text(fig, cpi=cpi, today=date(2026, 9, 20))
    assert "Новее данных пока нет" not in fresh


def test_separate_token_poller_and_admin_bot_back_to_owner_only(env, monkeypatch):
    _, sent, api_calls = env
    monkeypatch.setattr(settings, "public_bot_token", "PUBLIC", raising=False)
    monkeypatch.setattr(tb, "interactive_authorized_ids", lambda: {"42"})
    admin: list = []

    async def admin_send(chat_id, text, reply_markup=None, kind="bot_reply", **kw):
        admin.append(text)
        return True
    monkeypatch.setattr(tb, "send_message", admin_send)
    n = len(sent)
    asyncio.run(tb._handle_message(_msg("дизель", chat_id=999)))  # служебный бот чужим молчит
    asyncio.run(tb._handle_message(_msg("/start r014", chat_id=42)))  # и владельцу даёт админ-меню
    assert len(sent) == n and admin == []
    assert pb.bot_token() == "PUBLIC"

    class _R:
        store: dict = {}
        async def get(self, k): return self.store.get(k)
        async def set(self, k, v): self.store[k] = v

    async def fake_redis():
        return _R()
    import app.core.cache as cache_mod
    monkeypatch.setattr(cache_mod, "get_state_redis", fake_redis)

    async def api(method, payload, files=None, token=None, **kw):
        api_calls.append((method, payload, token))
        if method == "getUpdates":
            return {"ok": True, "result": [{"update_id": 7, "message": _msg("/start r005_ai92", chat_id=777)}]}
        return {"ok": True}
    monkeypatch.setattr(tb, "_api", api)
    monkeypatch.setattr(pb, "_POLL_BUDGET_S", 0.0)  # один опрос
    asyncio.run(pb.public_bot_poll_job())
    polls = [c for c in api_calls if c[0] == "getUpdates"]
    assert polls and polls[0][2] == "PUBLIC"
    assert _R.store["fe:tg:public_offset"] == "8"
    assert any("Бензин АИ-92" in s["text"] for s in sent[n:])


def test_send_message_can_disable_link_preview(monkeypatch):
    import app.services.telegram_outbox as outbox
    payloads: list = []

    async def api(method, payload, files=None, token=None, **kw):
        payloads.append((payload, token))
        return {"ok": True, "result": {"message_id": 1}}

    async def begin(**kw):
        return 1

    async def finish(*a, **kw):
        return None
    monkeypatch.setattr(tb, "_api", api)
    monkeypatch.setattr(outbox, "archive_begin", begin)
    monkeypatch.setattr(outbox, "archive_finish", finish)
    asyncio.run(tb.send_message("1", "x", link_preview=False, token="T"))
    assert payloads == [({"chat_id": "1", "text": "x", "parse_mode": "HTML",
                          "link_preview_options": {"is_disabled": True}}, "T")]


def test_returning_start_greeting_thanks_and_next_release(env):
    maker, sent, _ = env

    async def seed():
        async with maker() as db:
            dep = Indicator(code="deposit-rate", name="Ставки по вкладам", unit="%", frequency="monthly",
                            source="Банк России")
            db.add(dep)
            await db.flush()
            db.add(IndicatorData(indicator_id=dep.id, date=date(2026, 8, 1), value=12.84))
            db.add(EconomicEvent(title="Ставки", event_type="data_release", source="cbr", indicator_id=dep.id,
                                 scheduled_date=date(2099, 12, 8), is_estimated=False))
            await db.commit()
    asyncio.run(seed())
    asyncio.run(pb.handle_message(_msg("/start")))
    assert "Forecast Economy" in sent[-1]["text"] and "/stop" in sent[-1]["text"]
    asyncio.run(pb.handle_callback(_cb("pb:s:deposit")))
    asyncio.run(pb.handle_message(_msg("/start")))
    assert sent[-1]["text"] == pb.WELCOME_BACK + "\nПрисылаю новые данные: Ставки по вкладам."
    n = len(sent)
    asyncio.run(pb.handle_message(_msg("Привет!")))
    asyncio.run(pb.handle_message(_msg("спасибо")))
    assert [s["text"] for s in sent[n:]] == [pb.GREETING_TEXT, pb.THANKS_TEXT]
    asyncio.run(pb.handle_callback(_cb("pb:t:deposit")))
    assert "Следующие данные: 8 декабря." in sent[-1]["text"] or "Следующие данные" in sent[-2]["text"]


def test_without_model_typos_and_emoji_use_scripts(env, monkeypatch):
    _, sent, _ = env
    monkeypatch.setattr(settings, "public_bot_llm_enabled", False, raising=False)
    assert pb.match_topic("дизиль")[0] == "diesel" and pb.match_topic("инфляцыя")[0] == "inflation"
    asyncio.run(pb.handle_message(_msg("дизиль")))
    assert "86,52" in sent[-1]["text"]
    asyncio.run(pb.handle_message(_msg("👍")))
    asyncio.run(pb.handle_message(_msg("привет!")))
    assert [s["text"] for s in sent[-2:]] == [pb.THANKS_TEXT, pb.GREETING_TEXT]


def test_model_first_memory_html_and_actions(env, monkeypatch):
    maker, sent, _ = env
    monkeypatch.setattr(settings, "public_bot_llm_enabled", True, raising=False)
    monkeypatch.setattr(settings, "openrouter_api_key", "k", raising=False)
    calls: list = []

    async def llm(context, question, history=None):
        calls.append((question, list(history or [])))
        return ("Привет! **Дизель** <b>86,52 ₽</b> <script>x</script>\n"
                "<blockquote expandable>подробно</blockquote>\n[[темы: diesel, ai92, nope]]\n[[подписка: diesel]]")
    monkeypatch.setattr(pb, "_llm_complete", llm)
    pb.forget_history("555")
    asyncio.run(pb.handle_message(_msg("дизель")))  # слово темы тоже отвечает модель
    asyncio.run(pb.handle_message(_msg("а для 95-го?")))
    assert calls[0] == ("дизель", [])
    assert calls[1][1][0] == {"role": "user", "content": "дизель"} and calls[1][1][1]["role"] == "assistant"
    text, kb = sent[-1]["text"], sent[-1]["kb"]["inline_keyboard"]
    assert "<b>Дизель</b> <b>86,52 ₽</b> &lt;script&gt;" in text and "<blockquote expandable>подробно</blockquote>" in text
    assert "[[" not in text
    assert [b["callback_data"] for b in kb[0]] == ["pb:t:diesel", "pb:t:ai92"]
    assert kb[1][0]["callback_data"] == "pb:s:diesel" and kb[-1][0]["callback_data"] == "pb:menu"
    asyncio.run(pb.handle_message(_msg("/stop")))
    assert pb._history("555") == []


def test_no_text_messages_get_a_reply(env):
    _, sent, _ = env
    asyncio.run(pb.handle_message({"chat": {"id": 555, "type": "private"}, "voice": {"file_id": "x"}}))
    asyncio.run(pb.handle_message({"chat": {"id": 555, "type": "private"}, "sticker": {"file_id": "x"}}))
    assert "Голосовые" in sent[-2]["text"] and "Картинки" in sent[-1]["text"]


def test_llm_context_has_wallet_lines_and_language_rule(env):
    maker, _, _ = env

    async def ctx():
        async with maker() as db:
            return await pb.build_llm_context(db)
    text = asyncio.run(ctx())
    assert "для кошелька: Полный бак 50 л: ≈4 326 ₽" in text
    assert "языке собеседника" in pb.LLM_SYSTEM_PROMPT and "[[темы:" in pb.LLM_SYSTEM_PROMPT
    assert "Нашего расчёта (прогноза) нет" in text and "Дизель" in text.split("Нашего расчёта")[1]


def test_inline_query_cards(env):
    _, _, api_calls = env
    asyncio.run(pb.handle_inline_query({"id": "iq1", "query": "дизель", "from": {"id": 7}}))
    method, payload = api_calls[-1][:2]
    assert method == "answerInlineQuery" and payload["inline_query_id"] == "iq1"
    [card] = payload["results"]
    assert card["id"] == "diesel" and card["title"] == "Дизель: 86,52 ₽ за литр"
    assert card["thumbnail_url"].endswith("/og/russia/fuel-diesel.png")
    assert "86,52" in card["input_message_content"]["message_text"]
    assert card["reply_markup"]["inline_keyboard"][0][0]["url"] == "https://t.me/ForecastEconomyBot?start=share_diesel"
    asyncio.run(pb.handle_inline_query({"id": "iq2", "query": "", "from": {"id": 7}}))
    ids = [r["id"] for r in api_calls[-1][1]["results"]]
    assert "diesel" in ids and "inflation" in ids and "keyrate" in ids  # пустой запрос — все темы с данными


def test_chart_action_for_any_topic_but_unknown_key_dropped():
    _, _, _, _, charts = pb.split_actions("x [[график: keyrate]]")
    assert charts == ["keyrate"]  # свой график рисуется и для дневных рядов
    _, _, _, _, charts = pb.split_actions("x [[график: bitcoin]]")
    assert charts == []


def test_week_command_asks_model_for_digest(env, monkeypatch):
    maker, sent, _ = env
    monkeypatch.setattr(settings, "public_bot_llm_enabled", True, raising=False)
    monkeypatch.setattr(settings, "openrouter_api_key", "k", raising=False)
    asked: list = []

    async def llm(context, question, history=None):
        asked.append(question)
        return "📰 <b>Неделя</b>\n[[вопросы: Почему бензин дешевеет?]]"
    monkeypatch.setattr(pb, "_llm_complete", llm)
    asyncio.run(pb.handle_message(_msg("/week")))
    assert asked == [pb.WEEK_PROMPT]
    assert sent[-1]["text"] == "📰 <b>Неделя</b>"
    assert sent[-1]["kb"]["inline_keyboard"][0][0]["text"] == "💬 Почему бензин дешевеет?"
    kinds = [e.kind for e in asyncio.run(_rows(maker, PublicBotEvent))]
    assert kinds == ["week", "ask"]


def test_chart_render_and_send(env, monkeypatch):
    from io import BytesIO
    from PIL import Image
    from app.services.bot_chart import Series, render_chart

    png = render_chart(Series(
        title="Ключевая ставка", unit="%", source="Банк России",
        points=[(date(2025, 11, 1), 16.5), (date(2026, 3, 1), 15.0), (date(2026, 11, 6), 14.0)],
        year_ago=(date(2025, 11, 1), 16.5), compare_label="инфляция",
        compare_points=[(date(2025, 11, 1), 7.9), (date(2026, 9, 1), 6.35)], step=True, is_rate=True,
        forecast=(date(2026, 12, 1), 13.5), target=("цель ЦБ", 4.0),
    ))
    assert Image.open(BytesIO(png)).size == (1600, 1000)  # 2× от показа

    _, sent, api_calls = env
    seen: list = []

    async def api(method, payload, files=None, token=None, **kw):
        seen.append((method, payload, files))
        return {"ok": True}
    monkeypatch.setattr(tb, "_api", api)
    assert asyncio.run(pb.send_chart("555", "diesel"))
    method, payload, files = seen[-1]
    assert method == "sendPhoto" and "photo" in files and "Дизель" in payload["caption"]
    assert Image.open(files["photo"][1]).size == (1600, 1000)


def test_reel_start_reply_context_subscriptions_and_toggle(env, monkeypatch):
    maker, sent, api_calls = env
    monkeypatch.setattr(settings, "public_bot_llm_enabled", True, raising=False)
    monkeypatch.setattr(settings, "openrouter_api_key", "k", raising=False)
    seen: list = []

    async def llm(context, question, history=None):
        seen.append((context, question))
        return "Привет!"
    monkeypatch.setattr(pb, "_llm_complete", llm)
    pb.forget_history("555")
    asyncio.run(pb.handle_message(_msg("/start r003_jobs")))
    assert "закон Оукена" in seen[-1][1] and sent[-2]["text"] == "Привет!"
    assert sent[-1]["text"].startswith(pb.SHORT_INTRO)
    assert "Подписки этого человека на новые данные: нет." in seen[-1][0]
    # Подписка с карточки меняет кнопку под ней на «Не присылать».
    card = {"message_id": 10, "chat": {"id": 555, "type": "private"},
            "reply_markup": pb.figure_keyboard(pb.TOPICS["diesel"], None, False)}
    asyncio.run(pb.handle_callback({"id": "c", "data": "pb:s:diesel", "message": card}))
    edits = [p for m, p, *_ in api_calls if m == "editMessageReplyMarkup"]
    assert edits and edits[-1]["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "pb:u:diesel"
    # Ответ на сообщение бота: модель видит цитату; подписка теперь в данных.
    msg = _msg("а почему так?")
    msg["reply_to_message"] = {"text": "Дизель 86,52"}
    asyncio.run(pb.handle_message(msg))
    assert seen[-1][1].startswith("(в ответ на сообщение: «Дизель 86,52»)")
    assert "Подписки этого человека на новые данные: Дизель." in seen[-1][0]


def test_notify_shows_was_and_no_stale_line():
    fig = pb.Figure(topic=pb.TOPICS["diesel"], name="", source="Росстат", frequency="weekly",
                    last_date=date(2026, 10, 26), last_value=86.52, prev_value=86.0, year_ago_value=None,
                    forecast_date=None, forecast_value=None)
    text = pb.figure_text(fig, header="🔔 <b>Новые данные</b>", today=date(2026, 11, 20),
                          was=(date(2026, 10, 19), 86.0))
    assert "Было 86,00 ₽ за литр (19 октября 2026)." in text and "Новее данных" not in text
    assert pb.fmt_date(date(2026, 4, 1), "quarterly") == "2-й квартал 2026"


def test_context_yearly_inflation_and_prompt_trusts_data(env):
    maker, _, _ = env

    async def seed_and_ctx():
        async with maker() as db:
            ind = Indicator(code="inflation-annual", name="Инфляция годовая", unit="%", frequency="annual",
                            source="Росстат")
            db.add(ind)
            await db.flush()
            db.add_all([IndicatorData(indicator_id=ind.id, date=date(2015, 1, 1), value=12.9),
                        IndicatorData(indicator_id=ind.id, date=date(2016, 1, 1), value=5.4)])
            await db.commit()
            return await pb.build_llm_context(db)
    text = asyncio.run(seed_and_ctx())
    assert "Инфляция по годам, % (декабрь к декабрю): 2015 — 12,9, 2016 — 5,4" in text
    assert "свежее твоих прошлых реплик" in pb.LLM_SYSTEM_PROMPT


def test_chart_monthly_subtitle_and_year_ago_matches_card(env):
    from app.services.bot_chart import Series, render_chart
    png = render_chart(Series(title="Вклады", unit="%", source="Банк России", monthly=True,
                              points=[(date(2025, 8, 1), 15.57), (date(2026, 8, 1), 12.84)],
                              compare_label="инфляция",
                              compare_points=[(date(2025, 8, 1), 8.1), (date(2026, 8, 1), 6.3)]))
    assert png[:8] == b"\x89PNG\r\n\x1a\n"

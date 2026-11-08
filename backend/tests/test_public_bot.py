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
    Forecast, ForecastValue, Indicator, IndicatorData,
    PublicBotChat, PublicBotEvent, PublicBotSubscription, TelegramOutbox,
)

_TABLES = (Indicator, IndicatorData, Forecast, ForecastValue,
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

    async def fake_api(method, payload, files=None):
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
    assert chats[0].asked_source_at is not None
    events = asyncio.run(_rows(maker, PublicBotEvent))
    assert [(e.kind, e.code, e.topic) for e in events] == [("start", "r014_diesel", "diesel")]
    assert all(e.chat_hash != "555" and len(e.chat_hash) == 64 for e in events)
    texts = [s["text"] for s in sent]
    assert "Forecast Economy" in texts[0] and "/stop" in texts[0]
    assert "<b>86,52 ₽ за литр</b> — 26 октября 2026" in texts[1]
    assert "За неделю: +0,6 %" in texts[1] and "За год: +12,4 %" in texts[1]
    assert texts[2] == pb.SOURCE_QUESTION
    url = sent[1]["kb"]["inline_keyboard"][1][0]["url"]
    assert url.startswith("https://forecasteconomy.com/russia/indicator/fuel-diesel?")
    assert "utm_source=telegram" in url and "utm_campaign=diesel" in url and "utm_content=r014_diesel" in url


def test_word_answer_and_source_asked_once(env):
    maker, sent, _ = env
    asyncio.run(pb.handle_message(_msg("Инфляция")))
    asyncio.run(pb.handle_message(_msg("дизель")))
    texts = [s["text"] for s in sent]
    assert texts.count(pb.SOURCE_QUESTION) == 1
    cpi = texts[0]
    assert "<b>6,35 % за год</b> — сентябрь 2026" in cpi
    # Прогноз — одной точкой, без диапазона (правило владельца).
    assert "Наш прогноз на октябрь 2026: 6,26 % за год" in cpi and "5,00" not in cpi and "7,50" not in cpi
    chat = asyncio.run(_rows(maker, PublicBotChat))[0]
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

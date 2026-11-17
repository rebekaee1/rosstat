"""Автор Telegram-канала (ADR-0035): сводка, сторож чисел, запуск модели, утверждение владельцем, публикация, счётчик."""
import asyncio
import importlib.util
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.database as dbm
import app.services.channel_author as ca
import app.services.channel_facts as cf
import app.services.channel_posts as cp
import app.services.channel_stats as cs
import app.services.channel_voice as cv
import app.services.public_bot as pb
import app.services.telegram_bot as tb
from app.config import settings
from app.models import (
    Base, ChannelAuthorRun, ChannelPost, ChannelPostView, ChannelStatsDaily, ChannelVoiceRule, EconomicEvent, Forecast,
    ForecastValue,
    Indicator, IndicatorData, TelegramOutbox,
)

ROOT = Path(__file__).resolve().parents[1]
MSK = cf.MSK
_TABLES = (Indicator, IndicatorData, Forecast, ForecastValue, EconomicEvent, TelegramOutbox,
           ChannelPost, ChannelAuthorRun, ChannelStatsDaily, ChannelPostView, ChannelVoiceRule)


# ---------------------------------------------------------------------------
# Числа, скачки, серии
# ---------------------------------------------------------------------------

def test_fmt_num_rounds_half_up_like_the_guard():
    # 62,25 ₽ × 50 л = 3 112,5: обычное форматирование Python дало бы 3 112, сторож ждёт 3 113.
    assert cf.fmt_num(3112.5, 0) == "3 113"
    assert cf.fmt_num(86.63) == "86,63"
    assert cf.fmt_num(-0.25, 1) == "−0,3"
    assert cf.fmt_num(1234567.891) == "1 234 567,89"
    # (74,72 − 70,01) × 50 в двоичной арифметике — 235,49999999999997; человек видит 235,5 и округляет до 236.
    assert cf.fmt_num((74.72 - 70.01) * 50, 0) == "236"
    c = cf.Corpus()
    c.n(74.72, "АИ-92 · 5 октября", series="fuel-ai92")
    c.n(70.01, "АИ-92 · 9 ноября", series="fuel-ai92")
    audit = cf.check_post("АИ-92 — 70,01 ₽, было 74,72 ₽. Бак дешевле на 236 ₽.", c,
                          [{"shown": "236", "basis": "calc", "expr": "(74.72-70.01)*50"}])
    assert not audit.blocked and {n["shown"]: n["status"] for n in audit.numbers}["236"] == "calc"


def test_jump_and_streak():
    base = [(date(2026, 1, 1) + timedelta(days=i), 100 + (i % 2) * 0.5) for i in range(40)]
    assert cf.detect_jump(base, is_rate=False) is None
    jumped = base + [(date(2026, 3, 1), 95.0)]
    assert cf.detect_jump(jumped, is_rate=False) >= 4
    # У ставок мелкий шаг скачком не считается, даже если он больше обычного.
    rates = [(date(2026, 1, 1) + timedelta(days=30 * i), 10 + (i % 2) * 0.01) for i in range(30)]
    assert cf.detect_jump(rates + [(date(2028, 7, 1), 10.2)], is_rate=True) is None
    assert cf.detect_jump(rates + [(date(2028, 7, 1), 8.6)], is_rate=True) is not None
    up = [(date(2026, 1, i + 1), v) for i, v in enumerate([5, 4, 5, 6, 7])]
    assert cf.streak_of(up) == 3
    assert cf.streak_of([(date(2026, 1, 1), 2.0), (date(2026, 1, 2), 2.0)]) == 0


def test_window_jump_catches_slow_slide():
    # Нефть: дневные шаги обычные (около 1 %), но за месяц набежало −29 % — это тоже повод перепроверить.
    pts, v = [], 100.0
    for i in range(300):
        v *= 1.01 if i % 2 else 0.99
        pts.append((date(2025, 1, 1) + timedelta(days=i), v))
    assert cf.detect_window_jumps(pts) == []
    for i in range(21):
        v *= 0.984
        pts.append((date(2025, 10, 28) + timedelta(days=i), v))
    assert cf.detect_jump(pts, is_rate=False) is None           # последний дневной шаг не выделяется
    words = [w for w, _ in cf.detect_window_jumps(pts)]
    assert "за месяц" in words


def test_extract_numbers_kinds():
    text = "АИ-95 — 76,29 ₽, 9 ноября 2026 года в 10:00, бак 4 332 ₽, 5 недель, зарплата 103 тыс. ₽, 95-го, 14 %"
    kinds = {t.raw: t.kind for t in cf.extract_numbers(text)}
    assert kinds["76,29"] == "number" and kinds["4 332"] == "number" and kinds["14"] == "number"
    assert kinds["9"] == "date" and kinds["2026"] == "year"
    assert kinds["5"] == "small"
    assert kinds["10"] == "skip" and kinds["00"] == "skip"
    assert [t for t in cf.extract_numbers(text) if t.raw == "95"][0].kind == "skip"   # марка бензина
    scaled = [t for t in cf.extract_numbers(text) if t.raw == "103"][0]
    assert scaled.scale == 1000


def _corpus() -> cf.Corpus:
    c = cf.Corpus()
    c.n(86.63, "Дизель · 9 ноября 2026 · Росстат", source="Росстат", series="fuel-diesel")
    c.n(0.29, "Дизель · изменение", 1, source="Росстат", kind="derived", series="fuel-diesel")
    c.n(86.63 * 50, "Дизель · бак 50 л", 0, source="Росстат", kind="derived", series="fuel-diesel")
    c.n(12.54, "Юань · 15 октября 2026 · Банк России", source="Банк России", series="cny-rub")
    c.n(6.26, "Инфляция · наш расчёт на октябрь 2026", source="расчёт Forecast Economy", kind="forecast", series="cpi-yoy")
    c.n(10222.10, "Золото · 14 ноября 2026 · Банк России", source="Банк России", series="gold-price", jump=True)
    c.d(date(2026, 11, 9))
    return c


def test_guard_accepts_data_calc_and_assumption():
    audit = cf.check_post(
        "<b>Дизель — 86,63 ₽ за литр</b>\nЗа неделю +0,3 %. Бак на 50 литров — 4 332 ₽, два бака — 8 663 ₽. Цены на 9 ноября.",
        _corpus(), [{"shown": "50", "basis": "assumption", "note": "бак"},
                    {"shown": "8 663", "basis": "calc", "expr": "86.63*50*2"}])
    assert not audit.blocked, audit.issues
    status = {n["shown"]: n["status"] for n in audit.numbers}
    assert status == {"86,63": "data", "0,3": "derived", "50": "assumption", "4 332": "derived", "8 663": "calc",
                      "9 ноября": "date"}
    assert audit.sources == ["Росстат"]          # источник собран из оснований, а не со слов модели


def test_guard_reads_scaled_units_both_ways():
    # Резервы в базе уже в миллиардах: «724,30 млрд $» — это 724,30, а не 724,30 × 10⁹ (показ 17.11.2026).
    c = cf.Corpus()
    c.add_text("Международные резервы, млрд $. последнее 724,30 на 2026-11-06; максимум 826,80 на 2026-01-30", "база сайта: get_series")
    c.n(103014, "Средняя зарплата · август 2026 · Росстат", 0, source="Росстат", series="wages-nominal")
    audit = cf.check_post("Резервы — 724,30 млрд $, на 102,50 млрд меньше максимума. Около 724 млрд. Зарплата — 103 014 ₽, то есть 103 тыс. ₽.",
                          c, [{"shown": "102,50", "basis": "calc", "expr": "826.80-724.30"}])
    assert not audit.blocked, audit.issues


def test_guard_blocks_unknown_number_and_wrong_calc():
    audit = cf.check_post("Дизель — 86,63 ₽, год назад 71,20 ₽. Бак — 5 000 ₽.", _corpus(),
                          [{"shown": "5 000", "basis": "calc", "expr": "86.63*50"}])
    assert audit.blocked
    assert any("71,20" in i for i in audit.issues) and any("5 000" in i for i in audit.issues)


def test_guard_does_not_match_unrelated_series_by_rounding():
    # «12,5» случайно совпадает с юанем 12,54 после округления; о юане в посте ни слова — число не засчитывается.
    audit = cf.check_post("Дизель — 86,63 ₽. За год +12,5 %.", _corpus())
    assert audit.blocked and any("12,5" in i for i in audit.issues)
    # Если юань в посте назван точно, округление его же числа допустимо.
    ok = cf.check_post("Юань — 12,54 ₽, то есть около 12,5 ₽.", _corpus())
    assert not ok.blocked, ok.issues


def test_guard_forecast_needs_our_calc_words_and_no_range():
    c = _corpus()
    assert cf.check_post("В октябре инфляция будет 6,26 %.", c).blocked
    assert not cf.check_post("Наш расчёт на октябрь: 6,26 %.", c).blocked
    ranged = cf.check_post("Наш расчёт: инфляция будет от 6,0 до 6,5 %.", c)
    assert any("диапазон" in i for i in ranged.issues)


def test_guard_jump_number_needs_web_check():
    c = _corpus()
    text = "Золото — 10 222,10 ₽ за грамм."
    assert cf.check_post(text, c).blocked
    audit = cf.check_post(text, c, checks=[{"what": "цена золота", "where": "cbr.ru", "result": "совпадает"}], web_searches=1)
    assert not audit.blocked and audit.warnings


def test_guard_web_number_needs_snippet():
    c = _corpus()
    c.add_web("https://cbr.ru/hd_base/metall/", "Учётные цены", "золото - 10322,01 руб./грамм с 17 ноября")
    decl = [{"shown": "10 322,01", "basis": "web", "url": "https://cbr.ru/hd_base/metall/"}]
    assert not cf.check_post("По данным Банка России, золото — 10 322,01 ₽.", c, decl).blocked
    # Без объявления число из выдержки поиска не проходит; число, которого нет в выдержке, — тоже.
    assert cf.check_post("Золото — 10 322,01 ₽.", c).blocked
    assert cf.check_post("Золото — 10 400,00 ₽.", c, [{"shown": "10 400,00", "basis": "web", "url": "https://cbr.ru/x"}]).blocked


def test_guard_blocks_words_from_never_list():
    # Без словаря действует встроенный список жаргона; со словарём — он (файл + ответы владельца).
    assert any("г/г" in i for i in cf.check_post("Дизель — 86,63 ₽, +0,3 % г/г.", _corpus()).issues)
    audit = cf.check_post("Занятно, что дизель — 86,63 ₽.", _corpus(), banned=["занятно, что", "обвал"])
    assert audit.blocked and "«занятно, что»" in audit.issues[0]
    assert not cf.check_post("Дизель — 86,63 ₽.", _corpus(), banned=["занятно, что"]).blocked
    # Целое слово: «шок» не срабатывает на «шоколад», е/ё не различаются.
    assert cv.find_banned("Шоколад подорожал, всё просто", ["шок"]) == []
    assert cv.find_banned("Курс взлетел. Ещё раз", ["взлетел", "еще раз"]) == ["взлетел", "еще раз"]


def test_calc_declared_for_plain_rounding_still_passes():
    # Модель объявила расчётом простое округление числа из сводки: «10 222» из 10 222,10.
    c = _corpus()
    audit = cf.check_post("Золото — 10 222,10 ₽, то есть 10 222 ₽ за грамм.", c,
                          [{"shown": "10 222", "basis": "calc", "expr": "round(10222.10,0)"}],
                          checks=[{"what": "золото", "where": "cbr.ru", "result": "совпадает"}], web_searches=1)
    assert not audit.blocked, audit.issues
    assert cf.eval_expr("round(10222.10,0)")[0] == 10222.0 and cf.eval_expr("86,63*50")[0] == 4331.5


# ---------------------------------------------------------------------------
# Текст поста, ссылки, время выхода
# ---------------------------------------------------------------------------

def test_channel_url_has_channel_utm():
    url = ca.channel_url("fuel-diesel", "fuel", datetime(2026, 11, 17, 10, 0, tzinfo=MSK))
    assert url.startswith("https://ru.") and "/russia/indicator/fuel-diesel?" in url
    assert "utm_source=telegram" in url and "utm_medium=channel" in url
    assert "utm_campaign=fuel" in url and "utm_content=20261117" in url
    assert "/currencies/indicator/usd-rub?" in ca.channel_url("usd-rub", "week")
    assert "/research/bank-license-revoked?" in ca.channel_url("research:bank-license-revoked", "research")
    assert re.search(r"forecasteconomy\.com/\?utm_", ca.channel_url("../../etc", "noticed"))   # мусор → главная


def test_clean_body_and_compose():
    body = ca.clean_body('<b>Заголовок</b>\n\nТекст со <a href="https://evil.example/x">ссылкой</a> и <script>x</script>.\n'
                         '<i>Источник: выдумано</i>')
    assert "<b>Заголовок</b>" in body and "evil.example" not in body and "<script>" not in body
    assert "Источник" not in body
    full = ca.compose_post(body, ["Росстат", "Банк России"], "https://ru.forecasteconomy.com/x?utm_medium=channel", "График")
    assert full.endswith('Росстат, Банк России · <a href="https://ru.forecasteconomy.com/x?utm_medium=channel">График</a>')


def test_system_prompt_is_structured_and_tone_switches():
    for tone in ca.TONES:
        prompt = ca.system_prompt(tone)
        for tag in ("reader", "promise", "voice", "character", "truth", "tools", "rubrics", "format", "process",
                    "examples", "words", "tone"):
            assert f"<{tag}>" in prompt and f"</{tag}>" in prompt
        assert ca.TONE_NOTES[tone] in prompt
    # Правила владельца названы и объяснены, а не выкрикнуты заглавными буквами.
    prompt = ca.system_prompt()
    assert "наш расчёт" in prompt and "Диапазонов" in prompt and "не советуй" in prompt
    assert "НИКОГДА" not in prompt and "ОБЯЗАТЕЛЬНО" not in prompt
    assert all(r in prompt for r in ca.RUBRICS)
    # Характер редактора — наблюдение, а не юмор (слово владельца 17.11.2026); слова согласованы и входят в промпт.
    assert "а не шутка" in prompt and "не путать характер с юмором" in prompt
    assert "Не пишем никогда" in prompt and "«г/г»" in prompt and "Наш расчёт: 6,26 %" in prompt


def test_voice_rules_from_owner_reach_prompt_and_guard(env):
    maker, _, _ = env
    block = "/voice\nнет: «занятно, что»\nда: Наш расчёт: 6,26 %\nправило: заголовок без тире\nэто не правило"
    assert cv.parse_lines(block) == [("ban", "занятно, что"), ("use", "Наш расчёт: 6,26 %"), ("rule", "заголовок без тире")]
    assert cv.is_voice_command("/voice нет: шок") and not cv.is_voice_command("меню")
    reply = asyncio.run(cv.handle_owner_command(block))
    assert "Записал: 3 из 3" in reply
    assert "уже были" in asyncio.run(cv.handle_owner_command(block)) and "0 из 3" in asyncio.run(cv.handle_owner_command(block))

    async def brief():
        async with maker() as db:
            return await cf.build_briefing(db, datetime(2026, 11, 17, 9, 30, tzinfo=MSK))

    b = asyncio.run(brief())
    assert "занятно, что" in b.banned and "г/г" in b.banned
    prompt = ca.system_prompt("between", b.words)
    assert "заголовок без тире" in prompt and "«занятно, что»" in prompt
    assert cf.check_post("Занятно, что дизель — 86,63 ₽.", b.corpus, banned=b.banned).blocked
    listing = asyncio.run(cv.handle_owner_command("/voice"))
    assert "1. нет: занятно, что" in listing and "3. правило: заголовок без тире" in listing
    assert "Убрал правило 1" in asyncio.run(cv.handle_owner_command("/voice убрать 1"))
    assert "занятно, что" not in asyncio.run(brief()).banned
    # Владелец вернул в оборот слово из основного списка — сторож его больше не останавливает.
    asyncio.run(cv.handle_owner_command("/voice да: обвал"))
    assert "обвал" not in asyncio.run(brief()).banned and "рухнул" in asyncio.run(brief()).banned


def test_service_bot_takes_voice_command_from_owner_only(env, monkeypatch):
    maker, api_calls, _ = env
    monkeypatch.setattr(settings, "channel_author_enabled", True, raising=False)
    asyncio.run(tb._handle_message({"chat": {"id": 999}, "text": "/voice нет: шок"}))
    asyncio.run(tb._handle_message({"chat": {"id": 111}, "text": "/voice\nнет: рекордный"}))

    async def rules():
        async with maker() as db:
            return [(r.kind, r.text) for r in await cv.owner_rules(db)]

    assert asyncio.run(rules()) == [("ban", "рекордный")]
    assert any(m == "sendMessage" and "Записал" in p["text"] for m, p in api_calls)


def test_plan_time_rules(monkeypatch):
    monkeypatch.setattr(settings, "channel_post_hour_msk", 10, raising=False)
    morning = datetime(2026, 11, 17, 9, 35, tzinfo=MSK)
    t = cp.plan_time("slot", morning, busy_days={}, rubric="noticed")
    assert (t.hour, t.minute) == (10, 0) and cp.when_label(t, morning) == "сегодня в 10:00"
    noon = datetime(2026, 11, 17, 12, 5, tzinfo=MSK)
    assert cp.when_label(cp.plan_time("slot", noon, busy_days={}, rubric="noticed"), noon) == "сейчас"
    night = datetime(2026, 11, 17, 22, 30, tzinfo=MSK)
    t = cp.plan_time("now", night, busy_days={}, rubric="release")
    assert t.date() == date(2026, 11, 18) and t.hour == 10 and cp.when_label(t, night) == "завтра в 10:00"
    # Средний или большой пост — один в сутки; «цифра вышла» и короткая строка могут выйти рядом с ним.
    busy = {date(2026, 11, 17): (1, 1)}
    assert cp.plan_time("slot", morning, busy_days=busy, rubric="noticed").date() == date(2026, 11, 18)
    assert cp.plan_time("now", noon, busy_days=busy, rubric="release").date() == date(2026, 11, 17)
    assert cp.plan_time("now", noon, busy_days=busy, rubric="flash", short=True).date() == date(2026, 11, 17)
    # Но не больше трёх постов в день, даже коротких.
    full = {date(2026, 11, 17): (3, 1)}
    assert cp.plan_time("now", noon, busy_days=full, rubric="flash", short=True).date() == date(2026, 11, 18)


def test_sizes_and_footer():
    assert ca.size_of("Доллар — 82,15 ₽. За день −0,83 ₽.") == "short"
    assert ca.size_of("x" * 500) == "medium" and ca.size_of("x" * 900) == "long"
    prompt = ca.system_prompt()
    assert "<sizes>" in prompt and "шесть коротких, три средних и один большой" in prompt


# ---------------------------------------------------------------------------
# Счётчик канала
# ---------------------------------------------------------------------------

def test_parse_embed_and_summary_line(monkeypatch):
    html = ('<div class="tgme_widget_message"><span class="tgme_widget_message_views">1.2K</span>'
            '<time datetime="2026-11-10T17:45:51+00:00" class="time">20:45</time></div>')
    views, posted = cs.parse_embed(html)
    assert views == 1200 and posted == datetime(2026, 11, 10, 17, 45, 51)
    assert cs.parse_embed('<div class="tgme_widget_message_error">Post not found</div>') is None
    assert cs.parse_embed("<div>служебное сообщение без счётчика</div>") is None
    assert cs.parse_views("28") == 28
    line = cs.summary_line((16, 2), [{"message_id": 31, "views": 28, "posted_at": None}], 3)
    assert line == "<b>Канал:</b> 16 подписчиков (+2 за неделю); последний пост — 28 просмотров; на сайт из канала за неделю — 3 захода."
    assert cs.summary_line(None, [], None) is None
    monkeypatch.setattr(settings, "channel_chat_id", "@forecasteconomy", raising=False)
    assert cs.channel_username() == "forecasteconomy"
    monkeypatch.setattr(settings, "channel_chat_id", "-1003511287649", raising=False)
    assert cs.channel_username() is None


# ---------------------------------------------------------------------------
# База: сводка, утверждение, публикация
# ---------------------------------------------------------------------------

@pytest.fixture
def env(monkeypatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path/'channel.db'}")
    maker = async_sessionmaker(engine, expire_on_commit=False)
    api_calls: list[tuple[str, dict]] = []
    once_calls: list[tuple[str, dict]] = []

    async def setup():
        async with engine.begin() as conn:
            for m in _TABLES:
                await conn.run_sync(lambda c, t=m.__table__: t.create(c))
        async with maker() as db:
            diesel = Indicator(code="fuel-diesel", name="Цена дизельного топлива", unit="руб./л", frequency="weekly", source="Росстат")
            a95 = Indicator(code="fuel-ai95", name="АИ-95", unit="руб./л", frequency="weekly", source="Росстат")
            cpi = Indicator(code="cpi-yoy", name="ИПЦ год к году", unit="%", frequency="monthly", source="Росстат")
            gold = Indicator(code="gold-price", name="Золото", unit="руб./г", frequency="daily", source="Банк России")
            db.add_all([diesel, a95, cpi, gold])
            await db.flush()
            start = date(2025, 11, 10)
            for i in range(53):   # год недельных цен: дизель плавно растёт
                db.add(IndicatorData(indicator_id=diesel.id, date=start + timedelta(days=7 * i), value=round(74.56 + i * 0.2321, 2)))
                db.add(IndicatorData(indicator_id=a95.id, date=start + timedelta(days=7 * i), value=round(67.34 + i * 0.1721, 2)))
            for i in range(14):
                db.add(IndicatorData(indicator_id=cpi.id, date=date(2025 + (7 + i) // 12, (7 + i) % 12 + 1, 1), value=8.0 - i * 0.127))
            for i in range(40):   # золото: мелкие шаги и резкое падение в последний день
                db.add(IndicatorData(indicator_id=gold.id, date=date(2026, 10, 1) + timedelta(days=i), value=10700 + (i % 3) * 20))
            db.add(IndicatorData(indicator_id=gold.id, date=date(2026, 11, 10), value=10222.10))
            f = Forecast(indicator_id=cpi.id, model_name="m", is_current=True)
            db.add(f)
            await db.flush()
            db.add(ForecastValue(forecast_id=f.id, date=date(2026, 10, 1), value=6.26, lower_bound=5.0, upper_bound=7.5))
            await db.commit()

    asyncio.run(setup())

    counter = {"n": 100}

    async def fake_api(method, payload, files=None, token=None, **kw):
        api_calls.append((method, payload))
        counter["n"] += 1
        return {"ok": True, "result": {"message_id": counter["n"]}}

    async def fake_once(method, payload, files=None, token=None):
        once_calls.append((method, payload))
        return {"ok": True, "result": {"message_id": 46}}

    async def no_chart(topic_key):
        return b"png-bytes"

    monkeypatch.setattr(dbm, "async_session", maker)
    monkeypatch.setattr(tb, "_api", fake_api)
    monkeypatch.setattr(cp, "_tg_once", fake_once)
    monkeypatch.setattr(pb, "render_topic_chart", no_chart)
    monkeypatch.setattr(settings, "telegram_bot_token", "test-token", raising=False)
    monkeypatch.setattr(settings, "telegram_chat_id", "111", raising=False)
    monkeypatch.setattr(settings, "channel_review_chat_ids", "", raising=False)
    monkeypatch.setattr(settings, "channel_chat_id", "@forecasteconomy", raising=False)
    monkeypatch.setattr(settings, "channel_publish_enabled", False, raising=False)
    monkeypatch.setattr(settings, "channel_post_hour_msk", 10, raising=False)
    import app.services.telegram_outbox as outbox
    monkeypatch.setattr(outbox, "async_session", maker)
    yield maker, api_calls, once_calls
    asyncio.run(engine.dispose())


def test_briefing_registers_every_number_and_flags_jump(env):
    maker, _, _ = env

    async def run():
        async with maker() as db:
            return await cf.build_briefing(db, datetime(2026, 11, 17, 9, 30, tzinfo=MSK), fresh=["fuel-diesel"])

    b = asyncio.run(run())
    assert "<today>Вторник, 17 ноября 2026, 09:30 по Москве.</today>" in b.text
    assert "<new_today>" in b.text and "Дизель [fuel-diesel]" in b.text
    assert "86,63 ₽ за литр, на 9 ноября 2026" in b.text
    assert "необычный скачок" in b.text.split("[gold-price]")[1]
    assert "необычный скачок" not in b.text.split("[fuel-diesel]")[1].split("[fuel-ai95]")[0]
    assert "только с пометкой «наш расчёт»" in b.text
    assert "5,0" not in b.text.split("[cpi-yoy]")[1].split("\n\n")[0]      # границы прогноза в сводку не попадают
    # Каждое число вида «12,34» в блоке данных есть в основаниях.
    block = b.text.split("<fresh_data>")[1].split("</fresh_data>")[0]
    for tok in cf.extract_numbers(cf.plain_text(block)):
        if tok.kind == "number" and tok.decimals:
            assert b.corpus.find(tok.value, tok.decimals), tok.raw
    post = "<b>Дизель подорожал до 86,63 ₽</b>\nБак на 50 литров — 4 332 ₽, год назад — 3 728 ₽."
    audit = cf.check_post(post, b.corpus, [{"shown": "50", "basis": "assumption"}])
    assert not audit.blocked, audit.issues
    assert audit.sources == ["Росстат"]


def _draft(blocked=False, rubric="fuel", when="slot") -> ca.Draft:
    body = "<b>Дизель — 86,63 ₽ за литр</b>\n\nБак на 50 литров — 4 332 ₽."
    audit = {"numbers": [{"shown": "86,63", "status": "data", "basis": "Дизель · 9 ноября 2026 · Росстат"},
                         {"shown": "71,20", "status": "unmatched", "basis": "нет в данных"}] if blocked else
             [{"shown": "86,63", "status": "data", "basis": "Дизель · 9 ноября 2026 · Росстат"}],
             "issues": ["число «71,20» не найдено"] if blocked else [], "warnings": [], "sources": ["Росстат"],
             "checks": [], "concerns": "", "web": [], "declared": []}
    return ca.Draft(rubric=rubric, size="medium", body=body, text=ca.compose_post(body, ["Росстат"], ca.channel_url("fuel-diesel", rubric), None),
                    chart_topic="diesel", link_url=ca.channel_url("fuel-diesel", rubric), when=when, silent=True,
                    why="Вышли недельные цены.", audit=audit, blocked=blocked)


def _cq(data, chat_id=111, message_id=1):
    return {"id": "cq1", "data": data, "from": {"first_name": "Иван"},
            "message": {"chat": {"id": chat_id}, "message_id": message_id}}


async def _get(maker, pid) -> ChannelPost:
    async with maker() as db:
        return await db.get(ChannelPost, pid)


def test_draft_goes_to_owner_with_buttons_and_nothing_to_channel(env):
    maker, api_calls, once_calls = env
    pid = asyncio.run(cp.create_and_send(_draft()))
    methods = [m for m, _ in api_calls]
    assert methods == ["sendPhoto", "sendMessage"]              # пост как он выйдет + панель с кнопками
    photo, panel = api_calls[0][1], api_calls[1][1]
    assert photo["chat_id"] == "111" and "utm_medium=channel" in photo["caption"]
    assert "Черновик для канала" in panel["text"] and "Бензин и дизель" in panel["text"]
    buttons = [b["callback_data"] for row in panel["reply_markup"]["inline_keyboard"] for b in row]
    assert f"ch:ok:{pid}" in buttons and f"ch:edit:{pid}" in buttons and f"ch:no:{pid}" in buttons
    assert not once_calls                                       # в канал ничего не ушло
    assert all(p.get("chat_id") != "@forecasteconomy" for _, p in api_calls)
    post = asyncio.run(_get(maker, pid))
    assert post.status == "draft" and post.review_messages[0]["chat_id"] == "111"


def test_blocked_draft_has_no_publish_button_and_cannot_be_approved(env):
    maker, api_calls, _ = env
    pid = asyncio.run(cp.create_and_send(_draft(blocked=True)))
    panel = api_calls[1][1]
    buttons = [b["callback_data"] for row in panel["reply_markup"]["inline_keyboard"] for b in row]
    assert not [b for b in buttons if b.startswith(("ch:ok", "ch:now"))]
    assert "Публиковать нельзя" in panel["text"]
    asyncio.run(cp.handle_callback(_cq(f"ch:ok:{pid}")))
    assert asyncio.run(_get(maker, pid)).status == "draft"


def test_stranger_cannot_press_buttons(env):
    maker, _, _ = env
    pid = asyncio.run(cp.create_and_send(_draft()))
    asyncio.run(cp.handle_callback(_cq(f"ch:ok:{pid}", chat_id=999)))
    assert asyncio.run(_get(maker, pid)).status == "draft"


def test_approve_undo_and_publish_only_with_flag(env, monkeypatch):
    maker, api_calls, once_calls = env
    pid = asyncio.run(cp.create_and_send(_draft(when="now", rubric="release")))
    asyncio.run(cp.handle_callback(_cq(f"ch:ok:{pid}")))
    post = asyncio.run(_get(maker, pid))
    assert post.status == "approved" and post.planned_at is not None and post.decided_by == "111"
    assert any(m == "editMessageText" for m, _ in api_calls)
    # Публикация выключена: одобренный пост остаётся в базе.
    assert asyncio.run(cp.channel_publish_job()) == {"skipped": "disabled"}
    assert not once_calls
    asyncio.run(cp.handle_callback(_cq(f"ch:undo:{pid}")))
    assert asyncio.run(_get(maker, pid)).status == "draft"
    asyncio.run(cp.handle_callback(_cq(f"ch:now:{pid}")))

    async def due():
        async with maker() as db:
            p = await db.get(ChannelPost, pid)
            p.planned_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
            await db.commit()

    asyncio.run(due())
    monkeypatch.setattr(settings, "channel_publish_enabled", True, raising=False)
    assert asyncio.run(cp.channel_publish_job()) == {"published": pid}
    assert len(once_calls) == 1 and once_calls[0][0] == "sendPhoto" and once_calls[0][1]["chat_id"] == "@forecasteconomy"
    post = asyncio.run(_get(maker, pid))
    assert post.status == "published" and post.telegram_message_id == 46
    # Второй запуск ничего не шлёт: пост не уходит дважды.
    assert asyncio.run(cp.channel_publish_job()) == {"skipped": "nothing_due"}
    assert len(once_calls) == 1


def test_publish_failure_is_not_retried_automatically(env, monkeypatch):
    maker, _, once_calls = env

    async def failing(method, payload, files=None, token=None):
        once_calls.append((method, payload))
        cp._last_once_error = "{'ok': False, 'description': 'Bad Request: not enough rights to send photos to the chat'}"
        return None

    monkeypatch.setattr(cp, "_tg_once", failing)
    monkeypatch.setattr(settings, "channel_publish_enabled", True, raising=False)
    pid = asyncio.run(cp.create_and_send(_draft()))

    async def approve():
        async with maker() as db:
            p = await db.get(ChannelPost, pid)
            p.status, p.planned_at = "approved", datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
            await db.commit()

    asyncio.run(approve())
    assert asyncio.run(cp.channel_publish_job()) == {"failed": pid}
    post = asyncio.run(_get(maker, pid))
    assert post.status == "failed" and "администратором" in post.error
    assert asyncio.run(cp.channel_publish_job()) == {"skipped": "nothing_due"}
    assert len(once_calls) == 1


def test_stale_approval_returns_to_owner_and_claim_is_atomic(env, monkeypatch):
    """17.11.2026: одобрение старше шести часов само в канал не уходит; занятый пост не берётся повторно."""
    maker, _, once_calls = env
    monkeypatch.setattr(settings, "channel_publish_enabled", True, raising=False)
    pid = asyncio.run(cp.create_and_send(_draft()))

    async def approve(hours_ago):
        async with maker() as db:
            p = await db.get(ChannelPost, pid)
            p.status = "approved"
            p.planned_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=hours_ago)
            await db.commit()

    asyncio.run(approve(cp.APPROVAL_STALE_HOURS + 1))
    assert asyncio.run(cp.channel_publish_job()) == {"expired": pid}
    post = asyncio.run(_get(maker, pid))
    assert post.status == "draft" and post.planned_at is None and "подтвердите заново" in post.error
    assert once_calls == []                                   # в канал ничего не ушло

    # Пост, уже взятый другим процессом («publishing»), второй раз не отправляется.
    async def taken():
        async with maker() as db:
            p = await db.get(ChannelPost, pid)
            p.status, p.planned_at = "publishing", datetime.now(timezone.utc).replace(tzinfo=None)
            await db.commit()

    asyncio.run(taken())
    assert asyncio.run(cp.channel_publish_job()) == {"skipped": "nothing_due"}
    assert once_calls == []


def test_reject_with_reason_feeds_author_memory(env):
    maker, _, _ = env
    pid = asyncio.run(cp.create_and_send(_draft()))
    asyncio.run(cp.handle_callback(_cq(f"ch:no:{pid}")))
    asyncio.run(cp.handle_callback(_cq(f"ch:why:{pid}:dull")))
    post = asyncio.run(_get(maker, pid))
    assert post.status == "skipped" and post.feedback == "скучно"

    async def brief():
        async with maker() as db:
            return await cf.build_briefing(db, datetime(2026, 11, 17, 9, 30, tzinfo=MSK))

    assert "отклонён: скучно" in asyncio.run(brief()).text


def test_two_reviewers_first_press_wins_and_both_panels_update(env, monkeypatch):
    maker, api_calls, _ = env
    monkeypatch.setattr(settings, "channel_review_chat_ids", "111, 222", raising=False)
    pid = asyncio.run(cp.create_and_send(_draft()))
    assert sorted({p["chat_id"] for m, p in api_calls if m in ("sendPhoto", "sendMessage")}) == ["111", "222"]
    api_calls.clear()
    asyncio.run(cp.handle_callback(_cq(f"ch:ok:{pid}", chat_id=222)))
    edited = [p for m, p in api_calls if m == "editMessageText"]
    assert sorted(p["chat_id"] for p in edited) == ["111", "222"]
    assert all("Одобрено" in p["text"] and "Иван" in p["text"] for p in edited)
    api_calls.clear()
    asyncio.run(cp.handle_callback(_cq(f"ch:ok:{pid}", chat_id=111)))     # второе нажатие ничего не меняет
    post = asyncio.run(_get(maker, pid))
    assert post.status == "approved" and post.decided_by == "222"


def test_owner_reply_asks_author_to_rewrite(env, monkeypatch):
    maker, api_calls, _ = env
    monkeypatch.setattr(settings, "openrouter_api_key", "k", raising=False)
    seen = {}

    async def fake_run(kind, **kw):
        seen.update(kind=kind, revise=kw.get("revise"))
        return ca.AuthorResult(kind=kind, model="m", drafts=[_draft()])

    monkeypatch.setattr(ca, "run_author", fake_run)

    async def scenario():
        pid = await cp.create_and_send(_draft())
        post = await _get(maker, pid)
        msg = {"chat": {"id": 111}, "text": "Короче и без бака",
               "reply_to_message": {"message_id": post.review_messages[0]["panel_id"]}}
        assert await cp.handle_message(msg) is True
        await asyncio.gather(*list(cp._tasks))
        return pid

    pid = asyncio.run(scenario())
    assert seen["kind"] == "revise" and seen["revise"]["note"] == "Короче и без бака"
    assert "86,63" in seen["revise"]["body"] and "utm_medium" not in seen["revise"]["body"]
    old = asyncio.run(_get(maker, pid))
    assert old.status == "replaced" and old.feedback == "Короче и без бака"

    async def newest():
        async with maker() as db:
            return (await db.execute(select(ChannelPost).order_by(ChannelPost.id.desc()).limit(1))).scalar_one()

    new = asyncio.run(newest())
    assert new.parent_id == pid and new.status == "draft"
    # Обычное сообщение владельца без ответа на черновик модулю канала не принадлежит.
    assert asyncio.run(cp.handle_message({"chat": {"id": 111}, "text": "меню"})) is False


def test_service_bot_routes_channel_buttons(env, monkeypatch):
    maker, _, _ = env
    monkeypatch.setattr(settings, "channel_author_enabled", True, raising=False)
    pid = asyncio.run(cp.create_and_send(_draft()))
    asyncio.run(tb._handle_callback(_cq(f"ch:no:{pid}")))
    assert asyncio.run(_get(maker, pid)).status == "skipped"


def test_stats_job_writes_subscribers_and_views(env, monkeypatch):
    maker, _, _ = env
    monkeypatch.setattr(settings, "channel_stats_enabled", True, raising=False)

    async def fake_subs():
        return 16

    async def fake_views(known):
        return {31: (28, datetime(2026, 11, 10, 17, 45)), 30: (22, None)}

    monkeypatch.setattr(cs, "fetch_subscribers", fake_subs)
    monkeypatch.setattr(cs, "collect_views", fake_views)
    res = asyncio.run(cs.channel_stats_job(date(2026, 11, 17)))
    assert res["subscribers"] == 16 and res["posts"] == 2
    asyncio.run(cs.channel_stats_job(date(2026, 11, 17)))     # повтор в тот же день не плодит строк

    async def read():
        async with maker() as db:
            subs = (await db.execute(select(ChannelStatsDaily))).scalars().all()
            views = (await db.execute(select(ChannelPostView))).scalars().all()
            return subs, views, await cs.latest_views(db, 5), await cs.subscribers_trend(db, date(2026, 11, 17))

    subs, views, latest, trend = asyncio.run(read())
    assert len(subs) == 1 and len(views) == 2
    assert latest[0] == {"message_id": 31, "views": 28, "posted_at": datetime(2026, 11, 10, 17, 45)}
    assert trend == (16, None)
    monkeypatch.setattr(settings, "channel_stats_enabled", False, raising=False)
    assert asyncio.run(cs.channel_stats_job()) == {"skipped": "disabled"}


# ---------------------------------------------------------------------------
# Запуск модели (OpenRouter подменён)
# ---------------------------------------------------------------------------

class _Resp:
    status_code = 200
    text = ""

    def __init__(self, message, usage=None):
        self._data = {"choices": [{"message": message}],
                      "usage": usage or {"prompt_tokens": 1000, "completion_tokens": 100, "cost": 0.01}}

    def json(self):
        return self._data


def _call(name, args, cid="c1"):
    return {"id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}


def _briefing() -> cf.Briefing:
    return cf.Briefing(text="<fresh_data>Дизель 86,63</fresh_data>", corpus=_corpus(), facts={},
                       now=datetime(2026, 11, 17, 9, 30, tzinfo=MSK), fresh=[])


def test_author_loop_guard_sends_draft_back_then_accepts(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "k", raising=False)
    sent_payloads = []
    replies = [
        _Resp({"content": "", "tool_calls": [_call("submit_draft", {
            "rubric": "fuel", "text": "<b>Дизель — 86,63 ₽</b>\nГод назад — 71,20 ₽.", "link": "fuel-diesel",
            "when": "slot", "silent": True, "why": "цены вышли"})], "reasoning_details": [{"type": "reasoning.text"}]}),
        _Resp({"content": "", "tool_calls": [_call("submit_draft", {
            "rubric": "fuel", "size": "medium", "text": "<b>Дизель — 86,63 ₽</b>\nБак на 50 литров — 4 332 ₽.", "link": "fuel-diesel",
            "when": "slot", "silent": True, "why": "цены вышли", "chart_topic": "diesel",
            "numbers": [{"shown": "50", "basis": "assumption"}]}, "c2")]},
              usage={"prompt_tokens": 1200, "completion_tokens": 80, "cost": 0.02}),
    ]

    async def fake_post(client, payload):
        sent_payloads.append(json.loads(json.dumps(payload)))
        return replies[len(sent_payloads) - 1]

    monkeypatch.setattr(ca, "_post", fake_post)
    result = asyncio.run(ca.run_author("daily", briefing=_briefing(), save=False))
    assert result.decision == "draft" and result.steps == 2 and result.web_searches == 0
    assert round(result.cost_usd, 2) == 0.03
    draft = result.drafts[0]
    assert not draft.blocked and "71,20" not in draft.text and draft.chart_topic == "diesel"
    assert draft.text.endswith('\n\nРосстат · <a href="' + draft.link_url.replace("&", "&amp;") + '">график и все годы</a>')
    assert draft.size == "medium" and draft.audit["size"] == "medium"
    # Первый черновик вернулся модели с названным числом; блоки размышления возвращены без изменений.
    second = sent_payloads[1]["messages"]
    assert second[-1]["role"] == "tool" and "71,20" in second[-1]["content"]
    assert second[-2]["reasoning_details"] == [{"type": "reasoning.text"}]
    names = [t["function"]["name"] for t in sent_payloads[0]["tools"]]
    assert names == ["find_series", "get_series", "rank_regions", "calendar", "calculate", "web_search",
                     "submit_draft", "nothing_today"]
    assert sent_payloads[0]["messages"][0]["content"][0]["cache_control"] == {"type": "ephemeral"}
    assert sent_payloads[0]["messages"][1]["content"][-1]["text"].startswith("<task>")   # задание — в конце, после данных


def test_author_keeps_blocked_draft_after_two_corrections(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "k", raising=False)
    bad = {"rubric": "fuel", "text": "<b>Дизель — 99,99 ₽</b>", "link": "fuel-diesel", "when": "slot", "silent": True, "why": "x"}
    n = {"i": 0}

    async def fake_post(client, payload):
        n["i"] += 1
        return _Resp({"content": "", "tool_calls": [_call("submit_draft", bad, f"c{n['i']}")]})

    monkeypatch.setattr(ca, "_post", fake_post)
    result = asyncio.run(ca.run_author("daily", briefing=_briefing(), save=False))
    assert n["i"] == 3 and result.drafts and result.drafts[0].blocked


def test_research_numbers_and_tool_sources_are_grounds(env, monkeypatch):
    maker, _, _ = env

    async def brief():
        async with maker() as db:
            return await cf.build_briefing(db, datetime(2026, 11, 21, 9, 30, tzinfo=MSK))

    b = asyncio.run(brief())
    # Числа аннотации отчёта из очереди исследований — основания: пост о нём пишется по ним.
    audit = cf.check_post("В одном банке вернут не больше 1,4 млн ₽. На вкладах 71 трлн ₽, наличных — 21 трлн ₽.", b.corpus,
                          [{"shown": "71", "basis": "assumption"}], banned=b.banned, reports=True)
    assert not audit.blocked, audit.issues
    assert audit.sources == ["исследование Forecast Economy"]
    # Число есть в данных — это данные, даже если автор объявил его допущением.
    assert {n["shown"]: n["status"] for n in audit.numbers} == {"1,4": "report", "71": "report", "21": "report"}
    # Даже если такое же число случайно есть у ряда, о котором в посте ни слова (евро подешевел на 1,4 %).
    b.corpus.n(1.4, "Евро · изменение к прошлой дате", 1, source="Банк России", kind="derived", series="eur-rub")
    again = cf.check_post("В одном банке вернут не больше 1,4 млн ₽.", b.corpus, banned=b.banned, reports=True)
    assert again.numbers[0]["status"] == "report" and again.sources == ["исследование Forecast Economy"]
    # В посте другой рубрики числа отчётов основанием не считаются: «3,4» не совпадёт с «×3,4» из отчёта.
    other = cf.check_post("Дизель — 86,63 ₽. Это в 3,4 раза больше.", b.corpus)
    assert other.blocked and "исследование Forecast Economy" not in other.sources

    # Источник ряда из ответа базы попадает в строку под постом.
    monkeypatch.setattr(settings, "openrouter_api_key", "k", raising=False)
    import app.services.bot_agent_tools as tools

    async def fake_tool(name, args):
        return ("Международные резервы, млрд $ (Россия, Банк России). Точек за период: 45.\n"
                "Первое 752,50 на 2026-01-02; последнее 724,30 на 2026-11-06.")

    monkeypatch.setattr(tools, "run_tool", fake_tool)
    replies = [
        _Resp({"content": "", "tool_calls": [_call("get_series", {"code": "international-reserves"})]}),
        _Resp({"content": "", "tool_calls": [_call("submit_draft", {
            "rubric": "flash", "size": "short", "text": "Международные резервы — 724,30 млрд $ на 6 ноября.",
            "link": "home", "when": "slot", "silent": True, "why": "резервы"}, "c2")]}),
    ]
    n = {"i": 0}

    async def fake_post(client, payload):
        n["i"] += 1
        return replies[n["i"] - 1]

    monkeypatch.setattr(ca, "_post", fake_post)
    result = asyncio.run(ca.run_author("daily", briefing=_briefing(), save=False))
    draft = result.drafts[0]
    assert not draft.blocked, draft.audit["issues"]
    assert draft.audit["sources"] == ["Банк России"] and "\n\nБанк России · <a href=" in draft.text


def test_author_may_decide_nothing_today_and_uses_db_tool(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "k", raising=False)
    replies = [
        _Resp({"content": "", "tool_calls": [_call("calculate", {"expression": "86.63*50"})]}),
        _Resp({"content": "", "tool_calls": [_call("nothing_today", {"reason": "Новых данных нет.", "concerns": "золото"}, "c2")]}),
    ]
    n = {"i": 0}

    async def fake_post(client, payload):
        n["i"] += 1
        return replies[n["i"] - 1]

    monkeypatch.setattr(ca, "_post", fake_post)
    result = asyncio.run(ca.run_author("daily", briefing=_briefing(), save=False))
    assert result.decision == "nothing" and result.nothing == "Новых данных нет." and result.concerns == "золото"
    assert result.tool_log[0]["tool"] == "calculate"


def test_author_web_search_goes_through_helper_and_feeds_the_guard(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "k", raising=False)
    monkeypatch.setattr(settings, "channel_author_web_max_searches", 1, raising=False)
    helper_payloads = []
    author_replies = [
        _Resp({"content": "", "tool_calls": [_call("web_search", {"query": "учётная цена золота 14 ноября 2026", "site": "cbr.ru"})]}),
        _Resp({"content": "", "tool_calls": [_call("web_search", {"query": "ещё раз"}, "c2")]}),
        _Resp({"content": "", "tool_calls": [_call("submit_draft", {
            "rubric": "flash", "size": "short", "chart_topic": "gold", "text": "Золото — 10 222,10 ₽ за грамм.", "link": "gold-price", "when": "slot",
            "silent": True, "why": "скачок подтверждён",
            "checks": [{"what": "цена золота 14 ноября", "where": "https://cbr.ru/hd_base/metall/", "result": "совпадает"}]}, "c3")]}),
    ]
    n = {"i": 0}

    async def fake_post(client, payload):
        if payload["messages"][0]["content"] == ca.WEB_HELPER_PROMPT:
            helper_payloads.append(payload)
            return _Resp({"content": "На 14.11.2026 — 10222,10 руб./грамм.", "annotations": [{"type": "url_citation", "url_citation": {
                "url": "https://cbr.ru/hd_base/metall/", "title": "Учётные цены", "content": "14.11.2026 золото 10222,10"}}]},
                usage={"cost": 0.004})
        n["i"] += 1
        return author_replies[n["i"] - 1]

    monkeypatch.setattr(ca, "_post", fake_post)
    result = asyncio.run(ca.run_author("daily", briefing=_briefing(), save=False))
    assert len(helper_payloads) == 1                         # второй поиск упёрся в лимит запуска
    helper = helper_payloads[0]
    assert helper["model"] == "anthropic/claude-haiku-5.5"
    assert helper["tools"] == [{"type": "openrouter:web_search", "parameters": {
        "engine": "auto", "max_uses": 2, "max_results": 5, "allowed_domains": ["cbr.ru"]}}]
    assert result.web_searches == 1 and round(result.cost_usd, 3) == 0.034
    draft = result.drafts[0]
    assert not draft.blocked, draft.audit["issues"]          # число со скачком перепроверено — публиковать можно
    assert draft.size == "short" and draft.chart_topic is None      # короткая строка идёт без картинки
    assert draft.audit["web"] == [{"url": "https://cbr.ru/hd_base/metall/", "title": "Учётные цены"}]
    assert any("необычным скачком" in w for w in draft.audit["warnings"])


def test_author_without_key_or_flag_does_nothing(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "", raising=False)
    assert asyncio.run(ca.run_author("daily", briefing=_briefing(), save=False)).status == "no_key"
    monkeypatch.setattr(settings, "channel_author_enabled", False, raising=False)
    assert asyncio.run(ca.channel_author_daily_job()) == {"skipped": "disabled"}
    assert asyncio.run(ca.channel_author_release_job()) == {"skipped": "disabled"}
    assert asyncio.run(ca.channel_plan_job()) == {"skipped": "disabled"}


# ---------------------------------------------------------------------------
# Настройки и миграция
# ---------------------------------------------------------------------------

def test_new_flags_are_off_by_default_and_reach_containers():
    from app.config import Settings

    fields = Settings.model_fields
    for flag in ("channel_stats_enabled", "channel_author_enabled", "channel_plan_enabled", "channel_publish_enabled"):
        assert fields[flag].default is False
    compose = (ROOT.parent / "docker-compose.yml").read_text(encoding="utf-8")
    for name in ("CHANNEL_CHAT_ID", "CHANNEL_STATS_ENABLED", "CHANNEL_AUTHOR_ENABLED", "CHANNEL_AUTHOR_MODEL",
                 "CHANNEL_AUTHOR_EFFORT", "CHANNEL_AUTHOR_TONE", "CHANNEL_AUTHOR_WEB_ENABLED", "CHANNEL_AUTHOR_WEB_ENGINE",
                 "CHANNEL_AUTHOR_WEB_MODEL",
                 "CHANNEL_AUTHOR_WEB_MAX_SEARCHES", "CHANNEL_AUTHOR_DAILY_USD_LIMIT", "CHANNEL_PLAN_ENABLED",
                 "CHANNEL_REVIEW_CHAT_IDS", "CHANNEL_PUBLISH_ENABLED", "CHANNEL_POST_HOUR_MSK", "CHANNEL_BOT_TOKEN"):
        assert f"RUSTATS_{name}: ${{RUSTATS_{name}:-" in compose, name
        assert name.lower() in fields, name
    assert "RUSTATS_CHANNEL_AUTHOR_ENABLED: ${RUSTATS_CHANNEL_AUTHOR_ENABLED:-false}" in compose
    assert "RUSTATS_CHANNEL_PUBLISH_ENABLED: ${RUSTATS_CHANNEL_PUBLISH_ENABLED:-false}" in compose


def test_channel_kinds_are_not_held_and_not_resent():
    from app.services.telegram_calm import HELD_KINDS
    from app.services.telegram_resend import RESEND_KINDS

    for kind in (cp.KIND_DRAFT, cp.KIND_POST, "channel_note", "channel_plan"):
        assert kind not in HELD_KINDS        # черновик ждёт человека: не технический алерт
        assert kind not in RESEND_KINDS      # досылка не должна повторить пост в канал


def test_migration_matches_models_and_only_adds():
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    path = ROOT / "alembic" / "versions" / "20261117_channel_author.py"
    spec = importlib.util.spec_from_file_location("m20261117", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.revision == "20261117_channel_author" and len(mod.revision) <= 32
    assert mod.down_revision == "20261116_mail_tracking"
    src = path.read_text(encoding="utf-8")
    assert not [w for w in ("add_column", "drop_column", "alter_column", "rename_table", "execute(") if w in src]
    tables = {"channel_posts", "channel_author_runs", "channel_stats_daily", "channel_post_views", "channel_voice_rules"}
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            mod.upgrade()
        assert tables <= set(sa.inspect(conn).get_table_names())
        diffs = compare_metadata(
            MigrationContext.configure(conn, opts={"include_object": lambda obj, name, type_, reflected, compare_to:
                                                   (name in tables) if type_ == "table" else True}),
            Base.metadata)
        ours = [d for d in diffs if any(t in repr(d) for t in tables)]
        assert not ours, ours
        with Operations.context(MigrationContext.configure(conn)):
            mod.downgrade()
        assert not tables & set(sa.inspect(conn).get_table_names())


def test_calculator_reads_comma_as_argument_separator_first():
    from app.services.bot_agent_tools import calculate

    assert calculate("round(71/21, 1)").endswith("= 3,40")       # было 3,00: запятая превращалась в точку
    assert calculate("86,63*50").endswith("= 4 331,50")
    assert calculate("round((341.06/313.90-1)*100,1)").endswith("= 8,70")
    assert calculate("1 000 000/(1+0,0635)").startswith("1 000 000/(1+0,0635) = 940")
    assert "Не посчитал" in calculate("__import__('os')")

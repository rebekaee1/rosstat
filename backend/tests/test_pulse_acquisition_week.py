"""Недельная строка привлечения в Пульсе (совет 19.11.2026, `app/services/pulse_acquisition.py`)."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

from tests.test_analytics2 import _run_with_db

D = date(2026, 11, 18)
END = datetime(2026, 11, 18, 21, 0)  # конец дня по Москве в UTC


def _visit(n: int, client: str | None, at: datetime, *, engine: str | None = "yandex", source: str = "organic",
           referer: str | None = None, country: str | None = None):
    from app.models import RawMetrikaVisit

    raw = {"ym:s:regionCountry": country} if country else {}
    return RawMetrikaVisit(counter_id="1", visit_id=f"v{n}", client_id_hash=client, visit_date=at.date(),
                           start_time=at, traffic_source=source, search_engine=engine, referer=referer,
                           raw_json=raw, row_hash=f"h{n}")


def test_return_cohort_separates_self_return_from_search_return():
    from app.services import pulse_acquisition as pa

    first = datetime(2026, 10, 5, 10, 0)  # 44 дня до отчётного дня: в когорте 31–60 дней

    async def scenario(maker):
        async with maker() as db:
            n = iter(range(1000))
            db.add_all([
                # a — вернулся сам (без поисковика) через 3 дня
                _visit(next(n), "a", first, engine="yandex"),
                _visit(next(n), "a", first + timedelta(days=3), engine=None, source="direct"),
                # b — вернулся через Яндекс в другой день
                _visit(next(n), "b", first, engine="yandex"),
                _visit(next(n), "b", first + timedelta(days=5), engine="yandex"),
                # c — второй визит в тот же день: не возврат
                _visit(next(n), "c", first, engine="yandex"),
                _visit(next(n), "c", first + timedelta(hours=3), engine=None, source="direct"),
                # d — вернулся сам, но через 40 дней: вне окна 30 дней
                _visit(next(n), "d", first, engine="yandex"),
                _visit(next(n), "d", first + timedelta(days=40), engine=None, source="direct"),
                # e — первый вход 10 дней назад: не в когорте
                _visit(next(n), "e", datetime(2026, 11, 8, 9, 0), engine="yandex"),
                # f — первый вход из Яндекса раньше когорты: не в когорте
                _visit(next(n), "f", datetime(2026, 8, 1, 9, 0), engine="yandex"),
                _visit(next(n), "f", first, engine="yandex"),
            ])
            await db.commit()
            return await pa.return_cohort(db, D)

    r = _run_with_db(scenario)
    assert r["cohort"] == 4
    assert r["other_day"] == 2 and r["by_self"] == 1
    assert r["other_day_pct"] == 50.0 and r["by_self_pct"] == 25.0


def test_build_week_counts_line_bot_subscriptions_signups_ai_and_google_ru():
    from app.models import (Consent, FrontendEvent, PublicBotChat, PublicBotSubscription, ServerSession, User,
                            UserSignup)
    from app.services import pulse_acquisition as pa

    t = END - timedelta(days=2)

    async def scenario(maker):
        async with maker() as db:
            n = iter(range(1000))
            db.add_all([
                _visit(next(n), "y1", t), _visit(next(n), "y2", t),
                _visit(next(n), "g1", t, engine="google", country="Russia"),
                _visit(next(n), "g2", t, engine="google", country="Germany"),
                _visit(next(n), "ai", t, engine=None, source="referral", referer="https://chatgpt.com/"),
                _visit(next(n), "al", t, engine=None, source="referral", referer="https://alice.yandex.ru/"),
                _visit(next(n), "old", END - timedelta(days=9)),  # вне 7 дней
            ])
            for i in range(4):
                db.add(FrontendEvent(event_name="subscribe_line_view", visitor_id_hash=f"p{i}", occurred_at=t,
                                     params_json={"topic": "inflation", "channel": "telegram"}))
            db.add(FrontendEvent(event_name="subscribe_line_click", visitor_id_hash="p1", occurred_at=t,
                                 params_json={"topic": "inflation", "channel": "telegram"}))
            db.add_all([
                PublicBotChat(chat_id="1", chat_hash="h1", first_code="site_inflation", first_seen_at=t, last_seen_at=t),
                PublicBotChat(chat_id="2", chat_hash="h2", first_code="ig_bio", first_seen_at=t, last_seen_at=t),
                # Приветственный экран и «Исследования» тоже ведут в бота с кодом site_*, но это не строка «присылать».
                PublicBotChat(chat_id="3", chat_hash="h3", first_code="site_welcome", first_seen_at=t, last_seen_at=t),
                PublicBotChat(chat_id="4", chat_hash="h4", first_code="site_research", first_seen_at=t, last_seen_at=t),
            ])
            await db.flush()
            db.add_all([PublicBotSubscription(chat_id="1", topic="inflation", created_at=t),
                        PublicBotSubscription(chat_id="2", topic="usd", created_at=t),
                        PublicBotSubscription(chat_id="3", topic="gold", created_at=t)])
            db.add(ServerSession(day=t.date(), visitor_id_hash="p1", started_at=t, ended_at=t,
                                 is_bot=False, is_internal=False, is_human=True))
            uid = uuid.uuid4()
            db.add(User(id=uid, created_at=t))
            await db.flush()
            db.add(UserSignup(user_id=uid, created_at=t, trigger="gate_download"))
            db.add(Consent(user_id=uid, kind="watch_mail", version="t", granted_at=t))
            await db.commit()
            return await pa.build_week(db, D, END)

    w = _run_with_db(scenario)
    assert w["metrika"]["yandex_visits"] == 2
    assert w["metrika"]["google_ru_visits"] == 1
    assert w["metrika"]["ai_visits"] == 2
    assert w["line"]["views"] == 4 and w["line"]["clicks"] == 1
    assert w["line"]["clicks_per_1000_views"] == 250.0
    assert w["line"]["clicks_by_channel"] == {"telegram": 1}
    s = w["subscriptions"]
    assert s["site_bot_chats_new"] == 1
    assert s["bot_subscriptions_new"] == 3 and s["bot_subscriptions_new_from_site"] == 1
    assert s["watch_mail_consents_new"] == 1
    assert w["signups"] == {"total": 1, "by_trigger": {"gate_download": 1}}
    assert w["people"]["human_visitors"] == 1

    lines = pa.week_lines(w)
    assert lines[0].startswith("Неделя 2026-11-12 — 2026-11-18: люди из Яндекса 2")
    assert "Строка «присылать»: показов 4 (4 чел.), нажатий 1 (1 чел.), 250,0 на 1 000 показов" in lines[2]
    assert "Нажал → открыл бота: 1" in lines[3]
    assert pa.memory_core(w)["week_bot_subs_from_site"] == 1


def test_week_block_is_visible_and_survives_old_or_broken_snapshot():
    from app.services import pulse_acquisition as pa
    from app.services.pulse_report import _acquisition_week_block

    assert _acquisition_week_block({}) == ""
    assert _acquisition_week_block({"acquisition_week": {"error": "OperationalError"}}) == ""
    assert pa.memory_core(None) == {}
    week = {"window": {"from": "2026-11-12", "to": "2026-11-18"}, "metrika": {"yandex_visits": 1900},
            "return": {"cohort": 4735, "by_self_pct": 1.4, "other_day_pct": 5.3,
                       "cohort_first_from": "2026-09-20", "cohort_first_to": "2026-10-19"},
            "line": {"views": 0, "clicks": 0}, "subscriptions": {}, "signups": {}, "people": {}}
    block = _acquisition_week_block({"acquisition_week": week})
    assert block.startswith("📈 <b>Привлечение за 7 дней</b>")
    assert "сами, не из поиска 1,4 %; в другой день 5,3 %" in block
    assert "на 1 000 показов" not in block  # без показов доли нет
    assert "&lt;" not in block and "<blockquote" not in block


def test_site_topic_codes_are_the_bot_topics_only():
    from app.services.public_bot import TOPICS
    from app.services.pulse_acquisition import site_topic_codes

    codes = site_topic_codes()
    assert len(codes) == len(TOPICS) == 10
    assert "site_inflation" in codes and "site_diesel" in codes
    assert "site_welcome" not in codes and "site_research" not in codes

"""Человек — только сессия с признаком живого посетителя (разбор Пульса за 17.11.2026, пункт 4).

Пульс назвал людьми семь заходов одной программы на английском хосте: Windows, Chrome, окно 1366×768,
главная, через 8–26 с одно нажатие «Sign up» в точку (1257, 72), указатель прыгает в кнопку одним
смещением (траектории нет), прокрутки нет. Счёт робота у них 0–20 из 60, поэтому до 18.11 они были «людьми».
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.services.bot_score import (
    BOT_THRESHOLD, SessionSignals, human_evidence, score_session, visitor_status,
)
from tests.test_analytics2 import _run_with_db

NOW = datetime.utcnow().replace(microsecond=0)


def _sig(**kw):
    base = dict(pageviews=1, clicks=0, moves=0, active_ms=0, max_scroll_pct=0, synthetic_clicks=0,
                visitor_sessions=1, has_portrait=True, device_type="desktop", cpu_cores=8,
                screen_w=1920, screen_h=1080, referrer="https://chatgpt.com/", timezone="America/New_York")
    base.update(kw)
    return SessionSignals(**base)


def _status(s: SessionSignals) -> str:
    return visitor_status(score_session(s), human_evidence(s))


def test_sign_up_program_is_not_a_person_and_not_a_proven_bot():
    # Две записанные формы того же сценария: с кликом в потоке (два pageview: главная и /register)
    # и без него (клик потерялся при переходе страницы, остался один pageview).
    for s in (_sig(pageviews=2, clicks=1, active_ms=785), _sig(pageviews=1, clicks=0, active_ms=0)):
        assert score_session(s) < BOT_THRESHOLD
        assert human_evidence(s) == []
        assert _status(s) == "unconfirmed"


def test_each_trace_of_a_live_visitor_confirms_a_person():
    cases = {
        "pointer_path": _sig(moves=1),
        "scroll": _sig(device_type="mobile", touch=True, max_scroll_pct=30),
        "sustained_input": _sig(active_ms=15_001),
        "two_clicks": _sig(clicks=2),
        "signed_in": _sig(signed_in=True),
    }
    for name, s in cases.items():
        assert human_evidence(s) == [name], name
        assert _status(s) == "human", name


def test_one_input_window_and_script_clicks_are_not_evidence():
    # Одно действие продлевает активность ровно на 15 с: этого мало для «двух действий в разные моменты».
    assert human_evidence(_sig(active_ms=15_000, clicks=1)) == []
    # Нажатия скрипта (isTrusted=false) не считаются нажатиями человека.
    assert human_evidence(_sig(clicks=3, synthetic_clicks=2)) == []
    assert human_evidence(_sig(clicks=3, synthetic_clicks=1)) == ["two_clicks"]


def test_bot_signal_wins_over_evidence():
    s = _sig(moves=4, max_scroll_pct=50, is_webdriver=True)
    assert human_evidence(s) == ["pointer_path", "scroll"]
    assert _status(s) == "bot"


def _ev(visitor, kind, seconds, **params):
    from app.models import BehaviorEvent

    return BehaviorEvent(visitor_id_hash=visitor, session_id_hash=visitor + "-tab", event_type=kind,
                         page="/", occurred_at=NOW - timedelta(minutes=30) + timedelta(seconds=seconds),
                         params_json=params or None, element_path="nav > a" if kind == "click" else None,
                         x=1257 if kind == "click" else None, y=72 if kind == "click" else None)


def _portrait(visitor, user_id=None):
    from app.models import BehaviorSession

    return BehaviorSession(session_id_hash=visitor + "-tab", visitor_id_hash=visitor, device_type="desktop",
                           channel="referral", started_at=NOW - timedelta(minutes=30), screen_w=1920, screen_h=1080,
                           viewport_w=1366, viewport_h=768, cpu_cores=8, is_synthetic=False, user_id=user_id,
                           referrer="https://chatgpt.com/", timezone="America/New_York", touch=False)


def test_sessionize_writes_is_human_and_pulse_splits_events_by_people():
    from app.models import FrontendEvent, ServerSession
    from app.services import pulse_people
    from app.tasks import analytics_rollups as rollups

    async def scenario(maker):
        async with maker() as db:
            db.add_all([
                # Программа «Sign up»: главная, одно нажатие, переход на /register.
                _ev("prog", "pageview", 0, ref="https://chatgpt.com/", vw=1366, touch=0),
                _ev("prog", "click", 19), _ev("prog", "dwell", 19, active_ms=527, scroll_pct=0),
                _ev("prog", "pageview", 20, ref="https://forecasteconomy.com/", vw=1366, touch=0),
                _portrait("prog"),
                FrontendEvent(event_name="header_register_click", session_id_hash="prog-tab", visitor_id_hash="prog",
                              occurred_at=NOW - timedelta(minutes=30) + timedelta(seconds=19)),
                # Человек: ведёт указатель, читает, нажимает «Регистрация».
                _ev("person", "pageview", 0, ref="https://ya.ru/", vw=1440, touch=0),
                _ev("person", "move", 5), _ev("person", "move", 9),
                _ev("person", "click", 40), _ev("person", "dwell", 41, active_ms=36_000, scroll_pct=40),
                _portrait("person"),
                FrontendEvent(event_name="header_register_click", session_id_hash="person-tab",
                              visitor_id_hash="person", occurred_at=NOW - timedelta(minutes=30) + timedelta(seconds=40)),
                # Событие фронта дошло, а клик поведенческого потока — нет: через 9 с после конца сессии.
                FrontendEvent(event_name="header_register_click", session_id_hash="prog-tab", visitor_id_hash="prog",
                              occurred_at=NOW - timedelta(minutes=30) + timedelta(seconds=29)),
            ])
            await db.commit()
        async with maker() as db:
            await rollups.sessionize(db, NOW - timedelta(days=1), NOW)
        async with maker() as db:
            rows = {r.visitor_id_hash: r for r in (await db.execute(select(ServerSession))).scalars()}
            start, end = NOW - timedelta(hours=2), NOW
            index = await pulse_people.load_index(db, start, end)
            people = await pulse_people.people_snapshot(db, start, end)
            events = await pulse_people.events_by_people(db, start, end, index, ["header_register_click"])
            return rows, people, events

    rows, people, events = _run_with_db(scenario)
    assert (rows["prog"].is_bot, rows["prog"].is_human) == (False, False)
    assert (rows["person"].is_bot, rows["person"].is_human) == (False, True)
    assert people["sessions"]["human"] == 1 and people["sessions"]["unconfirmed"] == 1
    assert people["human_visitors"] == 1
    assert events["header_register_click"] == {"people": 1, "people_sessions": 1, "unconfirmed": 2, "bot": 0,
                                               "internal": 0, "unknown": 0}


def test_index_status_and_unrated_sessions():
    from app.services.pulse_people import PeopleIndex, digits_line, memory_core, session_status

    t0 = NOW - timedelta(hours=3)
    index = PeopleIndex([
        ("v", t0, t0 + timedelta(minutes=10), False, False, True, 1),
        ("v", t0 + timedelta(minutes=60), t0 + timedelta(minutes=61), False, False, None, 2),
    ])
    assert index.find("v", t0 + timedelta(minutes=12)) == ("human", 1)       # в запасе 5 минут после конца
    assert index.find("v", t0 + timedelta(minutes=30)) == ("unknown", None)  # между сессиями
    assert index.find("v", t0 + timedelta(minutes=60, seconds=30)) == ("unknown", 2)
    assert index.find("w", t0) == ("unknown", None)
    assert session_status(True, False, True) == "bot" and session_status(False, True, True) == "internal"
    people = {"sessions": {"human": 3, "unconfirmed": 7, "bot": 20, "internal": 0, "unknown": 1}, "human_visitors": 2}
    assert digits_line(people) == ("Люди (есть признак живого посетителя): сессий 3, разных посетителей 2; "
                                   "не подтверждено 7, роботов 20, без оценки 1")
    assert digits_line(None) is None and memory_core({}) == {}
    assert memory_core(people) == {"people_sessions": 3, "unconfirmed_sessions": 7, "people_visitors": 2}


def test_report_prompt_explains_people_and_unconfirmed():
    from app.services import pulse_report

    source = open(pulse_report.__file__, encoding="utf-8").read()
    assert "people.sessions.human" in source and "заходы без признаков" in source
    people = {"sessions": {"human": 5, "unconfirmed": 9, "bot": 40}, "human_visitors": 4}
    assert "🧍 Люди (есть признак живого посетителя): сессий 5" in pulse_report._fallback_summary({"people": people})
    assert "Люди (есть признак" in pulse_report._raw_digits_block({"people": people})
    # Снимок до 18.11.2026 раздела не содержит: строки нет, сводка не падает.
    assert "Люди" not in pulse_report._fallback_summary({})

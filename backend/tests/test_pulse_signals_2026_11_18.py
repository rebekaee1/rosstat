"""Разбор Пульса за 17.11.2026: два ложных вывода отчёта, оба из-за того, как собраны цифры.

1. «46 dead- и 41 rage-клик по рейтингу регионов — главный сигнал дня»: все клики сделал один человек.
   Рядом с числом кликов теперь число сессий, первыми идут места, где ошиблось больше людей.
2. «106 писем, открытий нет, даже машинных — странно, вероятно спам»: счётчик открытий выключен намеренно
   (ADR-0034), ноль был не измерением. Теперь в снимке `open_tracking=false` и `opened_people=None`.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from tests.test_analytics2 import _run_with_db


def test_friction_tops_count_people_not_only_clicks():
    from app.models import BehaviorEvent
    from app.services.pulse import _friction_tops

    now = datetime.utcnow().replace(microsecond=0)

    def click(session: str, path: str, *, rage: bool = False, page: str = "/russia/region"):
        return BehaviorEvent(session_id_hash=session, event_type="click", occurred_at=now, page=page,
                             element_path=path, is_dead=True, is_rage=rage)

    async def scenario(maker):
        async with maker() as db:
            db.add_all([click("one-person", "ol.fe-rank__list", rage=True) for _ in range(46)])
            db.add_all([click(f"s{i}", "div.fe-brush__track", page="/russia/indicator/fuel-diesel") for i in range(4)])
            db.add(BehaviorEvent(session_id_hash="s9", event_type="click", occurred_at=now, page="/", element_path="a.ok"))
            await db.commit()
            return await _friction_tops(db, now - timedelta(hours=1), now + timedelta(hours=1))

    dead, rage = _run_with_db(scenario)
    # Место, где ошиблись четыре человека, стоит выше места, где 46 раз щёлкнул один.
    assert [(row["element"], row["n"], row["sessions"]) for row in dead] == [
        ("div.fe-brush__track", 4, 4), ("ol.fe-rank__list", 46, 1)]
    assert rage == [{"page": "/russia/region", "element": "ol.fe-rank__list", "n": 46, "sessions": 1}]


def test_report_prompt_tells_to_judge_by_people_and_not_by_missing_opens():
    from app.services import pulse_report

    source = open(pulse_report.__file__, encoding="utf-8").read()
    assert "sessions=1" in source and "open_tracking=false" in source


def test_digits_line_says_opens_are_not_counted():
    from app.services import pulse_extra

    campaign = {"campaign": "fe-weekly-01", "delivered": 106, "clicked_people": 1, "unsubscribed": 0}
    off = pulse_extra.digits_lines({"mail": {"open_tracking": False, "events": {"click": 2},
                                             "last_campaign": {**campaign, "opened_people": None}}})
    assert "Письма: открытия не считаем, переходов на сайт 2" in off
    assert ("Последний выпуск fe-weekly-01: дошло 106, открытия не считаем (счётчик выключен), "
            "перешли 1, отписались 0") in off
    assert not any("открыли 0" in line or "открытий людьми 0" in line for line in off)

    on = pulse_extra.digits_lines({"mail": {"open_tracking": True, "events": {"open": 3, "open_machine": 1, "click": 2},
                                            "last_campaign": {**campaign, "opened_people": 3}}})
    assert "Письма: открытий людьми 3, программами 1, переходов на сайт 2" in on
    assert any("открыли 3" in line for line in on)
    # Снимок, сохранённый до 18.11.2026, ключа не содержит: строка остаётся прежней.
    old = pulse_extra.digits_lines({"mail": {"events": {"click": 1}, "last_campaign": {**campaign, "opened_people": 0}}})
    assert any("открыли 0" in line for line in old)

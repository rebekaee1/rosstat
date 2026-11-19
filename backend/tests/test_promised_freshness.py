"""Сторож обещанной свежести (совет 19.11.2026, п. 4.3): правила по видам рядов и сообщение владельцу."""
from datetime import date, datetime

from app.services import promised_freshness as pf
from app.services.telegram_calm import _KIND_GROUP, HELD_KINDS, KIND_LABELS

FUEL = pf.PromisedTopic("diesel", "fuel-diesel", "Дизель", "fuel", "fuel-diesel")
GOLD = pf.PromisedTopic("gold", "gold-price", "Золото", "daily", "gold-price")
CPI = pf.PromisedTopic("inflation", "cpi-yoy", "Инфляция", "monthly", "cpi")


def test_topics_cover_every_bot_topic_with_kind():
    from app.services.public_bot import TOPICS

    topics = {t.key: t for t in pf.promised_topics()}
    assert set(topics) == set(TOPICS)
    assert topics["diesel"].kind == "fuel" and topics["gold"].kind == "daily"
    assert topics["inflation"].kind == "monthly" and topics["inflation"].load_code == "cpi"


def test_fuel_on_19_november_with_point_9_november_is_not_late_until_friday():
    # 19.11.2026 (чт): точка 9.11, бюллетень 18.11 не загружен. Четверг — ещё запас, пятница — опоздание.
    assert pf.judge(FUEL, today=date(2026, 11, 19), last_date=date(2026, 11, 9),
                    last_load_at=None, last_release=None).status == pf.STATUS_OK
    late = pf.judge(FUEL, today=date(2026, 11, 20), last_date=date(2026, 11, 9), last_load_at=None, last_release=None)
    assert late.status == pf.STATUS_LATE and "09.11" in late.reason


def test_daily_series_late_after_five_days():
    assert pf.judge(GOLD, today=date(2026, 11, 19), last_date=date(2026, 11, 15),
                    last_load_at=None, last_release=None).status == pf.STATUS_OK
    assert pf.judge(GOLD, today=date(2026, 11, 19), last_date=date(2026, 11, 14),
                    last_load_at=None, last_release=None).status == pf.STATUS_LATE


def test_monthly_series_late_when_release_passed_without_load():
    # ИПЦ за октябрь выходит 25.11: 27.11 без загрузки после 25.11 — опоздание; загрузка 25.11 вечером — норма.
    late = pf.judge(CPI, today=date(2026, 11, 27), last_date=date(2026, 9, 1),
                    last_load_at=datetime(2026, 10, 14, 20, 3), last_release=date(2026, 11, 25))
    assert late.status == pf.STATUS_LATE and late.release_date == date(2026, 11, 25)
    ok = pf.judge(CPI, today=date(2026, 11, 27), last_date=date(2026, 10, 1),
                  last_load_at=datetime(2026, 11, 25, 20, 3), last_release=date(2026, 11, 25))
    assert ok.status == pf.STATUS_OK


def test_monthly_without_calendar_uses_75_days_after_month_end():
    assert pf.judge(CPI, today=date(2026, 11, 19), last_date=date(2026, 9, 1),
                    last_load_at=None, last_release=None).status == pf.STATUS_OK
    assert pf.judge(CPI, today=date(2026, 12, 14), last_date=date(2026, 9, 1),
                    last_load_at=None, last_release=None).status == pf.STATUS_LATE


def test_message_lists_only_late_topics_and_goes_to_morning_digest():
    rows = [
        pf.judge(FUEL, today=date(2026, 11, 20), last_date=date(2026, 11, 9), last_load_at=None, last_release=None),
        pf.judge(GOLD, today=date(2026, 11, 20), last_date=date(2026, 11, 19), last_load_at=None, last_release=None),
    ]
    msg = pf.format_message(rows)
    assert "Дизель" in msg and "Золото" not in msg
    assert pf.signature(rows) == "diesel:2026-11-09"
    assert pf.format_message(rows[1:]) is None
    assert "promised_freshness" in HELD_KINDS and _KIND_GROUP["promised_freshness"] == "data"
    assert "promised_freshness" in KIND_LABELS

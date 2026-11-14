"""Портреты behavior_sessions в BI считаются без роботов (14.11.2026).

13-14.11.2026 карточка «Поисковые системы» показала ~1 800 переходов из Google в сутки при 7-13
в Метрике: ферма с Referer https://www.google.com/ исполняла JS и писала портреты, а запрос
поисковиков по портретам роботов не отсеивал. Инвариант: поисковики, срезы источников,
браузеры/экраны/пояса аудитории и гео идут только от посетителей без бот- и внутренних сессий.
"""
from datetime import date, datetime, timedelta

from app.models import BehaviorSession, ServerSession
from app.services.analytics_period import Period
from test_analytics2 import _run_with_db

DAY = date(2026, 11, 13)
START = datetime(2026, 11, 12, 21)  # 00:00 МСК
PERIOD = Period(START, START + timedelta(days=1), "custom", DAY, DAY)


def _portrait(sid, visitor, minute, **kw):
    base = dict(session_id_hash=sid, visitor_id_hash=visitor, started_at=START + timedelta(hours=8, minutes=minute),
                channel="search", referrer="https://www.google.com/", referrer_host="google.com",
                device_type="desktop", browser="Chrome", os="Linux", screen_w=1920, screen_h=1080,
                timezone="America/New_York", country="США", city="Ashburn")
    base.update(kw)
    return BehaviorSession(**base)


def _session(visitor, minute, *, bot):
    at = START + timedelta(hours=8, minutes=minute)
    return ServerSession(day=DAY, visitor_id_hash=visitor, started_at=at, ended_at=at, pageviews=1,
                         channel="search", device="desktop", is_bot=bot, bot_score=80 if bot else 0)


async def _seed(maker):
    async with maker() as db:
        for n in range(5):  # ферма: каждая вкладка — новый посетитель, сессия признана ботом
            db.add(_portrait(f"farm-{n}", f"farm-v{n}", n, cpu_cores=640))
            db.add(_session(f"farm-v{n}", n, bot=True))
        db.add(_portrait("human-g", "human-1", 10, referrer_host="google.ru", os="Windows",
                         timezone="Europe/Moscow", country="Россия", city="Москва", screen_w=1536, screen_h=864))
        db.add(_session("human-1", 10, bot=False))
        db.add(_portrait("human-y", "human-2", 11, referrer="https://yandex.ru/", referrer_host="yandex.ru",
                         os="Android", device_type="mobile", timezone="Europe/Moscow", country="Россия",
                         city="Казань", screen_w=412, screen_h=915))
        db.add(_session("human-2", 11, bot=False))
        await db.commit()


def test_search_engines_and_slices_skip_bot_portraits():
    from app.services.admin_bi import _own_acquisition

    async def scenario(maker):
        await _seed(maker)
        async with maker() as db:
            out = await _own_acquisition(db, PERIOD)
        assert sum(out["search_engines"].values()) == 2
        assert out["source_slices"] == {"search": 2}
        assert out["channels"] == {"search": 2}
    _run_with_db(scenario)


def test_audience_portraits_and_geo_skip_bot_portraits():
    from app.services.admin_bi import _audience
    from app.services.analytics_marts import mart_geo

    async def scenario(maker):
        await _seed(maker)
        async with maker() as db:
            aud = await _audience(db, PERIOD, [])
            geo = await mart_geo(db, PERIOD)
        assert aud["portraits_total"] == 2 and aud["own_sessions_total"] == 2
        assert "America/New_York" not in aud["timezones"]
        assert "1920×1080" not in aud["screens"]
        assert "google.com" not in aud["referrer_hosts"]
        assert geo["countries"] == {"Россия": 2}
    _run_with_db(scenario)

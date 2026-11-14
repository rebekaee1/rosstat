"""«Путь до упора» (14.11.2026): страницы сессии до упора, окно ≤ 30 дней, ограниченный запрос."""
import asyncio
import io
from datetime import date, datetime, timedelta

from openpyxl import load_workbook

from app.models import BehaviorEvent, Indicator
from app.services import download_content as dc

from tests.test_analytics2 import _run_with_db

T0 = datetime(2026, 11, 13, 9, 0)


def _row(**kw):
    base = {"wall": True, "at": T0, "person": "v1", "session": "s1", "title": "Цена дизельного топлива",
            "key": "ru|fuel-diesel||", "what": "таблица (лимит скачиваний)", "channel": "search",
            "signed_up_after": True, "section": "russia", "authed": False, "event": "download_limit",
            "page": "/russia/indicator/fuel-diesel", "device": "mobile", "country": ""}
    return {**base, **kw}


def test_build_paths_orders_dedupes_and_marks_same_download_after():
    rows = [
        _row(),
        _row(wall=False, at=T0 + timedelta(minutes=5), what="Excel", signed_up_after=None, event="download_excel"),
        _row(person="v2", session="s2", signed_up_after=False, at=T0 + timedelta(minutes=1)),
    ]
    views = [
        ("s1", "/", T0 - timedelta(minutes=9)),
        ("s1", "/russia/indicator/cpi", T0 - timedelta(minutes=8)),
        ("s1", "/russia/indicator/cpi?mode=yoy", T0 - timedelta(minutes=7)),  # повтор подряд не дублируется
        ("s1", "/russia/indicator/fuel-diesel", T0 - timedelta(minutes=1)),
        ("s1", "/russia/indicator/key-rate", T0 + timedelta(minutes=3)),  # после упора — не входит
    ]
    titles = {"/russia/indicator/cpi": "Инфляция", "/russia/indicator/fuel-diesel": "Цена дизельного топлива"}
    items = dc.build_paths(rows, views, titles)
    assert len(items) == 2
    first = items[0]
    assert first["path"] == ["главная", "Инфляция", "Цена дизельного топлива"] and first["pages_before"] == 4
    assert first["signed_up_after"] is True and first["same_after"] is True
    assert items[1]["path"] == [] and items[1]["same_after"] is False


def test_long_period_says_too_big_without_query():
    data = {"period": dc.period_for_window("90", date(2026, 11, 14)), "rows": [_row()]}

    class NoDb:
        async def execute(self, *_a, **_k):
            raise AssertionError("запрос не должен идти при периоде > 30 дней")

    paths = asyncio.run(dc.collect_paths(NoDb(), data))
    assert paths == {"status": "too_long", "items": []}
    book = dc.build_xlsx({**data, "paths": paths})
    ws = load_workbook(io.BytesIO(book))["Путь до упора"]
    assert ws["A2"].value.startswith("Слишком большой период")


def test_query_failure_becomes_a_sentence_not_an_error():
    data = {"period": dc.period_for_window("7", date(2026, 11, 14)), "rows": [_row()]}

    class Broken:
        bind = None

        async def execute(self, *_a, **_k):
            raise TimeoutError("canceling statement due to statement timeout")

        async def rollback(self):
            pass

    paths = asyncio.run(dc.collect_paths(Broken(), data))
    assert paths["status"] == "timeout"
    ws = load_workbook(io.BytesIO(dc.build_xlsx({**data, "paths": paths})))["Путь до упора"]
    assert "не успела ответить" in ws["A2"].value


def test_collect_paths_reads_session_pageviews_on_sqlite():
    now = datetime.utcnow().replace(microsecond=0)

    async def scenario(maker):
        async with maker() as db:
            db.add_all([
                Indicator(code="cpi", name="Инфляция"),
                BehaviorEvent(event_type="pageview", session_id_hash="s1", page="/russia/indicator/cpi",
                              occurred_at=now - timedelta(minutes=5)),
                BehaviorEvent(event_type="click", session_id_hash="s1", page="/russia/indicator/cpi",
                              occurred_at=now - timedelta(minutes=4)),
                BehaviorEvent(event_type="pageview", session_id_hash="other", page="/x",
                              occurred_at=now - timedelta(minutes=4)),
            ])
            await db.commit()
        today = (now + timedelta(hours=3)).date()
        data = {"period": dc.period_for_window("7", today), "rows": [_row(at=now)]}
        async with maker() as db:
            return await dc.collect_paths(db, data)

    paths = _run_with_db(scenario)
    assert paths["status"] == "ok" and not paths["cut"]
    assert paths["items"][0]["path"] == ["Инфляция"] and paths["items"][0]["pages_before"] == 1

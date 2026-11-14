"""Понедельник: блок «Что скачивали за неделю» в утреннем дайджесте вместо дневного (14.11.2026).
Отдельного сообщения нет — спокойный режим (telegram_calm, 08.11.2026)."""
import asyncio
from contextlib import asynccontextmanager
from datetime import date

from app.services import download_content as dc


def _summary(people_dl=3, people_wall=4, signed=1):
    rows = []
    for i in range(people_dl):
        rows.append({"wall": False, "key": "ru|cpi||", "title": "Инфляция", "section": "russia", "person": f"d{i}",
                     "what": "Excel", "authed": True, "signed_up_after": None, "channel": "search"})
    for i in range(people_wall):
        rows.append({"wall": True, "key": "ru|fuel-diesel||", "title": "Цена дизельного топлива", "section": "russia",
                     "person": f"w{i}", "what": "таблица (лимит скачиваний)", "authed": False,
                     "signed_up_after": i < signed, "channel": "search"})
    return dc.summarize(rows)


def test_week_block_compares_with_previous_week_and_shows_server_line():
    cur = _summary(3, 4, 1)
    cur["server"] = {"count": 6, "browser": 5, "items": []}
    lines = dc.week_digest_lines(cur, _summary(1, 6, 0), "09.11–15.11")
    text = "\n".join(lines)
    assert "Что скачивали за неделю (09.11–15.11)" in text
    assert "Скачали 3 человека (+2 к прошлой неделе)" in text
    assert "Упёрлись в лимит 4 человека (−2 к прошлой неделе), зарегистрировались 1 (25 %)" in text
    assert "сервер видел упоров 6 / браузер сообщил 5" in text
    assert "Чаще скачивали: Инфляция (3)" in text and "Чаще упирались: Цена дизельного топлива (4)" in text
    assert dc.week_digest_lines(dc.summarize([]), None, "x") == []


def test_monday_digest_uses_week_other_days_use_yesterday(monkeypatch):
    from app.tasks import analytics_scheduler as sched

    seen = []

    async def fake_collect(_db, period):
        seen.append((period.start_date, period.end_date))
        return {"summary": _summary()}

    @asynccontextmanager
    async def fake_session():
        yield None

    monkeypatch.setattr(dc, "collect", fake_collect)
    monkeypatch.setattr(sched, "analytics_session", fake_session)

    sunday = date(2026, 11, 8)  # дайджест понедельника 09.11 — за воскресенье (прошлая дата: resolve_period режет будущее)
    lines = asyncio.run(sched._download_content_lines(sunday))
    assert seen == [(date(2026, 11, 2), sunday), (date(2026, 10, 26), date(2026, 11, 1))]
    assert any("за неделю (02.11–08.11)" in line for line in lines)

    seen.clear()
    lines = asyncio.run(sched._download_content_lines(date(2026, 11, 13)))
    assert seen == [(date(2026, 11, 13), date(2026, 11, 13))]
    assert any("Что скачивали вчера" in line for line in lines)

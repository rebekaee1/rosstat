"""Роль «только отчёты» в служебном боте (14.11.2026): за флагом, список пуст, без персональных данных."""
import asyncio
import io
from datetime import date, datetime

from openpyxl import load_workbook

from app.config import settings
from app.services import alerting
from app.services import download_content as dc
from app.services import telegram_bot as tb

OWNER, GUEST = "42", "777"


def _setup(monkeypatch, *, enabled=True, ids=GUEST):
    monkeypatch.setattr(settings, "telegram_chat_id", OWNER, raising=False)
    monkeypatch.setattr(settings, "telegram_reports_only_enabled", enabled)
    monkeypatch.setattr(settings, "telegram_reports_only_chat_ids", ids)


def test_defaults_are_off_and_empty():
    assert settings.telegram_reports_only_enabled is False
    assert settings.telegram_reports_only_chat_ids == ""
    assert alerting.reports_only_ids() == set()


def test_flag_and_list_are_both_required_and_full_rights_win(monkeypatch):
    _setup(monkeypatch, enabled=False)
    assert alerting.reports_only_ids() == set()
    _setup(monkeypatch, ids=f" {GUEST} , {OWNER} ,")
    assert alerting.reports_only_ids() == {GUEST}  # владелец остаётся с полными правами


def _capture(monkeypatch):
    calls = []

    async def fake_api(method, payload, files=None):
        return {"ok": True, "result": []}

    async def fake_send(chat_id, text, reply_markup=None, **_kw):
        calls.append(("message", chat_id, text, reply_markup))
        return True

    async def fake_doc(chat_id, filename, content, caption="", **_kw):
        calls.append(("document", chat_id, filename, caption))
        return True

    async def fake_report(chat_id, window):
        calls.append(("report", chat_id, window))

    async def fake_file(chat_id, window, reports_only=False):
        calls.append(("file", chat_id, window, reports_only))

    async def fake_export(chat_id, kind, window, reports_only=False):
        calls.append((kind, chat_id, window, reports_only))

    monkeypatch.setattr(tb, "_api", fake_api)
    monkeypatch.setattr(tb, "send_message", fake_send)
    monkeypatch.setattr(tb, "send_document", fake_doc)
    monkeypatch.setattr(tb, "_send_downloads_report", fake_report)
    monkeypatch.setattr(tb, "_send_downloads_file", fake_file)
    monkeypatch.setattr(tb, "_send_export_file", fake_export)
    return calls


def _press(chat, data):
    asyncio.run(tb._handle_callback({"id": "1", "data": data, "message": {"chat": {"id": int(chat)}}}))


def test_reports_only_chat_gets_only_whitelisted_buttons(monkeypatch):
    _setup(monkeypatch)
    calls = _capture(monkeypatch)

    async def boom(*_a, **_k):
        raise AssertionError("персональные данные недоступны роли «только отчёты»")

    for name in ("_users_overview", "_users_csv", "_user_card", "_hypotheses_overview"):
        monkeypatch.setattr(tb, name, boom)

    for data in ("users", "users_csv", "user:abc", "pulse_today", "dataset", "hypotheses", "signups"):
        _press(GUEST, data)
    assert calls == []

    for data in ("dl:30", "dlx:7", "exs:30", "exv:7", "export", "menu"):
        _press(GUEST, data)
    kinds = [c[0] for c in calls]
    assert kinds == ["report", "file", "exs", "exv", "message", "message"]
    assert calls[1][3] is True and calls[2][3] is True and calls[3][3] is True  # файлы обезличены
    export_kb = calls[4][3]["inline_keyboard"]
    assert "users_csv" not in {b["callback_data"] for row in export_kb for b in row}
    menu = {b["callback_data"] for row in calls[5][3]["inline_keyboard"] for b in row}
    assert menu == {"dl:7", "export"}


def test_reports_only_messages_and_strangers(monkeypatch):
    _setup(monkeypatch)
    calls = _capture(monkeypatch)
    for text in ("/start", "/downloads 30", "/users", "/export"):
        asyncio.run(tb._handle_message({"chat": {"id": int(GUEST)}, "text": text}))
    assert [c[0] for c in calls] == ["message", "report", "message"]
    assert "отчёты" in calls[0][2]
    calls.clear()
    _setup(monkeypatch, enabled=False)
    _press(GUEST, "dl:7")
    asyncio.run(tb._handle_message({"chat": {"id": int(GUEST)}, "text": "/downloads"}))
    assert calls == []  # без флага чат никто


def test_owner_keeps_full_file(monkeypatch):
    _setup(monkeypatch)
    calls = _capture(monkeypatch)
    _press(OWNER, "dlx:7")
    assert calls == [("file", OWNER, "7", False)]


def test_anonymous_files_have_no_visitor_hashes():
    rows = [{"wall": True, "at": datetime(2026, 11, 13, 9), "event": "download_limit", "what": "x", "title": "T",
             "key": "k", "section": "russia", "page": "/p", "authed": False, "person": "abcdef1234567",
             "session": "s", "signed_up_after": False, "channel": "search", "device": "mobile", "country": "Россия"}]
    data = {"period": dc.period_for_window("7", date(2026, 11, 14)), "rows": rows,
            "paths": {"status": "ok", "items": dc.build_paths(rows, [], {})}}
    for anonymous, expect in ((False, True), (True, False)):
        wb = load_workbook(io.BytesIO(dc.build_xlsx(data, anonymous=anonymous)))
        text = repr([c.value for ws in wb for r in ws.iter_rows() for c in r])
        assert ("abcdef1234" in text) is expect


def test_anonymous_events_csv_drops_visitor_hash():
    from datetime import timedelta

    from app.models import FrontendEvent
    from app.services import bot_exports
    from tests.test_analytics2 import _run_with_db

    now = datetime.utcnow().replace(microsecond=0)

    async def scenario(maker):
        async with maker() as db:
            db.add(FrontendEvent(event_name="indicator_view", occurred_at=now, session_id_hash="s",
                                 visitor_id_hash="visitorhash123", url="https://ru.forecasteconomy.com/x",
                                 params_json={"indicator": "cpi"}))
            await db.commit()
        period = dc.period_for_window("7", (now + timedelta(hours=3)).date())
        async with maker() as db:
            full = await bot_exports.events_csv(db, period)
            anon = await bot_exports.events_csv(db, period, anonymous=True)
        return full[0].decode("utf-8-sig"), anon[0].decode("utf-8-sig")

    full, anon = _run_with_db(scenario)
    assert "visitorhas" in full and "visitorhas" not in anon and "indicator_view" in anon

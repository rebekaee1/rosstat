"""Контекст проекта для аналитика Пульса (14.11.2026): записи, журнал выпусков, флаги, остаток, страж."""
import asyncio
import importlib.util
import json
import re
from datetime import date
from pathlib import Path

from app.services import pulse_context
from app.services.pulse_context import Entry, build_block, load_entries, release_date_of

TODAY = date(2026, 11, 20)
RELEASES = [
    {"sha": "aaaa1111", "date": "2026-11-10", "lines": ["aaaa1111 fix: старое"], "more": 0},
    {"sha": "bbbb2222", "date": "2026-11-18", "lines": [f"a5d7194{i} fix: правка {i}" for i in range(20)], "more": 3},
]


def _entry(i, d, until=None, commit=None, expect="что ждать"):
    return Entry(id=f"e{i}", date=d, kind="смена счёта метрик", title=f"заголовок {i}", expect=expect,
                 until=until, commit=commit)


def test_repository_entries_are_valid_and_free_of_pii():
    entries = load_entries()
    assert entries, "в репозитории должны быть записи контекста"
    assert len({e.id for e in entries}) == len(entries)
    raw = pulse_context.ENTRIES_PATH.read_text(encoding="utf-8")
    assert not re.search(r"[\w.+-]+@[\w-]+\.\w", raw), "почта в контексте"
    assert not re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", raw), "IP в контексте"
    assert not re.search(r"(?:sk-|Bearer |token=|secret)", raw, re.IGNORECASE), "похоже на ключ"
    for e in entries:
        assert e.kind and e.title and re.fullmatch(r"[a-z0-9-]+", e.id)
    ids = {e.id for e in entries}
    assert {"bot-filter-google-farm", "adr-0031-apex-google", "openrouter-topup", "rosstat-partial-outage"} <= ids


def test_release_date_comes_from_release_log_by_short_sha():
    assert release_date_of("a5d71940", RELEASES) == date(2026, 11, 18)
    assert release_date_of("ffffffff", RELEASES) is None
    assert release_date_of(None, RELEASES) is None


def test_block_has_releases_flags_balance_and_active_entries_only():
    entries = [
        _entry(1, date(2026, 11, 14), commit="a5d71940"),       # выпущена 18.11
        _entry(2, date(2026, 9, 1)),                             # старше 45 дней, без until - не показывать
        _entry(3, date(2026, 9, 1), until=date(2026, 12, 31)),  # старая, но действует
        _entry(4, date(2026, 11, 1), until=date(2026, 11, 15)),  # истекла
    ]
    block = build_block(TODAY, entries=entries, releases=RELEASES, flags=["telegram_calm_mode=true"], balance=1.5)
    assert "2026-11-18 выпуск bbbb2222" in block
    assert block.count("· a5d7194") == 15 and "и ещё 8" in block       # 15 строк + 5 сверх + 3 в журнале
    assert "Режимы и флаги сейчас: telegram_calm_mode=true" in block
    assert "Остаток счёта OpenRouter: $1.50 — мало" in block
    assert "[e1] выпущено 18.11.2026" in block and "[e3]" in block
    assert "[e2]" not in block and "[e4]" not in block


def test_block_is_bounded_and_drops_detail_first():
    entries = [_entry(i, date(2026, 11, 1), expect="х" * 280) for i in range(40)]
    block = build_block(TODAY, entries=entries, releases=[], flags=[], balance=None)
    assert len(block) <= pulse_context.MAX_BLOCK_CHARS
    assert "[e39]" in block


def test_block_is_scrubbed_and_empty_without_knowledge():
    e = _entry(1, date(2026, 11, 14), expect="писать на owner@example.com или +7 912 345-67-89")
    block = build_block(TODAY, entries=[e], releases=[], flags=[], balance=None)
    assert "owner@example.com" not in block and "345-67-89" not in block
    assert build_block(TODAY, entries=[], releases=[], flags=[], balance=None) == ""


def test_flags_whitelist_has_no_secrets(monkeypatch):
    monkeypatch.setattr(pulse_context.settings, "telegram_calm_mode", True, raising=False)
    lines = pulse_context.flag_lines()
    assert "telegram_calm_mode=true" in lines
    assert not any(h in name for name in pulse_context.FLAG_WHITELIST for h in pulse_context._SECRET_HINTS)


def test_balance_is_a_number_and_key_never_logged(monkeypatch, caplog):
    import httpx

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def get(self, url, headers):
            assert url.endswith("/api/v1/credits") and headers["Authorization"] == "Bearer fixture-key"
            return httpx.Response(200, json={"data": {"total_credits": 25, "total_usage": 22.6}})

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    monkeypatch.setattr(pulse_context.settings, "openrouter_api_key", "fixture-key")
    with caplog.at_level("INFO"):
        assert asyncio.run(pulse_context.openrouter_balance()) == 2.4
    assert "fixture-key" not in caplog.text


def test_llm_input_starts_with_project_context():
    from app.services.pulse_report import _SYSTEM_PROMPT, build_llm_user_content

    content = build_llm_user_content({"users": {}}, [], [], "Последние выпуски на боевом:\n- x")
    assert content.startswith("Контекст проекта:\nПоследние выпуски на боевом:")
    assert "Снапшот за отчётный день" in content
    assert "закрой" in _SYSTEM_PROMPT and "[id]" in _SYSTEM_PROMPT


def _guard():
    path = Path(__file__).resolve().parents[2] / "scripts/check-pulse-context.py"
    spec = importlib.util.spec_from_file_location("check_pulse_context", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_guard_warns_without_entry_and_never_fails(tmp_path, monkeypatch, capsys):
    mod = _guard()
    answers = {("log",): "abc1234\ndef5678", ("show",): "2026-11-14"}
    monkeypatch.setattr(mod, "git", lambda *a: answers[(a[0],)])
    ctx = tmp_path / "ctx.yaml"
    ctx.write_text("entries:\n  - id: old\n    date: 2026-10-01\n    kind: x\n    title: y\n", encoding="utf-8")
    monkeypatch.setattr(mod, "CONTEXT", ctx)
    assert mod.main(["x", "base"]) == 0
    assert "ВНИМАНИЕ pulse-context" in capsys.readouterr().out
    ctx.write_text("entries:\n  - id: new\n    date: 2026-11-14\n    kind: x\n    title: y\n", encoding="utf-8")
    assert mod.main(["x", "base"]) == 0
    assert "ок" in capsys.readouterr().out
    ctx.write_text("entries:\n  - id: c\n    date: 2026-10-01\n    kind: x\n    title: y\n    commit: def5678\n",
                   encoding="utf-8")
    assert mod.main(["x", "base"]) == 0
    assert "ок" in capsys.readouterr().out


def test_release_log_script_keeps_only_subjects(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[2] / "scripts/release-log.py"
    spec = importlib.util.spec_from_file_location("release_log", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    class R:
        def __init__(self, out):
            self.stdout = out

    def fake_run(args, **kw):
        if args[1] == "log":
            return R("abcdef12 chore(deploy): одобрить abc\nbbbbbbb1 docs(knowledge): карты\n"
                     "ccccccc2 fix: письмо от a@b.ru\n" + "".join(f"d{i:07d} feat: {i}\n" for i in range(20)))
        return R("feedbeef\n")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    out = tmp_path / "rl.json"
    out.write_text(json.dumps({"releases": [{"sha": f"s{i}", "date": "2026-11-01", "lines": []} for i in range(7)]}))
    data = mod.update(out, "prev", "new", "2026-11-18")
    last = data["releases"][-1]
    assert len(data["releases"]) == mod.MAX_RELEASES
    assert last == {"sha": "feedbeef", "date": "2026-11-18", "lines": last["lines"], "more": 6}
    assert last["lines"][0] == "ccccccc2 fix: письмо от [почта]"
    assert len(last["lines"]) == 15 and not any("одобрить" in x or "docs(knowledge)" in x for x in last["lines"])


# --- заметки владельца из бота -----------------------------------------------------------------------------------


def test_parse_command_latin_command_and_russian_text_trigger():
    from app.services.pulse_context import parse_command

    assert parse_command("/context") == ("list", None, None)
    assert parse_command("/context@forecast_bot список") == ("list", None, None)
    assert parse_command("контекст удалить 3") == ("delete", 3, None)
    kind, text, until = parse_command("Контекст: пополнил OpenRouter на $20 до 25.11.2026")
    assert kind == "add" and text == "пополнил OpenRouter на $20" and until == date(2026, 11, 25)
    assert parse_command("/context выпуск ферма") == ("add", "выпуск ферма", None)
    assert parse_command("дизель") is None
    assert parse_command("/contextual") is None


def test_notes_add_list_delete_and_scrub(monkeypatch):
    from tests.test_analytics2 import _run_with_db

    async def scenario(maker):
        monkeypatch.setattr("app.database.async_session", maker)
        r1 = await pulse_context.handle_owner_command("/context договорились с партнёром, пишите на a@b.ru до 30.12")
        r2 = await pulse_context.handle_owner_command("контекст выпустили фильтр фермы")
        listing = await pulse_context.handle_owner_command("/context")
        gone = await pulse_context.handle_owner_command("/context удалить 1")
        again = await pulse_context.handle_owner_command("/context удалить 1")
        async with maker() as db:
            notes = await pulse_context.active_notes(db, date(2026, 11, 20))
        return r1, r2, listing, gone, again, notes

    r1, r2, listing, gone, again, notes = _run_with_db(scenario)
    assert "заметка 1" in r1 and "30.12" in r1 and "заметка 2" in r2
    assert "a@b.ru" not in listing and "выпустили фильтр фермы" in listing
    assert gone == "🧭 Заметка 1 удалена." and again == "Заметки 1 нет."
    assert [n.text for n in notes] == ["выпустили фильтр фермы"]
    block = build_block(TODAY, entries=[], releases=[], flags=[], balance=None, notes=notes)
    assert "Заметки владельца" in block and "[заметка 2]" in block


def test_owner_chat_context_is_handled_and_stranger_is_not(monkeypatch):
    from app.services import telegram_bot as tb

    sent = []

    async def fake_send(chat_id, text, reply_markup=None, kind="bot_reply"):
        sent.append((chat_id, text))
        return True

    async def fake_handle(raw):
        return f"ответ на {raw}"

    monkeypatch.setattr(tb, "interactive_authorized_ids", lambda: {"42"})
    monkeypatch.setattr(tb, "send_message", fake_send)
    monkeypatch.setattr(pulse_context, "handle_owner_command", fake_handle)
    monkeypatch.setattr(tb.settings, "public_bot_enabled", True, raising=False)
    monkeypatch.setattr(tb.settings, "public_bot_token", "", raising=False)
    asyncio.run(tb._handle_message({"chat": {"id": 42}, "text": "Контекст: Выпуск 18.11"}))
    assert sent == [("42", "ответ на Контекст: Выпуск 18.11")]
    assert tb._is_public_message("42", "/context") is False
    sent.clear()
    routed = []

    async def public(msg):
        routed.append(msg["text"])

    from app.services import public_bot
    monkeypatch.setattr(public_bot, "handle_message", public)
    asyncio.run(tb._handle_message({"chat": {"id": 999}, "text": "/context чужой"}))
    assert sent == [] and routed == ["/context чужой"]

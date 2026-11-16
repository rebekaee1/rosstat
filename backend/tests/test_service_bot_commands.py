"""Меню команд служебного бота только в чате владельца (BotCommandScopeChat, 14.11.2026)."""
import asyncio
import importlib.util
from pathlib import Path

from app.config import settings
from app.services import telegram_bot as tb

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "service-bot-commands.py"


def _script():
    spec = importlib.util.spec_from_file_location("service_bot_commands", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_commands_go_only_to_owner_chat_scope(monkeypatch):
    monkeypatch.setattr(settings, "telegram_chat_id", "433221767", raising=False)
    monkeypatch.setattr(settings, "telegram_reports_only_enabled", False)
    calls = tb.service_command_calls()
    assert calls == [("setMyCommands", {"commands": tb.OWNER_COMMANDS,
                                        "scope": {"type": "chat", "chat_id": 433221767}})]
    assert all(c[1]["scope"]["type"] == "chat" for c in calls)  # не all_private_chats, не default
    assert tb.service_command_calls(reset=True) == [
        ("deleteMyCommands", {"scope": {"type": "chat", "chat_id": 433221767}})]
    # Каждая команда меню обрабатывается ботом.
    for c in tb.OWNER_COMMANDS:
        assert f"/{c['command']}" in tb._ADMIN_TEXTS + tb._EXPORT_COMMANDS + tb._DOWNLOAD_COMMANDS + tb._CONTEXT_COMMANDS \
            + tb._MAIL_COMMANDS


def test_reports_only_chats_get_short_menu(monkeypatch):
    monkeypatch.setattr(settings, "telegram_chat_id", "42", raising=False)
    monkeypatch.setattr(settings, "telegram_reports_only_enabled", True)
    monkeypatch.setattr(settings, "telegram_reports_only_chat_ids", "777")
    calls = tb.service_command_calls()
    assert [c[1]["scope"]["chat_id"] for c in calls] == [42, 777]
    assert calls[1][1]["commands"] == tb.REPORTS_ONLY_COMMANDS
    assert "users" not in {c["command"] for c in tb.REPORTS_ONLY_COMMANDS}


def test_script_dry_run_sends_nothing_and_apply_uses_service_token_only(monkeypatch, capsys):
    monkeypatch.setattr(settings, "telegram_chat_id", "42", raising=False)
    monkeypatch.setattr(settings, "telegram_reports_only_enabled", False)
    mod = _script()
    sent = []

    async def fake_api(method, payload, files=None, token=None, timeout=None):
        sent.append((method, payload, token))
        return {"ok": True, "result": True}

    monkeypatch.setattr(mod, "_api", fake_api)
    assert asyncio.run(mod.main([])) == 0
    assert sent == [] and "Показ без отправки" in capsys.readouterr().out
    assert asyncio.run(mod.main(["--apply"])) == 0
    assert sent == [("setMyCommands", {"commands": tb.OWNER_COMMANDS, "scope": {"type": "chat", "chat_id": 42}}, None)]
    # Токен не передаётся → _api берёт служебный; токен публичного бота в скрипте не упоминается.
    assert "public_bot_token" not in SCRIPT.read_text() and "PUBLIC_BOT_TOKEN`) не трогается" in SCRIPT.read_text()


def test_public_bot_setup_keeps_its_own_scope():
    """Публичный бот задаёт команды всем личным чатам своим токеном; служебное меню — только чат владельца."""
    text = (SCRIPT.parents[0] / "public-bot-setup.py").read_text()
    assert '"all_private_chats"' in text

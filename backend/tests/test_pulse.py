"""Тесты «пульса» (П9б): память, оформление отчёта, безопасность бота."""
import asyncio

from app.services.pulse import memory_core
from app.services.pulse_report import _fallback_summary, _raw_digits_block
from app.services.telegram_bot import main_menu_keyboard


SNAP = {
    "date": "2026-07-01",
    "users": {"total": 12, "new": 2, "new_list": [], "newsletter": 5},
    "auth": {"login": 4, "register": 2},
    "events": {
        "total": 150,
        "by_name": {"indicator_view": 60, "scroll_depth": 40},
        "top_indicators": {"cpi": 20, "gdp-real": 10},
        "top_regions": {"moskva": 7},
        "downloads": {"download_csv": 3, "chart_image_download": 1},
        "errors": {"error_reload": 2},
        "search_top": {"инфляция": 5},
        "search_zero_results": {"биткоин к рублю": 2},
    },
    "etl": {"by_status": {"success": {"runs": 100, "records": 40}}, "failed_indicator_ids": [3]},
    "data": {"new_points": 40},
}


def test_memory_core_is_compact():
    core = memory_core(SNAP)
    assert core == {
        "date": "2026-07-01",
        "users_total": 12,
        "users_new": 2,
        "events": 150,
        "downloads": 4,
        "errors": 2,
        "etl_failed": 1,
        "new_points": 40,
    }


def test_fallback_summary_mentions_key_numbers():
    text = _fallback_summary(SNAP)
    assert "12" in text and "Скачиваний: 4" in text and "Ошибок фронта: 2" in text


def test_raw_digits_uses_expandable_blockquote():
    block = _raw_digits_block(SNAP)
    assert block.startswith("<blockquote expandable>")
    assert block.endswith("</blockquote>")
    assert "инфляция" in block
    assert "биткоин к рублю" in block  # zero-result запросы = пробелы каталога


def test_main_menu_has_users_and_pulse_buttons():
    kb = main_menu_keyboard()
    datas = [b["callback_data"] for row in kb["inline_keyboard"] for b in row]
    assert {"users", "users_csv", "pulse_today"} <= set(datas)


def test_poller_ignores_foreign_chat(monkeypatch):
    """Callback из чужого чата подтверждается, но данные не отправляются."""
    from app.services import telegram_bot as tb

    calls = []

    async def fake_api(method, payload, files=None):
        calls.append(method)
        return {"ok": True, "result": []}

    monkeypatch.setattr(tb, "_api", fake_api)
    monkeypatch.setattr(tb.settings, "pulse_chat_id", "433221767")

    asyncio.run(tb._handle_callback({
        "id": "1",
        "data": "users_csv",
        "message": {"chat": {"id": 999}},
    }))
    # только answerCallbackQuery, никакого sendDocument
    assert calls == ["answerCallbackQuery"]

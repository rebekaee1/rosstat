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
        "by_audience": {"authed": 40, "guest": 110},
        "downloads_by_audience": {"authed": 3, "guest": 1},
        "top_indicators": {"cpi": 20, "gdp-real": 10},
        "top_regions": {"moskva": 7},
        "downloads": {"download_csv": 3, "chart_image_download": 1},
        "errors": {"error_reload": 2},
        "search_top": {"инфляция": 5},
        "search_zero_results": {"биткоин к рублю": 2},
    },
    "audience": {"authed_active": 6, "guest_sessions": 44},
    "etl": {"by_status": {"success": {"runs": 100, "records": 40}}, "failed_indicator_ids": [3]},
    "data": {"new_points": 40},
    "behavior": {
        "by_type": {"pageview": 200, "click": 90, "dwell": 180, "move": 60, "copy": 4},
        "pageviews_top": {"/indicator/cpi": 50},
        "clicks_top": [{"element": "main > button[Прогноз]", "text": "Прогноз", "n": 30}],
        "dead_clicks_top": [{"element": "div.chart", "text": None, "n": 7}],
        "rage_clicks_top": [{"page": "/compare", "element": "button.add", "n": 5}],
        "dwell_by_page": {"/indicator/cpi": {"visits": 40, "avg_seconds": 65.0, "avg_scroll_pct": 72}},
        "copied_top": {"8.4%": 3},
    },
    "acquisition": {
        "traffic_sources": {
            "Переходы по рекламе": {"id": "ad", "visits": 130, "users": 110},
            "Переходы из поисковых систем": {"id": "organic", "visits": 120, "users": 100},
            "Прямые заходы": {"id": "direct", "visits": 30, "users": 25},
        },
        "search_engines": {"Яндекс": {"id": "yandex", "visits": 110, "users": 95}},
        "search_phrases_top": [
            {"phrase": "инфляция в россии 2026", "engine": "Яндекс", "visits": 12},
            {"phrase": "курс доллара прогноз", "engine": "Яндекс", "visits": 8},
        ],
        "raw_visits": {"total": 280, "by_source": {"ad": 130, "organic": 120, "direct": 30}},
    },
}


def test_memory_core_is_compact():
    core = memory_core(SNAP)
    assert core == {
        "date": "2026-07-01",
        "users_total": 12,
        "users_new": 2,
        "events": 150,
        "downloads": 4,
        "downloads_authed": 3,
        "downloads_guest": 1,
        "authed_active": 6,
        "guest_sessions": 44,
        "errors": 2,
        "etl_failed": 1,
        "new_points": 40,
        "behavior_clicks": 90,
        "behavior_dead": 7,
        "behavior_rage": 5,
        "metrika_visits": 280,
        "metrika_ad_visits": 130,
    }


def test_fallback_summary_mentions_key_numbers():
    text = _fallback_summary(SNAP)
    assert "12" in text and "Скачиваний: 4" in text and "Ошибок фронта: 2" in text


def test_fallback_summary_splits_audience():
    """Отчёт обязан разделять зарегистрированных и гостей (ключевое требование)."""
    text = _fallback_summary(SNAP)
    assert "зарег. 40" in text and "гости 110" in text  # события
    assert "зарег. 6" in text and "гостей 44" in text    # активная аудитория


def test_raw_digits_reports_audience():
    block = _raw_digits_block(SNAP)
    assert "Аудитория:" in block
    assert "зарег/гость 40/110" in block


def test_raw_digits_uses_expandable_blockquote():
    block = _raw_digits_block(SNAP)
    assert block.startswith("<blockquote expandable>")
    assert block.endswith("</blockquote>")
    assert "инфляция" in block
    assert "биткоин к рублю" in block  # zero-result запросы = пробелы каталога


def test_raw_digits_reports_acquisition():
    """Блок сырых цифр обязан показывать источники Метрики и поисковые фразы."""
    block = _raw_digits_block(SNAP)
    assert "Источники (Метрика):" in block
    assert "Переходы по рекламе: 130" in block
    assert "инфляция в россии 2026" in block


def test_main_menu_has_users_and_pulse_buttons():
    kb = main_menu_keyboard()
    datas = [b["callback_data"] for row in kb["inline_keyboard"] for b in row]
    assert {"users", "users_csv", "pulse_today", "dataset", "hypotheses"} <= set(datas)


def test_split_llm_output_extracts_hypotheses():
    from app.services.pulse_report import _split_llm_output

    content = (
        "День обычный, трафик стабильный.\n---HYPOTHESES---\n"
        '[{"id": null, "statement": "Фразы про НДФЛ дают визиты без раздела", '
        '"verdict": null, "confidence": 0.6, "rationale": "12 визитов по фразе"}]'
    )
    text, updates = _split_llm_output(content)
    assert text == "День обычный, трафик стабильный."
    assert len(updates) == 1
    assert updates[0]["statement"].startswith("Фразы про НДФЛ")


def test_split_llm_output_without_separator_is_plain_text():
    from app.services.pulse_report import _split_llm_output

    text, updates = _split_llm_output("Просто текст отчёта.")
    assert text == "Просто текст отчёта." and updates == []


def test_parse_visits_tsv():
    from app.services.metrika_acquisition import parse_visits_tsv

    tsv = (
        "ym:s:visitID\tym:s:date\tym:s:lastTrafficSource\n"
        "123\t2026-07-02\tad\n"
        "456\t2026-07-02\torganic\n"
        "битая строка без табов\n"
    )
    rows = parse_visits_tsv(tsv)
    assert len(rows) == 2
    assert rows[0]["ym:s:visitID"] == "123"
    assert rows[1]["ym:s:lastTrafficSource"] == "organic"


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

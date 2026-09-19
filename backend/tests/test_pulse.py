"""Тесты «пульса» (П9б): память, оформление отчёта, безопасность бота."""
import asyncio
import os
import tempfile
from datetime import date, datetime

from app.services.pulse import ETL_ERROR_STATUSES, _day_bounds, _etl_snapshot, memory_core
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


def test_etl_snapshot_sees_failed_and_timeout():
    """Регрессия Б-1: Пульс был слеп к ошибкам ETL.

    Парсеры и планировщик пишут статусы "failed"/"timeout" (base_parser.py:142,
    tasks/scheduler.py:68,77), а Пульс фильтровал по несуществующему "error" и
    рапортовал «0 ошибок» при реальных провалах. Тест кормит _etl_snapshot всеми
    боевыми статусами и требует, чтобы оба ошибочных попали в failed-список.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.models import Base, FetchLog

    assert set(ETL_ERROR_STATUSES) == {"failed", "timeout"}

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        sync_engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(sync_engine)
        sync_engine.dispose()

        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        Session = async_sessionmaker(engine, expire_on_commit=False)
        d = date(2026, 7, 6)
        ts = datetime(2026, 7, 6, 6, 0)

        async def run() -> dict:
            async with Session() as db:
                db.add_all([
                    FetchLog(indicator_id=1, status="success", started_at=ts, records_added=5),
                    FetchLog(indicator_id=2, status="no_new_data", started_at=ts, records_added=0),
                    FetchLog(indicator_id=3, status="failed", started_at=ts, records_added=0),
                    FetchLog(indicator_id=4, status="timeout", started_at=ts, records_added=0),
                ])
                await db.commit()
                start, end = _day_bounds(d)
                snap = await _etl_snapshot(db, start, end)
            await engine.dispose()
            return snap

        snap = asyncio.run(run())
        assert sorted(snap["failed_indicator_ids"]) == [3, 4]
        assert snap["by_status"]["failed"]["runs"] == 1
        assert snap["by_status"]["timeout"]["runs"] == 1
        assert snap["by_status"]["success"]["records"] == 5
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


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
        "metrika_organic_visits": 120,
        "metrika_campaign_rows": None,
        "metrika_campaign_visits": None,
        "acquisition_metadata": None,
        "seo_indexed_share_pct": None,
        "seo_searchable_pages": None,
    }


def test_acquisition_warehouse_preserves_zero_missing_failed_and_stale(tmp_path, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "analytics_allowed_counter_ids", "test")
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.models import (
        AnalyticsSyncRun, MetrikaReportSnapshot, MetrikaSearchPhrase, RawMetrikaVisit,
    )
    from app.services.pulse import _acquisition_from_warehouse

    async def run():
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'acq.db'}")
        async with engine.begin() as conn:
            for model in (AnalyticsSyncRun, MetrikaReportSnapshot, MetrikaSearchPhrase, RawMetrikaVisit):
                await conn.run_sync(model.__table__.create)
        Session = async_sessionmaker(engine, expire_on_commit=False)
        async with Session() as db:
            missing = await _acquisition_from_warehouse(db, date(2026, 9, 18))
            assert missing["metadata"]["reports"]["traffic_sources"]["status"] == "missing"
            db.add(MetrikaReportSnapshot(
                counter_id="test", report_type="traffic_sources", query_hash="zero",
                date_from=date(2026, 9, 18), date_to=date(2026, 9, 18),
                captured_at=datetime(2026, 9, 19, 5), response_json={"data": [], "total_rows": 0},
            ))
            await db.commit()
            zero = await _acquisition_from_warehouse(db, date(2026, 9, 18))
            assert zero["traffic_sources"] == {}
            assert zero["metadata"]["reports"]["traffic_sources"]["status"] == "available"
            assert memory_core({**SNAP, "acquisition": zero})["metrika_ad_visits"] == 0
            stale = await _acquisition_from_warehouse(db, date(2026, 9, 19))
            assert "traffic_sources" not in stale
            assert stale["metadata"]["reports"]["traffic_sources"]["status"] == "stale"
            assert stale["metadata"]["reports"]["traffic_sources"]["date_to"] == "2026-09-18"
            db.add(AnalyticsSyncRun(
                source="yandex_metrika", job_type="daily_acquisition_reports", status="failed",
                date_from=date(2026, 9, 19), date_to=date(2026, 9, 19),
                started_at=datetime(2026, 9, 20, 5), error_message="fixture failure",
            ))
            await db.commit()
            failed = await _acquisition_from_warehouse(db, date(2026, 9, 19))
            assert failed["metadata"]["sync"]["status"] == "failed"
            assert failed["metadata"]["reports"]["traffic_sources"]["status"] == "failed"
            assert memory_core({**SNAP, "acquisition": failed})["metrika_ad_visits"] is None
            db.add(MetrikaReportSnapshot(
                counter_id="test", report_type="traffic_sources", query_hash="null",
                date_from=date(2026, 9, 19), date_to=date(2026, 9, 19),
                captured_at=datetime(2026, 9, 20, 6), response_json={"data": [{
                    "dimensions": [{"id": "ad", "name": "Ads"}], "metrics": [None, None],
                }]},
            ))
            db.add(MetrikaReportSnapshot(
                counter_id="another-counter", report_type="traffic_sources", query_hash="foreign",
                date_from=date(2026, 9, 19), date_to=date(2026, 9, 19),
                captured_at=datetime(2026, 9, 20, 7), response_json={"data": []},
            ))
            await db.commit()
            partial = await _acquisition_from_warehouse(db, date(2026, 9, 19))
            assert partial["metadata"]["sync"]["status"] == "failed"
            assert partial["metadata"]["reports"]["traffic_sources"]["status"] == "available"
            assert partial["traffic_sources"]["Ads"]["visits"] is None
            assert memory_core({**SNAP, "acquisition": partial})["metrika_ad_visits"] is None
            assert "Ads: нет данных" in _raw_digits_block({**SNAP, "acquisition": partial})
        await engine.dispose()

    asyncio.run(run())


def test_pulse_acquisition_zero_and_revenue_are_separate():
    snap = {**SNAP, "acquisition": {"traffic_sources": {}, "ad_campaigns": {}},
            "marts": {"partner_revenue": {
                "connected": True, "total_revenue_rub": 999.99,
                "days": [{"day": SNAP["date"], "revenue_rub": 12.34, "shows": 88, "hits": 19}],
            }}}
    for render in (_fallback_summary, _raw_digits_block):
        text = render(snap)
        assert "Платное привлечение: 0 визитов" in text
        assert "Органический поиск: 0 визитов" in text
        assert "UTM-кампании: строк отчёта 0" in text
        assert "Доход РСЯ за отчётный день: 12.34 руб." in text
        assert "999.99" not in text
        assert "Директ:" not in text
        assert "остановка кампании" not in text
    snap["marts"]["partner_revenue"]["days"] = []
    assert "Доход РСЯ: нет данных за отчётный день" in _fallback_summary(snap)


def test_acquisition_quality_labels_and_html_escaping():
    for state, label in (("missing", "нет данных"), ("failed", "сбой синхронизации"),
                         ("stale", "устаревшие данные")):
        snap = {**SNAP, "acquisition": {"metadata": {"reports": {
            "traffic_sources": {"status": state, "date_to": "2026-06-30"},
        }}}}
        for render in (_fallback_summary, _raw_digits_block):
            text = render(snap)
            assert label in text
            assert "Платное привлечение: 0" not in text
    snap = {**SNAP, "acquisition": {"traffic_sources": {
        "<ad & other>": {"id": "ad", "visits": 123, "users": 99},
    }, "ad_campaigns": {"<campaign>": {"visits": 123}}}}
    raw = _raw_digits_block(snap)
    assert "&lt;ad &amp; other&gt;: 123" in raw
    assert "строк отчёта 1, визитов 123" in raw
    assert "число активных кампаний неизвестно" in raw


def test_acquisition_partial_report_does_not_invent_missing_channel_zero():
    snap = {**SNAP, "acquisition": {
        "traffic_sources": {"Organic": {"id": "organic", "visits": 120}},
        "metadata": {"reports": {"traffic_sources": {
            "status": "available", "total_rows": 3, "returned_rows": 1,
        }}},
    }}
    assert memory_core(snap)["metrika_ad_visits"] is None
    for render in (_fallback_summary, _raw_digits_block):
        text = render(snap)
        assert "Платное привлечение: нет данных" in text
        assert "Органический поиск: 120 визитов" in text
        assert "неполная выборка" in text


def test_llm_payload_keeps_zero_missing_and_quality_metadata(monkeypatch):
    import json
    from unittest.mock import AsyncMock
    from app.services import pulse_report

    seen = []

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, json, headers):
            seen.append(json)
            import httpx
            return httpx.Response(200, json={"choices": [{
                "message": {"content": "Наблюдение без причинного вывода.---HYPOTHESES---[]"},
            }]})

    monkeypatch.setattr(pulse_report.httpx, "AsyncClient", Client)
    monkeypatch.setattr(pulse_report.settings, "openrouter_api_key", "fixture-key")
    monkeypatch.setattr(pulse_report, "_open_hypotheses", AsyncMock(return_value=[]))
    monkeypatch.setattr(pulse_report, "send_message", AsyncMock(side_effect=AssertionError("no send")))
    for acq in ({"traffic_sources": {}, "ad_campaigns": {}}, {}, {
        "metadata": {"reports": {"traffic_sources": {"status": "failed"}}},
    }):
        snap = {**SNAP, "acquisition": acq}
        assert asyncio.run(pulse_report._llm_summary(snap, [memory_core(snap)]))
        content = seen[-1]["messages"][1]["content"]
        data = json.loads(content.split("Снапшот за отчётный день:\n")[1]
                          .split("\n\nОткрытые гипотезы")[0])
        assert data["acquisition"] == acq
        assert data["users"]["total"] == 12
        digits = _raw_digits_block(data)
        assert ("Платное привлечение: 0 визитов" in digits) == ("traffic_sources" in acq)
        assert "Директ:" not in digits


def test_pulse_prompt_does_not_infer_campaign_state():
    from app.services.pulse_report import _SYSTEM_PROMPT

    assert "это остановка кампании в Директе" not in _SYSTEM_PROMPT
    assert "не доказывает остановку" in _SYSTEM_PROMPT
    assert "missing" in _SYSTEM_PROMPT and "stale" in _SYSTEM_PROMPT
    assert "partner_revenue" in _SYSTEM_PROMPT
    assert "не число активных кампаний" in _SYSTEM_PROMPT


def test_acquisition_missing_is_not_zero():
    snap = {**SNAP, "acquisition": {}}
    for render in (_fallback_summary, _raw_digits_block):
        text = render(snap)
        assert "Платное привлечение: нет данных" in text
        assert "Органический поиск: нет данных" in text
        assert "Директ:" not in text
    core = memory_core(snap)
    assert core["metrika_ad_visits"] is None
    assert core["metrika_visits"] is None


def test_fallback_summary_mentions_key_numbers():
    text = _fallback_summary(SNAP)
    assert "12" in text and "Скачиваний: 4" in text and "Ошибок фронта: 2" in text
    assert "Платное привлечение: 130 визитов" in text


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
    assert "Платное привлечение: 130 визитов" in block
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


def test_seo_snapshot_disabled_without_token(monkeypatch):
    from app.services import pulse

    monkeypatch.setattr(pulse.settings, "yandex_webmaster_token", "")
    result = asyncio.run(pulse._seo_snapshot(None))
    assert result == {"available": False, "reason": "webmaster token not configured"}


def test_seo_snapshot_computes_indexed_share(monkeypatch):
    """Н-24 (2026-07-08): доля индексации должна попадать в снапшот Пульса —
    раньше эта цифра жила только в отдельном еженедельном отчёте без LLM."""
    from app.services import pulse
    from app.services import yandex_webmaster_client as ywc

    monkeypatch.setattr(pulse.settings, "yandex_webmaster_token", "token")

    class FakeResp:
        def __init__(self, data):
            self.data = data

    class FakeClient:
        async def user(self):
            return FakeResp({"user_id": "u1"})

        async def summary(self, user_id, host_id):
            return FakeResp({
                "searchable_pages_count": 3527,
                "excluded_pages_count": 2,
                "sqi": 10,
                "site_problems": {"RECOMMENDATION": 3},
            })

        async def search_events_samples(self, user_id, host_id, limit=100):
            return FakeResp({"samples": []})

    monkeypatch.setattr(ywc, "YandexWebmasterClient", FakeClient)
    monkeypatch.setattr("app.services.sitemap_static.url_count_from_stats", lambda: 43300)

    class FakeDB:
        async def scalar(self, *a, **kw):
            return None  # нет строк webmaster_search_queries за сегодня

        async def execute(self, *a, **kw):
            class _R:
                def all(self):
                    return []
            return _R()

    class _CM:
        async def __aenter__(self):
            return FakeDB()
        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(pulse, "analytics_session", lambda: _CM())

    result = asyncio.run(pulse._seo_snapshot(None))
    assert result["available"] is True
    assert result["searchable_pages"] == 3527
    assert result["sitemap_urls_total"] == 43300
    assert result["indexed_share_pct"] == round(100 * 3527 / 43300, 1)
    assert result["top_search_queries"] == []


def test_seo_snapshot_dual_host_summary(monkeypatch):
    """Dual-host (ADR-0013 §F): apex всегда, ru. при cutover; сбой ru. не валит снапшот."""
    from app.config import settings
    from app.services import pulse
    from app.services import yandex_webmaster_client as ywc

    monkeypatch.setattr(pulse.settings, "yandex_webmaster_token", "token")
    monkeypatch.setattr(settings, "apex_locale_en", True)

    counts = {"https:forecasteconomy.com:443": 3527, "https:ru.forecasteconomy.com:443": 610}

    class FakeResp:
        def __init__(self, data):
            self.data = data

    class FakeClient:
        async def user(self):
            return FakeResp({"user_id": "u1"})

        async def summary(self, user_id, host_id):
            if host_id not in counts:
                raise AssertionError(f"unexpected host {host_id}")
            return FakeResp({
                "searchable_pages_count": counts[host_id],
                "excluded_pages_count": 2,
                "sqi": 10,
                "site_problems": {},
            })

        async def search_events_samples(self, user_id, host_id, limit=100):
            return FakeResp({"samples": []})

    monkeypatch.setattr(ywc, "YandexWebmasterClient", FakeClient)
    monkeypatch.setattr("app.services.sitemap_static.url_count_from_stats", lambda: 43300)

    class FakeDB:
        async def scalar(self, *a, **kw):
            return None

        async def execute(self, *a, **kw):
            class _R:
                def all(self):
                    return []
            return _R()

    class _CM:
        async def __aenter__(self):
            return FakeDB()
        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(pulse, "analytics_session", lambda: _CM())

    result = asyncio.run(pulse._seo_snapshot(None))
    assert result["available"] is True
    assert set(result["summary_by_host"]) == {
        "forecasteconomy.com", "ru.forecasteconomy.com",
    }
    assert result["summary_by_host"]["forecasteconomy.com"]["searchable_pages"] == 3527
    assert result["summary_by_host"]["ru.forecasteconomy.com"]["searchable_pages"] == 610
    # Верхний уровень — apex, обратная совместимость.
    assert result["searchable_pages"] == 3527
    assert result["demand_by_host"] == []


def test_seo_snapshot_single_host_before_cutover(monkeypatch):
    """До cutover (apex_locale_en=false) ru.-свойство не запрашивается вовсе."""
    from app.config import settings
    from app.services import pulse
    from app.services import yandex_webmaster_client as ywc

    monkeypatch.setattr(pulse.settings, "yandex_webmaster_token", "token")
    monkeypatch.setattr(settings, "apex_locale_en", False)

    seen_hosts: list[str] = []

    class FakeResp:
        def __init__(self, data):
            self.data = data

    class FakeClient:
        async def user(self):
            return FakeResp({"user_id": "u1"})

        async def summary(self, user_id, host_id):
            seen_hosts.append(host_id)
            return FakeResp({
                "searchable_pages_count": 3527,
                "excluded_pages_count": 2,
                "sqi": 10,
                "site_problems": {},
            })

        async def search_events_samples(self, user_id, host_id, limit=100):
            return FakeResp({"samples": []})

    monkeypatch.setattr(ywc, "YandexWebmasterClient", FakeClient)
    monkeypatch.setattr("app.services.sitemap_static.url_count_from_stats", lambda: 100)

    class FakeDB:
        async def scalar(self, *a, **kw):
            return None

        async def execute(self, *a, **kw):
            class _R:
                def all(self):
                    return []
            return _R()

    class _CM:
        async def __aenter__(self):
            return FakeDB()
        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(pulse, "analytics_session", lambda: _CM())

    result = asyncio.run(pulse._seo_snapshot(None))
    assert result["available"] is True
    assert set(result["summary_by_host"]) == {"forecasteconomy.com"}
    assert seen_hosts.count("https:ru.forecasteconomy.com:443") == 0


def test_memory_core_includes_seo_indexed_share():
    from app.services.pulse import memory_core

    snap = {**SNAP, "seo": {"available": True, "indexed_share_pct": 8.1, "searchable_pages": 3527}}
    core = memory_core(snap)
    assert core["seo_indexed_share_pct"] == 8.1
    assert core["seo_searchable_pages"] == 3527


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


def test_split_telegram_text_short_stays_single():
    from app.services.telegram_bot import _split_telegram_text

    assert _split_telegram_text("короткий текст") == ["короткий текст"]


def test_split_telegram_text_splits_long_and_keeps_blockquote_valid():
    from app.services.telegram_bot import _split_telegram_text

    header = "\n".join(f"строка заголовка номер {i}" for i in range(50))
    blockquote = "<blockquote expandable>" + "\n".join(f"строка {i}" for i in range(20)) + "</blockquote>"
    text = header + "\n" + blockquote
    chunks = _split_telegram_text(text, limit=200)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 200
        # ни один чанк не оставляет тег незакрытым/несбалансированным
        assert chunk.count("<blockquote") == chunk.count("</blockquote>")


def test_split_telegram_text_splits_oversized_single_blockquote():
    """Реальный кейс 2026-07-08: LLM обернула почти весь ответ в один blockquote
    длиннее лимита — старая версия сплиттера держала его целиком и не резала."""
    from app.services.telegram_bot import _split_telegram_text

    inner = "\n".join(f"пункт отчёта номер {i} с содержательным текстом" for i in range(120))
    text = "🛰 <b>Пульс</b>\n\n<blockquote expandable>" + inner + "</blockquote>"
    assert len(text) > 4000
    chunks = _split_telegram_text(text, limit=1000)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 1000
        assert chunk.count("<blockquote") == chunk.count("</blockquote>")


def test_send_message_splits_and_archives_each_chunk(monkeypatch):
    from app.services import telegram_bot as tb

    sent_texts = []

    async def fake_api(method, payload, files=None):
        sent_texts.append(payload["text"])
        return {"ok": True, "result": {"message_id": len(sent_texts)}}

    monkeypatch.setattr(tb, "_api", fake_api)
    long_text = "x" * 9000
    ok = asyncio.run(tb.send_message("1", long_text, reply_markup={"a": 1}))
    assert ok is True
    assert len(sent_texts) >= 3
    assert "".join(sent_texts) == long_text


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

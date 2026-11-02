"""Заглушка «технические работы» Росстата и догрузка рядов после возвращения сайта.

01-02.11.2026 rosstat.gov.ru отвечал на любой адрес одной страницей «Сайт Росстата временно недоступен» (главная 200,
остальное 404). Парсеры читали это как «файл не найден»: вечерний ETL показал 45 разных ошибок вместо одной причины,
а ряды ждали следующего планового прогона (до 14 часов) после возвращения сайта.
"""

import asyncio
import os
import tempfile
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import requests

import app.services.alerting as alerting
from app.services import http_client
from app.services.http_client import SourceMaintenance, create_session
from app.tasks import scheduler

STUB_HTML = (
    "<html><head><title>Федеральная служба государственной статистики</title></head><body>"
    "<h1>Сайт Росстата временно недоступен — ведутся технические работы</h1></body></html>"
).encode("utf-8")


@pytest.fixture(autouse=True)
def _clean_breaker():
    http_client._reset_host_breaker()
    yield
    http_client._reset_host_breaker()


def _response(status: int, body: bytes, content_type: str = "text/html") -> requests.Response:
    r = requests.Response()
    r.status_code = status
    r._content = body
    r.headers["content-type"] = content_type
    return r


def test_stub_page_is_source_maintenance_and_arms_breaker():
    calls = []

    def fake_request(self, method, url, **kwargs):
        calls.append(url)
        return _response(404, STUB_HTML)

    s = create_session(proxy=False, socks=False)
    with patch.object(requests.Session, "request", fake_request):
        with pytest.raises(SourceMaintenance) as first:
            s.get("https://rosstat.gov.ru/storage/mediabank/demo21_2025.xlsx")
        assert "unreachable" in str(first.value)
        # предохранитель хоста взведён: второй запрос без сети
        with pytest.raises(requests.ConnectionError, match="unreachable on all hops recently"):
            s.get("https://rosstat.gov.ru/storage/mediabank/ind_10-2026.xlsx")
    assert len(calls) == 1


def test_breaker_refusal_is_recorded_as_fetch_issue_for_parsers_that_swallow_it():
    """Недельные парсеры глотают ConnectionError: без записи сбоя прогон выглядел как «0 точек, смена вёрстки»."""
    s = create_session(proxy=False, socks=False)
    token = http_client.begin_fetch_issues()
    try:
        with patch.object(requests.Session, "request", lambda self, m, u, **k: _response(404, STUB_HTML)):
            for url in ("https://rosstat.gov.ru/storage/mediabank/a.xlsx", "https://rosstat.gov.ru/storage/mediabank/b.xlsx"):
                with pytest.raises(requests.ConnectionError):
                    s.get(url)
        issues = http_client.current_fetch_issues()
    finally:
        http_client.end_fetch_issues(token)
    assert len(issues) == 2 and all("unreachable" in i for i in issues)
    assert "host breaker" in issues[1]


def test_stub_on_homepage_with_status_200_is_also_maintenance():
    s = create_session(proxy=False, socks=False)
    with patch.object(requests.Session, "request", lambda self, m, u, **k: _response(200, STUB_HTML)):
        with pytest.raises(SourceMaintenance):
            s.get("https://rosstat.gov.ru/")


def test_ordinary_not_found_and_files_are_not_mistaken_for_the_stub():
    s = create_session(proxy=False, socks=False)
    plain_404 = _response(404, "<html><body>Страница не найдена</body></html>".encode())
    xlsx = _response(200, STUB_HTML, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    other_host = _response(200, STUB_HTML)
    with patch.object(requests.Session, "request", lambda self, m, u, **k: plain_404):
        assert s.get("https://rosstat.gov.ru/storage/mediabank/nope.xlsx").status_code == 404
    with patch.object(requests.Session, "request", lambda self, m, u, **k: xlsx):
        assert s.get("https://rosstat.gov.ru/storage/mediabank/a.xlsx").status_code == 200
    with patch.object(requests.Session, "request", lambda self, m, u, **k: other_host):
        assert s.get("https://example.com/").status_code == 200


def test_summary_puts_unreachable_series_on_one_line_without_red():
    sent = []

    async def fake_send(message, chat_id=None, reply_markup=None, kind="alert"):
        sent.append((kind, message))
        return True

    codes = [f"s{i}" for i in range(12)]
    with patch.object(alerting, "send_telegram", fake_send):
        asyncio.run(alerting.alert_etl_summary(119, 10, [], 162.0, unreachable=codes))
        asyncio.run(alerting.alert_etl_summary(119, 10, ["cpi"], 162.0, unreachable=codes))
        asyncio.run(alerting.alert_etl_summary(12, 12, [], 300.0, recovery=True))
        asyncio.run(alerting.alert_etl_summary(89, 7, ["key-rate"], 525.0))
    first, mixed, recovered, plain = (m for _, m in sent)
    assert first.startswith("🟡") and "источник недоступен: 12" in first and "с ошибкой: 0" in first
    assert "Источник недоступен (12): s0, s1, s2, s3, s4, s5, s6, s7 и ещё 4" in first
    assert "загрузка повторится сама" in first
    assert mixed.startswith("🔴") and "С ошибкой: cpi" in mixed
    assert "Догрузка данных после недоступности источника завершена" in recovered and recovered.startswith("🟢")
    # без новых аргументов текст прежний
    assert plain.startswith("🔴 <b>Ежедневная выгрузка данных завершена</b>")
    assert "источник недоступен" not in plain


def test_primary_weekly_cpi_reports_unreachable_source_as_failed_without_zero_parse_alert():
    """`inflation-weekly` переопределяет run(): раньше при недоступном источнике он ставил parsed_zero и слал zero_parse."""
    from app.models import FetchLog
    from app.services import rosstat_weekly_inflation_parser as weekly

    class SwallowedNetworkFailure(weekly.RosstatWeeklyCpiParser):
        async def _fetch_and_parse(self, db, indicator, cfg, fetch_log):
            http_client.record_fetch_issue("rosstat.gov.ru unreachable: сайт на технических работах")
            self._segment_points = None
            return [], "https://rosstat.gov.ru/storage/mediabank/nedel_Ipc.xlsx"

    class Db:
        commits = 0

        async def commit(self):
            self.commits += 1

    db = Db()
    indicator = SimpleNamespace(code="inflation-weekly", model_config_json={})
    log = FetchLog(indicator_id=1, status="running")
    asyncio.run(SwallowedNetworkFailure().run(db, indicator, log))
    assert log.status == "failed" and db.commits == 1
    assert log.error_message.startswith("Source unreachable, 0 points:") and "unreachable" in log.error_message


# --- daily_update_job: ряды недоступного источника -------------------------------------------------------


def _fake_job_env(monkeypatch, inds, fake_run):
    class _Res:
        def scalars(self):
            return SimpleNamespace(all=lambda: inds)

    class _Sess:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def execute(self, *_a, **_k):
            return _Res()

    summaries = []

    async def fake_summary(total, updated, failed, duration, *, degraded=None, **extra):
        summaries.append({"total": total, "updated": updated, "failed": list(failed), "degraded": degraded, **extra})

    async def noop(*_a, **_k):
        return []

    monkeypatch.setattr(scheduler, "async_session", lambda: _Sess())
    monkeypatch.setattr(scheduler, "_run_etl_with_timeout", fake_run)
    monkeypatch.setattr(scheduler, "alert_etl_summary", fake_summary)
    monkeypatch.setattr(scheduler, "_catch_up_empty_forecasts_safe", noop)
    monkeypatch.setattr(scheduler, "_promote_past_events", noop)
    monkeypatch.setattr(scheduler, "_running_locks", set())
    return summaries


def test_daily_job_reports_unreachable_series_apart_from_real_failures(monkeypatch):
    inds = [SimpleNamespace(code=c, parser_type="rosstat_demo") for c in ("a", "b")] + [
        SimpleNamespace(code="broken", parser_type="cbr_fx_xml"),
        SimpleNamespace(code="ok", parser_type="cbr_fx_xml"),
    ]

    async def fake_run(code, timeout):
        if code in ("a", "b"):
            raise SourceMaintenance("rosstat.gov.ru unreachable: site is under maintenance")
        if code == "broken":
            raise ValueError("parser blew up")
        return False, "no_new_data"

    summaries = _fake_job_env(monkeypatch, inds, fake_run)
    asyncio.run(scheduler.daily_update_job())
    assert summaries[0]["failed"] == ["broken"]
    assert summaries[0]["unreachable"] == ["a", "b"]
    assert summaries[0]["recovery"] is False


def test_weekly_zero_points_caused_by_unreachable_source_are_not_a_layout_change(monkeypatch):
    inds = [SimpleNamespace(code=c, parser_type="rosstat_weekly_price") for c in ("fuel-ai92", "fuel-ai95")] + [
        SimpleNamespace(code="inflation-weekly", parser_type="rosstat_weekly_cpi"),
    ]

    async def fake_run(code, timeout):
        return False, "parsed_zero"

    async def only_fuel_ai92(codes=None, *, rosstat_only=True):
        assert rosstat_only is False
        return [c for c in codes if c == "fuel-ai92"]

    summaries = _fake_job_env(monkeypatch, inds, fake_run)
    monkeypatch.setattr(scheduler, "_rosstat_unreachable_codes", only_fuel_ai92)
    asyncio.run(scheduler.daily_update_job())
    assert summaries[0]["unreachable"] == ["fuel-ai92"]
    # настоящий «ноль точек» остаётся замечанием о вёрстке
    assert summaries[0]["degraded"]["parsed_zero"] == ["fuel-ai95", "inflation-weekly"]


def test_recovery_run_loads_only_asked_series_and_stays_silent_when_nothing_loaded(monkeypatch):
    inds = [SimpleNamespace(code=c, parser_type="rosstat_demo") for c in ("a", "b", "c")]
    ran = []

    async def fake_run(code, timeout):
        ran.append(code)
        raise SourceMaintenance("rosstat.gov.ru unreachable: site is under maintenance")

    summaries = _fake_job_env(monkeypatch, inds, fake_run)
    asyncio.run(scheduler.daily_update_job({"a", "c"}, recovery=True))
    # повтор по сетевым сбоям в догрузке отключён, итога нет: сайт ещё молчит
    assert ran == ["a", "c"]
    assert summaries == []


# --- rosstat_recovery_job ---------------------------------------------------------------------------------


@pytest.fixture
def recovery(monkeypatch):
    state = SimpleNamespace(pending=["cpi", "ppi"], site=True, loaded=[], probes=0)

    async def pending():
        return list(state.pending)

    def probe():
        state.probes += 1
        return state.site

    async def fake_daily(only_codes=None, *, recovery=False):
        state.loaded.append((set(only_codes), recovery))

    monkeypatch.setattr(scheduler, "_rosstat_unreachable_codes", pending)
    monkeypatch.setattr(scheduler, "_rosstat_site_answers", probe)
    monkeypatch.setattr(scheduler, "daily_update_job", fake_daily)
    monkeypatch.setattr(scheduler, "_rosstat_recovery_paused_until", 0.0)
    return state


def test_recovery_does_nothing_without_pending_series(recovery):
    recovery.pending = []
    assert asyncio.run(scheduler.rosstat_recovery_job()) == {"pending": 0}
    assert recovery.probes == 0 and recovery.loaded == []


def test_recovery_waits_while_site_is_down(recovery):
    recovery.site = False
    result = asyncio.run(scheduler.rosstat_recovery_job())
    assert result == {"pending": 2, "site": "down"}
    assert recovery.loaded == []


def test_recovery_loads_pending_series_when_site_answers(recovery, monkeypatch):
    calls = {"n": 0}

    async def pending_then_clear():
        calls["n"] += 1
        return ["cpi", "ppi"] if calls["n"] == 1 else []

    monkeypatch.setattr(scheduler, "_rosstat_unreachable_codes", pending_then_clear)
    result = asyncio.run(scheduler.rosstat_recovery_job())
    assert recovery.loaded == [({"cpi", "ppi"}, True)]
    assert result == {"pending": 2, "site": "up", "still_pending": 0}


def test_recovery_pauses_when_site_answers_but_nothing_loads(recovery):
    first = asyncio.run(scheduler.rosstat_recovery_job())
    assert first["still_pending"] == 2
    probes = recovery.probes
    second = asyncio.run(scheduler.rosstat_recovery_job())
    assert second == {"pending": 2, "site": "paused"}
    assert recovery.probes == probes and len(recovery.loaded) == 1


# --- какие ряды ждут догрузки (последний прогон «unreachable») ---------------------------------------------


def test_unreachable_codes_query_takes_only_latest_rosstat_failures(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.models import Base, FetchLog, Indicator

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        sync_engine = create_engine(f"sqlite:///{path}")
        Base.metadata.create_all(sync_engine)
        sync_engine.dispose()
        engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
        maker = async_sessionmaker(engine, expire_on_commit=False)
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        def ind(code, parser_type="rosstat_demo", active=True):
            return Indicator(code=code, name=code, parser_type=parser_type, is_active=active)

        def log(indicator, status, error, ago_h):
            return FetchLog(indicator_id=indicator.id, status=status, error_message=error,
                            records_added=0, started_at=now - timedelta(hours=ago_h))

        async def run():
            async with maker() as db:
                items = {c: ind(c) for c in ("waits", "recovered", "real_error", "inactive", "old", "weekly")}
                items["cbr"] = ind("cbr", parser_type="cbr_fx_xml")
                items["inactive"].is_active = False
                db.add_all(items.values())
                await db.flush()
                gone = "Rosstat unreachable: ind XLSX requests failed on network"
                db.add_all([
                    log(items["waits"], "failed", gone, 3),
                    log(items["recovered"], "failed", gone, 5), log(items["recovered"], "success", None, 1),
                    log(items["real_error"], "failed", "Rosstat mediabank file not found", 2),
                    log(items["inactive"], "failed", gone, 2),
                    log(items["old"], "failed", gone, 24 * 9),
                    log(items["weekly"], "parsed_zero", "nedel_sred_cen.xlsx fetch failed: rosstat.gov.ru unreachable on all hops", 2),
                    log(items["cbr"], "failed", gone, 2),
                ])
                await db.commit()

            monkeypatch.setattr(scheduler, "async_session", maker)
            return await scheduler._rosstat_unreachable_codes()

        assert asyncio.run(run()) == ["waits", "weekly"]
    finally:
        os.unlink(path)

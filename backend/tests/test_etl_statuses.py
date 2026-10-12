"""fetch_log.status: parsed_zero / fallback_used вместо «зелёного» no_new_data.

Инцидент 2026-09: 107 из 117 прогонов — no_new_data, среди них тихо сломанные
(housing zero-parse с 2026-07-29, Минфин на packaged artifact с 2026-08-18).
"""

import asyncio
from datetime import date
from types import SimpleNamespace

import pytest

from app.models import FetchLog
from app.services import alerting
from app.services import base_parser as bp
from app.services.base_parser import (
    BaseParser,
    mark_expected_empty,
    mark_fallback_used,
)


class _FakeDB:
    def __init__(self, existing: int = 0):
        self.existing = existing
        self.commits = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        pass

    def add(self, obj):
        pass

    async def scalar(self, stmt):
        return self.existing


class _Parser(BaseParser):
    parser_type = "test_parser"

    def __init__(self, points, *, expected_empty=None, fallback=None, replace=False):
        self._points = points
        self._expected_empty = expected_empty
        self._fallback = fallback
        self.replace_series = replace

    async def _fetch_and_parse(self, db, indicator, cfg, fetch_log):
        if self._expected_empty:
            mark_expected_empty(fetch_log, self._expected_empty)
        if self._fallback:
            mark_fallback_used(fetch_log, self._fallback)
        return list(self._points), "https://example.test/src"

    async def _handle_forecasts(self, db, indicator, cfg, records_added, records_updated, pruned=0):
        return None


@pytest.fixture
def env(monkeypatch):
    state = {"upsert": (0, 0), "prune_calls": [], "zero_alerts": []}

    async def fake_upsert(db, indicator_id, points):
        return state["upsert"]

    async def fake_prune(db, indicator_id, points, *, keep_after=None):
        state["prune_calls"].append(keep_after)
        return 0

    async def fake_invalidate(code):
        return None

    async def fake_zero_alert(code, existing):
        state["zero_alerts"].append((code, existing))

    monkeypatch.setattr(bp, "bulk_upsert", fake_upsert)
    monkeypatch.setattr(bp, "prune_indicator_dates_not_in", fake_prune)
    monkeypatch.setattr(bp, "cache_invalidate_indicator", fake_invalidate)
    monkeypatch.setattr(alerting, "alert_zero_parse", fake_zero_alert)
    return state


def _run(parser, db):
    indicator = SimpleNamespace(id=1, code="x", model_config_json={})
    fetch_log = FetchLog(indicator_id=1, status="running")
    asyncio.run(parser.run(db, indicator, fetch_log))
    return fetch_log


def test_zero_parse_with_history_is_parsed_zero(env):
    fl = _run(_Parser([]), _FakeDB(existing=62))
    assert fl.status == "parsed_zero"
    assert env["zero_alerts"] == [("x", 62)]


def test_zero_parse_without_history_stays_no_new_data(env):
    fl = _run(_Parser([]), _FakeDB(existing=0))
    assert fl.status == "no_new_data"


def test_expected_empty_stays_no_new_data_without_alert(env):
    fl = _run(_Parser([], expected_empty="no housing section"), _FakeDB(existing=62))
    assert fl.status == "no_new_data"
    assert fl.error_message == "no housing section"
    assert env["zero_alerts"] == []


def test_unchanged_points_no_new_data(env):
    fl = _run(_Parser([(date(2026, 6, 1), 1.0)]), _FakeDB())
    assert fl.status == "no_new_data"


def test_changed_points_success(env):
    env["upsert"] = (1, 0)
    fl = _run(_Parser([(date(2026, 6, 1), 1.0)]), _FakeDB())
    assert fl.status == "success"


def test_fallback_status_even_when_points_change(env):
    env["upsert"] = (1, 1)
    fl = _run(_Parser([(date(2026, 6, 1), 1.0)], fallback="artifact"), _FakeDB())
    assert fl.status == "fallback_used"
    assert fl.error_message == "artifact"
    assert fl.records_added == 1 and fl.records_updated == 1


def test_fallback_prune_keeps_points_newer_than_coverage(env):
    pts = [(date(2026, 5, 1), 1.0), (date(2026, 6, 1), 2.0)]
    _run(_Parser(pts, fallback="artifact", replace=True), _FakeDB())
    assert env["prune_calls"] == [date(2026, 6, 1)]


def test_live_prune_is_full_snapshot(env):
    _run(_Parser([(date(2026, 6, 1), 2.0)], replace=True), _FakeDB())
    assert env["prune_calls"] == [None]


def test_status_fits_column():
    for s in bp.DEGRADED_STATUSES:
        assert len(s) <= 20  # fetch_log.status VARCHAR(20), без enum/constraint


def test_etl_summary_counts_problems(monkeypatch):
    sent = []

    async def fake_send(text, *a, **k):
        sent.append(text)
        return True

    monkeypatch.setattr(alerting, "send_telegram", fake_send)
    asyncio.run(alerting.alert_etl_summary(
        117, 10, [], 700.0,
        degraded={"parsed_zero": ["housing-price-primary"], "fallback_used": ["budget-deficit", "budget-revenue"]},
    ))
    text = sent[0]
    assert text.startswith("🟡")
    assert "Problems: 3" in text
    assert "housing-price-primary" in text and "budget-revenue" in text


def test_etl_summary_green_without_problems(monkeypatch):
    sent = []

    async def fake_send(text, *a, **k):
        sent.append(text)
        return True

    monkeypatch.setattr(alerting, "send_telegram", fake_send)
    asyncio.run(alerting.alert_etl_summary(117, 10, [], 700.0, degraded={"parsed_zero": []}))
    assert sent[0].startswith("🟢") and "Problems: 0" in sent[0]


def test_fetch_changed_semantics():
    from app.tasks.scheduler import _fetch_changed

    assert _fetch_changed(FetchLog(status="success", records_added=0, records_updated=0))
    assert not _fetch_changed(FetchLog(status="fallback_used", records_added=0, records_updated=0))
    assert _fetch_changed(FetchLog(status="fallback_used", records_added=0, records_updated=2))
    assert not _fetch_changed(FetchLog(status="parsed_zero", records_added=0, records_updated=0))


# --- Сбой сети не маскируется под «смену layout» (круг 12, 09.10.2026) --------
# fuel-ai92 и inflation-weekly дали 0 точек, потому что rosstat.gov.ru на
# минуту не принял соединение; парсер проглотил RequestException, ETL написал
# parsed_zero и «вероятна смена layout источника».


class _NetDownParser(_Parser):
    """Парсер, чей fetch глотает сетевую ошибку, как rosstat_weekly_price."""

    async def _fetch_and_parse(self, db, indicator, cfg, fetch_log):
        import requests

        from app.services import http_client

        session = http_client.create_session(proxy=None, socks=None)
        with pytest.MonkeyPatch.context() as mp:
            def dead(self, method, url, **kwargs):
                raise requests.ConnectTimeout("no route")

            mp.setattr(requests.Session, "request", dead)
            http_client._reset_host_breaker()
            try:
                session.get("https://rosstat.gov.ru/storage/mediabank/nedel_sred_cen.xlsx")
            except requests.RequestException:
                pass  # как в парсере: ошибка проглочена, точек нет
            finally:
                http_client._reset_host_breaker()
        return [], "https://rosstat.gov.ru/storage/mediabank/nedel_sred_cen.xlsx"


def test_unreachable_source_with_zero_points_is_failed_not_parsed_zero(env):
    fl = _run(_NetDownParser([]), _FakeDB(existing=243))
    assert fl.status == "failed"
    assert "Source unreachable" in fl.error_message
    assert "rosstat.gov.ru" in fl.error_message
    assert env["zero_alerts"] == []  # ложный «смена layout» не рассылается


def test_unreachable_secondary_request_does_not_fail_run_with_points(env):
    class _P(_NetDownParser):
        async def _fetch_and_parse(self, db, indicator, cfg, fetch_log):
            await super()._fetch_and_parse(db, indicator, cfg, fetch_log)
            return [(date(2026, 6, 1), 1.0)], "https://example.test"

    fl = _run(_P([]), _FakeDB(existing=243))
    assert fl.status == "no_new_data"


def test_fetch_issues_do_not_leak_between_runs(env):
    _run(_NetDownParser([]), _FakeDB(existing=243))
    fl = _run(_Parser([]), _FakeDB(existing=0))
    assert fl.status == "no_new_data"

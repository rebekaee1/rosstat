"""Росстат отвечает старой копией сайта без файлов (09.11.2026): одна причина вместо 41 ошибки и 4 «смен вёрстки»."""

import asyncio
from datetime import date
from types import SimpleNamespace

import app.services.rosstat_outage as rosstat_outage
from app.tasks import scheduler
from tests.test_rosstat_recovery import _fake_job_env

FRESH = '<a href="/storage/mediabank/12_04-11-2026.html">О потребительских ценах на нефтепродукты</a>'
# Лента 09.11.2026 на живом сайте: самые свежие бюллетени от 13 марта.
STALE = (
    '<a href="/storage/mediabank/36_13-03-2026.html">x</a>'
    '<a href="/storage/mediabank/35_13-03-2026.html">x</a>'
    '<a href="/storage/mediabank/30_06-03-2026.html">x</a>'
)
TODAY = date(2026, 11, 9)


def test_newest_bulletin_date_takes_the_latest_link():
    assert rosstat_outage.newest_bulletin_date(STALE) == date(2026, 3, 13)
    assert rosstat_outage.newest_bulletin_date("<html>нет ссылок</html>") is None


def test_stale_feed_gives_unreachable_reason():
    reason = rosstat_outage.stale_reason_from_html(STALE, today=TODAY)
    assert reason and "unreachable" in reason and "13.03.2026" in reason


def test_fresh_feed_and_feed_without_dates_claim_nothing():
    assert rosstat_outage.stale_reason_from_html(FRESH, today=TODAY) is None
    # лента сменила разметку - не повод объявлять сайт недоступным
    assert rosstat_outage.stale_reason_from_html("<html></html>", today=TODAY) is None


def test_january_holidays_gap_is_not_an_outage():
    html = '<a href="/storage/mediabank/1_29-12-2026.html">x</a>'
    assert rosstat_outage.stale_reason_from_html(html, today=date(2027, 1, 12)) is None


def test_probe_result_is_cached(monkeypatch):
    calls = []

    def probe():
        calls.append(1)
        return "rosstat.gov.ru unreachable: старая копия"

    monkeypatch.setattr(rosstat_outage, "_probe", probe)
    assert rosstat_outage.stale_copy_reason()
    assert rosstat_outage.stale_copy_reason()
    assert len(calls) == 1
    assert rosstat_outage.stale_copy_reason(force=True)
    assert len(calls) == 2


def _outage_env(monkeypatch, reason):
    inds = [SimpleNamespace(code=c, parser_type="rosstat_demo") for c in ("births", "deaths")] + [
        SimpleNamespace(code="usd-rub", parser_type="cbr_fx_xml"),
    ]

    async def fake_run(code, timeout):
        if code in ("births", "deaths"):
            raise RuntimeError("Rosstat mediabank file not found (patterns=['demo21'], tried=['demo21_2025.xlsx'])")
        raise RuntimeError("CBR XML: unexpected root")

    summaries = _fake_job_env(monkeypatch, inds, fake_run)
    annotated = []

    async def annotate(codes, why):
        annotated.append((list(codes), why))

    monkeypatch.setattr(rosstat_outage, "_probe", lambda: reason)
    monkeypatch.setattr(scheduler, "_annotate_outage", annotate)
    return summaries, annotated


def test_daily_job_moves_rosstat_failures_to_unreachable_during_stale_copy(monkeypatch):
    reason = rosstat_outage.stale_reason_from_html(STALE, today=TODAY)
    summaries, annotated = _outage_env(monkeypatch, reason)
    asyncio.run(scheduler.daily_update_job())
    assert summaries[0]["unreachable"] == ["births", "deaths"]
    # чужой источник со своей ошибкой остаётся ошибкой
    assert summaries[0]["failed"] == ["usd-rub"]
    assert annotated == [(["births", "deaths"], reason)]


def test_daily_job_keeps_rosstat_failures_when_site_is_current(monkeypatch):
    summaries, annotated = _outage_env(monkeypatch, None)
    asyncio.run(scheduler.daily_update_job())
    assert summaries[0]["failed"] == ["births", "deaths", "usd-rub"]
    assert summaries[0]["unreachable"] == []
    assert annotated == []


def test_recovery_probe_waits_while_site_is_a_stale_copy(monkeypatch):
    import requests

    class _Resp:
        status_code = 200

    monkeypatch.setattr(requests.Session, "get", lambda self, url, **kw: _Resp())
    monkeypatch.setattr(rosstat_outage, "_probe", lambda: "rosstat.gov.ru unreachable: старая копия")
    assert scheduler._rosstat_site_answers() is False
    monkeypatch.setattr(rosstat_outage, "_probe", lambda: None)
    assert scheduler._rosstat_site_answers() is True

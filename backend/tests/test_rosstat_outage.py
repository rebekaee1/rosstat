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


def _outage_env(monkeypatch, reason, *, keep_failed=(), modes=None):
    modes = modes if modes is not None else []
    inds = [SimpleNamespace(code=c, parser_type="rosstat_demo") for c in ("births", "deaths")] + [
        SimpleNamespace(code="usd-rub", parser_type="cbr_fx_xml"),
    ]

    async def fake_run(code, timeout):
        if code in ("births", "deaths"):
            raise RuntimeError("Rosstat mediabank file not found (patterns=['demo21'], tried=['demo21_2025.xlsx'])")
        raise RuntimeError("CBR XML: unexpected root")

    summaries = _fake_job_env(monkeypatch, inds, fake_run)
    annotated = []

    async def annotate(codes, why, *, only_missing_file=False):
        annotated.append((list(codes), why))
        modes.append(only_missing_file)
        return [c for c in codes if c not in keep_failed] if only_missing_file else list(codes)

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


# --- 13.11.2026: сайт восстановлен частично (цены вернулись, промышленность, счета и демография нет) ----------

def test_bulletin_date_is_read_from_pdf_links():
    html = '<a href="/storage/mediabank/172_11-11-2026.pdf">Об оценке индекса потребительских цен</a>'
    assert rosstat_outage.newest_bulletin_date(html) == date(2026, 11, 11)
    assert rosstat_outage.stale_reason_from_html(html, today=date(2026, 11, 13)) is None


def test_section_sample_is_deterministic_and_bounded():
    html = "".join(f'<a href="/storage/mediabank/f{i:02d}.xlsx">x</a>' for i in range(20))
    html += '<a href="/storage/mediabank/f00.xlsx">дубль</a><a href="/storage/mediabank/doc.pdf">не файл данных</a>'
    sample = rosstat_outage.sample_section_files(html)
    assert sample == ["f00.xlsx", "f04.xlsx", "f08.xlsx", "f12.xlsx", "f16.xlsx"]
    assert rosstat_outage.sample_section_files('<a href="/storage/mediabank/a.xls">x</a>') == ["a.xls"]


def test_partial_reason_needs_most_of_the_sample_missing():
    reason = rosstat_outage.partial_reason_from_sections([("промышленность", 5, 5), ("демография", 1, 5)])
    assert reason and "unreachable" in reason and rosstat_outage.is_partial(reason)
    assert "промышленность" in reason and "демография" not in reason
    # одна битая ссылка и слишком маленькая выборка - не признак
    assert rosstat_outage.partial_reason_from_sections([("демография", 1, 5), ("счета", 3, 3)]) is None
    assert not rosstat_outage.is_partial("rosstat.gov.ru unreachable: сайт отдаёт старую копию без файлов")
    assert not rosstat_outage.is_partial(None)


def test_missing_file_error_texts():
    assert rosstat_outage.is_missing_file_error("Rosstat ipi_historical_2018: HTTP 404")
    assert rosstat_outage.is_missing_file_error("ind XLSX not found (tried ['ind_11-2026.xlsx'])")
    assert rosstat_outage.is_missing_file_error("nedel_sred_cen.xlsx fetch failed: 404 Client Error: Not Found")
    assert not rosstat_outage.is_missing_file_error("CPI sheet layout changed: header row missing")
    assert not rosstat_outage.is_missing_file_error(None)


class _FakeSession:
    """Сессия с заготовленными ответами по адресу: (status, text); неизвестный адрес - 404."""

    def __init__(self, pages):
        self.pages = pages
        self.urls = []

    def get(self, url, **kwargs):
        self.urls.append(url)
        status, text = self.pages.get(url, (404, ""))
        return SimpleNamespace(status_code=status, text=text, close=lambda: None)


def test_sections_are_probed_only_when_feed_is_fresh():
    stale = _FakeSession({rosstat_outage.CENTRAL_NEWS_URL: (200, STALE)})
    assert "старую копию" in (rosstat_outage._reason_for(stale) or "")
    assert stale.urls == [rosstat_outage.CENTRAL_NEWS_URL]


def test_fresh_feed_with_sections_without_files_is_a_partial_copy():
    fresh_feed = '<a href="/storage/mediabank/1_%s.pdf">x</a>' % date.today().strftime("%d-%m-%Y")
    listing = "".join(f'<a href="/storage/mediabank/ind_{i}.xlsx">x</a>' for i in range(6))
    industry_url = rosstat_outage.SECTION_PAGES[0][1]
    session = _FakeSession({rosstat_outage.CENTRAL_NEWS_URL: (200, fresh_feed), industry_url: (200, listing)})
    reason = rosstat_outage._reason_for(session)
    assert rosstat_outage.is_partial(reason) and "промышленность (5 из 5" in reason
    # результат разделов держится в своём кэше: второй вызов читает только ленту
    session.urls.clear()
    assert rosstat_outage._reason_for(session) == reason
    assert session.urls == [rosstat_outage.CENTRAL_NEWS_URL]


def test_fresh_feed_with_live_files_claims_nothing():
    fresh_feed = '<a href="/storage/mediabank/1_%s.pdf">x</a>' % date.today().strftime("%d-%m-%Y")
    listing = "".join(f'<a href="/storage/mediabank/ind_{i}.xlsx">x</a>' for i in range(6))
    pages = {rosstat_outage.CENTRAL_NEWS_URL: (200, fresh_feed), rosstat_outage.SECTION_PAGES[0][1]: (200, listing)}
    pages.update({f"https://rosstat.gov.ru/storage/mediabank/ind_{i}.xlsx": (200, "") for i in range(6)})
    assert rosstat_outage._reason_for(_FakeSession(pages)) is None


def test_daily_job_in_partial_copy_moves_only_missing_file_failures(monkeypatch):
    reason = rosstat_outage.partial_reason_from_sections([("демография", 5, 5)])
    modes = []
    summaries, _ = _outage_env(monkeypatch, reason, keep_failed=("deaths",), modes=modes)
    asyncio.run(scheduler.daily_update_job())
    assert modes == [True]
    assert summaries[0]["unreachable"] == ["births"]
    assert summaries[0]["failed"] == ["deaths", "usd-rub"]

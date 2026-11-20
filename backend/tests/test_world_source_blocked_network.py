"""Мировые источники, закрытые для сети сервера, и честный журнал прогона (20.11.2026).

15–19.11 national-core давал в Пульсе «7 из 10 наборов с ошибкой, причина не ясна»: StatCan (403), MoSPI
(таймаут соединения) и CFETS (таймаут чтения) перестали пускать сервер, а в счёт входили ещё и ряды без
ключей API. Здесь: обход через ETL-прокси для мировых адаптеров, запоминание обхода и причина в журнале.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import requests

from app.services.http_client import ProxyFallbackSession, _reset_host_breaker, create_source_session


def _resp(code: int) -> requests.Response:
    r = MagicMock(spec=requests.Response)
    r.status_code = code
    r.headers = {}
    r.content = b""
    return r


def _proxy_settings(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "etl_http_proxy_url", "http://proxy.test:8888")
    monkeypatch.setattr(settings, "openrouter_proxy_url", "")
    monkeypatch.setattr(settings, "etl_socks_proxy_url", "")


def test_world_adapters_use_proxy_fallback_session(monkeypatch):
    _proxy_settings(monkeypatch)
    from app.services.world_adapters.cfets_chinamoney import CfetsChinamoneyAdapter
    from app.services.world_adapters.mospi_api import build_session
    from app.services.world_national_ingest import load_national_core_yaml, resolve_adapter

    statcan = resolve_adapter("statcan", series_specs=load_national_core_yaml("ca").series)
    for session in (
        build_session(),
        statcan._session,
        CfetsChinamoneyAdapter()._session,
    ):
        assert isinstance(session, ProxyFallbackSession)
        assert session._proxy_url == "http://proxy.test:8888"
        assert session._remember_detour is True
    assert build_session().verify is False


def test_detour_is_remembered_after_direct_timeout(monkeypatch):
    """Прямой таймаут → прокси 200; следующий запрос к тому же хосту сразу через прокси."""
    _proxy_settings(monkeypatch)
    _reset_host_breaker()
    s = create_source_session()
    calls: list[str | None] = []

    def fake_request(self, method, url, **kwargs):
        px = (kwargs.get("proxies") or {}).get("https")
        calls.append(px)
        if not px:
            raise requests.exceptions.ConnectTimeout("direct blocked")
        return _resp(200)

    with patch.object(requests.Session, "request", fake_request):
        assert s.get("https://api.mospi.gov.in/a").status_code == 200
        assert s.get("https://api.mospi.gov.in/b").status_code == 200
        assert s.get("https://api.mospi.gov.in/c").status_code == 200
    assert calls == [None, "http://proxy.test:8888", "http://proxy.test:8888", "http://proxy.test:8888"]


def test_detour_forgotten_when_proxy_fails(monkeypatch):
    _proxy_settings(monkeypatch)
    _reset_host_breaker()
    s = create_source_session()
    state = {"proxy_ok": True}
    calls: list[str | None] = []

    def fake_request(self, method, url, **kwargs):
        px = (kwargs.get("proxies") or {}).get("https")
        calls.append(px)
        if px:
            if state["proxy_ok"]:
                return _resp(200)
            raise requests.exceptions.ProxyError("proxy down")
        return _resp(403) if state["proxy_ok"] else _resp(200)

    with patch.object(requests.Session, "request", fake_request):
        assert s.get("https://www150.statcan.gc.ca/x").status_code == 200  # 403 → прокси
        state["proxy_ok"] = False
        assert s.get("https://www150.statcan.gc.ca/y").status_code == 200  # прокси упал → прямо
    assert calls == [None, "http://proxy.test:8888", "http://proxy.test:8888", None]
    assert s._detour_until == {}


def test_plain_etl_session_does_not_remember(monkeypatch):
    """ETL России сохраняет прежнее поведение: каждый запрос сначала прямо."""
    from app.services.http_client import create_session

    _proxy_settings(monkeypatch)
    _reset_host_breaker()
    s = create_session()
    calls: list[str | None] = []

    def fake_request(self, method, url, **kwargs):
        px = (kwargs.get("proxies") or {}).get("https")
        calls.append(px)
        return _resp(200) if px else _resp(403)

    with patch.object(requests.Session, "request", fake_request):
        s.get("https://rosstat.gov.ru/a")
        s.get("https://rosstat.gov.ru/b")
    assert calls == [None, "http://proxy.test:8888", None, "http://proxy.test:8888"]


def test_failed_reasons_text_strips_source_html():
    from app.services.world_national_ingest import failed_reasons_text

    text = failed_reasons_text({
        "au": [
            ("au-cpi-all", "AbsDataError: ABS GET https://x HTTP 504: <!DOCTYPE html>\n<html><head><meta a=1/>"),
            ("au-gdp-real", "AbsDataError: other"),
        ],
    })
    assert text.startswith("au (2): AbsDataError: ABS GET https://x HTTP 504")
    assert "<" not in text


def _run_with_stats(auth_env, monkeypatch, stats_by_country):
    import app.core.cache as cache_mod
    import app.services.alerting as alerting
    import app.services.world_national_ingest as ingest_mod
    from app.models import WorldIngestRun

    monkeypatch.setattr(ingest_mod, "async_session", auth_env["session_maker"])

    async def fake_ingest_country(db, country, *, dry_run, **_):
        return stats_by_country[country]

    async def no_bump(*_namespaces):
        return None

    alerts: list[dict] = []

    async def capture_alert(source, **kwargs):
        alerts.append(kwargs)

    monkeypatch.setattr(ingest_mod, "ingest_country", fake_ingest_country)
    monkeypatch.setattr(cache_mod, "bump_namespaces", no_bump)
    monkeypatch.setattr(alerting, "alert_world_ingest_summary", capture_alert)

    async def go():
        result = await ingest_mod.run_national_core_ingest(country_codes=list(stats_by_country))
        async with auth_env["session_maker"]() as db:
            run = await db.get(WorldIngestRun, result["run_id"])
            return run.status, run.datasets_succeeded, run.datasets_failed, run.error_message or ""

    return asyncio.run(go()), alerts


def _stats(cc: str, ok: int, errors: list[tuple[str, str]]):
    from app.services.world_national_ingest import CountryIngestStats, SeriesIngestResult

    st = CountryIngestStats(country_code=cc.upper(), series_ok=ok, series_err=len(errors), indicators_upserted=ok)
    st.results = [SeriesIngestResult(code=c, provider="p", dataset_id="d", error=e) for c, e in errors]
    return st


def test_known_failures_do_not_count_as_broken_countries(auth_env, monkeypatch):
    """Нет ключа API у Японии и закрытый для сервера RBA — прогон «ok», 0 стран с ошибкой, причина в журнале."""
    (status, ok, failed, message), alerts = _run_with_stats(auth_env, monkeypatch, {
        "us": _stats("us", 5, []),
        "jp": _stats("jp", 0, [("jp-cpi-all", "estat adapter requires RUSTATS_ESTAT_APP_ID")]),
        "au": _stats("au", 3, [("au-policy-rate", "RbaStatsError: RBA GET x HTTP 403: Access Denied")]),
    })
    assert (status, ok, failed) == ("ok", 3, 0)
    assert "нужен бесплатный ключ: jp 1" in message
    assert "не пускает наш сервер: au 1" in message
    assert alerts[0]["status"] == "ok"


def test_real_failure_is_counted_with_reason(auth_env, monkeypatch):
    (status, ok, failed, message), alerts = _run_with_stats(auth_env, monkeypatch, {
        "in": _stats("in", 0, [
            ("in-cpi-all", "MospiApiError: MoSPI GET https://api.mospi.gov.in/x failed: ConnectTimeoutError"),
        ]),
        "kr": _stats("kr", 0, [("kr-cpi-all", "ecos adapter requires RUSTATS_ECOS_API_KEY")]),
    })
    assert (status, ok, failed) == ("partial", 1, 1)
    assert "series errors (1): in (1): MospiApiError: MoSPI GET https://api.mospi.gov.in/x failed" in message
    assert "kr 1" in message
    assert alerts[0]["status"] == "partial"


def test_eurostat_quarantine_reason_lands_in_run_journal(monkeypatch):
    """Пульс читает журнал прогона: карантин разлома структуры назван с причиной, а не «1 набор с ошибкой»."""
    from app.services import world_eurostat_ingest as ingest
    from tests.test_world_eurostat_ingest import _job_env

    verdict = ('{"dataset_id": "nrg_stk_oem", "accept": false, "kept": 3, "remapped": 0, "orphans": 90, '
               '"orphans_listed": 88, "reason": "32 из 43 публичных карточек не нашли срез в новой структуре"}')
    _job_env(monkeypatch, (False, "STRUCTURE_VERDICT " + verdict))

    class Run:
        id = 7
        datasets_selected = 0
        error_message = None

    run = Run()

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        def add(self, obj):
            pass

        async def commit(self):
            pass

        async def refresh(self, obj):
            obj.id = 7

        async def get(self, *_):
            return run

    monkeypatch.setattr(ingest, "async_session", Session)
    asyncio.run(ingest.world_eurostat_ingest_job(shadow=False, include_imf=False))
    assert run.status == "partial" and run.datasets_failed == 1
    assert run.error_message == "карантин nrg_stk_oem: 32 из 43 публичных карточек не нашли срез в новой структуре"

"""Проверка загрузки данных 28.10.2026: три дефекта парсеров, найденные сверкой боевой БД с источниками.

1. ВВП по использованию читал зашитый `..._1kv-2026.xls` при опубликованном `..._2kv-2026.xls`.
2. Банк Бразилии: окно Selic с не-JSON ответом пропускалось молча, в БД остались дыры 2000-2018.
3. Росстат IPI: сбой текущего файла глотался, 86-131 точки каждого ряда переписывались значениями
   цепочки по одному историческому файлу.
(Пункт про лимит простоя транзакции national-core закрыт в main правкой оркестратора 6fc8ea0d.)
"""

from __future__ import annotations

import asyncio
from datetime import date
from types import SimpleNamespace

import pytest

import app.services.rosstat_ipi_parser as ipi_mod
import app.services.rosstat_sdds_fetcher as f
import app.services.world_adapters.bcb_sgs as bcb
from app.services.world_source_adapter import WorldSeriesRef


# ---------------------------------------------------------------- 1. ВВП по использованию


class _Resp:
    def __init__(self, status, content=b""):
        self.status_code, self.content, self.headers = status, content, {"content-type": "application/vnd.ms-excel"}


class _GdpSession:
    """Отдаёт 200 только для перечисленных адресов, остальные - 404."""

    def __init__(self, available):
        self.available = set(available)
        self.calls = []

    def get(self, url, **kw):
        self.calls.append(url)
        if url in self.available:
            return _Resp(200, f.XLS_MAGIC + b"payload")
        return _Resp(404)


def test_gdp_use_candidates_go_from_current_quarter_down_then_pinned():
    urls = f.gdp_use_candidate_urls(date(2026, 10, 28))
    assert urls[0].endswith("GDP-quarters-of-use-1995_4kv-2026.xls")
    assert urls[1].endswith("_3kv-2026.xls")
    assert urls[2].endswith("_2kv-2026.xls")
    assert urls[4].endswith("_4kv-2025.xls")  # переход через год
    assert f.ROSSTAT_STATIC_URLS["gdp_use_quarterly"] in urls  # 1kv-2026 в окне шести кварталов, второй раз не добавляется
    assert len(urls) == len(set(urls))
    # через год зашитый адрес выпадает из окна и добавляется последним запасным
    later = f.gdp_use_candidate_urls(date(2027, 9, 1))
    assert later[-1] == f.ROSSTAT_STATIC_URLS["gdp_use_quarterly"]


def test_gdp_use_takes_second_quarter_file_not_pinned_first_quarter(monkeypatch):
    q2 = f._GDP_USE_URL_TMPL.format(quarter=2, year=2026)
    q1 = f._GDP_USE_URL_TMPL.format(quarter=1, year=2026)
    session = _GdpSession([q2, q1])  # Росстат держит оба файла рядом (проверено 28.10.2026)
    monkeypatch.setattr(f, "_get_session", lambda: session)
    content, url = f.fetch_rosstat_gdp_use_latest(date(2026, 10, 28))
    assert url == q2
    assert session.calls == [
        f._GDP_USE_URL_TMPL.format(quarter=4, year=2026),
        f._GDP_USE_URL_TMPL.format(quarter=3, year=2026),
        q2,
    ]


def test_gdp_use_falls_back_to_pinned_url(monkeypatch):
    pinned = f.ROSSTAT_STATIC_URLS["gdp_use_quarterly"]
    monkeypatch.setattr(f, "_get_session", lambda: _GdpSession([pinned]))
    # 3 кв. 2027: шесть кварталов назад (до 2 кв. 2026 включительно) зашитого 1kv-2026 в списке нет - он добавляется последним
    _, url = f.fetch_rosstat_gdp_use_latest(date(2027, 9, 1))
    assert url == pinned


def test_gdp_use_network_failure_is_unreachable_not_not_found(monkeypatch):
    import requests

    class _Down:
        def get(self, *a, **kw):
            raise requests.ConnectionError("down")

    monkeypatch.setattr(f, "_get_session", lambda: _Down())
    with pytest.raises(f.RosstatUnreachable):
        f.fetch_rosstat_gdp_use_latest(date(2026, 10, 28))


def test_gdp_use_none_found_is_plain_runtime_error(monkeypatch):
    monkeypatch.setattr(f, "_get_session", lambda: _GdpSession([]))
    with pytest.raises(RuntimeError) as exc:
        f.fetch_rosstat_gdp_use_latest(date(2026, 10, 28))
    assert not isinstance(exc.value, f.RosstatUnreachable)


# ---------------------------------------------------------------- 2. Банк Бразилии


class _BcbResp:
    def __init__(self, status=200, payload=None, text=""):
        self.status_code, self._payload, self.text = status, payload, text

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


class _BcbSession:
    """Скрипт ответов по окнам: ключ - dataInicial (DD/MM/YYYY)."""

    def __init__(self, by_start, default=None):
        self.by_start = by_start
        self.default = default or _BcbResp(404, text='{"erro":{"detail":"Value(s) not found"}}')
        self.calls = []

    def get(self, url, params=None, **kw):
        start = (params or {}).get("dataInicial")
        self.calls.append(start)
        scripted = self.by_start.get(start)
        if isinstance(scripted, list):
            resp = scripted.pop(0) if len(scripted) > 1 else scripted[0]
        else:
            resp = scripted or self.default
        return resp


def _daily_ref():
    return WorldSeriesRef(
        provider="bcb_sgs", dataset_id="432", series_id="432", country_code="BR",
        frequency="daily", unit_code="PERCENT", dimensions={},
    )


def _row(d, v):
    return {"data": d, "valor": str(v)}


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(bcb, "_sleep", lambda s: None)


def test_bcb_daily_windows_start_in_1984_not_1900():
    sess = _BcbSession({})
    adapter = bcb.BcbSgsAdapter(session=sess)
    with pytest.raises(bcb.BcbSgsError):  # все окна пустые -> ряд без наблюдений
        asyncio.run(adapter.fetch_series(_daily_ref()))
    assert sess.calls[0] == "01/01/1984"
    assert len(sess.calls) <= 15  # с 1900 года окон было бы 40+


def test_bcb_non_json_window_is_retried_then_succeeds():
    # Окно 2004-2014 (даты зависят от разбиения с 1984) сначала отдаёт HTML, затем данные.
    windows = bcb._date_windows(bcb._DAILY_DEFAULT_DATE_FROM, date.today(), max_span_days=bcb._DAILY_MAX_SPAN_DAYS)
    key = bcb.format_br_date(windows[1][0])
    script = {
        bcb.format_br_date(windows[-1][0]): _BcbResp(200, [_row("28/10/2026", "13.75")]),
        key: [_BcbResp(200, None, text="<html>error</html>"), _BcbResp(200, [_row("04/12/2009", "8.75")])],
    }
    sess = _BcbSession(script)
    payload = asyncio.run(bcb.BcbSgsAdapter(session=sess).fetch_series(_daily_ref()))
    assert [o.period for o in payload.observations] == [date(2009, 12, 4), date(2026, 10, 28)]
    assert sess.calls.count(key) == 2


def test_bcb_persistent_failure_of_latest_window_fails_series():
    windows = bcb._date_windows(bcb._DAILY_DEFAULT_DATE_FROM, date.today(), max_span_days=bcb._DAILY_MAX_SPAN_DAYS)
    script = {
        bcb.format_br_date(windows[0][0]): _BcbResp(200, [_row("02/01/1990", "40.0")]),
        bcb.format_br_date(windows[-1][0]): _BcbResp(200, None, text="<html>error</html>"),
    }
    # без свежего окна ряд не обновится: раньше такой прогон выглядел успешным
    with pytest.raises(bcb.BcbSgsTransientError):
        asyncio.run(bcb.BcbSgsAdapter(session=_BcbSession(script)).fetch_series(_daily_ref()))


def test_bcb_persistent_failure_of_old_window_is_loud_and_keeps_fresh_data(caplog):
    windows = bcb._date_windows(bcb._DAILY_DEFAULT_DATE_FROM, date.today(), max_span_days=bcb._DAILY_MAX_SPAN_DAYS)
    broken_start = bcb.format_br_date(windows[-3][0])
    script = {
        bcb.format_br_date(windows[-1][0]): _BcbResp(200, [_row("28/10/2026", "13.75")]),
        broken_start: _BcbResp(200, None, text="<html>error</html>"),
    }
    with caplog.at_level("WARNING", logger=bcb.logger.name):
        payload = asyncio.run(bcb.BcbSgsAdapter(session=_BcbSession(script)).fetch_series(_daily_ref()))
    assert [o.period for o in payload.observations] == [date(2026, 10, 28)]
    assert any("исторические окна не загружены" in r.getMessage() for r in caplog.records)


def test_bcb_daily_windows_fit_the_gateway_limit():
    # ~9 мс на строку при таймауте шлюза ~30 с: окно не больше ~1100 дневных строк
    windows = bcb._date_windows(bcb._DAILY_DEFAULT_DATE_FROM, date(2026, 10, 28), max_span_days=bcb._DAILY_MAX_SPAN_DAYS)
    assert all((e - s).days + 1 <= 1095 for s, e in windows)
    assert len(windows) <= 15


def test_bcb_5xx_is_transient_and_404_not_found_stays_soft():
    windows = bcb._date_windows(bcb._DAILY_DEFAULT_DATE_FROM, date.today(), max_span_days=bcb._DAILY_MAX_SPAN_DAYS)
    latest = bcb.format_br_date(windows[-1][0])
    sess = _BcbSession({latest: _BcbResp(502, text="<html>bad gateway</html>")})
    with pytest.raises(bcb.BcbSgsTransientError):
        asyncio.run(bcb.BcbSgsAdapter(session=sess).fetch_series(_daily_ref()))
    assert sess.calls.count(latest) == 3  # попытка + два повтора, дальше ошибка

    ok_only_last = {latest: _BcbResp(200, [_row("28/10/2026", "13.75")])}
    payload = asyncio.run(bcb.BcbSgsAdapter(session=_BcbSession(ok_only_last)).fetch_series(_daily_ref()))
    assert len(payload.observations) == 1  # пустые окна до начала ряда (404 «значений нет») пропущены


# ---------------------------------------------------------------- 3. Росстат IPI


def test_ipi_current_file_failure_fails_the_run_instead_of_rebuilding_history(monkeypatch):
    monkeypatch.setattr(ipi_mod, "fetch_rosstat_static_xlsx", lambda key: (b"hist", "hist-url"))
    monkeypatch.setattr(ipi_mod, "parse_rosstat_ipi_mom_xlsx", lambda content, section="BCDE": {date(2023, 1, 1): 100.0})

    def _boom():
        raise f.RosstatUnreachable("Rosstat unreachable: IPI current-file requests failed on network")

    monkeypatch.setattr(ipi_mod, "fetch_rosstat_ipi_current", _boom)
    parser = ipi_mod.RosstatIpiParser()
    with pytest.raises(f.RosstatUnreachable):
        asyncio.run(parser._fetch_and_parse(None, SimpleNamespace(code="ipi"), {}, SimpleNamespace()))


def test_ipi_merges_history_and_current_when_both_available(monkeypatch):
    monkeypatch.setattr(ipi_mod, "fetch_rosstat_static_xlsx", lambda key: (b"hist", "hist-url"))
    monkeypatch.setattr(ipi_mod, "fetch_rosstat_ipi_current", lambda: (b"cur", "cur-url"))

    def _parse(content, section="BCDE"):
        if content == b"hist":
            return {date(2023, m, 1): 100.0 for m in range(1, 13)}
        return {date(2023, 12, 1): 101.0, date(2026, 1, 1): 100.5}

    monkeypatch.setattr(ipi_mod, "parse_rosstat_ipi_mom_xlsx", _parse)
    points, url = asyncio.run(
        ipi_mod.RosstatIpiParser()._fetch_and_parse(None, SimpleNamespace(code="ipi"), {}, SimpleNamespace())
    )
    assert url == "hist-url; cur-url"
    assert date(2026, 1, 1) in {p.date for p in points}


def test_ipi_current_fetch_reports_network_failure_as_unreachable(monkeypatch):
    import requests

    class _Down:
        def get(self, *a, **kw):
            raise requests.ConnectionError("down")

    monkeypatch.setattr(f, "_get_session", lambda: _Down())
    with pytest.raises(f.RosstatUnreachable):
        f.fetch_rosstat_ipi_current()

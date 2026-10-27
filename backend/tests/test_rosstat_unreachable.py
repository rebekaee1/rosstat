"""Сетевой отказ Росстата не должен выглядеть как «файл не найден» (вечерний ETL 27.10.2026)."""

import pytest
import requests

import app.services.rosstat_sdds_fetcher as f


class _DownSession:
    def get(self, *a, **kw):
        raise requests.ConnectionError("rosstat.gov.ru unreachable on all hops recently")


class _Resp:
    def __init__(self, status, text="", content=b"", ct="text/html"):
        self.status_code, self.text, self.content = status, text, content
        self.headers = {"content-type": ct}


class _NotFoundSession:
    def get(self, *a, **kw):
        return _Resp(404)


def test_resolve_raises_unreachable_when_every_request_failed_on_network():
    with pytest.raises(f.RosstatUnreachable):
        f.resolve_mediabank_file(
            catalog_urls=["https://rosstat.gov.ru/folder/1"],
            name_patterns=[r"demo14\.xlsx"],
            fallback_filenames=["demo14.xlsx"],
            session=_DownSession(),
        )


def test_resolve_keeps_not_found_when_server_answers_404():
    with pytest.raises(RuntimeError) as exc:
        f.resolve_mediabank_file(
            catalog_urls=["https://rosstat.gov.ru/folder/1"],
            name_patterns=[r"demo14\.xlsx"],
            fallback_filenames=["demo14.xlsx"],
            session=_NotFoundSession(),
        )
    assert not isinstance(exc.value, f.RosstatUnreachable)
    assert "not found" in str(exc.value)


def test_pdf_and_okpopul_report_unreachable(monkeypatch):
    monkeypatch.setattr(f, "_get_session", lambda: _DownSession())
    with pytest.raises(f.RosstatUnreachable):
        f.fetch_latest_socioeconomic_report_pdf()
    with pytest.raises(f.RosstatUnreachable):
        f.fetch_rosstat_okpopul()

"""Оглавление Евростата: обрыв соединения не роняет ночную задачу, повтор берёт ответ (круг 13)."""
import pytest
import requests

from app.services import world_eurostat_ingest as ing

TOC = 'x\tsts_trtu_m\tdataset\t01.10.2026\t01.01.2024\t\t\n'


class _Ok:
    content = TOC.encode()

    def raise_for_status(self):
        return None


def test_toc_retries_after_dropped_connection(monkeypatch):
    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        if len(calls) < 3:
            raise requests.ConnectionError("Remote end closed connection without response")
        return _Ok()

    monkeypatch.setattr(ing.requests, "get", fake_get)
    monkeypatch.setattr(ing.time, "sleep", lambda s: None)
    toc = ing._fetch_toc_sync()
    assert len(calls) == 3 and "sts_trtu_m" in toc


def test_toc_gives_up_after_three_attempts(monkeypatch):
    monkeypatch.setattr(ing.requests, "get", lambda url, timeout: (_ for _ in ()).throw(requests.Timeout("cold")))
    monkeypatch.setattr(ing.time, "sleep", lambda s: None)
    with pytest.raises(requests.Timeout):
        ing._fetch_toc_sync()

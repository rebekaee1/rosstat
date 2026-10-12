"""11–12.10.2026: api.webmaster.yandex.net не отвечал (ConnectTimeout), а журнал синхронизаций молчал."""
import asyncio

import httpx
import pytest

from app.services import analytics_backfill
from app.services.analytics_ingestion import describe_exception


class FakeDb:
    def __init__(self):
        self.added = []
        self.commits = 0

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        return None

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        return None


def test_describe_exception_keeps_type_for_empty_network_errors():
    assert describe_exception(httpx.ConnectTimeout("")) == "ConnectTimeout"
    assert describe_exception(ValueError("плохо")) == "ValueError: плохо"
    assert len(describe_exception(RuntimeError("x" * 900))) <= 500


def test_api_unreachable_leaves_a_failed_run_row(monkeypatch):
    from app.config import settings
    from app.services import yandex_webmaster_client

    monkeypatch.setattr(settings, "yandex_webmaster_token", "t")

    async def boom(self):
        raise httpx.ConnectTimeout("")

    monkeypatch.setattr(yandex_webmaster_client.YandexWebmasterClient, "user", boom)
    monkeypatch.setattr(analytics_backfill, "webmaster_sync_host_ids", lambda: ["https:ru.forecasteconomy.com:443"])
    db = FakeDb()
    from datetime import date

    with pytest.raises(httpx.ConnectTimeout):
        asyncio.run(analytics_backfill.backfill_webmaster_search_queries(db, date_from=date(2026, 10, 5), date_to=date(2026, 10, 11)))
    runs = list({id(o): o for o in db.added if getattr(o, "job_type", "") == "daily_search_queries"}.values())
    assert len(runs) == 1
    assert runs[0].status == "failed" and runs[0].error_message == "ConnectTimeout"

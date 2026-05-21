"""Правка №6: пустой ответ парсера не должен затирать историю в БД."""

import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.base_parser import BaseParser


class _StubParser(BaseParser):
    parser_type = "stub_empty"

    def __init__(self, points: list):
        self._points = points

    async def _fetch_and_parse(self, db, indicator, cfg, fetch_log):
        return self._points, "https://example.test/source"


def test_empty_parse_skips_bulk_upsert():
    parser = _StubParser([])
    indicator = MagicMock()
    indicator.code = "test-empty"
    indicator.id = 1
    indicator.model_config_json = {}
    fetch_log = MagicMock()
    fetch_log.error_message = None

    db = AsyncMock()

    async def _run():
        with patch("app.services.base_parser.bulk_upsert", new_callable=AsyncMock) as upsert:
            await parser.run(db, indicator, fetch_log)
        return upsert

    upsert = asyncio.run(_run())
    upsert.assert_not_called()
    assert fetch_log.status == "no_new_data"


def test_nonempty_parse_calls_bulk_upsert():
    parser = _StubParser([(date(2026, 1, 1), 1.0)])
    indicator = MagicMock()
    indicator.code = "test-ok"
    indicator.id = 2
    indicator.model_config_json = {"forecast_steps": 0}
    fetch_log = MagicMock()
    fetch_log.error_message = None

    db = AsyncMock()

    async def _run():
        with patch("app.services.base_parser.bulk_upsert", new_callable=AsyncMock, return_value=(1, 0)):
            with patch("app.services.base_parser.cache_invalidate_indicator", new_callable=AsyncMock):
                await parser.run(db, indicator, fetch_log)

    asyncio.run(_run())
    assert fetch_log.status == "success"

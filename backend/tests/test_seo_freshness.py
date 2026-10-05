"""Сигнал свежести для поисковиков: дата последней успешной загрузки данных из журнала загрузок."""
from __future__ import annotations

import asyncio
from datetime import date, datetime

from app.services.seo_renderer import _last_data_refresh


class _Db:
    def __init__(self, value=None, error: Exception | None = None):
        self._value, self._error = value, error

    async def scalar(self, _stmt):
        if self._error:
            raise self._error
        return self._value


def test_last_data_refresh_uses_fetch_log_date_not_today():
    got = asyncio.run(_last_data_refresh(_Db(datetime(2026, 10, 3, 6, 4, 12))))
    assert got == date(2026, 10, 3)


def test_last_data_refresh_is_none_without_successful_loads():
    assert asyncio.run(_last_data_refresh(_Db(None))) is None


def test_last_data_refresh_never_breaks_the_page_on_database_error():
    assert asyncio.run(_last_data_refresh(_Db(error=RuntimeError("db down")))) is None

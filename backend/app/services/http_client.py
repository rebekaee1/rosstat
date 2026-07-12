"""Shared requests.Session with automatic retries and User-Agent for all ETL fetchers."""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_RETRY_STRATEGY = Retry(
    total=3,
    backoff_factor=2,
    status_forcelist=[408, 429, 500, 502, 503, 504],
    allowed_methods=["GET", "POST"],
)


class _TimeoutAdapter(HTTPAdapter):
    """HTTPAdapter that applies a default timeout to every request."""

    def __init__(self, timeout: int = 60, **kwargs):
        self._default_timeout = timeout
        super().__init__(**kwargs)

    def send(self, request, **kwargs):
        kwargs.setdefault("timeout", self._default_timeout)
        return super().send(request, **kwargs)


def create_session(
    timeout: int = 60,
    *,
    retry: Retry | None = None,
) -> requests.Session:
    """Build a Session with retries.

    Defaults (`total=3`) stay for all parsers. Flaky hosts (e.g. Minfin) pass a
    stronger `retry=` without changing the global strategy.
    """
    s = requests.Session()
    adapter = _TimeoutAdapter(timeout=timeout, max_retries=retry or _RETRY_STRATEGY)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; ForecastEconomy/1.0; +https://forecasteconomy.com)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.3",
    })
    return s

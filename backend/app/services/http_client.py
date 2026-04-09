"""Shared requests.Session with automatic retries and User-Agent for all ETL fetchers."""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_RETRY_STRATEGY = Retry(
    total=3,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "POST"],
)


def create_session(timeout: int = 60) -> requests.Session:
    s = requests.Session()
    adapter = HTTPAdapter(max_retries=_RETRY_STRATEGY)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; ForecastEconomy/1.0; +https://forecasteconomy.com)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.3",
    })
    return s

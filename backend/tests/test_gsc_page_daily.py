"""Снимок Search Console по страницам (08.11.2026): полные показы страницы без разреза по запросу."""
from datetime import date

from app.services.gsc_client import page_rows


def test_page_rows_parse_and_skip_bad():
    result = {"rows": [
        {"keys": ["https://forecasteconomy.com/russia/indicator/key-rate/2025", "2026-11-05"],
         "impressions": 12, "clicks": 1, "ctr": 0.083, "position": 7.4},
        {"keys": ["", "2026-11-05"], "impressions": 3},          # пустая страница
        {"keys": ["https://x/", "not-a-date"], "impressions": 3},  # битая дата
        {"keys": ["https://x/"], "impressions": 3},                # не тот разрез
    ]}
    rows = page_rows(result)
    assert rows == [{
        "date": date(2026, 11, 5), "page": "https://forecasteconomy.com/russia/indicator/key-rate/2025",
        "impressions": 12, "clicks": 1, "ctr": 0.083, "position": 7.4,
    }]


def test_page_rows_empty():
    assert page_rows({}) == [] and page_rows({"rows": []}) == []

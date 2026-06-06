"""Tests for RosstatWeeklyCpiParser — bulletin discovery + cutoff_date filter."""

from datetime import date
from unittest.mock import MagicMock, patch

from app.services.rosstat_weekly_inflation_parser import (
    WeeklyPoint,
    _classify_local_code,
    _find_bulletin_urls_central_news,
    fetch_weekly_cpi,
)


# Minimal fragment that resembles real central-news HTML structure.
SAMPLE_CENTRAL_NEWS_PAGE = """
<html><body>
<div class="news-item">
    <a href="/storage/mediabank/67_06-05-2026.html"
       title="link">Об оценке индекса потребительских цен с 28 апреля по 4 мая 2026 года</a>
</div>
<div class="news-item">
    <a href="/storage/mediabank/66_06-05-2026.html"
       title="link">О потребительских ценах на нефтепродукты с 28 апреля по 4 мая 2026 года</a>
</div>
<div class="news-item">
    <a href="/storage/mediabank/65_29-04-2026.html"
       title="link">Об оценке индекса потребительских цен с 21 по 27 апреля 2026 года</a>
</div>
<div class="news-item">
    <a href="/storage/mediabank/64_29-04-2026.html"
       title="link">О потребительских ценах на нефтепродукты с 21 по 27 апреля 2026 года</a>
</div>
<div class="news-item">
    <a href="/storage/mediabank/63_29-04-2026.html"
       title="link">Деловая активность организаций в России в апреле 2026 года</a>
</div>
</body></html>
"""

EMPTY_PAGE = "<html><body></body></html>"


def _build_session_mock(pages: dict[int, str]) -> MagicMock:
    """Build a requests-like session whose .get returns canned page bodies."""
    session = MagicMock()

    def fake_get(url, params=None, timeout=None, verify=None):
        page = (params or {}).get("page", 1)
        resp = MagicMock()
        if page in pages:
            resp.status_code = 200
            resp.text = pages[page]
        else:
            resp.status_code = 200
            resp.text = EMPTY_PAGE
        return resp

    session.get = MagicMock(side_effect=fake_get)
    return session


class TestCentralNewsCrawler:
    """Crawler `_find_bulletin_urls_central_news` keeps только CPI-titled bulletins."""

    def test_extracts_only_cpi_bulletins(self):
        session = _build_session_mock({1: SAMPLE_CENTRAL_NEWS_PAGE})
        urls = _find_bulletin_urls_central_news(session, year=2026, max_pages=2)
        # Only the two "Об оценке индекса потребительских цен" titled items.
        assert len(urls) == 2
        assert urls[0].endswith("/65_29-04-2026.html")
        assert urls[1].endswith("/67_06-05-2026.html")

    def test_stops_at_year_boundary(self):
        """If max_year on page < requested year, crawler stops crawl."""
        page_2025 = SAMPLE_CENTRAL_NEWS_PAGE.replace("-2026.html", "-2025.html").replace(
            "2026 года", "2025 года",
        )
        session = _build_session_mock({1: SAMPLE_CENTRAL_NEWS_PAGE, 2: page_2025})
        urls = _find_bulletin_urls_central_news(session, year=2026, max_pages=5)
        # Page 1 = 2026 (2 CPI), page 2 = all 2025 → max_year < 2026 → stop.
        # Crawler still scans page 2 but adds nothing for year=2026.
        assert len(urls) == 2

    def test_empty_page_stops_crawl(self):
        session = _build_session_mock({1: SAMPLE_CENTRAL_NEWS_PAGE, 2: EMPTY_PAGE})
        urls = _find_bulletin_urls_central_news(session, year=2026, max_pages=10)
        assert len(urls) == 2

    def test_non_cpi_titles_skipped(self):
        # Page with 3 non-CPI items.
        page = """
        <a href="/storage/mediabank/1_01-01-2024.html"
           title="x">О промышленном производстве в декабре 2023</a>
        <a href="/storage/mediabank/2_01-01-2024.html"
           title="x">О задолженности по заработной плате</a>
        <a href="/storage/mediabank/3_01-01-2024.html"
           title="x">О динамике цен на бензин в декабре 2023</a>
        """
        session = _build_session_mock({1: page})
        urls = _find_bulletin_urls_central_news(session, year=2024, max_pages=2)
        assert urls == []


class TestClassifyLocalCode:
    def test_food_nonfood_services(self):
        assert _classify_local_code(111) == "food"
        assert _classify_local_code(4100) == "nonfood"
        assert _classify_local_code(9000) == "services"
        assert _classify_local_code("940.АГ") == "services"
        assert _classify_local_code(3) is None


class TestFetchWeeklyCpiCutoff:
    """Cutoff_date filters out XLSX-approximation для дат до bulletin cutoff."""

    @patch("app.services.rosstat_weekly_inflation_parser.fetch_bulletin_points")
    @patch("app.services.rosstat_weekly_inflation_parser._parse_weekly_xlsx_multi")
    @patch("app.services.rosstat_weekly_inflation_parser._load_product_weights")
    @patch("app.services.rosstat_weekly_inflation_parser.create_session")
    def test_cutoff_filters_xlsx_history(
        self, mock_session, mock_weights, mock_parse_xlsx, mock_bulletins,
    ):
        # Bulletin gives 2023+ values, XLSX gives 2022+ approximation.
        mock_bulletins.return_value = [
            WeeklyPoint(date=date(2023, 1, 9), value=100.5),
            WeeklyPoint(date=date(2023, 1, 16), value=100.3),
        ]
        xlsx_all = [
            WeeklyPoint(date=date(2022, 1, 10), value=100.8),  # XLSX, before cutoff
            WeeklyPoint(date=date(2022, 6, 1), value=99.9),    # XLSX, before cutoff
            WeeklyPoint(date=date(2023, 2, 1), value=100.2),   # XLSX, after cutoff
        ]
        mock_parse_xlsx.return_value = {
            "all": xlsx_all,
            "food": [],
            "nonfood": [],
            "services": [],
        }
        mock_weights.return_value = {"A": (0.5, "food"), "B": (0.5, "nonfood")}
        sess = MagicMock()
        sess.get = MagicMock(return_value=MagicMock(status_code=200, content=b"PK..."))
        mock_session.return_value = sess

        points = fetch_weekly_cpi(cutoff_date=date(2023, 1, 9))
        dates = [p.date for p in points]
        # 2022 points filtered out, 2023+ retained from both sources.
        assert date(2022, 1, 10) not in dates
        assert date(2022, 6, 1) not in dates
        assert date(2023, 1, 9) in dates
        assert date(2023, 1, 16) in dates
        assert date(2023, 2, 1) in dates

    @patch("app.services.rosstat_weekly_inflation_parser.fetch_bulletin_points")
    @patch("app.services.rosstat_weekly_inflation_parser._parse_weekly_xlsx_multi")
    @patch("app.services.rosstat_weekly_inflation_parser._load_product_weights")
    @patch("app.services.rosstat_weekly_inflation_parser.create_session")
    def test_no_cutoff_retains_all(
        self, mock_session, mock_weights, mock_parse_xlsx, mock_bulletins,
    ):
        mock_bulletins.return_value = [WeeklyPoint(date=date(2024, 1, 1), value=100.1)]
        mock_parse_xlsx.return_value = {
            "all": [
                WeeklyPoint(date=date(2022, 1, 10), value=100.8),
                WeeklyPoint(date=date(2023, 2, 1), value=100.2),
            ],
            "food": [],
            "nonfood": [],
            "services": [],
        }
        mock_weights.return_value = {"A": (0.5, "food")}
        sess = MagicMock()
        sess.get = MagicMock(return_value=MagicMock(status_code=200, content=b"PK..."))
        mock_session.return_value = sess

        points = fetch_weekly_cpi(cutoff_date=None)
        dates = [p.date for p in points]
        assert date(2022, 1, 10) in dates
        assert date(2023, 2, 1) in dates
        assert date(2024, 1, 1) in dates

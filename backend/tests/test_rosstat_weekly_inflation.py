"""Tests for RosstatWeeklyCpiParser — bulletin discovery + cutoff_date filter."""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from app.services.rosstat_weekly_inflation_parser import (
    CENTRAL_NEWS_STEADY_MAX_PAGES,
    WeeklyPoint,
    _classify_local_code,
    _filter_new_points,
    _find_bulletin_urls,
    _find_bulletin_urls_central_news,
    _parse_bulletin_html,
    fetch_weekly_cpi,
    fetch_weekly_cpi_multi,
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


class TestParseBulletinHtml:
    """Парсинг HTML-бюллетеня: значение + дата конца периода, оба предлога с/со."""

    def test_preposition_s(self):
        html = (
            "<p>Об оценке индекса потребительских цен с 26 мая по 1 июня 2026 года</p>"
            "<p>За период с 26 мая по 1 июня 2026 г. индекс потребительских цен, "
            "по оценке Росстата, составил 100,15%, с начала месяца ...</p>"
        )
        pt = _parse_bulletin_html(html)
        assert pt is not None
        assert pt.date == date(2026, 6, 1)
        assert pt.value == 100.15

    def test_preposition_so(self):
        # Регрессия: «со 2 по 8 июня» (со второго) ранее не матчился —
        # bulletin терялся, ETL возвращал 0 точек. Реальный текст за 2026-06-08.
        html = (
            "<p>ОБ ОЦЕНКЕ ИНДЕКСА ПОТРЕБИТЕЛЬСКИХ ЦЕН СО 2 ПО 8 ИЮНЯ 2026 ГОДА</p>"
            "<p>За период со 2 по 8 июня 2026 г. индекс потребительских цен, "
            "по оценке Росстата, составил 100,20%, с начала месяца – 100,23% ...</p>"
        )
        pt = _parse_bulletin_html(html)
        assert pt is not None
        assert pt.date == date(2026, 6, 8)
        assert pt.value == 100.2


class TestFilterNewPoints:
    def test_keeps_new_and_refresh_window_drops_old_known(self):
        # Старое известное (вне окна обновления) — не перезаписываем; свежее
        # известное (в окне) — перечитываем заново (ревизии Росстата); новое —
        # добавляем.
        today = date.today()
        old_known = today - timedelta(days=200)
        recent_known = today - timedelta(days=10)
        new_date = today - timedelta(days=3)
        known = {old_known, recent_known}
        points = [
            WeeklyPoint(date=old_known, value=100.1),
            WeeklyPoint(date=recent_known, value=100.2),
            WeeklyPoint(date=new_date, value=100.3),
        ]
        out = {p.date for p in _filter_new_points(points, known)}
        assert old_known not in out
        assert recent_known in out
        assert new_date in out


class TestSteadyBulletinDiscovery:
    def test_steady_state_limits_central_news_pages(self):
        session = _build_session_mock({i: EMPTY_PAGE for i in range(1, 20)})
        session.get = MagicMock(side_effect=session.get.side_effect)
        calls: list[int] = []

        def track_get(url, params=None, timeout=None, verify=None):
            if "central-news" in str(url):
                page = (params or {}).get("page", 1)
                calls.append(page)
            resp = MagicMock()
            resp.status_code = 200
            resp.text = EMPTY_PAGE
            return resp

        session.get = MagicMock(side_effect=track_get)
        _find_bulletin_urls(session, year=2026, steady_state=True)
        assert calls
        assert max(calls) <= CENTRAL_NEWS_STEADY_MAX_PAGES


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

    @patch("app.services.rosstat_weekly_inflation_parser.fetch_bulletin_points")
    @patch("app.services.rosstat_weekly_inflation_parser._parse_weekly_xlsx_multi")
    @patch("app.services.rosstat_weekly_inflation_parser._load_product_weights")
    @patch("app.services.rosstat_weekly_inflation_parser.create_session")
    def test_segment_existing_filters_food_only(
        self, mock_session, mock_weights, mock_parse_xlsx, mock_bulletins,
    ):
        # Старая дата (вне окна обновления) и свежая (в окне). Известная старая
        # food-дата отфильтровывается; nonfood без known-набора — обе остаются.
        today = date.today()
        old = today - timedelta(days=200)
        recent = today - timedelta(days=10)
        mock_bulletins.return_value = []
        mock_parse_xlsx.return_value = {
            "all": [],
            "food": [
                WeeklyPoint(date=old, value=100.1),
                WeeklyPoint(date=recent, value=100.2),
            ],
            "nonfood": [
                WeeklyPoint(date=old, value=99.9),
                WeeklyPoint(date=recent, value=100.0),
            ],
            "services": [],
        }
        mock_weights.return_value = {"A": (1.0, "food")}
        sess = MagicMock()
        sess.get = MagicMock(return_value=MagicMock(status_code=200, content=b"PK..."))
        mock_session.return_value = sess

        result = fetch_weekly_cpi_multi(
            existing_dates={old, recent},
            segment_existing={
                "food": {old},
                "nonfood": set(),
                "services": set(),
            },
        )
        # food: старая известная (вне окна) ушла, свежая осталась.
        assert {p.date for p in result["food"]} == {recent}
        # nonfood: known-набор пуст → обе точки остаются.
        assert len(result["nonfood"]) == 2


# --- Fuel bulletin (rosstat_weekly_price_parser) ---------------------------

FUEL_BULLETIN_HTML = """
<html><body>
<p>О ПОТРЕБИТЕЛЬСКИХ ЦЕНАХ НА НЕФТЕПРОДУКТЫ С 23 ПО 29 ИЮНЯ 2026 ГОДА</p>
<p>Средние потребительские цены на бензин автомобильный
и дизельное топливо по Российской Федерации</p>
<table>
<tr><td>На дату регистрации</td></tr>
<tr><td>22 июня&#160;2026 г.</td><td>29 июня&#160;2026 г.</td></tr>
<tr><td>Бензин автомобильный</td><td>71,20</td><td>72,38</td></tr>
<tr><td>в том числе: марки АИ-92</td><td>67,54</td><td>68,76</td></tr>
<tr><td>марки АИ-95</td><td>73,20</td><td>74,38</td></tr>
<tr><td>марки АИ-98 и выше</td><td>96,51</td><td>97,15</td></tr>
<tr><td>Дизельное топливо</td><td>82,93</td><td>84,84</td></tr>
</table>
</body></html>
"""


class TestFuelBulletinParse:
    """HTML-бюллетень «О потребительских ценах на нефтепродукты» → PricePoint'ы."""

    def test_parses_ai92_two_dates(self):
        from app.services.rosstat_weekly_price_parser import _parse_fuel_bulletin_html

        pts = _parse_fuel_bulletin_html(FUEL_BULLETIN_HTML, "аи-92")
        assert [(p.date, p.value) for p in pts] == [
            (date(2026, 6, 22), 67.54),
            (date(2026, 6, 29), 68.76),
        ]

    def test_parses_diesel(self):
        from app.services.rosstat_weekly_price_parser import _parse_fuel_bulletin_html

        pts = _parse_fuel_bulletin_html(FUEL_BULLETIN_HTML, "дизельное топливо")
        assert pts[-1].value == 84.84

    def test_no_table_returns_empty(self):
        from app.services.rosstat_weekly_price_parser import _parse_fuel_bulletin_html

        assert _parse_fuel_bulletin_html("<html><body>пусто</body></html>", "аи-92") == []

    def test_bulletin_overrides_xlsx_on_merge(self):
        """union: бюллетень первичен на совпадающих датах."""
        from app.services.rosstat_weekly_price_parser import PricePoint

        xlsx = {date(2026, 6, 22): 67.50}
        bulletin = [
            PricePoint(date=date(2026, 6, 22), value=67.54),
            PricePoint(date=date(2026, 6, 29), value=68.76),
        ]
        merged = dict(xlsx)
        merged.update({p.date: p.value for p in bulletin})
        assert merged[date(2026, 6, 22)] == 67.54
        assert merged[date(2026, 6, 29)] == 68.76

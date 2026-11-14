from datetime import date

from app.config import Settings
from app.services import seo_weekly_report as r


def test_flag_is_off_by_default():
    assert Settings.model_fields["seo_weekly_report_enabled"].default is False


def test_bot_family_by_ua():
    assert r.bot_family("Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)") == "googlebot"
    assert r.bot_family("Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)") == "yandex"
    assert r.bot_family("Mozilla/5.0 (compatible; bingbot/2.0)") == "bing"
    assert r.bot_family("Mozilla/5.0 Safari/605") is None


def test_week_windows_are_adjacent_seven_days():
    cur, prev = r.week_windows(date(2026, 10, 6))
    assert cur == (date(2026, 9, 30), date(2026, 10, 6))
    assert prev == (date(2026, 9, 23), date(2026, 9, 29))


def test_report_text_and_stale_warning():
    data = {
        "today": date(2026, 10, 12),
        "yandex": {"ru.": ({"imp": 33335, "clk": 474, "pos": 7.9}, {"imp": 21751, "clk": 376, "pos": 7.9})},
        "yandex_window": (date(2026, 9, 30), date(2026, 10, 6)),
        "last_yandex_day": date(2026, 10, 6),
        "google": ({"imp": 32470, "clk": 58, "pos": 17.7}, {"imp": 12660, "clk": 25, "pos": 16.5}),
        "google_window": (date(2026, 10, 3), date(2026, 10, 9)),
        "last_google_day": date(2026, 10, 9),
        "sitemap": {"https:ru.forecasteconomy.com:443": (date(2026, 10, 9), 946, 9543)},
        "webmaster_last_run": ("failed", date(2026, 10, 11), "ConnectTimeout"),
        "bots": {"googlebot": {"2xx": 990, "5xx": 10}},
    }
    text = r.format_seo_week(data)
    assert "доля кликов 1.42%" in text and "(+53%)" in text
    assert "946" in text and "googlebot: 1 000 ответов, 5xx — 10 (1.00%)" in text
    assert "данные запросов Яндекса последние за 06.10" in text   # старше трёх суток
    assert "упал: ConnectTimeout" in text
    assert "не означает ноль" in text


def test_adr31_block_reports_week_base_and_goal():
    """Замер ADR-0031 (14.11.2026): английские запросы apex, клики apex и годовых страниц, клики ru."""
    adr31 = {
        "en_window": (date(2026, 11, 4), date(2026, 11, 10)),
        "en": ({"imp": 280, "clk": 2}, {"imp": 325, "clk": 2}),
        "pages_window": (date(2026, 11, 4), date(2026, 11, 10)),
        "apex": ({"imp": 9000, "clk": 88}, {"imp": 8000, "clk": 70}),
        "apex_years": ({"imp": 5000, "clk": 44}, {"imp": 4000, "clk": 35}),
        "ru": ({"imp": 10, "clk": 0}, {"imp": 5, "clk": 0}),
    }
    text = "\n".join(r.format_adr31(adr31))
    assert "<b>Google, английский хост (ADR-0031)</b>" in text
    assert "Английские запросы (04.11–10.11): показы 280" in text and f"цель > {r._fmt_int(5000)}" in text
    assert "Клики forecasteconomy.com (04.11–10.11): 88" in text and "из них годовые страницы 44" in text
    assert "Клики ru.: 0 (было 0); цель > 10" in text
    assert r.format_adr31(None) == []
    full = r.format_seo_week({"today": date(2026, 11, 12), "adr31": adr31,
                              "last_yandex_day": date(2026, 11, 11), "last_google_day": date(2026, 11, 10)})
    assert "ADR-0031" in full


def test_adr31_queries_are_parameterized_and_scoped():
    """SQL замера: английские запросы — только apex и без кириллицы; годовые — регулярное выражение пути."""
    assert ":apex" in r._EN_QUERY and "[а-яА-ЯёЁ]" in r._EN_QUERY
    assert r._YEAR_PAGE.startswith("AND page ~ '^https://forecasteconomy\\.com/")
    assert r._YEAR_PAGE.endswith("/[0-9]{4}$'")


def test_adr31_collect_runs_against_both_tables():
    """Сбор: окно по последней дате каждой таблицы, пять сумм по параметрам (без подстановки строк в SQL)."""
    import asyncio

    calls = []

    class Result:
        def __init__(self, sql):
            self.sql = sql

        def scalar(self):
            return date(2026, 11, 10)

        def one(self):
            class Row:
                imp, clk = 100.0, 3.0
            return Row()

    class FakeDb:
        async def execute(self, statement, params=None):
            calls.append((str(statement), params))
            return Result(str(statement))

    out = asyncio.run(r._collect_adr31(FakeDb(), date(2026, 11, 10)))
    assert out["en"][0] == {"imp": 100.0, "clk": 3.0} and out["ru"][1]["clk"] == 3.0
    assert out["pages_window"] == (date(2026, 11, 4), date(2026, 11, 10))
    sums = [c for c in calls if "SUM(impressions)" in c[0]]
    assert len(sums) == 8  # en ×2, apex ×2, годовые ×2, ru ×2
    assert all(p["a"] <= p["b"] for _sql, p in sums)

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

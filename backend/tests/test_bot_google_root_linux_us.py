"""Сигнал google_root_linux_us (14.11.2026): добавка к счёту робота, не самостоятельная метка."""

from app.services.bot_score import BOT_THRESHOLD, SessionSignals, score_session, signal_breakdown

LINUX = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36"
WINDOWS = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36"


def _sig(**kw):
    base = dict(pageviews=1, clicks=0, moves=0, active_ms=0, max_scroll_pct=0, synthetic_clicks=0,
                visitor_sessions=1, has_portrait=True, device_type="desktop", ua_raw=LINUX,
                referrer="https://www.google.com/", timezone="America/New_York", cpu_cores=8,
                screen_w=1920, screen_h=1080)
    base.update(kw)
    return SessionSignals(**base)


def test_farm_fingerprint_without_input_is_bot_even_with_ordinary_cpu():
    s = _sig()
    assert "google_root_linux_us" in signal_breakdown(s)
    assert score_session(s) >= BOT_THRESHOLD


def test_signal_alone_is_not_a_verdict():
    for traces in ({"clicks": 1}, {"moves": 2}, {"max_scroll_pct": 15}, {"active_ms": 900}):
        s = _sig(**traces)
        assert "google_root_linux_us" in signal_breakdown(s)
        assert score_session(s) < BOT_THRESHOLD


def test_other_os_path_timezone_or_mobile_do_not_trigger():
    for kw in ({"ua_raw": WINDOWS}, {"referrer": "https://www.google.com/search?q=x"},
               {"referrer": "https://www.google.ru/"}, {"timezone": "Europe/Moscow"},
               {"device_type": "mobile"}, {"has_portrait": False}):
        assert "google_root_linux_us" not in signal_breakdown(_sig(**kw))

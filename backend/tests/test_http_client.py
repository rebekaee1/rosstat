"""Tests for http_client — timeout adapter."""

from app.services.http_client import create_session, _TimeoutAdapter


def test_create_session_has_timeout_adapter():
    s = create_session(timeout=30)
    adapter = s.get_adapter("https://example.com")
    assert isinstance(adapter, _TimeoutAdapter)
    assert adapter._default_timeout == 30


def test_session_has_user_agent():
    s = create_session()
    assert "ForecastEconomy" in s.headers.get("User-Agent", "")

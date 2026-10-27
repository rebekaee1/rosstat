"""Алерты планировщика не должны приходить без причины (пустой str(exc) у таймаутов)."""

import httpx

from app.services.alerting import exception_reason


def test_reason_uses_text_when_present():
    assert exception_reason(RuntimeError("boom")) == "boom"


def test_reason_falls_back_to_class_name_for_empty_message():
    assert exception_reason(httpx.ConnectTimeout("")) == "ConnectTimeout"


def test_reason_includes_cause_class():
    try:
        try:
            raise TimeoutError()
        except TimeoutError as inner:
            raise RuntimeError() from inner
    except RuntimeError as exc:
        assert exception_reason(exc) == "RuntimeError (TimeoutError)"


def test_reason_limit_and_none():
    assert len(exception_reason(RuntimeError("x" * 500), 200)) == 200
    assert exception_reason(None) == "причина не указана"

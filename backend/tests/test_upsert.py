"""Tests for the upsert helper — verify it generates correct SQL."""

from datetime import date

from app.services.upsert import upsert_indicator_data


def test_upsert_generates_insert():
    stmt = upsert_indicator_data(1, date(2024, 1, 1), 100.5)
    compiled = stmt.compile()
    sql = str(compiled)
    assert "INSERT INTO indicator_data" in sql
    assert "ON CONFLICT" in sql

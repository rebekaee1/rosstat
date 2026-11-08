"""Сторож данных при записи и ежедневная проверка базы (08.11.2026).

Повод: 05.11.2026 парсер цен на топливо записал 31 неделю датами 0001-…, derived размножили их до 194 точек,
годовые страницы /russia/indicator/fuel-*/{год} три дня отвечали 500.
"""
import asyncio
from datetime import date, timedelta

import pytest

import app.services.upsert as upsert
from app.services.data_sanity import format_findings
from app.services.upsert import _dedup_points, point_rejection


@pytest.mark.parametrize("dt, val, bad", [
    (date(2026, 1, 10), 60.1, False),
    (date(1897, 1, 1), 67.5, False),        # перепись 1897 года — законная точка
    (date(1, 1, 10), 47.4, True),           # инцидент 05.11.2026
    (date(1799, 12, 31), 1.0, True),
    (date.today() + timedelta(days=700), 1.0, False),
    (date.today() + timedelta(days=800), 1.0, True),
    (date(2026, 1, 1), float("nan"), True),
    (date(2026, 1, 1), float("inf"), True),
    (date(2026, 1, 1), "abc", True),
    ("2026-01-01", 1.0, True),
])
def test_point_rejection(dt, val, bad):
    assert (point_rejection(dt, val) is not None) is bad


def test_dedup_drops_impossible_points_and_reports_them():
    rejected = []
    out = _dedup_points([(date(1, 1, 10), 47.4), (date(2026, 1, 12), 60.0), (date(2026, 1, 19), None)], rejected)
    assert out == {date(2026, 1, 12): 60.0}
    assert [r[0] for r in rejected] == [date(1, 1, 10)]
    assert "раньше 1800 года" in rejected[0][2]


def test_bulk_upsert_does_not_write_rejected_and_reports(monkeypatch):
    reported = []

    async def fake_report(db, indicator_id, rejected):
        reported.append((indicator_id, list(rejected)))

    monkeypatch.setattr(upsert, "_report_rejected", fake_report)
    written = []

    async def fake_row_by_row(db, indicator_id, dedup):
        written.append(dict(dedup))
        return len(dedup), 0

    monkeypatch.setattr(upsert, "_bulk_upsert_row_by_row", fake_row_by_row)

    class _Db:
        bind = None

    added, _ = asyncio.run(upsert.bulk_upsert(_Db(), 7, [(date(1, 1, 10), 47.4), (date(2026, 1, 12), 60.0)]))
    assert added == 1
    assert written == [{date(2026, 1, 12): 60.0}]
    assert reported and reported[0][0] == 7 and len(reported[0][1]) == 1


def test_all_rejected_writes_nothing(monkeypatch):
    async def fake_report(db, indicator_id, rejected):
        return None

    monkeypatch.setattr(upsert, "_report_rejected", fake_report)

    class _Db:
        bind = None

    assert asyncio.run(upsert.bulk_upsert(_Db(), 7, [(date(1, 1, 10), 47.4)])) == (0, 0)


def test_report_without_telegram_only_logs(caplog):
    """Без токена (тесты, локально) — только лог, ни Redis, ни базы."""
    asyncio.run(upsert._report_rejected(None, 7, [(date(1, 1, 10), 47.4, "дата 0001-01-10 раньше 1800 года")]))
    assert "Сторож данных" in caplog.text


def test_sanity_findings_text():
    assert format_findings([]) is None
    text = format_findings([("fuel-ai92", 31, "0001-01-10", "0001-08-08"), ("fuel-ai92-avg-year", 1, "-infinity", "-infinity")])
    assert "32 точек у 2 рядов" in text
    assert "fuel-ai92 (31)" in text and "0001-01-10" in text
    assert "почисти битые точки" in text


def test_guard_and_sanity_kinds_go_to_morning_summary():
    from app.services.telegram_calm import HELD_KINDS, KIND_LABELS

    assert {"data_guard", "data_sanity"} <= HELD_KINDS
    assert "data_guard" in KIND_LABELS and "data_sanity" in KIND_LABELS

"""Tests for MinfinBudgetParser CSV parsing."""

from unittest.mock import MagicMock

import pytest
import requests

from app.services.minfin_budget_parser import (
    MinfinBudgetParser,
    _DATA_RE,
    _cache_set_csv_url,
    _find_csv_url,
    _invalidate_csv_url_cache,
    _parse_budget_csv,
    fetch_and_parse_budget,
    normalize_minfin_csv_url,
)


SAMPLE_CSV = """\
\ufeffГод,Месяц,"Доходы, всего",Нефтегазовые доходы,"Расходы, всего","Дефицит (-)/Профицит (+)"
2024,январь,2500.0,800.0,3000.0,-500.0
2024,февраль,5200.0,1700.0,5800.0,-600.0
2024,март,8100.0,2600.0,8000.0,100.0
2025,январь,2600.0,900.0,3200.0,-600.0
"""


def test_parse_budget_csv_monthly_values():
    points = _parse_budget_csv(SAMPLE_CSV)
    assert len(points) == 4

    jan24 = points[0]
    assert jan24.date.year == 2024 and jan24.date.month == 1
    assert jan24.value == -500.0

    feb24 = points[1]
    assert feb24.date.year == 2024 and feb24.date.month == 2
    assert feb24.value == -100.0  # -600 - (-500)

    mar24 = points[2]
    assert mar24.date.year == 2024 and mar24.date.month == 3
    assert mar24.value == 700.0  # 100 - (-600)

    jan25 = points[3]
    assert jan25.date.year == 2025 and jan25.date.month == 1
    assert jan25.value == -600.0


def test_parse_budget_csv_empty():
    points = _parse_budget_csv("Год,Месяц\n")
    assert len(points) == 0


def test_parse_budget_csv_skips_gap_months():
    """Пропуск месяца в накопленном CSV не должен списываться в один «месяц».

    Mar+Apr отсутствуют, есть Jan, Feb и May. May нельзя разложить в помесячное
    (cum[May]−cum[Feb] = Mar+Apr+May), поэтому точка May пропускается, а не
    превращается в ложный трёхмесячный «месяц».
    """
    csv_with_gap = """\
\ufeffГод,Месяц,"Доходы, всего",Нефтегазовые доходы,"Расходы, всего","Дефицит (-)/Профицит (+)"
2026,январь,2500.0,800.0,3000.0,-500.0
2026,февраль,5200.0,1700.0,5800.0,-600.0
2026,май,12000.0,3000.0,18000.0,-6000.0
"""
    points = _parse_budget_csv(csv_with_gap)
    months = [(p.date.month, p.value) for p in points]
    assert months == [(1, -500.0), (2, -100.0)]
    assert all(p.date.month != 5 for p in points), "месяц после пропуска не должен попадать в ряд"


def test_parse_budget_csv_fallback_columns():
    csv_no_deficit = """\
\ufeffГод,Месяц,"Доходы, всего","Расходы, всего"
2024,январь,2500.0,3000.0
2024,февраль,5200.0,5800.0
"""
    points = _parse_budget_csv(csv_no_deficit)
    assert len(points) == 2
    assert points[0].value == -500.0
    assert points[1].value == -100.0


def test_fetch_and_parse_budget_does_not_augment_from_press():
    """OpenData CSV-only: май после пропуска мар–апр не попадает в ряд."""
    points, _ = fetch_and_parse_budget("revenue")
    for p in points:
        assert p.value < 9000.0, (
            f"подозрительно большое помесячное значение {p.value} на {p.date}"
        )


def test_minfin_parser_replace_series_flag():
    assert MinfinBudgetParser.replace_series is True


def test_parse_budget_csv_revenue_target():
    csv = """\
\ufeffГод,Месяц,"Доходы, всего","Расходы, всего","Дефицит (-)/Профицит (+)"
2026,январь,2364.3,3993.3,-1628.9
2026,февраль,4767.4,8216.2,-3448.8
"""
    points = _parse_budget_csv(csv, target="revenue")
    assert [(p.date.month, p.value) for p in points] == [
        (1, 2364.3),
        (2, 2403.1),
    ]


def test_normalize_minfin_csv_url_strips_ru_locale():
    bad = (
        "https://minfin.gov.ru/ru/opendata/7710168360-fedbud_month/"
        "data-20260709T0100-structure-20210312T0100.csv"
    )
    good = (
        "https://minfin.gov.ru/opendata/7710168360-fedbud_month/"
        "data-20260709T0100-structure-20210312T0100.csv"
    )
    assert normalize_minfin_csv_url(bad) == good
    assert normalize_minfin_csv_url(good) == good


def test_data_re_accepts_legacy_and_timed_filenames():
    assert _DATA_RE.search("data-20250819-structure-20210312.csv")
    assert _DATA_RE.search("data-20260709T0100-structure-20210312T0100.csv")
    assert not _DATA_RE.search("structure-20210312.csv")


def test_find_csv_url_uses_process_cache(monkeypatch):
    _invalidate_csv_url_cache()
    calls = {"n": 0}

    def fake_discover(_session):
        calls["n"] += 1
        return (
            "https://minfin.gov.ru/opendata/7710168360-fedbud_month/"
            "data-20260709T0100-structure-20210312T0100.csv"
        )

    monkeypatch.setattr(
        "app.services.minfin_budget_parser._discover_csv_url_from_catalog",
        fake_discover,
    )
    monkeypatch.setattr(
        "app.services.minfin_budget_parser._persist_csv_url",
        lambda _url: None,
    )
    monkeypatch.setattr(
        "app.services.minfin_budget_parser._create_minfin_session",
        lambda **_kw: MagicMock(close=lambda: None),
    )

    a = _find_csv_url()
    b = _find_csv_url()
    assert a == b
    assert calls["n"] == 1
    _invalidate_csv_url_cache()


def test_find_csv_url_falls_back_to_persisted_on_catalog_error(monkeypatch):
    _invalidate_csv_url_cache()
    persisted = (
        "https://minfin.gov.ru/opendata/7710168360-fedbud_month/"
        "data-20260609T0100-structure-20210312T0100.csv"
    )

    def boom(_session):
        raise requests.exceptions.RetryError("too many 503")

    monkeypatch.setattr(
        "app.services.minfin_budget_parser._discover_csv_url_from_catalog",
        boom,
    )
    monkeypatch.setattr(
        "app.services.minfin_budget_parser._load_persisted_csv_url",
        lambda: persisted,
    )
    monkeypatch.setattr(
        "app.services.minfin_budget_parser._create_minfin_session",
        lambda **_kw: MagicMock(close=lambda: None),
    )

    assert _find_csv_url() == persisted
    _invalidate_csv_url_cache()


def test_find_csv_url_force_catalog_skips_stale_fallback(monkeypatch):
    _invalidate_csv_url_cache()
    _cache_set_csv_url(
        "https://minfin.gov.ru/opendata/7710168360-fedbud_month/"
        "data-STALE.csv"
    )

    def boom(_session):
        raise RuntimeError("catalog down")

    monkeypatch.setattr(
        "app.services.minfin_budget_parser._discover_csv_url_from_catalog",
        boom,
    )
    monkeypatch.setattr(
        "app.services.minfin_budget_parser._load_persisted_csv_url",
        lambda: "https://minfin.gov.ru/opendata/x/data-STALE.csv",
    )
    monkeypatch.setattr(
        "app.services.minfin_budget_parser._create_minfin_session",
        lambda **_kw: MagicMock(close=lambda: None),
    )

    with pytest.raises(RuntimeError, match="catalog down"):
        _find_csv_url(force_catalog=True)
    _invalidate_csv_url_cache()


def test_artifact_fallback_when_network_fails(monkeypatch):
    """При недоступности minfin.gov.ru парсер читает packaged CSV."""
    from app.services import minfin_budget_parser as m

    def boom(*a, **k):
        raise RuntimeError("503 simulated")

    monkeypatch.setattr(m, "_find_csv_url", boom)
    points, src = m.fetch_and_parse_budget("deficit")
    assert src.startswith("artifact://")
    assert len(points) >= 180
    assert points[-1].date.year >= 2026

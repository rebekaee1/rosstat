"""Страница сравнения стран не считает «темп от темпа» (13.11.2026).

Понятие «потребительские цены» на странице сравнения всегда показывается как
изменение за год. Ряд МВФ ``PCPIPCH`` (Япония, Корея и другие страны без
национального индекса) уже является изменением за год, китайский индекс — «тот же
месяц прошлого года = 100». До исправления страница, её картинка и sitemap пропускали
такие ряды через расчёт изменения за год второй раз: у Японии выходило 16,19 % при
настоящих 3,19 %.
"""

from __future__ import annotations

import re
from datetime import date
from types import SimpleNamespace

import pytest

from app.services.world_rank_values import (
    YOY_KIND_INDEX_MINUS_100,
    YOY_KIND_LEVEL,
    YOY_KIND_PASSTHROUGH,
    apply_rank_series,
    apply_rank_series_for,
    rank_yoy_kind,
)
from tests.test_world_compare_frequency import frequency_client  # noqa: F401  (фикстура)

IMF = SimpleNamespace(code="jp-weo-pcpipch", slice_json={"weo_code": "PCPIPCH"})
CHINA = SimpleNamespace(code="cn-cpi-all", slice_json={})
BRAZIL = SimpleNamespace(code="br-cpi-ipca-yoy", slice_json={})
EUROSTAT = SimpleNamespace(code="de-prc_hicp_minr-cp00-i15", slice_json={"coicop": "CP00", "unit": "I15"})

# Настоящие значения МВФ по Японии на 13.11.2026.
JAPAN = [(date(2022, 1, 1), 2.502978), (date(2023, 1, 1), 3.255119),
         (date(2024, 1, 1), 2.7474), (date(2025, 1, 1), 3.192241)]


class TestSeriesByKind:
    def test_kinds(self):
        assert rank_yoy_kind(IMF) == YOY_KIND_PASSTHROUGH
        assert rank_yoy_kind(BRAZIL) == YOY_KIND_PASSTHROUGH
        assert rank_yoy_kind(CHINA) == YOY_KIND_INDEX_MINUS_100
        assert rank_yoy_kind(EUROSTAT) == YOY_KIND_LEVEL

    def test_imf_inflation_is_not_transformed_twice(self):
        assert apply_rank_series_for(IMF, JAPAN, "yoy") == JAPAN
        # Прежний вызов без природы ряда давал «темп от темпа»: 30,05; −15,6; 16,19.
        broken = [round(value, 2) for _, value in apply_rank_series(JAPAN, "yoy")]
        assert broken == [30.05, -15.6, 16.19]

    def test_china_same_month_index_becomes_change(self):
        series = [(date(2025, 1, 1), 100.5), (date(2025, 2, 1), 99.3)]
        assert apply_rank_series_for(CHINA, series, "yoy") == [
            (date(2025, 1, 1), 0.5), (date(2025, 2, 1), -0.7),
        ]

    def test_index_level_still_gets_year_over_year(self):
        series = [(date(2023, 1, 1), 100.0), (date(2024, 1, 1), 104.0)]
        assert apply_rank_series_for(EUROSTAT, series, "yoy") == apply_rank_series(series, "yoy")
        assert apply_rank_series_for(EUROSTAT, series, "yoy")[-1][1] == pytest.approx(4.0)

    @pytest.mark.parametrize("indicator", [IMF, CHINA, BRAZIL, EUROSTAT])
    def test_level_mode_is_untouched(self, indicator):
        series = [(date(2024, 1, 1), 7.0), (date(2023, 1, 1), 5.0)]
        assert apply_rank_series_for(indicator, series, "level") == sorted(series)


def test_vs_page_shows_imf_inflation_as_published(frequency_client):  # noqa: F811
    """Германия (индекс Евростата) против Японии (МВФ): у Японии 2,5 %, а не −10,71 %."""
    response = frequency_client.get(
        "/seo/world-vs/germany-vs-japan/hicp-index",
        headers={"Host": "forecasteconomy.com", "X-FE-Locale": "en"},
    )
    assert response.status_code == 200, response.text[:300]
    html = response.text
    assert "Japan — 2.5 %" in html
    # Последняя ячейка строки таблицы — Япония: только опубликованные МВФ 3,2; 2,8; 2,5.
    # «Темп от темпа» давал бы −12,5 и −10,71.
    japan_cells = set(re.findall(r"<td>([^<]+)</td></tr>", html))
    assert japan_cells and japan_cells <= {"3.2", "2.8", "2.5"}


def test_no_caller_skips_the_series_kind():
    """Любой расчёт режима рейтинга обязан передать природу ряда."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "app"
    offenders = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"\bapply_rank_series\(([^()]*(?:\([^()]*\)[^()]*)*)\)", text):
            if "def apply_rank_series" in text[max(0, match.start() - 4):match.start() + 22]:
                continue
            if "yoy_kind" not in match.group(1):
                offenders.append(f"{path.relative_to(root)}: {match.group(0)[:70]}")
    assert offenders == []

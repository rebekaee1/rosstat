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


def test_vs_page_answers_in_words_and_titles_the_pair_first(frequency_client):  # noqa: F811
    """Заголовок английской страницы начинается с пары стран; под лидом — история пары словами (13.11.2026)."""
    en = frequency_client.get("/seo/world-vs/germany-vs-japan/hicp-index",
        headers={"Host": "forecasteconomy.com", "X-FE-Locale": "en"}).text
    title = re.search(r"<title>(.*?)</title>", en, re.S).group(1)
    assert title.startswith("Germany vs Japan: ") and title.endswith(", 2025") and "data comparison" not in title
    # Германия здесь месячная, Япония годовая: счёт периодов не выводится, у каждой страны своя подпись периода.
    assert "was higher in" not in en
    assert "Germany: highest 12 % (January 2024), lowest 10.62 % (February 2025)." in en
    assert "Japan: highest 2.8 % (2024), lowest 2.5 % (2025)." in en
    ru = frequency_client.get("/seo/world-vs/germany-vs-japan/hicp-index",
        headers={"Host": "ru.forecasteconomy.com", "X-FE-Locale": "ru"}).text
    assert "Германия: максимум — 12 % (январь 2024), минимум — 10,62 % (февраль 2025)." in ru
    assert "сравнение данных" in re.search(r"<title>(.*?)</title>", ru, re.S).group(1)


def test_vs_history_counts_periods_for_one_frequency():
    """Одна частота: счёт «выше в N из M периодов» и разрыв по краям; настоящие значения Евростата (доля от среднего ЕС)."""
    from app.services.locale import _locale_var
    from app.services.seo_world_compare import _pair_history

    germany = [(date(2022, 1, 1), 134.3), (date(2023, 1, 1), 132.8), (date(2024, 1, 1), 130.7), (date(2025, 1, 1), 129.8)]
    netherlands = [(date(2022, 1, 1), 155.1), (date(2023, 1, 1), 152.7), (date(2024, 1, 1), 154.2), (date(2025, 1, 1), 154.9)]
    common = dict(table_freq="annual", freq_a="annual", freq_b="annual", label_a_name="Germany", label_b_name="Netherlands",
        gen_a="Германии", gen_b="Нидерландов", vsfx_a=" %", vsfx_b=" %", diff_sfx=" pp")
    token = _locale_var.set("en")
    try:
        english = _pair_history(germany, netherlands, en=True, **common)
        short = _pair_history(germany[:2], netherlands[:2], en=True, **common)
        mixed = _pair_history(germany, netherlands, en=True, **{**common, "table_freq": None})
    finally:
        _locale_var.reset(token)
    assert english == (
        "From 2022 to 2025, Netherlands was higher in 4 of 4 periods. The gap was 20.8 pp in 2022 and 25.1 pp in 2025. "
        "Germany: highest 134.3 % (2022), lowest 129.8 % (2025). Netherlands: highest 155.1 % (2022), lowest 152.7 % (2023).")
    token = _locale_var.set("ru")
    try:
        ru = _pair_history(germany, netherlands, en=False, **{**common, "label_a_name": "Германия", "label_b_name": "Нидерланды", "diff_sfx": " п.п."})
    finally:
        _locale_var.reset(token)
    assert ru.startswith("За 2022–2025 значение у Нидерландов было выше в 4 из 4 периодов. Разница: 20,8 п.п. в начале периода (2022), 25,1 п.п. в конце (2025).")
    # Короткая история и разные частоты.
    assert short == ""
    assert "was higher in" not in mixed and "The gap was" not in mixed and mixed.startswith("Germany: highest")

"""Региональный bounded context: артефакт данных, реестр территорий, SEO-текст.

Тесты герметичны: живая БД не нужна. Проверяются инварианты, на которых стоит
весь блок: целостность артефакта app/data/regional/ (сидер зальёт его as-is),
согласованность реестра регионов и русская типографика SSR-текстов.
"""

import csv
import gzip
import json
import math
from pathlib import Path

import pytest

from app.services.seo_regional import _fmt, _pct, _rank_phrase, _times_word

DATA_DIR = Path(__file__).parent.parent / "app" / "data" / "regional"


@pytest.fixture(scope="module")
def artifact():
    regions = json.loads((DATA_DIR / "regions.json").read_text())
    indicators = json.loads((DATA_DIR / "indicators.json").read_text())
    points = []
    with gzip.open(DATA_DIR / "data.csv.gz", "rt", encoding="utf-8") as fh:
        reader = csv.reader(fh, delimiter=";")
        next(reader)
        for code, rslug, year, value in reader:
            points.append((code, rslug, int(year), float(value)))
    return regions, indicators, points


class TestRegistry:
    def test_territory_composition(self, artifact):
        regions, _, _ = artifact
        kinds = {}
        for r in regions:
            kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
        # 85 субъектов (без новых территорий 2022), РФ, 8 ФО, 2 остатка-агрегата
        assert kinds["region"] == 85
        assert kinds["country"] == 1
        assert kinds["district"] == 8
        assert kinds.get("remainder", 0) == 2

    def test_slugs_unique_and_districts_resolve(self, artifact):
        regions, _, _ = artifact
        slugs = [r["slug"] for r in regions]
        assert len(slugs) == len(set(slugs))
        known = set(slugs)
        for r in regions:
            if r["kind"] == "region":
                assert r["district"] in known, r["slug"]


class TestArtifact:
    def test_indicator_codes_unique(self, artifact):
        _, indicators, _ = artifact
        codes = [i["code"] for i in indicators]
        assert len(codes) == len(set(codes))

    def test_all_units_non_empty(self, artifact):
        """В-8 (CTO-аудит 2026-07-06): «Соотношение мужчин и женщин: 1200»
        без «на 1000 мужчин» — обман витрины. 79 таблиц без единицы в шапке
        закрыты кураторским фолбэком scripts/regional/unit_fallbacks.py."""
        _, indicators, _ = artifact
        empty = [i["code"] for i in indicators if not (i.get("unit") or "").strip()]
        assert not empty, f"показатели без unit: {empty[:10]}"

    def test_units_have_no_defective_templates(self, artifact):
        """P1: unit — единица измерения, не момент учёта и не голое «тысяч».

        Ловит: пустое существительное («тысяч»), «на конец/начало года» в unit,
        «тысяча гектаров», «в процентах» / длинные «в процентах …», «тысяч га»,
        ед.ч. «гектар»/«килограмм», сокращение «млн руб.».
        """
        import sys

        regional_scripts = Path(__file__).resolve().parents[2] / "scripts" / "regional"
        sys.path.insert(0, str(regional_scripts))
        from unit_normalize import unit_defect  # noqa: E402

        _, indicators, _ = artifact
        bad = [
            (i["code"], i["unit"], unit_defect(i["unit"]))
            for i in indicators
            if unit_defect(i.get("unit") or "")
        ]
        assert not bad, f"дефектные unit ({len(bad)}): {bad[:12]}"

    def test_timing_caveats_live_in_note_not_unit(self, artifact):
        """Момент учёта сохраняется в note, а unit — счётная единица."""
        _, indicators, _ = artifact
        by_code = {i["code"]: i for i in indicators}
        org = by_code["chislo-organizatsiy"]
        assert org["unit"] == "единиц"
        assert "на конец года" in (org.get("note") or "")
        unemployed = by_code["chislennost-nezanyatyh-grazhdan-sostoyaschih-na-uchete-v"]
        assert unemployed["unit"] == "тысяч человек"
        assert "на конец года" in (unemployed.get("note") or "")
        families = by_code[
            "predostavlenie-grazhdanam-zhilyh-pomescheniy-chislo-semey-sostoyavshih"
        ]
        assert families["unit"] == "тысяч семей"
        assert "на конец года" in (families.get("note") or "")

    def test_percent_unit_is_percent_sign(self, artifact):
        """SSR печатает «1,5 %», а не «1,5 в процентах»."""
        _, indicators, _ = artifact
        urban = next(
            i for i in indicators
            if i["code"] == "udelnyy-ves-gorodskogo-naseleniya-v-obschey-chislennosti"
        )
        assert urban["unit"] == "%"
        yoy = next(
            i for i in indicators
            if i["code"] == "izmenenie-srednegodovoy-chislennosti-zanyatyh"
        )
        assert yoy["unit"] == "% к предыдущему году"
        # Как собирается публичная фраза в seo_regional.
        assert f"{_fmt(1.5)} {urban['unit']}" == "1,5 %"

    def test_points_reference_known_metadata(self, artifact):
        regions, indicators, points = artifact
        known_codes = {i["code"] for i in indicators}
        known_slugs = {r["slug"] for r in regions}
        bad = [p for p in points if p[0] not in known_codes or p[1] not in known_slugs]
        assert not bad, bad[:5]

    def test_years_and_values_sane(self, artifact):
        _, _, points = artifact
        for code, rslug, year, value in points:
            assert 1990 <= year <= 2026, (code, year)
            assert math.isfinite(value), (code, rslug, year)

    def test_no_duplicate_points(self, artifact):
        _, _, points = artifact
        keys = {(p[0], p[1], p[2]) for p in points}
        assert len(keys) == len(points)

    def test_scale_of_backfilled_sections(self, artifact):
        """Дособранные ряды: РФ-строка не должна остаться в «тыс.» при регионах в единицах."""
        _, indicators, points = artifact
        by_code = {i["code"]: i for i in indicators}
        crime = "chislo-prestupleniy-nesovershennoletnih"
        assert crime in by_code
        vals = {(p[1], p[2]): p[3] for p in points if p[0] == crime}
        # РФ 2017 = 45,3 тыс. случаев -> в артефакте абсолют
        assert vals[("russia", 2017)] == pytest.approx(45300)
        # регион строго меньше страны
        assert vals[("moskva", 2017)] < vals[("russia", 2017)]

    def test_history_extended_into_nineties(self, artifact):
        _, indicators, _ = artifact
        by_table = {i["table_code"]: i for i in indicators}
        assert by_table["1.9"]["year_min"] == 1990   # рождаемость
        assert by_table["22.1"]["year_min"] == 1990  # преступность на 100 000

    def test_external_trade_present(self, artifact):
        _, indicators, _ = artifact
        trade = [i for i in indicators if i["section_num"] == 21]
        assert len(trade) == 4
        assert all("(2023)" in i["source_sheet"] for i in trade)


class TestSeoTypography:
    def test_fmt_russian(self):
        assert _fmt(146980.061) == "146\u202f980"
        assert _fmt(45.34) == "45,3"
        assert _fmt(0.567) == "0,57"
        assert _fmt(None) == "—"
        assert _fmt(1000.0) == "1\u202f000"

    def test_times_word_agreement(self):
        assert _times_word(2.5) == "в 2,5 раза"
        assert _times_word(4) == "в 4 раза"
        assert _times_word(45) == "в 45 раз"

    def test_pct_phrases(self):
        assert _pct(122.2, 100) == "вырос на 22,2%"
        assert _pct(50, 100) == "снизился на 50%"
        assert _pct(4460, 100) == "вырос в 44,6 раза"
        assert _pct(100.001, 100) == "практически не изменился"
        assert _pct(5, 0) is None

    def test_rank_phrase(self):
        # В-31: нейтральная формулировка вместо «лидера» — «наибольшее значение»
        # не хвалит регион за нежелательные метрики (преступность, аборты).
        assert "наибольш" in _rank_phrase(1, 85)
        assert "лидер" not in _rank_phrase(1, 85).lower()
        assert "положен" in _rank_phrase(85, 85)
        # Curated lower_better — язык достижений без слова «лидер».
        assert "лучших" in _rank_phrase(1, 85, achievement=True)
        assert "место" in _rank_phrase(40, 85, achievement=True)

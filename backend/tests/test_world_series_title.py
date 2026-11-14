"""Названия рядов стран мира с уточнением среза (14.11.2026).

Замер `scripts/world-title-duplicates.py` на локальной копии каталога 14.11: рядов в группах с
одинаковым названием внутри страны — ru 171 970 → 52 646, en 259 108 → 23 649 (из 278 847).
Подписи — из официальных кодлистов Евростата (английские) и перевода официального термина (русские).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.data.eurostat_dim_labels_en import label_for_dim_member as label_en
from app.data.eurostat_dim_labels_en import official_label_en
from app.data.eurostat_dim_labels_ru import label_for_dim_member as label_ru
from app.data.eurostat_dim_labels_ru_official import RU_FROM_OFFICIAL_EN
from app.services import world_series_title as wst

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = json.loads((ROOT / "backend/app/data/eurostat_codelists_en.json").read_text("utf-8"))


def _row(country_id, name_ru, slice_json, name_en="Motor coaches, buses and trolley buses by age", code="x"):
    return SimpleNamespace(country_id=country_id, name_ru=name_ru, name_en=name_en, slice_json=slice_json, code=code)


BUSES = "Автобусы и троллейбусы по возрасту, штук"


@pytest.fixture(autouse=True)
def clean_context():
    token = wst._TITLE_AXES.set(None)
    yield
    wst._TITLE_AXES.reset(token)


def test_differing_axes_only_for_same_name_groups_and_varying_axes():
    rows = [
        _row(1, BUSES, {"age": "Y_LT2", "unit": "NR"}),
        _row(1, BUSES, {"age": "Y10-20", "unit": "NR"}),
        _row(1, "Население", {"age": "TOTAL"}, name_en="Population"),
        _row(2, BUSES, {"age": "Y_LT2", "unit": "NR"}),
    ]
    axes = wst.differing_axes(rows)
    assert axes[("ru", 1, BUSES)] == frozenset({"age"})
    assert ("ru", 1, "Население") not in axes  # один ряд — уточнять нечего
    assert ("ru", 2, BUSES) not in axes  # другая страна — своя группа


def test_title_gets_short_qualifier_only_with_siblings():
    rows = [_row(1, BUSES, {"age": "Y_LT2"}), _row(1, BUSES, {"age": "Y10-20"}), _row(1, BUSES, {"age": "TOTAL"})]
    assert wst.world_series_title(rows[0], "ru") == BUSES  # карта не загружена — как раньше
    wst.bind_title_axes(wst.differing_axes(rows))
    assert wst.world_series_title(rows[0], "ru") == f"{BUSES} (младше 2 лет)"
    assert wst.world_series_title(rows[1], "en") == "Motor coaches, buses and trolley buses by age (10–20 years)"
    assert wst.world_series_title(rows[2], "ru") == BUSES  # «итого» — базовое имя
    titles = {wst.world_series_title(row, "ru") for row in rows}
    assert len(titles) == 3


def test_label_already_in_name_is_not_repeated():
    rows = [
        _row(1, "Валовая добавленная стоимость, % ВВП", {"na_item": "B1G", "nace_r2": "G-I"}),
        _row(1, "Валовая добавленная стоимость, % ВВП", {"na_item": "B1G", "nace_r2": "R-U"}),
    ]
    wst.bind_title_axes(wst.differing_axes(rows))
    assert wst.world_series_title(rows[0], "ru") == (
        "Валовая добавленная стоимость, % ВВП (торговля, транспорт, гостиницы и общепит)"
    )
    assert "валовая добавленная стоимость (" not in wst.world_series_title(rows[1], "ru").lower()


def test_russian_translations_are_tied_to_official_english_labels():
    """Каждый перевод — пара с официальной английской подписью снимка кодлистов Евростата."""
    labels = SNAPSHOT["labels"]
    for dim, members in RU_FROM_OFFICIAL_EN.items():
        for code, (english, russian) in members.items():
            assert labels.get(dim, {}).get(code) == english, (dim, code)
            assert russian and russian == russian.strip() and not any("a" <= ch.lower() <= "z" for ch in russian)
            assert label_ru(dim, code), (dim, code)


def test_english_labels_come_from_official_snapshot():
    assert SNAPSHOT["source"].startswith("https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/codelist/ESTAT/")
    assert official_label_en("wstatus", "EMP") == "employed persons"
    assert label_en("statinfo", "MEAN_EI") == "mean equivalised income"
    assert label_en("wstatus", "NO_SUCH_CODE") is None


def test_russian_age_grammar():
    assert label_ru("age", "Y_LT2") == "младше 2 лет"
    assert label_ru("age", "Y_LT1") == "младше 1 года"
    assert label_ru("age", "Y_LT21") == "младше 21 года"


def _script():
    spec = importlib.util.spec_from_file_location("world_title_duplicates", ROOT / "scripts/world-title-duplicates.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_duplicate_measure_counts_groups_and_missing_labels():
    script = _script()
    rows = [
        _row(1, BUSES, {"age": "Y_LT2"}), _row(1, BUSES, {"age": "Y_XX"}), _row(1, BUSES, {"age": "TOTAL"}),
        _row(1, "Население", {}), _row(2, "Население", {}),
    ]
    groups = script.series_groups(rows, lambda row: row.name_ru)
    from app.data.eurostat_dim_labels_ru import is_dim_totalish

    report = script.summarize(groups, lambda axis, value: label_ru(axis, value), is_dim_totalish)
    assert report["groups"] == 1 and report["series_in_groups"] == 3 and report["series_total"] == 5
    assert report["differing_axes"] == [("age", 1)]
    assert report["missing_labels"] == [("age=Y_XX", 1)]  # «итого» не требует подписи

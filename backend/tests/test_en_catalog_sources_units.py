"""Круг 13: источники и единицы каталога не остаются русскими в английской версии (Brent: «Управление энергетической информации США»)."""
import re
from pathlib import Path

import pytest

from app.services.display import localize_unit
from app.services.seo_i18n import translate_source

SEED = (Path(__file__).resolve().parents[1] / "seed_data.py").read_text(encoding="utf-8")
CYR = re.compile(r"[А-Яа-яЁё]")
# Источники мировых карточек на стенде 13.10 (SELECT DISTINCT source FROM world_indicators)
WORLD_SOURCES = [
    "Евростат", "Бюро экономического анализа США", "Международный валютный фонд",
    "Федеральный резервный банк Сент-Луиса", "Австралийское бюро статистики",
    "Управление национальной статистики Великобритании", "Банк Бразилии", "Статистическое управление Канады",
    "Банк Мексики", "Банк Японии", "Министерство статистики и программной реализации Индии",
    "Китайская система валютных торгов", "Национальное статистическое бюро Китая", "Банк Канады",
    "Резервный банк Индии", "Банк Англии", "Бюро переписи населения США",
    "Бразильский институт географии и статистики (IBGE)",
]


def test_seed_has_sources_to_check():
    assert len(set(re.findall(r'"source":\s*"([^"]+)"', SEED))) >= 12


@pytest.mark.parametrize("source", sorted(set(re.findall(r'"source":\s*"([^"]+)"', SEED))) + WORLD_SOURCES)
def test_source_has_english_form(source):
    assert not CYR.search(translate_source(source, "en") or ""), source
    assert translate_source(source, "ru") == source


def test_brent_source_in_english():
    assert translate_source("Управление энергетической информации США (EIA)", "en") == (
        "U.S. Energy Information Administration (EIA)"
    )


@pytest.mark.parametrize("unit", sorted(set(re.findall(r'"unit":\s*"([^"]+)"', SEED))))
def test_seed_unit_has_english_form(unit):
    assert not CYR.search(localize_unit(unit, locale="en")), unit
    assert localize_unit(unit, locale="ru") == unit

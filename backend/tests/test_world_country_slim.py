"""Слим-форма каталога страны (`?slim=1`, круг 12): без потерь, меньше байт, клиент восстанавливает прежний вид."""
from __future__ import annotations

import copy
import json

from app.api.world import slim_country_payload

_DEFAULTS = {
    "simple_name": None, "aggregated_frequencies": [], "merged_slices": [],
    "last_value": None, "last_date": None, "prev_value": None, "change": None, "archived": False,
}


def _expand(data: dict) -> dict:
    """Зеркало `expandSlimCountry` на клиенте (frontend/src/lib/worldApi.js)."""
    data = copy.deepcopy(data)
    for cat in data["categories"]:
        for item in cat["indicators"]:
            item.setdefault("category_ru", cat["name_ru"])
            item.setdefault("category", cat["name"])
            item.setdefault("category_en", cat["name_en"])
            item.setdefault("name_ru", item.get("name"))
            item.setdefault("unit_ru", item.get("unit"))
            for key, value in _DEFAULTS.items():
                item.setdefault(key, copy.deepcopy(value))
    data.pop("slim")
    return data


def _payload() -> dict:
    def item(code, **extra):
        base = {
            "code": code, "name_ru": f"Показатель {code}", "name": f"Показатель {code}", "name_en": f"Indicator {code}",
            "simple_name": None, "unit_ru": "млн евро", "unit": "млн евро", "unit_suffix": "млн евро",
            "category_ru": "Бизнес", "category": "Бизнес", "frequency": "annual", "frequencies": ["annual"],
            "aggregated_frequencies": [], "last_value": 1.5, "last_date": "2025-01-01", "prev_value": None,
            "change": None, "points_count": 12, "archived": False, "merged_slices": [], "category_en": "Business",
        }
        base.update(extra)
        return base

    return {
        "country": {"slug": "germany"},
        "categories": [{
            "name": "Бизнес", "name_en": "Business", "name_ru": "Бизнес", "count": 3,
            "indicators": [
                item("a"),
                item("b", simple_name="Госдолг", merged_slices=[{"code": "x", "unit": "%"}], archived=True),
                item("c", name="Иное имя", name_en="Other", unit="%", headline={"value": 1}),
            ],
        }],
        "overview": [], "coverage": {}, "market_indicators": [],
    }


def test_slim_roundtrip_is_lossless():
    full = _payload()
    slim = slim_country_payload(full)
    assert slim["slim"] == 1 and "slim" not in full, "исходный объект не меняется"
    assert _expand(slim) == full


def test_slim_is_much_smaller_and_drops_repeats():
    full = _payload()
    slim = slim_country_payload(full)
    item = slim["categories"][0]["indicators"][0]
    for key in ("category", "category_ru", "category_en", "name_ru", "unit_ru", "simple_name", "merged_slices", "archived"):
        assert key not in item
    assert len(json.dumps(slim, ensure_ascii=False)) < 0.7 * len(json.dumps(full, ensure_ascii=False))
    # у карточки с отличающимся именем/единицей поля сохраняются
    third = slim["categories"][0]["indicators"][2]
    assert third["name"] == "Иное имя" and third["name_ru"] == "Показатель c" and third["unit_ru"] == "млн евро"

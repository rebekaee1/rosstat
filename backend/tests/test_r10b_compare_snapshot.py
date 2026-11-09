"""R10-B: сравнение цен собирается из снимков регионов без обращения к базе."""
from types import SimpleNamespace

from app.services.r4a_price_compare import BASKET, compose_pair


def _snap(factor: float, wage: float) -> dict:
    return {"prices": {code: [202609, 100.0 * factor] for code, _q in BASKET}, "wage": {"2025": wage}}


def _regions():
    return SimpleNamespace(slug="a-oblast", name="А область"), SimpleNamespace(slug="b-kray", name="Б край")


def test_compose_pair_from_snapshots():
    ra, rb = _regions()
    out = compose_pair("a-oblast", "b-kray", ra, rb, _snap(1.0, 60000), _snap(1.1, 75000))
    assert out["basket"]["cheaper_slug"] == "a-oblast"
    assert out["basket"]["diff_pct"] == 10.0
    assert out["wage"]["year"] == 2025
    assert out["cheaper_count"]["a"] == out["cheaper_count"]["total"]


def test_compose_pair_without_common_wage_year():
    ra, rb = _regions()
    a, b = _snap(1.0, 60000), _snap(1.0, 70000)
    b["wage"] = {"2024": 70000.0}
    out = compose_pair("a-oblast", "b-kray", ra, rb, a, b)
    assert out["wage"] is None
    assert out["basket"]["cheaper_slug"] is None

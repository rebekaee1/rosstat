"""Чистые части скрипта эксперимента индексации (выборка и сравнение)."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "seo_index_experiment", Path(__file__).resolve().parents[1] / "scripts" / "seo-index-experiment.py"
)
exp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(exp)


def test_sample_is_fixed_by_seed_and_split_between_hosts():
    shards = {"world-years": [f"/c/indicator/x/{i}" for i in range(100)], "world-vs": ["/a-vs-b/gdp"]}
    first = exp.pick_sample(shards, 6, seed=13)
    assert first == exp.pick_sample(shards, 6, seed=13)
    assert first != exp.pick_sample(shards, 6, seed=14)
    hosts = [u.split("/")[2] for u in first["world-years"]]
    assert hosts.count("forecasteconomy.com") == 3 and hosts.count("ru.forecasteconomy.com") == 3
    assert len(first["world-vs"]) == 1


def test_compare_prints_share_by_type_and_day():
    history = {
        "2026-10-12": [{"type": "world-years", "indexed": False}, {"type": "world-years", "indexed": True},
                       {"type": "world-vs", "indexed": True}],
        "2026-10-26": [{"type": "world-years", "indexed": True}, {"type": "world-years", "indexed": True},
                       {"type": "world-vs", "indexed": True}],
    }
    text = exp.format_compare(history)
    assert "1/2 (50%)" in text and "2/2 (100%)" in text and "1/1 (100%)" in text
    assert exp.format_compare({}) == "Проверок ещё не было."

"""Круг 12, BACK2 (U15): одно название — один смысл. Каталог названий наборов Евростата и точечных переопределений."""
import json
import re
from collections import defaultdict
from pathlib import Path

from app.data.eurostat_titles_ru import split_freq_suffix
from app.data.world_indicator_titles_ru import public_indicator_name, title_override_for_code

DATA = Path(__file__).resolve().parents[1] / "app" / "data"
INDEX_TITLE = "Гармонизированный индекс потребительских цен"


def _curated():
    return json.loads((DATA / "eurostat_titles_curated.json").read_text(encoding="utf-8"))


def _decisions():
    return json.loads((DATA / "eurostat_listing_decisions.json").read_text(encoding="utf-8"))


def _frequency_stem(dataset: str) -> str:
    """`sts_inpr_a` / `_m` / `_q` — один и тот же набор в разных периодах: допустимо делить название."""
    return re.sub(r"_(a|m|q)(?=$|_)", "_*", dataset)


def test_hicp_weights_and_first_publications_do_not_borrow_the_index_title():
    curated = _curated()
    for dataset in ("prc_hicp_cw", "prc_hicp_cow", "prc_hicp_iw", "prc_hicp_inw", "prc_hicp_fpd"):
        subject, _ = split_freq_suffix(curated[dataset])
        assert subject != INDEX_TITLE, dataset
    assert "Веса" in curated["prc_hicp_iw"] and "Веса" in curated["prc_hicp_cw"]
    assert "первые публикации" in curated["prc_hicp_fpd"]


def test_code_overrides_name_weights_and_first_publications_distinctly():
    names = {
        "fr-prc_hicp_cw-cowea": "Веса стран",
        "tr-prc_hicp_iw-total-iw": "Веса товаров",
        "tr-prc_hicp_inw-cp00": "Веса товаров",
        "fr-prc_hicp_fpd-total-fin-i15": "первые публикации",
    }
    for code, part in names.items():
        title = title_override_for_code(code)
        assert title and part in title, code
        assert part in public_indicator_name("Гармонизированный индекс потребительских цен, за год", code)
    # сам индекс остаётся под своим названием
    assert title_override_for_code("fr-prc_hicp_midx-cp00-i15") is None
    assert public_indicator_name(INDEX_TITLE + ", помесячно", "fr-prc_hicp_midx-cp00-i15") == INDEX_TITLE


# Сколько групп наборов с одинаковым названием существовало на 12.10.2026 (кроме пар «год/месяц/квартал»).
# Число можно только уменьшать: новый набор не должен занимать чужое название.
_BASELINE_SHARED_TITLE_GROUPS = 57


def test_shared_curated_titles_do_not_grow():
    decisions = _decisions()
    groups = defaultdict(set)
    for dataset, title in _curated().items():
        if (decisions.get(dataset) or {}).get("listable", True) is False:
            continue
        groups[split_freq_suffix(title)[0]].add(dataset)
    shared = [datasets for datasets in groups.values() if len({_frequency_stem(d) for d in datasets}) > 1]
    assert len(shared) <= _BASELINE_SHARED_TITLE_GROUPS, (
        f"{len(shared)} групп наборов с одинаковым названием (база {_BASELINE_SHARED_TITLE_GROUPS}): "
        + "; ".join(sorted(",".join(sorted(g)[:3]) for g in shared)[:5]))

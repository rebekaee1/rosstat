"""Тесты авто-expand срезов Eurostat."""

from app.data.eurostat_deep_expand import (
    expand_independent_slices,
    resolve_slice_specs,
)
from app.data.eurostat_listing import DEEP_DATASET_SLICES


def test_expand_independent_no_cartesian():
    headline = {"freq": "A", "age": "TOTAL", "sex": "T", "unit": "NR"}
    dims = {
        "freq": ["A"],
        "age": ["TOTAL", "Y15-24", "Y25-49", "Y_GE65"],
        "sex": ["T", "M", "F"],
        "unit": ["NR", "PC"],
        "geo": ["FR", "DE"],
        "time": ["2020"],
    }
    specs, skips = expand_independent_slices(headline, dims, dataset_id="demo_x")
    # headline + 3 age + 2 sex = 6; unit не расширяем
    assert len(specs) == 6
    assert not any(s.get("unit") == "PC" for s in specs)
    assert skips == []


def test_expand_skips_over_cap():
    headline = {"freq": "A", "nace_r2": "TOTAL", "unit": "I15"}
    members = ["TOTAL"] + [f"C{i:02d}" for i in range(1, 50)]
    dims = {"freq": ["A"], "nace_r2": members, "unit": ["I15"]}
    specs, skips = expand_independent_slices(headline, dims, dataset_id="sts_x")
    assert len(specs) == 1
    assert len(skips) == 1
    assert skips[0].reason == "over_cap"


def test_manual_deep_une_rt_wins():
    dims = {
        "freq": ["M"],
        "age": ["TOTAL", "Y_LT25", "Y25-74", "Y15-64"],
        "sex": ["T", "M"],
        "unit": ["PC_ACT", "THS_PER"],
        "s_adj": ["SA"],
    }
    plan = resolve_slice_specs("une_rt_m", dims)
    assert plan.source == "manual_deep"
    assert len(plan.specs) == len(DEEP_DATASET_SLICES["une_rt_m"])


def test_manual_deep_ilc_di04_wins():
    dims = {
        "freq": ["A"],
        "hhcomp": ["TOTAL", "A1", "A2"],
        "statinfo": ["MEAN_EI", "MED_EI"],
        "unit": ["EUR", "PPS"],
    }
    plan = resolve_slice_specs("ilc_di04", dims)
    assert plan.source == "manual_deep"
    assert all(s.get("statinfo") == "MEAN_EI" for s in plan.specs)
    assert all(s.get("unit") == "EUR" for s in plan.specs)


def test_label_age_pattern():
    from app.data.eurostat_dim_labels_ru import label_for_dim_member

    assert label_for_dim_member("age", "Y15-19") == "15–19 лет"
    assert label_for_dim_member("age", "Y_LT25") == "младше 25 лет"
    assert label_for_dim_member("nace_r2", "C") == "обрабатывающая промышленность"
    assert label_for_dim_member("nace_r2", "C99") is None
    assert label_for_dim_member("nace_r2", "K-N") == "финансы, недвижимость, проф- и адмуслуги"
    assert label_for_dim_member("indic_bt", "REG") == "регистрация"
    assert label_for_dim_member("indic_bt", "BKRT") == "банкротства"
    assert label_for_dim_member("indic_bt", "BPRM_DW") == "разрешения, число жилищ"
    assert label_for_dim_member("indic_bt", "BPRM_SQM") == "разрешения, кв. м полезной площади"
    assert label_for_dim_member("cpa2_1", "CPA_F410011") == "одноквартирные дома"
    assert label_for_dim_member("indic", "BS-CSMCI-BAL") == "уверенность потребителей"
    assert label_for_dim_member("indic", "BS-CCI-BAL") == "уверенность в строительстве"
    assert label_for_dim_member("indic", "CP-HI00XEF") == "ГИПЦ без энергии, продуктов, алкоголя и табака"
    assert label_for_dim_member("indic_de", "NATT") == "естественный оборот (рождения и смерти)"
    assert label_for_dim_member("siec", "G3000") == "природный газ"
    assert label_for_dim_member("siec", "O4000XBIO") == "нефть и нефтепродукты без биотоплива"
    assert label_for_dim_member("age", "D_LT7") == "младше 7 дней"
    assert label_for_dim_member("partner", "STLS") == "лица без гражданства"
    assert label_for_dim_member("marsta", "REP") == "в зарегистрированном партнёрстве"

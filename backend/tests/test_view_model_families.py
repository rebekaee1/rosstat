"""Инварианты canonical view-mode конфига (источник истины backend+frontend)."""

from __future__ import annotations

import pytest

from app.data import view_model_families as vmf
from app.services import derived_ops as ops


def test_families_have_base_and_default_mode():
    assert vmf.FAMILIES, "конфиг семейств пуст"
    for fam in vmf.FAMILIES:
        assert fam.base
        modes = {m.mode for m in fam.modes}
        assert fam.default_mode in modes, f"{fam.base}: default_mode не среди режимов"


def test_mode_tokens_unique_within_family():
    for fam in vmf.FAMILIES:
        tokens = [m.mode for m in fam.modes]
        assert len(tokens) == len(set(tokens)), f"{fam.base}: дубли токенов режимов"


def test_native_level_uses_source_code_no_pipeline():
    for fam in vmf.FAMILIES:
        for m in fam.modes:
            if m.is_native:
                assert m.code == fam.base, f"{fam.base}: нативный режим должен рендерить source"
                assert m.pipeline == ()
            else:
                assert m.code != fam.base, f"{fam.base}/{m.mode}: derived-код совпал с source"
                assert m.pipeline, f"{fam.base}/{m.mode}: непустой режим без pipeline"


def test_no_duplicate_lines_avg_skips_native_granularity():
    """Группа «Средняя за период» не должна иметь гранулярность нативной частоты
    (там среднее == уровню → дубль линии, решение созвона)."""
    for fam in vmf.FAMILIES:
        native = vmf.NATIVE_GRAN[
            next(m.frequency for m in fam.modes if m.is_native)
        ]
        for m in fam.modes:
            if m.group == "avg":
                assert not m.mode.endswith(native), (
                    f"{fam.base}: средняя на нативной гранулярности {native} — дубль"
                )


def test_percent_modes_have_percent_unit():
    """Относительные приросты (mom/qoq/yoy через ratio) — в процентах; абсолютные
    приросты (*_abs, для рядов со знаком/ставок) — в единицах источника или
    пунктах (п.п./‰/млн $)."""
    for fam in vmf.FAMILIES:
        for m in fam.modes:
            op_names = [op for op, _ in m.pipeline]
            is_abs = any(op.endswith("_abs") for op in op_names)
            if is_abs:
                assert m.unit != "%", (
                    f"{fam.base}/{m.mode}: абсолютный прирост не должен быть в процентах"
                )
            elif m.mode in ("mom", "qoq", "yoy"):
                assert m.unit == "%", f"{fam.base}/{m.mode}: ожидается unit '%'"


def test_pipeline_ops_exist_and_callable():
    for _dst, _src, pipeline in vmf.iter_derived_specs():
        for op_name, _kwargs in pipeline:
            fn = getattr(ops, op_name, None)
            assert callable(fn), f"op '{op_name}' не найден в derived_ops"


def test_derived_codes_globally_unique():
    codes = [dst for dst, _src, _pipe in vmf.iter_derived_specs()]
    assert len(codes) == len(set(codes)), "глобальные derived-коды не уникальны"


def test_gdp_reuses_legacy_codes():
    gdp = vmf.FAMILY_BY_BASE["gdp-nominal"]
    by_mode = {m.mode: m.code for m in gdp.modes}
    assert by_mode["yoy"] == "gdp-yoy"
    assert by_mode["qoq"] == "gdp-qoq"
    assert by_mode["sum-year"] == "gdp-nominal-annual"


def test_wages_nominal_yoy_year_override_supersedes_auto_sibling():
    wages = vmf.FAMILY_BY_BASE["wages-nominal"]
    by_mode = {m.mode: m.code for m in wages.modes}
    assert by_mode["yoy-year"] == "wages-nominal-annual-yoy"
    superseded = set(vmf.iter_superseded_default_sibling_codes())
    assert "wages-nominal-yoy-year" in superseded
    assert "wages-nominal-avg-year" in superseded
    assert "wages-nominal-annual-yoy" not in superseded


def test_superseded_default_siblings_not_in_active_iter():
    active = {m["code"] for m in vmf.iter_sibling_indicators()}
    for code in vmf.iter_superseded_default_sibling_codes():
        assert code not in active, f"{code} не должен генерироваться после override"


def test_superseded_siblings_hidden_in_seed():
    import seed_data

    superseded = set(vmf.iter_superseded_default_sibling_codes())
    assert superseded, "ожидаются superseded-коды от overrides"
    assert superseded <= seed_data.INDICATOR_HIDDEN_FROM_LISTING


def test_budget_deficit_flow_plus_abs_deltas():
    """Дефицит (поток со знаком): За период (сумма) + приросты в АБСОЛЮТЕ.

    Группа «Г/г» — многоуровневая (по месяцам/кварталам/годам): дефицит — поток,
    свод суб-периодов к кварталу/году = сумма, прирост к году назад в абсолюте.
    """
    fam = vmf.FAMILY_BY_BASE["budget-deficit"]
    assert {g.id for g in fam.groups} == {"flow", "pop", "yoy"}
    by_mode = {m.mode: m for m in fam.modes}
    assert set(by_mode) == {
        "level", "sum-quarter", "sum-year", "mom", "qoq",
        "yoy", "yoy-quarter", "yoy-year", "pop-gg",
    }
    # Г/г в «К прошлому периоду» — алиас на yoy-year (тот же ряд), группа pop.
    assert by_mode["pop-gg"].group == "pop"
    assert by_mode["pop-gg"].code == by_mode["yoy-year"].code
    # Приросты — абсолютные (млрд руб.), не проценты: база меняет знак.
    for tok in ("mom", "qoq", "yoy", "yoy-quarter", "yoy-year"):
        assert by_mode[tok].unit != "%", f"{tok}: должен быть абсолютным"
        op_names = [op for op, _ in by_mode[tok].pipeline]
        assert any(op.endswith("_abs") for op in op_names), f"{tok}: ожидается *_abs op"


def test_affordability_no_rolling_12m_mode():
    """Созвон 2026-06-16: режим «Скользящая 12 мес.» убран у доступности жилья."""
    for base in ("housing-affordability", "housing-affordability-primary"):
        fam = vmf.FAMILY_BY_BASE[base]
        tokens = {m.mode for m in fam.modes}
        assert "rolling-12m" not in tokens, f"{base}: rolling-12m должен быть убран"
        group_ids = {g.id for g in fam.groups}
        assert "rolling" not in group_ids, f"{base}: группа rolling должна быть убрана"


def test_weekly_yoy_aggregates_to_monthly_first():
    fam = vmf.FAMILY_BY_BASE["international-reserves"]
    yoy = next(m for m in fam.modes if m.mode == "yoy")
    assert yoy.pipeline[0][0] == "period_last"
    assert yoy.pipeline[0][1]["granularity"] == "month"
    assert yoy.pipeline[-1][0] == "yoy"
    assert yoy.frequency == "monthly"


def test_sibling_metadata_complete():
    for meta in vmf.iter_sibling_indicators():
        assert meta["code"] and meta["name"] and meta["unit"]
        assert meta["frequency"] in vmf.GRAN_FREQUENCY.values()
        assert meta["parent"] in vmf.FAMILY_BY_BASE


def test_sibling_name_en_suffix_covers_all_tokens():
    """Каждый sibling несёт EN-суффикс для name_en на английской витрине.

    Seed собирает `f"{parent.name_en} — {name_en_suffix}"`; пустой суффикс
    оставил бы русское имя на EN-странице режима (M-аудит EN-покрытия).
    """
    for meta in vmf.iter_sibling_indicators():
        suffix = meta.get("name_en_suffix")
        assert suffix, f"{meta['code']}: нет EN-суффикса имени"
        assert not any(
            ch in suffix for ch in "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
        ), f"{meta['code']}: кириллица в EN-суффиксе ({suffix!r})"


def test_seed_writes_name_en_for_siblings_with_curated_parent():
    """Sibling семьи с name_en у родителя получает составное EN-имя.

    Родители без name_en (легаси gdp-*/wages-*) покрыты оверлеем
    INDICATOR_COPY_EN и здесь не проверяются.
    """
    import seed_data

    parent = seed_data._PARENT_META["usd-rub"]
    assert (parent.get("name_en") or "").strip()
    sibling = next(
        i for i in seed_data.INDICATORS if i["code"] == "usd-rub-avg-quarter"
    )
    name_en = sibling.get("name_en") or ""
    assert name_en.startswith("USD/RUB Exchange Rate")
    assert "quarter average" in name_en
    assert "—" in name_en


def test_only_monthly_sources_get_partial_bucket_nowcasts():
    """Quarterly source already has a published fact for its quarter.

    `monthly_tail_extrapolate` is valid only when a monthly source needs
    predicted remaining months to complete the current bucket. Applying it to
    quarterly sources caused a forecast to replace the current fact in modes
    such as external-debt-qoq.
    """
    siblings = {meta["code"]: meta for meta in vmf.iter_sibling_indicators()}

    assert siblings["m2-qoq"]["forecast"]["monthly_tail_extrapolate"] is True
    assert "monthly_tail_extrapolate" not in siblings["external-debt-qoq"]["forecast"]
    assert siblings["external-debt-eop-year"]["forecast"]["complete_bucket"] == "year"
    assert siblings["external-debt-eop-year"]["forecast"]["min_periods"] == 4


def test_frontend_mirror_serializable():
    import json

    blob = vmf.to_frontend_families()
    assert json.dumps(blob)  # не падает на сериализации
    assert "m2" in blob
    assert blob["budget-deficit"]["template"] == "T7"


def test_resolve_view_mode_defaults_to_family_default():
    resolved = vmf.resolve_view_mode("budget-revenue", None)
    assert resolved is not None
    assert resolved.mode == vmf.FAMILY_BY_BASE["budget-revenue"].default_mode


def test_data_indicator_code_sum_quarter_sibling():
    assert vmf.data_indicator_code("budget-revenue", "sum-quarter") == "budget-revenue-sum-quarter"
    assert vmf.data_indicator_code("budget-revenue", "level") == "budget-revenue"


def test_mode_display_suffix_for_sum_quarter():
    fam = vmf.FAMILY_BY_BASE["budget-revenue"]
    mode = next(m for m in fam.modes if m.mode == "sum-quarter")
    suffix = vmf.mode_display_suffix(fam, mode)
    assert suffix is not None
    assert "квартал" in suffix.lower()


def test_weo_gdp_families_are_annual_only():
    """Оценки МВФ — годовой уровень + Г/г + индекс, без квартальной частоты."""
    for code in ("weo-gdp-usd", "weo-gdp-per-capita-usd"):
        fam = vmf.FAMILY_BY_BASE[code]
        assert fam.template == "T10"
        assert {m.frequency for m in fam.modes} == {"annual"}
        assert {m.mode for m in fam.modes} == {"level", "yoy", "index"}
        assert not any(m.forecastable for m in fam.modes)


def test_weo_budget_family_is_signed_annual():
    fam = vmf.FAMILY_BY_BASE["weo-budget-balance-gdp"]
    assert fam.template == "T10a"
    assert {m.frequency for m in fam.modes} == {"annual"}
    by_mode = {m.mode: m for m in fam.modes}
    assert set(by_mode) == {"level", "yoy"}
    assert by_mode["yoy"].unit == "п.п."
    assert not any(m.forecastable for m in fam.modes)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

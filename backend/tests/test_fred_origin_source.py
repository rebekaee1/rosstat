"""Ряды США через FRED подписаны первоисточником (рассылка 14.11.2026: безработица США была «ФРБ Сент-Луиса»)."""
from app.services.locale import reset_locale, set_locale
from app.services.seo_i18n import translate_source
from app.services.seo_world import _source_label
from app.services.world_national_ingest import load_national_core_yaml, public_source_for_spec


def _en(fn):
    token = set_locale("en")
    try:
        return fn()
    finally:
        reset_locale(token)


def test_every_fred_series_names_its_origin_agency():
    manifest = load_national_core_yaml("us")
    fred = [s for s in manifest.series if s.provider == "fred"]
    assert len(fred) == 62
    for s in fred:
        assert s.origin_ru and "Сент-Луиса" not in s.origin_ru, s.code_suffix
        assert public_source_for_spec(s) == f"{s.origin_ru} (через FRED)"
    unrate = next(s for s in fred if s.code_suffix == "unemployment-rate")
    assert public_source_for_spec(unrate) == "Бюро трудовой статистики США (через FRED)"


def test_fred_origin_names_translate_fully_to_english():
    manifest = load_national_core_yaml("us")
    for s in manifest.series:
        if s.provider != "fred":
            continue
        en = _en(lambda: translate_source(public_source_for_spec(s)))
        assert en.endswith("(via FRED)"), en
        assert not any("Ѐ" <= ch <= "ӿ" for ch in en), en


def test_ssr_source_label_keeps_origin_for_fred():
    raw = "Бюро трудовой статистики США (через FRED)"
    assert _source_label(raw, "fred") == raw
    assert _en(lambda: _source_label(raw, "fred")) == "U.S. Bureau of Labor Statistics (via FRED)"
    # Старые строки без первоисточника (до перезагрузки) — прежнее имя провайдера.
    assert _source_label("Федеральный резервный банк Сент-Луиса", "fred") == "Федеральный резервный банк Сент-Луиса"


def test_translate_source_replaces_every_known_part():
    assert _en(lambda: translate_source("Министерство финансов США (через FRED)")) == (
        "U.S. Department of the Treasury (via FRED)"
    )
    assert translate_source("Министерство финансов США (через FRED)") == "Министерство финансов США (через FRED)"

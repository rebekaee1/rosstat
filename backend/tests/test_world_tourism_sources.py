"""Раздел «Туризм» стран мира: разбор файлов издателей (фикстуры — выборки из файлов сбора 20.11.2026)."""

from datetime import date
from pathlib import Path

import pytest

from app.data.eurostat_titles_ru import listing_category_ru
from app.services import world_tourism_sources as src
from app.services.seo_i18n import localize_category_name
from app.services.world_tourism_ingest import MAX_SILENT_YEARS, _cli, plan_writes

FIXTURES = Path(__file__).parent / "fixtures" / "world_tourism"


def _text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8-sig")


def _bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_imf_quarters_in_million_dollars_and_annual_fallback():
    parsed, freqs = src.parse_imf_bop_csv(_text("imf_bop_sample.csv"))
    # Сверено с api.imf.org 20.11.2026: Турция, поездки, кредит, II кв. 2026 — 14 812 млн долл.
    assert parsed[("imf-travel-receipts", "TR")][-1] == (date(2026, 4, 1), pytest.approx(14812.0))
    assert freqs[("imf-travel-receipts", "TR")] == "quarterly"
    # Греция у МВФ — GRC, в каталоге — EL.
    assert ("imf-travel-receipts", "EL") in parsed
    # Германия публикует деловые поездки только за год.
    assert freqs[("imf-travel-business-receipts", "DE")] == "annual"
    assert parsed[("imf-travel-business-receipts", "DE")][-1][0] == date(2025, 1, 1)
    # Россия в мировой каталог не входит; страны вне каталога пропускаются.
    assert not any(country in ("RU", "AIA") for _, country in parsed)


def test_untourism_long_format_m49_and_regions_skipped():
    parsed = src.parse_untourism_workbooks([_bytes("untourism_sample.xlsx")])
    arrivals = dict(parsed[("unt-inbound-tourists", "TR")])
    assert arrivals[date(2022, 1, 1)] == pytest.approx(50453.0)
    assert ("tourism-gdp-share", "ES") in parsed
    # Занятые — в тысячах человек.
    employment = parsed[("unt-tourism-employment", "ES")][-1][1]
    assert 1000 < employment < 5000
    # Прибытия по регионам происхождения не берём; Россия (M49 643) вне каталога.
    assert not any(country == "RU" for _, country in parsed)


def test_untourism_links_from_pages():
    page = _text("pages_sample.html")
    assert src.untourism_zip_link(page).endswith("UN_Tourism_bulk_data_download_05_2026.zip")
    assert src.geostat_visits_link(page).endswith("0505EN0204_Visits-by-country-of-citizenship.xlsx")
    assert src.untourism_zip_link("<html></html>") is None


def test_oecd_key_and_russian_arrivals_pick_fresher_source():
    key = src.parse_oecd_key_csv(_text("oecd_df_key_ind_pc_sample.csv"))
    assert ("oecd-tourism-employment-share", "TR") in key
    assert ("tourism-gdp-share", "ES") in key
    ru = src.parse_oecd_inbound_russia_csv(_text("oecd_df_inbound_sample.csv"))
    # Турция даёт и опрос (TDS), и гостиницы с границей (TSS) — последние точки одинаковые, берётся TDS.
    assert dict(ru[("tour-arrivals-russia", "TR")])[date(2024, 1, 1)] == pytest.approx(6598759.0)
    assert ("tour-arrivals-russia", "EL") in ru
    assert not any(country == "EG" for _, country in ru)  # Египта в каталоге нет


def test_eurostat_travel_with_russia_credit_and_debit():
    parsed = src.parse_estat_travel_russia_csv(_text("estat_travel_ru_sample.csv"))
    assert dict(parsed[("estat-travel-russia-receipts", "CY")])[date(2025, 1, 1)] == pytest.approx(75.2)
    assert ("estat-travel-russia-payments", "CY") in parsed
    assert any(country == "UK" or country == "EL" for _, country in parsed)


def test_cystat_unreliable_and_missing_cells_are_gaps():
    parsed = src.parse_cystat_csv(_text("cystat_sample.csv"))
    russia = dict(parsed[("tour-arrivals-russia", "CY")])
    assert russia[date(2026, 10, 1)] == 5906.0
    assert russia[date(2026, 9, 1)] == 6737.0
    assert date(2026, 8, 1) not in russia  # «u» в августе 2026
    assert parsed[("tour-arrivals-total", "CY")][-1] == (date(2026, 10, 1), 508301.0)
    assert not any(country != "CY" for _, country in parsed)


def test_geostat_quarter_rows_inherit_year():
    parsed = src.parse_geostat_visits_xlsx(_bytes("geostat_0505EN0204_sample.xlsx"))
    russia = parsed[("tour-visits-russia", "GE")]
    assert russia[0] == (date(2014, 7, 1), pytest.approx(92.2117, rel=1e-4))
    assert russia[-1][0] == date(2026, 7, 1)
    assert ("tour-visits-total", "GE") in parsed


def _tidy(folder: str) -> src.Parsed:
    specs = [spec for spec in src.TIDY_SPECS if spec.folder == folder]
    return src.parse_tidy_csv(_text(f"tidy/{folder}/tidy.csv"), specs)


def test_turkey_monthly_russia_merges_spellings_and_top_origins():
    parsed = _tidy("turkey")
    russia = dict(parsed[("tour-arrivals-russia", "TR")])
    # «RUSYA FED.» (2014–2016), «Rusya» и «Rusya Fed.» — одна страна; сентябрь 2026 — 979 647 (бюллетень).
    assert russia[date(2014, 1, 1)] > 0 and russia[date(2015, 1, 1)] > 0
    assert russia[date(2026, 9, 1)] == 979647.0
    assert ("tour-arrivals-total", "TR") in parsed
    assert ("tour-arrivals-de", "TR") in parsed and ("tour-arrivals-uk", "TR") in parsed
    assert ("tour-arrivals-us", "TR") in parsed
    # «Beyaz Rusya» (Беларусь) — свой ряд и не попадает в российский.
    belarus = dict(parsed[("tour-arrivals-by", "TR")])
    assert belarus[date(2026, 9, 1)] != russia[date(2026, 9, 1)] and belarus[date(2026, 9, 1)] < 100000


def test_armenia_cumulative_totals_become_quarters():
    russia = dict(_tidy("armenia")[("tour-arrivals-russia", "AM")])
    # 2026: янв–мар 178 321, янв–июн 416 743, янв–сен 704 935.
    assert russia[date(2026, 1, 1)] == 178321.0
    assert russia[date(2026, 4, 1)] == 416743.0 - 178321.0
    assert russia[date(2026, 7, 1)] == 704935.0 - 416743.0
    assert russia[date(2023, 10, 1)] == 1137005.0 - 927813.0


def test_national_tables_of_destination_countries():
    assert dict(_tidy("israel")[("tour-arrivals-russia", "IL")])[date(2026, 10, 1)] == pytest.approx(7900.0)
    assert dict(_tidy("japan")[("tour-arrivals-russia", "JP")])[date(2026, 10, 1)] == 32600.0
    assert ("tour-arrivals-total", "JP") in _tidy("japan")
    assert _tidy("korea")[("tour-arrivals-russia", "KR")][-1][0] == date(2026, 8, 1)
    me = _tidy("montenegro")
    assert dict(me[("tour-accommodation-arrivals-russia", "ME")])[date(2026, 9, 1)] == 10881.0
    assert ("tour-accommodation-nights-russia", "ME") in me
    assert ("tour-accommodation-arrivals-russia", "RS") in _tidy("serbia")
    assert _tidy("azerbaijan")[("tour-arrivals-russia", "AZ")][-1] == (date(2025, 1, 1), 614904.0)
    assert ("tour-arrivals-russia", "IN") in _tidy("india")
    spain = _tidy("spain")
    assert spain[("tour-arrivals-russia", "ES")][-1][0] == date(2022, 2, 1)
    assert spain[("tour-arrivals-total", "ES")][-1][0] == date(2026, 9, 1)
    assert ("tour-hotel-accommodation-arrivals-russia", "ES") in spain


def test_eurostat_nights_by_residence_only_catalog_countries():
    parsed = _tidy("eurostat_by_residence")
    countries = {country for _, country in parsed}
    assert "TR" in countries and "EL" in countries
    assert not countries & {"EU27_2020", "LI"}
    assert ("estat-accommodation-nights-russia", "TR") in parsed


def _pts(*years: int) -> list[tuple[date, float]]:
    return [(date(year, 1, 1), float(year)) for year in years]


def test_plan_national_beats_oecd_and_oecd_gdp_share_beats_untourism():
    fetched = {
        src.OECD_PROVIDER: ({
            ("tour-arrivals-russia", "TR"): _pts(2023, 2024),
            ("tour-arrivals-russia", "EL"): _pts(2023, 2024),
            ("tourism-gdp-share", "ES"): _pts(2024, 2025),
        }, {}),
        src.UNT_PROVIDER: ({
            ("tourism-gdp-share", "ES"): _pts(2023, 2024),
            ("tourism-gdp-share", "GE"): _pts(2023, 2024),
        }, {}),
    }
    plan = plan_writes(fetched, set(), {"TR", "EL", "ES", "GE"}, today=date(2026, 11, 20))
    oecd = {(series.code_suffix, country) for series, country, _ in plan[src.OECD_PROVIDER]}
    unt = {(series.code_suffix, country) for series, country, _ in plan[src.UNT_PROVIDER]}
    assert ("tour-arrivals-russia", "TR") not in oecd  # у Турции — министерство туризма
    assert ("tour-arrivals-russia", "EL") in oecd
    assert ("tourism-gdp-share", "ES") not in unt and ("tourism-gdp-share", "GE") in unt


def test_plan_untourism_gdp_share_waits_when_oecd_failed_and_drops_silent_series():
    fetched = {src.UNT_PROVIDER: ({
        ("tourism-gdp-share", "GE"): _pts(2023, 2024),
        ("unt-hotels", "GE"): _pts(2005, 2026 - MAX_SILENT_YEARS - 1),
    }, {})}
    plan = plan_writes(fetched, {src.OECD_PROVIDER}, {"GE"}, today=date(2026, 11, 20))
    assert plan[src.UNT_PROVIDER] == []


def test_plan_applies_imf_frequency_per_country():
    fetched = {src.IMF_PROVIDER: ({("imf-travel-business-receipts", "DE"): _pts(2024, 2025)},
                                  {("imf-travel-business-receipts", "DE"): "annual"})}
    (series, country, _), = plan_writes(fetched, set(), {"DE"}, today=date(2026, 11, 20))[src.IMF_PROVIDER]
    assert series.frequency == "annual" and country == "DE"


def test_every_series_has_both_languages_and_tourism_category():
    for series in src.ALL_SERIES:
        assert series.category_ru == "Туризм"
        for text in (series.name_en, series.unit_en, series.description_en, series.methodology_en):
            assert text and not any("а" <= ch.lower() <= "я" for ch in text), series.code_suffix
        for text in (series.name_ru, series.unit_ru, series.description_ru, series.methodology_ru):
            assert text and any("а" <= ch.lower() <= "я" for ch in text), series.code_suffix
        # Публичные тексты без кодов наборов и жаргона.
        assert "SDMX" not in series.methodology_ru and "API" not in series.methodology_ru


def test_curated_english_copy_by_card():
    copy = src.curated_copy_en("imf_bop", "tr-imf-travel-receipts")
    assert copy["unit_en"] == "million US dollars" and "travel" in copy["methodology_en"].lower()
    assert src.curated_copy_en("cystat", "cy-tour-arrivals-russia")["unit_en"] == "people"
    assert src.curated_copy_en("eurostat", "tr-imf-travel-receipts") is None
    assert src.curated_copy_en("imf_bop", None) is None


def test_eurostat_tourism_sets_join_tourism_section():
    assert listing_category_ru("tour_occ_nim", "Общество", provider="eurostat") == "Туризм"
    assert localize_category_name("Туризм", locale="en") == "Tourism"


def test_cli_tidy_dir_loads_national_tables_only(monkeypatch):
    seen = {}

    async def fake_run(providers, *, raw_dir=None, tidy_dir=None):
        seen.update(providers=providers, raw_dir=raw_dir, tidy_dir=tidy_dir)
        return {}

    monkeypatch.setattr("app.services.world_tourism_ingest.run_world_tourism_ingest", fake_run)
    _cli([])
    assert not set(seen["providers"]) & set(src.TIDY_PROVIDERS)
    _cli(["--tidy-dir", "/tmp/c5"])
    assert set(seen["providers"]) == set(src.TIDY_PROVIDERS) and str(seen["tidy_dir"]) == "/tmp/c5"


def test_english_card_copy_and_unit_on_api_and_ssr():
    from types import SimpleNamespace

    from app.api.world import _indicator_public_unit, _tourism_or_safe_copy
    from app.services.locale import reset_locale, set_locale
    from app.services.seo_world import _unit_of

    ind = SimpleNamespace(
        provider="imf_bop", code="tr-imf-travel-receipts", unit="MIO_USD", unit_ru="млн долл. США",
        description="Сколько денег иностранцы тратят в стране.", methodology="Статья «Поездки».",
    )
    token = set_locale("en")
    try:
        assert _indicator_public_unit(ind) == "million US dollars"
        assert _unit_of(ind) == "million US dollars"
        assert _tourism_or_safe_copy(ind, "description").startswith("How much foreign travellers spend")
        assert "balance of payments" in _tourism_or_safe_copy(ind, "methodology")
    finally:
        reset_locale(token)
    token = set_locale("ru")
    try:
        assert _indicator_public_unit(ind) == "млн долл. США"
        assert _tourism_or_safe_copy(ind, "description") == ind.description
    finally:
        reset_locale(token)


def test_tourism_rating_concepts_match_written_cards():
    from types import SimpleNamespace

    from app.data.world_concepts import concept_for_indicator

    def card(series):
        return SimpleNamespace(provider=series.provider, dataset_id=series.dataset_id, unit=series.unit,
                               unit_ru=series.unit_ru, slice_json={"series": series.series_id})

    unt = {item.series_id: item for item in src.UNT_SERIES}
    assert concept_for_indicator(card(unt["INBD_TRIP_TOTL_TOTL_TOUR"])).slug == "tourist-arrivals"
    assert concept_for_indicator(card(unt["OUTB_TRIP_TOTL_TOTL_TOUR"])).slug == "outbound-trips"
    assert concept_for_indicator(card(unt["ST_GDP_ZS"])).slug == "tourism-gdp-share"
    assert concept_for_indicator(card(src.OECD_GDP_SHARE)).slug == "tourism-gdp-share"
    assert concept_for_indicator(card(src.OECD_EMP_SHARE)).slug == "tourism-employment-share"
    # Квартальные траты туристов (МВФ) в рейтинг не идут.
    assert concept_for_indicator(card(src.IMF_SERIES[0])) is None

"""BIS / Всемирный банк / МОТ: разбор живых ответов (фикстуры 19.11.2026), правило национального ряда, понятия, поиск."""

from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.data.world_concept_national import national_codes_for_concept
from app.data.world_concept_russia import RUSSIA_CONCEPT_LINKS
from app.data.world_concepts import CONCEPT_BY_SLUG, concept_for_indicator
from app.services import world_intl_ingest
from app.services.search_intent import match_score, parse_intent
from app.services.world_intl_sources import (
    SERIES,
    SERIES_BY_SUFFIX,
    bis_area,
    indicator_code,
    parse_bis_csv,
    parse_ilo_csv,
    parse_wb_json,
)

FIXTURES = Path(__file__).parent / "fixtures" / "world_intl"


def _text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_bis_csv_months_and_nan():
    parsed = parse_bis_csv(_text("bis_cbpol_sample.csv"))
    # Сверено с data.bis.org 19.11.2026: Индия 5,25 % (сентябрь), Китай LPR 3 % (октябрь), Банк Англии 3,75 %.
    assert parsed["IN"][-1] == (date(2026, 9, 1), 5.25)
    assert parsed["CN"][-1] == (date(2026, 10, 1), 3.0)
    assert parsed["GB"][-1] == (date(2026, 10, 1), 3.75)
    assert "HR" not in parsed  # NaN после перехода Хорватии на евро не пишется


def test_bis_area_uses_bis_codes_for_eurostat_exceptions():
    assert bis_area("UK") == "GB" and bis_area("EL") == "GR" and bis_area("tr") == "TR"


def test_wb_json_years():
    parsed = parse_wb_json(_text("wb_gini_sample.json"))
    assert parsed["RUS"][-1] == (date(2023, 1, 1), 33.0)
    assert parsed["USA"][-1] == (date(2024, 1, 1), 41.8)


def test_wb_json_error_message_is_raised():
    with pytest.raises(ValueError):
        parse_wb_json('[{"message": [{"id": "120", "value": "Invalid value"}]}]')


def test_ilo_drops_model_projection_years():
    parsed = parse_ilo_csv(_text("ilo_youth_sample.csv"), classif="AGE_YTHADULT_Y15-24", last_closed_year=2025)
    years = [when.year for when, _ in parsed["RUS"]]
    assert max(years) == 2025 and 2026 not in years
    assert dict(parsed["RUS"])[date(2024, 1, 1)] == pytest.approx(8.256)


def test_fetch_provider_maps_publisher_codes_to_catalog(monkeypatch):
    texts = {"stats.bis.org": _text("bis_cbpol_sample.csv")}
    monkeypatch.setattr(world_intl_ingest, "_get_text", lambda url: next(v for k, v in texts.items() if k in url))
    out = world_intl_ingest.fetch_provider("bis", ["IN", "CN", "UK", "DE"], today=date(2026, 11, 19))
    assert set(out) == {("bis-policy-rate", "IN"), ("bis-policy-rate", "CN"), ("bis-policy-rate", "UK")}


def test_discontinued_monthly_series_are_skipped():
    bis = SERIES_BY_SUFFIX["bis-policy-rate"]
    today = date(2026, 11, 19)
    assert world_intl_ingest.is_live(bis, [(date(1998, 12, 1), 3.0)], today) is False  # Германия до евро
    assert world_intl_ingest.is_live(bis, [(date(2026, 10, 1), 36.0)], today) is True
    # Обследования Джини выходят раз в несколько лет — старый год не отсекается.
    assert world_intl_ingest.is_live(SERIES_BY_SUFFIX["wb-gini"], [(date(2005, 1, 1), 26.6)], today) is True


def test_international_series_hidden_only_when_national_series_is_alive():
    bis = SERIES_BY_SUFFIX["bis-policy-rate"]
    live = {"us-policy-rate", "cn-lpr-1y"}
    assert world_intl_ingest.listed_for(bis, "US", live) is False
    assert world_intl_ingest.listed_for(bis, "CN", live) is False
    # Ставка репо РБИ не обновляется (1 точка 1970 г.) — ряд BIS публичен.
    assert world_intl_ingest.listed_for(bis, "IN", live) is True
    assert world_intl_ingest.listed_for(bis, "TR", live) is True
    assert world_intl_ingest.listed_for(SERIES_BY_SUFFIX["wb-gini"], "US", live) is True


@pytest.mark.parametrize("series", SERIES, ids=lambda s: s.code_suffix)
def test_every_series_matches_exactly_its_concept(series):
    indicator = SimpleNamespace(
        provider=series.provider, dataset_id=series.dataset_id, unit=series.unit,
        unit_ru=series.unit_ru, slice_json={"series": series.series_id}, code=indicator_code("TR", series),
    )
    concept = concept_for_indicator(indicator)
    assert concept is not None and concept.slug == series.concept_slug
    assert "rating" in concept.enabled_surfaces
    assert "индекс" not in series.unit_ru.lower()  # иначе рейтинг считает «изменение за год»


def test_policy_rate_national_first_and_russia_key_rate():
    assert {"us-policy-rate", "cn-lpr-1y", "in-policy-rate"} <= national_codes_for_concept("policy-rate")
    assert RUSSIA_CONCEPT_LINKS["policy-rate"].indicator_code == "key-rate"
    assert RUSSIA_CONCEPT_LINKS["youth-unemployment-rate"].indicator_code == "unemployment-youth"
    assert "gini-index" not in RUSSIA_CONCEPT_LINKS  # коэффициент Росстата не сопоставим с индексом Всемирного банка


GEOMETRY = [
    dict(key="country:china", kind="country", slug="china", name_ru="Китай", name_en="China", country_slug="china", country_code="CN"),
    dict(key="country:india", kind="country", slug="india", name_ru="Индия", name_en="India", country_slug="india", country_code="IN"),
]


@pytest.mark.parametrize("query, code, names", [
    ("ключевая ставка Китай", "cn-lpr-1y", ("Базовая кредитная ставка LPR на 1 год",)),
    ("ключевая ставка Индия", "in-bis-policy-rate", ("Ключевая ставка центрального банка",)),
    ("ставка цб индии", "in-bis-policy-rate", ("Ключевая ставка центрального банка",)),
])
def test_key_rate_of_china_and_india_is_found(query, code, names):
    intent = parse_intent(query, GEOMETRY)
    assert intent.countries and len(intent.terms) == 1
    assert match_score(intent, code=code, names=names, metadata="") is not None


def test_china_key_rate_is_the_one_year_lpr_only():
    intent = parse_intent("ключевая ставка Китай", GEOMETRY)
    assert match_score(intent, code="cn-lpr-5y", names=("Базовая кредитная ставка LPR на 5 лет и более",), metadata="") is None


def test_youth_unemployment_and_inequality_queries():
    youth = parse_intent("безработица молодежи", [])
    assert match_score(youth, code="unemployment-youth", names=("Безработица (15–24 лет)",), metadata="") is not None
    assert match_score(youth, code="tr-ilo-youth-unemployment", names=("Безработица молодёжи 15–24 лет",), metadata="") is not None
    # «Безработица молодёжи» ведёт ко всей безработице (R8-A: у регионов ряда 15–24 лет нет, студенту из Самары
    # нужна безработица области); ряды 15–24 лет Росстата и МОТ находятся тем же словом.
    top = parse_intent("доля доходов 10% самых богатых", [])
    # Знак % в запросе требует процентную единицу ряда — поиск добавляет её в metadata (`search._unit_metadata`).
    assert match_score(top, code="us-wb-income-top10", names=("Доля доходов 10% самых обеспеченных",),
                       metadata="search-unit-percent") is not None
    assert match_score(parse_intent("джини", []), code="us-wb-gini", names=("Индекс Джини",), metadata="") is not None


def test_rating_concepts_have_public_names():
    from app.data.world_simple_names import SIMPLE_NAMES
    from app.services.world_rank_values import WORLD_RATING_QUERY_NAMES, WORLD_RATING_QUERY_NAMES_EN

    for series in SERIES:
        slug = series.concept_slug
        assert CONCEPT_BY_SLUG[slug].name_en
        assert slug in SIMPLE_NAMES and slug in WORLD_RATING_QUERY_NAMES and slug in WORLD_RATING_QUERY_NAMES_EN

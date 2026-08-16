"""Полярность региональных рейтингов: curated lower_better + нейтральная подача."""

from app.data.region_indicator_polarity import (
    LOWER_BETTER_CODES,
    region_indicator_polarity,
    region_rating_default_sort,
    region_rating_is_achievement,
    region_rating_meta,
)
from app.services.seo_regional import _rank_phrase, _rating_copy


class TestRegionPolarityCatalog:
    def test_unemployment_and_poverty_are_lower_better(self):
        assert region_indicator_polarity("uroven-bezrabotitsy") == "lower_better"
        assert region_rating_default_sort("uroven-bezrabotitsy") == "asc"
        assert region_rating_is_achievement("uroven-bezrabotitsy") is True
        assert region_indicator_polarity(
            "chislennost-naseleniya-s-denezhnymi-dohodami-nizhe-granitsy"
        ) == "lower_better"

    def test_table_code_fallback(self):
        assert region_indicator_polarity("unknown-code", "2.10.1") == "lower_better"
        assert region_rating_default_sort(None, "3.12") == "asc"

    def test_unknown_is_neutral_desc(self):
        assert region_indicator_polarity("chislennost-naseleniya") is None
        assert region_rating_default_sort("chislennost-naseleniya") == "desc"
        assert region_rating_is_achievement("chislennost-naseleniya") is False
        meta = region_rating_meta("valovoy-regionalnyy-produkt")
        assert meta == {
            "polarity": None,
            "default_sort": "desc",
            "rank_as_achievement": False,
        }

    def test_mandatory_topics_covered(self):
        must = {
            "uroven-bezrabotitsy",
            "chislennost-naseleniya-s-denezhnymi-dohodami-nizhe-granitsy",
            "obschie-koeffitsienty-smertnosti",
            "koeffitsienty-mladencheskoy-smertnosti",
            "zabolevaemost-na-1000-chelovek-naseleniya",
            "chislo-zaregistrirovannyh-prestupleniy-na-100000",
            "stepen-iznosa-osnovnyh-fondov",
            "vybrosy-zagryaznyayuschih-veschestv-v-atmosfernyy-vozduh-othodyaschih",
            "sbros-zagryaznennyh-stochnyh-vod-v-poverhnostnye-vodnye",
            "prosrochennaya-zadolzhennost-po-zarabotnoy-plate-rabotnikam-organizatsiy",
            "chislo-dorozhno-transportnyh-proisshestviy-na-100000-chelovek",
        }
        assert must <= LOWER_BETTER_CODES


class TestRegionRatingCopy:
    def test_achievement_allows_first_place_language(self):
        copy = _rating_copy(achievement=True)
        assert "Первые места" in copy["intro_lead"]
        assert copy["table_col"] == "Место"
        phrase = _rank_phrase(1, 85, achievement=True)
        assert "лучших" in phrase
        assert "лидер" not in phrase.lower()

    def test_neutral_forbids_achievement_language(self):
        copy = _rating_copy(achievement=False)
        assert "Первые места" not in copy["intro_lead"]
        assert "лидер" not in copy["intro_lead"].lower()
        assert "Наибольшие значения" in copy["intro_lead"]
        assert copy["table_col"] == "№"
        phrase = _rank_phrase(1, 85, achievement=False)
        assert "наибольш" in phrase
        mid = _rank_phrase(40, 85, achievement=False)
        assert "положен" in mid
        assert "место" not in mid

    def test_rank_order_matches_table_positions(self):
        rows = [
            ("respublika-ingushetiya", 26.4),
            ("moskva", 1.0),
            ("sankt-peterburg", 1.5),
        ]
        une = sorted(
            rows,
            key=lambda x: x[1],
            reverse=(region_rating_default_sort("uroven-bezrabotitsy") == "desc"),
        )
        assert une[0][0] == "moskva"
        assert next(i for i, (s, _) in enumerate(une, 1) if s == "moskva") == 1

        pop = sorted(
            [("a", 100.0), ("b", 500.0), ("c", 50.0)],
            key=lambda x: x[1],
            reverse=(region_rating_default_sort("chislennost-naseleniya") == "desc"),
        )
        assert pop[0][0] == "b"
        assert next(i for i, (s, _) in enumerate(pop, 1) if s == "b") == 1

from app.services.calendar_i18n import INDICATOR_CALENDAR_CONTEXT_EN, english_event_description
from app.services.calendar_sources.official_calendar import INDICATOR_CALENDAR_CONTEXT


def test_every_russian_context_has_an_english_twin():
    assert set(INDICATOR_CALENDAR_CONTEXT) == set(INDICATOR_CALENDAR_CONTEXT_EN)


def test_description_with_schedule_note_gets_the_context_twin():
    ru = INDICATOR_CALENDAR_CONTEXT["cpi"] + " Плановая дата публикации Росстата: каждый месяц."
    assert english_event_description(ru) == INDICATOR_CALENDAR_CONTEXT_EN["cpi"]


def test_legacy_wording_is_still_recognised():
    legacy = "Индикативная взвешенная ставка однодневных рублёвых межбанковских кредитов крупнейших банков."
    assert english_event_description(legacy) == INDICATOR_CALENDAR_CONTEXT_EN["ruonia"]


def test_unknown_russian_text_is_not_shown_in_english():
    assert english_event_description("Что-то совсем другое") is None
    assert english_event_description(None) is None


def test_indicator_code_is_the_fallback():
    assert english_event_description("Что-то другое", "key-rate") == INDICATOR_CALENDAR_CONTEXT_EN["key-rate"]

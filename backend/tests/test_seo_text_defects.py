"""Мелкие дефекты шаблонов description, найденные выборкой sitemap 12.10.2026."""
from app.services import seo_calendar
from app.services.seo_year_ui import plural_ru


def test_calendar_month_prepositional_forms():
    assert len(seo_calendar._MONTHS_PREP) == 12
    assert seo_calendar._MONTHS_PREP[1] == "феврале" and seo_calendar._MONTHS_PREP[4] == "мае"


def test_calendar_publication_plural():
    assert plural_ru(34, "публикация", "публикации", "публикаций") == "публикации"
    assert plural_ru(11, "публикация", "публикации", "публикаций") == "публикаций"
    assert plural_ru(21, "публикация", "публикации", "публикаций") == "публикация"

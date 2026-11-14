"""Блоки выпуска рассылки (14.11.2026): разбор, запрет диапазона в прогнозе, календарь без
прошедших дат, мини-график без картинок, абзацы, подпись, прехедер, число на телефоне."""
from datetime import date

import pytest

from app.services.mail import blocks
from app.services.mail.campaign import CampaignError, parse_issue
from app.services.mail.templates import Digest, preheader_of, render_digest

LEAD = {"type": "lead", "kicker": "Число недели", "title": "Бензин АИ-92, литр", "value": "70,01 ₽",
        "delta": "−4,71 ₽ за 5 недель", "delta_dir": "down", "source": "Росстат",
        "url": "https://ru.forecasteconomy.com/russia/indicator/fuel-ai92",
        "bars": {"unit": "₽ за литр", "points": [["7 сен", 74.25], ["14 сен", 74.6], ["9 ноя", 70.01]]}}


def _issue(**ru):
    base = {"subject": "Тема", "title": "Заголовок", "blocks": [LEAD]}
    base.update(ru)
    return {"key": "fe-weekly-test", "ru": base}


@pytest.mark.parametrize("bad", [
    {"value": "140–150 тыс. ₽"}, {"value": "от 140 до 150 тыс. ₽"}, {"lower": 1}, {"upper": 2}, {"range": "x"},
])
def test_forecast_single_number_only(bad):
    b = {"type": "forecast", "title": "Зарплата в декабре", "value": "147 187 ₽", **bad}
    with pytest.raises(CampaignError, match="только одно число"):
        parse_issue(_issue(blocks=[b]))
    blocks.validate_block({"type": "forecast", "title": "x", "value": "147 187 ₽"})  # одно число — можно


def test_unknown_block_type_rejected():
    with pytest.raises(CampaignError, match="неизвестный тип"):
        parse_issue(_issue(blocks=[{"type": "chart", "title": "x"}]))


def test_calendar_hides_past_dates():
    cal = {"type": "calendar", "title": "Что выйдет дальше", "entries": [
        {"date": "18 ноября", "title": "цены производителей", "date_iso": "2026-11-18"},
        {"date": "18 декабря", "time": "13:30 мск", "title": "ключевая ставка", "date_iso": "2026-12-18"},
        {"date": "Каждую среду", "title": "недельные цены"}]}
    html = blocks.render(cal, "ru", today=date(2026, 11, 20))
    assert "цены производителей" not in html and "ключевая ставка" in html and "недельные цены" in html
    assert "18 ноября" not in blocks.as_text(cal, "ru", date(2026, 11, 20))


def test_lead_bars_are_table_cells_last_bar_blue():
    html = blocks.render(LEAD, "ru")
    assert "<img" not in html and "#2C4A8A" in html and "70,01" in html
    assert "border:" not in html.replace("border-radius", "")
    text = blocks.as_text(LEAD, "ru")
    assert "График: 74,25 → 74,6 → 70,01 ₽ за литр (7 сен — 9 ноя)" in text


def test_issue_render_paragraphs_signoff_masthead_and_utm():
    data = _issue(intro="Первый абзац.\n\nВторой абзац.", outro="Ответьте нам. Редакция Forecast Economy.",
                  signoff="Редакция Forecast Economy", masthead="Неделя в цифрах · № 1")
    issue = parse_issue(data)
    d = issue.by_locale["ru"]
    assert d.outro == "Ответьте нам." and d.signoff == "Редакция Forecast Economy"
    assert "utm_campaign=fe-weekly-test" in d.blocks[0]["url"]
    r = render_digest(d, "ru", site_url="https://x/", unsubscribe_url="https://x/u", today=date(2026, 11, 14))
    assert r.html.count("Редакция Forecast Economy") == 1
    assert "Первый абзац.</p>" in r.html and "Второй абзац.</p>" in r.html
    assert "Неделя в цифрах" in r.html and "ЧИСЛО НЕДЕЛИ" in r.html


def test_story_value_moves_under_title_on_phone_without_double_show():
    story = {"type": "story", "kicker": "Топливо", "title": "Дизель", "value": "86,63 ₽", "text": "Цена литра."}
    html = blocks.render(story, "ru")
    # Копия числа под заголовком спрятана встроенным стилем: без медиазапросов видно одно число.
    assert 'class="fe-val-m" style="display:none' in html and 'class="fe-val"' in html


def test_preheader_cut_on_word_boundary():
    d = Digest(subject="s", title="t", intro="слово " * 40)
    p = preheader_of(d)
    assert p.endswith("…") and len(p) <= 112 and not p[:-1].endswith(" ")


def test_editor_issue_files_parse(tmp_path):
    """Файлы редактора (если лежат рядом) разбираются без ошибок."""
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / ".artifacts" / "newsletter-editorial-2026-11-14"
    files = sorted(root.glob("issue-*.json")) if root.exists() else []
    if not files:
        pytest.skip("материалы редактора вне репозитория")
    for f in files:
        parse_issue(json.loads(f.read_text(encoding="utf-8")))


def test_why_and_section_blocks():
    story = {"type": "story", "title": "Ипотека", "source": "Банк России", "why": "Вы смотрели ипотечный калькулятор"}
    html = blocks.render(story, "ru")
    assert html.index("Источник: Банк России") < html.index("Вы смотрели ипотечный калькулятор")
    assert blocks.as_text(story, "ru").endswith("Вы смотрели ипотечный калькулятор")
    sec = {"type": "section", "title": "Для вас", "text": "По вашим слежениям"}
    blocks.validate_block(sec)
    html = blocks.render(sec, "ru")
    assert "Для вас" in html and "background:#F3F5F9" not in html
    assert blocks.as_text(sec, "ru").startswith("ДЛЯ ВАС")


def test_with_utm_keeps_existing_tags():
    from app.services.mail.campaign import with_utm

    url = with_utm("https://ru.forecasteconomy.com/x?utm_campaign=own&utm_content=hero", "fe-weekly-01", "b1-lead")
    assert "utm_campaign=own" in url and "utm_content=hero" in url and "utm_source=email" in url
    assert with_utm("https://example.com/x", "k", "b1") == "https://example.com/x"


def test_personal_note_footer_has_unpersonalize_link():
    d = Digest(subject="s", title="t", personal_note="Подборка составлена по вашим действиям на сайте.")
    r = render_digest(d, "ru", site_url="https://x/", unsubscribe_url="https://x/u", unpersonalize_url="https://x/p")
    assert "Подборка составлена" in r.html and "Письма без персональной подборки" in r.html and "https://x/p" in r.text

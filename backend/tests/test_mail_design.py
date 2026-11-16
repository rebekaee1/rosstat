"""Страж правил письма (docs/newsletter-playbook.md): палитра, шрифты, главы, тон «для вас», без рамок.

Правила письма — не пожелание: новое письмо, блок или цвет либо проходит этот тест, либо правило
сначала меняется в документе (и здесь), с датой и причиной.
"""
import re
from datetime import date

from app.services.mail import blocks as blk
from app.services.mail import templates as T

ISSUE = [
    {"type": "lead", "kicker": "Число недели", "title": "Бензин АИ-92, литр", "value": "70,01 ₽",
     "delta": "−4,71 ₽ за 5 недель", "delta_dir": "down", "text": "Средняя цена по России.", "source": "Росстат",
     "bars": {"unit": "₽", "points": [["7 сен", 74.2], ["14 сен", 74.6], ["9 ноя", 70.0]]}},
    {"type": "section", "title": "Для вас", "text": "Подборка по тому, что вы смотрели."},
    {"type": "story", "kicker": "Вы скачивали", "title": "Рабочая сила", "value": "76,7 млн чел.",
     "delta": "Без изменений за месяц", "delta_dir": "flat", "text": "За сентябрь 2026.", "source": "Росстат",
     "why": "Вы скачивали этот ряд.", "url": "https://ru.forecasteconomy.com/russia/indicator/labor-force"},
    {"type": "forecast", "kicker": "Прогноз", "title": "Россия: безработица, сентябрь 2027", "value": "1,77 %",
     "last_actual": "2,2 % за сентябрь 2026", "text": "Модельный прогноз.", "source": "Росстат",
     "why": "Вы смотрели этот прогноз."},
    {"type": "table", "kicker": "Ваши показатели", "title": "Ваши показатели за неделю",
     "columns": ["Показатель", "Значение", "Изменение"], "rows": [["Доходы бюджета", "3 687,1", "−130,3"],
                                                                 ["Расходы бюджета", "3 072,8", "−143,0"]],
     "source": "Минфин", "why": "Вы смотрели этот показатель."},
    {"type": "story", "kicker": "Мир", "title": "Нефть Brent", "value": "92,14 $", "text": "Цена барреля.",
     "source": "EIA"},
    {"type": "calendar", "kicker": "Календарь", "title": "Что выйдет дальше",
     "entries": [{"date": "18 декабря", "title": "решение Банка России", "date_iso": "2026-12-18"}]},
]


def _html() -> str:
    d = T.Digest(subject="Тема", title="Заголовок", intro="Вступление.", masthead="Неделя в цифрах · № 1",
                 blocks=ISSUE, cta_label="Открыть", cta_url="https://ru.forecasteconomy.com/", outro="Ответьте.",
                 signoff="Редакция", personal_note="Подборка составлена по вашим действиям.")
    return T.render_digest(d, "ru", site_url="https://ru.forecasteconomy.com/", unsubscribe_url="https://x/u",
                           manage_url="https://x/a", today=date(2026, 11, 16), unpersonalize_url="https://x/p").html


PALETTE = {getattr(T, n).upper() for n in (
    "INK", "TEXT", "MUTED", "BLUE", "BLUE_DEEP", "ON_DARK", "ON_DARK_MUTED", "SAPPHIRE", "GOLD", "GOLD_BRIGHT",
    "BG", "SURFACE", "LAYER", "LAYER_PERSONAL", "HAIRLINE", "DELTA", "ARROW")}
# Производные тонов палитры: верх кнопки, столбики графика, служебная строка реквизитов.
DERIVED = {"#3558A0", "#C9D3E2", "#8A93A5", "#FFFFFF"}


def test_palette_only_tokens_no_red_green():
    colors = {c.upper() for c in re.findall(r"#[0-9A-Fa-f]{6}\b", _html())}
    assert colors <= PALETTE | DERIVED, colors - PALETTE - DERIVED


def test_typography_scale_and_weights():
    html = _html()
    weights = {int(w) for w in re.findall(r"font-weight:(\d+)", html)}
    assert weights <= {300, 400, 600, 700}, weights          # Яндекс Почта рисует 650 обычным начертанием
    sizes = {float(s) for s in re.findall(r"font-size:([\d.]+)px", html)}
    # 24 и 38 — заголовок и число недели на телефоне (медиазапрос).
    assert sizes <= {1, 2, 11, 12, 12.5, 13, 13.5, 14, 15.5, 16, 17, 19, 22, 24, 25, 27, 38, 46}, sizes


def test_no_borders_and_gold_is_a_thin_accent():
    html = _html()
    assert not re.findall(r"border(?:-(?:top|bottom|left|right))?:\s*[1-9]", html)   # отделение — светом, не рамкой
    gold = html.upper().count(T.GOLD.upper()) + html.upper().count(T.GOLD_BRIGHT.upper())
    assert gold <= 8, gold        # линия под шапкой, черта «Числа недели», точка прогноза — и всё


def test_chapters_tell_the_story_in_order():
    html = blk.render_all(ISSUE, "ru", date(2026, 11, 16))
    order = [html.index(x) for x in (">01<", "Число недели", ">02<", "Для вас", ">03<", "Ещё на этой неделе",
                                     ">04<", "Что выйдет дальше")]
    assert order == sorted(order)
    text = "\n".join(blk.text_all(ISSUE, "ru", date(2026, 11, 16)))
    assert "02 · ДЛЯ ВАС" in text and "03 · ЕЩЁ НА ЭТОЙ НЕДЕЛЕ" in text
    # Прошедший календарь не оставляет пустую главу.
    past = blk.render_all(ISSUE, "ru", date(2027, 1, 1))
    assert ">04<" not in past and "Что выйдет дальше" not in past


def test_personal_blocks_are_tinted_and_editorial_are_not():
    personal = blk.render(ISSUE[2], "ru")
    editorial = blk.render(ISSUE[5], "ru")
    assert T.LAYER_PERSONAL in personal and T.LAYER_PERSONAL not in editorial and T.LAYER in editorial
    assert "Источник: Росстат" in personal and "Вы скачивали этот ряд" in personal   # одна служебная строка
    assert "Без изменений за месяц" in personal                                      # изменение — своей строкой


def test_old_issue_without_lead_and_section_has_no_chapters():
    html = blk.render_all([ISSUE[5]], "ru", date(2026, 11, 16))
    assert ">01<" not in html and "Ещё на этой неделе" not in html

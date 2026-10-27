"""Дайджест «Пульс» уходит в Telegram с parse_mode=HTML: текст LLM не должен ломать разбор.

Регрессия 2026-10-17: в тексте модели было «норма < 2500 мс», Bot API ответил HTTP 400
«can't parse entities» и два адресата не получили дайджест.
"""
from app.services.pulse_report import sanitize_llm_html


def test_bare_less_than_is_escaped():
    assert sanitize_llm_html("норма < 2500 мс") == "норма &lt; 2500 мс"


def test_greater_than_and_ampersand_are_escaped():
    assert sanitize_llm_html("рост > 5% & спад") == "рост &gt; 5% &amp; спад"


def test_existing_entities_are_kept_not_double_escaped():
    assert sanitize_llm_html("A &amp; B &lt;C&gt; &#8212;") == "A &amp; B &lt;C&gt; &#8212;"


def test_allowed_telegram_tags_pass_through():
    src = "<b>Итог</b>: <i>слабый</i> <code>ttfb</code> <blockquote>цитата</blockquote>"
    assert sanitize_llm_html(src) == src


def test_link_and_spoiler_tags_pass_through():
    src = '<a href="https://forecasteconomy.com/x">ссылка</a> <tg-spoiler>тайна</tg-spoiler>'
    assert sanitize_llm_html(src) == src


def test_unknown_tag_is_escaped_as_text():
    assert sanitize_llm_html("<script>x</script>") == "&lt;script&gt;x&lt;/script&gt;"


def test_mixed_model_text_matches_telegram_rules():
    src = "<b>Пульс</b>: TTFB 7116 мс, это очень медленно (норма < 2500 мс) & 3 ошибки"
    out = sanitize_llm_html(src)
    assert out == (
        "<b>Пульс</b>: TTFB 7116 мс, это очень медленно (норма &lt; 2500 мс) &amp; 3 ошибки"
    )
    # после санитизации в тексте не остаётся ни одного «голого» <, который Telegram не примет
    stripped = out.replace("<b>", "").replace("</b>", "")
    assert "<" not in stripped

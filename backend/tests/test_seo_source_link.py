"""Источник в SSR указывает на публикацию, если её URL известен."""

from app.services.seo_renderer import _published_source_link


def test_published_source_url_is_linked():
    assert _published_source_link("https://rosstat.gov.ru/folder/13877", "Росстат") == (
        '<a href="https://rosstat.gov.ru/folder/13877">Росстат</a>'
    )


def test_unknown_source_is_text_without_misleading_internal_link():
    assert _published_source_link(None, "Росстат") == "Росстат"
    assert _published_source_link("/russia", "Росстат") == "Росстат"

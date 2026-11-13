"""Серверная страница «О проекте» несёт тексты карточек приложения (13.11.2026).

До правки серверный HTML содержал только вводный абзац (45 слов): откуда данные, как
считаются прогнозы, чего проект не делает и как с ним связаться — было видно только
после загрузки приложения. Тексты блоков взяты из карточек (`x4.about.*`).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _messages(locale: str) -> dict[str, str]:
    text = (ROOT / f"frontend/src/i18n/messages.{locale}.js").read_text(encoding="utf-8")
    out = {}
    for key, value in re.findall(r"'(x4\.about\.[a-z.]+)':\s*'((?:[^'\\]|\\.)*)'", text):
        out[key] = value.replace("\\'", "'")
    return out


def _page(locale: str):
    if locale == "en":
        from app.data.i18n.seo_en import PAGE_META_EN

        return PAGE_META_EN["about"]
    from app.services.seo_content import PAGE_META

    return PAGE_META["about"]


CARDS = ("sources", "inside", "forecast", "audience", "free", "limits", "contact")


@pytest.mark.parametrize("locale", ["ru", "en"])
def test_blocks_repeat_the_app_cards(locale):
    messages = _messages(locale)
    blocks = _page(locale).blocks
    assert [block.title for block in blocks] == [messages[f"x4.about.{card}.title"] for card in CARDS]
    for block, card in zip(blocks, CARDS, strict=True):
        body = messages[f"x4.about.{card}.body"]
        # Карточка источников в приложении заканчивается списком ссылок, контактная — почтой.
        assert block.body.startswith(body), (locale, card)


@pytest.mark.parametrize("locale", ["ru", "en"])
def test_trust_facts_are_in_server_text(locale):
    page = _page(locale)
    text = " ".join(block.body for block in page.blocks)
    assert "info@forecasteconomy.com" in text
    assert ("/methodology" in {path for path, _ in page.links})
    for source in (("Росстат", "Банк России", "Евростат", "МВФ") if locale == "ru" else ("Eurostat", "IMF")):
        assert source in text


def test_server_html_carries_the_blocks(client):
    for locale, title in (("ru", "Чего мы не делаем"), ("en", "What we do not do")):
        response = client.get("/seo/page/about", headers={"X-FE-Locale": locale})
        assert response.status_code == 200
        assert f"<h2>{title}</h2>" in response.text
        assert "info@forecasteconomy.com" in response.text

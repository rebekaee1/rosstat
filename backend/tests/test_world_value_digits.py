"""Точность чисел ряда страны мира на сервере — правило SPA (14.11.2026).

Случаи общие с фронтендом: ``frontend/src/lib/worldValueDigits.cases.json`` читает и
``worldValueDigits.test.js``. Ряд меньше единицы по модулю — до четырёх знаков с обеих сторон.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.services.display import format_fixed, world_series_digits
from tests.test_seo_world_year import CODE_ANNUAL, CODE_MONTHLY, world_year_client  # noqa: F401
from tests.test_world_compare_frequency import frequency_client  # noqa: F401

CASES = json.loads(
    (Path(__file__).resolve().parents[2] / "frontend/src/lib/worldValueDigits.cases.json").read_text("utf-8")
)


UNIFORM_CASES = json.loads(
    (Path(__file__).resolve().parents[2] / "frontend/src/lib/uniformDigits.cases.json").read_text("utf-8")
)


@pytest.mark.parametrize("case", UNIFORM_CASES["cases"], ids=lambda c: str(c["values"]))
def test_rating_precision_matches_spa(case):
    """Рейтинг мира: одна точность на список, как countryFlag.uniformDigits (14.11.2026)."""
    from app.services.display import uniform_digits

    assert uniform_digits(case["values"]) == case["digits"]


@pytest.mark.parametrize("host, locale", [("forecasteconomy.com", "en"), ("ru.forecasteconomy.com", "ru")])
def test_world_vs_page_uses_series_precision(frequency_client, host, locale):  # noqa: F811
    """Сравнение стран: числа каждой страны — по правилу её ряда, без «2,5333» (14.11.2026)."""
    html = frequency_client.get("/seo/world-vs/germany-vs-japan/hicp-index",
                                headers={"Host": host, "X-FE-Locale": locale}).text
    body = html.split("<h1", 1)[1]
    numbers = re.findall(r"\d+[.,](\d+)\s?%", re.sub(r"<[^>]+>", " ", body))
    assert numbers and all(len(frac) <= 2 for frac in numbers), numbers


def _plain(text: str) -> str:
    return text.replace("\u00a0", " ").replace("\u202f", " ").replace("\u2212", "-")


@pytest.mark.parametrize("case", CASES["cases"], ids=lambda c: str(c["values"]))
def test_same_digits_and_text_as_spa(case):
    digits = world_series_digits(case["values"])
    assert digits == case["digits"]
    assert _plain(format_fixed(case["values"][0], digits, locale="en")) == case["en"]
    assert _plain(format_fixed(case["values"][0], digits, locale="ru")) == case["ru"]


def test_format_fixed_typography_and_rounding():
    assert format_fixed(1234567.891, 2, locale="ru") == "1 234 567,89"
    assert format_fixed(-3.25, 1, locale="ru") == "\u22123,3"  # как toFixed: от нуля при равной близости
    assert format_fixed(2.5, 0, locale="en") == "3"
    assert format_fixed(-0.001, 2, locale="ru") == "0,00"  # округлилось до нуля — без минуса
    assert format_fixed(None, 2, locale="en") == "no data"


def test_digits_edge_cases():
    assert world_series_digits([]) == 2
    assert world_series_digits([None, 3.25]) == 2
    assert world_series_digits([5.0, 6.0]) == 0
    assert world_series_digits([0.5, 0.25, 0.123456]) == 4  # меньше единицы — до четырёх знаков


def test_world_card_uses_series_precision(world_year_client):  # noqa: F811
    """Карточка страны мира: лид, «Последние значения» и «по годам» — одна точность ряда."""
    html = world_year_client.get(
        f"/seo/world/germany/{CODE_ANNUAL}", headers={"Host": "forecasteconomy.com", "X-FE-Locale": "en"},
    ).text
    cells = re.findall(r"<td>([0-9][0-9,.  ]*)</td>", html)
    assert cells and all("." not in cell for cell in cells), cells  # численность — целые числа


@pytest.mark.parametrize("code, host, locale, expected", [
    (CODE_ANNUAL, "forecasteconomy.com", "en", re.compile(r"^\d{4}$")),
    (CODE_ANNUAL, "ru.forecasteconomy.com", "ru", re.compile(r"^\d{4}$")),
    (CODE_MONTHLY, "forecasteconomy.com", "en", re.compile(r"^[A-Z][a-z]+ \d{4}$")),
])
def test_world_og_period_follows_frequency(world_year_client, monkeypatch, code, host, locale, expected):  # noqa: F811
    """OG-картинка карточки страны мира (14.11.2026): у годового ряда «2025», а не «January 2025»; месяц — как был."""
    from app.api import sitemap

    captured = {}
    monkeypatch.setattr("app.services.og_image.cached_og", lambda *_args, **_kwargs: None)

    async def capture_render(_renderer, **kwargs):
        captured.update(kwargs)
        return b"\x89PNG\r\n\x1a\n"

    async def skip_store(*_args, **_kwargs):
        return None

    monkeypatch.setattr(sitemap, "render_og_async", capture_render)
    monkeypatch.setattr("app.services.og_image.store_og_async", skip_store)
    response = world_year_client.get(
        f"/api/v1/og-image/world/germany/{code}.png", headers={"Host": host, "X-FE-Locale": locale},
    )
    assert response.status_code == 200
    assert expected.match(captured["date_text"]), captured["date_text"]
    assert captured["code"].startswith("fe3:world:")
    # Единица на языке картинки: до 14.11 русская картинка брала английскую («annual change», «people»).
    tail = captured["value_text"].split(" ", 1)[1] if " " in captured["value_text"] else ""
    if locale == "ru":
        assert not re.search(r"[A-Za-z]", tail), captured["value_text"]
    else:
        assert not re.search(r"[А-Яа-яЁё]", tail), captured["value_text"]

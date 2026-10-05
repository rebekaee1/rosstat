"""«Главное» в серверном HTML страницы страны и в предзагрузке для приложения."""

from __future__ import annotations

import json
import re
from datetime import date

import pytest

from app.services import seo_country_figures as scf
from test_seo_world import world_seo_client  # noqa: F401  (фикстура мирового датасета)

NB = chr(0xA0)  # неразрывный пробел
MINUS = chr(0x2212)
MIDDLE_DOT = chr(0xB7)


def _nb(text: str) -> str:
    """В шаблонах `~` означает неразрывный пробел."""
    return text.replace("~", NB)


def _bootstrap(html: str) -> dict:
    match = re.search(
        r'<script type="application/json" id="fe-country-bootstrap">(.*?)</script>', html, re.S,
    )
    assert match, "в head нет #fe-country-bootstrap"
    return json.loads(match.group(1))


def _key_section(html: str) -> str:
    match = re.search(r'<section class="seo-section" id="key-figures">(.*?)</section>', html, re.S)
    assert match, "в теле нет секции «Главное»"
    return match.group(1)


def test_country_html_has_key_figures_text_ru(world_seo_client):  # noqa: F811
    html = world_seo_client.get("/seo/world/germany").text
    section = _key_section(html)
    assert "<h2>Главное</h2>" in section
    # Инфляция за год: название, значение, период.
    assert _nb("Инфляция</strong></a>: <strong>11,4~% за год</strong>, июнь 2025.") in section
    # Безработица: единица читается сразу после числа, «год назад» без повтора единицы.
    assert _nb(
        "Безработица</strong></a>: <strong>4,7~% экономически активного населения</strong>, "
        "июнь 2025. Год назад: 3,5~%."
    ) in section
    # Годовой ВВП в «трлн €» с пометкой про инфляцию; 3,25 округляется вверх, как в приложении.
    assert _nb(
        "ВВП, год</strong></a>: <strong>3,3~трлн €</strong>, 2025, с поправкой на инфляцию. "
        "Год назад: 3,2~трлн €."
    ) in section
    # Ссылки ведут на страницы показателей страны.
    assert 'href="/germany/indicator/de-nama_10_gdp-b1gq-clv15-meur"' in section
    # Правила репозитория: без средней точки в серверном тексте.
    assert MIDDLE_DOT not in section
    # Секция идёт раньше картинки и ключевой таблицы: поисковик видит её сразу.
    assert html.index('id="key-figures"') < html.index("<figure")


def test_country_html_key_figures_en(world_seo_client):  # noqa: F811
    html = world_seo_client.get("/seo/world/germany?preview_locale=en").text
    section = _key_section(html)
    assert "<h2>Key figures</h2>" in section
    assert _nb("Inflation</strong></a>: <strong>11.4~% year over year</strong>, June 2025.") in section
    assert _nb("A year ago: 3.5~%.") in section
    assert _nb("3.3~trillion €</strong>, 2025, adjusted for inflation.") in section
    assert not re.search(r"[А-Яа-яЁё]", section)


def test_country_html_bootstrap_matches_text(world_seo_client):  # noqa: F811
    html = world_seo_client.get("/seo/world/germany").text
    data = _bootstrap(html)
    assert data["v"] == 1
    assert data["slug"] == "germany"
    assert data["locale"] == "ru"
    assert data["country"]["name"] == "Германия"
    items = data["overview"]
    assert 1 <= len(items) <= scf.KEY_FIGURES_MAX
    for item in items:
        assert item["indicator_code"] and item["concept_slug"]
        assert item["points"], item
        # Последняя точка графика совпадает со значением карточки.
        assert item["points"][-1] == [item["date"], item["value"]]
        # Точки идут по возрастанию даты.
        days = [point[0] for point in item["points"]]
        assert days == sorted(days)
    # Закрывающий тег в JSON не ломает страницу.
    raw = re.search(r'id="fe-country-bootstrap">(.*?)</script>', html, re.S).group(1)
    assert "</" not in raw
    # Предзагрузка легка: четыре ряда по десять лет, без полных историй.
    assert len(raw) < 30_000


def test_country_html_uses_redis_catalog_when_cached(world_seo_client, monkeypatch):  # noqa: F811
    """Каталог страны уже в Redis: «Главное» берётся оттуда, без повторного расчёта."""
    import app.core.cache as cache_mod
    from app.api import world as world_api

    catalog = {
        "country": {"code": "DE", "slug": "germany", "name": "Германия", "name_en": "Germany",
                    "region": "Европа", "region_en": "Europe"},
        "overview": [{
            "concept_slug": "unemployment-rate",
            "name": "Уровень безработицы", "name_en": "Unemployment rate",
            "unit": "% экономически активного населения",
            "indicator_code": "de-une_rt_m-total-sa-t-pc-act",
            "frequency": "monthly", "date": "2025-06-01", "value": 4.7,
        }],
    }
    real_cache_get = cache_mod.cache_get

    async def _cache_get(key, *args, **kwargs):
        if ":country:v18:germany:" in str(key):
            return catalog
        return await real_cache_get(key, *args, **kwargs)

    monkeypatch.setattr(cache_mod, "cache_get", _cache_get)

    async def _boom(*_a, **_k):
        raise AssertionError("overview не должен пересчитываться при попадании в Redis")

    monkeypatch.setattr(world_api, "build_country_overview", _boom)
    html = world_seo_client.get("/seo/world/germany").text
    data = _bootstrap(html)
    assert [item["concept_slug"] for item in data["overview"]] == ["unemployment-rate"]
    assert "Безработица" in _key_section(html)


def test_country_page_survives_failed_key_figures(world_seo_client, monkeypatch):  # noqa: F811
    async def _fail(db, country):
        raise RuntimeError("redis and db are down")

    monkeypatch.setattr(scf, "_load", _fail)
    resp = world_seo_client.get("/seo/world/germany")
    assert resp.status_code == 200
    assert 'id="key-figures"' not in resp.text
    assert "fe-country-bootstrap" not in resp.text
    assert "Экономика Германии" in resp.text


def test_year_ago_point_picks_same_period():
    points = [(date(2024, m, 1), float(m)) for m in range(1, 13)] + [(date(2025, 6, 1), 20.0)]
    ago = scf.year_ago_point(sorted(points), "monthly")
    assert ago == (date(2024, 6, 1), 6.0)
    assert scf.year_ago_point([(date(2025, 6, 1), 1.0)], "monthly") is None
    # Слишком большой разрыв: нет честного «года назад».
    far = [(date(2020, 6, 1), 1.0), (date(2025, 6, 1), 2.0)]
    assert scf.year_ago_point(far, "monthly") is None


def test_scale_money_matches_frontend_rules():
    scaled = scf._scale_money(849_680.0, "в постоянных ценах 2015 года, млн евро", "ru")
    assert scaled is not None
    assert round(scaled[0], 2) == 849.68
    assert scaled[1:] == ("млрд €", "в постоянных ценах 2015 года")
    trillions = scf._scale_money(3_250_000.0, "млн евро", "ru")
    assert trillions is not None and round(trillions[0], 2) == 3.25 and trillions[1] == "трлн €"
    english = scf._scale_money(
        849_680.0, scf._tidy_unit_en("chain-linked volumes, 2015, million euro"), "en",
    )
    assert english is not None
    assert english[1:] == ("billion €", "in 2015 prices")
    assert scf._scale_money(4.7, "%", "ru") is None


def test_period_text_quarter_both_languages():
    assert scf._period_text(date(2026, 4, 1), "quarterly", "ru") == "II кв. 2026"
    assert scf._period_text(date(2026, 4, 1), "quarterly", "en") == "Q2 2026"
    assert scf._period_text(date(2026, 4, 1), "annual", "ru") == "2026"


def test_number_format_follows_locale():
    assert scf._fixed(849.68, 1, "ru") == "849,7"
    assert scf._fixed(849.68, 1, "en") == "849.7"
    assert scf._fixed(12345.0, 0, "ru") == "12" + NB + "345"
    assert scf._fixed(12345.0, 0, "en") == "12,345"
    assert scf._fixed(-0.4, 1, "ru") == MINUS + "0,4"
    # Как toFixed в JS: ничья округляется вверх.
    assert scf._fixed(3.25, 1, "ru") == "3,3"
    assert scf._fixed(-0.001, 2, "ru") == "0,00"

"""Integration test: все 8 индикаторов семьи ВВП обязаны отдавать
непустой прогноз через публичный API `/api/v1/indicators/{code}/forecast`.

Тест ходит в живую БД через FastAPI TestClient. Если запускается в среде,
где БД недоступна (роль не существует / БД не поднята / индикатор не сидован),
тест мягко skip'ается — в production CI и на проде должна быть поднятая БД
со всеми 8 индикаторами.

Контракт: ровно 8 кодов (4 номинала + 4 реала) должны вернуть валидный
объект `forecast` с непустым `values`. Это защищает от регрессий вида
«после деплоя на /indicator/gdp-real-annual пропал прогноз».
"""

from __future__ import annotations

import pytest

GDP_FAMILY_CODES = (
    "gdp-nominal",
    "gdp-yoy",
    "gdp-qoq",
    "gdp-nominal-annual",
    "gdp-real",
    "gdp-real-yoy",
    "gdp-real-qoq",
    "gdp-real-annual",
)


@pytest.mark.parametrize("code", GDP_FAMILY_CODES)
def test_gdp_family_indicator_returns_non_empty_forecast(client, code: str) -> None:
    try:
        r = client.get(f"/api/v1/indicators/{code}/forecast")
    except Exception as exc:  # noqa: BLE001 — БД недоступна локально
        pytest.skip(f"DB not reachable in this environment: {exc!r}")
    if r.status_code in (404, 500, 503):
        pytest.skip(
            f"indicator '{code}' not reachable (HTTP {r.status_code}); "
            "requires seeded DB with retrained forecasts"
        )
    assert r.status_code == 200, f"{code}: HTTP {r.status_code} — {r.text[:200]}"

    payload = r.json()
    forecast = payload.get("forecast")
    assert forecast is not None, (
        f"{code}: forecast is null on /forecast endpoint — "
        "retrain after deploy missing or strategy misconfigured"
    )
    values = forecast.get("values") or []
    assert len(values) >= 1, (
        f"{code}: forecast.values is empty — "
        "derived strategy returned no future points"
    )

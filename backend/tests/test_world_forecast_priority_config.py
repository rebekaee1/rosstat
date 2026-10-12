"""Список приоритетных стран прогнозов: config.py, .env.example и docker-compose.yml говорят одно и то же.

Круг 13: список изменили (Китай и Япония вперёд, добавлена Турция) в config.py и .env.example, а
docker-compose.yml его не пробрасывал; значение из .env хоста в контейнер не попадало вовсе
(backend/.dockerignore исключает .env из образа, compose передаёт только перечисленное в environment).
"""
import re
from pathlib import Path

import pytest

from app.config import Settings
from app.services.world_forecast_pipeline import parse_priority_countries

ROOT = Path(__file__).resolve().parents[2]
NAME = "RUSTATS_WORLD_FORECAST_PRIORITY_COUNTRIES"


def _config_default() -> list[str]:
    return parse_priority_countries(Settings.model_fields["world_forecast_priority_countries"].default)


def test_default_order_puts_china_and_japan_forward_and_includes_turkey():
    slugs = _config_default()
    assert slugs[:3] == ["united-states", "china", "japan"]
    assert "turkey" in slugs
    assert len(slugs) == len(set(slugs))


@pytest.mark.skipif(not (ROOT / "docker-compose.yml").exists(), reason="нет корня репозитория")
def test_compose_passes_the_variable_with_the_same_default():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    hits = re.findall(rf"^\s+{NAME}:\s*\$\{{{NAME}:-([^}}]+)\}}\s*$", compose, flags=re.M)
    assert hits, "docker-compose.yml не пробрасывает приоритетные страны прогнозов в backend/scheduler"
    # пустое значение недопустимо: пустая строка стала бы пустым списком и сняла приоритет
    assert all(parse_priority_countries(h) == _config_default() for h in hits)


@pytest.mark.skipif(not (ROOT / ".env.example").exists(), reason="нет корня репозитория")
def test_env_example_matches_config_default():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    found = re.search(rf"^{NAME}=(.*)$", text, flags=re.M)
    assert found, ".env.example не содержит переменную"
    assert parse_priority_countries(found.group(1)) == _config_default()

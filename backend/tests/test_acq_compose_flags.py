"""Флаги совета по привлечению (19.11.2026) доходят до контейнеров backend и scheduler.

Settings читает переменные окружения контейнера, а не `.env` напрямую: переменная, которой нет в
`environment` у backend в docker-compose.yml, на боевом молча остаётся значением по умолчанию.
Так при сведении веток чуть не потерялись подписка сразу по ссылке и три флага строки «присылать».
"""
from pathlib import Path

import pytest

from app.config import Settings

COMPOSE = Path(__file__).resolve().parents[2] / "docker-compose.yml"

COUNCIL_FIELDS = (
    "public_bot_site_autosubscribe",
    "acq_site_line_enabled",
    "acq_site_line_topics",
    "acq_site_first_screen_enabled",
    "topic_mail_enabled",
    "promised_freshness_watchdog_enabled",
    "regional_fuel_bulletin_enabled",
)


@pytest.mark.parametrize("field", COUNCIL_FIELDS)
def test_council_flag_reaches_backend_container(field):
    assert field in Settings.model_fields, f"{field} нет в Settings"
    env = f"RUSTATS_{field.upper()}"
    text = COMPOSE.read_text(encoding="utf-8")
    assert f"      {env}: ${{{env}:-" in text, f"{env} не передаётся в контейнер (docker-compose.yml, backend environment)"

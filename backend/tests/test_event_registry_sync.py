"""Имена групп событий должны существовать в реестре фронтенда (круг 11, зона H)."""
import re
from pathlib import Path

import pytest

from app.services import goal_taxonomy as tax


def test_grouped_events_exist_in_frontend_registry():
    """Все имена групп заведены в реестре track.js (иначе событие нечем породить)."""
    track = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "track.js"
    if not track.exists():
        pytest.skip("frontend/src/lib/track.js недоступен в этом окружении")
    registry = set(re.findall(r"[A-Z_]+:\s*'([a-z0-9_]+)'", track.read_text()))
    missing = tax.all_grouped_events() - registry
    assert not missing, f"в track.js не хватает событий групп: {sorted(missing)}"

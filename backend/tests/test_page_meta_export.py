"""Guard: pageMeta.generated.json ↔ seo_content / seo_world (ADR-0003)."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.page_meta_export import build_page_meta_blob

ROOT = Path(__file__).resolve().parents[2]
GENERATED = ROOT / "frontend" / "src" / "lib" / "pageMeta.generated.json"


def test_page_meta_generated_matches_backend():
    blob = build_page_meta_blob()
    expected = json.dumps(blob, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    assert GENERATED.exists(), "pageMeta.generated.json отсутствует — python scripts/export-page-meta.py"
    actual = GENERATED.read_text(encoding="utf-8")
    assert actual == expected, (
        "pageMeta.generated.json устарел относительно seo_content.py / seo_world.py. "
        "Запустите: python scripts/export-page-meta.py"
    )


def test_page_meta_covers_static_pages_and_categories():
    blob = build_page_meta_blob()
    for slug in ("home", "about", "methodology", "calculator-mortgage", "compare"):
        assert slug in blob["pages"]
        page = blob["pages"][slug]
        assert page["title"] and page["description"] and page["h1"]
    assert "prices" in blob["categories"]
    assert blob["categories"]["prices"]["h1"] == blob["categories"]["prices"]["title"]
    assert "home" not in blob["world"], "витрина /world снята — метаданных быть не должно"
    assert "germany" in blob["world"]["countryGenitive"]

"""Regression: scripts/audit-public-language.py зелёный на product-surfaces."""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit-public-language.py"


def _load_audit_module():
    spec = importlib.util.spec_from_file_location("audit_public_language", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_audit_public_language_script_exits_zero():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "OK:" in proc.stdout


def test_product_claim_banlist_catches_stale_counters():
    mod = _load_audit_module()
    samples = [
        "80+ индикаторов в 9 категориях",
        "в девяти тематических разделах",
        "статистика стран мира",
        "аккаунт снимает лимит на выгрузку",
        "скачивание без регистрации",
    ]
    for sample in samples:
        assert mod.PRODUCT_CLAIM_RE.search(sample), sample


def test_product_claim_banlist_allows_honest_copy():
    mod = _load_audit_module()
    ok = (
        "Более 100 макроиндикаторов России, регионы и доступная статистика стран. "
        "Просмотр бесплатен без аккаунта. Скачивание — после бесплатной регистрации."
    )
    assert mod.PRODUCT_CLAIM_RE.search(ok) is None


def test_product_surfaces_listed_and_exist():
    mod = _load_audit_module()
    assert "frontend/src/pages/About.jsx" in mod.PRODUCT_SURFACES
    assert "frontend/public/llms.txt" in mod.PRODUCT_SURFACES
    for rel in mod.PRODUCT_SURFACES:
        assert (ROOT / rel).is_file(), rel


@pytest.mark.parametrize(
    "needle",
    [
        re.compile(r"после бесплатной регистрации", re.I),
        re.compile(r"доступн\w+\s+статистик", re.I),
    ],
)
def test_about_has_honest_product_phrasing(needle: re.Pattern[str]):
    text = (ROOT / "frontend/src/pages/About.jsx").read_text(encoding="utf-8")
    assert needle.search(text)

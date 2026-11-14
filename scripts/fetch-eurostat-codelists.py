#!/usr/bin/env python3
"""Снимок официальных английских подписей кодлистов Евростата для срезов рядов (14.11.2026).

Подписи уточнений в названиях рядов стран мира (`world_series_title`) берутся только из официальных
кодлистов источника. Скрипт читает из базы, какие значения измерений встречаются в срезах листинговых
рядов, скачивает кодлисты Евростата (SDMX 2.1, ``codelist/ESTAT/{ID}/latest?format=TSV&lang=en``) и
пишет в ``backend/app/data/eurostat_codelists_en.json`` только используемые значения — с адресом
источника и датой. Сеть нужна только здесь; приложение читает готовый снимок.

Запуск: ``backend/.venv/bin/python scripts/fetch-eurostat-codelists.py`` с ``RUSTATS_DATABASE_URL``
локальной копии. За VPN: ``FE_CURL_INTERFACE=en0``.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
OUT = ROOT / "backend/app/data/eurostat_codelists_en.json"
URL = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/codelist/ESTAT/{cl}/latest?format=TSV&lang=en"


def parse_tsv(text: str) -> dict[str, str]:
    """Строки «КОД<TAB>Подпись» кодлиста; пустые и неполные пропускаются."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        code, _, label = line.partition("\t")
        if code.strip() and label.strip():
            out[code.strip().upper()] = label.strip()
    return out


async def used_members() -> dict[str, set[str]]:
    from sqlalchemy import text

    from app.database import async_session
    from app.services.world_series_title import SLICE_AXES

    async with async_session() as db:
        rows = (await db.execute(text(
            "select distinct slice_json from world_indicators where is_listed and provider = 'eurostat'"
        ))).all()
    used: dict[str, set[str]] = {axis: set() for axis in SLICE_AXES}
    for (raw,) in rows:
        data = raw if isinstance(raw, dict) else json.loads(raw or "{}")
        for axis in SLICE_AXES:
            if data.get(axis) is not None:
                used[axis].add(str(data[axis]).strip().upper())
    return {axis: codes for axis, codes in used.items() if codes}


def fetch(cl: str) -> str:
    cmd = ["curl", "-s", "-m", "60", "-f", URL.format(cl=cl)]
    if os.environ.get("FE_CURL_INTERFACE"):
        cmd[1:1] = ["--interface", os.environ["FE_CURL_INTERFACE"]]
    return subprocess.run(cmd, capture_output=True, text=True, check=False).stdout


def main() -> int:
    used = asyncio.run(used_members())
    labels: dict[str, dict[str, str]] = {}
    missing: dict[str, int] = {}
    for axis, codes in sorted(used.items()):
        codelist = parse_tsv(fetch(axis.upper()))
        if not codelist:
            missing[axis] = len(codes)
            continue
        labels[axis] = {code: codelist[code] for code in sorted(codes) if code in codelist}
    OUT.write_text(json.dumps({
        "source": URL.format(cl="{ID}"),
        "retrieved": date.today().isoformat(),
        "note": "Официальные английские подписи кодлистов Евростата; только значения из срезов листинговых рядов.",
        "labels": labels,
    }, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"измерений: {len(labels)}, значений: {sum(len(v) for v in labels.values())}; без кодлиста: {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

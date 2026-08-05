#!/usr/bin/env python3
"""Общие хелперы для аудита правдивости world/Eurostat (read-only)."""

from __future__ import annotations

import asyncio
import json
import math
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import asyncpg
import requests

REPO = Path(__file__).resolve().parents[1]
DB_DSN = "postgresql://rustats:rustats_dev@localhost:5434/rustats"
API_BASE = "http://127.0.0.1:8000/api/v1"
EUROSTAT_BASE = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
)
OUT_DIR = Path(__file__).resolve().parent / "audit-world-out"

# Ожидаемый порядок населения (примерно, млн человек, 2020-е).
# Используется для проверки единиц «тысяч человек» / «млн».
POP_MILLIONS_APPROX: dict[str, float] = {
    "DE": 83, "FR": 68, "IT": 59, "ES": 48, "PL": 38, "RO": 19, "NL": 18,
    "BE": 12, "CZ": 11, "SE": 10, "PT": 10, "HU": 10, "AT": 9, "CH": 9,
    "BG": 7, "DK": 6, "FI": 5.5, "SK": 5.5, "NO": 5.5, "IE": 5.2, "HR": 3.9,
    "LT": 2.8, "SI": 2.1, "LV": 1.9, "EE": 1.3, "CY": 0.9, "LU": 0.66,
    "MT": 0.52, "IS": 0.38, "AL": 2.8, "RS": 6.6, "BA": 3.2, "MK": 1.8,
    "ME": 0.62, "XK": 1.8, "TR": 85, "UA": 37, "MD": 2.5, "GE": 3.7,
    "AM": 3.0, "AZ": 10, "UK": 67, "US": 335, "CN": 1410, "JP": 125,
    "KR": 52, "IN": 1420, "BR": 215, "MX": 130, "CA": 40, "AU": 27,
    "NZ": 5.2, "ZA": 60, "IL": 9.5,
}

TOPIC_PATTERNS: list[tuple[str, str]] = [
    ("gdp", r"ввп|gdp|b1gq|nama_10_gdp|namq_10_gdp"),
    ("inflation", r"инфляц|hicp|ипц|prc_hicp|цен"),
    ("unemployment", r"безработ|une_rt|teilm"),
    ("population", r"населен|demo_pjan|tps00001|демограф"),
    ("industry", r"промпроизв|промышленн|sts_inpr|ipi"),
    ("trade", r"торгов|баланс|ext_|бсальдо"),
    ("wages", r"зарплат|заработ|оплат.*труд|earn|lc_lci|nama_10_fte|wages"),
]


def ensure_out() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUT_DIR


def write_json(name: str, payload: Any) -> Path:
    ensure_out()
    path = OUT_DIR / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


async def connect() -> asyncpg.Connection:
    return await asyncpg.connect(DB_DSN)


def parse_period(period: str) -> date:
    s = (period or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return date.fromisoformat(s)
    if re.fullmatch(r"\d{4}-W\d{2}", s):
        return datetime.strptime(s + "-1", "%G-W%V-%u").date()
    m = re.fullmatch(r"(\d{4})-Q([1-4])", s)
    if m:
        y, q = int(m.group(1)), int(m.group(2))
        return date(y, (q - 1) * 3 + 1, 1)
    m = re.fullmatch(r"(\d{4})-S([12])", s)
    if m:
        y, sem = int(m.group(1)), int(m.group(2))
        return date(y, 1 if sem == 1 else 7, 1)
    if re.fullmatch(r"\d{4}-\d{2}", s):
        y, mo = map(int, s.split("-"))
        return date(y, mo, 1)
    if re.fullmatch(r"\d{4}", s):
        return date(int(s), 1, 1)
    raise ValueError(f"unsupported period: {period!r}")


def as_slice_dict(slice_json: Any) -> dict[str, Any]:
    """asyncpg часто отдаёт jsonb как str — нормализуем в dict."""
    if slice_json is None:
        return {}
    if isinstance(slice_json, dict):
        return slice_json
    if isinstance(slice_json, str):
        return json.loads(slice_json) if slice_json.strip() else {}
    return dict(slice_json)


def build_eurostat_url(dataset_id: str, slice_json: Any, geo: str | None = None) -> str:
    params: dict[str, Any] = {"format": "JSON", "lang": "en"}
    for k, v in as_slice_dict(slice_json).items():
        if str(k).lower() in {"geo", "time", "time_period"}:
            continue
        params[k] = v
    if geo:
        params["geo"] = geo
    return f"{EUROSTAT_BASE}/{dataset_id}?{urlencode(params)}"


def fetch_eurostat_series(
    dataset_id: str,
    slice_json: Any,
    geo: str,
    *,
    timeout: int = 120,
    session: requests.Session | None = None,
) -> list[tuple[date, float]]:
    """Скачать один geo-ряд из JSON-stat с теми же измерениями, что в slice_json."""
    url = build_eurostat_url(dataset_id, as_slice_dict(slice_json), geo=geo)
    sess = session or requests.Session()
    resp = sess.get(url, timeout=timeout)
    resp.raise_for_status()
    payload = resp.json()
    return parse_jsonstat_geo(payload, geo)


def parse_jsonstat_geo(payload: dict, geo: str) -> list[tuple[date, float]]:
    ids: list[str] = list(payload.get("id") or [])
    sizes: list[int] = list(payload.get("size") or [])
    dimension = payload.get("dimension") or {}
    values = payload.get("value") or {}
    if "geo" not in ids or "time" not in ids:
        raise ValueError(f"JSON-stat missing geo/time: {ids}")

    def members(dim: str) -> list[str]:
        index = ((dimension.get(dim) or {}).get("category") or {}).get("index") or {}
        if isinstance(index, dict):
            return [k for k, _ in sorted(index.items(), key=lambda kv: kv[1])]
        return list(index)

    geo_members = members("geo")
    time_members = members("time")
    if geo not in geo_members:
        # EL/GR, UK/GB aliases
        aliases = {"EL": "GR", "GR": "EL", "UK": "GB", "GB": "UK"}
        alt = aliases.get(geo)
        if alt and alt in geo_members:
            geo = alt
        else:
            return []

    geo_idx = ids.index("geo")
    time_idx = ids.index("time")
    strides = [1] * len(sizes)
    for i in range(len(sizes) - 2, -1, -1):
        strides[i] = strides[i + 1] * sizes[i + 1]

    def decode(flat: int) -> list[int]:
        coords = [0] * len(sizes)
        rem = flat
        for i, stride in enumerate(strides):
            coords[i] = rem // stride
            rem %= stride
        return coords

    geo_pos = geo_members.index(geo)
    out: dict[date, float] = {}
    items = values.items() if isinstance(values, dict) else (
        (str(i), v) for i, v in enumerate(values) if v is not None
    )
    for key, raw in items:
        if raw is None:
            continue
        try:
            flat = int(key)
            val = float(raw)
        except (TypeError, ValueError):
            continue
        coords = decode(flat)
        if coords[geo_idx] != geo_pos:
            continue
        period = time_members[coords[time_idx]]
        try:
            dt = parse_period(period)
        except ValueError:
            continue
        out[dt] = val
    return sorted(out.items())


def values_close(a: float, b: float, *, rel: float = 1e-6, abs_tol: float = 1e-4) -> bool:
    if math.isnan(a) or math.isnan(b):
        return False
    return abs(a - b) <= max(abs_tol, rel * max(abs(a), abs(b), 1.0))


def classify_topic(name_ru: str, dataset_id: str, category_ru: str) -> str | None:
    hay = f"{name_ru} {dataset_id} {category_ru}".lower()
    for topic, pat in TOPIC_PATTERNS:
        if re.search(pat, hay, re.I):
            return topic
    return None


def unit_looks_percent(unit: str, unit_ru: str) -> bool:
    u = (unit or "").upper().replace("-", "_")
    ru = (unit_ru or "").lower().strip()
    # Коды, которые Eurostat иногда зовёт PC, но это НЕ проценты (PPS и пр.)
    if u in {"PPS_EU27_2020_HAB", "PPS_HAB", "NAC_HAB", "EUR_HAB", "CP_EUR_HAB"}:
        return False
    if u in {"PC", "PC_ACT", "PC_POP", "PC_GDP", "PCH_SAME", "PCH_SM", "PCH_PRE", "RT"}:
        return True
    if ru.startswith("%") or ru == "%" or "процент" in ru:
        return True
    return False


def unit_looks_index(unit: str, unit_ru: str) -> bool:
    u = (unit or "").upper()
    ru = (unit_ru or "").lower()
    if u.startswith("I") and u[1:].isdigit():
        return True
    if "индекс" in ru and "= 100" in ru.replace("=", " = "):
        return True
    if "2015 = 100" in ru or "2010 = 100" in ru or "2005 = 100" in ru:
        return True
    return False


def index_base_year(unit: str, unit_ru: str) -> int | None:
    u = (unit or "").upper()
    m = re.fullmatch(r"I(\d{2})", u)
    if m:
        yy = int(m.group(1))
        return 2000 + yy if yy < 80 else 1900 + yy
    m = re.search(r"(20\d{2})\s*=\s*100", unit_ru or "")
    if m:
        return int(m.group(1))
    return None


def unit_scale_people(unit: str, unit_ru: str) -> str | None:
    """Возвращает 'ths' | 'mio' | 'nr' | None."""
    u = (unit or "").upper()
    ru = (unit_ru or "").lower()
    if u in {"THS_PER", "THS"} or "тысяч человек" in ru or "тыс. человек" in ru:
        return "ths"
    if u in {"MIO_PER", "MIO"} or "млн человек" in ru or "миллион" in ru and "человек" in ru:
        return "mio"
    if u == "NR" or ru == "человек":
        return "nr"
    return None


async def fetch_indicator_points(conn: asyncpg.Connection, indicator_id: int) -> list[tuple[date, float]]:
    rows = await conn.fetch(
        """
        SELECT date, value::float8 AS value
        FROM world_data_points
        WHERE indicator_id = $1
        ORDER BY date
        """,
        indicator_id,
    )
    return [(r["date"], float(r["value"])) for r in rows]


def api_get(path: str, *, params: dict | None = None, timeout: int = 60) -> Any:
    url = f"{API_BASE}{path}"
    resp = requests.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def run_async(coro):
    return asyncio.run(coro)


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

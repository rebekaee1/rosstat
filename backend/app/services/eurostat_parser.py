"""Eurostat JSON-stat parser for the world economy bounded context.

Canonical source
----------------
Eurostat Dissemination API (SDMX 2.1 / statistics 1.0), base::

    https://ec.europa.eu/eurostat/api/dissemination/

Endpoints used
--------------
1. Structure (dimension members) — lightweight probe with ``lastTimePeriod=1``::

       GET .../statistics/1.0/data/{DATASET_ID}?format=JSON&lang=en&lastTimePeriod=1

   Response is JSON-stat: ``dimension`` maps each dimension id → category
   index/label. Dimensions ``geo`` and ``time`` (``TIME_PERIOD``) stay free;
   every other dimension is pinned to a headline member (see
   ``HEADLINE_PRIORITY``).

   Optional DSD fallback (XML)::

       GET .../sdmx/2.1/datastructure/ESTAT/{DATASET_ID}?compressed=false

2. Full series for all geos with fixed headline filters::

       GET .../statistics/1.0/data/{DATASET_ID}?format=JSON&lang=en&{dim}={member}&...

   ``geo`` and ``time`` are NOT fixed — one request returns all countries ×
   all periods for the chosen slice.

Period normalisation
--------------------
``2026-06`` → 2026-06-01; ``2026-Q2`` → 2026-04-01; ``2026`` → 2026-01-01;
``2026-W23`` → Monday of ISO week; ``2026-06-15`` kept as-is; ``2026-S1`` →
2026-01-01.

Headline slice selection
------------------------
For each non-geo/non-time dimension pick the first member present in
``HEADLINE_PRIORITY[dim]`` (case-insensitive key match on dim id prefixes
like ``indic*``). Else prefer TOTAL / TOT / T; else the first code in the
codelist order.

Country filter
--------------
Keep ISO-2 style geo codes present in ``WORLD_COUNTRIES`` and not in
``EXCLUDED_GEO_CODES``. Drop a country series with fewer than ``MIN_POINTS``
(8) non-null observations.

Caching / politeness
--------------------
HTTP responses cached under ``backend/.cache/eurostat/`` (or ``/tmp/eurostat-cache``)
keyed by URL hash. Parallelism ≤ 8, retries with exponential backoff, timeout
120 s. No forecast / derived materialisation — points are raw levels only.

Dataset selection
-----------------
Loader queries ``research.source_catalog`` (source='eurostat') — single source
of truth; this module does not hardcode dataset lists.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

logger = logging.getLogger(__name__)

BASE_STATS = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
BASE_DSD = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/datastructure/ESTAT"

MIN_POINTS = 8
HTTP_TIMEOUT = 120
MAX_RETRIES = 4
DEFAULT_WORKERS = 8

# Priority member codes per dimension (first hit wins). Keys matched
# case-insensitively; ``indic*`` uses prefix match via _priority_for_dim.
HEADLINE_PRIORITY: dict[str, list[str]] = {
    "unit": [
        "I15", "I10", "I05", "I96", "PC", "PC_ACT", "PC_POP", "PC_GDP",
        "PCH_SAME", "PCH_SM", "PCH_PRE", "MIO_EUR", "CLV15_MEUR", "CP_MEUR",
        "THS_PER", "NR", "EUR", "RT", "INDEX",
    ],
    "s_adj": ["SCA", "SA", "NSA", "CA"],
    "nace_r2": ["B-D", "TOTAL", "B-E36", "C", "B", "F"],
    "nace_r1": ["TOTAL", "D", "C"],
    "coicop": ["CP00", "TOT_X_NRG", "TOT_X_NRG_FOOD"],
    "sex": ["T", "TOTAL"],
    "age": ["TOTAL", "Y15-74", "Y_GE15", "Y15-64"],
    "na_item": ["B1GQ", "B1G", "P3", "P51G", "B11"],
    "geo": [],  # never pin
    "time": [],
    "freq": ["M", "Q", "A", "W", "D"],
    "indic": [
        "INFMORRT", "TOTFERRT", "GNUPRT", "GBIRTHRT", "GDEATHRT",
        "JAN", "AVG", "TOTAL", "B1GQ",
    ],
    "indic_bt": [],
    "indic_sb": [],
    "indic_de": [
        "INFMORRT", "TOTFERRT", "GNUPRT", "GBIRTHRT", "GDEATHRT",
        "JAN", "AVG", "DEPRATIO1", "MEDAGEPOP",
    ],
    "cpa2_1": ["TOTAL"],
    "sizeclas": ["TOTAL"],
    "worktime": ["TOTAL"],
    "citizen": ["TOTAL"],
    "wstatus": ["EMP", "TOTAL"],
    "isced11": ["TOTAL"],
    "currency": ["EUR", "NAC"],
    "stk_flow": ["BAL_RT", "CRE", "DEB"],
    "partner": ["EXT_EU27_2020", "WORLD", "EU27_2020"],
    "sitc06": ["TOTAL"],
    # Энергетика: inland deliveries / available market — не «добыча угля,
    # которой в стране нет» (IPRD→нулевая константа на десятках стран).
    "nrg_bal": [
        "GID_OBS", "GID_CAL", "AIM", "ID", "FC_E", "GIC",
        "IMP", "EXP", "IPRD", "TI_EHG_MAP",
    ],
    "siec": [
        "TOTAL", "C0000X0350-0370", "C0000", "G3000", "O4000XBIO",
        "E7000", "H8000", "C0100",
    ],
}

_SKIP_DIMS = frozenset({"geo", "time", "time_period"})

FREQ_MAP = {
    "M": "monthly",
    "Q": "quarterly",
    "A": "annual",
    "W": "weekly",
    "D": "daily",
    "S": "annual",  # semester → treat as coarse annual-ish; rare
}

# Гео-коды, которые сознательно НЕ грузим в мировой блок.
# RU — на сайте уже полный российский каталог (Росстат / Банк России);
#      шесть рядов Евростата на /world/russia создают ложное впечатление,
#      что «российский» раздел платформы — это и есть весь продукт.
# Остальное — наднациональные агрегаты Евростата (не суверенные страны);
#      в списке рядом с Германией и Францией им не место.
EXCLUDED_GEO_CODES: frozenset[str] = frozenset({
    "RU",
    "EU", "EU27_2020", "EU28", "EU27", "EU25", "EU15", "EU12",
    "EA", "EA20", "EA19", "EA18", "EA17", "EA12", "EA11",
    "EFTA", "EEA", "EFTA18",
    "OECD", "G20", "WORLD", "WRL_REST",
})


# ISO-2 → (slug, name_ru, name_en, region_ru, sort_order)
WORLD_COUNTRIES: dict[str, tuple[str, str, str, str, int]] = {
    "AT": ("austria", "Австрия", "Austria", "Европа", 10),
    "BE": ("belgium", "Бельгия", "Belgium", "Европа", 20),
    "BG": ("bulgaria", "Болгария", "Bulgaria", "Европа", 30),
    "HR": ("croatia", "Хорватия", "Croatia", "Европа", 40),
    "CY": ("cyprus", "Кипр", "Cyprus", "Европа", 50),
    "CZ": ("czechia", "Чехия", "Czechia", "Европа", 60),
    "DK": ("denmark", "Дания", "Denmark", "Европа", 70),
    "EE": ("estonia", "Эстония", "Estonia", "Европа", 80),
    "FI": ("finland", "Финляндия", "Finland", "Европа", 90),
    "FR": ("france", "Франция", "France", "Европа", 100),
    "DE": ("germany", "Германия", "Germany", "Европа", 110),
    "EL": ("greece", "Греция", "Greece", "Европа", 120),
    "GR": ("greece", "Греция", "Greece", "Европа", 120),
    "HU": ("hungary", "Венгрия", "Hungary", "Европа", 130),
    "IE": ("ireland", "Ирландия", "Ireland", "Европа", 140),
    "IT": ("italy", "Италия", "Italy", "Европа", 150),
    "LV": ("latvia", "Латвия", "Latvia", "Европа", 160),
    "LT": ("lithuania", "Литва", "Lithuania", "Европа", 170),
    "LU": ("luxembourg", "Люксембург", "Luxembourg", "Европа", 180),
    "MT": ("malta", "Мальта", "Malta", "Европа", 190),
    "NL": ("netherlands", "Нидерланды", "Netherlands", "Европа", 200),
    "PL": ("poland", "Польша", "Poland", "Европа", 210),
    "PT": ("portugal", "Португалия", "Portugal", "Европа", 220),
    "RO": ("romania", "Румыния", "Romania", "Европа", 230),
    "SK": ("slovakia", "Словакия", "Slovakia", "Европа", 240),
    "SI": ("slovenia", "Словения", "Slovenia", "Европа", 250),
    "ES": ("spain", "Испания", "Spain", "Европа", 260),
    "SE": ("sweden", "Швеция", "Sweden", "Европа", 270),
    "IS": ("iceland", "Исландия", "Iceland", "Европа", 280),
    "NO": ("norway", "Норвегия", "Norway", "Европа", 290),
    "CH": ("switzerland", "Швейцария", "Switzerland", "Европа", 300),
    "UK": ("united-kingdom", "Великобритания", "United Kingdom", "Европа", 310),
    "GB": ("united-kingdom", "Великобритания", "United Kingdom", "Европа", 310),
    "TR": ("turkey", "Турция", "Türkiye", "Европа", 320),
    "RS": ("serbia", "Сербия", "Serbia", "Европа", 330),
    "ME": ("montenegro", "Черногория", "Montenegro", "Европа", 340),
    "MK": ("north-macedonia", "Северная Македония", "North Macedonia", "Европа", 350),
    "AL": ("albania", "Албания", "Albania", "Европа", 360),
    "BA": ("bosnia", "Босния и Герцеговина", "Bosnia and Herzegovina", "Европа", 370),
    "XK": ("kosovo", "Косово", "Kosovo", "Европа", 380),
    "UA": ("ukraine", "Украина", "Ukraine", "Европа", 390),
    "MD": ("moldova", "Молдова", "Moldova", "Европа", 400),
    "GE": ("georgia", "Грузия", "Georgia", "Европа", 410),
    "AM": ("armenia", "Армения", "Armenia", "Европа", 420),
    "AZ": ("azerbaijan", "Азербайджан", "Azerbaijan", "Европа", 430),
    "US": ("united-states", "США", "United States", "Америка", 500),
    "CA": ("canada", "Канада", "Canada", "Америка", 510),
    "JP": ("japan", "Япония", "Japan", "Азия", 600),
    "KR": ("south-korea", "Южная Корея", "South Korea", "Азия", 610),
    "CN": ("china", "Китай", "China", "Азия", 620),
    "IN": ("india", "Индия", "India", "Азия", 630),
    "BR": ("brazil", "Бразилия", "Brazil", "Америка", 640),
    "MX": ("mexico", "Мексика", "Mexico", "Америка", 650),
    "AU": ("australia", "Австралия", "Australia", "Океания", 700),
    "NZ": ("new-zealand", "Новая Зеландия", "New Zealand", "Океания", 710),
    "ZA": ("south-africa", "ЮАР", "South Africa", "Африка", 800),
    "IL": ("israel", "Израиль", "Israel", "Азия", 810),
    # Россия намеренно отсутствует — см. EXCLUDED_GEO_CODES.
}


def _cache_dir() -> Path:
    candidates = [
        Path(__file__).resolve().parents[2] / ".cache" / "eurostat",
        Path("/tmp/eurostat-cache"),
    ]
    for p in candidates:
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except OSError:
            continue
    return Path("/tmp")


def _cache_path(url: str) -> Path:
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return _cache_dir() / f"{h}.json"


def http_get_json(url: str, *, use_cache: bool = True, session: requests.Session | None = None) -> dict:
    """GET JSON with disk cache, retries, backoff. Raises on persistent failure."""
    cp = _cache_path(url)
    if use_cache and cp.exists() and cp.stat().st_size > 10:
        try:
            return json.loads(cp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    sess = session or requests.Session()
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = sess.get(url, timeout=HTTP_TIMEOUT)
            if resp.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"HTTP {resp.status_code}", response=resp)
            resp.raise_for_status()
            data = resp.json()
            if use_cache:
                try:
                    cp.write_text(json.dumps(data), encoding="utf-8")
                except OSError:
                    pass
            return data
        except Exception as exc:  # noqa: BLE001 — retries wrap all transport errors
            last_err = exc
            sleep = min(2 ** attempt * 1.5, 30)
            logger.warning("Eurostat GET failed (%s) attempt %d: %s", url[:80], attempt + 1, exc)
            time.sleep(sleep)
    raise RuntimeError(f"Eurostat GET failed after retries: {url}") from last_err


def parse_period(period: str) -> date:
    """Normalize Eurostat TIME_PERIOD labels to first day of the period."""
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
    raise ValueError(f"unsupported period label: {period!r}")


def _priority_for_dim(dim: str, *, dataset_id: str | None = None) -> list[str]:
    from app.data.eurostat_headline import headline_priority_for

    override = headline_priority_for(dataset_id, dim)
    if override is not None:
        return override
    d = dim.lower()
    if d in HEADLINE_PRIORITY:
        return HEADLINE_PRIORITY[d]
    if d.startswith("indic"):
        return HEADLINE_PRIORITY.get("indic", [])
    return HEADLINE_PRIORITY.get(d, [])


def pick_headline_member(
    dim: str,
    members: list[str],
    *,
    dataset_id: str | None = None,
) -> str | None:
    """Select the most aggregated / default member for ``dim``."""
    if not members:
        return None
    if dim.lower() in _SKIP_DIMS:
        return None
    priority = _priority_for_dim(dim, dataset_id=dataset_id)
    upper_map = {m.upper(): m for m in members}
    for code in priority:
        if code.upper() in upper_map:
            return upper_map[code.upper()]
    for fallback in ("TOTAL", "TOT", "T", "ALL"):
        if fallback in upper_map:
            return upper_map[fallback]
    return members[0]


def extract_dimensions(payload: dict) -> dict[str, list[str]]:
    """dimension_id → ordered member codes from a JSON-stat payload."""
    dims: dict[str, list[str]] = {}
    dimension = payload.get("dimension") or {}
    ids = payload.get("id") or list(dimension.keys())
    for dim_id in ids:
        cat = (dimension.get(dim_id) or {}).get("category") or {}
        index = cat.get("index") or {}
        if isinstance(index, dict):
            ordered = sorted(index.items(), key=lambda kv: kv[1])
            dims[dim_id] = [k for k, _ in ordered]
        elif isinstance(index, list):
            dims[dim_id] = list(index)
        else:
            dims[dim_id] = list((cat.get("label") or {}).keys())
    return dims


def choose_headline_slice(
    dims: dict[str, list[str]],
    *,
    dataset_id: str | None = None,
) -> dict[str, str]:
    """Pin every dim except geo/time to a headline member."""
    slice_: dict[str, str] = {}
    for dim, members in dims.items():
        if dim.lower() in _SKIP_DIMS:
            continue
        picked = pick_headline_member(dim, members, dataset_id=dataset_id)
        if picked is not None:
            slice_[dim] = picked
    return slice_


def slice_hash(slice_: dict[str, str]) -> str:
    canonical = json.dumps(slice_, sort_keys=True, ensure_ascii=True)
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest()


def make_indicator_code(country: str, dataset_id: str, slice_: dict[str, str]) -> str:
    parts = [country.lower(), dataset_id.lower()]
    for key in sorted(slice_):
        if key.lower() in _SKIP_DIMS or key.lower() == "freq":
            continue
        parts.append(str(slice_[key]).lower().replace("_", "-"))
    code = "-".join(parts)
    if len(code) <= 120:
        return code
    h = hashlib.sha1(code.encode()).hexdigest()[:8]
    return f"{code[:111]}-{h}"


def build_data_url(dataset_id: str, slice_: dict[str, str], *, last_time_period: int | None = None) -> str:
    params: dict[str, Any] = {"format": "JSON", "lang": "en"}
    for k, v in slice_.items():
        if k.lower() in _SKIP_DIMS:
            continue
        params[k] = v
    if last_time_period is not None:
        params["lastTimePeriod"] = last_time_period
    return f"{BASE_STATS}/{dataset_id}?{urlencode(params)}"


@dataclass
class CountrySeries:
    geo: str
    points: list[tuple[date, float]] = field(default_factory=list)


@dataclass
class DatasetParseResult:
    dataset_id: str
    title_en: str
    frequency: str
    slice_: dict[str, str]
    slice_hash: str
    unit: str
    series_by_geo: dict[str, list[tuple[date, float]]]
    source_url: str
    unit_label_en: str = ""


def parse_jsonstat_values(
    payload: dict,
) -> tuple[dict[str, list[tuple[date, float]]], str, str]:
    """Parse JSON-stat → (series, unit_code, unit_label_en)."""
    ids: list[str] = list(payload.get("id") or [])
    sizes: list[int] = list(payload.get("size") or [])
    dimension = payload.get("dimension") or {}
    values = payload.get("value") or {}

    if "geo" not in ids or "time" not in ids:
        raise ValueError(f"JSON-stat missing geo/time dims: {ids}")

    geo_idx = ids.index("geo")
    time_idx = ids.index("time")

    def members(dim: str) -> list[str]:
        index = ((dimension.get(dim) or {}).get("category") or {}).get("index") or {}
        if isinstance(index, dict):
            return [k for k, _ in sorted(index.items(), key=lambda kv: kv[1])]
        return list(index)

    def label_of(dim: str, code: str) -> str:
        lab = ((dimension.get(dim) or {}).get("category") or {}).get("label") or {}
        return str(lab.get(code) or "")

    geo_members = members("geo")
    time_members = members("time")

    unit = ""
    unit_label_en = ""
    if "unit" in ids:
        um = members("unit")
        if um:
            unit = um[0]
            unit_label_en = label_of("unit", unit)

    # strides for row-major index → multi-index
    strides = [1] * len(sizes)
    for i in range(len(sizes) - 2, -1, -1):
        strides[i] = strides[i + 1] * sizes[i + 1]

    series: dict[str, list[tuple[date, float]]] = {g: [] for g in geo_members}

    def decode_index(flat: int) -> list[int]:
        coords = [0] * len(sizes)
        rem = flat
        for i, stride in enumerate(strides):
            coords[i] = rem // stride
            rem = rem % stride
        return coords

    if isinstance(values, dict):
        items = values.items()
    else:
        items = ((str(i), v) for i, v in enumerate(values) if v is not None)

    for key, raw in items:
        if raw is None:
            continue
        try:
            flat = int(key)
            val = float(raw)
        except (TypeError, ValueError):
            continue
        coords = decode_index(flat)
        geo = geo_members[coords[geo_idx]]
        period = time_members[coords[time_idx]]
        try:
            dt = parse_period(period)
        except ValueError:
            continue
        series.setdefault(geo, []).append((dt, val))

    for geo, pts in series.items():
        pts.sort(key=lambda p: p[0])
        # dedupe by date keeping last
        dedup: dict[date, float] = {}
        for d, v in pts:
            dedup[d] = v
        series[geo] = sorted(dedup.items())

    return series, unit, unit_label_en


def fetch_dataset_structure(dataset_id: str, session: requests.Session | None = None) -> dict[str, list[str]]:
    url = build_data_url(dataset_id, {}, last_time_period=1)
    payload = http_get_json(url, session=session)
    return extract_dimensions(payload)


def fetch_and_parse_dataset(
    dataset_id: str,
    *,
    catalog_freq: str | None = None,
    session: requests.Session | None = None,
    use_cache: bool = True,
    forced_slice: dict[str, str] | None = None,
) -> DatasetParseResult:
    """Full pipeline for one dataset: structure → headline slice → data → series.

    ``forced_slice`` — явный срез (для догрузки глубоких age/unit вариантов
    вместо единственного headline TOTAL).
    """
    sess = session or requests.Session()
    dims = fetch_dataset_structure(dataset_id, session=sess)
    slice_ = (
        dict(forced_slice)
        if forced_slice
        else choose_headline_slice(dims, dataset_id=dataset_id)
    )

    # Prefer catalog frequency if freq dim absent / mismatched
    freq_code = (slice_.get("freq") or catalog_freq or "M").upper()
    if "freq" in dims and freq_code in {m.upper() for m in dims["freq"]}:
        # keep exact casing from members
        for m in dims["freq"]:
            if m.upper() == freq_code:
                slice_["freq"] = m
                break
    frequency = FREQ_MAP.get(freq_code, "monthly")

    url = build_data_url(dataset_id, slice_)
    payload = http_get_json(url, use_cache=use_cache, session=sess)
    title_en = payload.get("label") or dataset_id
    series, unit, unit_label_en = parse_jsonstat_values(payload)
    if not unit and "unit" in slice_:
        unit = slice_["unit"]
        if not unit_label_en:
            # метка может быть в probe-payload структуры
            unit_label_en = (
                ((payload.get("dimension") or {}).get("unit") or {})
                .get("category", {})
                .get("label", {})
                .get(unit, "")
            )

    # Filter geos + min points
    filtered: dict[str, list[tuple[date, float]]] = {}
    for geo, pts in series.items():
        if geo in EXCLUDED_GEO_CODES or geo not in WORLD_COUNTRIES:
            continue
        if len(pts) < MIN_POINTS:
            continue
        filtered[geo] = pts

    return DatasetParseResult(
        dataset_id=dataset_id,
        title_en=title_en,
        frequency=frequency,
        slice_=slice_,
        slice_hash=slice_hash(slice_),
        unit=unit,
        series_by_geo=filtered,
        source_url=f"https://ec.europa.eu/eurostat/databrowser/view/{dataset_id}/default/table",
        unit_label_en=unit_label_en or "",
    )


def fetch_deep_slices(
    dataset_id: str,
    *,
    session: requests.Session | None = None,
    use_cache: bool = True,
) -> list[DatasetParseResult]:
    """Загрузить все срезы из DEEP_DATASET_SLICES (или один headline)."""
    from app.data.eurostat_listing import DEEP_DATASET_SLICES

    specs = DEEP_DATASET_SLICES.get(dataset_id.lower())
    if not specs:
        return [
            fetch_and_parse_dataset(
                dataset_id, session=session, use_cache=use_cache
            )
        ]
    out: list[DatasetParseResult] = []
    for spec in specs:
        try:
            out.append(
                fetch_and_parse_dataset(
                    dataset_id,
                    catalog_freq=spec.get("freq"),
                    session=session,
                    use_cache=use_cache,
                    forced_slice=spec,
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("deep slice %s %s failed: %s", dataset_id, spec, exc)
    return out

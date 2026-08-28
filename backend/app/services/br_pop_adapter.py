"""IBGE population adapter (SIDRA API) for the world data plane.

Official-first source (ADR-0012): Instituto Brasileiro de Geografia e
Estatística (IBGE). Wire format stays inside this module; product layers see
``WorldSourceAdapter`` only.

Verified live 2026-08-27:

- The v1 JSON API (``https://servicodados.ibge.gov.br/api/v1/populacao``)
  answered HTTP 503 on every probe — not usable.
- The SIDRA values API (``https://apisidra.ibge.gov.br/values/t/...``) is
  the stable public endpoint. Response: JSON array, first element is the
  header row (dimension code → label), every following element is one
  observation with ``V`` (value), ``D3C`` (year) and ``MC=45 / MN=Pessoas``.
- Series composition (two official IBGE series, stitched):
    * Table 6579 "População residente estimada", variable 9324 — annual
      resident population **estimates**, 2001–2025. Gaps: 2007, 2010, 2022,
      2023 — in census years IBGE suspends the estimates series and the
      census result becomes the published figure.
    * Table 1209 "População residente, censos", variable 606 — census
      **counts**: 1872…2022. Since 1980 censuses are decennial (1991, 2000,
      2010, 2022); pre-1980 points are irregular and not used (demographic
      methodology changes pre-1970 make them incomparable with the modern
      series).
  Census years that the estimates table skips (2022, 2023 — the estimates
  series resumes in 2024) come from the census table, so the merged series
  has no holes from 1980 onwards. The 2022 census count is the
  methodologically official figure for that year.
- Unit: persons (July 1 reference date for estimates, census reference
  date for counts). No scaling.

Public fields must not mention tables, variables or API paths.
Attribution: «Бразильский институт географии и статистики (IBGE)» (RU) /
"IBGE" (EN) — names reused verbatim from ``world_country_population.py``.
Observation-year policy: population is a stock; every published year is a
closed observation, no extra cut-off on top of the source.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from typing import Any, AsyncIterator, Mapping, Sequence

import httpx

from app.services.world_source_adapter import (
    WorldDatasetVersion,
    WorldObservation,
    WorldSeriesPayload,
    WorldSeriesRef,
)

PROVIDER = "ibge"
DATASET_ID = "sidra_pop"
PUBLIC_SOURCE_NAME = "Бразильский институт географии и статистики (IBGE)"
PUBLIC_SOURCE_NAME_EN = "IBGE"
PUBLIC_SOURCE_URL = (
    "https://www.ibge.gov.br/estatisticas/sociais/populacao/"
    "9103-estimativas-de-populacao.html"
)
PUBLIC_UNIT = "PERSONS"
PUBLIC_UNIT_RU = "человек"

SIDRA_BASE = "https://apisidra.ibge.gov.br/values"
# Таблица 6579, переменная 9324: годовые оценки численности населения.
ESTIMATES_URL = f"{SIDRA_BASE}/t/6579/n1/all/v/9324/p/all"
# Таблица 1209, переменная 606: итоги переписей населения.
CENSUS_URL = f"{SIDRA_BASE}/t/1209/n1/all/v/606/p/all"

# Переписи с 1980: десятилетние точки, сопоставимые с современным рядом.
_CENSUS_MIN_YEAR = 1980

_UA = "ForecastEconomy/1.0 (+https://forecasteconomy.com)"

SERIES_CODE = "br-population-ibge"


def make_ibge_series_ref() -> WorldSeriesRef:
    return WorldSeriesRef(
        provider=PROVIDER,
        dataset_id=DATASET_ID,
        series_id=SERIES_CODE,
        country_code="BR",
        frequency="annual",
        unit_code=PUBLIC_UNIT,
        dimensions={"series": SERIES_CODE},
        title="Brazil resident population",
        source_url=PUBLIC_SOURCE_URL,
    )


def _year_from(raw: Any) -> int | None:
    text = str(raw or "").strip()
    if len(text) != 4 or not text.isdigit():
        return None
    year = int(text)
    if 1900 <= year <= 2100:
        return year
    return None


def _value_from(raw: Any) -> float | None:
    text = str(raw or "").strip().replace(",", "")
    if not text or text in {"-", "..."}:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    return value if value > 0 else None


def _points_from_rows(rows: Sequence[Mapping[str, Any]]) -> dict[int, float]:
    points: dict[int, float] = {}
    for row in rows[1:]:  # первая строка — заголовок словаря
        year = _year_from(row.get("D3C"))
        value = _value_from(row.get("V"))
        if year is None or value is None:
            continue
        points[year] = value
    return points


def parse_ibge_sidra_population(
    estimates_payload: Sequence[Mapping[str, Any]] | str,
    census_payload: Sequence[Mapping[str, Any]] | str,
    *,
    today: date | None = None,
) -> dict[date, float]:
    """Чистый разбор SIDRA-ответов → {1 января года: человек}.

    Оценки (6579) дают базовый ряд; переписи (1209, с 1980) дозаполняют
    годы, которых в оценках нет (2022, 2023 в год переписи), и перекрывают
    оценку в самом переписном году (перепись — официальный итог).
    """
    def _rows(payload) -> list[Mapping[str, Any]]:
        if isinstance(payload, str):
            decoded = json.loads(payload)
        else:
            decoded = payload
        if isinstance(decoded, Mapping):
            decoded = decoded.get("values") or []
        return [row for row in decoded if isinstance(row, Mapping)]

    estimates = _points_from_rows(_rows(estimates_payload))
    census = _points_from_rows(_rows(census_payload))
    merged = dict(estimates)
    for year, value in census.items():
        if year >= _CENSUS_MIN_YEAR:
            merged[year] = value
    return {date(year, 1, 1): value for year, value in sorted(merged.items())}


def _payload_hash(estimates: str, census: str) -> str:
    raw = json.dumps([estimates, census], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _fetch_sidra_json(url: str) -> str:
    with httpx.Client(
        timeout=60.0,
        headers={"User-Agent": _UA, "Accept": "application/json"},
        follow_redirects=True,
    ) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text


class IbgePopAdapter:
    """WorldSourceAdapter for IBGE resident population (SIDRA)."""

    provider = PROVIDER
    public_source_name = PUBLIC_SOURCE_NAME

    def __init__(
        self,
        *,
        fetch_json=None,
        estimates_url: str | None = None,
        census_url: str | None = None,
    ) -> None:
        self._fetch_json = fetch_json or _fetch_sidra_json
        self._estimates_url = estimates_url or ESTIMATES_URL
        self._census_url = census_url or CENSUS_URL

    async def list_datasets(self) -> AsyncIterator[WorldDatasetVersion]:
        yield WorldDatasetVersion(
            provider=PROVIDER,
            dataset_id=DATASET_ID,
            title="Resident population estimates and census counts",
            metadata_url=PUBLIC_SOURCE_URL,
        )

    async def list_series(
        self,
        dataset: WorldDatasetVersion | None,
    ) -> AsyncIterator[WorldSeriesRef]:
        if dataset is not None and dataset.dataset_id != DATASET_ID:
            return
        yield make_ibge_series_ref()

    async def fetch_series(
        self,
        series: WorldSeriesRef,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> WorldSeriesPayload:
        estimates = self._fetch_json(self._estimates_url)
        census = self._fetch_json(self._census_url)
        fetched_at = datetime.now(timezone.utc).replace(tzinfo=None)
        points = parse_ibge_sidra_population(estimates, census)
        observations = [
            WorldObservation(period=period, value=value)
            for period, value in points.items()
            if (date_from is None or period >= date_from)
            and (date_to is None or period <= date_to)
        ]
        return WorldSeriesPayload(
            ref=series,
            observations=observations,
            fetched_at=fetched_at,
            source_hash=_payload_hash(estimates, census),
        )

    def fetch_national_points(self) -> list[tuple[date, float]]:
        """Все национальные годовые точки (оценки + переписи) — для ingest."""
        estimates = self._fetch_json(self._estimates_url)
        census = self._fetch_json(self._census_url)
        return list(parse_ibge_sidra_population(estimates, census).items())

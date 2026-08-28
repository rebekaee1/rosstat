"""Banco de México SIE REST API adapter.

Official JSON API (token required)::

    GET https://www.banxico.org.mx/SieAPIRest/service/v1/series/{ids}/datos/oportuno
    GET …/series/{ids}/datos/{yyyy-MM-dd}/{yyyy-MM-dd}
    Header: Bmx-Token: <64-char token>
    Or query: ?token=<token>

Token: https://www.banxico.org.mx/SieAPIRest/service/v1/token
Configure via ``RUSTATS_BANXICO_API_TOKEN`` / ``Settings.banxico_api_token``.

Curated national-core series (catalog / Banxico docs; live network may be
blocked from some egress paths):

- ``SP1`` — INPC (consumer price index, monthly)
- ``SL1`` — open unemployment rate (urban)
- ``SR16620`` — real GDP at market prices (quarterly; INEGI via Banxico)
- ``SF61745`` — target policy rate
- ``SF43718`` — USD/MXN FIX
- ``SF60648`` — TIIE 28 days
- ``SF43707`` — international reserves

``WorldSeriesRef.dataset_id`` equals the SIE series id. Country code ``MX``.
Observation dates arrive as ``DD/MM/YYYY``; missing cells use ``N/E``.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, AsyncIterator, Mapping, Sequence

import requests

from app.services.world_source_adapter import (
    WorldDatasetVersion,
    WorldObservation,
    WorldSeriesPayload,
    WorldSeriesRef,
)

logger = logging.getLogger(__name__)

SIE_BASE = "https://www.banxico.org.mx/SieAPIRest/service/v1"
# Banxico egress from some networks is slow / intermittent; prefer a long
# connect+read budget over fail-closed on the first TCP stall.
DEFAULT_TIMEOUT_SEC = 180
DEFAULT_COUNTRY_CODE = "MX"
_DEFAULT_DATE_FROM = date(1960, 1, 1)
_MISSING = {"", "n/e", "n/d", "na", "nd", "."}


class BanxicoSieError(RuntimeError):
    """Raised when SIE returns an error body or an unusable payload."""


@dataclass(frozen=True)
class BanxicoSeriesSpec:
    """Curated SIE series. ``dataset_id`` defaults to the SIE id."""

    series_id: str
    dataset_id: str | None = None
    title: str | None = None
    unit_code: str = "UNIT"
    frequency: str = "monthly"
    dimensions: Mapping[str, str] = field(default_factory=dict)
    source_url: str | None = None


DEFAULT_BANXICO_SERIES: tuple[BanxicoSeriesSpec, ...] = (
    BanxicoSeriesSpec(
        series_id="SP1",
        title="INPC — índice de precios al consumidor",
        unit_code="INDEX",
        frequency="monthly",
    ),
    BanxicoSeriesSpec(
        series_id="SL1",
        title="Tasa de desocupación abierta (áreas urbanas)",
        unit_code="PERCENT",
        frequency="monthly",
    ),
    BanxicoSeriesSpec(
        series_id="SR17493",
        title="PIB a precios de mercado (constantes, base 2018)",
        unit_code="MXN_MN",
        frequency="quarterly",
    ),
    BanxicoSeriesSpec(
        series_id="SF61745",
        title="Tasa objetivo",
        unit_code="PERCENT",
        frequency="daily",
    ),
    BanxicoSeriesSpec(
        series_id="SF43718",
        title="USD/MXN FIX",
        unit_code="MXN",
        frequency="daily",
        dimensions={"quote": "USD", "base": "MXN"},
    ),
    BanxicoSeriesSpec(
        series_id="SF60648",
        title="TIIE a 28 días",
        unit_code="PERCENT",
        frequency="daily",
    ),
    BanxicoSeriesSpec(
        series_id="SF43707",
        title="Reservas internacionales",
        unit_code="USD_MN",
        frequency="weekly",
    ),
)


def normalize_series_id(raw: str) -> str:
    text = (raw or "").strip().upper()
    if not text:
        raise BanxicoSieError("Empty Banxico SIE series id")
    return text


def normalize_dataset_id(raw: str | None, *, series_id: str) -> str:
    text = (raw or "").strip().upper()
    return text or series_id


def resolve_token(explicit: str | None = None) -> str:
    if explicit is not None and explicit.strip():
        return explicit.strip()
    for key in (
        "RUSTATS_BANXICO_API_TOKEN",
        "BANXICO_API_TOKEN",
        "BMX_TOKEN",
    ):
        value = (os.environ.get(key) or "").strip()
        if value:
            return value
    try:
        from app.config import settings

        token = (getattr(settings, "banxico_api_token", None) or "").strip()
        if token:
            return token
    except Exception:  # noqa: BLE001 — settings optional in unit tests
        pass
    return ""


def observations_oportuno_url(series_id: str, *, base_url: str = SIE_BASE) -> str:
    sid = normalize_series_id(series_id)
    return f"{base_url.rstrip('/')}/series/{sid}/datos/oportuno"


def observations_range_url(
    series_id: str,
    start: date,
    end: date,
    *,
    base_url: str = SIE_BASE,
) -> str:
    sid = normalize_series_id(series_id)
    return (
        f"{base_url.rstrip('/')}/series/{sid}/datos/"
        f"{start.isoformat()}/{end.isoformat()}"
    )


def series_metadata_url(series_id: str, *, base_url: str = SIE_BASE) -> str:
    sid = normalize_series_id(series_id)
    return f"{base_url.rstrip('/')}/series/{sid}"


def parse_observation_date(raw: str) -> date:
    text = (raw or "").strip()
    if not text:
        raise BanxicoSieError("Empty SIE observation date")
    parts = text.split("/")
    if len(parts) == 3:
        day_s, month_s, year_s = parts
        try:
            return date(int(year_s), int(month_s), int(day_s))
        except ValueError as exc:
            raise BanxicoSieError(
                f"Unparseable SIE observation date: {raw!r}"
            ) from exc
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise BanxicoSieError(f"Unparseable SIE observation date: {raw!r}") from exc


def _extract_series_block(payload: Mapping[str, Any], series_id: str) -> Mapping[str, Any]:
    sid = normalize_series_id(series_id)
    root = payload.get("bmx")
    if not isinstance(root, Mapping):
        raise BanxicoSieError("SIE payload missing bmx object")
    series_list = root.get("series")
    if not isinstance(series_list, list) or not series_list:
        raise BanxicoSieError(f"SIE payload has no series for {sid}")
    for item in series_list:
        if not isinstance(item, Mapping):
            continue
        if normalize_series_id(str(item.get("idSerie") or "")) == sid:
            return item
    # Single-series responses sometimes omit matching id — take first.
    first = series_list[0]
    if isinstance(first, Mapping):
        return first
    raise BanxicoSieError(f"SIE series block unusable for {sid}")


def parse_sie_observations(
    payload: Mapping[str, Any],
    *,
    series_id: str,
) -> list[WorldObservation]:
    """Parse SIE ``bmx.series[].datos`` list."""
    block = _extract_series_block(payload, series_id)
    raw_datos = block.get("datos")
    if raw_datos is None:
        raise BanxicoSieError(
            f"SIE payload missing datos for {normalize_series_id(series_id)}"
        )
    if not isinstance(raw_datos, list):
        raise BanxicoSieError(
            f"SIE datos must be a list, got {type(raw_datos)!r}"
        )
    if not raw_datos:
        raise BanxicoSieError(
            f"SIE datos empty for {normalize_series_id(series_id)}"
        )

    observations: list[WorldObservation] = []
    for index, item in enumerate(raw_datos):
        if not isinstance(item, Mapping):
            raise BanxicoSieError(f"datos[{index}] is not an object")
        raw_value = item.get("dato")
        if raw_value is None:
            continue
        text = str(raw_value).strip()
        if text.lower() in _MISSING:
            continue
        text = text.replace(",", "")
        try:
            value = float(text)
        except ValueError as exc:
            raise BanxicoSieError(
                f"datos[{index}].dato non-numeric: {raw_value!r}"
            ) from exc
        period = parse_observation_date(str(item.get("fecha") or ""))
        observations.append(WorldObservation(period=period, value=value))

    if not observations:
        raise BanxicoSieError(
            f"SIE datos had no numeric values for {normalize_series_id(series_id)}"
        )
    observations.sort(key=lambda item: item.period)
    return observations


def _series_title(payload: Mapping[str, Any], series_id: str) -> str | None:
    try:
        block = _extract_series_block(payload, series_id)
    except BanxicoSieError:
        return None
    title = block.get("titulo")
    return str(title) if title else None


class BanxicoSieAdapter:
    """``WorldSourceAdapter`` for Banco de México SIE."""

    provider = "banxico_sie"
    public_source_name = "Banco de México"

    def __init__(
        self,
        series: Sequence[BanxicoSeriesSpec] | None = None,
        *,
        session: requests.Session | None = None,
        timeout: float = DEFAULT_TIMEOUT_SEC,
        base_url: str = SIE_BASE,
        country_code: str = DEFAULT_COUNTRY_CODE,
        token: str | None = None,
    ) -> None:
        curated = tuple(series) if series is not None else DEFAULT_BANXICO_SERIES
        if not curated:
            raise BanxicoSieError(
                "BanxicoSieAdapter requires at least one curated BanxicoSeriesSpec"
            )
        self._series = curated
        self._session = session or requests.Session()
        self._timeout = timeout
        self._base_url = base_url.rstrip("/")
        self._country_code = country_code.strip().upper() or DEFAULT_COUNTRY_CODE
        self._token = resolve_token(token)
        self._by_dataset: dict[str, BanxicoSeriesSpec] = {}
        self._by_series_id: dict[str, BanxicoSeriesSpec] = {}
        for spec in self._series:
            sid = normalize_series_id(spec.series_id)
            did = normalize_dataset_id(spec.dataset_id, series_id=sid)
            normalized = BanxicoSeriesSpec(
                series_id=sid,
                dataset_id=did,
                title=spec.title,
                unit_code=(spec.unit_code or "UNIT").strip().upper() or "UNIT",
                frequency=(spec.frequency or "monthly").strip().lower() or "monthly",
                dimensions=dict(spec.dimensions),
                source_url=spec.source_url,
            )
            self._by_dataset[did] = normalized
            self._by_series_id[sid] = normalized

    async def list_datasets(self) -> AsyncIterator[WorldDatasetVersion]:
        for dataset_id, spec in self._by_dataset.items():
            yield WorldDatasetVersion(
                provider=self.provider,
                dataset_id=dataset_id,
                title=spec.title,
                metadata_url=series_metadata_url(
                    spec.series_id, base_url=self._base_url
                ),
            )

    async def list_series(
        self, dataset: WorldDatasetVersion
    ) -> AsyncIterator[WorldSeriesRef]:
        dataset_id = normalize_dataset_id(dataset.dataset_id, series_id="")
        spec = self._by_dataset.get(dataset_id)
        if spec is None:
            # Allow lookup by raw series id casing.
            spec = self._by_series_id.get(normalize_series_id(dataset.dataset_id or ""))
        if spec is None:
            raise BanxicoSieError(
                f"No curated SIE series for dataset_id={dataset.dataset_id!r}"
            )
        yield self._series_ref(spec)

    async def fetch_series(
        self,
        series: WorldSeriesRef,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> WorldSeriesPayload:
        if series.provider != self.provider:
            raise BanxicoSieError(
                f"Provider mismatch: expected {self.provider}, got {series.provider}"
            )
        if not self._token:
            raise BanxicoSieError(
                "Banxico SIE requires RUSTATS_BANXICO_API_TOKEN (Bmx-Token)"
            )
        series_id = normalize_series_id(series.series_id)
        fetched_at = datetime.now(timezone.utc)

        if date_from is not None or date_to is not None:
            start = date_from or _DEFAULT_DATE_FROM
            end = date_to or date.today()
            if end < start:
                raise BanxicoSieError(
                    f"date_to {end.isoformat()} is before date_from {start.isoformat()}"
                )
            payload = await asyncio.to_thread(
                self._get_observations_sync,
                series_id,
                start_date=start,
                end_date=end,
            )
        else:
            # Full history window — SIE has no ``recent=N``; use wide range.
            payload = await asyncio.to_thread(
                self._get_observations_sync,
                series_id,
                start_date=_DEFAULT_DATE_FROM,
                end_date=date.today(),
            )

        observations = parse_sie_observations(payload, series_id=series_id)
        title = _series_title(payload, series_id)
        revision = (
            f"{observations[0].period.isoformat()}"
            f"/{observations[-1].period.isoformat()}"
            f"#{len(observations)}"
        )
        source_hash = hashlib.sha256(
            json.dumps(
                {
                    "series": series_id,
                    "n": len(observations),
                    "first": observations[0].period.isoformat(),
                    "last": observations[-1].period.isoformat(),
                    "last_value": observations[-1].value,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

        ref = series
        if title and not series.title:
            ref = WorldSeriesRef(
                provider=series.provider,
                dataset_id=series.dataset_id,
                series_id=series.series_id,
                country_code=series.country_code,
                frequency=series.frequency,
                unit_code=series.unit_code,
                dimensions=dict(series.dimensions),
                title=title,
                source_url=series.source_url
                or observations_oportuno_url(series_id, base_url=self._base_url),
            )

        return WorldSeriesPayload(
            ref=ref,
            observations=observations,
            fetched_at=fetched_at,
            revision_token=revision,
            source_hash=source_hash,
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Bmx-Token": self._token,
        }

    def _get_json(self, url: str, *, params: Mapping[str, str] | None = None) -> Any:
        # Token only via Bmx-Token header — never put it in the query string
        # (URL with ?token= leaks into logs / exception messages).
        query = dict(params or {})
        query.pop("token", None)
        try:
            response = self._session.get(
                url,
                params=query or None,
                timeout=self._timeout,
                headers=self._headers(),
            )
        except requests.RequestException as exc:
            raise BanxicoSieError(f"SIE GET {url} failed: {exc}") from exc
        if response.status_code >= 400:
            raise BanxicoSieError(
                f"SIE GET {url} HTTP {response.status_code}: {response.text[:300]}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise BanxicoSieError(
                f"SIE GET {url} returned non-JSON: {response.text[:300]}"
            ) from exc
        if isinstance(payload, Mapping) and payload.get("error"):
            raise BanxicoSieError(f"SIE error: {payload.get('error')}")
        return payload

    def _get_observations_sync(
        self,
        series_id: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        if start_date is not None and end_date is not None:
            url = observations_range_url(
                series_id, start_date, end_date, base_url=self._base_url
            )
        else:
            url = observations_oportuno_url(series_id, base_url=self._base_url)
        payload = self._get_json(url)
        if not isinstance(payload, dict):
            raise BanxicoSieError(
                f"SIE observations payload must be an object, got {type(payload)!r}"
            )
        return payload

    def _series_ref(self, spec: BanxicoSeriesSpec) -> WorldSeriesRef:
        sid = normalize_series_id(spec.series_id)
        did = normalize_dataset_id(spec.dataset_id, series_id=sid)
        return WorldSeriesRef(
            provider=self.provider,
            dataset_id=did,
            series_id=sid,
            country_code=self._country_code,
            frequency=(spec.frequency or "monthly").strip().lower() or "monthly",
            unit_code=(spec.unit_code or "UNIT").strip().upper() or "UNIT",
            dimensions=dict(spec.dimensions),
            title=spec.title,
            source_url=spec.source_url
            or observations_oportuno_url(sid, base_url=self._base_url),
        )


def create_adapter(
    series_specs: Sequence[Any] | None = None,
) -> BanxicoSieAdapter:
    """Factory for ``world_national_ingest.resolve_adapter``."""
    if not series_specs:
        return BanxicoSieAdapter()
    curated: list[BanxicoSeriesSpec] = []
    for row in series_specs:
        if isinstance(row, BanxicoSeriesSpec):
            curated.append(row)
            continue
        provider = getattr(row, "provider", None) or (
            row.get("provider") if isinstance(row, Mapping) else None
        )
        if provider is not None and str(provider).strip().lower() not in {
            "banxico_sie",
            "banxico",
        }:
            continue
        series_id = getattr(row, "series_id", None) or (
            row.get("series_id") if isinstance(row, Mapping) else None
        )
        if not series_id:
            continue
        dataset_id = getattr(row, "dataset_id", None) or (
            row.get("dataset_id") if isinstance(row, Mapping) else None
        )
        curated.append(
            BanxicoSeriesSpec(
                series_id=str(series_id),
                dataset_id=str(dataset_id) if dataset_id else None,
                title=getattr(row, "name_en", None)
                or getattr(row, "name_ru", None)
                or (row.get("name_en") if isinstance(row, Mapping) else None),
                unit_code=str(
                    getattr(row, "unit", None)
                    or (row.get("unit") if isinstance(row, Mapping) else None)
                    or "UNIT"
                ),
                frequency=str(
                    getattr(row, "frequency", None)
                    or (row.get("frequency") if isinstance(row, Mapping) else None)
                    or "monthly"
                ),
                dimensions=dict(
                    getattr(row, "dimensions", None)
                    or (row.get("dimensions") if isinstance(row, Mapping) else None)
                    or {}
                ),
                source_url=getattr(row, "source_url", None)
                or (row.get("source_url") if isinstance(row, Mapping) else None),
            )
        )
    return BanxicoSieAdapter(curated or None)

"""Bank of Canada Valet API adapter.

Official JSON API: ``https://www.bankofcanada.ca/valet/…``
(docs: https://www.bankofcanada.ca/valet/docs).

Observations endpoint::

    GET /valet/observations/{seriesName}/json
        ?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
        | ?recent=N

Confirmed live series used by the Canada national-core passport:

- ``V39079`` — target for the overnight rate (business daily)
- ``FXUSDCAD`` — USD/CAD daily average exchange rate

``WorldSeriesRef.dataset_id`` may be a Valet series group name
(e.g. ``FX_RATES_DAILY``) or the series id itself when the series is
published standalone. ``series_id`` is always the Valet series name.
Country code is always ``CA`` for these series. Business-daily FX and
policy rates map to platform frequency ``daily``.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
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

VALET_BASE = "https://www.bankofcanada.ca/valet"
DEFAULT_TIMEOUT_SEC = 60
DEFAULT_RECENT_N = 10_000
DEFAULT_COUNTRY_CODE = "CA"
_DEFAULT_DATE_FROM = date(1900, 1, 1)


class BocValetError(RuntimeError):
    """Raised when Valet returns an error body or an unusable payload."""


@dataclass(frozen=True)
class BocSeriesSpec:
    """Curated Valet series. ``dataset_id`` may equal ``series_id`` or a group."""

    series_id: str
    dataset_id: str | None = None
    title: str | None = None
    unit_code: str = "UNIT"
    frequency: str = "daily"
    dimensions: Mapping[str, str] = field(default_factory=dict)
    source_url: str | None = None


# Confirmed live passport series (business daily → platform ``daily``).
DEFAULT_BOC_SERIES: tuple[BocSeriesSpec, ...] = (
    BocSeriesSpec(
        series_id="V39079",
        dataset_id="V39079",
        title="Target for the overnight rate",
        unit_code="PERCENT",
        frequency="daily",
    ),
    BocSeriesSpec(
        series_id="FXUSDCAD",
        dataset_id="FX_RATES_DAILY",
        title="USD/CAD",
        unit_code="CAD",
        frequency="daily",
        dimensions={"quote": "USD", "base": "CAD"},
    ),
)


def normalize_series_id(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise BocValetError("Empty Valet series id")
    return text


def normalize_dataset_id(raw: str | None, *, series_id: str) -> str:
    text = (raw or "").strip()
    return text or series_id


def observations_url(series_id: str, *, base_url: str = VALET_BASE) -> str:
    return f"{base_url.rstrip('/')}/observations/{normalize_series_id(series_id)}/json"


def series_metadata_url(series_id: str, *, base_url: str = VALET_BASE) -> str:
    return f"{base_url.rstrip('/')}/series/{normalize_series_id(series_id)}"


def group_metadata_url(group_name: str, *, base_url: str = VALET_BASE) -> str:
    return f"{base_url.rstrip('/')}/groups/{group_name.strip()}/json"


def parse_observation_date(raw: str) -> date:
    text = (raw or "").strip()
    if not text:
        raise BocValetError("Empty observation date")
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise BocValetError(f"Unparseable Valet observation date: {raw!r}") from exc


def parse_valet_observations(
    payload: Mapping[str, Any],
    *,
    series_id: str,
) -> list[WorldObservation]:
    """Parse Valet ``observations`` list for one series.

    Each observation is ``{"d": "YYYY-MM-DD", "<SERIES>": {"v": "1.23"}}``.
    Missing / blank ``v`` cells are skipped (holiday gaps, unpublished days).
    """
    sid = normalize_series_id(series_id)
    raw_obs = payload.get("observations")
    if raw_obs is None:
        raise BocValetError(f"Valet payload missing observations for {sid}")
    if not isinstance(raw_obs, list):
        raise BocValetError(
            f"Valet observations must be a list, got {type(raw_obs)!r}"
        )
    if not raw_obs:
        raise BocValetError(f"Valet observations empty for {sid}")

    observations: list[WorldObservation] = []
    for index, item in enumerate(raw_obs):
        if not isinstance(item, Mapping):
            raise BocValetError(f"observations[{index}] is not an object")
        period = parse_observation_date(str(item.get("d") or ""))
        cell = item.get(sid)
        if cell is None:
            # Group observation payloads may include sibling series on the same day.
            continue
        if not isinstance(cell, Mapping):
            raise BocValetError(
                f"observations[{index}].{sid} must be an object, got {type(cell)!r}"
            )
        raw_value = cell.get("v")
        if raw_value is None or raw_value == "":
            continue
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise BocValetError(
                f"observations[{index}].{sid}.v non-numeric: {raw_value!r}"
            ) from exc
        observations.append(WorldObservation(period=period, value=value))

    if not observations:
        raise BocValetError(f"Valet observations had no numeric values for {sid}")
    observations.sort(key=lambda item: item.period)
    return observations


def _series_detail_title(payload: Mapping[str, Any], series_id: str) -> str | None:
    detail = payload.get("seriesDetail")
    if isinstance(detail, Mapping):
        entry = detail.get(series_id)
        if isinstance(entry, Mapping):
            label = entry.get("label")
            if label:
                return str(label)
    details = payload.get("seriesDetails")
    if isinstance(details, Mapping) and str(details.get("name") or "") == series_id:
        label = details.get("label")
        if label:
            return str(label)
    return None


class BocValetAdapter:
    """``WorldSourceAdapter`` for Bank of Canada Valet."""

    provider = "boc_valet"
    public_source_name = "Bank of Canada"

    def __init__(
        self,
        series: Sequence[BocSeriesSpec] | None = None,
        *,
        session: requests.Session | None = None,
        timeout: float = DEFAULT_TIMEOUT_SEC,
        base_url: str = VALET_BASE,
        recent_n: int = DEFAULT_RECENT_N,
        country_code: str = DEFAULT_COUNTRY_CODE,
        resolve_group_members: bool = False,
    ) -> None:
        curated = tuple(series) if series is not None else DEFAULT_BOC_SERIES
        if not curated:
            raise BocValetError(
                "BocValetAdapter requires at least one curated BocSeriesSpec"
            )
        self._series = curated
        self._session = session or requests.Session()
        self._timeout = timeout
        self._base_url = base_url.rstrip("/")
        self._recent_n = recent_n
        self._country_code = country_code.strip().upper() or DEFAULT_COUNTRY_CODE
        self._resolve_group_members = resolve_group_members
        self._by_dataset: dict[str, list[BocSeriesSpec]] = {}
        self._by_series_id: dict[str, BocSeriesSpec] = {}
        for spec in self._series:
            sid = normalize_series_id(spec.series_id)
            did = normalize_dataset_id(spec.dataset_id, series_id=sid)
            normalized = BocSeriesSpec(
                series_id=sid,
                dataset_id=did,
                title=spec.title,
                unit_code=(spec.unit_code or "UNIT").strip().upper() or "UNIT",
                frequency=(spec.frequency or "daily").strip().lower() or "daily",
                dimensions=dict(spec.dimensions),
                source_url=spec.source_url,
            )
            self._by_dataset.setdefault(did, []).append(normalized)
            self._by_series_id[sid] = normalized

    async def list_datasets(self) -> AsyncIterator[WorldDatasetVersion]:
        for dataset_id, members in self._by_dataset.items():
            title = members[0].title
            if len(members) > 1 and dataset_id != members[0].series_id:
                if self._resolve_group_members:
                    try:
                        meta = await asyncio.to_thread(
                            self._get_group_metadata_sync, dataset_id
                        )
                        gd = meta.get("groupDetails") or meta.get("groupDetail") or {}
                        if isinstance(gd, Mapping) and gd.get("label"):
                            title = str(gd["label"])
                    except BocValetError:
                        logger.debug(
                            "Valet group metadata unavailable for %s", dataset_id
                        )
            yield WorldDatasetVersion(
                provider=self.provider,
                dataset_id=dataset_id,
                title=title,
                metadata_url=(
                    group_metadata_url(dataset_id, base_url=self._base_url)
                    if dataset_id not in self._by_series_id
                    or dataset_id != members[0].series_id
                    else series_metadata_url(dataset_id, base_url=self._base_url)
                ),
            )

    async def list_series(
        self, dataset: WorldDatasetVersion
    ) -> AsyncIterator[WorldSeriesRef]:
        dataset_id = (dataset.dataset_id or "").strip()
        members = self._by_dataset.get(dataset_id)
        if members:
            for spec in members:
                yield self._series_ref(spec)
            return

        if self._resolve_group_members:
            meta = await asyncio.to_thread(self._get_group_metadata_sync, dataset_id)
            gd = meta.get("groupDetails") or meta.get("groupDetail") or {}
            group_series = gd.get("groupSeries") if isinstance(gd, Mapping) else None
            if isinstance(group_series, Mapping) and group_series:
                for sid, info in group_series.items():
                    label = None
                    if isinstance(info, Mapping):
                        label = info.get("label")
                    yield WorldSeriesRef(
                        provider=self.provider,
                        dataset_id=dataset_id,
                        series_id=normalize_series_id(str(sid)),
                        country_code=self._country_code,
                        frequency="daily",
                        unit_code="UNIT",
                        title=str(label) if label else None,
                        source_url=observations_url(
                            str(sid), base_url=self._base_url
                        ),
                    )
                return

        raise BocValetError(
            f"No curated Valet series for dataset_id={dataset_id!r}"
        )

    async def fetch_series(
        self,
        series: WorldSeriesRef,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> WorldSeriesPayload:
        if series.provider != self.provider:
            raise BocValetError(
                f"Provider mismatch: expected {self.provider}, got {series.provider}"
            )
        series_id = normalize_series_id(series.series_id)
        fetched_at = datetime.now(timezone.utc)

        if date_from is not None or date_to is not None:
            start = date_from or _DEFAULT_DATE_FROM
            end = date_to or date.today()
            if end < start:
                raise BocValetError(
                    f"date_to {end.isoformat()} is before date_from {start.isoformat()}"
                )
            payload = await asyncio.to_thread(
                self._get_observations_sync,
                series_id,
                start_date=start,
                end_date=end,
            )
        else:
            payload = await asyncio.to_thread(
                self._get_observations_sync,
                series_id,
                recent=self._recent_n,
            )

        observations = parse_valet_observations(payload, series_id=series_id)
        title = _series_detail_title(payload, series_id)
        revision = None
        if observations:
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
                or observations_url(series_id, base_url=self._base_url),
            )

        return WorldSeriesPayload(
            ref=ref,
            observations=observations,
            fetched_at=fetched_at,
            revision_token=revision,
            source_hash=source_hash,
        )

    # ------------------------------------------------------------------ sync HTTP

    def _get_json(self, url: str, *, params: Mapping[str, str] | None = None) -> Any:
        try:
            response = self._session.get(
                url,
                params=dict(params or {}),
                timeout=self._timeout,
                headers={"Accept": "application/json"},
            )
        except requests.RequestException as exc:
            raise BocValetError(f"Valet GET {url} failed: {exc}") from exc
        if response.status_code >= 400:
            raise BocValetError(
                f"Valet GET {url} HTTP {response.status_code}: {response.text[:300]}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise BocValetError(
                f"Valet GET {url} returned non-JSON: {response.text[:300]}"
            ) from exc
        if isinstance(payload, Mapping) and payload.get("message"):
            # Valet error shape: {"message": "...", "docs": "..."}.
            raise BocValetError(f"Valet error: {payload.get('message')}")
        return payload

    def _get_observations_sync(
        self,
        series_id: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        recent: int | None = None,
    ) -> dict[str, Any]:
        url = observations_url(series_id, base_url=self._base_url)
        params: dict[str, str] = {}
        if start_date is not None or end_date is not None:
            if start_date is not None:
                params["start_date"] = start_date.isoformat()
            if end_date is not None:
                params["end_date"] = end_date.isoformat()
        elif recent is not None:
            if recent <= 0:
                raise BocValetError(f"recent must be > 0, got {recent}")
            params["recent"] = str(int(recent))
        payload = self._get_json(url, params=params)
        if not isinstance(payload, dict):
            raise BocValetError(
                f"Valet observations payload must be an object, got {type(payload)!r}"
            )
        return payload

    def _get_group_metadata_sync(self, group_name: str) -> dict[str, Any]:
        url = group_metadata_url(group_name, base_url=self._base_url)
        payload = self._get_json(url)
        if not isinstance(payload, dict):
            raise BocValetError(
                f"Valet group payload must be an object, got {type(payload)!r}"
            )
        return payload

    def _series_ref(self, spec: BocSeriesSpec) -> WorldSeriesRef:
        sid = normalize_series_id(spec.series_id)
        did = normalize_dataset_id(spec.dataset_id, series_id=sid)
        return WorldSeriesRef(
            provider=self.provider,
            dataset_id=did,
            series_id=sid,
            country_code=self._country_code,
            frequency=(spec.frequency or "daily").strip().lower() or "daily",
            unit_code=(spec.unit_code or "UNIT").strip().upper() or "UNIT",
            dimensions=dict(spec.dimensions),
            title=spec.title,
            source_url=spec.source_url
            or observations_url(sid, base_url=self._base_url),
        )

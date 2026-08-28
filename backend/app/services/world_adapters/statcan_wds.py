"""Statistics Canada Web Data Service (WDS) adapter.

Official JSON API: ``https://www150.statcan.gc.ca/t1/wds/rest/…``
(user guide: https://www.statcan.gc.ca/en/developers/wds/user-guide).

frequencyCode (WDS Appendix / getCodeSets) → our ``WorldSeriesRef.frequency``:

| code | StatCan label   | mapped frequency |
|------|-----------------|------------------|
| 1    | Daily           | daily            |
| 2    | Weekly          | weekly           |
| 4    | Every 2 weeks   | weekly           |
| 6    | Monthly         | monthly          |
| 7    | Every 2 months  | monthly          |
| 9    | Quarterly       | quarterly        |
| 11   | Semi-annual     | quarterly        |
| 12   | Annual          | annual           |
| 13+  | multi-year / occasional | annual   |

Note: code ``2`` is **weekly**, not daily (daily is ``1``). Mapping is confirmed
against WDS code sets and Delta File frequency table.

Data access:

- ``getDataFromVectorByReferencePeriodRange`` — **GET** with query params
  (official signature; POST body is not accepted by the service).
- ``getDataFromVectorsAndLatestNPeriods`` — **POST** JSON body when no date
  window is requested (large ``latestN``).
- ``getCubeMetadata`` — **POST** for curated product ids when titles /
  revision tokens are not pre-seeded.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
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

WDS_BASE = "https://www150.statcan.gc.ca/t1/wds/rest"
DEFAULT_TIMEOUT_SEC = 60
DEFAULT_LATEST_N = 10_000
DEFAULT_COUNTRY_CODE = "CA"
# Wide default window when caller asks for period-range without bounds.
_DEFAULT_DATE_FROM = date(1900, 1, 1)

# Confirmed WDS frequencyCode → platform frequency (see module docstring).
FREQUENCY_CODE_MAP: dict[int, str] = {
    1: "daily",
    2: "weekly",
    4: "weekly",
    6: "monthly",
    7: "monthly",
    9: "quarterly",
    11: "quarterly",
    12: "annual",
    13: "annual",
    14: "annual",
    15: "annual",
    16: "annual",
    17: "annual",
    18: "annual",
    19: "quarterly",
    20: "monthly",
    21: "daily",
}


class StatCanWdsError(RuntimeError):
    """Raised when WDS returns FAILED / non-zero status or an empty payload."""


@dataclass(frozen=True)
class StatCanVectorSpec:
    """Curated vector inside a product (cube). ``vector_id`` without leading ``v``."""

    vector_id: int | str
    title: str | None = None
    unit_code: str = "UNIT"
    frequency: str | None = None
    frequency_code: int | None = None
    dimensions: Mapping[str, str] = field(default_factory=dict)
    coordinate: str | None = None


@dataclass(frozen=True)
class StatCanCubeSpec:
    """Curated Statistics Canada product (PID / cube)."""

    product_id: int | str
    title: str | None = None
    vectors: Sequence[StatCanVectorSpec] = field(default_factory=tuple)
    revision_token: str | None = None
    data_updated_at: date | datetime | None = None


def normalize_vector_id(raw: int | str) -> str:
    text = str(raw).strip()
    if text.lower().startswith("v"):
        text = text[1:]
    if not text.isdigit():
        raise StatCanWdsError(f"Invalid StatCan vector id: {raw!r}")
    return text


def normalize_product_id(raw: int | str) -> str:
    text = str(raw).strip()
    if not text.isdigit():
        raise StatCanWdsError(f"Invalid StatCan product id: {raw!r}")
    return text


def map_frequency_code(code: int | str | None) -> str:
    if code is None or code == "":
        raise StatCanWdsError("Missing frequencyCode from StatCan WDS")
    try:
        numeric = int(code)
    except (TypeError, ValueError) as exc:
        raise StatCanWdsError(f"Invalid frequencyCode: {code!r}") from exc
    mapped = FREQUENCY_CODE_MAP.get(numeric)
    if mapped is None:
        raise StatCanWdsError(f"Unsupported StatCan frequencyCode: {numeric}")
    return mapped


def parse_ref_period(raw: str) -> date:
    """Parse ``refPer`` / ``refPerRaw`` into a calendar date.

    WDS returns ISO dates for most frequencies (``YYYY-MM-DD``); annual cubes
    may emit ``YYYY`` or ``YYYY-MM``.
    """
    text = (raw or "").strip()
    if not text:
        raise StatCanWdsError("Empty refPer in vectorDataPoint")
    if len(text) == 4 and text.isdigit():
        return date(int(text), 1, 1)
    if len(text) == 7 and text[4] == "-":
        year, month = text.split("-", 1)
        return date(int(year), int(month), 1)
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise StatCanWdsError(f"Unparseable refPer: {raw!r}") from exc


def parse_wds_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = str(raw).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    # WDS often emits ``YYYY-MM-DDTHH:MM`` without seconds / tz.
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M%z",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def cube_source_url(product_id: str) -> str:
    return f"https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid={product_id}"


def _unwrap_wds_items(payload: Any, *, context: str) -> list[dict[str, Any]]:
    if payload is None:
        raise StatCanWdsError(f"StatCan WDS returned empty body ({context})")
    if isinstance(payload, dict):
        items = [payload]
    elif isinstance(payload, list):
        items = payload
    else:
        raise StatCanWdsError(f"Unexpected WDS payload type for {context}: {type(payload)!r}")
    if not items:
        raise StatCanWdsError(f"StatCan WDS returned empty list ({context})")
    return items


def _require_success_object(item: Mapping[str, Any], *, context: str) -> dict[str, Any]:
    status = str(item.get("status") or "").upper()
    if status != "SUCCESS":
        raise StatCanWdsError(f"StatCan WDS {context} status={status or 'MISSING'}: {item!r}")
    obj = item.get("object")
    if not isinstance(obj, dict):
        raise StatCanWdsError(f"StatCan WDS {context} missing object: {item!r}")
    code = obj.get("responseStatusCode", 0)
    try:
        code_int = int(code)
    except (TypeError, ValueError) as exc:
        raise StatCanWdsError(f"StatCan WDS {context} bad responseStatusCode: {code!r}") from exc
    if code_int != 0:
        raise StatCanWdsError(
            f"StatCan WDS {context} responseStatusCode={code_int}: {obj!r}"
        )
    return obj


def parse_vector_data_points(points: Any) -> list[WorldObservation]:
    if points is None:
        raise StatCanWdsError("vectorDataPoint is null")
    if not isinstance(points, list):
        raise StatCanWdsError(f"vectorDataPoint must be a list, got {type(points)!r}")
    if not points:
        raise StatCanWdsError("vectorDataPoint is empty (no observations)")

    observations: list[WorldObservation] = []
    for index, point in enumerate(points):
        if not isinstance(point, Mapping):
            raise StatCanWdsError(f"vectorDataPoint[{index}] is not an object")
        raw_value = point.get("value")
        if raw_value is None or raw_value == "":
            # Suppressed / missing cell — skip rather than invent zeroes.
            continue
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise StatCanWdsError(
                f"vectorDataPoint[{index}] non-numeric value: {raw_value!r}"
            ) from exc
        ref = point.get("refPer") or point.get("refPerRaw")
        period = parse_ref_period(str(ref))
        decimals_raw = point.get("decimals")
        decimals: int | None
        try:
            decimals = int(decimals_raw) if decimals_raw is not None else None
        except (TypeError, ValueError):
            decimals = None
        status_code = point.get("statusCode")
        status = None if status_code in (None, 0, "0") else str(status_code)
        observations.append(
            WorldObservation(
                period=period,
                value=value,
                status=status,
                decimals=decimals,
            )
        )
    if not observations:
        raise StatCanWdsError("vectorDataPoint had no numeric observations")
    observations.sort(key=lambda item: item.period)
    return observations


class StatCanWdsAdapter:
    """``WorldSourceAdapter`` for Statistics Canada WDS."""

    provider = "statcan"
    public_source_name = "Statistics Canada"

    def __init__(
        self,
        cubes: Sequence[StatCanCubeSpec] | None = None,
        *,
        session: requests.Session | None = None,
        timeout: float = DEFAULT_TIMEOUT_SEC,
        base_url: str = WDS_BASE,
        latest_n: int = DEFAULT_LATEST_N,
        fetch_cube_metadata: bool = True,
        country_code: str = DEFAULT_COUNTRY_CODE,
    ) -> None:
        if not cubes:
            raise StatCanWdsError(
                "StatCanWdsAdapter requires at least one curated StatCanCubeSpec"
            )
        self._cubes = tuple(cubes)
        self._session = session or requests.Session()
        self._timeout = timeout
        self._base_url = base_url.rstrip("/")
        self._latest_n = latest_n
        self._fetch_cube_metadata = fetch_cube_metadata
        self._country_code = country_code.strip().upper() or DEFAULT_COUNTRY_CODE
        self._cubes_by_product = {
            normalize_product_id(cube.product_id): cube for cube in self._cubes
        }

    async def list_datasets(self) -> AsyncIterator[WorldDatasetVersion]:
        for cube in self._cubes:
            product_id = normalize_product_id(cube.product_id)
            if self._fetch_cube_metadata and (
                cube.title is None or cube.revision_token is None or cube.data_updated_at is None
            ):
                meta = await asyncio.to_thread(self._get_cube_metadata_sync, product_id)
                yield self._dataset_from_meta(product_id, cube, meta)
            else:
                yield WorldDatasetVersion(
                    provider=self.provider,
                    dataset_id=product_id,
                    title=cube.title,
                    data_updated_at=cube.data_updated_at,
                    revision_token=cube.revision_token,
                    metadata_url=f"{self._base_url}/getCubeMetadata",
                )

    async def list_series(
        self, dataset: WorldDatasetVersion
    ) -> AsyncIterator[WorldSeriesRef]:
        product_id = normalize_product_id(dataset.dataset_id)
        cube = self._cubes_by_product.get(product_id)
        if cube is None:
            raise StatCanWdsError(
                f"No curated vectors for StatCan productId={product_id}"
            )
        if not cube.vectors:
            raise StatCanWdsError(
                f"StatCan productId={product_id} has empty vectors list"
            )
        for vector in cube.vectors:
            yield self._series_ref(product_id, vector, dataset_title=dataset.title)

    async def fetch_series(
        self,
        series: WorldSeriesRef,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> WorldSeriesPayload:
        if series.provider != self.provider:
            raise StatCanWdsError(
                f"Provider mismatch: expected {self.provider}, got {series.provider}"
            )
        vector_id = normalize_vector_id(series.series_id)
        fetched_at = datetime.now(timezone.utc)

        if date_from is not None or date_to is not None:
            start = date_from or _DEFAULT_DATE_FROM
            end = date_to or date.today()
            if end < start:
                raise StatCanWdsError(
                    f"date_to {end.isoformat()} is before date_from {start.isoformat()}"
                )
            obj = await asyncio.to_thread(
                self._get_vector_by_period_range_sync, vector_id, start, end
            )
        else:
            obj = await asyncio.to_thread(
                self._get_vector_latest_n_sync, vector_id, self._latest_n
            )

        points = obj.get("vectorDataPoint")
        observations = parse_vector_data_points(points)
        revision = None
        if observations and isinstance(points, list) and points:
            # Prefer latest releaseTime from the last datapoint when present.
            last = points[-1] if isinstance(points[-1], Mapping) else {}
            release = last.get("releaseTime") if isinstance(last, Mapping) else None
            revision = str(release) if release else None
        source_hash = hashlib.sha256(
            json.dumps(
                {
                    "vectorId": vector_id,
                    "n": len(observations),
                    "first": observations[0].period.isoformat(),
                    "last": observations[-1].period.isoformat(),
                    "revision": revision,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return WorldSeriesPayload(
            ref=series,
            observations=observations,
            fetched_at=fetched_at,
            revision_token=revision,
            source_hash=source_hash,
        )

    # ------------------------------------------------------------------ sync HTTP

    def _url(self, method: str) -> str:
        return f"{self._base_url}/{method.lstrip('/')}"

    def _get_json(self, method: str, *, params: Mapping[str, str] | None = None) -> Any:
        try:
            response = self._session.get(
                self._url(method),
                params=dict(params or {}),
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise StatCanWdsError(f"StatCan WDS GET {method} failed: {exc}") from exc
        if response.status_code >= 400:
            raise StatCanWdsError(
                f"StatCan WDS GET {method} HTTP {response.status_code}: {response.text[:300]}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise StatCanWdsError(
                f"StatCan WDS GET {method} returned non-JSON: {response.text[:300]}"
            ) from exc

    def _post_json(self, method: str, body: Any) -> Any:
        try:
            response = self._session.post(
                self._url(method),
                json=body,
                timeout=self._timeout,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
        except requests.RequestException as exc:
            raise StatCanWdsError(f"StatCan WDS POST {method} failed: {exc}") from exc
        if response.status_code >= 400:
            raise StatCanWdsError(
                f"StatCan WDS POST {method} HTTP {response.status_code}: {response.text[:300]}"
            )
        if not (response.text or "").strip():
            raise StatCanWdsError(f"StatCan WDS POST {method} returned empty body")
        try:
            return response.json()
        except ValueError as exc:
            raise StatCanWdsError(
                f"StatCan WDS POST {method} returned non-JSON: {response.text[:300]}"
            ) from exc

    def _get_cube_metadata_sync(self, product_id: str) -> dict[str, Any]:
        payload = self._post_json(
            "getCubeMetadata",
            [{"productId": int(product_id)}],
        )
        items = _unwrap_wds_items(payload, context="getCubeMetadata")
        return _require_success_object(items[0], context="getCubeMetadata")

    def _get_vector_by_period_range_sync(
        self,
        vector_id: str,
        date_from: date,
        date_to: date,
    ) -> dict[str, Any]:
        # Official method is GET. vectorIds are quoted in StatCan examples.
        params = {
            "vectorIds": f'"{vector_id}"',
            "startRefPeriod": date_from.isoformat(),
            "endReferencePeriod": date_to.isoformat(),
        }
        payload = self._get_json("getDataFromVectorByReferencePeriodRange", params=params)
        items = _unwrap_wds_items(
            payload, context="getDataFromVectorByReferencePeriodRange"
        )
        for item in items:
            obj = _require_success_object(
                item, context="getDataFromVectorByReferencePeriodRange"
            )
            if str(obj.get("vectorId")) == vector_id:
                return obj
        raise StatCanWdsError(
            f"StatCan WDS period-range response missing vectorId={vector_id}"
        )

    def _get_vector_latest_n_sync(self, vector_id: str, latest_n: int) -> dict[str, Any]:
        if latest_n <= 0:
            raise StatCanWdsError(f"latestN must be > 0, got {latest_n}")
        payload = self._post_json(
            "getDataFromVectorsAndLatestNPeriods",
            [{"vectorId": int(vector_id), "latestN": int(latest_n)}],
        )
        items = _unwrap_wds_items(
            payload, context="getDataFromVectorsAndLatestNPeriods"
        )
        obj = _require_success_object(
            items[0], context="getDataFromVectorsAndLatestNPeriods"
        )
        if str(obj.get("vectorId")) != vector_id:
            raise StatCanWdsError(
                f"StatCan WDS latestN returned vectorId={obj.get('vectorId')}, "
                f"expected {vector_id}"
            )
        return obj

    def _dataset_from_meta(
        self,
        product_id: str,
        cube: StatCanCubeSpec,
        meta: Mapping[str, Any],
    ) -> WorldDatasetVersion:
        release = parse_wds_datetime(meta.get("releaseTime") or meta.get("issueDate"))
        title = cube.title or meta.get("cubeTitleEn") or meta.get("cubeTitleFr")
        revision = cube.revision_token or (
            str(meta.get("releaseTime")) if meta.get("releaseTime") else None
        )
        return WorldDatasetVersion(
            provider=self.provider,
            dataset_id=product_id,
            title=str(title) if title else None,
            data_updated_at=cube.data_updated_at or release,
            structure_updated_at=None,
            revision_token=revision,
            metadata_url=f"{self._base_url}/getCubeMetadata",
        )

    def _series_ref(
        self,
        product_id: str,
        vector: StatCanVectorSpec,
        *,
        dataset_title: str | None,
    ) -> WorldSeriesRef:
        vector_id = normalize_vector_id(vector.vector_id)
        if vector.frequency:
            frequency = vector.frequency.strip().lower()
        elif vector.frequency_code is not None:
            frequency = map_frequency_code(vector.frequency_code)
        else:
            # Fail closed: frequency must be known before identity is published.
            raise StatCanWdsError(
                f"Vector {vector_id} in product {product_id} needs frequency "
                "or frequency_code in StatCanVectorSpec"
            )
        dims = {str(k): str(v) for k, v in vector.dimensions.items()}
        if vector.coordinate:
            dims.setdefault("coordinate", vector.coordinate)
        title = vector.title or (
            f"{dataset_title} (v{vector_id})" if dataset_title else f"v{vector_id}"
        )
        return WorldSeriesRef(
            provider=self.provider,
            dataset_id=product_id,
            series_id=vector_id,
            country_code=self._country_code,
            frequency=frequency,
            unit_code=vector.unit_code.strip().upper() or "UNIT",
            dimensions=dims,
            title=title,
            source_url=cube_source_url(product_id),
        )

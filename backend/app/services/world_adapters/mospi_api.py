"""Ministry of Statistics and Programme Implementation (MoSPI) Open API adapter.

Official base: ``https://api.mospi.gov.in`` (also powers e-Sankhyiki).

The MoSPI TLS stack requires legacy renegotiation
(``ssl.OP_LEGACY_SERVER_CONNECT``). Without auth the platform still returns
paginated JSON for the curated national-core filters.

``dataset_id`` selects the MoSPI family: ``CPI`` / ``IIP`` / ``WPI`` / ``NAS`` /
``PLFS`` / ``RBI``. ``series_id`` is a stable passport key; filter dimensions
live in ``WorldSeriesRef.dimensions`` (and YAML ``dimensions``).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import ssl
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, AsyncIterator, Mapping, Sequence

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.services.world_source_adapter import (
    WorldDatasetVersion,
    WorldObservation,
    WorldSeriesPayload,
    WorldSeriesRef,
)

logger = logging.getLogger(__name__)

MOSPI_BASE = "https://api.mospi.gov.in"
DEFAULT_TIMEOUT_SEC = 90
DEFAULT_COUNTRY_CODE = "IN"
_PAGE_LIMIT = 500
_USER_AGENT = "Mozilla/5.0 (compatible; ForecastEconomy/1.0; +https://forecasteconomy.com)"

_MONTH_NAME_TO_NUM: dict[str, int] = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

_QUARTER_TO_MONTH: dict[str, int] = {
    "Q1": 4,   # Indian FY Q1 = Apr–Jun → period start April
    "Q2": 7,
    "Q3": 10,
    "Q4": 1,   # Jan–Mar of next calendar year; year adjusted below
    "1": 4,
    "2": 7,
    "3": 10,
    "4": 1,
}


class MospiApiError(RuntimeError):
    """Raised when MoSPI returns an unusable payload."""


class _LegacySSLAdapter(HTTPAdapter):
    """Enable OP_LEGACY_SERVER_CONNECT for api.mospi.gov.in."""

    def init_poolmanager(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


@dataclass(frozen=True)
class MospiSeriesSpec:
    series_id: str
    dataset_id: str
    title: str | None = None
    unit_code: str = "UNIT"
    frequency: str = "monthly"
    dimensions: Mapping[str, str] = field(default_factory=dict)
    source_url: str | None = None


DEFAULT_MOSPI_SERIES: tuple[MospiSeriesSpec, ...] = (
    MospiSeriesSpec(
        series_id="cpi-general-combined",
        dataset_id="CPI",
        title="CPI General Combined (All India)",
        unit_code="INDEX",
        frequency="monthly",
        dimensions={
            "base_year": "2012",
            "series": "Current",
            "state_code": "99",
            "sector_code": "3",
            "group_name": "General",
            "subgroup_name": "General-Overall",
        },
    ),
)


def normalize_dataset_id(raw: str) -> str:
    text = (raw or "").strip().upper()
    if text not in {"CPI", "IIP", "WPI", "NAS", "PLFS", "RBI"}:
        raise MospiApiError(f"Unsupported MoSPI dataset_id={raw!r}")
    return text


def normalize_series_id(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise MospiApiError("Empty MoSPI series_id")
    return text


def parse_month_token(raw: Any) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw if 1 <= raw <= 12 else None
    text = str(raw).strip()
    if text.isdigit():
        value = int(text)
        return value if 1 <= value <= 12 else None
    return _MONTH_NAME_TO_NUM.get(text.lower())


def parse_indian_fy_quarter(year_token: str, quarter_token: str) -> date:
    """Map Indian FY label ``2024-25`` + ``Q1``…``Q4`` to period start date."""
    text = (year_token or "").strip()
    start_year = int(text.split("-")[0])
    q = (quarter_token or "").strip().upper()
    if q in {"Q4", "4"}:
        # FY Q4 = Jan–Mar of start_year+1
        return date(start_year + 1, 1, 1)
    month = _QUARTER_TO_MONTH.get(q)
    if month is None:
        raise MospiApiError(f"Unknown NAS quarter token: {quarter_token!r}")
    return date(start_year, month, 1)


def parse_plfs_annual_period(year_token: str) -> date:
    text = (year_token or "").strip()
    if "-" in text:
        return date(int(text.split("-")[0]), 4, 1)
    return date(int(text), 1, 1)


def build_session() -> requests.Session:
    session = requests.Session()
    session.verify = False
    session.headers.update(
        {
            "User-Agent": _USER_AGENT,
            "Accept": "application/json",
        }
    )
    retry = Retry(
        total=3,
        connect=2,
        read=2,
        status=3,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
        respect_retry_after_header=True,
    )
    session.mount("https://", _LegacySSLAdapter(max_retries=retry))
    session.mount("http://", _LegacySSLAdapter(max_retries=retry))
    return session


def _endpoint_for(dataset_id: str, dims: Mapping[str, str]) -> str:
    if dataset_id == "CPI":
        if str(dims.get("base_year") or "") == "2024":
            return "/api/cpi/getCPIData"
        return "/api/cpi/getCPIIndex"
    if dataset_id == "IIP":
        freq = (dims.get("frequency") or "Monthly").strip().lower()
        if freq.startswith("annual"):
            return "/api/iip/getIIPAnnual"
        return "/api/iip/getIIPMonthly"
    if dataset_id == "WPI":
        return "/api/wpi/getWpiRecords"
    if dataset_id == "NAS":
        return "/api/nas/getNASData"
    if dataset_id == "PLFS":
        return "/api/plfs/getData"
    if dataset_id == "RBI":
        return "/api/rbi/getRbiRecords"
    raise MospiApiError(f"No endpoint for dataset {dataset_id}")


def _query_params(dataset_id: str, dims: Mapping[str, str]) -> dict[str, str]:
    params: dict[str, str] = {}
    if dataset_id == "CPI":
        params["base_year"] = str(dims.get("base_year") or "2012")
        params["series"] = str(dims.get("series") or "Current")
        if dims.get("state_code"):
            params["state_code"] = str(dims["state_code"])
        if dims.get("sector_code"):
            params["sector_code"] = str(dims["sector_code"])
        if dims.get("year"):
            params["year"] = str(dims["year"])
        if dims.get("month_code"):
            params["month_code"] = str(dims["month_code"])
        if dims.get("group_code"):
            params["group_code"] = str(dims["group_code"])
    elif dataset_id == "IIP":
        params["base_year"] = str(dims.get("base_year") or "2011-12")
        if dims.get("year"):
            params["year"] = str(dims["year"])
        if dims.get("financial_year"):
            params["financial_year"] = str(dims["financial_year"])
        if dims.get("month_code"):
            params["month_code"] = str(dims["month_code"])
        if dims.get("category_code"):
            params["category_code"] = str(dims["category_code"])
    elif dataset_id == "WPI":
        params["base_year"] = str(dims.get("base_year") or "2011-12")
        if dims.get("year"):
            params["year"] = str(dims["year"])
        if dims.get("month_code"):
            params["month_code"] = str(dims["month_code"])
        if dims.get("major_group_code"):
            params["major_group_code"] = str(dims["major_group_code"])
    elif dataset_id == "NAS":
        params["base_year"] = str(dims.get("base_year") or "2011-12")
        params["series"] = str(dims.get("series") or "Current")
        params["frequency_code"] = str(dims.get("frequency_code") or "Quarterly")
        params["indicator_code"] = str(dims.get("indicator_code") or "5")
        if dims.get("year"):
            params["year"] = str(dims["year"])
        if dims.get("quarterly_code"):
            params["quarterly_code"] = str(dims["quarterly_code"])
    elif dataset_id == "PLFS":
        params["indicator_code"] = str(dims.get("indicator_code") or "3")
        params["frequency_code"] = str(dims.get("frequency_code") or "1")
        params["year_type_code"] = str(dims.get("year_type_code") or "1")
        params["state_code"] = str(dims.get("state_code") or "99")
        params["gender_code"] = str(dims.get("gender_code") or "3")
        params["age_code"] = str(dims.get("age_code") or "1")
        params["sector_code"] = str(dims.get("sector_code") or "3")
        if dims.get("year"):
            params["year"] = str(dims["year"])
    elif dataset_id == "RBI":
        params["sub_indicator_code"] = str(dims.get("sub_indicator_code") or "36")
        if dims.get("year"):
            params["year"] = str(dims["year"])
        if dims.get("month"):
            params["month"] = str(dims["month"])
    return params


def _row_matches(dataset_id: str, row: Mapping[str, Any], dims: Mapping[str, str]) -> bool:
    if dataset_id == "CPI":
        group = str(dims.get("group_name") or "General").strip().lower()
        subgroup = str(dims.get("subgroup_name") or "").strip().lower()
        sector = str(dims.get("sector_name") or "Combined").strip().lower()
        state = str(dims.get("state_name") or "All India").strip().lower()
        if str(row.get("group") or "").strip().lower() != group:
            return False
        if subgroup and str(row.get("subgroup") or "").strip().lower() != subgroup:
            return False
        if str(row.get("sector") or "").strip().lower() != sector:
            return False
        if state and str(row.get("state") or "").strip().lower() != state:
            return False
        return True
    if dataset_id == "IIP":
        category = str(dims.get("category_name") or "General").strip().lower()
        return str(row.get("category") or "").strip().lower() == category
    if dataset_id == "WPI":
        major = str(dims.get("major_group_name") or "Wholesale price index").strip().lower()
        if str(row.get("majorgroup") or "").strip().lower() != major:
            return False
        # Overall index: no group / item breakdown.
        if row.get("group") not in (None, "", "null"):
            return False
        if row.get("item") not in (None, "", "null"):
            return False
        return True
    if dataset_id == "NAS":
        # GDP rows have industry/subindustry null.
        if row.get("industry") not in (None, "", "null"):
            return False
        return True
    if dataset_id == "PLFS":
        return True
    if dataset_id == "RBI":
        currency = str(dims.get("currency") or "US Dollar").strip().lower()
        if currency and str(row.get("currency") or "").strip().lower() != currency:
            return False
        ref = dims.get("reference_rate")
        if ref:
            if str(row.get("reference_rate") or "").strip().lower() != ref.strip().lower():
                return False
        return True
    return True


def _row_value(dataset_id: str, row: Mapping[str, Any], dims: Mapping[str, str]) -> float | None:
    keys: tuple[str, ...]
    if dataset_id == "CPI":
        keys = ("index", "Index")
    elif dataset_id == "IIP":
        keys = ("index",)
    elif dataset_id == "WPI":
        keys = ("index_value", "index")
    elif dataset_id == "NAS":
        price = (dims.get("price") or "constant").strip().lower()
        keys = ("constant_price",) if price.startswith("const") else ("current_price",)
    elif dataset_id == "PLFS":
        keys = ("value",)
    else:
        keys = ("value",)
    for key in keys:
        raw = row.get(key)
        if raw in (None, "", "null", "NA", "-"):
            continue
        try:
            return float(str(raw).replace(",", ""))
        except (TypeError, ValueError):
            continue
    return None


def _row_period(dataset_id: str, row: Mapping[str, Any]) -> date | None:
    try:
        if dataset_id in {"CPI", "IIP", "WPI", "RBI"}:
            year_raw = row.get("year")
            if year_raw is None:
                return None
            year = int(str(year_raw).split("-")[0])
            month = parse_month_token(row.get("month") or row.get("month_code"))
            if month is None:
                return None
            return date(year, month, 1)
        if dataset_id == "NAS":
            return parse_indian_fy_quarter(
                str(row.get("year") or ""),
                str(row.get("quarter") or row.get("quarterly_code") or ""),
            )
        if dataset_id == "PLFS":
            return parse_plfs_annual_period(str(row.get("year") or ""))
    except (TypeError, ValueError, MospiApiError):
        return None
    return None


def parse_mospi_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    dataset_id: str,
    dims: Mapping[str, str],
) -> list[WorldObservation]:
    by_period: dict[date, float] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if not _row_matches(dataset_id, row, dims):
            continue
        period = _row_period(dataset_id, row)
        value = _row_value(dataset_id, row, dims)
        if period is None or value is None:
            continue
        by_period[period] = value
    if not by_period:
        raise MospiApiError(
            f"MoSPI {dataset_id} rows had no matching numeric observations"
        )
    return [
        WorldObservation(period=period, value=value)
        for period, value in sorted(by_period.items())
    ]


def _specs_from_national(series_specs: Sequence[Any]) -> list[MospiSeriesSpec]:
    out: list[MospiSeriesSpec] = []
    for row in series_specs or ():
        provider = str(getattr(row, "provider", "") or "").strip().lower()
        if provider and provider not in {"mospi", "rbi"}:
            continue
        # RBI passport rows may also be served through this transport when
        # dataset_id == RBI (see rbi_mospi module / shared create).
        sid = getattr(row, "series_id", None)
        did = getattr(row, "dataset_id", None)
        if not sid or not did:
            continue
        try:
            dataset_id = normalize_dataset_id(str(did))
        except MospiApiError:
            continue
        if provider == "rbi" and dataset_id != "RBI":
            continue
        if provider == "mospi" and dataset_id == "RBI":
            # Prefer the rbi provider entry for RBI-tagged rows.
            continue
        out.append(
            MospiSeriesSpec(
                series_id=str(sid),
                dataset_id=dataset_id,
                title=getattr(row, "name_en", None)
                or getattr(row, "name_ru", None)
                or getattr(row, "title", None),
                unit_code=str(getattr(row, "unit", None) or "UNIT"),
                frequency=str(getattr(row, "frequency", None) or "monthly"),
                dimensions=dict(getattr(row, "dimensions", None) or {}),
                source_url=getattr(row, "source_url", None),
            )
        )
    return out


def create_adapter(
    *,
    series_specs: Sequence[Any] | None = None,
    **kwargs: Any,
) -> "MospiApiAdapter":
    curated = _specs_from_national(series_specs or ()) if series_specs is not None else None
    return MospiApiAdapter(curated or None, **kwargs)


class MospiApiAdapter:
    """``WorldSourceAdapter`` for MoSPI Open API families."""

    provider = "mospi"
    public_source_name = "Ministry of Statistics and Programme Implementation"

    def __init__(
        self,
        series: Sequence[MospiSeriesSpec] | None = None,
        *,
        session: requests.Session | None = None,
        timeout: float = DEFAULT_TIMEOUT_SEC,
        base_url: str = MOSPI_BASE,
        country_code: str = DEFAULT_COUNTRY_CODE,
        provider_name: str | None = None,
        public_source_name: str | None = None,
        accepted_datasets: Sequence[str] | None = None,
    ) -> None:
        curated = tuple(series) if series is not None else DEFAULT_MOSPI_SERIES
        if not curated:
            raise MospiApiError("MospiApiAdapter requires at least one curated series")
        if provider_name:
            self.provider = provider_name
        if public_source_name:
            self.public_source_name = public_source_name
        self._accepted = {
            normalize_dataset_id(x) for x in (accepted_datasets or ("CPI", "IIP", "WPI", "NAS", "PLFS"))
        }
        self._session = session or build_session()
        self._timeout = timeout
        self._base_url = base_url.rstrip("/")
        self._country_code = country_code.strip().upper() or DEFAULT_COUNTRY_CODE
        self._by_dataset: dict[str, list[MospiSeriesSpec]] = {}
        self._by_key: dict[tuple[str, str], MospiSeriesSpec] = {}
        for spec in curated:
            did = normalize_dataset_id(spec.dataset_id)
            if did not in self._accepted:
                continue
            sid = normalize_series_id(spec.series_id)
            normalized = MospiSeriesSpec(
                series_id=sid,
                dataset_id=did,
                title=spec.title,
                unit_code=(spec.unit_code or "UNIT").strip().upper() or "UNIT",
                frequency=(spec.frequency or "monthly").strip().lower() or "monthly",
                dimensions=dict(spec.dimensions),
                source_url=spec.source_url,
            )
            self._by_dataset.setdefault(did, []).append(normalized)
            self._by_key[(did, sid)] = normalized
        if not self._by_key:
            raise MospiApiError(
                f"No curated MoSPI series for provider={self.provider!r}"
            )

    async def list_datasets(self) -> AsyncIterator[WorldDatasetVersion]:
        for dataset_id, members in self._by_dataset.items():
            yield WorldDatasetVersion(
                provider=self.provider,
                dataset_id=dataset_id,
                title=members[0].title or dataset_id,
                metadata_url=f"{self._base_url}/",
            )

    async def list_series(
        self, dataset: WorldDatasetVersion
    ) -> AsyncIterator[WorldSeriesRef]:
        dataset_id = normalize_dataset_id(dataset.dataset_id)
        members = self._by_dataset.get(dataset_id)
        if not members:
            raise MospiApiError(f"No curated MoSPI series for {dataset_id!r}")
        for spec in members:
            yield self._series_ref(spec)

    async def fetch_series(
        self,
        series: WorldSeriesRef,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> WorldSeriesPayload:
        if series.provider != self.provider:
            raise MospiApiError(
                f"Provider mismatch: expected {self.provider}, got {series.provider}"
            )
        dataset_id = normalize_dataset_id(series.dataset_id)
        series_id = normalize_series_id(series.series_id)
        spec = self._by_key.get((dataset_id, series_id))
        dims = dict(spec.dimensions if spec else {})
        dims.update({str(k): str(v) for k, v in (series.dimensions or {}).items()})
        fetched_at = datetime.now(timezone.utc)
        rows = await asyncio.to_thread(
            self._fetch_all_rows_sync, dataset_id, dims
        )
        observations = parse_mospi_rows(rows, dataset_id=dataset_id, dims=dims)
        if date_from is not None:
            observations = [o for o in observations if o.period >= date_from]
        if date_to is not None:
            observations = [o for o in observations if o.period <= date_to]
        if not observations:
            raise MospiApiError(
                f"MoSPI {dataset_id}/{series_id} empty after filters"
            )
        revision = (
            f"{observations[0].period.isoformat()}"
            f"/{observations[-1].period.isoformat()}"
            f"#{len(observations)}"
        )
        source_hash = hashlib.sha256(
            json.dumps(
                {
                    "dataset": dataset_id,
                    "series": series_id,
                    "n": len(observations),
                    "last": observations[-1].period.isoformat(),
                    "last_value": observations[-1].value,
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

    def _fetch_all_rows_sync(
        self,
        dataset_id: str,
        dims: Mapping[str, str],
    ) -> list[Mapping[str, Any]]:
        endpoint = _endpoint_for(dataset_id, dims)
        url = f"{self._base_url}{endpoint}"
        base_params = _query_params(dataset_id, dims)
        rows: list[Mapping[str, Any]] = []
        page = 1
        total_pages = 1
        while page <= total_pages:
            params = {
                **base_params,
                "limit": str(_PAGE_LIMIT),
                "page": str(page),
            }
            try:
                response = self._session.get(
                    url, params=params, timeout=self._timeout
                )
            except requests.RequestException as exc:
                raise MospiApiError(f"MoSPI GET {url} failed: {exc}") from exc
            if response.status_code >= 400:
                raise MospiApiError(
                    f"MoSPI GET {url} HTTP {response.status_code}: "
                    f"{response.text[:300]}"
                )
            try:
                payload = response.json()
            except ValueError as exc:
                raise MospiApiError(
                    f"MoSPI GET {url} non-JSON: {response.text[:300]}"
                ) from exc
            if not isinstance(payload, dict):
                raise MospiApiError(f"MoSPI payload type {type(payload)!r}")
            if payload.get("statusCode") is False:
                raise MospiApiError(
                    f"MoSPI statusCode=false: {payload.get('msg') or payload.get('error')}"
                )
            chunk = payload.get("data")
            if isinstance(chunk, list):
                rows.extend(item for item in chunk if isinstance(item, Mapping))
            elif isinstance(chunk, Mapping):
                # Some meta endpoints return objects; treat as no data rows.
                pass
            meta = payload.get("meta_data") if isinstance(payload.get("meta_data"), Mapping) else {}
            try:
                total_pages = max(1, int(meta.get("totalPages") or 1))
            except (TypeError, ValueError):
                total_pages = 1
            if not chunk:
                break
            page += 1
            if page > 40:
                break
        if not rows:
            msg = payload.get("msg") if isinstance(payload, dict) else None
            raise MospiApiError(
                f"MoSPI {dataset_id} returned no rows ({msg or 'empty'})"
            )
        return rows

    def _series_ref(self, spec: MospiSeriesSpec) -> WorldSeriesRef:
        return WorldSeriesRef(
            provider=self.provider,
            dataset_id=spec.dataset_id,
            series_id=spec.series_id,
            country_code=self._country_code,
            frequency=spec.frequency,
            unit_code=spec.unit_code,
            dimensions=dict(spec.dimensions),
            title=spec.title,
            source_url=spec.source_url or f"{self._base_url}/",
        )

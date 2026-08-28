"""Reserve Bank of India series via MoSPI Open API (+ best-effort repo stub).

FX / reference-rate style series are officially redistributed by MoSPI under
``/api/rbi/*`` (same TLS stack as other MoSPI families). Policy-rate (repo)
archive pages on ``rbi.org.in`` are often unreachable from abroad; the
adapter still attempts a small set of official URLs and fails closed so the
passport can keep ``is_listed=false`` until the endpoint is reachable.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, AsyncIterator, Mapping, Sequence

import requests

from app.services.world_adapters.mospi_api import (
    MospiApiAdapter,
    MospiApiError,
    MospiSeriesSpec,
    build_session,
    create_adapter as create_mospi_adapter,
    normalize_dataset_id,
    normalize_series_id,
    parse_mospi_rows,
)
from app.services.world_source_adapter import (
    WorldDatasetVersion,
    WorldObservation,
    WorldSeriesPayload,
    WorldSeriesRef,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SEC = 45
DEFAULT_COUNTRY_CODE = "IN"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)

# Official archive / current-rate surfaces (best-effort; often timeout abroad).
_REPO_CANDIDATE_URLS: tuple[str, ...] = (
    "https://www.rbi.org.in/Scripts/BS_ViewPolicyInterestRateArchive.aspx",
    "https://www.rbi.org.in/Scripts/BS_ViewPolicyRateArchive.aspx",
    "https://rbi.org.in/Scripts/BS_ViewPolicyInterestRateArchive.aspx",
)

_REPO_ROW_RE = re.compile(
    r"(\d{1,2}[-/][A-Za-z]{3}[-/]\d{2,4}|\d{4}-\d{2}-\d{2})"
    r".{0,80}?"
    r"(\d+(?:\.\d+)?)\s*%?",
    re.IGNORECASE | re.DOTALL,
)


class RbiRatesError(RuntimeError):
    """Raised when RBI/MoSPI-RBI transport fails."""


@dataclass(frozen=True)
class RbiSeriesSpec:
    series_id: str
    dataset_id: str
    title: str | None = None
    unit_code: str = "UNIT"
    frequency: str = "monthly"
    dimensions: Mapping[str, str] = field(default_factory=dict)
    source_url: str | None = None


DEFAULT_RBI_SERIES: tuple[RbiSeriesSpec, ...] = (
    RbiSeriesSpec(
        series_id="usd-inr-avg",
        dataset_id="RBI",
        title="INR per USD — monthly average",
        unit_code="INR_PER_USD",
        frequency="monthly",
        dimensions={
            "sub_indicator_code": "36",
            "currency": "US Dollar",
        },
    ),
)


def _specs_from_national(series_specs: Sequence[Any]) -> list[MospiSeriesSpec]:
    out: list[MospiSeriesSpec] = []
    for row in series_specs or ():
        provider = str(getattr(row, "provider", "") or "").strip().lower()
        if provider and provider != "rbi":
            continue
        sid = getattr(row, "series_id", None)
        did = getattr(row, "dataset_id", None)
        if not sid or not did:
            continue
        out.append(
            MospiSeriesSpec(
                series_id=str(sid),
                dataset_id=str(did),
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
) -> "RbiRatesAdapter":
    curated = _specs_from_national(series_specs or ()) if series_specs is not None else None
    return RbiRatesAdapter(curated or None, **kwargs)


class RbiRatesAdapter:
    """RBI identity: MoSPI ``/api/rbi`` for FX; HTML archive attempt for repo."""

    provider = "rbi"
    public_source_name = "Reserve Bank of India"

    def __init__(
        self,
        series: Sequence[MospiSeriesSpec] | None = None,
        *,
        session: requests.Session | None = None,
        timeout: float = DEFAULT_TIMEOUT_SEC,
        country_code: str = DEFAULT_COUNTRY_CODE,
    ) -> None:
        curated = list(series or ())
        if not curated:
            curated = [
                MospiSeriesSpec(
                    series_id=s.series_id,
                    dataset_id=s.dataset_id,
                    title=s.title,
                    unit_code=s.unit_code,
                    frequency=s.frequency,
                    dimensions=dict(s.dimensions),
                    source_url=s.source_url,
                )
                for s in DEFAULT_RBI_SERIES
            ]
        self._timeout = timeout
        self._country_code = country_code.strip().upper() or DEFAULT_COUNTRY_CODE
        self._session = session or build_session()
        self._html_session = requests.Session()
        self._html_session.headers.update({"User-Agent": _USER_AGENT})

        mospi_rows = [s for s in curated if str(s.dataset_id).upper() == "RBI"]
        self._mospi: MospiApiAdapter | None
        if mospi_rows:
            self._mospi = MospiApiAdapter(
                mospi_rows,
                session=self._session,
                timeout=timeout,
                country_code=self._country_code,
                provider_name="rbi",
                public_source_name=self.public_source_name,
                accepted_datasets=("RBI",),
            )
        else:
            self._mospi = None
        self._repo_specs = [
            s
            for s in curated
            if str(s.dataset_id).strip().lower() in {"repo", "policy"}
        ]
        self._by_dataset: dict[str, list[MospiSeriesSpec]] = {}
        for spec in curated:
            did = str(spec.dataset_id).strip()
            self._by_dataset.setdefault(did, []).append(spec)

    async def list_datasets(self) -> AsyncIterator[WorldDatasetVersion]:
        if self._mospi is not None:
            async for item in self._mospi.list_datasets():
                yield item
        for dataset_id in self._by_dataset:
            if dataset_id.upper() == "RBI":
                continue
            yield WorldDatasetVersion(
                provider=self.provider,
                dataset_id=dataset_id,
                title="RBI policy / repo rate",
                metadata_url=_REPO_CANDIDATE_URLS[0],
            )

    async def list_series(
        self, dataset: WorldDatasetVersion
    ) -> AsyncIterator[WorldSeriesRef]:
        did = (dataset.dataset_id or "").strip()
        if did.upper() == "RBI":
            if self._mospi is None:
                raise RbiRatesError("No curated MoSPI-RBI series configured")
            async for item in self._mospi.list_series(dataset):
                yield item
            return
        for spec in self._by_dataset.get(did, []):
            yield WorldSeriesRef(
                provider=self.provider,
                dataset_id=did,
                series_id=normalize_series_id(spec.series_id),
                country_code=self._country_code,
                frequency=spec.frequency,
                unit_code=spec.unit_code,
                dimensions=dict(spec.dimensions),
                title=spec.title,
                source_url=spec.source_url or _REPO_CANDIDATE_URLS[0],
            )

    async def fetch_series(
        self,
        series: WorldSeriesRef,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> WorldSeriesPayload:
        if series.provider != self.provider:
            raise RbiRatesError(
                f"Provider mismatch: expected {self.provider}, got {series.provider}"
            )
        if str(series.dataset_id).upper() == "RBI":
            if self._mospi is None:
                raise RbiRatesError("No curated MoSPI-RBI series configured")
            return await self._mospi.fetch_series(
                series, date_from=date_from, date_to=date_to
            )
        # Policy / repo best-effort HTML scrape.
        observations = await asyncio.to_thread(self._fetch_repo_sync)
        if date_from is not None:
            observations = [o for o in observations if o.period >= date_from]
        if date_to is not None:
            observations = [o for o in observations if o.period <= date_to]
        if not observations:
            raise RbiRatesError("RBI repo/policy archive returned no observations")
        fetched_at = datetime.now(timezone.utc)
        revision = (
            f"{observations[0].period.isoformat()}"
            f"/{observations[-1].period.isoformat()}"
            f"#{len(observations)}"
        )
        source_hash = hashlib.sha256(
            json.dumps(
                {
                    "series": series.series_id,
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

    def _fetch_repo_sync(self) -> list[WorldObservation]:
        errors: list[str] = []
        for url in _REPO_CANDIDATE_URLS:
            try:
                response = self._html_session.get(url, timeout=self._timeout)
            except requests.RequestException as exc:
                errors.append(f"{url}: {exc}")
                continue
            if response.status_code >= 400:
                errors.append(f"{url}: HTTP {response.status_code}")
                continue
            obs = _parse_repo_html(response.text)
            if obs:
                return obs
            errors.append(f"{url}: no parseable rates")
        raise RbiRatesError(
            "RBI policy-rate archive unreachable: " + "; ".join(errors[:3])
        )


def _parse_repo_html(html: str) -> list[WorldObservation]:
    """Very defensive scrape of RBI policy-rate archive tables."""
    by_period: dict[date, float] = {}
    # Prefer table cells: Date | Repo Rate
    row_re = re.compile(
        r"<tr[^>]*>\s*<td[^>]*>\s*([^<]+?)\s*</td>\s*<td[^>]*>\s*([0-9]+(?:\.[0-9]+)?)\s*</td>",
        re.IGNORECASE,
    )
    for match in row_re.finditer(html or ""):
        period = _parse_loose_date(match.group(1))
        if period is None:
            continue
        try:
            value = float(match.group(2))
        except ValueError:
            continue
        by_period[period] = value
    if not by_period:
        for match in _REPO_ROW_RE.finditer(html or ""):
            period = _parse_loose_date(match.group(1))
            if period is None:
                continue
            try:
                value = float(match.group(2))
            except ValueError:
                continue
            by_period[period] = value
    return [
        WorldObservation(period=period, value=value)
        for period, value in sorted(by_period.items())
    ]


def _parse_loose_date(raw: str) -> date | None:
    text = (raw or "").strip()
    if not text:
        return None
    for fmt in ("%d-%b-%Y", "%d-%b-%y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text[:15].strip(), fmt).date()
        except ValueError:
            continue
    return None

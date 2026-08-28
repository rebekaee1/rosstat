"""CFETS / China Money (chinamoney.com.cn) adapter.

Official portal of the China Foreign Exchange Trade System (under PBOC).
Public JSON endpoints used by the national-core China passport:

- Central parity (CCPR) history::

    GET /ags/ms/cm-u-bk-ccpr/CcprHisNew
        ?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD
        &currency=USD/CNY&pageNum=1&pageSize=99

- Loan Prime Rate (LPR) history::

    GET /ags/ms/cm-u-bk-currency/LprHis
        ?startDate=…&endDate=…&pageNum=…&pageSize=…

- SHIBOR history::

    GET /ags/ms/cm-u-bk-shibor/ShiborHis
        ?startDate=…&endDate=…&pageNum=…&pageSize=…

``dataset_id`` is one of ``ccpr`` / ``lpr`` / ``shibor``.
``series_id`` is the field key (``USD/CNY``, ``1Y``, ``ON``, …).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, AsyncIterator, Mapping, Sequence

import requests

from app.services.world_source_adapter import (
    WorldDatasetVersion,
    WorldObservation,
    WorldSeriesPayload,
    WorldSeriesRef,
)

logger = logging.getLogger(__name__)

CFETS_BASE = "https://www.chinamoney.com.cn"
DEFAULT_TIMEOUT_SEC = 60
DEFAULT_COUNTRY_CODE = "CN"
_DEFAULT_DATE_FROM = date(2013, 1, 1)
_PAGE_SIZE = 99
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)

_ENDPOINT_BY_DATASET: dict[str, str] = {
    "ccpr": "/ags/ms/cm-u-bk-ccpr/CcprHisNew",
    "lpr": "/ags/ms/cm-u-bk-currency/LprHis",
    "shibor": "/ags/ms/cm-u-bk-shibor/ShiborHis",
}


class CfetsChinamoneyError(RuntimeError):
    """Raised when CFETS China Money returns an unusable payload."""


@dataclass(frozen=True)
class CfetsSeriesSpec:
    series_id: str
    dataset_id: str
    title: str | None = None
    unit_code: str = "UNIT"
    frequency: str = "daily"
    dimensions: Mapping[str, str] = field(default_factory=dict)
    source_url: str | None = None


DEFAULT_CFETS_SERIES: tuple[CfetsSeriesSpec, ...] = (
    CfetsSeriesSpec(
        series_id="USD/CNY",
        dataset_id="ccpr",
        title="USD/CNY central parity rate",
        unit_code="CNY_PER_USD",
        frequency="daily",
    ),
    CfetsSeriesSpec(
        series_id="1Y",
        dataset_id="lpr",
        title="Loan Prime Rate 1Y",
        unit_code="PERCENT",
        frequency="monthly",
    ),
)


def normalize_dataset_id(raw: str) -> str:
    text = (raw or "").strip().lower()
    if text not in _ENDPOINT_BY_DATASET:
        raise CfetsChinamoneyError(
            f"Unsupported CFETS dataset_id={raw!r}; "
            f"expected one of {sorted(_ENDPOINT_BY_DATASET)}"
        )
    return text


def normalize_series_id(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise CfetsChinamoneyError("Empty CFETS series_id")
    return text


def parse_cfets_date(raw: str) -> date:
    text = (raw or "").strip()
    if not text:
        raise CfetsChinamoneyError("Empty CFETS observation date")
    # Prefer ISO / CN form YYYY-MM-DD; fall back to "12 Aug 2026".
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        try:
            return date.fromisoformat(text[:10])
        except ValueError as exc:
            raise CfetsChinamoneyError(f"Unparseable CFETS date: {raw!r}") from exc
    try:
        return datetime.strptime(text, "%d %b %Y").date()
    except ValueError as exc:
        raise CfetsChinamoneyError(f"Unparseable CFETS date: {raw!r}") from exc


def parse_ccpr_records(
    payload: Mapping[str, Any],
    *,
    series_id: str,
) -> list[WorldObservation]:
    sid = normalize_series_id(series_id)
    searchlist = []
    data = payload.get("data")
    if isinstance(data, Mapping):
        raw_list = data.get("searchlist") or data.get("head") or []
        if isinstance(raw_list, list):
            searchlist = [str(x) for x in raw_list]
    try:
        col = searchlist.index(sid)
    except ValueError as exc:
        # Single-currency responses often put the asked pair alone in searchlist.
        if len(searchlist) == 1:
            col = 0
        else:
            raise CfetsChinamoneyError(
                f"CCPR payload missing currency {sid!r} in {searchlist!r}"
            ) from exc

    records = payload.get("records")
    if not isinstance(records, list) or not records:
        raise CfetsChinamoneyError(f"CCPR observations empty for {sid}")

    out: list[WorldObservation] = []
    for index, item in enumerate(records):
        if not isinstance(item, Mapping):
            raise CfetsChinamoneyError(f"CCPR records[{index}] is not an object")
        period = parse_cfets_date(str(item.get("date") or ""))
        values = item.get("values")
        if not isinstance(values, list) or col >= len(values):
            continue
        raw = values[col]
        if raw is None or raw == "":
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise CfetsChinamoneyError(
                f"CCPR records[{index}] non-numeric: {raw!r}"
            ) from exc
        out.append(WorldObservation(period=period, value=value))
    if not out:
        raise CfetsChinamoneyError(f"CCPR had no numeric values for {sid}")
    out.sort(key=lambda item: item.period)
    return out


def parse_keyed_rate_records(
    payload: Mapping[str, Any],
    *,
    series_id: str,
) -> list[WorldObservation]:
    """Parse LPR / SHIBOR ``records`` where each row has tenor keys + showDateCN."""
    sid = normalize_series_id(series_id)
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        raise CfetsChinamoneyError(f"CFETS rate observations empty for {sid}")

    out: list[WorldObservation] = []
    for index, item in enumerate(records):
        if not isinstance(item, Mapping):
            raise CfetsChinamoneyError(f"records[{index}] is not an object")
        raw_date = item.get("showDateCN") or item.get("date") or item.get("showDateEN")
        period = parse_cfets_date(str(raw_date or ""))
        raw = item.get(sid)
        if raw is None or raw == "":
            # Some payloads use lowercase keys.
            raw = item.get(sid.upper()) or item.get(sid.lower())
        if raw is None or raw == "":
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise CfetsChinamoneyError(
                f"records[{index}].{sid} non-numeric: {raw!r}"
            ) from exc
        out.append(WorldObservation(period=period, value=value))
    if not out:
        raise CfetsChinamoneyError(f"CFETS rate series had no numeric values for {sid}")
    out.sort(key=lambda item: item.period)
    return out


def _specs_from_national(series_specs: Sequence[Any]) -> list[CfetsSeriesSpec]:
    out: list[CfetsSeriesSpec] = []
    for row in series_specs or ():
        provider = str(getattr(row, "provider", "") or "").strip().lower()
        if provider and provider != "cfets":
            continue
        sid = getattr(row, "series_id", None)
        did = getattr(row, "dataset_id", None)
        if not sid or not did:
            continue
        out.append(
            CfetsSeriesSpec(
                series_id=str(sid),
                dataset_id=str(did),
                title=getattr(row, "name_en", None)
                or getattr(row, "name_ru", None)
                or getattr(row, "title", None),
                unit_code=str(getattr(row, "unit", None) or "UNIT"),
                frequency=str(getattr(row, "frequency", None) or "daily"),
                dimensions=dict(getattr(row, "dimensions", None) or {}),
                source_url=getattr(row, "source_url", None),
            )
        )
    return out


def create_adapter(
    *,
    series_specs: Sequence[Any] | None = None,
    **kwargs: Any,
) -> "CfetsChinamoneyAdapter":
    curated = _specs_from_national(series_specs or ()) if series_specs is not None else None
    return CfetsChinamoneyAdapter(curated or None, **kwargs)


class CfetsChinamoneyAdapter:
    """``WorldSourceAdapter`` for CFETS China Money JSON endpoints."""

    provider = "cfets"
    public_source_name = "China Foreign Exchange Trade System"

    def __init__(
        self,
        series: Sequence[CfetsSeriesSpec] | None = None,
        *,
        session: requests.Session | None = None,
        timeout: float = DEFAULT_TIMEOUT_SEC,
        base_url: str = CFETS_BASE,
        country_code: str = DEFAULT_COUNTRY_CODE,
        date_from: date | None = None,
    ) -> None:
        curated = tuple(series) if series is not None else DEFAULT_CFETS_SERIES
        if not curated:
            raise CfetsChinamoneyError(
                "CfetsChinamoneyAdapter requires at least one curated series"
            )
        self._session = session or requests.Session()
        self._timeout = timeout
        self._base_url = base_url.rstrip("/")
        self._country_code = country_code.strip().upper() or DEFAULT_COUNTRY_CODE
        self._date_from = date_from or _DEFAULT_DATE_FROM
        self._by_dataset: dict[str, list[CfetsSeriesSpec]] = {}
        self._by_series: dict[tuple[str, str], CfetsSeriesSpec] = {}
        for spec in curated:
            did = normalize_dataset_id(spec.dataset_id)
            sid = normalize_series_id(spec.series_id)
            normalized = CfetsSeriesSpec(
                series_id=sid,
                dataset_id=did,
                title=spec.title,
                unit_code=(spec.unit_code or "UNIT").strip().upper() or "UNIT",
                frequency=(spec.frequency or "daily").strip().lower() or "daily",
                dimensions=dict(spec.dimensions),
                source_url=spec.source_url,
            )
            self._by_dataset.setdefault(did, []).append(normalized)
            self._by_series[(did, sid)] = normalized

    async def list_datasets(self) -> AsyncIterator[WorldDatasetVersion]:
        for dataset_id, members in self._by_dataset.items():
            yield WorldDatasetVersion(
                provider=self.provider,
                dataset_id=dataset_id,
                title=members[0].title or dataset_id.upper(),
                metadata_url=f"{self._base_url}{_ENDPOINT_BY_DATASET[dataset_id]}",
            )

    async def list_series(
        self, dataset: WorldDatasetVersion
    ) -> AsyncIterator[WorldSeriesRef]:
        dataset_id = normalize_dataset_id(dataset.dataset_id)
        members = self._by_dataset.get(dataset_id)
        if not members:
            raise CfetsChinamoneyError(f"No curated CFETS series for {dataset_id!r}")
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
            raise CfetsChinamoneyError(
                f"Provider mismatch: expected {self.provider}, got {series.provider}"
            )
        dataset_id = normalize_dataset_id(series.dataset_id)
        series_id = normalize_series_id(series.series_id)
        start = date_from or self._date_from
        end = date_to or date.today()
        if end < start:
            raise CfetsChinamoneyError(
                f"date_to {end.isoformat()} before date_from {start.isoformat()}"
            )
        fetched_at = datetime.now(timezone.utc)
        payload_pages = await asyncio.to_thread(
            self._fetch_all_pages_sync,
            dataset_id,
            series_id=series_id,
            start=start,
            end=end,
        )
        observations = self._parse_merged(dataset_id, series_id, payload_pages)
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
                    "dataset": dataset_id,
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
        return WorldSeriesPayload(
            ref=series,
            observations=observations,
            fetched_at=fetched_at,
            revision_token=revision,
            source_hash=source_hash,
        )

    def _parse_merged(
        self,
        dataset_id: str,
        series_id: str,
        pages: Sequence[Mapping[str, Any]],
    ) -> list[WorldObservation]:
        by_period: dict[date, float] = {}
        for page in pages:
            if dataset_id == "ccpr":
                chunk = parse_ccpr_records(page, series_id=series_id)
            else:
                chunk = parse_keyed_rate_records(page, series_id=series_id)
            for obs in chunk:
                by_period[obs.period] = obs.value
        if not by_period:
            raise CfetsChinamoneyError(
                f"No observations for {dataset_id}/{series_id}"
            )
        return [
            WorldObservation(period=period, value=value)
            for period, value in sorted(by_period.items())
        ]

    def _fetch_all_pages_sync(
        self,
        dataset_id: str,
        *,
        series_id: str,
        start: date,
        end: date,
    ) -> list[dict[str, Any]]:
        # CFETS history endpoints often cap the window; walk year-sized chunks.
        pages: list[dict[str, Any]] = []
        cursor = start
        while cursor <= end:
            chunk_end = min(date(cursor.year, 12, 31), end)
            pages.extend(
                self._fetch_window_pages_sync(
                    dataset_id,
                    series_id=series_id,
                    start=cursor,
                    end=chunk_end,
                )
            )
            cursor = chunk_end + timedelta(days=1)
        if not pages:
            raise CfetsChinamoneyError(
                f"CFETS returned no pages for {dataset_id}/{series_id}"
            )
        return pages

    def _fetch_window_pages_sync(
        self,
        dataset_id: str,
        *,
        series_id: str,
        start: date,
        end: date,
    ) -> list[dict[str, Any]]:
        pages: list[dict[str, Any]] = []
        page_num = 1
        total_pages = 1
        while page_num <= total_pages:
            payload = self._get_page_sync(
                dataset_id,
                series_id=series_id,
                start=start,
                end=end,
                page_num=page_num,
            )
            pages.append(payload)
            data = payload.get("data") if isinstance(payload.get("data"), Mapping) else {}
            raw_total = (
                data.get("pageTotal")
                or data.get("totalPageNum")
                or payload.get("pageTotal")
            )
            try:
                total_pages = max(1, int(raw_total or 1))
            except (TypeError, ValueError):
                total_pages = 1
            page_num += 1
            if page_num > 50:
                break
        return pages

    def _get_page_sync(
        self,
        dataset_id: str,
        *,
        series_id: str,
        start: date,
        end: date,
        page_num: int,
    ) -> dict[str, Any]:
        path = _ENDPOINT_BY_DATASET[dataset_id]
        url = f"{self._base_url}{path}"
        params: dict[str, str | int] = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "pageNum": page_num,
            "pageSize": _PAGE_SIZE,
        }
        if dataset_id == "ccpr":
            params["currency"] = series_id
        elif dataset_id == "lpr":
            params["lang"] = "EN"
        try:
            response = self._session.get(
                url,
                params=params,
                timeout=self._timeout,
                headers={
                    "Accept": "application/json,text/plain,*/*",
                    "User-Agent": _USER_AGENT,
                    "Referer": f"{self._base_url}/english/",
                },
            )
        except requests.RequestException as exc:
            raise CfetsChinamoneyError(f"CFETS GET {url} failed: {exc}") from exc
        if response.status_code >= 400:
            raise CfetsChinamoneyError(
                f"CFETS GET {url} HTTP {response.status_code}: {response.text[:300]}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise CfetsChinamoneyError(
                f"CFETS GET {url} non-JSON: {response.text[:300]}"
            ) from exc
        if not isinstance(payload, dict):
            raise CfetsChinamoneyError(
                f"CFETS payload must be an object, got {type(payload)!r}"
            )
        head = payload.get("head")
        if isinstance(head, Mapping):
            rep = str(head.get("rep_code") or "")
            if rep and rep not in {"200", "0"}:
                raise CfetsChinamoneyError(
                    f"CFETS error rep_code={rep}: {head.get('rep_message')}"
                )
        return payload

    def _series_ref(self, spec: CfetsSeriesSpec) -> WorldSeriesRef:
        return WorldSeriesRef(
            provider=self.provider,
            dataset_id=spec.dataset_id,
            series_id=spec.series_id,
            country_code=self._country_code,
            frequency=spec.frequency,
            unit_code=spec.unit_code,
            dimensions=dict(spec.dimensions),
            title=spec.title,
            source_url=spec.source_url
            or f"{self._base_url}{_ENDPOINT_BY_DATASET[spec.dataset_id]}",
        )

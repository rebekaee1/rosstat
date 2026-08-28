"""National Bureau of Statistics of China (NBS) adapter.

Legacy EasyQuery (``easyquery.htm``) is geo/WAF-blocked from many overseas
IPs (HTTP 403 UrlACL). The live public path is the UUID stream API::

    POST .../dg/website/publicrelease/web/external/stream/esData

Body (nbsc / SPA contract)::

    {
      "cid": "<leaf catalog uuid>",
      "indicatorIds": ["<indicator uuid>"],
      "daCatalogId": "",
      "das": [{"text": "全国", "value": "000000000000"}],
      "showType": "1",
      "dts": ["202101MM-202612MM"],
      "rootId": "<monthly|quarterly root uuid>"
    }

Overseas ingest: set ``ALL_PROXY`` / ``HTTPS_PROXY`` to ``socks5://host:port``
(prefer ``socks5`` over ``socks5h`` so local DNS resolves A records; AAAA via
remote DNS often breaks NBS). The adapter also forces AF_INET when a proxy is
configured.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import socket
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, AsyncIterator, Mapping, Sequence

import requests
import urllib3.util.connection as urllib3_cn

from app.services.world_source_adapter import (
    WorldDatasetVersion,
    WorldObservation,
    WorldSeriesPayload,
    WorldSeriesRef,
)

logger = logging.getLogger(__name__)

NBS_EASYQUERY = "https://data.stats.gov.cn/easyquery.htm"
NBS_EASYQUERY_EN = "https://data.stats.gov.cn/english/easyquery.htm"
NBS_STREAM = (
    "https://data.stats.gov.cn/dg/website/publicrelease/web/external/stream/esData"
)
NBS_STREAM_LEGACY = (
    "https://data.stats.gov.cn/dg/website/publicrelease/web/external/"
    "getEsDataByCidAndDt"
)
NBS_PAGE = "https://data.stats.gov.cn/dg/website/page.html"
ROOT_MONTHLY = "fc982599aa684be7969d7b90b1bd0e84"
ROOT_QUARTERLY = "a94b8b7365a94874968cabbe392cf679"
DEFAULT_TIMEOUT_SEC = 90
DEFAULT_COUNTRY_CODE = "CN"
_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_PERIOD_MONTH = re.compile(r"^(\d{4})(A|0[1-9]|1[0-2])$", re.IGNORECASE)
_PERIOD_QUARTER = re.compile(r"^(\d{4})([A-D])$", re.IGNORECASE)
_PERIOD_YEAR = re.compile(r"^(\d{4})$")
_STREAM_CODE = re.compile(r"^(\d{4})(\d{2})?(MM|SS|A)?$", re.IGNORECASE)

_DBCODE_FREQ: dict[str, str] = {
    "hgyd": "monthly",
    "hgjd": "quarterly",
    "hgnd": "annual",
}

# Multi-leaf stream map (mbk-dev/nbsc codes.json, verified 2026-08-12).
# Keyed by legacy zb code AND by our national code_suffix aliases.
STREAM_SERIES: dict[str, dict[str, Any]] = {
    # CPI YoY index (same month previous year = 100)
    "A01010G01": {
        "frequency": "monthly",
        "root_id": ROOT_MONTHLY,
        "leaves": [
            {
                "cid": "5c7452825c7c4dcba391db5ca7f335c5",
                "indicator_id": "53180dfb9c14411ba4b762307c85920c",
                "year_start": 2026,
                "year_end": None,
            },
            {
                "cid": "809d2522b0fe4be89142650341b19083",
                "indicator_id": "4ae9047687934a6390984c21d6ddab96",
                "year_start": 2021,
                "year_end": 2025,
            },
            {
                "cid": "9d4eec43537742a7ab5d63db97fa2f51",
                "indicator_id": "e5c318ffdbbc4d38898e52b52267eb25",
                "year_start": 2016,
                "year_end": 2020,
            },
            {
                "cid": "954cfd7597e34b919ec71caf6aeead51",
                "indicator_id": "4c1065dd4e984b25a21190c843551697",
                "year_start": 1987,
                "year_end": 2015,
            },
        ],
    },
    "cpi-all": "A01010G01",
    "A01030101": "A01010G01",  # YAML historically pointed at MoM code; map to YoY
    "UNEMPLOYMENT": {
        "frequency": "monthly",
        "root_id": ROOT_MONTHLY,
        "leaves": [
            {
                "cid": "ee3b7046b390415b9b7745e3d16f6052",
                "indicator_id": "3888eac6062945a79c8a27e5f13d4953",
                "year_start": 2018,
                "year_end": None,
            },
        ],
    },
    "A0E0101": "UNEMPLOYMENT",
    "urban-unemployment": "UNEMPLOYMENT",
    "GDP_REAL_Q": {
        "frequency": "quarterly",
        "root_id": ROOT_QUARTERLY,
        "leaves": [
            {
                "cid": "b676631776424600bdae363df047559f",
                "indicator_id": "b704155cd926437b8ee9c65fe058210d",
                "year_start": 2011,
                "year_end": None,
            },
        ],
    },
    "A0101": "GDP_REAL_Q",
    "gdp-real": "GDP_REAL_Q",
}


class NbsStatsError(RuntimeError):
    """Raised when NBS returns an unusable or blocked payload."""


@dataclass(frozen=True)
class NbsSeriesSpec:
    series_id: str
    dataset_id: str
    title: str | None = None
    unit_code: str = "UNIT"
    frequency: str | None = None
    dimensions: Mapping[str, str] = field(default_factory=dict)
    source_url: str | None = None


DEFAULT_NBS_SERIES: tuple[NbsSeriesSpec, ...] = (
    NbsSeriesSpec(
        series_id="A01010G01",
        dataset_id="hgyd",
        title="Consumer Price Index (same month previous year = 100)",
        unit_code="INDEX",
        frequency="monthly",
        dimensions={"transport": "stream"},
    ),
)


def normalize_dataset_id(raw: str) -> str:
    text = (raw or "").strip().lower()
    if not text:
        raise NbsStatsError("Empty NBS dataset_id / dbcode")
    return text


def normalize_series_id(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise NbsStatsError("Empty NBS series_id / indicator code")
    # Keep mixed-case aliases (cpi-all); upper-case legacy zb codes.
    if text.replace("-", "").isalnum() and "-" in text:
        return text.lower()
    return text.upper() if text[:1].isalpha() and text[0].isupper() or text[0] == "A" else text


def resolve_stream_entry(series_key: str) -> dict[str, Any] | None:
    key = (series_key or "").strip()
    if not key:
        return None
    candidates = [key, key.upper(), key.lower()]
    for cand in candidates:
        entry = STREAM_SERIES.get(cand)
        if entry is None:
            continue
        if isinstance(entry, str):
            entry = STREAM_SERIES.get(entry)
        if isinstance(entry, dict):
            return entry
    return None


def parse_nbs_period(raw: str, *, frequency: str | None = None) -> date:
    text = (raw or "").strip().upper()
    if not text:
        raise NbsStatsError("Empty NBS time code")
    m = _PERIOD_MONTH.match(text)
    if m and m.group(2) != "A":
        year = int(m.group(1))
        month = int(m.group(2))
        return date(year, month, 1)
    m = _PERIOD_QUARTER.match(text)
    if m:
        year = int(m.group(1))
        quarter = "ABCD".index(m.group(2)) + 1
        return date(year, quarter * 3 - 2, 1)
    if text.endswith("A") and len(text) == 5 and text[:4].isdigit():
        return date(int(text[:4]), 1, 1)
    m = _PERIOD_YEAR.match(text)
    if m:
        return date(int(m.group(1)), 1, 1)
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise NbsStatsError(f"Unparseable NBS period: {raw!r}") from exc


def parse_stream_period_code(raw: str, *, frequency: str | None = None) -> date | None:
    """Parse stream codes like ``202401MM`` / ``202601SS`` / ``2026A``."""
    text = (raw or "").strip().upper()
    if not text:
        return None
    m = _STREAM_CODE.match(text)
    if not m:
        try:
            return parse_nbs_period(text, frequency=frequency)
        except NbsStatsError:
            return None
    year = int(m.group(1))
    mid = m.group(2)
    suffix = (m.group(3) or "").upper()
    freq = (frequency or "").lower()
    if suffix == "SS" or freq == "quarterly":
        q = int(mid or "1")
        if not 1 <= q <= 4:
            return None
        return date(year, q * 3 - 2, 1)
    if suffix in {"", "A"} and mid is None:
        return date(year, 1, 1)
    month = int(mid or "1")
    if not 1 <= month <= 12:
        return None
    return date(year, month, 1)


def parse_easyquery_observations(
    payload: Mapping[str, Any],
    *,
    frequency: str | None = None,
) -> list[WorldObservation]:
    """Parse NBS EasyQuery ``returndata`` into observations."""
    returndata = payload.get("returndata")
    if not isinstance(returndata, Mapping):
        if payload.get("returncode") not in (None, 200, "200"):
            raise NbsStatsError(
                f"NBS EasyQuery error returncode={payload.get('returncode')}"
            )
        raise NbsStatsError("NBS EasyQuery payload missing returndata")

    datanodes = returndata.get("datanodes")
    if not isinstance(datanodes, list) or not datanodes:
        raise NbsStatsError("NBS EasyQuery datanodes empty")

    out: list[WorldObservation] = []
    for node in datanodes:
        if not isinstance(node, Mapping):
            continue
        wds = node.get("wds")
        time_code = None
        if isinstance(wds, list):
            for dim in wds:
                if isinstance(dim, Mapping) and str(dim.get("wdcode") or "").lower() == "sj":
                    time_code = str(dim.get("valuecode") or "")
                    break
        if not time_code:
            code = str(node.get("code") or "")
            if "." in code:
                time_code = code.split(".")[-1]
        if not time_code:
            continue
        data = node.get("data")
        raw_value = None
        if isinstance(data, Mapping):
            raw_value = data.get("data")
            if raw_value in (None, "", "-"):
                raw_value = data.get("strdata")
        if raw_value in (None, "", "-", "…"):
            continue
        try:
            value = float(str(raw_value).replace(",", ""))
        except (TypeError, ValueError):
            continue
        period = parse_nbs_period(time_code, frequency=frequency)
        out.append(WorldObservation(period=period, value=value))

    if not out:
        raise NbsStatsError("NBS EasyQuery had no numeric observations")
    out.sort(key=lambda item: item.period)
    return out


def parse_stream_observations(
    payload: Mapping[str, Any],
    *,
    frequency: str | None = None,
) -> list[WorldObservation]:
    """Parse ``stream/esData`` JSON (state=20000) into observations."""
    state = payload.get("state")
    if state not in (None, 20000, "20000"):
        raise NbsStatsError(
            f"NBS stream state={state} message={payload.get('message')!r}"
        )
    blocks = payload.get("data")
    if not isinstance(blocks, list):
        raise NbsStatsError("NBS stream payload missing data[]")

    out: list[WorldObservation] = []
    for block in blocks:
        if not isinstance(block, Mapping):
            continue
        period = parse_stream_period_code(
            str(block.get("code") or ""), frequency=frequency
        )
        if period is None:
            continue
        values = block.get("values")
        if not isinstance(values, list) or not values:
            continue
        raw = None
        for entry in values:
            if isinstance(entry, Mapping) and entry.get("value") not in (None, ""):
                raw = entry.get("value")
                break
        if raw in (None, "", "-", "…"):
            continue
        try:
            value = float(str(raw).replace(",", ""))
        except (TypeError, ValueError):
            continue
        out.append(WorldObservation(period=period, value=value))

    out.sort(key=lambda item: item.period)
    return out


def _proxy_from_env() -> str | None:
    for key in ("ALL_PROXY", "HTTPS_PROXY", "HTTP_PROXY", "all_proxy", "https_proxy", "http_proxy"):
        raw = (os.environ.get(key) or "").strip()
        if raw:
            # Prefer local DNS (socks5) over remote (socks5h) for NBS IPv4.
            if raw.startswith("socks5h://"):
                return "socks5://" + raw[len("socks5h://") :]
            return raw
    return None


def _force_ipv4() -> None:
    urllib3_cn.allowed_gai_family = lambda: socket.AF_INET  # type: ignore[assignment]


def _dts_for_leaf(
    *,
    frequency: str,
    year_start: int,
    year_end: int | None,
) -> str:
    end = year_end or date.today().year
    start = year_start
    if frequency == "quarterly":
        return f"{start:04d}01SS-{end:04d}04SS"
    if frequency == "annual":
        return f"{start:04d}A-{end:04d}A"
    return f"{start:04d}01MM-{end:04d}12MM"


def _specs_from_national(series_specs: Sequence[Any]) -> list[NbsSeriesSpec]:
    out: list[NbsSeriesSpec] = []
    for row in series_specs or ():
        provider = str(getattr(row, "provider", "") or "").strip().lower()
        if provider and provider != "nbs":
            continue
        sid = getattr(row, "series_id", None)
        did = getattr(row, "dataset_id", None)
        if not sid or not did:
            continue
        dims = dict(getattr(row, "dimensions", None) or {})
        # Prefer stream whenever we know the leaf map.
        if resolve_stream_entry(str(sid)) or resolve_stream_entry(
            str(getattr(row, "code_suffix", "") or "")
        ):
            dims.setdefault("transport", "stream")
            suffix = str(getattr(row, "code_suffix", "") or "").strip()
            if suffix:
                dims.setdefault("code_suffix", suffix)
        out.append(
            NbsSeriesSpec(
                series_id=str(sid),
                dataset_id=str(did),
                title=getattr(row, "name_en", None)
                or getattr(row, "name_ru", None)
                or getattr(row, "title", None),
                unit_code=str(getattr(row, "unit", None) or "UNIT"),
                frequency=getattr(row, "frequency", None),
                dimensions=dims,
                source_url=getattr(row, "source_url", None),
            )
        )
    return out


def create_adapter(
    *,
    series_specs: Sequence[Any] | None = None,
    **kwargs: Any,
) -> "NbsStatsAdapter":
    curated = _specs_from_national(series_specs or ()) if series_specs is not None else None
    return NbsStatsAdapter(curated or None, **kwargs)


class NbsStatsAdapter:
    """``WorldSourceAdapter`` for NBS National Data (stream-first)."""

    provider = "nbs"
    public_source_name = "National Bureau of Statistics of China"

    def __init__(
        self,
        series: Sequence[NbsSeriesSpec] | None = None,
        *,
        session: requests.Session | None = None,
        timeout: float = DEFAULT_TIMEOUT_SEC,
        country_code: str = DEFAULT_COUNTRY_CODE,
        easyquery_urls: Sequence[str] | None = None,
        proxy: str | None = None,
    ) -> None:
        curated = tuple(series) if series is not None else DEFAULT_NBS_SERIES
        if not curated:
            raise NbsStatsError("NbsStatsAdapter requires at least one curated series")
        self._timeout = timeout
        self._country_code = country_code.strip().upper() or DEFAULT_COUNTRY_CODE
        self._easyquery_urls = tuple(
            easyquery_urls or (NBS_EASYQUERY, NBS_EASYQUERY_EN)
        )
        self._proxy = proxy if proxy is not None else _proxy_from_env()
        if self._proxy:
            _force_ipv4()
        self._session = session or requests.Session()
        if session is None and self._proxy:
            self._session.trust_env = False
            self._session.proxies = {"http": self._proxy, "https": self._proxy}
        self._warmed = False
        self._by_dataset: dict[str, list[NbsSeriesSpec]] = {}
        self._by_key: dict[tuple[str, str], NbsSeriesSpec] = {}
        for spec in curated:
            did = normalize_dataset_id(spec.dataset_id)
            sid = str(spec.series_id).strip()
            freq = (
                (spec.frequency or _DBCODE_FREQ.get(did) or "monthly").strip().lower()
            )
            normalized = NbsSeriesSpec(
                series_id=sid,
                dataset_id=did,
                title=spec.title,
                unit_code=(spec.unit_code or "UNIT").strip().upper() or "UNIT",
                frequency=freq,
                dimensions=dict(spec.dimensions),
                source_url=spec.source_url,
            )
            self._by_dataset.setdefault(did, []).append(normalized)
            self._by_key[(did, sid)] = normalized
            self._by_key[(did, sid.upper())] = normalized
            self._by_key[(did, sid.lower())] = normalized

    async def list_datasets(self) -> AsyncIterator[WorldDatasetVersion]:
        for dataset_id, members in self._by_dataset.items():
            yield WorldDatasetVersion(
                provider=self.provider,
                dataset_id=dataset_id,
                title=members[0].title or dataset_id,
                metadata_url=NBS_PAGE,
            )

    async def list_series(
        self, dataset: WorldDatasetVersion
    ) -> AsyncIterator[WorldSeriesRef]:
        dataset_id = normalize_dataset_id(dataset.dataset_id)
        members = self._by_dataset.get(dataset_id)
        if not members:
            raise NbsStatsError(f"No curated NBS series for dataset_id={dataset_id!r}")
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
            raise NbsStatsError(
                f"Provider mismatch: expected {self.provider}, got {series.provider}"
            )
        dataset_id = normalize_dataset_id(series.dataset_id)
        series_id = str(series.series_id).strip()
        spec = (
            self._by_key.get((dataset_id, series_id))
            or self._by_key.get((dataset_id, series_id.upper()))
            or self._by_key.get((dataset_id, series_id.lower()))
        )
        dims = dict(series.dimensions or (spec.dimensions if spec else {}))
        fetched_at = datetime.now(timezone.utc)
        frequency = (series.frequency or (spec.frequency if spec else None) or "monthly")

        stream_key = (
            dims.get("stream_code")
            or dims.get("code_suffix")
            or series_id
        )
        use_stream = (
            dims.get("transport", "").lower() == "stream"
            or dims.get("catalog_id")
            or resolve_stream_entry(stream_key) is not None
        )

        if use_stream:
            observations = await asyncio.to_thread(
                self._fetch_stream_merged,
                stream_key=stream_key,
                dims=dims,
                frequency=frequency,
            )
        else:
            payload = await asyncio.to_thread(
                self._post_easyquery_sync,
                dbcode=dataset_id,
                indicator_code=normalize_series_id(series_id),
            )
            observations = parse_easyquery_observations(
                payload, frequency=frequency
            )

        if date_from is not None:
            observations = [o for o in observations if o.period >= date_from]
        if date_to is not None:
            observations = [o for o in observations if o.period <= date_to]
        if not observations:
            raise NbsStatsError(
                f"NBS observations empty after date filter for {series_id}"
            )

        revision = (
            f"{observations[0].period.isoformat()}"
            f"/{observations[-1].period.isoformat()}"
            f"#{len(observations)}"
        )
        source_hash = hashlib.sha256(
            json.dumps(
                {
                    "dbcode": dataset_id,
                    "zb": series_id,
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

    def _warmup_sync(self) -> None:
        if self._warmed:
            return
        try:
            self._session.get(
                NBS_PAGE,
                timeout=self._timeout,
                headers={"User-Agent": _USER_AGENT, "Accept": "text/html,*/*"},
            )
        except requests.RequestException as exc:
            logger.warning("NBS cookie warmup failed: %s", exc)
        self._warmed = True

    def _fetch_stream_merged(
        self,
        *,
        stream_key: str,
        dims: Mapping[str, str],
        frequency: str,
    ) -> list[WorldObservation]:
        self._warmup_sync()
        entry = resolve_stream_entry(stream_key)
        leaves: list[Mapping[str, Any]]
        root_id: str
        freq = frequency
        if entry is not None:
            leaves = list(entry["leaves"])
            root_id = str(entry.get("root_id") or ROOT_MONTHLY)
            freq = str(entry.get("frequency") or frequency)
        elif dims.get("catalog_id") and dims.get("indicator_id"):
            leaves = [
                {
                    "cid": dims["catalog_id"],
                    "indicator_id": dims["indicator_id"],
                    "year_start": int(dims.get("year_start") or 1990),
                    "year_end": (
                        int(dims["year_end"]) if dims.get("year_end") else None
                    ),
                }
            ]
            root_id = dims.get("root_id") or (
                ROOT_QUARTERLY if freq == "quarterly" else ROOT_MONTHLY
            )
        else:
            raise NbsStatsError(
                f"No NBS stream leaf map for key={stream_key!r}; "
                "set dimensions.catalog_id/indicator_id or STREAM_SERIES entry"
            )

        merged: dict[date, float] = {}
        errors: list[str] = []
        for leaf in leaves:
            cid = str(leaf.get("cid") or "")
            indicator_id = str(leaf.get("indicator_id") or "")
            year_start = int(leaf.get("year_start") or 1990)
            year_end = leaf.get("year_end")
            year_end_i = int(year_end) if year_end not in (None, "") else None
            dts = _dts_for_leaf(
                frequency=freq, year_start=year_start, year_end=year_end_i
            )
            try:
                payload = self._post_stream_sync(
                    catalog_id=cid,
                    indicator_id=indicator_id,
                    dts=dts,
                    root_id=root_id,
                )
                chunk = parse_stream_observations(payload, frequency=freq)
            except NbsStatsError as exc:
                errors.append(f"{cid}/{indicator_id}: {exc}")
                continue
            for obs in chunk:
                # Prefer earlier leaf on overlap (historical segments first in map
                # are newer — keep first-seen = newer leaf wins if we iterate new→old).
                if obs.period not in merged:
                    merged[obs.period] = obs.value

        if not merged:
            raise NbsStatsError(
                f"NBS stream empty for {stream_key}: " + "; ".join(errors[:4])
            )
        out = [
            WorldObservation(period=period, value=value)
            for period, value in sorted(merged.items())
        ]
        return out

    def _post_easyquery_sync(
        self,
        *,
        dbcode: str,
        indicator_code: str,
    ) -> dict[str, Any]:
        form = {
            "m": "QueryData",
            "dbcode": dbcode,
            "rowcode": "zb",
            "colcode": "sj",
            "wds": "[]",
            "dfwds": json.dumps(
                [{"wdcode": "zb", "valuecode": indicator_code}],
                separators=(",", ":"),
            ),
            "k1": str(int(time.time() * 1000)),
        }
        errors: list[str] = []
        for url in self._easyquery_urls:
            try:
                response = self._session.post(
                    url,
                    data=form,
                    timeout=self._timeout,
                    headers={
                        "User-Agent": _USER_AGENT,
                        "Accept": "application/json,text/javascript,*/*",
                        "Referer": url,
                        "X-Requested-With": "XMLHttpRequest",
                    },
                )
            except requests.RequestException as exc:
                errors.append(f"{url}: {exc}")
                continue
            if response.status_code >= 400:
                errors.append(f"{url}: HTTP {response.status_code}")
                continue
            try:
                payload = response.json()
            except ValueError:
                errors.append(f"{url}: non-JSON ({response.text[:120]!r})")
                continue
            if not isinstance(payload, dict):
                errors.append(f"{url}: unexpected payload type")
                continue
            return payload
        raise NbsStatsError(
            "NBS EasyQuery unreachable from this network "
            f"(indicator={indicator_code}, dbcode={dbcode}): "
            + "; ".join(errors[:4])
        )

    def _post_stream_sync(
        self,
        *,
        catalog_id: str,
        indicator_id: str,
        dts: str,
        root_id: str,
    ) -> dict[str, Any]:
        body = {
            "cid": catalog_id,
            "indicatorIds": [indicator_id],
            "daCatalogId": "",
            "das": [{"text": "全国", "value": "000000000000"}],
            "showType": "1",
            "dts": [dts],
            "rootId": root_id,
        }
        headers = {
            "User-Agent": _USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Referer": NBS_PAGE,
            "Origin": "https://data.stats.gov.cn",
        }
        errors: list[str] = []
        for url in (NBS_STREAM, NBS_STREAM_LEGACY):
            try:
                response = self._session.post(
                    url,
                    json=body,
                    timeout=self._timeout,
                    headers=headers,
                )
            except requests.RequestException as exc:
                errors.append(f"{url}: {exc}")
                continue
            if response.status_code in (404, 405):
                errors.append(f"{url}: HTTP {response.status_code}")
                continue
            if response.status_code >= 400:
                errors.append(f"{url}: HTTP {response.status_code} {response.text[:160]}")
                continue
            try:
                payload = response.json()
            except ValueError as exc:
                errors.append(f"{url}: non-JSON ({response.text[:160]!r})")
                continue
            if not isinstance(payload, dict):
                errors.append(f"{url}: payload type {type(payload)!r}")
                continue
            return payload
        raise NbsStatsError(
            f"NBS stream POST failed for {catalog_id}/{indicator_id}: "
            + "; ".join(errors[:4])
        )

    def _series_ref(self, spec: NbsSeriesSpec) -> WorldSeriesRef:
        return WorldSeriesRef(
            provider=self.provider,
            dataset_id=spec.dataset_id,
            series_id=spec.series_id,
            country_code=self._country_code,
            frequency=(spec.frequency or "monthly"),
            unit_code=spec.unit_code,
            dimensions=dict(spec.dimensions),
            title=spec.title,
            source_url=spec.source_url or NBS_PAGE,
        )

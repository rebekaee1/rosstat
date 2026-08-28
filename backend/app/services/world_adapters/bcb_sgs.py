"""Banco Central do Brasil SGS (Sistema Gerenciador de Séries Temporais) adapter.

Official JSON API (no auth)::

    GET https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados
        ?formato=json
        &dataInicial=DD/MM/YYYY
        &dataFinal=DD/MM/YYYY

    GET …/dados/ultimos/{N}?formato=json

Confirmed live national-core series (probed 2026-08-12):

- ``433`` — IPCA monthly % change
- ``13522`` — IPCA 12-month accumulated %
- ``24369`` — unemployment rate (PNAD Contínua via BCB)
- ``22109`` — real GDP chain index, seasonally adjusted
- ``432`` — Selic target (meta)
- ``1`` — USD/BRL free rate (sale)
- ``21859`` — industrial production index
- ``1455`` — retail sales volume index
- ``24364`` — IBC-Br seasonally adjusted

``WorldSeriesRef.dataset_id`` equals the SGS series code (one series per
dataset). Country code is always ``BR``. Dates arrive as ``DD/MM/YYYY``.
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

SGS_BASE = "https://api.bcb.gov.br/dados/serie"
DEFAULT_TIMEOUT_SEC = 60
DEFAULT_RECENT_N = 10_000
DEFAULT_COUNTRY_CODE = "BR"
_DEFAULT_DATE_FROM = date(1900, 1, 1)
# BCB daily series: max query window is 10 years (HTTP 406 otherwise).
_DAILY_MAX_SPAN_DAYS = 3650


def _date_windows(start: date, end: date, *, max_span_days: int) -> list[tuple[date, date]]:
    """Inclusive date windows of at most ``max_span_days`` covering ``start..end``."""
    if end < start:
        return []
    span = max(1, int(max_span_days))
    out: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        # inclusive window length ≤ span days → last = cursor + (span - 1)
        chunk_end = min(end, date.fromordinal(cursor.toordinal() + span - 1))
        out.append((cursor, chunk_end))
        cursor = date.fromordinal(chunk_end.toordinal() + 1)
    return out


class BcbSgsError(RuntimeError):
    """Raised when SGS returns an unusable payload or HTTP error."""


@dataclass(frozen=True)
class BcbSeriesSpec:
    """Curated SGS series. ``dataset_id`` defaults to the numeric series code."""

    series_id: str
    dataset_id: str | None = None
    title: str | None = None
    unit_code: str = "UNIT"
    frequency: str = "monthly"
    dimensions: Mapping[str, str] = field(default_factory=dict)
    source_url: str | None = None


DEFAULT_BCB_SERIES: tuple[BcbSeriesSpec, ...] = (
    BcbSeriesSpec(
        series_id="433",
        title="IPCA — variação mensal",
        unit_code="PERCENT",
        frequency="monthly",
    ),
    BcbSeriesSpec(
        series_id="13522",
        title="IPCA — acumulado 12 meses",
        unit_code="PERCENT",
        frequency="monthly",
    ),
    BcbSeriesSpec(
        series_id="24369",
        title="Taxa de desocupação (PNAD Contínua)",
        unit_code="PERCENT",
        frequency="monthly",
    ),
    BcbSeriesSpec(
        series_id="22109",
        title="PIB — índice encadeado dessazonalizado",
        unit_code="INDEX",
        frequency="quarterly",
    ),
    BcbSeriesSpec(
        series_id="432",
        title="Meta Selic",
        unit_code="PERCENT",
        frequency="daily",
    ),
    BcbSeriesSpec(
        series_id="1",
        title="USD/BRL (venda)",
        unit_code="BRL",
        frequency="daily",
        dimensions={"quote": "USD", "base": "BRL"},
    ),
    BcbSeriesSpec(
        series_id="21859",
        title="Produção industrial — índice",
        unit_code="INDEX",
        frequency="monthly",
    ),
    BcbSeriesSpec(
        series_id="1455",
        title="Vendas no varejo — índice de volume",
        unit_code="INDEX",
        frequency="monthly",
    ),
    BcbSeriesSpec(
        series_id="24364",
        title="IBC-Br dessazonalizado",
        unit_code="INDEX",
        frequency="monthly",
    ),
)


def normalize_series_id(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise BcbSgsError("Empty BCB SGS series id")
    if not text.isdigit():
        raise BcbSgsError(f"BCB SGS series id must be numeric, got {raw!r}")
    return text


def normalize_dataset_id(raw: str | None, *, series_id: str) -> str:
    text = (raw or "").strip()
    return text or series_id


def observations_url(series_id: str, *, base_url: str = SGS_BASE) -> str:
    sid = normalize_series_id(series_id)
    return f"{base_url.rstrip('/')}/bcdata.sgs.{sid}/dados"


def recent_observations_url(
    series_id: str, n: int, *, base_url: str = SGS_BASE
) -> str:
    sid = normalize_series_id(series_id)
    if n <= 0:
        raise BcbSgsError(f"recent N must be > 0, got {n}")
    return f"{base_url.rstrip('/')}/bcdata.sgs.{sid}/dados/ultimos/{int(n)}"


def format_br_date(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def parse_observation_date(raw: str) -> date:
    text = (raw or "").strip()
    if not text:
        raise BcbSgsError("Empty SGS observation date")
    # Official shape: DD/MM/YYYY.
    parts = text.split("/")
    if len(parts) == 3:
        day_s, month_s, year_s = parts
        try:
            return date(int(year_s), int(month_s), int(day_s))
        except ValueError as exc:
            raise BcbSgsError(f"Unparseable SGS observation date: {raw!r}") from exc
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise BcbSgsError(f"Unparseable SGS observation date: {raw!r}") from exc


def parse_sgs_observations(payload: Any) -> list[WorldObservation]:
    """Parse SGS list ``[{"data": "DD/MM/YYYY", "valor": "1.23"}, …]``."""
    if not isinstance(payload, list):
        raise BcbSgsError(
            f"SGS payload must be a list, got {type(payload)!r}"
        )
    if not payload:
        raise BcbSgsError("SGS observations empty")

    observations: list[WorldObservation] = []
    for index, item in enumerate(payload):
        if not isinstance(item, Mapping):
            raise BcbSgsError(f"observations[{index}] is not an object")
        raw_value = item.get("valor")
        if raw_value is None or raw_value == "":
            continue
        try:
            value = float(str(raw_value).replace(",", "."))
        except (TypeError, ValueError) as exc:
            raise BcbSgsError(
                f"observations[{index}].valor non-numeric: {raw_value!r}"
            ) from exc
        period = parse_observation_date(str(item.get("data") or ""))
        observations.append(WorldObservation(period=period, value=value))

    if not observations:
        raise BcbSgsError("SGS observations had no numeric values")
    observations.sort(key=lambda item: item.period)
    return observations


class BcbSgsAdapter:
    """``WorldSourceAdapter`` for Banco Central do Brasil SGS."""

    provider = "bcb_sgs"
    public_source_name = "Banco Central do Brasil"

    def __init__(
        self,
        series: Sequence[BcbSeriesSpec] | None = None,
        *,
        session: requests.Session | None = None,
        timeout: float = DEFAULT_TIMEOUT_SEC,
        base_url: str = SGS_BASE,
        recent_n: int = DEFAULT_RECENT_N,
        country_code: str = DEFAULT_COUNTRY_CODE,
    ) -> None:
        curated = tuple(series) if series is not None else DEFAULT_BCB_SERIES
        if not curated:
            raise BcbSgsError(
                "BcbSgsAdapter requires at least one curated BcbSeriesSpec"
            )
        self._series = curated
        self._session = session or requests.Session()
        self._timeout = timeout
        self._base_url = base_url.rstrip("/")
        self._recent_n = recent_n
        self._country_code = country_code.strip().upper() or DEFAULT_COUNTRY_CODE
        self._by_dataset: dict[str, BcbSeriesSpec] = {}
        self._by_series_id: dict[str, BcbSeriesSpec] = {}
        for spec in self._series:
            sid = normalize_series_id(spec.series_id)
            did = normalize_dataset_id(spec.dataset_id, series_id=sid)
            normalized = BcbSeriesSpec(
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
                metadata_url=observations_url(spec.series_id, base_url=self._base_url),
            )

    async def list_series(
        self, dataset: WorldDatasetVersion
    ) -> AsyncIterator[WorldSeriesRef]:
        dataset_id = (dataset.dataset_id or "").strip()
        spec = self._by_dataset.get(dataset_id)
        if spec is None:
            raise BcbSgsError(
                f"No curated SGS series for dataset_id={dataset_id!r}"
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
            raise BcbSgsError(
                f"Provider mismatch: expected {self.provider}, got {series.provider}"
            )
        series_id = normalize_series_id(series.series_id)
        fetched_at = datetime.now(timezone.utc)

        start = date_from or _DEFAULT_DATE_FROM
        end = date_to or date.today()
        if end < start:
            raise BcbSgsError(
                f"date_to {end.isoformat()} is before date_from {start.isoformat()}"
            )

        freq = (series.frequency or "").strip().lower()
        # ``ultimos/{N}`` capped at N≤20 by BCB; prefer date windows.
        # Daily SGS series reject windows longer than 10 years (HTTP 406).
        if freq == "daily":
            windows = _date_windows(start, end, max_span_days=_DAILY_MAX_SPAN_DAYS)
        else:
            windows = [(start, end)]

        raw_rows: list[Any] = []
        for w_start, w_end in windows:
            try:
                chunk = await asyncio.to_thread(
                    self._get_observations_sync,
                    series_id,
                    start_date=w_start,
                    end_date=w_end,
                )
            except BcbSgsError as exc:
                # Empty / invalid historical windows (daily from 1900, HTML error pages).
                msg = str(exc)
                soft = (
                    "HTTP 404" in msg
                    or "Value(s) not found" in msg
                    or "non-JSON" in msg
                    or "Requisição inválida" in msg
                    or "Requisicao invalida" in msg
                )
                if soft:
                    logger.info(
                        "BCB SGS %s empty/invalid window %s..%s — skip",
                        series_id,
                        w_start.isoformat(),
                        w_end.isoformat(),
                    )
                    continue
                raise
            if isinstance(chunk, list):
                raw_rows.extend(chunk)
            elif chunk:
                raw_rows.append(chunk)

        if not raw_rows:
            raise BcbSgsError(
                f"SGS series {series_id} returned no observations "
                f"in {start.isoformat()}..{end.isoformat()}"
            )

        observations = parse_sgs_observations(raw_rows)
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
        curated = self._by_series_id.get(series_id)
        if curated and curated.title and not series.title:
            ref = WorldSeriesRef(
                provider=series.provider,
                dataset_id=series.dataset_id,
                series_id=series.series_id,
                country_code=series.country_code,
                frequency=series.frequency,
                unit_code=series.unit_code,
                dimensions=dict(series.dimensions),
                title=curated.title,
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

    def _get_json(self, url: str, *, params: Mapping[str, str] | None = None) -> Any:
        try:
            response = self._session.get(
                url,
                params=dict(params or {}),
                timeout=self._timeout,
                headers={"Accept": "application/json"},
            )
        except requests.RequestException as exc:
            raise BcbSgsError(f"SGS GET {url} failed: {exc}") from exc
        if response.status_code >= 400:
            raise BcbSgsError(
                f"SGS GET {url} HTTP {response.status_code}: {response.text[:300]}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise BcbSgsError(
                f"SGS GET {url} returned non-JSON: {response.text[:300]}"
            ) from exc

    def _get_observations_sync(
        self,
        series_id: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        recent: int | None = None,
    ) -> Any:
        if start_date is not None or end_date is not None:
            url = observations_url(series_id, base_url=self._base_url)
            params: dict[str, str] = {"formato": "json"}
            if start_date is not None:
                params["dataInicial"] = format_br_date(start_date)
            if end_date is not None:
                params["dataFinal"] = format_br_date(end_date)
            return self._get_json(url, params=params)

        n = recent if recent is not None else self._recent_n
        url = recent_observations_url(series_id, n, base_url=self._base_url)
        return self._get_json(url, params={"formato": "json"})

    def _series_ref(self, spec: BcbSeriesSpec) -> WorldSeriesRef:
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
            or observations_url(sid, base_url=self._base_url),
        )


def create_adapter(
    series_specs: Sequence[Any] | None = None,
) -> BcbSgsAdapter:
    """Factory for ``world_national_ingest.resolve_adapter``."""
    if not series_specs:
        return BcbSgsAdapter()
    curated: list[BcbSeriesSpec] = []
    for row in series_specs:
        if isinstance(row, BcbSeriesSpec):
            curated.append(row)
            continue
        provider = getattr(row, "provider", None) or (
            row.get("provider") if isinstance(row, Mapping) else None
        )
        if provider is not None and str(provider).strip().lower() not in {
            "bcb_sgs",
            "bcb",
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
            BcbSeriesSpec(
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
    return BcbSgsAdapter(curated or None)

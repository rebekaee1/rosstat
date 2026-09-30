"""Нормализованный контракт официальных источников мирового блока.

Адаптер отвечает только за каталог и извлечение исходных наблюдений. Перевод,
листинг, card grouping, derived-режимы и прогнозы работают уже над единым
контрактом и не знают особенностей Eurostat/BEA/IBGE/NBS.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import AsyncIterator, Iterable, Mapping, Protocol, Sequence


@dataclass(frozen=True)
class WorldDatasetVersion:
    provider: str
    dataset_id: str
    title: str | None = None
    data_updated_at: date | datetime | None = None
    structure_updated_at: date | datetime | None = None
    revision_token: str | None = None
    metadata_url: str | None = None


@dataclass(frozen=True)
class WorldSeriesRef:
    """Стабильная identity одного исходного ряда до привязки к стране."""

    provider: str
    dataset_id: str
    series_id: str
    country_code: str
    frequency: str
    unit_code: str
    dimensions: Mapping[str, str] = field(default_factory=dict)
    title: str | None = None
    source_url: str | None = None

    @property
    def slice_hash(self) -> str:
        payload = {
            "provider": self.provider.strip().lower(),
            "dataset_id": self.dataset_id.strip(),
            "series_id": self.series_id.strip(),
            "country_code": self.country_code.strip().upper(),
            "frequency": self.frequency.strip().lower(),
            "unit_code": self.unit_code.strip().upper(),
            "dimensions": {
                str(key).strip().lower(): str(value).strip()
                for key, value in sorted(self.dimensions.items())
            },
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class WorldObservation:
    period: date
    value: float
    status: str | None = None
    decimals: int | None = None


def validate_complete_coverage(
    *,
    is_complete: bool,
    coverage_start: date | None,
    coverage_end: date | None,
    periods: Iterable[date],
) -> tuple[date, date] | None:
    """Return an explicitly complete replacement window or reject its claim.

    Absence from a partial response is never a deletion instruction. Completeness
    is an adapter assertion about a declared interval, not something inferred
    from observed min/max dates, row count or successful HTTP status. Empty
    complete responses need a separate withdrawal contract; they cannot prune.
    """
    if type(is_complete) is not bool:
        raise ValueError("is_complete must be an explicit bool")
    if not is_complete:
        return None
    if type(coverage_start) is not date or type(coverage_end) is not date:
        raise ValueError("Complete coverage requires explicit start and end dates")
    if coverage_end < coverage_start:
        raise ValueError("Complete coverage end is before start")
    observed = tuple(periods)
    if not observed:
        raise ValueError("Empty complete coverage cannot authorize point removal")
    if any(not coverage_start <= period <= coverage_end for period in observed):
        raise ValueError("Observation is outside declared complete coverage")
    return coverage_start, coverage_end


@dataclass(frozen=True)
class WorldSeriesPayload:
    """Fetched observations; merge by default, bounded replacement only by opt-in.

    An adapter may set ``is_complete`` only after checking its source response
    covers every published observation in ``coverage_start..coverage_end``.
    Existing adapters make no such assertion and therefore preserve history.
    Transport/parse errors still raise; partial is not an error fallback.
    """

    ref: WorldSeriesRef
    observations: Sequence[WorldObservation]
    fetched_at: datetime
    revision_token: str | None = None
    etag: str | None = None
    source_hash: str | None = None
    is_complete: bool = False
    coverage_start: date | None = None
    coverage_end: date | None = None

    def __post_init__(self) -> None:
        validate_complete_coverage(
            is_complete=self.is_complete,
            coverage_start=self.coverage_start,
            coverage_end=self.coverage_end,
            periods=(observation.period for observation in self.observations),
        )


class WorldSourceAdapter(Protocol):
    """Минимальный provider contract; сети/пагинация остаются внутри адаптера."""

    provider: str
    public_source_name: str

    async def list_datasets(self) -> AsyncIterator[WorldDatasetVersion]:
        """Поток каталога с revision metadata, если источник его предоставляет."""
        ...

    async def list_series(self, dataset: WorldDatasetVersion) -> AsyncIterator[WorldSeriesRef]:
        """Нормализованные series identity и dimensions одного dataset."""
        ...

    async def fetch_series(
        self,
        series: WorldSeriesRef,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> WorldSeriesPayload:
        """Наблюдения с provenance; значения без product-side преобразований."""
        ...

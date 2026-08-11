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
from typing import AsyncIterator, Mapping, Protocol, Sequence


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


@dataclass(frozen=True)
class WorldSeriesPayload:
    ref: WorldSeriesRef
    observations: Sequence[WorldObservation]
    fetched_at: datetime
    revision_token: str | None = None
    etag: str | None = None
    source_hash: str | None = None


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

"""Fail-closed policy мировых прогнозов.

Новый официальный provider не получает прогнозы автоматически: его код надо
явно добавить в OFFICIAL_PROVIDER_POLICIES после проверки адаптера и семантики
частот. Quality gate затем решает судьбу каждого конкретного ряда отдельно.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class ProviderForecastPolicy:
    provider: str
    strategies: dict[str, str]
    min_points: dict[str, int]
    horizons: dict[str, int]
    seasons: dict[str, int]
    max_age_days: dict[str, int]


@dataclass(frozen=True)
class WorldForecastEligibility:
    provider: str
    dataset_id: str
    unit: str
    frequency: str
    strategy: str
    min_points: int
    horizon: int
    season: int

    @property
    def registry_key(self) -> tuple[str, str, str, str, str]:
        return (
            self.provider,
            self.dataset_id,
            self.unit,
            self.frequency,
            self.strategy,
        )


# Только уже подключённый официальный Eurostat. BEA/BLS/IBGE/MOSPI/NBS будут
# добавлены отдельными строками после schema-probe и golden-series проверки.
OFFICIAL_PROVIDER_POLICIES: dict[str, ProviderForecastPolicy] = {
    "eurostat": ProviderForecastPolicy(
        provider="eurostat",
        strategies={
            "monthly": "monthly_auto",
            "quarterly": "quarterly_auto",
        },
        min_points={"monthly": 72, "quarterly": 32},
        horizons={"monthly": 12, "quarterly": 4},
        seasons={"monthly": 12, "quarterly": 4},
        max_age_days={"monthly": 150, "quarterly": 260},
    ),
}


def forecast_eligibility_for(
    indicator: Any,
    *,
    today: date | None = None,
) -> tuple[WorldForecastEligibility | None, str]:
    provider = str(getattr(indicator, "provider", "") or "").strip().lower()
    policy = OFFICIAL_PROVIDER_POLICIES.get(provider)
    if policy is None:
        return None, "provider_not_approved"

    frequency = str(getattr(indicator, "frequency", "") or "").strip().lower()
    strategy = policy.strategies.get(frequency)
    if strategy is None:
        return None, "frequency_not_supported"
    if not bool(getattr(indicator, "is_listed", False)):
        return None, "not_primary_public_series"
    if str(getattr(indicator, "name_quality", "") or "") not in {"curated", "composed"}:
        return None, "name_quality_gate"

    points_count = int(getattr(indicator, "points_count", 0) or 0)
    min_points = policy.min_points[frequency]
    if points_count < min_points:
        return None, "history_too_short"

    history_end = getattr(indicator, "history_end", None)
    today = today or date.today()
    if history_end is None:
        return None, "missing_history_end"
    if (today - history_end).days > policy.max_age_days[frequency]:
        return None, "series_is_stale"

    dataset_id = str(getattr(indicator, "dataset_id", "") or "").strip()
    if not dataset_id:
        return None, "missing_dataset_identity"
    return WorldForecastEligibility(
        provider=provider,
        dataset_id=dataset_id,
        unit=str(getattr(indicator, "unit", "") or "").strip(),
        frequency=frequency,
        strategy=strategy,
        min_points=min_points,
        horizon=policy.horizons[frequency],
        season=policy.seasons[frequency],
    ), "eligible"

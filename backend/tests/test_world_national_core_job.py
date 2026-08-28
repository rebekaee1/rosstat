"""Контракт ежедневного national-core job: паспорта полны, адаптеры резолвятся.

Падение любого пункта = планировщик 02:10 МСК молча пропустит часть рядов
(или упадёт на импорте) — проверяем без сети и БД.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.world_national_ingest import (
    NATIONAL_CORE_COUNTRIES,
    load_national_core_yaml,
    resolve_adapter,
)


def test_national_core_countries_cover_all_passports():
    core_dir = Path(__file__).resolve().parents[1] / "app" / "data" / "world_national_core"
    yaml_stems = {p.stem for p in core_dir.glob("*.yaml")}
    assert yaml_stems == set(NATIONAL_CORE_COUNTRIES), (
        "паспорт без страны в NATIONAL_CORE_COUNTRIES (или наоборот)",
    )


@pytest.mark.parametrize("country", NATIONAL_CORE_COUNTRIES)
def test_passport_loads_and_has_listed_series(country: str):
    manifest = load_national_core_yaml(country)
    assert manifest.country_code
    assert manifest.series, f"{country}: пустой паспорт"
    assert any(s.is_listed for s in manifest.series), (
        f"{country}: нет ни одного публичного ряда",
    )


@pytest.mark.parametrize("country", NATIONAL_CORE_COUNTRIES)
def test_passport_adapters_resolve_or_declare_key(country: str):
    """Каждый провайдер паспорта резолвится или честно требует ключ.

    ``AdapterUnavailable`` — валидный исход только для key-gated адаптеров
    (estat/e-Stat, ecos/Bank of Korea): их ряды в каталоге уже помечены
    ``world_dataset_state.status='error'`` и ждут ключи в .env.
    """
    from app.services.world_national_ingest import AdapterUnavailable

    manifest = load_national_core_yaml(country)
    for provider in {s.provider for s in manifest.series}:
        try:
            adapter = resolve_adapter(provider, series_specs=manifest.series)
        except AdapterUnavailable as exc:
            assert provider in _KEY_GATED, (
                f"{provider} поднял AdapterUnavailable без причины: {exc}",
            )
            continue
        assert adapter.provider == provider


_KEY_GATED = frozenset({"estat", "ecos"})

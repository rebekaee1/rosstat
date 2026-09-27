"""Контракт ежедневного national-core job: паспорта полны, адаптеры резолвятся.

Падение любого пункта = планировщик 02:10 МСК молча пропустит часть рядов
(или упадёт на импорте) — проверяем без сети и БД.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.services.world_adapters import close_http_resources
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
        close_http_resources(adapter)


_KEY_GATED = frozenset({"estat", "ecos"})


def test_committed_national_data_reports_cache_invalidation_failure(auth_env, monkeypatch):
    """A failed generation bump cannot leave the run or alert marked successful."""
    import app.core.cache as cache_mod
    import app.services.alerting as alerting
    import app.services.world_national_ingest as ingest_mod
    from app.models import WorldIngestRun
    from app.services.world_national_ingest import CountryIngestStats

    monkeypatch.setattr(ingest_mod, "async_session", auth_env["session_maker"])

    async def fake_ingest_country(db, country, *, dry_run):
        assert country == "us"
        assert dry_run is False
        return CountryIngestStats(
            country_code="US", series_ok=1, indicators_upserted=1,
            points_touched=2,
        )

    async def failed_bump(*namespaces):
        assert namespaces == ("world", "ssr-world", "world-catalog")
        raise cache_mod.WorldCatalogInvalidationError("state Redis unavailable")

    alerts = []

    async def capture_alert(source, **kwargs):
        alerts.append((source, kwargs))

    monkeypatch.setattr(ingest_mod, "ingest_country", fake_ingest_country)
    monkeypatch.setattr(cache_mod, "bump_namespaces", failed_bump)
    monkeypatch.setattr(alerting, "alert_world_ingest_summary", capture_alert)

    async def run_and_check():
        result = await ingest_mod.run_national_core_ingest(country_codes=["us"])
        async with auth_env["session_maker"]() as db:
            run = await db.get(WorldIngestRun, result["run_id"])
            assert run is not None
            assert run.status == "partial"
            assert run.datasets_succeeded == 1
            assert run.datasets_failed == 0
            assert "WorldCatalogInvalidationError" in (run.error_message or "")
        return result

    result = asyncio.run(run_and_check())
    assert result["failures"] == 0  # country ingest succeeded
    assert result["cache_invalidation_failed"] == 1
    assert len(alerts) == 1
    assert alerts[0][1]["status"] == "partial"
    assert alerts[0][1]["failed"] == 1
    assert "кэша каталога" in alerts[0][1]["details"]


@pytest.mark.parametrize("metadata_changed,points_removed", [(1, 0), (0, 1)])
def test_national_catalog_bumps_without_touched_points(
    auth_env, monkeypatch, metadata_changed, points_removed,
):
    """Metadata edits and source deletions invalidate even when no points are upserted."""
    import app.core.cache as cache_mod
    import app.services.alerting as alerting
    import app.services.world_national_ingest as ingest_mod
    from app.services.world_national_ingest import CountryIngestStats

    monkeypatch.setattr(ingest_mod, "async_session", auth_env["session_maker"])

    async def fake_ingest_country(db, country, *, dry_run):
        return CountryIngestStats(
            country_code="US", series_ok=1, indicators_upserted=1,
            metadata_changed=metadata_changed, points_removed=points_removed,
        )

    bumps = []

    async def capture_bump(*namespaces):
        bumps.append(namespaces)

    alerts = []

    async def capture_alert(source, **kwargs):
        alerts.append(kwargs)

    monkeypatch.setattr(ingest_mod, "ingest_country", fake_ingest_country)
    monkeypatch.setattr(cache_mod, "bump_namespaces", capture_bump)
    monkeypatch.setattr(alerting, "alert_world_ingest_summary", capture_alert)

    result = asyncio.run(ingest_mod.run_national_core_ingest(country_codes=["us"]))
    assert result["points_touched"] == 0
    assert result["metadata_changed"] == metadata_changed
    assert result["points_removed"] == points_removed
    assert bumps == [("world", "ssr-world", "world-catalog")]
    assert alerts[0]["status"] == "ok"
    assert alerts[0]["changed"] == 1

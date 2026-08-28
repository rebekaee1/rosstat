"""Unit tests for national-core YAML parse and indicator code builder."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.world_national_ingest import (
    AdapterUnavailable,
    PUBLIC_SOURCE_RU,
    build_indicator_code,
    core_yaml_path,
    load_national_core_yaml,
    normalize_national_frequency,
    public_source_for_provider,
    resolve_adapter,
    series_ref_from_spec,
)

CORE = Path(__file__).resolve().parents[1] / "app" / "data" / "world_national_core"

_AU_YAML_MINIMAL = """\
country_code: AU
series:
  - code_suffix: cpi-all
    name_ru: Индекс потребительских цен
    name_en: Consumer Price Index
    category_ru: Цены
    unit: INDEX
    unit_ru: индекс
    frequency: monthly
    provider: abs
    dataset_id: "6401.0"
    series_id: "A2325846C"
    is_listed: true
  - code_suffix: policy-rate
    name_ru: Учётная ставка
    name_en: Cash Rate Target
    category_ru: Деньги
    unit: PCT
    unit_ru: "%"
    frequency: daily
    provider: rba
    dataset_id: "F1"
    series_id: "FIRMMCRTD"
    is_listed: true
"""


def test_build_indicator_code_stable_and_bounded():
    assert build_indicator_code("CA", "cpi-all") == "ca-cpi-all"
    assert build_indicator_code("ca", "policy_rate") == "ca-policy-rate"
    assert build_indicator_code("CA", "FX-USD/CAD") == "ca-fx-usd-cad"
    assert build_indicator_code("AU", "cpi-all") == "au-cpi-all"
    assert build_indicator_code("au", "policy_rate") == "au-policy-rate"
    with pytest.raises(ValueError):
        build_indicator_code("CA", "x" * 130)


def test_normalize_national_frequency_aliases():
    assert normalize_national_frequency("M") == "monthly"
    assert normalize_national_frequency("quarterly") == "quarterly"
    assert normalize_national_frequency("yearly") == "annual"
    assert normalize_national_frequency("D") == "daily"


def test_core_yaml_path_resolves_ca_and_au():
    assert core_yaml_path("ca") == CORE / "ca.yaml"
    assert core_yaml_path("CA") == CORE / "ca.yaml"
    assert core_yaml_path("au") == CORE / "au.yaml"
    assert core_yaml_path("AU") == CORE / "au.yaml"
    assert core_yaml_path("us") == CORE / "us.yaml"
    assert core_yaml_path("US") == CORE / "us.yaml"
    assert core_yaml_path("au", base_dir=Path("/tmp/national")) == Path(
        "/tmp/national/au.yaml"
    )


def test_load_ca_yaml_stub_structure():
    path = CORE / "ca.yaml"
    assert path.is_file()
    assert core_yaml_path("ca") == path

    manifest = load_national_core_yaml("ca")
    assert manifest.country_code == "CA"
    assert len(manifest.series) >= 2

    by_suffix = {s.code_suffix: s for s in manifest.series}
    cpi = by_suffix["cpi-all"]
    assert cpi.provider == "statcan"
    assert cpi.series_id == "41690973"
    assert cpi.frequency == "monthly"
    assert cpi.is_listed is True
    assert "Статистическое управление Канады" in (cpi.methodology or "")

    rate = by_suffix["policy-rate"]
    assert rate.provider == "boc_valet"
    assert rate.series_id == "V39079"
    assert rate.frequency == "daily"
    assert "Банк Канады" in (rate.methodology or "")


def test_load_au_yaml_path_resolution(tmp_path: Path):
    """AU uses the same <cc>.yaml stem; codes are au-{suffix}."""
    yaml_path = tmp_path / "au.yaml"
    yaml_path.write_text(_AU_YAML_MINIMAL, encoding="utf-8")
    assert core_yaml_path("au", base_dir=tmp_path) == yaml_path

    manifest = load_national_core_yaml("au", base_dir=tmp_path)
    assert manifest.country_code == "AU"
    assert manifest.path == yaml_path
    assert len(manifest.series) == 2

    by_suffix = {s.code_suffix: s for s in manifest.series}
    assert by_suffix["cpi-all"].provider == "abs"
    assert by_suffix["policy-rate"].provider == "rba"
    assert build_indicator_code(manifest.country_code, "cpi-all") == "au-cpi-all"
    assert (
        build_indicator_code(manifest.country_code, "policy-rate") == "au-policy-rate"
    )


def test_load_au_yaml_population_scale():
    """AU-паспорт: население ABS ERP в лицах (value_scale 1000) и в crosswalk.

    ABS публикует ERP в тысячах человек, рейтинг концепта population —
    в лицах; множитель применяется на инжесте до записи точек.
    """
    from app.data.world_concept_national import national_codes_for_concept

    manifest = load_national_core_yaml("au")
    by_suffix = {s.code_suffix: s for s in manifest.series}
    pop = by_suffix["population"]
    assert pop.provider == "abs"
    assert pop.dataset_id == "ERP_COMP_Q"
    assert pop.series_id == "10.AUS.Q"
    assert pop.frequency == "quarterly"
    assert pop.unit == "PERSONS"
    assert pop.value_scale == 1000.0
    assert pop.is_listed is True
    assert "Австралийское бюро статистики" in (pop.methodology or "")
    assert "au-population" in national_codes_for_concept("population")


def test_value_scale_default_and_parse():
    """value_scale: дефолт 1.0; YAML-множитель читается, кривой — ValueError."""
    from app.services.world_national_ingest import _parse_series_row

    base = {
        "code_suffix": "x",
        "name_ru": "Тест",
        "category_ru": "Тест",
        "unit": "PERSONS",
        "unit_ru": "человек",
        "frequency": "annual",
        "provider": "abs",
        "dataset_id": "D",
        "series_id": "S",
    }
    spec = _parse_series_row(dict(base), index=0)
    assert spec.value_scale == 1.0
    spec = _parse_series_row({**base, "value_scale": 1000}, index=0)
    assert spec.value_scale == 1000.0
    with pytest.raises(ValueError):
        _parse_series_row({**base, "value_scale": "abc"}, index=0)


def test_public_source_ru_abs_rba_and_canada():
    assert PUBLIC_SOURCE_RU["abs"] == "Австралийское бюро статистики"
    assert PUBLIC_SOURCE_RU["rba"] == "Резервный банк Австралии"
    assert public_source_for_provider("abs") == "Австралийское бюро статистики"
    assert public_source_for_provider("rba") == "Резервный банк Австралии"
    assert public_source_for_provider("statcan") == "Статистическое управление Канады"
    assert public_source_for_provider("boc_valet") == "Банк Канады"
    assert PUBLIC_SOURCE_RU["fred"] == "Федеральный резервный банк Сент-Луиса"
    assert PUBLIC_SOURCE_RU["bls"] == "Бюро трудовой статистики США"
    assert PUBLIC_SOURCE_RU["bea"] == "Бюро экономического анализа США"
    assert public_source_for_provider("fred") == "Федеральный резервный банк Сент-Луиса"
    assert PUBLIC_SOURCE_RU["boj"] == "Банк Японии"
    assert PUBLIC_SOURCE_RU["estat"] == "Статистическое бюро Японии"
    assert PUBLIC_SOURCE_RU["ecos"] == "Банк Кореи"
    assert public_source_for_provider("boj") == "Банк Японии"
    assert public_source_for_provider("ecos") == "Банк Кореи"
    assert PUBLIC_SOURCE_RU["bcb_sgs"] == "Банк Бразилии"
    assert PUBLIC_SOURCE_RU["banxico_sie"] == "Банк Мексики"
    assert public_source_for_provider("bcb_sgs") == "Банк Бразилии"
    assert public_source_for_provider("banxico_sie") == "Банк Мексики"


def test_load_br_yaml_structure():
    path = CORE / "br.yaml"
    assert path.is_file()
    manifest = load_national_core_yaml("br")
    assert manifest.country_code == "BR"
    listed = [s for s in manifest.series if s.is_listed]
    assert len(listed) >= 6
    by_suffix = {s.code_suffix: s for s in manifest.series}
    assert by_suffix["cpi-ipca"].provider == "bcb_sgs"
    assert by_suffix["cpi-ipca"].series_id == "433"
    assert by_suffix["policy-rate"].series_id == "432"
    assert by_suffix["fx-usd-brl"].series_id == "1"
    assert by_suffix["unemployment-rate"].series_id == "24369"
    assert build_indicator_code("BR", "cpi-ipca") == "br-cpi-ipca"
    assert "Банк Бразилии" in (by_suffix["policy-rate"].methodology or "")


def test_load_mx_yaml_structure():
    path = CORE / "mx.yaml"
    assert path.is_file()
    manifest = load_national_core_yaml("mx")
    assert manifest.country_code == "MX"
    listed = [s for s in manifest.series if s.is_listed]
    assert len(listed) >= 6
    by_suffix = {s.code_suffix: s for s in manifest.series}
    assert by_suffix["cpi-all"].provider == "banxico_sie"
    assert by_suffix["cpi-all"].series_id == "SP1"
    assert by_suffix["policy-rate"].series_id == "SF61745"
    assert by_suffix["fx-usd-mxn"].series_id == "SF43718"
    assert by_suffix["unemployment-rate"].series_id == "SL1"
    assert build_indicator_code("MX", "fx-usd-mxn") == "mx-fx-usd-mxn"
    assert "Банк Мексики" in (by_suffix["policy-rate"].methodology or "")


def test_resolve_bcb_and_banxico_adapters():
    bcb = resolve_adapter("bcb_sgs")
    assert bcb.provider == "bcb_sgs"
    banxico = resolve_adapter("banxico_sie")
    assert banxico.provider == "banxico_sie"
    assert getattr(banxico, "public_source_name") == "Banco de México"


def test_load_jp_yaml_structure():
    path = CORE / "jp.yaml"
    assert path.is_file()
    manifest = load_national_core_yaml("jp")
    assert manifest.country_code == "JP"
    listed = [s for s in manifest.series if s.is_listed]
    assert len(listed) >= 6
    by_suffix = {s.code_suffix: s for s in manifest.series}
    assert by_suffix["policy-rate"].provider == "boj"
    assert by_suffix["policy-rate"].series_id == "STRDCLUCON"
    assert by_suffix["fx-usd-jpy"].dataset_id == "FM08"
    assert by_suffix["cpi-all"].provider == "estat"
    assert build_indicator_code("JP", "cpi-all") == "jp-cpi-all"
    assert "Банк Японии" in (by_suffix["policy-rate"].methodology or "")


def test_load_kr_yaml_structure():
    path = CORE / "kr.yaml"
    assert path.is_file()
    manifest = load_national_core_yaml("kr")
    assert manifest.country_code == "KR"
    listed = [s for s in manifest.series if s.is_listed]
    assert len(listed) >= 6
    by_suffix = {s.code_suffix: s for s in manifest.series}
    assert by_suffix["policy-rate"].provider == "ecos"
    assert by_suffix["policy-rate"].series_id == "0101000"
    assert by_suffix["cpi-all"].dataset_id == "901Y009"
    assert by_suffix["unemployment-rate"].series_id == "I61BC/I28B"
    assert build_indicator_code("KR", "fx-usd-krw") == "kr-fx-usd-krw"
    assert "Банк Кореи" in (by_suffix["policy-rate"].methodology or "")


def test_resolve_boj_and_key_gated_jp_kr(monkeypatch):
    monkeypatch.delenv("RUSTATS_ESTAT_APP_ID", raising=False)
    monkeypatch.delenv("RUSTATS_ECOS_API_KEY", raising=False)
    adapter = resolve_adapter("boj")
    assert adapter.provider == "boj"
    with pytest.raises(AdapterUnavailable, match="RUSTATS_ESTAT_APP_ID"):
        resolve_adapter("estat")
    with pytest.raises(AdapterUnavailable, match="RUSTATS_ECOS_API_KEY"):
        resolve_adapter("ecos")


def test_load_us_yaml_structure():
    path = CORE / "us.yaml"
    assert path.is_file()
    manifest = load_national_core_yaml("us")
    assert manifest.country_code == "US"
    assert len(manifest.series) >= 6
    by_suffix = {s.code_suffix: s for s in manifest.series}
    assert by_suffix["cpi-all"].provider == "fred"
    assert by_suffix["cpi-all"].series_id == "CPIAUCSL"
    assert by_suffix["policy-rate"].series_id == "FEDFUNDS"
    assert by_suffix["gdp-real"].series_id == "GDPC1"
    assert build_indicator_code("US", "cpi-all") == "us-cpi-all"
    assert "Федеральный резервный банк Сент-Луиса" in (by_suffix["cpi-all"].methodology or "")


def test_resolve_fred_adapter_from_us_yaml():
    manifest = load_national_core_yaml("us")
    adapter = resolve_adapter("fred", series_specs=manifest.series)
    assert adapter.provider == "fred"
    assert getattr(adapter, "public_source_name") == "Federal Reserve Bank of St. Louis"


def test_resolve_bea_without_key_unavailable(monkeypatch):
    monkeypatch.delenv("RUSTATS_BEA_API_KEY", raising=False)
    with pytest.raises(AdapterUnavailable, match="RUSTATS_BEA_API_KEY"):
        resolve_adapter("bea")


def test_series_ref_slice_hash_stable():
    manifest = load_national_core_yaml("ca")
    spec = manifest.series[0]
    ref_a = series_ref_from_spec(spec, country_code=manifest.country_code)
    ref_b = series_ref_from_spec(spec, country_code=manifest.country_code)
    assert ref_a.slice_hash == ref_b.slice_hash
    assert len(ref_a.slice_hash) == 64
    code = build_indicator_code(manifest.country_code, spec.code_suffix)
    assert len(code) <= 120


def test_resolve_adapter_unknown_and_missing_module():
    with pytest.raises(AdapterUnavailable):
        resolve_adapter("not_a_real_provider")
    # boc_valet may already be present; abs/rba stay fail-closed until modules land.
    try:
        resolve_adapter("boc_valet")
    except AdapterUnavailable:
        pass


def test_resolve_abs_rba_registry_modules():
    """abs/rba resolve when their registered modules exist; else AdapterUnavailable."""
    import importlib.util

    from app.services.world_national_ingest import _ADAPTER_MODULES

    for provider in ("abs", "rba"):
        module_path, _preferred = _ADAPTER_MODULES[provider]
        if importlib.util.find_spec(module_path) is None:
            with pytest.raises(AdapterUnavailable):
                resolve_adapter(provider)
        else:
            adapter = resolve_adapter(provider)
            assert adapter.provider == provider
            assert getattr(adapter, "public_source_name")


def test_resolve_statcan_adapter_from_yaml_specs():
    manifest = load_national_core_yaml("ca")
    adapter = resolve_adapter("statcan", series_specs=manifest.series)
    assert adapter.provider == "statcan"
    assert getattr(adapter, "public_source_name") == "Statistics Canada"


def test_public_source_ru_china_india():
    assert PUBLIC_SOURCE_RU["nbs"] == "Национальное статистическое бюро Китая"
    assert PUBLIC_SOURCE_RU["cfets"] == "Китайская система валютных торгов"
    assert PUBLIC_SOURCE_RU["mospi"] == (
        "Министерство статистики и программной реализации Индии"
    )
    assert PUBLIC_SOURCE_RU["rbi"] == "Резервный банк Индии"
    assert public_source_for_provider("cfets") == "Китайская система валютных торгов"
    assert public_source_for_provider("mospi").startswith("Министерство статистики")


def test_load_cn_yaml_structure():
    path = CORE / "cn.yaml"
    assert path.is_file()
    manifest = load_national_core_yaml("cn")
    assert manifest.country_code == "CN"
    by_suffix = {s.code_suffix: s for s in manifest.series}
    assert by_suffix["fx-usd-cny"].provider == "cfets"
    assert by_suffix["fx-usd-cny"].series_id == "USD/CNY"
    assert by_suffix["lpr-1y"].is_listed is True
    assert by_suffix["cpi-all"].provider == "nbs"
    # cpi-all — YoY-поток A01010G01, публичен (в БД is_listed=t); скрыт только
    # промышленный VA (UUID-лист не подтверждён в каталоге потоков).
    assert by_suffix["cpi-all"].is_listed is True
    assert by_suffix["industrial-production"].is_listed is False
    assert build_indicator_code("CN", "fx-usd-cny") == "cn-fx-usd-cny"
    assert "Китайская система валютных торгов" in (
        by_suffix["fx-usd-cny"].methodology or ""
    )


def test_load_in_yaml_structure():
    path = CORE / "in.yaml"
    assert path.is_file()
    manifest = load_national_core_yaml("in")
    assert manifest.country_code == "IN"
    listed = [s for s in manifest.series if s.is_listed]
    assert len(listed) >= 5
    by_suffix = {s.code_suffix: s for s in manifest.series}
    assert by_suffix["cpi-all"].provider == "mospi"
    assert by_suffix["cpi-all"].dimensions["group_name"] == "General"
    assert by_suffix["gdp-real"].dataset_id == "NAS"
    assert by_suffix["fx-usd-inr"].provider == "rbi"
    assert by_suffix["policy-rate"].is_listed is False
    assert build_indicator_code("IN", "unemployment-rate") == "in-unemployment-rate"
    assert "Резервный банк Индии" in (by_suffix["fx-usd-inr"].methodology or "")


def test_resolve_cn_in_adapters_from_yaml():
    cn = load_national_core_yaml("cn")
    cfets = resolve_adapter("cfets", series_specs=cn.series)
    assert cfets.provider == "cfets"
    nbs = resolve_adapter("nbs", series_specs=cn.series)
    assert nbs.provider == "nbs"

    india = load_national_core_yaml("in")
    mospi = resolve_adapter("mospi", series_specs=india.series)
    assert mospi.provider == "mospi"
    rbi = resolve_adapter("rbi", series_specs=india.series)
    assert rbi.provider == "rbi"


def test_ingest_series_applies_value_scale(auth_env, monkeypatch):
    """value_scale множит точки до записи: ABS-тысячи → лица в world_data_points.

    Герметично (SQLite): фейковый адаптер отдаёт «тысячи», спек с
    value_scale=1000 пишет лица. Named ON CONFLICT (Postgres-синтаксис
    reconcile_points) в SQLite недоступен — подменяем на insert-or-update
    по индексным колонкам только на время теста.
    """
    import asyncio
    from datetime import date, datetime, timezone

    import app.services.world_national_ingest as ingest_mod
    from app.models import WorldDataPoint
    from app.services.world_national_ingest import (
        NationalSeriesSpec,
        WorldSeriesPayload,
        ensure_country,
        ingest_series,
    )
    from app.services.world_source_adapter import WorldObservation

    async def _sqlite_reconcile(db, indicator_id, points):
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        for d, v in points:
            stmt = sqlite_insert(WorldDataPoint).values(
                indicator_id=indicator_id, date=d, value=v
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["indicator_id", "date"],
                set_={"value": stmt.excluded.value},
            )
            await db.execute(stmt)
        return len(points), 0

    monkeypatch.setattr(ingest_mod, "reconcile_points", _sqlite_reconcile)

    class _FakeAdapter:
        provider = "abs"
        public_source_name = "Австралийское бюро статистики"

        async def fetch_series(self, ref, *, date_from=None, date_to=None):
            obs = [
                WorldObservation(period=date(2025, 1, 1), value=27529.8),
                WorldObservation(period=date(2025, 10, 1), value=27801.0),
            ]
            return WorldSeriesPayload(
                ref=ref,
                observations=obs,
                fetched_at=datetime.now(timezone.utc),
            )

    async def _run() -> None:
        spec = NationalSeriesSpec(
            code_suffix="population",
            name_ru="Численность населения",
            name_en=None,
            category_ru="Население",
            unit="PERSONS",
            unit_ru="человек",
            frequency="quarterly",
            provider="abs",
            dataset_id="ERP_COMP_Q",
            series_id="10.AUS.Q",
            value_scale=1000.0,
        )
        async with auth_env["session_maker"]() as db:
            async with db.begin():
                country = await ensure_country(
                    db,
                    code="AU",
                    slug="australia",
                    name_ru="Австралия",
                    name_en="Australia",
                    region_ru="Океания",
                )
                result = await ingest_series(
                    db, country=country, spec=spec, adapter=_FakeAdapter()
                )
                assert result.error is None, result.error
                iid = result.indicator_id
                rows = (
                    (await db.execute(
                        WorldDataPoint.__table__.select().where(
                            WorldDataPoint.indicator_id == iid
                        )
                    )).fetchall()
                )
                values = sorted(row.value for row in rows)
                assert values[-1] == 27_801_000.0
                assert values[0] == 27_529_800.0

    asyncio.run(_run())

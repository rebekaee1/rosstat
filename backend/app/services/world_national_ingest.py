"""National-core ingest: YAML pick-list → WorldSourceAdapter → world_* tables.

Курируемый паспорт страны (``app/data/world_national_core/<cc>.yaml``) задаёт
primary-ряды. Адаптер нормализует наблюдения; product-слой пишет
``WorldIndicator`` / ``WorldDataPoint`` / ``WorldDatasetState`` с provider в
identity. Существующие eurostat-ряды той же страны не трогаем.

Запуск: ``scripts/load-world-national.py --country ca|au|uk|us|jp|kr|br|mx|cn|in``.
"""

from __future__ import annotations

import importlib
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models import (
    WorldCountry,
    WorldDataPoint,
    WorldDatasetState,
    WorldIndicator,
    WorldIngestRun,
)
from app.services.world_source_adapter import (
    WorldSeriesPayload,
    WorldSeriesRef,
    WorldSourceAdapter,
)

logger = logging.getLogger(__name__)

CORE_DIR = Path(__file__).resolve().parents[1] / "data" / "world_national_core"

# Публичное имя организации (поле WorldIndicator.source) — не путать с provider.
PUBLIC_SOURCE_RU: dict[str, str] = {
    "statcan": "Статистическое управление Канады",
    "boc_valet": "Банк Канады",
    "abs": "Австралийское бюро статистики",
    "rba": "Резервный банк Австралии",
    "ons": "Управление национальной статистики Великобритании",
    "boe_iadb": "Банк Англии",
    "fred": "Федеральный резервный банк Сент-Луиса",
    "bls": "Бюро трудовой статистики США",
    "bea": "Бюро экономического анализа США",
    "boj": "Банк Японии",
    "estat": "Статистическое бюро Японии",
    "ecos": "Банк Кореи",
    "bcb_sgs": "Банк Бразилии",
    "banxico_sie": "Банк Мексики",
    "nbs": "Национальное статистическое бюро Китая",
    "cfets": "Китайская система валютных торгов",
    "mospi": "Министерство статистики и программной реализации Индии",
    "rbi": "Резервный банк Индии",
}

# provider → (module, preferred class name). Class name may differ; discovery
# also accepts ADAPTER / create_adapter() / any class with matching .provider.
# abs → abs_data.AbsDataAdapter; rba → rba_stats.RbaStatsAdapter;
# ons → ons_timeseries.OnsTimeseriesAdapter; boe_iadb → boe_iadb.BoeIadbAdapter.
# fred → fred_stlouis.FredStLouisAdapter; bls → bls_api.BlsApiAdapter;
# bea → bea_api.BeaApiAdapter;
# boj → boj_stat.BojStatAdapter; estat/ecos → create_adapter (key-gated).
_ADAPTER_MODULES: dict[str, tuple[str, str]] = {
    "statcan": ("app.services.world_adapters.statcan_wds", "StatCanWdsAdapter"),
    "boc_valet": ("app.services.world_adapters.boc_valet", "BocValetAdapter"),
    "abs": ("app.services.world_adapters.abs_data", "AbsDataAdapter"),
    "rba": ("app.services.world_adapters.rba_stats", "RbaStatsAdapter"),
    "ons": ("app.services.world_adapters.ons_timeseries", "OnsTimeseriesAdapter"),
    "boe_iadb": ("app.services.world_adapters.boe_iadb", "BoeIadbAdapter"),
    "fred": ("app.services.world_adapters.fred_stlouis", "FredStLouisAdapter"),
    "bls": ("app.services.world_adapters.bls_api", "BlsApiAdapter"),
    "bea": ("app.services.world_adapters.bea_api", "BeaApiAdapter"),
    "boj": ("app.services.world_adapters.boj_stat", "BojStatAdapter"),
    "estat": ("app.services.world_adapters.estat_api", "EstatApiAdapter"),
    "ecos": ("app.services.world_adapters.ecos_bok", "EcosBokAdapter"),
    "bcb_sgs": ("app.services.world_adapters.bcb_sgs", "BcbSgsAdapter"),
    "banxico_sie": ("app.services.world_adapters.banxico_sie", "BanxicoSieAdapter"),
    "nbs": ("app.services.world_adapters.nbs_stats", "NbsStatsAdapter"),
    "cfets": ("app.services.world_adapters.cfets_chinamoney", "CfetsChinamoneyAdapter"),
    "mospi": ("app.services.world_adapters.mospi_api", "MospiApiAdapter"),
    "rbi": ("app.services.world_adapters.rbi_rates", "RbiRatesAdapter"),
}

_FREQ_ALIASES: dict[str, str] = {
    "m": "monthly",
    "q": "quarterly",
    "a": "annual",
    "y": "annual",
    "yearly": "annual",
    "d": "daily",
    "w": "weekly",
    "monthly": "monthly",
    "quarterly": "quarterly",
    "annual": "annual",
    "daily": "daily",
    "weekly": "weekly",
}

_FREQ_ADJ_RU: dict[str, str] = {
    "monthly": "месячная",
    "quarterly": "квартальная",
    "annual": "годовая",
    "weekly": "недельная",
    "daily": "дневная",
}

_CODE_RE = re.compile(r"[^a-z0-9-]+")
_UPSERT_CHUNK = 2000


class AdapterUnavailable(RuntimeError):
    """Адаптер ещё не залит или не импортируется — scaffolding остаётся чистым."""


@dataclass(frozen=True)
class NationalSeriesSpec:
    code_suffix: str
    name_ru: str
    name_en: str | None
    category_ru: str
    unit: str
    unit_ru: str
    frequency: str
    provider: str
    dataset_id: str
    series_id: str
    source_url: str | None = None
    analog_ru: str | None = None
    dimensions: Mapping[str, str] = field(default_factory=dict)
    description: str | None = None
    methodology: str | None = None
    is_listed: bool = True
    # Источник публикует значения в кратном масштабе (тысячи/миллионы):
    # множитель приводится к публичной единице unit_ru ещё на инжесте,
    # чтобы точки в world_data_points лежали в единицах карточки (и рейтинг
    # сравнивал сопоставимые значения). Применяется до reconcile_points.
    value_scale: float = 1.0


@dataclass(frozen=True)
class NationalCoreManifest:
    country_code: str
    series: tuple[NationalSeriesSpec, ...]
    path: Path


@dataclass
class SeriesIngestResult:
    code: str
    provider: str
    dataset_id: str
    indicator_id: int | None = None
    created: bool = False
    points_touched: int = 0
    points_removed: int = 0
    observations: int = 0
    error: str | None = None


@dataclass
class CountryIngestStats:
    country_code: str
    series_ok: int = 0
    series_err: int = 0
    indicators_upserted: int = 0
    points_touched: int = 0
    results: list[SeriesIngestResult] = field(default_factory=list)


def normalize_national_frequency(raw: str | None) -> str:
    key = (raw or "").strip().lower()
    if key in _FREQ_ALIASES:
        return _FREQ_ALIASES[key]
    return key or "monthly"


def build_indicator_code(country_code: str, code_suffix: str) -> str:
    """Стабильный публичный код: ``ca-cpi-all`` / ``au-cpi-all`` (≤120)."""
    cc = (country_code or "").strip().lower()
    suffix = (code_suffix or "").strip().lower().replace("_", "-")
    suffix = _CODE_RE.sub("-", suffix).strip("-")
    while "--" in suffix:
        suffix = suffix.replace("--", "-")
    code = f"{cc}-{suffix}" if cc and suffix else (cc or suffix)
    if len(code) > 120:
        raise ValueError(f"indicator code exceeds 120 chars: {code!r}")
    if not code:
        raise ValueError("empty indicator code")
    return code


def core_yaml_path(country: str, *, base_dir: Path | None = None) -> Path:
    cc = country.strip().lower()
    root = base_dir or CORE_DIR
    return root / f"{cc}.yaml"


def _collapse_ws(text: str | None) -> str | None:
    if text is None:
        return None
    collapsed = " ".join(str(text).split())
    return collapsed or None


def _as_str_map(raw: Any) -> dict[str, str]:
    if not raw:
        return {}
    if not isinstance(raw, Mapping):
        raise ValueError(f"dimensions must be a mapping, got {type(raw).__name__}")
    return {str(k).strip(): str(v).strip() for k, v in raw.items() if str(k).strip()}


def _parse_series_row(row: Mapping[str, Any], *, index: int) -> NationalSeriesSpec:
    required = (
        "code_suffix",
        "name_ru",
        "category_ru",
        "unit",
        "unit_ru",
        "frequency",
        "provider",
        "dataset_id",
        "series_id",
    )
    missing = [k for k in required if not str(row.get(k) or "").strip()]
    if missing:
        raise ValueError(f"series[{index}] missing fields: {', '.join(missing)}")

    listed_raw = row.get("is_listed", True)
    if isinstance(listed_raw, str):
        is_listed = listed_raw.strip().lower() in {"1", "true", "yes", "y"}
    else:
        is_listed = bool(listed_raw)

    return NationalSeriesSpec(
        code_suffix=str(row["code_suffix"]).strip(),
        name_ru=str(row["name_ru"]).strip(),
        name_en=_collapse_ws(row.get("name_en")),
        category_ru=str(row["category_ru"]).strip(),
        unit=str(row["unit"]).strip(),
        unit_ru=str(row["unit_ru"]).strip(),
        frequency=normalize_national_frequency(str(row["frequency"])),
        provider=str(row["provider"]).strip().lower(),
        dataset_id=str(row["dataset_id"]).strip(),
        series_id=str(row["series_id"]).strip(),
        source_url=_collapse_ws(row.get("source_url")),
        analog_ru=_collapse_ws(row.get("analog_ru")),
        dimensions=_as_str_map(row.get("dimensions")),
        description=_collapse_ws(row.get("description")),
        methodology=_collapse_ws(row.get("methodology")),
        is_listed=is_listed,
        value_scale=float(row.get("value_scale") or 1.0),
    )


def load_national_core_yaml(
    country: str,
    *,
    base_dir: Path | None = None,
    path: Path | None = None,
) -> NationalCoreManifest:
    """Прочитать и провалидировать pick-list YAML страны."""
    yaml_path = path or core_yaml_path(country, base_dir=base_dir)
    if not yaml_path.is_file():
        raise FileNotFoundError(f"national-core YAML not found: {yaml_path}")

    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError(f"{yaml_path}: root must be a mapping")

    country_code = str(
        raw.get("country_code") or raw.get("country") or country
    ).strip().upper()
    if not country_code:
        raise ValueError(f"{yaml_path}: country_code is required")

    rows = raw.get("series")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{yaml_path}: series must be a non-empty list")

    series = tuple(_parse_series_row(row, index=i) for i, row in enumerate(rows))
    suffixes = [s.code_suffix.lower() for s in series]
    if len(suffixes) != len(set(suffixes)):
        raise ValueError(f"{yaml_path}: duplicate code_suffix in series")

    return NationalCoreManifest(
        country_code=country_code,
        series=series,
        path=yaml_path,
    )


def series_ref_from_spec(
    spec: NationalSeriesSpec,
    *,
    country_code: str,
) -> WorldSeriesRef:
    return WorldSeriesRef(
        provider=spec.provider,
        dataset_id=spec.dataset_id,
        series_id=spec.series_id,
        country_code=country_code.strip().upper(),
        frequency=spec.frequency,
        unit_code=spec.unit,
        dimensions=dict(spec.dimensions),
        title=spec.name_en or spec.name_ru,
        source_url=spec.source_url,
    )


def public_source_for_provider(
    provider: str,
    adapter: WorldSourceAdapter | None = None,
) -> str:
    mapped = PUBLIC_SOURCE_RU.get(provider.strip().lower())
    if mapped:
        return mapped
    if adapter is not None and getattr(adapter, "public_source_name", None):
        return str(adapter.public_source_name)
    return provider


def default_description(
    *,
    name_ru: str,
    country_name_ru: str,
    unit_ru: str,
    source_ru: str,
    history_start: date | None,
    history_end: date | None,
) -> str:
    where = f" ({country_name_ru})" if country_name_ru else ""
    if history_start and history_end and history_start != history_end:
        span = (
            f"Динамика с {history_start.isoformat()} по {history_end.isoformat()}."
        )
    elif history_end:
        span = f"Последнее наблюдение — {history_end.isoformat()}."
    else:
        span = f"Источник данных — {source_ru}."
    unit_bit = f" Единица измерения — {unit_ru}." if unit_ru else ""
    return f"{name_ru}{where}. {span}{unit_bit}".strip()


def default_methodology(
    *,
    source_ru: str,
    frequency: str,
    unit_ru: str,
) -> str:
    freq_adj = _FREQ_ADJ_RU.get(frequency, "регулярная")
    unit_bit = f" Единица измерения на графике — {unit_ru}." if unit_ru else ""
    return (
        f"Источник данных — {source_ru}. Частота публикации — {freq_adj}."
        f"{unit_bit} На графике показан официальный национальный ряд без "
        f"дополнительных преобразований."
    )


def _statcan_cubes_from_specs(specs: Sequence[NationalSeriesSpec]) -> list[Any]:
    """Собрать StatCanCubeSpec из YAML-рядов (без сетевого metadata)."""
    from app.services.world_adapters.statcan_wds import StatCanCubeSpec, StatCanVectorSpec

    by_product: dict[str, list[NationalSeriesSpec]] = {}
    for spec in specs:
        if spec.provider != "statcan":
            continue
        by_product.setdefault(spec.dataset_id, []).append(spec)

    cubes: list[Any] = []
    for product_id, rows in by_product.items():
        vectors = [
            StatCanVectorSpec(
                vector_id=row.series_id,
                title=row.name_en or row.name_ru,
                unit_code=row.unit or "UNIT",
                frequency=row.frequency,
                dimensions=dict(row.dimensions),
            )
            for row in rows
        ]
        cubes.append(
            StatCanCubeSpec(
                product_id=product_id,
                title=rows[0].name_en or rows[0].name_ru,
                vectors=vectors,
            )
        )
    return cubes


def _instantiate_adapter(
    cls: type,
    *,
    provider: str,
    series_specs: Sequence[NationalSeriesSpec] | None,
) -> WorldSourceAdapter:
    """Создать адаптер с учётом constructor contracts (cubes у StatCan и т.п.)."""
    if provider == "statcan":
        cubes = _statcan_cubes_from_specs(series_specs or ())
        if not cubes:
            raise AdapterUnavailable(
                "statcan adapter needs at least one YAML series to build StatCanCubeSpec"
            )
        return cls(cubes, fetch_cube_metadata=False)

    try:
        return cls()
    except TypeError:
        # Адаптер с обязательными curated specs — передаём YAML-ряды этого provider.
        provider_specs = tuple(
            s for s in (series_specs or ()) if s.provider == provider
        )
        try:
            return cls(provider_specs)
        except TypeError as exc:
            raise AdapterUnavailable(
                f"cannot instantiate adapter for {provider!r}: {exc}"
            ) from exc


def resolve_adapter(
    provider: str,
    *,
    series_specs: Sequence[NationalSeriesSpec] | None = None,
) -> WorldSourceAdapter:
    """Лениво поднять адаптер; ImportError → AdapterUnavailable (scaffolding)."""
    key = provider.strip().lower()
    entry = _ADAPTER_MODULES.get(key)
    if entry is None:
        raise AdapterUnavailable(f"no adapter registry entry for provider={provider!r}")

    module_path, preferred_name = entry
    try:
        mod = importlib.import_module(module_path)
    except ImportError as exc:
        raise AdapterUnavailable(
            f"adapter module unavailable for {provider!r}: {module_path} ({exc})"
        ) from exc

    if hasattr(mod, "ADAPTER"):
        adapter = getattr(mod, "ADAPTER")
        if isinstance(adapter, type):
            return _instantiate_adapter(
                adapter, provider=key, series_specs=series_specs
            )
        if callable(adapter) and not isinstance(adapter, type):
            return adapter()
        return adapter

    create = getattr(mod, "create_adapter", None)
    if callable(create):
        try:
            return create(series_specs=series_specs)
        except TypeError:
            return create()

    preferred = getattr(mod, preferred_name, None)
    if isinstance(preferred, type):
        return _instantiate_adapter(
            preferred, provider=key, series_specs=series_specs
        )

    for attr_name in dir(mod):
        obj = getattr(mod, attr_name)
        if (
            isinstance(obj, type)
            and attr_name.endswith("Adapter")
            and getattr(obj, "provider", None) == key
        ):
            return _instantiate_adapter(obj, provider=key, series_specs=series_specs)

    raise AdapterUnavailable(
        f"adapter class not found in {module_path} for provider={provider!r}"
    )


async def ensure_country(
    db: AsyncSession,
    *,
    code: str,
    slug: str | None = None,
    name_ru: str | None = None,
    name_en: str | None = None,
    region_ru: str = "Америка",
) -> WorldCountry:
    """Найти/создать страну. is_active не форсируем — это зона visibility/repair."""
    cc = code.strip().upper()
    row = (
        await db.execute(select(WorldCountry).where(WorldCountry.code == cc))
    ).scalar_one_or_none()
    if row is not None:
        return row

    slug_val = (slug or cc.lower()).strip()
    by_slug = (
        await db.execute(select(WorldCountry).where(WorldCountry.slug == slug_val))
    ).scalar_one_or_none()
    if by_slug is not None:
        return by_slug

    row = WorldCountry(
        code=cc,
        slug=slug_val,
        name_ru=name_ru or cc,
        name_en=name_en or cc,
        region_ru=region_ru,
        is_active=False,
        sort_order=500,
    )
    db.add(row)
    await db.flush()
    return row


async def reconcile_points(
    db: AsyncSession,
    indicator_id: int,
    points: list[tuple[date, float]],
) -> tuple[int, int]:
    """Идемпотентный upsert точек + удаление дат, исчезнувших из source-ответа."""
    if not points:
        return 0, 0
    touched = 0
    source_dates = [d for d, _ in points]
    source_set = set(source_dates)
    for i in range(0, len(points), _UPSERT_CHUNK):
        chunk = points[i : i + _UPSERT_CHUNK]
        values = [
            {"indicator_id": indicator_id, "date": d, "value": v}
            for d, v in chunk
        ]
        stmt = pg_insert(WorldDataPoint).values(values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_world_data_point",
            set_={"value": stmt.excluded.value},
            where=(WorldDataPoint.__table__.c.value.is_distinct_from(stmt.excluded.value)),
        ).returning(WorldDataPoint.id)
        res = await db.execute(stmt)
        touched += len(res.fetchall())

    existing_dates = (
        await db.execute(
            select(WorldDataPoint.date).where(
                WorldDataPoint.indicator_id == indicator_id
            )
        )
    ).scalars().all()
    stale = [d for d in existing_dates if d not in source_set]
    removed = 0
    for i in range(0, len(stale), _UPSERT_CHUNK):
        chunk = stale[i : i + _UPSERT_CHUNK]
        res = await db.execute(
            WorldDataPoint.__table__.delete().where(
                WorldDataPoint.indicator_id == indicator_id,
                WorldDataPoint.date.in_(chunk),
            )
        )
        removed += int(res.rowcount or 0)
    return touched, removed


async def refresh_indicator_extent(db: AsyncSession, indicator_id: int) -> None:
    count, history_start, history_end = (
        await db.execute(
            select(
                func.count(WorldDataPoint.id),
                func.min(WorldDataPoint.date),
                func.max(WorldDataPoint.date),
            ).where(WorldDataPoint.indicator_id == indicator_id)
        )
    ).one()
    ind = await db.get(WorldIndicator, indicator_id)
    if ind is not None:
        ind.points_count = int(count or 0)
        ind.history_start = history_start
        ind.history_end = history_end


def _slice_json(spec: NationalSeriesSpec) -> dict[str, str]:
    payload: dict[str, str] = {"series_id": spec.series_id}
    for key, value in spec.dimensions.items():
        payload[str(key)] = str(value)
    return payload


def _seo_bundle(
    *,
    name_ru: str,
    country_name_ru: str,
    description: str,
) -> tuple[str, str, str]:
    seo_title = f"{name_ru} — {country_name_ru}: график и данные"
    seo_kw = (
        f"{name_ru}, {country_name_ru}, {name_ru} {country_name_ru}, "
        f"{country_name_ru} статистика, график"
    )
    return seo_title[:300], description, seo_kw


async def upsert_national_indicator(
    db: AsyncSession,
    *,
    country: WorldCountry,
    spec: NationalSeriesSpec,
    ref: WorldSeriesRef,
    points: Sequence[tuple[date, float]],
    source_ru: str,
) -> tuple[int, bool]:
    """Upsert по (provider, country_id, dataset_id, slice_hash). Eurostat не трогаем."""
    code = build_indicator_code(country.code, spec.code_suffix)
    hs = points[0][0] if points else None
    he = points[-1][0] if points else None
    desc = spec.description or default_description(
        name_ru=spec.name_ru,
        country_name_ru=country.name_ru,
        unit_ru=spec.unit_ru,
        source_ru=source_ru,
        history_start=hs,
        history_end=he,
    )
    meth = spec.methodology or default_methodology(
        source_ru=source_ru,
        frequency=spec.frequency,
        unit_ru=spec.unit_ru,
    )
    seo_title, seo_desc, seo_kw = _seo_bundle(
        name_ru=spec.name_ru,
        country_name_ru=country.name_ru,
        description=desc,
    )
    slice_json = _slice_json(spec)
    slice_hash = ref.slice_hash

    existing = (
        await db.execute(
            select(WorldIndicator).where(
                WorldIndicator.provider == spec.provider,
                WorldIndicator.country_id == country.id,
                WorldIndicator.dataset_id == spec.dataset_id,
                WorldIndicator.slice_hash == slice_hash,
            )
        )
    ).scalar_one_or_none()
    created = False

    if existing is None:
        by_code = (
            await db.execute(select(WorldIndicator).where(WorldIndicator.code == code))
        ).scalar_one_or_none()
        if by_code is not None:
            # Код занят другим identity — не переписываем чужой (в т.ч. eurostat) ряд.
            # Тот же national provider+country: разрешаем смену dataset_id/slice
            # (переезд на новый id первоисточника, как MX GDP SR16620→SR17493).
            if by_code.provider != spec.provider or by_code.country_id != country.id:
                raise ValueError(
                    f"code {code!r} already owned by provider={by_code.provider!r} "
                    f"dataset_id={by_code.dataset_id!r}"
                )
            existing = by_code
        else:
            ind = WorldIndicator(
                country_id=country.id,
                provider=spec.provider,
                code=code,
                dataset_id=spec.dataset_id,
                slice_json=slice_json,
                slice_hash=slice_hash,
                name_ru=spec.name_ru,
                name_en=(spec.name_en or "")[:400] or None,
                name_quality="curated",
                unit=spec.unit,
                unit_ru=spec.unit_ru,
                frequency=spec.frequency,
                category_ru=spec.category_ru,
                source=source_ru,
                source_url=spec.source_url,
                description=desc,
                methodology=meth,
                history_start=hs,
                history_end=he,
                points_count=len(points),
                is_listed=spec.is_listed,
                seo_title=seo_title,
                seo_description=seo_desc,
                seo_keywords=seo_kw,
            )
            db.add(ind)
            await db.flush()
            return ind.id, True

    # Slice identity may need a new public code (YAML rename). Free the target
    # code if another same-country national row still holds the old suffix.
    if existing.code != code:
        conflict = (
            await db.execute(select(WorldIndicator).where(WorldIndicator.code == code))
        ).scalar_one_or_none()
        if conflict is not None and conflict.id != existing.id:
            if (
                conflict.provider == spec.provider
                and conflict.country_id == country.id
            ):
                conflict.code = f"{code}-superseded-{conflict.id}"
                conflict.is_listed = False
                await db.flush()
            else:
                raise ValueError(
                    f"code {code!r} already owned by provider={conflict.provider!r} "
                    f"dataset_id={conflict.dataset_id!r}"
                )

    existing.code = code
    existing.provider = spec.provider
    existing.dataset_id = spec.dataset_id
    existing.slice_json = slice_json
    existing.slice_hash = slice_hash
    existing.name_ru = spec.name_ru
    existing.name_en = (spec.name_en or "")[:400] or existing.name_en
    existing.name_quality = "curated"
    existing.unit = spec.unit
    existing.unit_ru = spec.unit_ru
    existing.frequency = spec.frequency
    existing.category_ru = spec.category_ru
    existing.source = source_ru
    existing.source_url = spec.source_url
    existing.description = desc
    existing.methodology = meth
    existing.history_start = hs
    existing.history_end = he
    existing.points_count = len(points)
    existing.is_listed = spec.is_listed
    existing.seo_title = seo_title
    existing.seo_description = seo_desc
    existing.seo_keywords = seo_kw
    await db.flush()
    return existing.id, created


async def touch_dataset_state(
    db: AsyncSession,
    *,
    provider: str,
    dataset_id: str,
    status: str,
    slice_hash: str | None = None,
    error: str | None = None,
    data_updated_at: date | None = None,
) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    state = await db.get(WorldDatasetState, (provider, dataset_id))
    if state is None:
        state = WorldDatasetState(provider=provider, dataset_id=dataset_id)
        db.add(state)
    state.status = status
    if slice_hash is not None:
        state.last_slice_hash = slice_hash
    if data_updated_at is not None:
        state.last_update_of_data = data_updated_at
    if status == "ok":
        state.last_success_at = now
        state.last_error = None
    else:
        state.last_error = (error or "")[:2000] or None
    await db.flush()


def observations_to_points(
    payload: WorldSeriesPayload,
) -> list[tuple[date, float]]:
    points = [(obs.period, float(obs.value)) for obs in payload.observations]
    points.sort(key=lambda item: item[0])
    # Dedup by date keeping last value (adapter should already be clean).
    dedup: dict[date, float] = {}
    for dt, val in points:
        dedup[dt] = val
    return sorted(dedup.items(), key=lambda item: item[0])


async def ingest_series(
    db: AsyncSession,
    *,
    country: WorldCountry,
    spec: NationalSeriesSpec,
    adapter: WorldSourceAdapter | None = None,
    dry_run: bool = False,
) -> SeriesIngestResult:
    code = build_indicator_code(country.code, spec.code_suffix)
    ref = series_ref_from_spec(spec, country_code=country.code)
    result = SeriesIngestResult(
        code=code,
        provider=spec.provider,
        dataset_id=spec.dataset_id,
    )
    try:
        async with db.begin_nested():
            adapter_obj = adapter or resolve_adapter(spec.provider)
            source_ru = public_source_for_provider(spec.provider, adapter_obj)
            if dry_run:
                result.observations = 0
                return result

            payload = await adapter_obj.fetch_series(ref)
            points = observations_to_points(payload)
            if spec.value_scale != 1.0:
                points = [(d, v * spec.value_scale) for d, v in points]
            result.observations = len(points)
            iid, created = await upsert_national_indicator(
                db,
                country=country,
                spec=spec,
                ref=ref,
                points=points,
                source_ru=source_ru,
            )
            touched, removed = await reconcile_points(db, iid, points)
            await refresh_indicator_extent(db, iid)
            await touch_dataset_state(
                db,
                provider=spec.provider,
                dataset_id=spec.dataset_id,
                status="ok",
                slice_hash=ref.slice_hash,
                data_updated_at=points[-1][0] if points else None,
            )
            result.indicator_id = iid
            result.created = created
            result.points_touched = touched
            result.points_removed = removed
            return result
    except Exception as exc:  # noqa: BLE001 — per-series quarantine
        result.error = f"{type(exc).__name__}: {exc}"
        if not dry_run:
            try:
                await touch_dataset_state(
                    db,
                    provider=spec.provider,
                    dataset_id=spec.dataset_id,
                    status="error",
                    slice_hash=ref.slice_hash,
                    error=result.error,
                )
            except Exception:  # noqa: BLE001
                logger.exception(
                    "failed to record dataset state for %s/%s",
                    spec.provider,
                    spec.dataset_id,
                )
        return result


_COUNTRY_DEFAULTS: dict[str, dict[str, str]] = {
    "CA": {
        "slug": "canada",
        "name_ru": "Канада",
        "name_en": "Canada",
        "region_ru": "Америка",
    },
    "AU": {
        "slug": "australia",
        "name_ru": "Австралия",
        "name_en": "Australia",
        "region_ru": "Океания",
    },
    "UK": {
        "slug": "united-kingdom",
        "name_ru": "Великобритания",
        "name_en": "United Kingdom",
        "region_ru": "Европа",
    },
    "US": {
        "slug": "united-states",
        "name_ru": "США",
        "name_en": "United States",
        "region_ru": "Америка",
    },
    "JP": {
        "slug": "japan",
        "name_ru": "Япония",
        "name_en": "Japan",
        "region_ru": "Азия",
    },
    "KR": {
        "slug": "south-korea",
        "name_ru": "Южная Корея",
        "name_en": "South Korea",
        "region_ru": "Азия",
    },
    "BR": {
        "slug": "brazil",
        "name_ru": "Бразилия",
        "name_en": "Brazil",
        "region_ru": "Америка",
    },
    "MX": {
        "slug": "mexico",
        "name_ru": "Мексика",
        "name_en": "Mexico",
        "region_ru": "Америка",
    },
    "CN": {
        "slug": "china",
        "name_ru": "Китай",
        "name_en": "China",
        "region_ru": "Азия",
    },
    "IN": {
        "slug": "india",
        "name_ru": "Индия",
        "name_en": "India",
        "region_ru": "Азия",
    },
}


async def ingest_country(
    db: AsyncSession,
    country: str,
    *,
    base_dir: Path | None = None,
    dry_run: bool = False,
    only_suffix: str | None = None,
) -> CountryIngestStats:
    manifest = load_national_core_yaml(country, base_dir=base_dir)
    defaults = _COUNTRY_DEFAULTS.get(manifest.country_code, {})
    country_row = await ensure_country(
        db,
        code=manifest.country_code,
        slug=defaults.get("slug"),
        name_ru=defaults.get("name_ru"),
        name_en=defaults.get("name_en"),
        region_ru=defaults.get("region_ru", "Америка"),
    )

    stats = CountryIngestStats(country_code=manifest.country_code)
    selected = manifest.series
    if only_suffix:
        needle = only_suffix.strip().lower()
        selected = tuple(
            s for s in manifest.series if s.code_suffix.strip().lower() == needle
        )
        if not selected:
            raise ValueError(f"no series with code_suffix={only_suffix!r}")

    # Cache adapters per provider within one country run.
    adapters: dict[str, WorldSourceAdapter | None] = {}
    adapter_errors: dict[str, str] = {}

    for spec in selected:
        if spec.provider not in adapters and spec.provider not in adapter_errors:
            try:
                adapters[spec.provider] = resolve_adapter(
                    spec.provider,
                    series_specs=selected,
                )
            except AdapterUnavailable as exc:
                adapters[spec.provider] = None
                adapter_errors[spec.provider] = str(exc)

        adapter = adapters.get(spec.provider)
        if adapter is None and not dry_run:
            err = adapter_errors.get(spec.provider) or "adapter unavailable"
            res = SeriesIngestResult(
                code=build_indicator_code(manifest.country_code, spec.code_suffix),
                provider=spec.provider,
                dataset_id=spec.dataset_id,
                error=err,
            )
            stats.series_err += 1
            stats.results.append(res)
            logger.error("SKIP %s: %s", res.code, err)
            await touch_dataset_state(
                db,
                provider=spec.provider,
                dataset_id=spec.dataset_id,
                status="error",
                error=err,
            )
            continue

        res = await ingest_series(
            db,
            country=country_row,
            spec=spec,
            adapter=adapter,
            dry_run=dry_run,
        )
        stats.results.append(res)
        if res.error:
            stats.series_err += 1
            logger.error("FAIL %s: %s", res.code, res.error)
        else:
            stats.series_ok += 1
            stats.indicators_upserted += 1
            stats.points_touched += res.points_touched
            logger.info(
                "OK %s provider=%s dataset=%s obs=%d touched=%d created=%s",
                res.code,
                res.provider,
                res.dataset_id,
                res.observations,
                res.points_touched,
                res.created,
            )
    return stats


NATIONAL_CORE_COUNTRIES: tuple[str, ...] = (
    "au", "br", "ca", "cn", "in", "jp", "kr", "mx", "uk", "us",
)


async def run_national_core_ingest(
    *,
    country_codes: list[str] | None = None,
) -> dict[str, int]:
    """Регулярная загрузка всех national-core паспортов (планировщик / вручную).

    Идемпотентна: повторный прогон перезаписывает значения и чинит extent.
    Одна запись WorldIngestRun на прогон; ошибка одной страны не валит остальные.
    Вызывается из планировщика отдельным job'ом (02:10 МСК, до Eurostat-очереди)
    и в начале ``world_eurostat_ingest_job``.
    """
    started_at = datetime.now(timezone.utc).replace(tzinfo=None)
    countries = [c.strip().lower() for c in (country_codes or NATIONAL_CORE_COUNTRIES)]
    async with async_session() as db:
        run = WorldIngestRun(source="world_national_core", is_shadow=False, started_at=started_at)
        db.add(run)
        await db.commit()
        await db.refresh(run)
        run_id = run.id

    indicators = 0
    points_touched = 0
    failures: list[str] = []
    per_country: dict[str, dict[str, int]] = {}
    for cc in countries:
        try:
            async with async_session() as db:
                async with db.begin():
                    stats = await ingest_country(db, cc, dry_run=False)
            per_country[cc] = {
                "ok": stats.series_ok,
                "err": stats.series_err,
                "indicators": stats.indicators_upserted,
                "points": stats.points_touched,
            }
            indicators += stats.indicators_upserted
            points_touched += stats.points_touched
            if stats.series_err:
                failures.append(cc)
        except Exception as exc:  # noqa: BLE001
            failures.append(cc)
            logger.exception("national-core ingest failed for %s", cc)
            per_country[cc] = {"error": 1, "message": str(exc)[:200]}
            async with async_session() as db:
                run = await db.get(WorldIngestRun, run_id)
                if run is not None:
                    run.error_message = f"{cc}: {exc}"[:2000]
                    await db.commit()

    async with async_session() as db:
        run = await db.get(WorldIngestRun, run_id)
        assert run is not None
        run.datasets_succeeded = sum(1 for c in countries if c not in failures)
        run.datasets_failed = len(failures)
        run.status = "ok" if not failures else "partial"
        run.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()

    try:
        if points_touched:
            from app.core.cache import bump_namespaces

            await bump_namespaces("world")
    except Exception:  # noqa: BLE001
        logger.warning("cache bump after national-core ingest failed", exc_info=True)

    result = {
        "run_id": run_id,
        "countries": len(countries),
        "indicators": indicators,
        "points_touched": points_touched,
        "failures": len(failures),
    }
    logger.info("national-core ingest done: %s (%s)", result, per_country)
    return result

"""IMF World Economic Outlook adapter (SDMX 3.0) for the world data plane.

Official-first source (ADR-0012): International Monetary Fund, World Economic
Outlook. No API key. Wire format stays inside this module; product layers see
``WorldSourceAdapter`` only.

Verified live 2026-08-22:

- Base: ``https://api.imf.org/external/sdmx/3.0``
- Dataflow: ``IMF.RES/WEO`` (latest = 9.0.0)
- Series key order is COUNTRY.INDICATOR.FREQUENCY, e.g. ``USA.NGDPD.A``.
  ``A.USA.NGDPD`` returns an empty structure.
- ``NGDPD`` observations arrive in US dollars; series SCALE ``9`` means
  divide by 1e9 to store billions (WEO publication unit).
- ``NGDPDPC`` SCALE ``0`` — already US dollars per person.
- ``GGXCNL_NGDP`` (verified live 2026-08-22) — general government net
  lending/borrowing, SCALE ``0``, values already in percent of GDP.
- ``GGXWDG_NGDP`` (verified live 2026-08-27) — general government gross debt,
  SCALE ``0``, percent of GDP.

Public fields must not mention API / SDMX / dataflow. Attribution:
«Source: International Monetary Fund, World Economic Outlook».
Observation-year policy: WEO publishes for the running year an estimate, not a
closed calendar outcome. Flow series (GDP in dollars, budget balance, gross
debt) are stored only through the last closed year; the running year is not an
observation. ``weo_max_observation_year(weo_code)`` encodes this per series
(flow → previous closed year; a future stock series may use the running year).
Medium-term projection years beyond that bound are dropped so the map and
ranking do not treat a far-outlook value as the latest one. They are never
written to ``world_forecasts``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, AsyncIterator, Iterable, Mapping, Sequence

import httpx

from app.services.world_source_adapter import (
    WorldDatasetVersion,
    WorldObservation,
    WorldSeriesPayload,
    WorldSeriesRef,
)

PROVIDER = "imf"
DATASET_ID = "WEO"
PUBLIC_SOURCE_NAME = "Международный валютный фонд"
PUBLIC_SOURCE_NAME_EN = "International Monetary Fund"
PUBLIC_SOURCE_URL = "https://www.imf.org/en/Publications/WEO"
PUBLIC_METHODOLOGY = (
    "Годовая оценка в текущих долларах США. "
    "Source: International Monetary Fund, World Economic Outlook."
)
PUBLIC_METHODOLOGY_EN = (
    "Annual estimate in current US dollars. "
    "Source: International Monetary Fund, World Economic Outlook."
)

SDMX_BASE = "https://api.imf.org/external/sdmx/3.0"
WEO_DATAFLOW = "data/dataflow/IMF.RES/WEO/latest"
_UA = "ForecastEconomy/1.0 (+https://forecasteconomy.com)"

WEO_NGDPD = "NGDPD"
WEO_NGDPDPC = "NGDPDPC"
WEO_GGXCNL_NGDP = "GGXCNL_NGDP"
WEO_GGXWDG_NGDP = "GGXWDG_NGDP"

# Identity + public units. Ranking compares measure_class(unit, unit_ru)
# to WorldConcept.measure — keep these codes in lockstep with world_concepts.
# Per-series public copy (desc_template / keywords / category) lives here so
# the ingest builds no GDP-flavoured text for a fiscal series.
WEO_SERIES: dict[str, dict[str, str]] = {
    WEO_NGDPD: {
        "unit": "BN_USD",
        "unit_ru": "млрд $",
        "unit_en": "billion $",
        "name_ru": "Валовой внутренний продукт в текущих ценах",
        "name_en": "Gross domestic product at current prices",
        "code_suffix": "ngdpd",
        "russia_indicator_code": "weo-gdp-usd",
        "category_ru": "Национальные счета",
        "desc_ru": (
            "{name} — годовая оценка Международного валютного фонда "
            "в текущих долларах США ({unit})."
        ),
        "keywords_ru": "{name}, {country}, ВВП, доллары США",
    },
    WEO_NGDPDPC: {
        "unit": "USD_PC",
        "unit_ru": "$ на человека",
        "unit_en": "$ per person",
        "name_ru": "Валовой внутренний продукт на душу населения в текущих ценах",
        "name_en": "Gross domestic product per capita at current prices",
        "code_suffix": "ngdpdpc",
        "russia_indicator_code": "weo-gdp-per-capita-usd",
        "category_ru": "Национальные счета",
        "desc_ru": (
            "{name} — годовая оценка Международного валютного фонда "
            "в текущих долларах США ({unit})."
        ),
        "keywords_ru": "{name}, {country}, ВВП, доллары США",
    },
    # Общий баланс (чистое кредитование/заимствование) сектора государственного
    # управления в % ВВП; SCALE=0 — значения приходят сразу в процентах.
    WEO_GGXCNL_NGDP: {
        "unit": "PC_GDP",
        "unit_ru": "% ВВП",
        "unit_en": "% of GDP",
        "name_ru": "Баланс бюджета сектора государственного управления",
        "name_en": "General government budget balance",
        "code_suffix": "ggxcnl",
        "russia_indicator_code": "weo-budget-balance-gdp",
        "category_ru": "Государственные финансы",
        "desc_ru": (
            "{name} — годовая оценка Международного валютного фонда "
            "в процентах от валового внутреннего продукта ({unit}); "
            "положительное значение — профицит, отрицательное — дефицит."
        ),
        "keywords_ru": (
            "{name}, {country}, баланс бюджета, дефицит бюджета, "
            "профицит бюджета, % ВВП"
        ),
    },
    # Валовый долг сектора государственного управления в % ВВП; SCALE=0 —
    # значения приходят сразу в процентах. Для стран с полным покрытием
    # Eurostat-направления государственных финансов рейтинг остаётся на
    # национальных определениях; ряд МВФ закрывает страны вне того охвата.
    WEO_GGXWDG_NGDP: {
        "unit": "PC_GDP",
        "unit_ru": "% ВВП",
        "unit_en": "% of GDP",
        "name_ru": "Государственный долг сектора государственного управления",
        "name_en": "General government gross debt",
        "code_suffix": "ggxwdg",
        "russia_indicator_code": "weo-government-debt-gdp",
        "category_ru": "Государственные финансы",
        "desc_ru": (
            "{name} — годовая оценка Международного валютного фонда "
            "в процентах от валового внутреннего продукта ({unit}); "
            "показывает объём накопленных обязательств сектора государственного "
            "управления на конец года."
        ),
        "keywords_ru": (
            "{name}, {country}, государственный долг, госдолг, "
            "долг к ВВП, % ВВП"
        ),
    },
}

# Публичная методология per series (RU/EN): денежные ряды и процентный ряд
# описываются по-разному.
WEO_METHODOLOGY_BY_CODE: dict[str, tuple[str, str]] = {
    WEO_NGDPD: (
        "Годовая оценка в текущих долларах США. "
        "Source: International Monetary Fund, World Economic Outlook.",
        "Annual estimate in current US dollars. "
        "Source: International Monetary Fund, World Economic Outlook.",
    ),
    WEO_NGDPDPC: (
        "Годовая оценка в текущих долларах США. "
        "Source: International Monetary Fund, World Economic Outlook.",
        "Annual estimate in current US dollars. "
        "Source: International Monetary Fund, World Economic Outlook.",
    ),
    WEO_GGXCNL_NGDP: (
        "Сальдо доходов и расходов сектора государственного управления "
        "за год, в процентах от валового внутреннего продукта. "
        "Source: International Monetary Fund, World Economic Outlook.",
        "General government net lending/borrowing for the year, "
        "percent of GDP. "
        "Source: International Monetary Fund, World Economic Outlook.",
    ),
    WEO_GGXWDG_NGDP: (
        "Валовый долг сектора государственного управления на конец года, "
        "в процентах от валового внутреннего продукта, по широкой "
        "классификации государственных финансов Международного валютного "
        "фонда. Для стран с полным покрытием европейского направления "
        "государственных финансов в рейтинге используются национальные "
        "определения долга; остальные страны отражены по оценкам фонда. "
        "Source: International Monetary Fund, World Economic Outlook.",
        "General government gross debt at the end of the year, percent of "
        "GDP, under the fund's broad public finance definitions. For countries "
        "fully covered by the European government finance framework the "
        "ranking uses national debt definitions; other countries are shown by "
        "the fund's estimates. "
        "Source: International Monetary Fund, World Economic Outlook.",
    ),
}


def weo_methodology(weo_code: str, *, locale: str = "ru") -> str:
    ru, en = WEO_METHODOLOGY_BY_CODE[
        (weo_code or "").strip().upper()
    ]
    return en if locale == "en" else ru

# ISO2 (WorldCountry.code / RU overlay) → WEO COUNTRY (ISO3).
# Kosovo has no WEO series; EL/GR and UK/GB share one WEO country.
WEO_ISO3_BY_ISO2: dict[str, str] = {
    "AL": "ALB",
    "AM": "ARM",
    "AT": "AUT",
    "AU": "AUS",
    "AZ": "AZE",
    "BA": "BIH",
    "BE": "BEL",
    "BG": "BGR",
    "BR": "BRA",
    "CA": "CAN",
    "CH": "CHE",
    "CN": "CHN",
    "CY": "CYP",
    "CZ": "CZE",
    "DE": "DEU",
    "DK": "DNK",
    "EE": "EST",
    "EL": "GRC",
    "ES": "ESP",
    "FI": "FIN",
    "FR": "FRA",
    "GB": "GBR",
    "GE": "GEO",
    "GR": "GRC",
    "HR": "HRV",
    "HU": "HUN",
    "IE": "IRL",
    "IL": "ISR",
    "IN": "IND",
    "IS": "ISL",
    "IT": "ITA",
    "JP": "JPN",
    "KR": "KOR",
    "LT": "LTU",
    "LU": "LUX",
    "LV": "LVA",
    "MD": "MDA",
    "ME": "MNE",
    "MK": "MKD",
    "MT": "MLT",
    "MX": "MEX",
    "NL": "NLD",
    "NO": "NOR",
    "NZ": "NZL",
    "PL": "POL",
    "PT": "PRT",
    "RO": "ROU",
    "RS": "SRB",
    "RU": "RUS",
    "SE": "SWE",
    "SI": "SVN",
    "SK": "SVK",
    "TR": "TUR",
    "UA": "UKR",
    "UK": "GBR",
    "US": "USA",
    "ZA": "ZAF",
}


@dataclass(frozen=True)
class WeoParsedPoint:
    """One WEO observation after SCALE is applied (storage unit)."""

    country_iso3: str
    weo_code: str
    period: date
    value: float
    scale: int = 0


# Политика года наблюдений по коду серии (D1). Поточные показатели
# получают наблюдения только по закрытым календарным годам: оценка МВФ за
# текущий год ещё не годовой итог и в шапке рейтинга выглядела бы как
# состоявшееся значение. Стоковые показатели (население, безработица) —
# уровень на дату; их текущий год допустим. Новый код серии обязан явственно
# выбрать политику: KeyError при добавлении серии без записи здесь —
# осознанный предохранитель.
WEO_YEAR_POLICY_BY_CODE: dict[str, str] = {
    WEO_NGDPD: "closed",
    WEO_NGDPDPC: "closed",
    WEO_GGXCNL_NGDP: "closed",
    WEO_GGXWDG_NGDP: "closed",
}

_YEAR_POLICY_CLOSED = "closed"
_YEAR_POLICY_STOCK = "stock"


def weo_max_observation_year(
    weo_code: str | None = None, today: date | None = None
) -> int:
    """Последний год, который пишем как наблюдение для серии ``weo_code``.

    Поточные серии ("closed") — только закрытые годы: today.year - 1.
    Стоковые ("stock") — текущий год допустим. Дефолт ``weo_code=None``
    возвращает today.year для обратной совместимости со старыми вызовами;
    оба боевых вызова (ingest и парсер каталога) передают фактический код.
    """
    year = (today or date.today()).year
    if weo_code is None:
        return year
    policy = WEO_YEAR_POLICY_BY_CODE.get((weo_code or "").strip().upper())
    if policy is None:
        raise KeyError(f"Unknown WEO year policy for series: {weo_code!r}")
    return year - 1 if policy == _YEAR_POLICY_CLOSED else year


def weo_iso3_for(iso2: str) -> str | None:
    code = (iso2 or "").strip().upper()
    return WEO_ISO3_BY_ISO2.get(code)


def weo_series_meta(weo_code: str) -> dict[str, str]:
    meta = WEO_SERIES.get((weo_code or "").strip().upper())
    if meta is None:
        raise KeyError(f"Unsupported WEO series: {weo_code!r}")
    return meta


def world_indicator_code(iso2: str, weo_code: str) -> str:
    meta = weo_series_meta(weo_code)
    return f"{iso2.strip().lower()}-weo-{meta['code_suffix']}"


def make_weo_series_ref(iso2: str, weo_code: str) -> WorldSeriesRef:
    iso2_n = iso2.strip().upper()
    code = weo_code.strip().upper()
    meta = weo_series_meta(code)
    return WorldSeriesRef(
        provider=PROVIDER,
        dataset_id=DATASET_ID,
        series_id=code,
        country_code=iso2_n,
        frequency="annual",
        unit_code=meta["unit"],
        dimensions={"weo_code": code},
        title=meta["name_en"],
        source_url=PUBLIC_SOURCE_URL,
    )


def weo_data_url(iso3_codes: Sequence[str], weo_code: str) -> str:
    countries = "+".join(code.strip().upper() for code in iso3_codes if code.strip())
    indicator = weo_code.strip().upper()
    return f"{SDMX_BASE}/{WEO_DATAFLOW}/{countries}.{indicator}.A"


def _dim_code(entry: Mapping[str, Any] | None) -> str:
    if not entry:
        return ""
    for key in ("id", "value", "name"):
        raw = entry.get(key)
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    return ""


def _period_to_date(entry: Mapping[str, Any] | str | None) -> date | None:
    if entry is None:
        return None
    if isinstance(entry, str):
        text = entry.strip()
    else:
        text = _dim_code(entry)
    if len(text) == 4 and text.isdigit():
        year = int(text)
        if 1800 <= year <= 2100:
            return date(year, 1, 1)
    return None


def _scale_from_id(raw: Any) -> int:
    text = str(raw or "").strip()
    if not text:
        return 0
    try:
        value = int(text)
    except ValueError:
        return 0
    return value if value > 0 else 0


def _series_scale(structure: Mapping[str, Any], attribute_indexes: Sequence[Any] | None) -> int:
    attrs = ((structure.get("attributes") or {}).get("series") or [])
    if not attrs:
        return 0
    scale_pos = next(
        (i for i, item in enumerate(attrs) if str(item.get("id") or "").upper() == "SCALE"),
        None,
    )
    if scale_pos is None:
        return 0
    values = attrs[scale_pos].get("values") or []
    chosen = None
    if attribute_indexes and scale_pos < len(attribute_indexes):
        idx = attribute_indexes[scale_pos]
        if isinstance(idx, int) and 0 <= idx < len(values):
            chosen = values[idx]
    if chosen is None and values:
        chosen = values[0]
    return _scale_from_id(_dim_code(chosen) if isinstance(chosen, Mapping) else chosen)


def _float_or_none(raw: Any) -> float | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, (list, tuple)):
        if not raw:
            return None
        return _float_or_none(raw[0])
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def parse_imf_weo_sdmx(payload: Mapping[str, Any]) -> list[WeoParsedPoint]:
    """Чистый разбор SDMX 3.0 JSON → точки в единице хранения (млрд $ / $)."""
    data = payload.get("data") if isinstance(payload.get("data"), Mapping) else payload
    if not isinstance(data, Mapping):
        return []
    datasets = data.get("dataSets") or []
    structures = data.get("structures") or []
    if not datasets or not structures:
        return []
    structure = structures[0] if isinstance(structures[0], Mapping) else {}
    dims = (structure.get("dimensions") or {}) if isinstance(structure, Mapping) else {}
    series_dims = list(dims.get("series") or [])
    obs_dims = list(dims.get("observation") or [])
    time_values = list((obs_dims[0] or {}).get("values") or []) if obs_dims else []

    country_pos = next(
        (i for i, item in enumerate(series_dims) if str(item.get("id") or "").upper() == "COUNTRY"),
        0,
    )
    indicator_pos = next(
        (
            i
            for i, item in enumerate(series_dims)
            if str(item.get("id") or "").upper() == "INDICATOR"
        ),
        1,
    )

    out: list[WeoParsedPoint] = []
    for dataset in datasets:
        if not isinstance(dataset, Mapping):
            continue
        series_map = dataset.get("series") or {}
        if not isinstance(series_map, Mapping):
            continue
        for key, series in series_map.items():
            if not isinstance(series, Mapping):
                continue
            parts = [int(part) for part in str(key).split(":") if part.isdigit()]
            country = ""
            weo_code = ""
            if country_pos < len(series_dims) and country_pos < len(parts):
                values = list(series_dims[country_pos].get("values") or [])
                idx = parts[country_pos]
                if 0 <= idx < len(values):
                    country = _dim_code(values[idx]).upper()
            if indicator_pos < len(series_dims) and indicator_pos < len(parts):
                values = list(series_dims[indicator_pos].get("values") or [])
                idx = parts[indicator_pos]
                if 0 <= idx < len(values):
                    weo_code = _dim_code(values[idx]).upper()
            if weo_code not in WEO_SERIES or not country:
                continue
            scale = _series_scale(structure, series.get("attributes"))
            divisor = 10.0 ** scale if scale else 1.0
            observations = series.get("observations") or {}
            if not isinstance(observations, Mapping):
                continue
            for obs_key, raw_value in observations.items():
                try:
                    time_idx = int(obs_key)
                except (TypeError, ValueError):
                    continue
                if not (0 <= time_idx < len(time_values)):
                    continue
                period = _period_to_date(time_values[time_idx])
                value = _float_or_none(raw_value)
                if period is None or value is None:
                    continue
                if period.year > weo_max_observation_year(weo_code):
                    continue
                out.append(
                    WeoParsedPoint(
                        country_iso3=country,
                        weo_code=weo_code,
                        period=period,
                        value=value / divisor,
                        scale=scale,
                    )
                )
    out.sort(key=lambda item: (item.country_iso3, item.weo_code, item.period))
    return out


def points_for_iso3(
    parsed: Sequence[WeoParsedPoint],
    iso3: str,
    weo_code: str,
) -> list[tuple[date, float]]:
    iso3_n = iso3.strip().upper()
    code = weo_code.strip().upper()
    return [
        (item.period, item.value)
        for item in parsed
        if item.country_iso3 == iso3_n and item.weo_code == code
    ]


def _payload_hash(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _fetch_weo_json(url: str) -> dict[str, Any]:
    with httpx.Client(
        timeout=60.0,
        headers={"User-Agent": _UA, "Accept": "application/json"},
        follow_redirects=True,
    ) as client:
        response = client.get(url)
        response.raise_for_status()
        data = response.json()
    if not isinstance(data, dict):
        raise ValueError("IMF WEO response is not a JSON object")
    return data


class ImfWeoAdapter:
    """WorldSourceAdapter for IMF WEO current-USD GDP series."""

    provider = PROVIDER
    public_source_name = PUBLIC_SOURCE_NAME

    def __init__(
        self,
        *,
        country_codes: Sequence[str],
        fetch_json=None,
    ) -> None:
        seen: list[str] = []
        for raw in country_codes:
            iso2 = (raw or "").strip().upper()
            if not iso2 or iso2 in seen:
                continue
            if weo_iso3_for(iso2) is None:
                continue
            seen.append(iso2)
        self._country_codes = tuple(seen)
        self._fetch_json = fetch_json or _fetch_weo_json

    async def list_datasets(self) -> AsyncIterator[WorldDatasetVersion]:
        yield WorldDatasetVersion(
            provider=PROVIDER,
            dataset_id=DATASET_ID,
            title="World Economic Outlook",
            metadata_url=PUBLIC_SOURCE_URL,
        )

    async def list_series(
        self, dataset: WorldDatasetVersion
    ) -> AsyncIterator[WorldSeriesRef]:
        if dataset.dataset_id != DATASET_ID:
            return
        for iso2 in self._country_codes:
            for weo_code in WEO_SERIES:
                yield make_weo_series_ref(iso2, weo_code)

    async def fetch_series(
        self,
        series: WorldSeriesRef,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> WorldSeriesPayload:
        iso3 = weo_iso3_for(series.country_code)
        if iso3 is None:
            raise ValueError(f"No WEO country for {series.country_code}")
        weo_code = (series.dimensions or {}).get("weo_code") or series.series_id
        url = weo_data_url([iso3], weo_code)
        fetched_at = datetime.now(timezone.utc).replace(tzinfo=None)
        payload = self._fetch_json(url)
        parsed = parse_imf_weo_sdmx(payload)
        observations = [
            WorldObservation(period=period, value=value)
            for period, value in points_for_iso3(parsed, iso3, weo_code)
            if (date_from is None or period >= date_from)
            and (date_to is None or period <= date_to)
        ]
        return WorldSeriesPayload(
            ref=series,
            observations=observations,
            fetched_at=fetched_at,
            source_hash=_payload_hash(payload),
        )

    def fetch_weo_code(self, weo_code: str, iso3_codes: Iterable[str]) -> list[WeoParsedPoint]:
        """Один HTTP на код WEO × набор ISO3 — для ingest, не для product-слоя.

        Граница года наблюдений считается здесь по фактическому коду серии
        (политика года из ``WEO_YEAR_POLICY_BY_CODE``): поточные серии не
        получают наблюдений за незакрывшийся год даже если источник вернул
        оценку текущего года.
        """
        countries = [code.strip().upper() for code in iso3_codes if code and code.strip()]
        if not countries:
            return []
        url = weo_data_url(countries, weo_code)
        payload = self._fetch_json(url)
        max_year = weo_max_observation_year(weo_code)
        wanted = weo_code.strip().upper()
        return [
            item
            for item in parse_imf_weo_sdmx(payload)
            if item.weo_code == wanted and item.period.year <= max_year
        ]

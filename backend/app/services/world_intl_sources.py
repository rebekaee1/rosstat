"""Международные издатели для стран мира: BIS, Всемирный банк, МОТ (19.11.2026).

Три источника дополняют страны каталога `world_countries` там, где у страны нет своего
национального ряда того же смысла (ADR-0012, official-first): международный издатель здесь —
канонический для межстранового ряда, а не замена национальному.

- **BIS** `WS_CBPOL` — ключевые ставки центральных банков, месяц, конец периода. Условия BIS
  (data.bis.org/help/legal, проверено 19.11.2026): использование свободное, в том числе в коммерческом
  продукте, если за сами цифры не берут отдельную плату; источник — BIS; перевод — не официальный
  перевод BIS; не инвестиционная рекомендация.
- **Всемирный банк** WDI — индекс Джини, доля населения за чертой крайней бедности ($3 в день), доля
  доходов 10 % самых обеспеченных, продолжительность жизни; год; CC BY 4.0.
- **МОТ** (ILOSTAT, модельные оценки) — безработица молодёжи 15–24 лет; год; CC BY 4.0. Будущие годы
  модели (прогноз МОТ) отбрасываются: публикуются только закрытые годы.

Модуль чистый: разбор ответов и описание рядов. Запись в базу — `world_intl_ingest`.
"""

from __future__ import annotations

import csv
import io
import json
import math
from dataclasses import dataclass
from datetime import date
from typing import Iterable

BIS_PROVIDER = "bis"
WB_PROVIDER = "worldbank"
ILO_PROVIDER = "ilo"

BIS_DATASET = "ws_cbpol"
WB_DATASET = "wdi"
ILO_DATASET = "ilostat"

BIS_URL = "https://stats.bis.org/api/v1/data/WS_CBPOL/M.{areas}/all?format=csv"
WB_URL = "https://api.worldbank.org/v2/country/{iso3}/indicator/{code}?format=json&per_page=20000&date=1960:{year}"
ILO_URL = (
    "https://rplumber.ilo.org/data/indicator/?id={indicator}&ref_area={iso3}"
    "&sex=SEX_T&classif1={classif}&timefrom=1990&format=.csv"
)

# Код страны каталога (ISO-2 с исключениями Евростата) → код BIS.
BIS_AREA_BY_ISO2 = {"UK": "GB", "EL": "GR"}


@dataclass(frozen=True)
class IntlSeries:
    provider: str
    dataset_id: str
    series_id: str  # код ряда у издателя — единственное измерение среза
    code_suffix: str  # хвост кода карточки: {iso2}-{code_suffix}
    concept_slug: str
    name_ru: str
    name_en: str
    unit: str
    unit_ru: str
    frequency: str
    category_ru: str
    source_ru: str
    source_url: str
    description_ru: str
    methodology_ru: str
    keywords_ru: str


_BIS_SOURCE = "Банк международных расчётов (BIS)"
_WB_SOURCE = "Всемирный банк"
_ILO_SOURCE = "Международная организация труда (МОТ)"

SERIES: tuple[IntlSeries, ...] = (
    IntlSeries(
        provider=BIS_PROVIDER, dataset_id=BIS_DATASET, series_id="CBPOL", code_suffix="bis-policy-rate",
        concept_slug="policy-rate",
        name_ru="Ключевая ставка центрального банка", name_en="Central bank policy rate",
        unit="PC", unit_ru="% годовых", frequency="monthly", category_ru="Финансы",
        source_ru=_BIS_SOURCE, source_url="https://data.bis.org/topics/CBPOL",
        description_ru=(
            "Ключевая ставка центрального банка — главный инструмент денежно-кредитной политики: от неё "
            "зависят ставки по кредитам и вкладам. Значение на конец месяца."
        ),
        methodology_ru=(
            "Ставка, которую центральный банк объявляет основной для своей политики, на последний день "
            "месяца. Банк международных расчётов собирает ставки у центральных банков и публикует их в "
            "одном ряду; если банк сменил основную ставку, ряд продолжается новой ставкой с даты смены. "
            "Сравнивать страны можно по уровню: везде это процент годовых. Перевод названий выполнен "
            "Forecast Economy и не является официальным переводом BIS."
        ),
        keywords_ru="ключевая ставка {country}, ставка центрального банка {country}, ставка ЦБ {country}",
    ),
    IntlSeries(
        provider=WB_PROVIDER, dataset_id=WB_DATASET, series_id="SI.POV.GINI", code_suffix="wb-gini",
        concept_slug="gini-index",
        name_ru="Индекс Джини", name_en="Gini index",
        unit="GINI", unit_ru="пунктов из 100", frequency="annual", category_ru="Общество",
        source_ru=_WB_SOURCE, source_url="https://data.worldbank.org/indicator/SI.POV.GINI",
        description_ru=(
            "Индекс Джини показывает неравенство доходов или потребления: 0 — у всех поровну, 100 — всё "
            "у одного человека."
        ),
        methodology_ru=(
            "Всемирный банк считает индекс по обследованиям домохозяйств страны. В одних странах в основе "
            "доходы, в других — расходы на потребление, поэтому сравнение стран приблизительное. Обследования "
            "проходят не каждый год: в ряду бывают пропуски, последнее значение может быть за прошлые годы."
        ),
        keywords_ru="индекс Джини {country}, коэффициент Джини {country}, неравенство доходов {country}",
    ),
    IntlSeries(
        provider=WB_PROVIDER, dataset_id=WB_DATASET, series_id="SI.POV.DDAY", code_suffix="wb-poverty-3usd",
        concept_slug="poverty-rate",
        name_ru="Доля населения в крайней бедности", name_en="Population in extreme poverty",
        unit="PC_POP", unit_ru="% населения", frequency="annual", category_ru="Общество",
        source_ru=_WB_SOURCE, source_url="https://data.worldbank.org/indicator/SI.POV.DDAY",
        description_ru=(
            "Доля людей, которые живут меньше чем на 3 доллара в день по паритету покупательной "
            "способности 2021 года, — международная черта крайней бедности."
        ),
        methodology_ru=(
            "Всемирный банк пересчитывает доходы или расходы из обследований домохозяйств в доллары по "
            "паритету покупательной способности и считает долю людей ниже черты 3 доллара в день. Черта одна "
            "для всех стран, поэтому страны можно сравнивать между собой. Национальная черта бедности обычно "
            "выше, и её доля больше. Обследования проходят не каждый год."
        ),
        keywords_ru="уровень бедности {country}, крайняя бедность {country}, доля бедных {country}",
    ),
    IntlSeries(
        provider=WB_PROVIDER, dataset_id=WB_DATASET, series_id="SI.DST.10TH.10", code_suffix="wb-income-top10",
        concept_slug="income-share-top10",
        name_ru="Доля доходов 10% самых обеспеченных", name_en="Income share held by the richest 10%",
        unit="PC", unit_ru="% всех доходов", frequency="annual", category_ru="Общество",
        source_ru=_WB_SOURCE, source_url="https://data.worldbank.org/indicator/SI.DST.10TH.10",
        description_ru="Какая часть всех доходов или расходов страны приходится на 10% самых обеспеченных людей.",
        methodology_ru=(
            "Всемирный банк делит население по доходу или потреблению на десять равных групп и считает долю "
            "верхней группы в общей сумме. Основа — те же обследования домохозяйств, что и для индекса Джини; "
            "обследования проходят не каждый год."
        ),
        keywords_ru="доля доходов богатых {country}, доходы 10% самых богатых {country}, неравенство {country}",
    ),
    IntlSeries(
        provider=WB_PROVIDER, dataset_id=WB_DATASET, series_id="SP.DYN.LE00.IN", code_suffix="wb-life-expectancy",
        concept_slug="life-expectancy",
        name_ru="Ожидаемая продолжительность жизни при рождении", name_en="Life expectancy at birth",
        unit="YR", unit_ru="лет", frequency="annual", category_ru="Население",
        source_ru=_WB_SOURCE, source_url="https://data.worldbank.org/indicator/SP.DYN.LE00.IN",
        description_ru=(
            "Сколько лет в среднем прожил бы новорождённый, если бы смертность в каждом возрасте осталась "
            "такой, как в этом году."
        ),
        methodology_ru=(
            "Всемирный банк публикует оценки Отдела народонаселения ООН и национальных статистических "
            "служб. Значение считается по смертности всех возрастов за год, для мужчин и женщин вместе."
        ),
        keywords_ru="продолжительность жизни {country}, средняя продолжительность жизни {country}",
    ),
    IntlSeries(
        provider=ILO_PROVIDER, dataset_id=ILO_DATASET, series_id="UNE_2EAP_SEX_AGE_RT_A:Y15-24",
        code_suffix="ilo-youth-unemployment",
        concept_slug="youth-unemployment-rate",
        name_ru="Безработица молодёжи 15–24 лет", name_en="Youth unemployment rate, ages 15–24",
        unit="PC_ACT", unit_ru="% экономически активного населения 15–24 лет", frequency="annual",
        category_ru="Рынок труда",
        source_ru=_ILO_SOURCE, source_url="https://ilostat.ilo.org/data/",
        description_ru="Доля безработных среди молодых людей 15–24 лет, которые работают или ищут работу.",
        methodology_ru=(
            "Международная организация труда приводит обследования рабочей силы разных стран к одному "
            "определению безработицы и одному возрасту, 15–24 года. Где обследования нет, МОТ даёт свою "
            "оценку по модели. Показаны только закрытые годы; прогноз МОТ на текущий и следующий год не "
            "публикуется."
        ),
        keywords_ru="безработица молодёжи {country}, молодёжная безработица {country}, безработица 15-24 {country}",
    ),
)

SERIES_BY_SUFFIX = {item.code_suffix: item for item in SERIES}


def indicator_code(iso2: str, series: IntlSeries) -> str:
    return f"{iso2.strip().lower()}-{series.code_suffix}"


def _finite(raw) -> float | None:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def bis_area(iso2: str) -> str:
    code = iso2.strip().upper()
    return BIS_AREA_BY_ISO2.get(code, code)


def parse_bis_csv(text: str) -> dict[str, list[tuple[date, float]]]:
    """CSV BIS → {код BIS: [(первое число месяца, ставка)]}; NaN и пустые значения пропускаются."""
    out: dict[str, list[tuple[date, float]]] = {}
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    for row in reader:
        if (row.get("FREQ") or "").strip() != "M":
            continue
        period = (row.get("TIME_PERIOD") or "").strip()
        value = _finite(row.get("OBS_VALUE"))
        if len(period) != 7 or value is None:
            continue
        out.setdefault((row.get("REF_AREA") or "").strip(), []).append(
            (date(int(period[:4]), int(period[5:7]), 1), value)
        )
    for points in out.values():
        points.sort()
    return out


def parse_wb_json(text: str) -> dict[str, list[tuple[date, float]]]:
    """Ответ WDI → {ISO-3: [(1 января года, значение)]}; пустые годы пропускаются."""
    payload = json.loads(text)
    if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[1], list):
        message = payload[0].get("message") if isinstance(payload, list) and payload and isinstance(payload[0], dict) else None
        if message:
            raise ValueError(f"World Bank API error: {message}")
        return {}
    out: dict[str, list[tuple[date, float]]] = {}
    for row in payload[1]:
        value = _finite(row.get("value"))
        year = str(row.get("date") or "")
        iso3 = str(row.get("countryiso3code") or "").strip().upper()
        if value is None or not year.isdigit() or not iso3:
            continue
        out.setdefault(iso3, []).append((date(int(year), 1, 1), value))
    for points in out.values():
        points.sort()
    return out


def parse_ilo_csv(text: str, *, classif: str, last_closed_year: int) -> dict[str, list[tuple[date, float]]]:
    """CSV ILOSTAT → {ISO-3: [(1 января года, %)]}; только нужная группа возраста и закрытые годы."""
    out: dict[str, list[tuple[date, float]]] = {}
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    for row in reader:
        if (row.get("classif1") or "") != classif or (row.get("sex") or "") != "SEX_T":
            continue
        year = str(row.get("time") or "")
        value = _finite(row.get("obs_value"))
        if not year.isdigit() or value is None or int(year) > last_closed_year:
            continue
        out.setdefault(str(row.get("ref_area") or "").upper(), []).append((date(int(year), 1, 1), value))
    for points in out.values():
        points.sort()
    return out


ILO_AGE_CLASSIF = {"Y15-24": "AGE_YTHADULT_Y15-24"}


def ilo_request(series: IntlSeries) -> tuple[str, str]:
    indicator, age = series.series_id.split(":", 1)
    return indicator, ILO_AGE_CLASSIF[age]


def dedupe_points(points: Iterable[tuple[date, float]]) -> list[tuple[date, float]]:
    by_date: dict[date, float] = {}
    for when, value in points:
        by_date[when] = value
    return sorted(by_date.items())

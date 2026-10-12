"""Устаревшие дубли мировых рядов: у источника ряд остановлен, рядом живёт канонический.

Круг 12 (12.10.2026). Образец: Евростат с января 2026 перевёл гармонизированный
ИПЦ на ECOICOP ver.2; набор `prc_hicp_cind` («при постоянных налоговых ставках»,
ECOICOP ver.1) закончился декабрём 2025, а основной индекс (`prc_hicp_minr`)
идёт до августа 2026. Человек, открывший карточку cind, видел «Устарело: данные до
декабря 2025» и делал вывод, что за 2026 год данных нет, хотя актуальный показатель
рядом. Правило «один показатель — один смысл»: такой дубль

* не листингуется (`is_listed=false`, значит нет ни в каталоге страны, ни в sitemap);
* исключён из поисковой выдачи;
* страница ряда отвечает 301 на каноническую карточку страны (оба языка,
  годовые страницы сохраняют год, если у канона есть этот год).

Состав списка проверяется оглавлением Евростата (`toc/txt`): дата последних данных
набора совпадает с периодом заморозки. Наборы `prc_hicp_midx/manr/mmor/mv12r/aind/fp`
сюда не входят: у них уже есть слияние с карточкой minr (`CATALOG_STEM_ALIASES`) и
301 (`resolve_world_hicp_successor`), снятие их с листинга сломало бы эти группы.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SupersededDataset:
    successor_dataset: str
    frozen_through: str          # последний период данных у источника
    reason: str


SUPERSEDED_WORLD_DATASETS: dict[str, SupersededDataset] = {
    "prc_hicp_cind": SupersededDataset(
        "prc_hicp_minr", "2025-12",
        "ИПЦ при постоянных налоговых ставках (ECOICOP ver.1): набор закрыт Евростатом "
        "в декабре 2025; актуальный гармонизированный индекс — prc_hicp_minr (ECOICOP ver.2).",
    ),
    "prc_hicp_cann": SupersededDataset(
        "prc_hicp_minr", "2025-12",
        "Темп ИПЦ при постоянных налогах (ver.1), закрыт в декабре 2025; режим yoy карточки minr.",
    ),
    "prc_hicp_cmon": SupersededDataset(
        "prc_hicp_minr", "2025-12",
        "Помесячный темп ИПЦ при постоянных налогах (ver.1), закрыт в декабре 2025; режим step карточки minr.",
    ),
}

# Единица замороженного ряда → режим канонической карточки.
_MODE_BY_UNIT = {"RCH_A": "yoy", "RCH_M": "step", "RCH_MV12MAVR": "yoy"}

# Только заголовочный срез (все товары и услуги) имеет канонический аналог;
# подгруппы ECOICOP (CP01…) в ver.2 имеют другие коды и не перенаправляются.
_HEADLINE_COICOP = frozenset({"CP00", "TOTAL"})

_CODE_PREFIX_RE = re.compile(r"^([a-z]{2,3})-")


def is_superseded_dataset(dataset_id: str | None) -> bool:
    return (dataset_id or "") in SUPERSEDED_WORLD_DATASETS


def superseded_dataset_ids() -> tuple[str, ...]:
    return tuple(SUPERSEDED_WORLD_DATASETS)


def superseded_target(
    dataset_id: str | None, code: str, slice_json: dict | None, unit: str | None,
) -> tuple[str, str | None] | None:
    """(код канонической карточки, режим или None) для замороженного дубля.

    Чистая функция: код канона строится из кода страны и заголовочного среза
    набора-преемника. None — у среза нет канонического аналога.
    """
    spec = SUPERSEDED_WORLD_DATASETS.get(dataset_id or "")
    if spec is None:
        return None
    sl = slice_json or {}
    coicop = str(sl.get("coicop") or sl.get("coicop18") or "").upper()
    if coicop not in _HEADLINE_COICOP:
        return None
    match = _CODE_PREFIX_RE.match(code or "")
    if not match:
        return None
    canonical = f"{match.group(1)}-{spec.successor_dataset}-total-i15"
    unit_code = (unit or sl.get("unit") or "").strip().upper().replace("-", "_")
    return canonical, _MODE_BY_UNIT.get(unit_code)

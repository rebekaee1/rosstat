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
набора совпадает с периодом заморозки. Наборы `prc_hicp_midx/manr/mmor/mv12r`
сюда не входят: у них уже есть слияние с карточкой minr (`CATALOG_STEM_ALIASES`) и
301 (`resolve_world_hicp_successor`), снятие их с листинга сломало бы эти группы.

Круг 13 (12.10.2026) добавил два класса того же рода:

* `prc_hicp_fp` (первые публикации ГИПЦ, ECOICOP ver.1, данные до 2025-12) → `prc_hicp_fpd`
  (то же, ECOICOP ver.2, данные до 2026-08, база 2015=100, значения совпадают до 0,04).
  У Франции эта карточка оставалась в листинге с пометкой «Устарело» без ссылки на живую.
* `prc_ppp_ind` (паритеты покупательной способности, COICOP 1999, данные до 2024) →
  `prc_ppp_ind_1` (COICOP 2018, до 2025). Карта кодов групп не нужна: в листинге стоят только
  заголовочные срезы (`ppp_cat = GDP`, он общий для обеих классификаций), подгруппы
  не перенаправляются. Меры старых составов ЕС (EU15, EU28, EU27_2007) аналога не имеют и
  остаются как есть.

`prc_hicp_aind` → `prc_hicp_ainr` сознательно НЕ добавлен: у ainr база 2025=100, у aind 2015=100,
это разные представления, а не один ряд.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SupersededDataset:
    successor_dataset: str
    frozen_through: str          # последний период данных у источника
    reason: str
    # Какие измерения среза говорят «заголовочный срез» и какими значениями.
    headline_dims: tuple[str, ...] = ("coicop", "coicop18")
    headline_values: frozenset[str] = frozenset({"CP00", "TOTAL"})
    # Хвост кода канона после набора («total-i15»); None — хвост кода берётся из самого ряда.
    canonical_tail: str | None = "total-i15"
    # True — набор снимается с листинга целиком (в загрузчике), даже срезы без канона.
    whole_dataset: bool = False


SUPERSEDED_WORLD_DATASETS: dict[str, SupersededDataset] = {
    "prc_hicp_cind": SupersededDataset(
        "prc_hicp_minr", "2025-12",
        "ИПЦ при постоянных налоговых ставках (ECOICOP ver.1): набор закрыт Евростатом "
        "в декабре 2025; актуальный гармонизированный индекс — prc_hicp_minr (ECOICOP ver.2).",
        whole_dataset=True,
    ),
    "prc_hicp_cann": SupersededDataset(
        "prc_hicp_minr", "2025-12",
        "Темп ИПЦ при постоянных налогах (ver.1), закрыт в декабре 2025; режим yoy карточки minr.",
        whole_dataset=True,
    ),
    "prc_hicp_cmon": SupersededDataset(
        "prc_hicp_minr", "2025-12",
        "Помесячный темп ИПЦ при постоянных налогах (ver.1), закрыт в декабре 2025; режим step карточки minr.",
        whole_dataset=True,
    ),
    "prc_hicp_fp": SupersededDataset(
        "prc_hicp_fpd", "2025-12",
        "Первые публикации ГИПЦ (ECOICOP ver.1), закрыты в декабре 2025; продолжение — "
        "prc_hicp_fpd (ver.2, та же база 2015=100).",
        canonical_tail="total-fin-i15",
    ),
    "prc_ppp_ind": SupersededDataset(
        "prc_ppp_ind_1", "2024",
        "Паритеты покупательной способности по COICOP 1999: набор остановлен в 2025 году; "
        "продолжение — prc_ppp_ind_1 (COICOP 2018). Перенаправляется только заголовочный срез GDP.",
        headline_dims=("ppp_cat", "ppp_cat18"),
        headline_values=frozenset({"GDP"}),
        canonical_tail=None,
    ),
    "nama_10_co3_p3": SupersededDataset(
        "nama_10_cp18", "2022",
        "Конечное потребление домохозяйств по целям, % ВВП, по COICOP 1999: набор остановлен "
        "(данные до 2022–2024 в зависимости от страны); продолжение — nama_10_cp18 (COICOP 2018), "
        "значения совпадают. Перенаправляется только срез TOTAL.",
        canonical_tail=None,
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
    """Наборы, которые поиск исключает целиком (cind/cann/cmon).

    Остальные классы (fp, prc_ppp_ind, nama_10_co3_p3) поиск отсекает через `is_listed`: снятые
    скриптом срезы в выдачу не попадают, а срезы без канона (старые составы ЕС, страны без
    набора-преемника) остаются в каталоге и поиске, как и их страницы.
    """
    return tuple(k for k, v in SUPERSEDED_WORLD_DATASETS.items() if v.whole_dataset)


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
    value = ""
    for dim in spec.headline_dims:
        raw = sl.get(dim)
        if raw:
            value = str(raw).upper()
            break
    if value not in spec.headline_values:
        return None
    match = _CODE_PREFIX_RE.match(code or "")
    if not match:
        return None
    tail = spec.canonical_tail
    if tail is None:
        own = re.match(rf"^[a-z]{{2,3}}-{re.escape(dataset_id or '')}-(.+)$", code or "")
        if not own:
            return None
        tail = own.group(1)
    canonical = f"{match.group(1)}-{spec.successor_dataset}-{tail}"
    unit_code = (unit or sl.get("unit") or "").strip().upper().replace("-", "_")
    return canonical, _MODE_BY_UNIT.get(unit_code)


async def live_superseded_canonical(
    db, country_id: int, dataset_id: str | None, code: str,
    slice_json: dict | None, unit: str | None, history_start=None,
):
    """Листингованная карточка-канон для замороженного ряда или None.

    Для классов кроме cind/cann/cmon канон обязан начинаться не позже старого ряда:
    иначе уход на него отнимал бы у читателя годы истории (у Дании и Финляндии
    набор ver.2 короче ver.1). Без такого канона карточка остаётся архивом с блоком
    «Актуальные данные», который ссылается на ближайший живой показатель.
    """
    spec = SUPERSEDED_WORLD_DATASETS.get(dataset_id or "")
    target = superseded_target(dataset_id, code, slice_json, unit)
    if spec is None or target is None:
        return None
    from sqlalchemy import select

    from app.models import WorldIndicator

    canonical = (
        await db.execute(
            select(WorldIndicator).where(
                WorldIndicator.country_id == country_id,
                WorldIndicator.code == target[0],
                WorldIndicator.is_listed.is_(True),
                WorldIndicator.points_count > 0,
            ).limit(1)
        )
    ).scalar_one_or_none()
    if canonical is None:
        return None
    if (
        not spec.whole_dataset
        and history_start is not None
        and canonical.history_start is not None
        and canonical.history_start > history_start
    ):
        return None
    return canonical


async def should_unlist_superseded(
    db, country_id: int, dataset_id: str | None, code: str,
    slice_json: dict | None, unit: str | None, history_start=None,
) -> bool:
    """Снимать ли ряд с листинга при загрузке и пересчёте листинга.

    Наборы cind/cann/cmon снимаются целиком (закрыты у источника, подгруппы ver.1
    ведут в никуда). Остальные классы (fp, prc_ppp_ind, nama_10_co3_p3) — только если
    у среза есть канон, в этой стране он сейчас листингован с данными и не короче по
    истории: иначе страница осталась бы без замены. Совпадает с проверкой
    `scripts/unlist-superseded-world.py`, поэтому ежесуточная загрузка не возвращает
    снятую карточку в каталог.
    """
    spec = SUPERSEDED_WORLD_DATASETS.get(dataset_id or "")
    if spec is None:
        return False
    if spec.whole_dataset:
        return True
    return await live_superseded_canonical(
        db, country_id, dataset_id, code, slice_json, unit, history_start,
    ) is not None


def successor_dataset_of(dataset_id: str | None) -> str | None:
    """Набор-преемник замороженного набора (для поиска «ближайшего актуального»)."""
    spec = SUPERSEDED_WORLD_DATASETS.get(dataset_id or "")
    return spec.successor_dataset if spec else None

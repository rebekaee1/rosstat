"""Достоверные единицы измерения Eurostat для мирового блока.

Инвариант (репутация): единицу НЕЛЬЗЯ угадывать по голому коду.
Коды вроде RT / NR / RAT полисемичны: «Rate» бывает «на 1000 живорождённых»,
«на 1000 жителей», «детей на женщину». Ошибочный «%» вместо «на 1000»
уничтожает доверие (см. working-agreement.mdc, инцидент «100,2%»).

Источник правды (в порядке приоритета):
  1. curated override набора / набора+кода / indic-кода в срезе;
  2. человекочитаемая англ. метка члена кодлиста unit (из JSON-stat или
     глобального SDMX UNIT), переведённая словарём — только если метка
     однозначна (не «Rate» / «Number» / «Average» / «Index» / «Ratio»).
  3. иначе unit_ru = None → индикатор НЕ листингуется.

Чувствительные темы (аборты, мертворождения) — явный exclude-список:
макроэкономическая витрина, не медстатистика.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

# ---------------------------------------------------------------------------
# Чувствительные темы — не показываем в каталоге (данные в БД остаются).
# Причина: платформа для экономистов/инвесторов; аборты и мертворождения
# в общем каталоге экономики выглядят неуместно и создают репутационный риск.
# ---------------------------------------------------------------------------

SENSITIVE_TOPIC_DATASET_IDS: frozenset[str] = frozenset({
    "demo_fabort",
    "demo_fabortind",
    "demo_fabortord",
    "demo_mfoet",
})

# Метки кодлиста, которые сами по себе НЕ дают единицу для витрины.
_VAGUE_EN_LABELS: frozenset[str] = frozenset({
    "rate",
    "number",
    "average",
    "person",
    "persons",
    "index",
    "ratio",
    "score",
    "total",
    "value",
    "unit",
})

# Curated: dataset_id → русская единица (когда кодлист говорит только Rate/Number
# или unit-измерения нет, а смысл ряда зафиксирован методологией Евростата).
DATASET_UNIT_RU: dict[str, str] = {
    # Младенческая смертность — всегда на 1000 живорождённых
    "demo_minfind": "на 1000 живорождённых",
    "demo_r_minfind": "на 1000 живорождённых",
    "tps00027": "на 1000 живорождённых",
    # Возрастные коэффициенты рождаемости — на 1000 женщин данного возраста
    "demo_frate": "на 1000 женщин соответствующего возраста",
    "demo_r_frate2": "на 1000 женщин соответствующего возраста",
    # Суммарный коэффициент рождаемости
    "tps00199": "детей на женщину",
    # Общие коэффициенты (crude rates) — на 1000 человек среднегодового населения
    "tps00206": "на 1000 человек населения",
    "tps00019": "на 1000 человек населения",
    "tps00204": "человек",  # ряд смешанный; headline обычно число родившихся
    "tps00029": "человек",
    # Счётчики событий / численности (код NR = Number, но ряд — headcount)
    "demo_pjan": "человек",
    "demo_pjanbroad": "человек",
    "demo_pjangroup": "человек",
    "demo_pjanedu": "человек",
    "demo_pjanmarsta": "человек",
    "demo_urespop": "человек",
    "demo_fmonth": "человек",
    "demo_mmonth": "человек",
    "demo_fagec": "человек",
    "demo_fager": "человек",
    "demo_fasec": "человек",
    "demo_fordagec": "человек",
    "demo_facbc": "человек",
    "demo_faczc": "человек",
    "demo_faeduc": "человек",
    "demo_magec": "человек",
    "demo_mager": "человек",
    "demo_macbc": "человек",
    "demo_maczc": "человек",
    "demo_maeduc": "человек",
    "demo_marstac": "человек",
    "demo_minf": "человек",
    "demo_minfs": "человек",
    "demo_r_minf": "человек",
    "demo_r_births": "человек",
    "demo_r_deaths": "человек",
    "demo_nmsta": "человек",
    "demo_nmsta2": "человек",
    "demo_ndivdur": "человек",
    "demo_nsinagec": "человек",
    "demo_marcb": "человек",
    "demo_marcz": "человек",
    "demo_divcb": "человек",
    "demo_divcz": "человек",
    "demo_fweight": "человек",
    "demo_pjanind": "%",  # коэффициенты нагрузки / доли — уточняется indic; fallback %
    "demo_r_pjanind2": "%",
    "demo_r_pjanind3": "%",
    "tps00198": "%",  # old-age dependency
    "tps00028": "% населения",
    "demo_ndivind": "на 1000 человек населения",
    "demo_nind": "лет",  # headline — средний возраст; иначе indic
    "demo_nsinrt": "на 1000 человек соответствующего возраста",
    "demo_mlifetable": "вероятность / лет",
    "demo_r_mlife": "вероятность / лет",
    "demo_gind": "человек",  # headline AVG population; rates via indic
    # Избыточная смертность — проценты к базовому уровню
    "demo_mexrt": "% к ожидаемому уровню",
    # Плотность
    "demo_r_d3dens": "чел. на км²",
    # Коррупция
    "sdg_16_50": "балл индекса",
    # Образование (NR = enrolled persons)
    "educ_uoe_enra01": "человек",
    "educ_uoe_enra02": "человек",
    "educ_uoe_enrp01": "человек",
    "educ_uoe_enrp02": "человек",
    "educ_uoe_enrp04": "человек",
    "educ_uoe_enrp05": "человек",
    "educ_uoe_enrs01": "человек",
    "educ_uoe_enrs04": "человек",
    "educ_uoe_enrt01": "человек",
    "educ_uoe_enrt02": "человек",
    "educ_uoe_ent01": "человек",
    "hlth_rs_phys": "человек",
    "hlth_rs_bds1": "койко-мест",
    # ВВП на душу по ППС (unit-код PC в этом наборе = уровень PPS, не процент)
    "sdg_10_10": "ППС на душу населения",
    # Денежный рынок / депозитные ставки (unit часто отсутствует или RT)
    "ei_mfir_m": "%",
    "irt_st_m": "%",
    "irt_lt_mcby_m": "%",
    "irt_lt_mcby_q": "%",
    "irt_lt_mcby_a": "%",
    # ВВП относительно среднего по ЕС (не «голый %»)
    "nama_10_pc": "% от среднего по ЕС на душу населения",
    # Рынок труда / вакансии (unit часто пуст, indic=JVR)
    "ei_lmjv_q_r2": "%",
    "ei_lmjv_m_r2": "%",
    # Распределение доходов
    "ilc_di11": "раз",
    "ilc_di12": "пунктов индекса Джини",
    # Бизнес-опросы (INX = индекс настроений, не «голый Index»)
    "ei_bsee_m_r2": "индекс",
    "ei_bslh_m_r2": "индекс",
    "ei_bsin_q_r2": "индекс",
    "ei_bsbu_m_r2": "индекс",
    "ei_bssi_m_r2": "индекс",
    "teibs030": "индекс",
    # Образование: ожидаемая продолжительность обучения
    "educ_uoe_enra07": "лет",
    # Демография / здравоохранение / транспорт (NR = headcount)
    "demo_fordager": "человек",
    "hlth_rs_grd2": "человек",
    "hlth_rs_prs2": "человек",
    "prc_hpi_hsnq": "сделок",
    # Веса HPI/OOHPI: Eurostat unit PM = per mille share of total (не «смертность»)
    "prc_hpi_cow": "‰ от суммарных весов стран ЕС",
    "prc_hpi_inw": "‰ от суммарных весов категорий",
    "prc_hpi_oocow": "‰ от суммарных весов стран ЕС",
    "prc_hpi_ooinw": "‰ от суммарных весов категорий",
    "nrg_chdd_m": "градусо-сутки",
    "nrg_chdd_a": "градусо-сутки",
    "nrg_chddr2_m": "градусо-сутки",
    "nrg_chddr2_a": "градусо-сутки",
    "nrg_stk_oem": "дней запаса",
    "road_eqs_busage": "штук",
    "road_eqs_busveh": "штук",
    "road_eqs_carage": "автомобилей",
    "road_eqs_carmot": "автомобилей",
    "road_eqs_carpda": "автомобилей",
    "road_eqs_unlweig": "автомобилей",
    "road_eqr_carmot": "автомобилей",
    "road_eqr_unlweig": "автомобилей",
    # LFS/LFSI: код THS = тысяч человек (не «тыс. единиц»)
    "lfsi_abt_q": "тысяч человек",
    "lfsi_lea_q": "тысяч человек",
    "lfsi_sta_q": "тысяч человек",
    "lfsi_long_q": "тысяч человек",
    # Отработанные часы (код HR)
    "lfsq_ewhais": "часов в неделю",
    "lfsq_ewhan2": "часов в неделю",
    "lfsq_ewhuis": "часов в неделю",
    "lfsq_ewhun2": "часов в неделю",
    "lfsq_ewh2n2": "часов в неделю",
    # Сырая нефть: объём в срезе indic_nrg=VOL_THS_BBL
    "nrg_cb_cosm": "тыс. баррелей",
    # Платёжный баланс / headline-таблицы (валюта в срезе, unit пуст)
    "teibp010": "млн евро",
    "teibp040": "млн евро",
    "teibp041": "млн евро",
    "teibp050": "млн евро",
    "teibp110": "млн евро",
}

# indic_* коды в срезе (когда unit-dim отсутствует или полисемичен).
INDIC_UNIT_RU: dict[str, str] = {
    "INFMORRT": "на 1000 живорождённых",
    "NEOMORRT": "на 1000 живорождённых",
    "ENEOMORRT": "на 1000 живорождённых",
    "PERIMORRT": "на 1000 живорождённых",
    "LFOEMORRT": "на 1000 живорождённых",
    "TOTFERRT": "детей на женщину",
    "GNUPRT": "на 1000 человек населения",
    "GBIRTHRT": "на 1000 человек населения",
    "GDEATHRT": "на 1000 человек населения",
    "GROWRT": "на 1000 человек населения",
    "NATGROWRT": "на 1000 человек населения",
    "CNMIGRATRT": "на 1000 человек населения",
    "AGEMOTH": "лет",
    "AGEMOTH1": "лет",
    "AGEMOTH2": "лет",
    "AGEMOTH3": "лет",
    "AGEMOTH4_MAX": "лет",
    "MEDAGEMOTH": "лет",
    "FAGEMAR1": "лет",
    "MAGEMAR1": "лет",
    "LBIRTHR1PC": "%",
    "LBIRTHR2PC": "%",
    "LBIRTHR3PC": "%",
    "LBIRTHR4_MAXPC": "%",
    "NMARPCT": "%",
    "FMAR1PC": "%",
    "MMAR1PC": "%",
    "FMAR1CUM": "на одну женщину",
    "MMAR1CUM": "на одного мужчину",
    "POPSHARE": "% населения ЕС",
    "POPSHARE_EU27_2020": "% населения ЕС",
    "JAN": "человек",
    "FJAN": "человек",
    "MJAN": "человек",
    "AVG": "человек",
    "FAVG": "человек",
    "MAVG": "человек",
    "LBIRTH": "человек",
    "FLBIRTH": "человек",
    "MLBIRTH": "человек",
    "DEATH": "человек",
    "FDEATH": "человек",
    "MDEATH": "человек",
    "GROW": "человек",
    "NATGROW": "человек",
    "CNMIGRAT": "человек",
    "MARRIAGE": "человек",
    "DEPRATIO1": "%",
    "DEPRATIO2": "%",
    "DEPRATIO3": "%",
    "DEPRATIO4": "%",
    "OLDDEP1": "%",
    "OLDDEP2": "%",
    "OLDDEP3": "%",
    "OLDDEP4": "%",
    "YOUNGDEP1": "%",
    "YOUNGDEP2": "%",
    "YOUNGDEP3": "%",
    "YOUNGDEP4": "%",
    "MEDAGEPOP": "лет",
    "FMEDAGEPOP": "лет",
    "MMEDAGEPOP": "лет",
    "PC_Y65_MAX": "% населения",
    "PC_FM": "женщин на 100 мужчин",
    # Денежные ставки (не демографические *RT)
    "MF-DDI-RT": "%",
    "MF-LTGBY-RT": "%",
    "MF-NBRATE-RT": "%",
    # Вакансии / бизнес-опросы
    "JVR": "%",
    "BS-EEI-I": "индекс",
    "BS-ESI-I": "индекс",
    "BS-ICI-I": "индекс",
    "BS-CCI-I": "индекс",
    "BS-RCI-I": "индекс",
    "BS-CSMCI-I": "индекс",
    "GINI_HND": "пунктов индекса Джини",
    "MF-LON-RT": "%",
    # PPS per capita (не Percentage, несмотря на соседний unit=PC)
    "EXP_PPS_EU27_2020_HAB": "ППС на душу населения",
    "EXP_PPS_HAB": "ППС на душу населения",
    "PPS_EU27_2020_HAB": "ППС на душу населения",
    "PPS_HAB": "ППС на душу населения",
}


def _t_en(en: str) -> str | None:
    """Перевод однозначной англ. метки кодлиста. None = метка слишком общая."""
    s = re.sub(r"\s+", " ", (en or "").strip())
    if not s:
        return None
    low = s.lower()
    if low in _VAGUE_EN_LABELS:
        return None

    exact = {
        "percentage": "%",
        "percentage of total population": "% населения",
        "percentage of population in the labour force": "% экономически активного населения",
        "percentage of total employment": "% занятости",
        "percentage of gdp": "% ВВП",
        "percentage of gross domestic product (gdp)": "% ВВП",
        "percentage of total": "% от итога",
        "index, 2015=100": "индекс (2015 = 100)",
        "index, 2010=100": "индекс (2010 = 100)",
        "index, 2005=100": "индекс (2005 = 100)",
        "index, 2021=100": "индекс (2021 = 100)",
        "index, 2025=100": "индекс (2025 = 100)",
        "index, 2021=100 (sca)": "индекс (2021 = 100), с сезонной корректировкой",
        "index, 2025=100 (nsa)": "индекс (2025 = 100)",
        "quarterly index, 2015=100": "индекс (2015 = 100)",
        "annual average index, 2015=100": "индекс (2015 = 100), среднегодовой",
        "annual average index": "индекс, среднегодовой",
        "quarterly index": "индекс, квартальный",
        "million euro": "млн евро",
        "million euro (sca)": "млн евро, с сезонной корректировкой",
        "thousand euro": "тыс. евро",
        "euro": "евро",
        "current prices, million euro": "в текущих ценах, млн евро",
        "current prices, euro per capita": "на душу населения, евро",
        "million euro at constant prices": "млн евро, в постоянных ценах",
        "chain linked volumes (2015), million euro": "в постоянных ценах 2015 года, млн евро",
        "chain linked volumes (2010), million euro": "в постоянных ценах 2010 года, млн евро",
        "chain linked volumes (2020), euro per capita": "в постоянных ценах 2020 года, евро на душу населения",
        "euro per capita": "на душу населения, евро",
        "thousand persons": "тысяч человек",
        "thousand": "тыс. единиц",
        "million persons": "млн человек",
        "persons per square kilometre": "чел. на км²",
        "per thousand live birth": "на 1000 живорождённых",
        "per thousand inhabitants": "на 1000 жителей",
        "per mille": "промилле",
        "number per inhabitant": "на одного жителя",
        "number per hundred thousand persons": "на 100 000 человек",
        "number of enterprises": "число предприятий",
        "gigawatt-hour": "ГВт·ч",
        "megawatt": "МВт",
        "terajoule": "ТДж",
        "thousand tonnes": "тыс. тонн",
        "thousand tonnes of oil equivalent": "тыс. т н. э.",
        "kilogram of oil equivalent (kgoe)": "кг н. э.",
        "euro per kilogram of oil equivalent (kgoe)": "евро за кг н. э.",
        "million cubic metres": "млн м³",
        "kilometre": "км",
        "thousand square metres": "тыс. м²",
        "thousand tonnes per year": "тыс. тонн в год",
        "percentage change on previous period": "изменение к предыдущему периоду",
        "percentage change compared to same period in previous year": "изменение к тому же периоду прошлого года",
        "percentage change (t/t-1) - seasonally and calendar adjusted data": (
            "темп изменения, с сезонной корректировкой"
        ),
        "growth rate on previous period (t/t-1)": "темп изменения к предыдущему периоду",
        "annual rate of change": "изменение за год",
        "monthly rate of change": "изменение за месяц",
        "moving 12 months average rate of change": "среднее изменение за 12 месяцев",
        "monthly rate differences between hicp and hicp at constant taxes": (
            "изменение за месяц, п.п."
        ),
        "trade value - million of euro - seasonally and working day adjusted": (
            "млн евро, с сезонной корректировкой"
        ),
        "balance": "сальдо",
        "year": "лет",
        "percentage point": "п.п.",
    }
    if low in exact:
        return exact[low]

    if low.startswith("percentage of "):
        return "%"
    if low.startswith("percentage change"):
        return "изменение, %"
    m = re.match(r"^index,\s*(\d{4})=100(?:\s*\(([^)]+)\))?$", low)
    if m:
        y, flag = m.group(1), (m.group(2) or "").upper()
        base = f"индекс ({y} = 100)"
        if flag == "SCA":
            return f"{base}, с сезонной корректировкой"
        return base
    if re.match(r"^(annual average |quarterly )?index,\s*\d{4}=100", low):
        y = re.search(r"(\d{4})=100", low).group(1)
        return f"индекс ({y} = 100)"
    if "chain linked volumes" in low and "2015" in low and "million euro" in low:
        return "в постоянных ценах 2015 года, млн евро"
    if "chain linked volumes" in low and "2010" in low and "million euro" in low:
        return "в постоянных ценах 2010 года, млн евро"
    if low.startswith("growth rate"):
        return "темп изменения"
    if "million euro" in low and "season" in low:
        return "млн евро, с сезонной корректировкой"
    if low.startswith("current prices") and "million euro" in low:
        return "в текущих ценах, млн евро"
    if low.startswith("current prices") and "per capita" in low:
        return "на душу населения, евро"
    return None


@lru_cache(maxsize=1)
def _unit_codelist_en() -> dict[str, str]:
    """Глобальный SDMX UNIT: code → english label. Файл — снимок для офлайна."""
    path = Path(__file__).with_name("eurostat_unit_codelist_en.json")
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def unit_label_en_for_code(unit_code: str | None) -> str:
    if not unit_code:
        return ""
    return _unit_codelist_en().get(unit_code.strip().upper(), "") or _unit_codelist_en().get(
        unit_code.strip(), ""
    )


def is_sensitive_topic(dataset_id: str) -> bool:
    return (dataset_id or "").lower() in SENSITIVE_TOPIC_DATASET_IDS


def resolve_public_unit(
    *,
    dataset_id: str,
    unit_code: str | None = None,
    unit_label_en: str | None = None,
    slice_json: dict | None = None,
) -> tuple[str | None, str]:
    """Вернуть (unit_ru, provenance). unit_ru is None → не листинговать.

    provenance: curated-dataset | curated-indic | label-en | refused-vague | missing
    """
    ds = (dataset_id or "").lower()
    if is_sensitive_topic(ds):
        return None, "sensitive-topic"

    code = (unit_code or "").strip()
    slice_json = slice_json or {}

    # 1) indic в срезе — точнее, чем общий override набора
    for dim in (
        "indic_de", "indic", "indic_n", "indic_sb", "indic_bt", "indic_ppp", "na_item",
        "statinfo",
    ):
        ic = (slice_json.get(dim) or "").strip().upper()
        if not ic:
            continue
        if ic in INDIC_UNIT_RU:
            return INDIC_UNIT_RU[ic], "curated-indic"
        if ic == "PC_FM":
            return "женщин на 100 мужчин", "curated-indic"
        if ic.startswith("PC_Y") or ic.startswith("PC_"):
            return "% населения", "curated-indic"
        if ic.startswith(("DEPRATIO", "OLDDEP", "YOUNGDEP")):
            return "%", "curated-indic"
        if "AGE" in ic and ic.endswith(("MOTH", "POP", "MAR1")):
            return "лет", "curated-indic"
        if ic.startswith("MF-") and ic.endswith("RT"):
            return "%", "curated-indic"
        if "PPS" in ic and ("HAB" in ic or "EU27" in ic):
            return "ППС на душу населения", "curated-indic"
        if ic.endswith("RT") and ic not in {"RT"}:
            # демографические *RT без явного словаря — crude/infant rates
            if "MOR" in ic or "INF" in ic or "FOE" in ic or "NEO" in ic or "PERI" in ic:
                return "на 1000 живорождённых", "curated-indic"
            if "FERRT" in ic or ic == "TOTFERRT":
                return "детей на женщину", "curated-indic"
            return "на 1000 человек населения", "curated-indic"

    # 2) curated на набор (когда unit полисемичен или отсутствует)
    if ds in DATASET_UNIT_RU:
        return DATASET_UNIT_RU[ds], "curated-dataset"

    # 2b) валюта / единица, лежащая в срезе (типично teibp*/bop_* без unit-dim)
    for cur_key in ("currency", "unit", "curr"):
        cur = (slice_json.get(cur_key) or "").strip().upper()
        if not cur or cur == code.upper():
            continue
        cur_en = unit_label_en_for_code(cur)
        if cur_en:
            ru = _t_en(cur_en)
            if ru:
                return ru, "label-en-slice"
        # частые SDMX-коды денег без отдельной метки
        if cur in {"MIO_EUR", "MIO-EUR", "MEUR"}:
            return "млн евро", "curated-slice-currency"
        if cur in {"MIO_NAC", "MIO-NAC"}:
            return "млн национальной валюты", "curated-slice-currency"

    # 3) англ. метка из ответа / кодлиста
    en = (unit_label_en or "").strip() or unit_label_en_for_code(code)
    if en:
        ru = _t_en(en)
        if ru:
            return ru, "label-en"
        if en.lower().strip() in _VAGUE_EN_LABELS:
            return None, f"refused-vague:{en}"

    if not code and not en:
        return None, "missing"

    # 4) голый код без однозначной метки — не угадываем
    return None, f"refused-code:{code or '?'}"


def unit_is_listable(unit_ru: str | None) -> bool:
    return bool(unit_ru and unit_ru.strip())


# ---------------------------------------------------------------------------
# Приписывание единицы к числу.
#
# `unit_ru` описывает измерение полностью и годится для оси графика и строки
# «Единицы измерения». Но приклеивать его к значению дословно нельзя: получается
# «-14,4 индекс», «7,3 балл индекса», «180 изменение за год». Часть значений
# unit_ru — не единицы, а характеристика самого показателя; после числа они
# читаются как безграмотный русский. `unit_suffix()` возвращает только то, что
# корректно стоит справа от числа, и пустую строку для безразмерных величин.
# ---------------------------------------------------------------------------

# Сегменты, не читающиеся после числа: описание показателя, а не его единица.
_NON_APPENDABLE_PREFIXES: tuple[str, ...] = (
    "индекс",
    "балл индекса",
    "изменение",
    "темп изменения",
    "среднее изменение",
    "сальдо",
    "вероятность",
    "раз",
    "в постоянных ценах",
    "в текущих ценах",
    "с сезонной",
    "среднегодов",
    "на душу населения",
)


def _is_appendable_segment(segment: str) -> bool:
    low = segment.strip().lower()
    if not low:
        return False
    return not low.startswith(_NON_APPENDABLE_PREFIXES)


@lru_cache(maxsize=512)
def unit_suffix(unit_ru: str | None) -> str:
    """Часть единицы, которую можно поставить справа от числа («» — нельзя).

    Составные единицы разбираются по запятым: у «в постоянных ценах 2015 года,
    млн евро» приписывается «млн евро», у «изменение за месяц, п.п.» — «п.п.»,
    у «индекс (2015 = 100), среднегодовой» — ничего.
    """
    raw = (unit_ru or "").strip()
    if not raw:
        return ""
    for segment in raw.split(","):
        if _is_appendable_segment(segment):
            return segment.strip()
    return ""

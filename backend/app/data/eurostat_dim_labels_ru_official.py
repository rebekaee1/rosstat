"""Русские подписи значений срезов, переведённые с официальных английских подписей Евростата (14.11.2026).

Евростат не публикует кодлисты на русском. Для значений, которых нет в `eurostat_dim_labels_ru`,
здесь хранится пара «официальная английская подпись (снимок `eurostat_codelists_en.json`) → русский
перевод термина». Тест `test_world_series_title.py` сверяет английскую половину с официальным
снимком: подпись не может разойтись с источником молча. Отрасли — названиями разделов ОКВЭД 2
(гармонизирован с NACE Rev. 2), энергоносители — терминами энергобаланса, занятость — терминами
выборочного обследования рабочей силы. Отбор — самые массовые значения в одинаковых названиях
(замер `scripts/world-title-duplicates.py` 14.11.2026).
"""
from __future__ import annotations

# измерение → код → (официальная английская подпись, русский перевод)
RU_FROM_OFFICIAL_EN: dict[str, dict[str, tuple[str, str]]] = {
    "stk_flow": {
        "STKOP_NAT": ("Opening stock - national territory", "запасы на начало периода, национальная территория"),
        "STK_OP": ("Opening stock", "запасы на начало периода"),
        "STKCL_NAT": ("Closing stock - national territory", "запасы на конец периода, национальная территория"),
        "IMP": ("Imports", "импорт"),
        "EXP": ("Exports", "экспорт"),
    },
    "hhcomp": {
        "A1_LT65": ("One adult younger than 65 years", "один взрослый младше 65 лет"),
    },
    "wstatus": {
        "POP": ("Population", "всё население"),
        "INAC_OTH": ("Other persons outside the labour force", "прочие лица вне рабочей силы"),
        "SELF_NS": ("Self-employed persons without employees (own-account workers)",
                    "самозанятые без наёмных работников"),
        "SELF_S": ("Self-employed persons with employees (employers)", "работодатели"),
        "UEMP_PT": ("Underemployed persons working part-time", "частично занятые, готовые работать больше"),
        "RET": ("Retired persons", "пенсионеры"),
        "NCFAM": ("Employed persons except contributing family workers",
                  "занятые, кроме помогающих членов семьи"),
        "NSEEK_AVL": ("Persons available to work but not seeking", "готовы работать, но не ищут работу"),
        "SEEK_NAVL": ("Persons seeking work but not immediately available",
                      "ищут работу, но не готовы приступить сразу"),
        "EMP_PT": ("Employed persons working part-time", "занятые неполное рабочее время"),
        "ACT": ("Persons in the labour force", "рабочая сила"),
        "SLACK": ("Labour market slack", "неиспользованная рабочая сила"),
        "EMP_TEMP": ("Employed persons with temporary contract", "занятые по временному договору"),
        "SAL_PERM": ("Employees with a permanent job", "наёмные работники с постоянной работой"),
        "SAL_TEMP": ("Employees with a temporary job", "наёмные работники с временной работой"),
    },
    "isced11": {
        "ED35_45": ("Upper secondary and post-secondary non-tertiary education - vocational (levels 35 and 45)",
                    "среднее профессиональное образование"),
        "ED34_44": ("Upper secondary and post-secondary non-tertiary education - general (levels 34 and 44)",
                    "среднее общее образование"),
    },
    "na_item": {
        "EMP_DC": ("Total employment domestic concept", "все занятые на территории страны"),
        "SAL_DC": ("Employees domestic concept", "наёмные работники на территории страны"),
        "SELF_DC": ("Self-employed domestic concept", "самозанятые на территории страны"),
    },
    "duration": {
        "N_GE1": ("1 night or over", "от 1 ночи"),
        "N_GE4": ("4 nights or over", "от 4 ночей"),
        "N1-3": ("From 1 to 3 nights", "1–3 ночи"),
        "H0": ("Zero hours", "0 часов"),
        "H1-24": ("From 1 to 24 hours", "1–24 часа"),
    },
    "nace_r2": {
        "G-I": ("Wholesale and retail trade, transport, accommodation and food service activities",
                "торговля, транспорт, гостиницы и общепит"),
        "M_N": ("Professional, scientific and technical activities; administrative and support service activities",
                "профессиональная, научная, техническая и административная деятельность"),
        "O-Q": ("Public administration, defence, education, human health and social work activities",
                "госуправление, оборона, образование, здравоохранение и соцуслуги"),
        "R-U": ("Arts, entertainment and recreation; other service activities; activities of household and "
                "extra-territorial organizations and bodies", "культура, спорт, отдых и прочие услуги"),
        "O-U": ("Public administration and defence; compulsory social security; education; human health and social "
                "work activities; arts, entertainment and recreation, repair of household goods and other services",
                "госуправление, образование, здравоохранение, культура и прочие услуги"),
        "F_CC1": ("Buildings", "здания"),
        "F_CC2": ("Civil engineering works", "сооружения"),
    },
    "siec": {
        "O4600": ("Oil products", "нефтепродукты"),
        "O4620": ("Ethane", "этан"),
        "O4653": ("Gasoline-type jet fuel", "реактивное топливо бензинового типа"),
        "O4671XR5220B": ("Gas oil and diesel oil (excluding biofuel portion)", "дизельное топливо (без биотоплива)"),
        "R5220B": ("Blended biodiesels", "смесевое биодизельное топливо"),
        "R5230B": ("Blended bio jet kerosene", "смесевое реактивное биотопливо"),
        "R5210P": ("Pure biogasoline", "чистый биобензин"),
        "R5220P": ("Pure biodiesels", "чистое биодизельное топливо"),
        "R5290": ("Other liquid biofuels", "прочее жидкое биотопливо"),
        "O4695": ("Bitumen", "битум"),
        "O4300": ("Refinery feedstocks", "сырьё для нефтепереработки"),
        "O4400": ("Additives and oxygenates", "присадки и оксигенаты"),
        "O4500": ("Other hydrocarbons", "прочие углеводороды"),
        "RA300": ("Wind", "энергия ветра"),
        "O4600XBIO": ("Oil products (excluding biofuel portion)", "нефтепродукты (без биотоплива)"),
        "O4691": ("White spirit and special boiling point industrial spirits", "уайт-спирит и бензины-растворители"),
        "O4692": ("Lubricants", "смазочные масла"),
        "O4693": ("Paraffin waxes", "парафин"),
        "O4699": ("Other oil products n.e.c.", "прочие нефтепродукты"),
        "C0320": ("Patent fuel", "угольные брикеты"),
        "C0330": ("Brown coal briquettes", "брикеты бурого угля"),
        "C0340": ("Coal tar", "каменноугольная смола"),
        "P1200": ("Peat products", "торфяная продукция"),
        "RA100": ("Hydro", "гидроэнергия"),
        "RA130": ("Pumped hydro power", "гидроаккумулирующие станции"),
        "RA200": ("Geothermal", "геотермальная энергия"),
        "RA500": ("Tide, wave, ocean", "энергия приливов, волн и океана"),
        "X9900": ("Other fuels n.e.c.", "прочие виды топлива"),
        "O4610": ("Refinery gas", "нефтезаводской газ"),
        "RA110": ("Pure hydro power", "гидроэнергия без гидроаккумуляции"),
        "RA120": ("Mixed hydro power", "смешанные гидростанции"),
        "RA410": ("Solar thermal", "солнечная тепловая энергия"),
        "RA420": ("Solar photovoltaic", "солнечная фотоэлектрическая энергия"),
        "RA400": ("Solar", "солнечная энергия"),
        "RA310": ("Wind on shore", "наземная ветроэнергетика"),
        "RA320": ("Wind off shore", "морская ветроэнергетика"),
        "N9000": ("Nuclear fuels and other fuels n.e.c.", "ядерное и прочее топливо"),
        "O4410": ("Biofuels for blending", "биотопливо для смешения"),
    },
    "indic_nrg": {
        "HDD": ("Heating degree days", "градусо-сутки отопительного периода"),
        "CDD": ("Cooling degree days", "градусо-сутки охлаждения"),
    },
    "statinfo": {
        "VAL_A": ("Annual value", "годовое значение"),
    },
    "indic_is": {
        "I_IU3": ("Last internet use: in last 3 months", "пользовались интернетом за последние 3 месяца"),
        "I_ILT12": ("Last internet use: in the last 12 months", "пользовались интернетом за последние 12 месяцев"),
        "I_IUX": ("Internet use: never", "никогда не пользовались интернетом"),
    },
}


# Дополнение 14.11.2026: значения с показами в Search Console (по убыванию показов), тот же формат.
RU_FROM_OFFICIAL_EN_GSC: dict[str, dict[str, tuple[str, str]]] = {
    "indic": {
        "LM-UN-M-TOT": ("Unemployment according to ILO definition - males", "по методологии МОТ: мужчины"),
        "LM-UN-F-TOT": ("Unemployment according to ILO definition - females", "по методологии МОТ: женщины"),
        "LM-UN-T-LE25": ("Unemployment according to ILO definition - under 25 years - total", "по методологии МОТ: моложе 25 лет, всего"),
        "LM-UN-M-LE25": ("Unemployment according to ILO definition - under 25 years - males", "по методологии МОТ: моложе 25 лет, мужчины"),
        "LM-UN-F-LE25": ("Unemployment according to ILO definition - under 25 years - females", "по методологии МОТ: моложе 25 лет, женщины"),
        "LM-UN-T-GT25": ("Unemployment according to ILO definition - over 25 years - total", "по методологии МОТ: старше 25 лет, всего"),
        "LM-UN-M-GT25": ("Unemployment according to ILO definition - over 25 years - males", "по методологии МОТ: старше 25 лет, мужчины"),
        "LM-UN-F-GT25": ("Unemployment according to ILO definition - over 25 years - females", "по методологии МОТ: старше 25 лет, женщины"),
    },
    "na_item": {
        "P5G": ("Gross capital formation", "валовое накопление"),
        "D21X31": ("Taxes less subsidies on products", "налоги на продукты за вычетом субсидий"),
        "D31": ("Subsidies on products", "субсидии на продукты"),
        "P3_P5": ("Final consumption expenditure and gross capital formation", "конечное потребление и валовое накопление"),
        "P3_P6": ("Final consumption expenditure, gross capital formation and exports of goods and services", "конечное потребление, валовое накопление и экспорт"),
        "POP_NC": ("Total population national concept", "всё население, национальная концепция"),
        "EMP_NC": ("Total employment national concept", "все занятые, национальная концепция"),
        "IGL_F4_EA21": ("Intergovernmental lending within EA21 (from 2026)", "межгосударственные кредиты внутри еврозоны-21 (с 2026)"),
        "IGL_F4_EA20": ("Intergovernmental lending within EA20 (2023-2025)", "межгосударственные кредиты внутри еврозоны-20 (2023–2025)"),
        "IGL_F4_EA19": ("Intergovernmental lending within EA19 (2015-2022)", "межгосударственные кредиты внутри еврозоны-19 (2015–2022)"),
        "IGL_F4_EU27_2020": ("Intergovernmental lending within EU27 (from 2020)", "межгосударственные кредиты внутри ЕС-27 (с 2020)"),
        "GD_F2": ("Government consolidated gross debt at face value - currency and deposits", "госдолг по номиналу: наличные деньги и депозиты"),
        "GD_F3": ("Government consolidated gross debt at face value - debt securities", "госдолг по номиналу: долговые ценные бумаги"),
        "GD_F31": ("Government consolidated gross debt at face value - short-term debt securities", "госдолг по номиналу: краткосрочные долговые ценные бумаги"),
        "GD_F32": ("Government consolidated gross debt at face value - long-term debt securities", "госдолг по номиналу: долгосрочные долговые ценные бумаги"),
        "GD_F4": ("Government consolidated gross debt at face value - loans", "госдолг по номиналу: кредиты"),
        "GD_F41": ("Government consolidated gross debt at face value - short-term loans", "госдолг по номиналу: краткосрочные кредиты"),
        "GD_F42": ("Government consolidated gross debt at face value - long-term loans", "госдолг по номиналу: долгосрочные кредиты"),
        "AF_81L": ("Trade credits and advances - liabilities", "торговые кредиты и авансы, обязательства"),
        "EXP_PPS_EU27_2020": ("Real expenditure (in PPS_EU27_2020)", "реальные расходы в ППС ЕС-27 (2020)"),
        "EXP_PPS_EU27_2007": ("Real expenditure (in PPS_EU27_2007)", "реальные расходы в ППС ЕС-27 (2007)"),
        "EXP_PPS_EU27_2020_HAB": ("Real expenditure per capita (in PPS_EU27_2020)", "реальные расходы на душу в ППС ЕС-27 (2020)"),
        "EXP_PPS_EU28_HAB": ("Real expenditure per capita (in PPS_EU28)", "реальные расходы на душу в ППС ЕС-28"),
        "EXP_PPS_EU27_2007_HAB": ("Real expenditure per capita (in PPS_EU27_2007)", "реальные расходы на душу в ППС ЕС-27 (2007)"),
    },
    "ord_brth": {
        "1": ("First", "первый ребёнок"),
        "2": ("Second", "второй ребёнок"),
        "3": ("Third", "третий ребёнок"),
        "GE4": ("Fourth and following", "четвёртый и последующие"),
        "UNK": ("Unknown", "очерёдность не указана"),
    },
    "indic_de": {
        "NUMBERDYING": ("Number dying between exact ages (dx)", "число умирающих между точными возрастами"),
        "SURVIVORS": ("Number left alive at given exact age (lx)", "число доживающих до точного возраста"),
    },
    "c_birth": {
        "NRP": ("No response", "нет ответа"),
    },
}
for _dim, _members in RU_FROM_OFFICIAL_EN_GSC.items():
    RU_FROM_OFFICIAL_EN.setdefault(_dim, {}).update(_members)


def official_translation_ru(dim: str, code: str) -> str | None:
    """Русский перевод официальной подписи значения или None."""
    pair = RU_FROM_OFFICIAL_EN.get(dim, {}).get(code)
    return pair[1] if pair else None

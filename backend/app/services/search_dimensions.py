"""Exact Eurostat slice evidence for explicit demographic and category facets.

No destination, dataset or visitor-query lookup. Shared rules require the named
axis and an actual stored member, before SQL LIMIT and again in DTO metadata.
Labels come from existing public dictionaries or verified official codelists.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from functools import lru_cache

from sqlalchemy import and_, case, false, func, literal, or_
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.functions import FunctionElement
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.types import Boolean

from app.data.eurostat_dim_labels_en import AGE_EN, LABELS_BY_DIM as LABELS_EN, label_for_dim_member as label_en
from app.data.eurostat_dim_labels_ru import AGE_RU, LABELS_BY_DIM as LABELS_RU, label_for_dim_member as label_ru

# Supplements are member labels, shared across Eurostat datasets. Official JSON
# evidence (URL, update and response hash) is retained beside the private module.
_SUPPLEMENTAL_LABELS = {
    "sex": {"T": ("both sexes", "оба пола"), "TOTAL": ("both sexes", "оба пола")},
    "citizen": {"TOTAL": ("all citizenships", "все гражданства")},
    "partner": {"TOTAL": ("all partner countries", "все страны партнеры"),
        "WORLD": ("all countries of the world", "all partner countries", "все страны партнеры")},
    "hhcomp": {"TOTAL": ("all household types", "все типы домохозяйств")},
    "quant_inc": {"TOTAL": ("all income quintiles", "все квинтили доходов"),
        "QU1": ("first income quintile", "первый квинтиль доходов"),
        "QU2": ("second income quintile", "второй квинтиль доходов"),
        "QU3": ("third income quintile", "третий квинтиль доходов"),
        "QU4": ("fourth income quintile", "четвертый квинтиль доходов"),
        "QU5": ("fifth income quintile", "пятый квинтиль доходов")},
    "rskpovth": {"TOTAL": ("all income threshold groups", "все группы по порогу доходов")},
    "nace_r2": {"TOTAL": ("all economic activities", "all NACE activities", "все виды экономической деятельности")},
    "nace_r1": {"TOTAL": ("all economic activities", "all NACE activities", "все виды экономической деятельности")},
    "isced11": {"ED0-2": ("below upper secondary education", "less than primary primary and lower secondary education", "ниже среднего образования")},
    "wstatus": {"EMP": ("employed persons", "занятые"), "PRACT": ("practising", "практикующие"),
        "PACT": ("professionally active", "профессионально активные"), "LIC": ("licensed to practice", "имеющие лицензию на практику")},
    "med_spec": {"PHYS": ("physicians", "врачи"), "MWS": ("midwives", "акушерки"),
        "NRS": ("nurses", "медсестры"), "DENT": ("dentists", "стоматологи"),
        "PHARM": ("pharmacists", "фармацевты"), "PER_CARE": ("caring personnel", "персонал по уходу"),
        "PHYSIO": ("physiotherapists", "физиотерапевты")},
    "indic_is": {"I_IDAY": ("daily internet use", "frequency of internet access daily", "ежедневное использование интернета")},
    "ind_type": {"IND_TOTAL": ("all individuals", "all persons", "все люди")},
    "stk_flow": {"STKOP_NAT": ("opening stock national territory", "opening stock", "начальные запасы на территории страны"),
        "IMP": ("imports", "импорт")},
    "siec": {"O4000": ("oil and petroleum products", "нефть и нефтепродукты")},
}
# Official field labels override generic/misleading local translations for these
# global codelist members. Provenance is in v5-overlay/evidence/verified-dimension-members.json.
# There is no dataset, country, destination, selected-indicator or query lookup.
_VERIFIED_MEMBER_LABELS = {'age': {'TOTAL': ('Total',),
         'Y15-59': ('From 15 to 59 years', 'От 15 до 59 лет'),
         'Y15-74': ('From 15 to 74 years', 'От 15 до 74 лет'),
         'Y16-24': ('From 16 to 24 years', 'От 16 до 24 лет'),
         'Y18-64': ('From 18 to 64 years', 'От 18 до 64 лет'),
         'Y20-64': ('From 20 to 64 years', 'От 20 до 64 лет'),
         'Y40-64': ('From 40 to 64 years', 'От 40 до 64 лет'),
         'Y50-64': ('From 50 to 64 years', 'От 50 до 64 лет'),
         'Y60-64': ('From 60 to 64 years', 'От 60 до 64 лет'),
         'Y_GE18': ('18 years or over', '18 лет и старше'),
         'Y_GE65': ('65 years or over', '65 лет и старше')},
 'c_birth': {'TOTAL': ('Total',)},
 'duration': {'M_LT1': ('Less than 1 month', 'Менее одного месяца')},
 'hhcomp': {'A_GE3': ('Three or more adults', 'Три или более взрослых')},
 'indic_bt': {'PRD': ('Production (volume)', 'Производство (объем)')},
 'indic_em': {'ACT': ('Persons in the labour force', 'Лица в составе рабочей силы'),
              'SC072': ('People aged 18-59 living in jobless households: share of persons aged 18-59 '
                        'who are living in households where no-one works',
                        'Доля населения 18–59 лет, живущего в домохозяйствах, где никто не работает')},
 'isced11': {'ED0-2': ('Less than primary, primary and lower secondary education (levels 0-2)',
                       'Образование ниже начального, начальное и неполное среднее (уровни 0–2)'),
             'ED02': ('Pre-primary education', 'Дошкольное образование'),
             'ED35_45': ('Upper secondary and post-secondary non-tertiary education - vocational '
                         '(levels 35 and 45)',
                         'Профессиональное среднее и послесреднее нетретичное образование (уровни 35 и '
                         '45)'),
             'ED5-8': ('Tertiary education (levels 5-8)', 'Высшее образование (уровни 5–8)'),
             'TOTAL': ('All ISCED 2011 levels', 'Все уровни образования ISCED 2011')},
 'iscedf13': {'TOTAL': ('Total',)},
 'lev_limit': {'SOME': ('Some', 'Некоторые ограничения активности')},
 'mgstatus': {'TOTAL': ('Total',)},
 'na_item': {'P34': ('Final consumption expenditure of non-resident households on the economic '
                     'territory - total',
                     'Конечное потребление нерезидентных домохозяйств на экономической территории — '
                     'всего')},
 'nace_r2': {'M_STS': ('Professional, scientific and technical activities required by STS regulation',
                       'Профессиональная, научная и техническая деятельность в составе, предусмотренном '
                       'регламентом STS')},
 'reason': {'TXP': ('Too expensive', 'Слишком дорого')},
 's_adj': {'SA': ('Seasonally adjusted data, not calendar adjusted data',
                  'Сезонно скорректированные данные без календарной корректировки'),
           'SCA': ('Seasonally and calendar adjusted data',
                   'Сезонно и календарно скорректированные данные')},
 'sector': {'TOT_SEC': ('Total',)},
 'statinfo': {'AVG': ('Average', 'Среднее'),
              'MEAN_EI': ('Mean equivalised income', 'Средний эквивалентный доход')},
 'worktime': {'TOTAL': ('Total',)}}
_KNOWN_AXES = frozenset({"age", "sex", "citizen", "partner", "hhcomp", "quant_inc", "rskpovth",
    "nace_r2", "nace_r1", "isced11", "wstatus", "med_spec", "indic_is", "ind_type", "stk_flow", "siec",
    "duration", "worktime", "c_birth", "statinfo", "sector", "na_item", "indic_em", "indic_bt",
    "mgstatus", "iscedf13", "lev_limit", "reason", "s_adj"})
_AGGREGATE_MEMBERS = {"sex": {"T", "TOTAL"}, "citizen": {"TOTAL"}, "partner": {"TOTAL", "WORLD"},
    "hhcomp": {"TOTAL"}, "quant_inc": {"TOTAL"}, "rskpovth": {"TOTAL"},
    "nace_r2": {"TOTAL"}, "nace_r1": {"TOTAL"}, "ind_type": {"IND_TOTAL"}, "age": {"TOTAL"},
    "isced11": {"TOTAL"}, "iscedf13": {"TOTAL"}, "mgstatus": {"TOTAL"},
    "c_birth": {"TOTAL"}, "worktime": {"TOTAL"}, "sector": {"TOT_SEC"}}
_MEMBER_CODES = {axis: frozenset(set(LABELS_EN.get(axis, {})) | set(LABELS_RU.get(axis, {}))
    | set(_SUPPLEMENTAL_LABELS.get(axis, {})) | set(_VERIFIED_MEMBER_LABELS.get(axis, {}))) for axis in _KNOWN_AXES}

DIMENSION_RULES: dict[str, tuple[str, tuple[str, ...]]] = {
    "search-dim-sex-total": ("sex", ("T", "TOTAL")),
    "search-dim-sex-male": ("sex", ("M",)),
    "search-dim-sex-female": ("sex", ("F",)),
    "search-dim-citizen-total": ("citizen", ("TOTAL",)),
    "search-dim-partner-total": ("partner", ("TOTAL", "WORLD")),
    "search-dim-household-type-total": ("hhcomp", ("TOTAL",)),
    "search-dim-income-quintiles-total": ("quant_inc", ("TOTAL",)),
    "search-dim-income-threshold-groups-total": ("rskpovth", ("TOTAL",)),
    "search-dim-education-below-upper-secondary": ("isced11", ("ED0-2",)),
    "search-dim-status-employed": ("wstatus", ("EMP",)),
    "search-dim-clinical-practising": ("wstatus", ("PRACT",)),
    "search-dim-clinical-active": ("wstatus", ("PACT",)),
    "search-dim-clinical-licensed": ("wstatus", ("LIC",)),
    "search-dim-medical-physicians": ("med_spec", ("PHYS",)),
    "search-dim-internet-daily": ("indic_is", ("I_IDAY",)),
    "search-dim-individuals-total": ("ind_type", ("IND_TOTAL",)),
    "search-dim-oil-opening-stock": ("stk_flow", ("STKOP_NAT",)),
}
# Named aggregate roles stay independent; a TOTAL on a different axis is never
# an equivalent, and full-time-equivalent worktime is not the combined total.
_NATIVE_FACETS = (
    ("search-dim-age-total", "age", ("TOTAL",),
        ("all age groups", "all ages", "все возрастные группы", "всех возрастных групп")),
    ("search-dim-education-levels-total", "isced11", ("TOTAL",),
        ("all education levels", "all ISCED 2011 levels", "все уровни образования", "всех уровней образования")),
    ("search-dim-education-fields-total", "iscedf13", ("TOTAL",),
        ("all fields of study", "all fields of education", "все направления подготовки", "всех направлений подготовки")),
    ("search-dim-migration-statuses-total", "mgstatus", ("TOTAL",),
        ("all migration statuses", "все миграционные статусы", "всех миграционных статусов")),
    ("search-dim-birth-countries-total", "c_birth", ("TOTAL",),
        ("all countries of birth", "all birth countries", "все страны рождения", "всех стран рождения")),
    ("search-dim-worktime-total", "worktime", ("TOTAL",),
        ("all working-time categories", "full time and part time together", "full and part time employment together",
         "полный и неполный рабочий день вместе", "полный и неполный рабочий день", "все режимы рабочего времени")),
    ("search-dim-institution-sectors-total", "sector", ("TOT_SEC",),
        ("sector total", "all institution sectors", "все секторы учреждений")),
    ("search-dim-education-pre-primary", "isced11", ("ED02",),
        ("pre primary education", "дошкольное образование", "дошкольном образовании")),
    ("search-dim-education-tertiary", "isced11", ("ED5-8",),
        ("tertiary education", "высшее образование", "высшего образования")),
    ("search-dim-education-vocational-secondary-post-secondary", "isced11", ("ED35_45",),
        ("upper secondary and post secondary non tertiary education vocational",
         "vocational upper secondary and post secondary non tertiary education",
         "профессиональное среднее или послесреднее нетретичное образование",
         "профессиональным средним или послесредним нетретичным образованием")),
    ("search-dim-statistic-mean-equivalised-income", "statinfo", ("MEAN_EI",),
        ("mean equivalised income", "средний эквивалентный доход", "среднего эквивалентного дохода")),
    ("search-dim-statistic-average", "statinfo", ("AVG",),
        ("statistic average", "статистическое среднее")),
    ("search-dim-contract-duration-under-one-month", "duration", ("M_LT1",),
        ("employment contract less than one month", "employment contract less than 1 month",
         "contract duration less than one month", "contract duration less than 1 month",
         "трудовым договором менее одного месяца", "срок трудового договора менее 1 месяца")),
    ("search-dim-adjustment-seasonal-calendar", "s_adj", ("SCA",),
        ("seasonally and calendar adjusted", "сезонно и календарно скорректированные")),
    ("search-dim-adjustment-seasonal-without-calendar", "s_adj", ("SA",),
        ("seasonally adjusted without calendar adjustment", "seasonally adjusted not calendar adjusted",
         "сезонно скорректированные без календарной корректировки")),
    ("search-dim-reason-too-expensive", "reason", ("TXP",),
        ("reason too expensive", "причина слишком дорого")),
    ("search-dim-activity-limitation-some", "lev_limit", ("SOME",),
        ("activity limitation category some", "категория ограничения активности некоторые")),
    ("search-dim-activities-professional-sts", "nace_r2", ("M_STS",),
        ("professional scientific and technical activities required by STS regulation",
         "профессиональная научная и техническая деятельность в составе предусмотренном регламентом STS")),
)
for _key, _axis, _accepted, _aliases in _NATIVE_FACETS:
    DIMENSION_RULES[_key] = (_axis, _accepted)

# A generic income-group total may name either recognised income classification.
# This never equates a quintile with a threshold or accepts another TOTAL axis.
DIMENSION_ANY_RULES = {
    "search-dim-income-groups-total": (("quant_inc", ("TOTAL",)), ("rskpovth", ("TOTAL",))),
    "search-dim-activities-total": (("nace_r2", ("TOTAL",)), ("nace_r1", ("TOTAL",))),
}

_EXPLICIT_CONCEPTS = (
    (("both sexes", "all sexes", "оба пола", "обоих полов"), ("search-dim-sex-total",)),
    (("sex males", "male sex", "пол мужчины", "мужской пол"), ("search-dim-sex-male",)),
    (("sex females", "female sex", "пол женщины", "женский пол"), ("search-dim-sex-female",)),
    (("all citizens", "all citizenships", "все гражданства", "всех гражданств", "все гражданства населения"), ("search-dim-citizen-total",)),
    (("all partner countries", "all trading partners", "все страны партнеры", "все страны партнёры", "всех стран партнеров", "все страны партнеры торговли"), ("search-dim-partner-total",)),
    (("all household types", "all types of households", "все типы домохозяйств", "всех типов домохозяйств"), ("search-dim-household-type-total",)),
    (("all income quintiles", "across all income quintiles", "все квинтили доходов", "всех квинтилей доходов", "по всем квинтилям доходов"), ("search-dim-income-quintiles-total",)),
    (("all income threshold groups", "all poverty threshold groups", "все группы по порогу доходов", "всех групп по порогу доходов"), ("search-dim-income-threshold-groups-total",)),
    (("all income groups", "income group total", "все группы дохода", "всех групп дохода", "все группы доходов", "всех групп доходов"), ("search-dim-income-groups-total",)),
    (("all economic activities", "all NACE activities", "все виды экономической деятельности", "всех видов экономической деятельности"), ("search-dim-activities-total",)),
    (("below upper secondary education", "below upper secondary", "less than primary primary and lower secondary education", "ниже среднего образования"), ("search-dim-education-below-upper-secondary",)),
    (("labour status employed", "labor status employed", "employment status employed", "статус занятости занятые"), ("search-dim-status-employed",)),
    (("clinical status practising", "clinical status practicing", "статус практикующие"), ("search-dim-clinical-practising",)),
    (("clinical status professionally active", "статус профессионально активные"), ("search-dim-clinical-active",)),
    (("clinical status licensed to practice", "статус лицензированные"), ("search-dim-clinical-licensed",)),
    (("medical specialty physicians", "медицинская специальность врачи"), ("search-dim-medical-physicians",)),
    (("internet access frequency daily", "daily internet access dimension", "частота доступа к интернету ежедневно"), ("search-dim-internet-daily",)),
    (("all individuals", "all individual types", "all persons", "все люди", "всех людей"), ("search-dim-individuals-total",)),
    (("opening stock", "opening stocks", "начальные запасы", "начальных запасов"), ("search-dim-oil-opening-stock",)),
)

_MEDICAL_CONCEPTS = []
for _member, _labels in _SUPPLEMENTAL_LABELS["med_spec"].items():
    if _member == "PHYS":
        continue
    _key = "search-dim-medical-" + _member.casefold().replace("_", "-")
    DIMENSION_RULES[_key] = ("med_spec", (_member,))
    _MEDICAL_CONCEPTS.append((("medical specialty " + _labels[0], "медицинская специальность " + _labels[1]), (_key,)))


def _phrase(text: str) -> str:
    """Use parser-compatible case/yo/punctuation normalisation without imports."""
    return " ".join(re.findall(r"[a-zа-я0-9]+", str(text).casefold().replace("ё", "е")))


def _age_alias(code: str) -> str:
    """Internal nonnumeric phrase shields recognised age numbers from dates."""
    def alphabetic(match: re.Match[str]) -> str:
        number, letters = int(match[0]), ""
        while True:
            number, digit = divmod(number, 26)
            letters = chr(97 + digit) + letters
            if not number:
                return letters
    return "age facet " + re.sub(r"\d+", alphabetic, code.casefold().replace("_", " ").replace("-", " through "))


def _age_concepts() -> tuple:
    """Register only actual public dictionary age members and bounded wording."""
    concepts = []
    for code in sorted(set(AGE_RU) | set(AGE_EN) | set(_VERIFIED_MEMBER_LABELS.get("age", {}))):
        aliases = [_age_alias(code)]
        match = re.fullmatch(r"Y(\d+)-(\d+)", code)
        if match:
            low, high = match.groups()
            aliases += [f"age {low} to {high}", f"ages {low} to {high}", f"aged {low} to {high}",
                f"ages {low} {high}", f"aged {low} {high}", f"age {low} {high}", f"{low} {high} years", f"{low} {high} лет",
                f"от {low} до {high} лет", f"возраст {low} {high}"]
        match = re.fullmatch(r"Y_LT(\d+)", code)
        if match:
            age = match[1]
            aliases += [f"under {age} years", f"under {age}", f"less than {age} years",
                f"младше {age} лет", f"младше {age}"]
        match = re.fullmatch(r"Y_GE(\d+)", code)
        if match:
            age = match[1]
            aliases += [f"age {age} and over", f"aged {age} and over", f"{age} years and over",
                f"age {age} or over", f"aged {age} or over", f"{age} years or over", f"{age} лет и старше"]
        match = re.fullmatch(r"Y(\d+)", code)
        if match:
            age = match[1]
            aliases += [f"aged {age}", f"age {age}", f"возраст {age} лет"]
        if len(aliases) == 1:
            continue
        key = "search-dim-age-" + code.casefold().replace("_", "-")
        DIMENSION_RULES[key] = ("age", (code,))
        concepts.append((tuple(dict.fromkeys(_phrase(alias) for alias in aliases)), (key,)))
    return tuple(concepts)


def _native_alias(key: str) -> str:
    """A nonnumeric typed role phrase shields contract and education numbers."""
    return "native facet " + key.removeprefix("search-dim-").replace("-", " ")


_NATIVE_REPLACEMENTS = {_phrase(alias): _native_alias(key)
    for key, _axis, _accepted, aliases in _NATIVE_FACETS for alias in aliases}
_NATIVE_PATTERN = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(alias) for alias in
    sorted(_NATIVE_REPLACEMENTS, key=len, reverse=True)) + r")(?!\w)")
_NATIVE_CONCEPTS = tuple(((_native_alias(key),), (key,))
    for key, _axis, _accepted, _aliases in _NATIVE_FACETS)

_AGE_CONCEPTS = _age_concepts()
# Numeric age wording is consumed by the one compiled pre-parser expression.
# The main intent inventory needs only its canonical nonnumeric phrase, not a
# second scan of hundreds of equivalent numeric aliases on every request.
DIMENSION_CONCEPTS = _EXPLICIT_CONCEPTS + tuple(((aliases[0],), group)
    for aliases, group in _AGE_CONCEPTS) + tuple(_MEDICAL_CONCEPTS) + _NATIVE_CONCEPTS
_AGE_REPLACEMENTS = {alias: aliases[0] for aliases, _group in _AGE_CONCEPTS for alias in aliases[1:]}
_AGE_PATTERN = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(alias) for alias in
    sorted(_AGE_REPLACEMENTS, key=len, reverse=True)) + r")(?!\w)")
_CLINICAL_REPLACEMENTS = {}
for _labels in _SUPPLEMENTAL_LABELS["med_spec"].values():
    for _status, _replacement in (("practising", "clinical status practising"),
        ("practicing", "clinical status practising"), ("professionally active", "clinical status professionally active"),
        ("licensed to practice", "clinical status licensed to practice")):
        _CLINICAL_REPLACEMENTS[_status + " " + _labels[0]] = _replacement + " medical specialty " + _labels[0]
    _CLINICAL_REPLACEMENTS["практикующие " + _labels[1]] = "статус практикующие медицинская специальность " + _labels[1]
_CLINICAL_PATTERN = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(alias) for alias in
    sorted(_CLINICAL_REPLACEMENTS, key=len, reverse=True)) + r")(?!\w)")


def prepare_dimensions(text: str) -> str:
    """Shield complete recognised age spans; preserve all outside query text.

    Exact named native categories become typed roles before calendar parsing.
    Explicit compound clinical subjects become two independent slice facets.
    Bare years, month ranges, unknown age bands and unsupported words stay intact.
    """
    text = _NATIVE_PATTERN.sub(lambda match: _NATIVE_REPLACEMENTS[match[0]], text)
    if re.search(r"(?<!\d)\d{1,3}(?!\d)", text):
        text = _AGE_PATTERN.sub(lambda match: _AGE_REPLACEMENTS[match[0]], text)
    if any(status in text for status in ("practis", "practic", "professionally active", "licensed", "практикующие")):
        text = _CLINICAL_PATTERN.sub(lambda match: _CLINICAL_REPLACEMENTS[match[0]], text)
    return text


def _members(provider: str | None, slice_json: Mapping | None) -> dict[str, str]:
    """Only the actual Eurostat provider and string slice values are evidence."""
    if str(provider or "").strip().casefold() != "eurostat" or not isinstance(slice_json, Mapping):
        return {}
    return {axis: member.strip().upper() for axis, member in slice_json.items()
        if axis in _KNOWN_AXES and isinstance(member, str) and member.strip()}


@lru_cache(maxsize=8192)
def _member_labels(axis: str, member: str) -> tuple[str, ...]:
    """Exact native member labels, with axis-specific totals and no flat Total."""
    # Aggregate labels are represented only by their named typed markers. The
    # word "all" must never match an unrelated TOTAL member as ordinary text.
    if member in _AGGREGATE_MEMBERS.get(axis, ()):
        return ()
    if axis not in _KNOWN_AXES or member not in _MEMBER_CODES[axis]:
        return ()
    labels = [*_SUPPLEMENTAL_LABELS.get(axis, {}).get(member, ())]
    # A corrected official member never inherits a contradictory local label.
    witnesses = _VERIFIED_MEMBER_LABELS.get(axis, {}).get(member)
    if witnesses is None:
        witnesses = (label_en(axis, member), label_ru(axis, member))
    for label in witnesses:
        if label and _phrase(label) not in {"total", "итого", "всего"}:
            labels.append(label)
    return tuple(dict.fromkeys(labels))


@lru_cache(maxsize=1)
def _label_catalogue() -> tuple[tuple[str, str, str, str, tuple[str, ...]], ...]:
    """Normalise the finite static member-label catalogue once per process."""
    rows = []
    for axis in sorted(_KNOWN_AXES):
        for member in sorted(_MEMBER_CODES[axis]):
            text = " ".join(_member_labels(axis, member))
            if text:
                norm = _phrase(text)
                rows.append((axis, member, text, " " + norm + " ", tuple(norm.split())))
    return tuple(rows)


def native_dimension_labels(provider: str | None, slice_json: Mapping | None) -> tuple[str, ...]:
    """Expose semantic witnesses only for present recognised native fields."""
    return tuple(dict.fromkeys(label for axis, member in _members(provider, slice_json).items()
        for label in _member_labels(axis, member)))


def dimension_metadata(provider: str | None, slice_json: Mapping | None) -> str:
    """Emit the same required markers used by pre-LIMIT exact slice clauses."""
    members = _members(provider, slice_json)
    markers = [key for key, (axis, accepted) in DIMENSION_RULES.items() if members.get(axis) in accepted]
    markers += [key for key, rules in DIMENSION_ANY_RULES.items()
        if any(members.get(axis) in accepted for axis, accepted in rules)]
    return " ".join((*markers, *native_dimension_labels(provider, slice_json)))


def _provider_clause(provider_column: ColumnElement) -> ColumnElement:
    """Mirror the exact Python provider normalisation in SQL."""
    return func.lower(func.trim(func.coalesce(provider_column, ""))) == "eurostat"


class _JsonMemberIsString(FunctionElement):
    """Dialect-specific JSON type witness shared by every member predicate."""
    type = Boolean()
    inherit_cache = True


@compiles(_JsonMemberIsString)
def _json_member_string_unknown(element, compiler, **kw):
    return "false"  # Unimplemented dialects have no trusted JSON evidence.


@compiles(_JsonMemberIsString, "postgresql")
def _json_member_string_postgresql(element, compiler, **kw):
    column, axis = list(element.clauses)
    return "jsonb_typeof(CAST(" + compiler.process(column, **kw) + " AS JSONB) -> " + compiler.process(axis, **kw) + ") = 'string'"


@compiles(_JsonMemberIsString, "sqlite")
def _json_member_string_sqlite(element, compiler, **kw):
    column, axis = list(element.clauses)
    return "json_type(" + compiler.process(column, **kw) + ", '$.' || " + compiler.process(axis, **kw) + ") = 'text'"


def _member_column(slice_column: ColumnElement, axis: str) -> ColumnElement:
    """Use parameterised JSON extraction; missing/non-string values fail closed."""
    normalised = func.upper(func.trim(func.coalesce(slice_column[axis].as_string(), "")))
    return case((_JsonMemberIsString(slice_column, literal(axis)), normalised), else_="")


def dimension_constraints(terms: tuple[tuple[str, ...], ...], provider_column: ColumnElement,
        slice_column: ColumnElement) -> list[ColumnElement]:
    """Require each explicit axis before candidate limits, never a flat TOTAL."""
    clauses = []
    for alternatives in terms:
        key = alternatives[0] if alternatives else ""
        rule = DIMENSION_RULES.get(key)
        if rule:
            axis, accepted = rule
            clauses.append(and_(_provider_clause(provider_column), _member_column(slice_column, axis).in_(accepted)))
        elif key in DIMENSION_ANY_RULES:
            clauses.append(and_(_provider_clause(provider_column), or_(*(
                _member_column(slice_column, axis).in_(accepted) for axis, accepted in DIMENSION_ANY_RULES[key]))))
        elif key.startswith("search-dim-"):
            clauses.append(false())
    return clauses


@lru_cache(maxsize=2048)
def _lexical_member_groups(alternatives: tuple[tuple[str, bool], ...]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Select static member witnesses for complete words or retained raw prefixes.

    The catalogue is native, finite and independent of rows and visitor history.
    Every complete phrase uses normalized word boundaries; a raw single word
    may keep its established token-prefix role. Aggregate members have no labels.
    """
    queries = tuple((_phrase(word), complete) for word, complete in alternatives
        if not word.startswith("search-") and len(_phrase(word)) >= 3)
    selected: dict[str, set[str]] = {}
    for axis, member, _text, padded, tokens in _label_catalogue():
        if any(" " + word + " " in padded or (not complete and " " not in word
                and any(token.startswith(word) for token in tokens)) for word, complete in queries):
            selected.setdefault(axis, set()).add(member)
    return tuple((axis, tuple(sorted(members))) for axis, members in sorted(selected.items()))


def native_dimension_match_clause(provider_column: ColumnElement, slice_column: ColumnElement,
        alternatives: tuple[tuple[str, bool], ...]) -> ColumnElement:
    """One grouped native provider/axis/member predicate per required term.

    Static labels decide which exact members can witness the term. SQL checks
    only actual string member identities, never a concatenated label CASE pool.
    Typed facets remain independently mandatory through dimension_constraints.
    """
    groups = _lexical_member_groups(alternatives)
    if not groups:
        return false()
    return and_(_provider_clause(provider_column), or_(*(
        _member_column(slice_column, axis).in_(members) for axis, members in groups)))


def native_dimension_text(provider_column: ColumnElement, slice_column: ColumnElement,
        terms: tuple[tuple[str, ...], ...] | None = None) -> ColumnElement:
    """SQL semantic label witnesses from actual fields, matching Python labels.

    Passing query terms emits only relevant labelled members to bound expression
    size. Explicit marker clauses remain separate and mandatory. No category,
    SEO text, dataset name or absent field can fabricate a dimension witness.
    """
    query_words = tuple(sorted({_phrase(alt) for group in (terms or ()) for alt in group
        if not alt.startswith("search-") and len(_phrase(alt)) >= 3}))
    explicit_members: dict[str, set[str]] = {}
    for group in terms or ():
        key = group[0] if group else ""
        rules = (DIMENSION_RULES[key],) if key in DIMENSION_RULES else DIMENSION_ANY_RULES.get(key, ())
        for axis, accepted in rules:
            explicit_members.setdefault(axis, set()).update(accepted)
    if terms is not None and not query_words and not explicit_members:
        return literal("")
    selected: dict[str, list[tuple[str, str]]] = {}
    for axis, member, text, padded, tokens in _label_catalogue():
        if terms is not None and member not in explicit_members.get(axis, ()) and not any(
            " " + word + " " in padded or (" " not in word and any(token.startswith(word) for token in tokens))
            for word in query_words):
            continue
        selected.setdefault(axis, []).append((member, text))
    if not selected:
        return literal("")
    expression = literal("")
    for axis, branches in selected.items():
        # Display/measure witnesses retain the exact label output. A simple
        # CASE evaluates the same type-guarded member once per axis instead of
        # repeating JSON extraction/type normalization for every member.
        expression = expression + literal(" ") + case(dict(branches), value=_member_column(slice_column, axis), else_="")
    return case((_provider_clause(provider_column), func.trim(expression)), else_="")

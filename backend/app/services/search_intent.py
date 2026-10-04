"""Bounded, explainable RU/EN search intent; no network or learned claims."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from app.services.search_language import LANGUAGE_CONCEPTS, QUESTION_WORDS, prepare_language
from app.services.search_vocabulary import VOCABULARY_CONCEPTS, GRAMMAR_WORDS, prepare_vocabulary, prepare_temporal_roles
from app.services.search_units import UNIT_CONCEPTS
from app.services.search_dimensions import DIMENSION_CONCEPTS, prepare_dimensions

SEARCH_VERSION = "federated-v2"
TOKEN_RE = re.compile(r"[a-zа-я0-9]+")
STOP_WORDS = frozenset(("в", "во", "по", "за", "на", "из", "для", "и", "к", "the", "in", "of", "for", "and")) | QUESTION_WORDS | GRAMMAR_WORDS

# Equivalent concepts only. Minimum wage deliberately does not alias average wages.
CONCEPTS = (
    (("ввп на душу населения", "ввп на душу", "gdp per capita", "per capita gdp"), ("gdp-per-capita", "gdp per capita", "ввп на душу")),
    (("мрот", "minimum wage", "минимальная зарплата"), ("minimum-wage", "minimum wage", "минималь")),
    (("ипц", "cpi", "инфляция", "инфляции", "inflation", "рост цен"), ("cpi", "inflation", "hicp", "потребительских цен", "consumer price")),
    (("ввп", "gdp", "валовой продукт"), ("gdp", "ввп", "валовой внутренний продукт", "gross domestic product")),
    (("ключевая ставка", "ставка цб", "key rate", "cbr rate", "central bank rate"), ("key-rate", "ключевая ставка")),
    (("средняя заработная плата", "зарплата", "зарплаты", "заработная плата", "зпл", "зп", "з п", "salary", "wages"), ("wage", "salary", "заработн", "зарплат")),
    (("безработица", "безработицы", "уровень безработицы", "unemployment", "unemployment rate"), ("unemployment", "безработ", "jobless")),
    (("экспорт товаров", "exports of goods", "goods exports"), ("exports", "экспорт товаров", "exports of goods")),
    (("импорт товаров", "imports of goods", "goods imports"), ("imports", "импорт товаров", "imports of goods")),
    (("население", "населения", "population"), ("population", "населен", "resident population")),
    (("промпроизводство", "ипп", "industrial production"), ("ipi", "industrial production", "промышленного производства")),
    (("ицп", "ppi", "цены производителей"), ("ppi", "producer price", "цен производителей")),
    (("нефть", "нефти", "oil", "brent"), ("brent", "нефт", "crude oil")),
    (("золото", "золота", "gold"), ("gold", "золот")),
    (("курс доллара к рублю", "курс доллара", "доллар", "usd rub", "usdrub"), ("usd-rub", "usd rub", "доллар")),
    (("курс юаня к рублю", "курс юаня", "юань", "юаня", "cny rub", "cnyrub"), ("cny-rub", "cny rub", "юан")),
    (("курс доллара к иене", "usd jpy", "usdjpy"), ("usd-jpy", "usd jpy", "dollar yen")),
    (("курс евро к доллару", "eur usd", "eurusd"), ("eur-usd", "eur usd")),
    (("индекс доллара", "dollar index", "dxy"), ("usd-index", "dollar index", "индекс доллара")),
    (("курс евро", "евро", "eur rub"), ("eur-rub", "eur rub", "евро")),
    (("биткоин", "биткойн", "bitcoin", "btc"), ("btc-usd", "bitcoin", "биткоин")),
    (("ипотека", "ипотеки", "mortgage"), ("mortgage", "ипотеч")),
    (("розница", "retail trade"), ("retail", "рознич")),
    (("бензин", "gasoline", "petrol"), ("fuel", "gasoline", "petrol", "бензин")),
    (("аи95", "аи 95", "ai95", "ai 95", "бензин 95"), ("fuel-ai95", "аи95", "аи 95", "ai95", "ceni-ai95")),
    (("аи92", "аи 92", "ai92", "ai 92", "бензин 92"), ("fuel-ai92", "аи92", "аи 92", "ai92", "ceni-ai92")),
    (("дизельное топливо", "дизель", "diesel"), ("fuel-diesel", "diesel", "дизель", "ceni-dt")),
    (("пенсии", "пенсия", "pension"), ("pension", "пенси")),
    (("вклады от 1 до 3 лет", "вклады на 1 3 года"), ("deposit-rate-medium",)),
    (("доступность первичного жилья",), ("housing-affordability-primary",)),
    # Native mean transaction prices are an economic measure. «Средние» here
    # must not become a request to compute a temporal average of another row.
    (("средние цены на первичном рынке жилья", "average prices on the primary housing market", "average prices on primary housing market"),
        ("housing-price-primary", "srednie-tseny-na-pervichnom-rynke-zhilya", "средние цены на первичном рынке жилья", "average prices on the primary housing market")),
    (("средние цены на вторичном рынке жилья", "average prices on the secondary housing market", "average prices on secondary housing market"),
        ("housing-price-secondary", "srednie-tseny-na-vtorichnom-rynke-zhilya", "средние цены на вторичном рынке жилья", "average prices on the secondary housing market")),
    (("промышленность добыча",), ("ipi-mining",)),
    (("промышленность обработка",), ("ipi-manufacturing",)),
    (("продовольствие ипц",), ("cpi-food",)),
    (("денежная масса", "money supply"), ("money supply", "денежная масса", "m2", "m1", "m0")),
    (("средняя ставка депозитов", "средняя ставка по вкладам", "средняя ставка по депозитам", "ставка по вкладам", "deposit rate", "deposit rates"), ("deposit-rate", "deposit interest", "ставка по вкладам")),
    (("депозит", "депозиты", "вклад", "вклады"), ("deposit", "вклад", "депозит")),
    (("уголь", "coal"), ("coal", "угол")),
    (("количество студентов", "число студентов", "численность студентов"), ("численность студентов", "student enrollment", "students enrolled")),
    (("сталь", "steel"), ("steel", "сталь")),
    (("год к году", "year on year", "annual rate of change", "yoy"), ("search-mode-yoy",)),
    (("к прошлому периоду", "к предыдущему периоду", "period on period"), ("search-mode-pop",)),
    (("уровень", "level"), ("search-mode-level",)),
    (("средняя", "среднее", "average", "mean"), ("search-mode-avg",)),
    (("по годам", "annual", "yearly"), ("search-freq-annual",)),
    (("по кварталам", "quarterly"), ("search-freq-quarterly",)),
    (("по месяцам", "monthly"), ("search-freq-monthly",)),
    (("по неделям", "weekly"), ("search-freq-weekly",)),
    (("по дням", "daily"), ("search-freq-daily",)),
    (("проценты", "процент", "percent", "percentage"), ("search-unit-percent",)),
)

CONCEPTS = CONCEPTS + LANGUAGE_CONCEPTS + VOCABULARY_CONCEPTS + UNIT_CONCEPTS + DIMENSION_CONCEPTS

_SINGLE_ALIASES = tuple((phrase_alias, alternatives) for aliases, alternatives in CONCEPTS
    for alias in aliases if " " not in (phrase_alias := " ".join(TOKEN_RE.findall(
        unicodedata.normalize("NFKC", alias).casefold().replace("ё", "е")))))
_CONTROL_WORDS = frozenset(token for aliases, alternatives in CONCEPTS
    if alternatives[0].startswith(("search-unit-", "search-mode-", "search-freq-", "search-source-freq-",
        "search-dim-", "search-denominator-", "search-price-base-")) for alias in aliases for token in TOKEN_RE.findall(
        unicodedata.normalize("NFKC", alias).casefold().replace("ё", "е")) if len(token) >= 3
        and not (alternatives[0] == "search-unit-chained-prices" and token in ("prices", "цены", "ценах")))
_CURRENCY_KEYS = frozenset(("search-unit-usd", "search-unit-cad", "search-unit-aud", "search-unit-gbp",
    "search-unit-cny", "search-unit-eur", "search-unit-jpy", "search-unit-rub"))
_FX_SUBJECT_KEYS = frozenset(("usd-index", "usd-rub", "cny-rub", "usd-jpy", "eur-usd", "eur-rub"))
_DENOMINATOR_COUNTS = {"1000": 1000, "1 000": 1000, "thousand": 1000, "one thousand": 1000,
    "тысячу": 1000, "тысячи": 1000, "10000": 10000, "10 000": 10000, "ten thousand": 10000,
    "десять тысяч": 10000, "100000": 100000, "100 000": 100000, "hundred thousand": 100000,
    "сто тысяч": 100000}
_DENOMINATOR_RE = re.compile(r"\b(?:per|на)\s+(?P<count>"
    + "|".join(re.escape(count) for count in sorted(_DENOMINATOR_COUNTS, key=len, reverse=True))
    + r")\s+(?:population|persons?|people|inhabitants?|residents?|населения|жителей|жителя|человек(?:а)?|чел)"
    + r"(?:\s+(?:population|населения))?\b")

# These ISO codes are also ordinary English words. Lowercase prose must not
# become an unrelated country facet; an explicit uppercase code still works.
_AMBIGUOUS_ISO = frozenset(("is", "it", "in", "at", "us", "no", "be", "as", "to", "am", "me", "do"))
_CODE_RE = re.compile(r"(?<![\w-])[a-z][a-z0-9_]*(?:-[a-z0-9_]+)+(?![\w-])")

COUNTRY_ALIASES = {
    "russia": ("россия", "россии", "россию", "российский", "российская", "российской", "российском", "российские", "российских", "рф", "russia", "russian", "russian federation"),
    "germany": ("германия", "германии", "германию", "фрг", "deutschland", "germany", "german"),
    "united-states": ("сша", "соединенные штаты", "united states", "usa", "us", "america", "american", "americans"),
    "canada": ("canadian",),
    "australia": ("australian",),
    "mexico": ("mexican",),
    "united-kingdom": ("великобритания", "великобритании", "британия", "britain", "uk", "united kingdom", "british"),
    "china": ("китай", "китая", "китае", "кнр", "china", "chinese"),
    "japan": ("япония", "японии", "японию", "japan", "japanese"),
    "france": ("франция", "франции", "францию", "france", "french"),
    "india": ("индия", "индии", "индию", "india", "indian"),
    "brazil": ("бразилия", "бразилии", "бразилию", "brazil"),
    "south-korea": ("южная корея", "южной кореи", "корея", "south korea", "korea"),
    "turkey": ("турция", "турции", "турцию", "turkey", "türkiye"),
}
REGION_ALIASES = {
    "moskva": ("москва", "москвы", "москве", "москву", "moscow"),
    "moscow": ("москва", "москвы", "москве", "москву", "moscow"),
    "moskovskaya-oblast": ("московская область", "московской области", "moscow oblast", "moscow region"),
    "sankt-peterburg": ("санкт петербург", "санкт петербурга", "петербург", "спб", "saint petersburg"),
    "respublika-tatarstan": ("татарстан", "татарстана", "татарстане", "tatarstan"),
    "respublika-bashkortostan": ("башкортостан", "башкортостана", "башкортостане", "bashkortostan"),
    "krasnodarskiy-kray": ("краснодарский край", "краснодарского края", "краснодарском крае", "krasnodar krai"),
}

_EN_KEYS = "qwertyuiop[]asdfghjkl;'zxcvbnm,."
_RU_KEYS = "йцукенгшщзхъфывапролджэячсмитьбю"
_LAYOUT_EN_RU = str.maketrans(_EN_KEYS, _RU_KEYS)
_LAYOUT_RU_EN = str.maketrans(_RU_KEYS, _EN_KEYS)
MONTHS = (
    ("январ", "january", "jan"), ("феврал", "february", "feb"),
    ("март", "march", "mar"), ("апрел", "april", "apr"),
    ("мая", "май", "may"), ("июн", "june", "jun"),
    ("июл", "july", "jul"), ("август", "august", "aug"),
    ("сентябр", "september", "sep"), ("октябр", "october", "oct"),
    ("ноябр", "november", "nov"), ("декабр", "december", "dec"),
)


# The three text helpers below are pure functions of a string and are called
# hundreds of thousands of times per search over the same catalogue titles.
# Memoizing them (per process) removes most of the scoring CPU without changing
# any result.
@lru_cache(maxsize=131072)
def _normalize_text(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().replace("ё", "е").split())


def normalize(value: object) -> str:
    return _normalize_text(value if isinstance(value, str) else str(value or ""))


@lru_cache(maxsize=131072)
def _tokens_of_normalized(text: str) -> tuple[str, ...]:
    return tuple(TOKEN_RE.findall(text))


def tokens(value: object) -> tuple[str, ...]:
    return _tokens_of_normalized(normalize(value))


@lru_cache(maxsize=131072)
def _phrase_of_normalized(text: str) -> str:
    return " ".join(_tokens_of_normalized(text))


def phrase(value: object) -> str:
    return _phrase_of_normalized(normalize(value))


@lru_cache(maxsize=262144)
def edit_distance_one(left: str, right: str) -> bool:
    """At most one insertion/deletion/substitution/adjacent transposition."""
    if left == right:
        return True
    if abs(len(left) - len(right)) > 1:
        return False
    if len(left) == len(right):
        mismatch = [i for i, (a, b) in enumerate(zip(left, right)) if a != b]
        return len(mismatch) == 1 or (len(mismatch) == 2 and mismatch[1] == mismatch[0] + 1
            and left[mismatch[0]] == right[mismatch[1]] and left[mismatch[1]] == right[mismatch[0]])
    short, long = sorted((left, right), key=len)
    for i in range(len(long)):
        if long[:i] + long[i + 1:] == short:
            return True
    return False


@lru_cache(maxsize=4096)
def _control_neighbour(token: str) -> bool:
    """An unfinished/misspelt unit, mode or frequency never becomes a facet."""
    return token not in _CONTROL_WORDS and any(edit_distance_one(token, alias) for alias in _CONTROL_WORDS)


def _concept_correction(token: str) -> tuple[str, tuple[str, ...]] | None:
    """Correct one long unknown word only when one noncontrol meaning exists."""
    if len(token) < 5 or _control_neighbour(token):
        return None
    candidates = [(alias, alternatives) for alias, alternatives in _SINGLE_ALIASES
        if len(alias) >= 4 and not alternatives[0].startswith("search-") and edit_distance_one(token, alias)]
    return candidates[0] if len({alternatives for _alias, alternatives in candidates}) == 1 else None


@lru_cache(maxsize=2048)
def nominal_variants(token: str) -> tuple[str, ...]:
    """Generate bounded complete nominal forms, never a truncated stem match.

    Each form remains inside one mandatory OR group shared by SQL and scoring.
    Unit/period/dimension controls and their near typos are exempt. This is
    inflection, not a synonym/subject correction or unknown-qualifier deletion.
    """
    if token not in ("index", "indices") and (token in _CONTROL_WORDS or _control_neighbour(token)):
        return (token,)
    # A grammatical case of a declared control noun is still a control, not
    # another economic subject. Exact unit aliases are resolved by the parser;
    # unsupported oblique forms remain their original mandatory word.
    if token.endswith(("ами", "ями")) and token[:-3] in _CONTROL_WORDS:
        return (token,)
    forms = [token]
    if re.fullmatch(r"[a-z]{4,}", token):
        if token.endswith("ies") and len(token) >= 7:
            forms.append(token[:-3] + "y")
        elif token.endswith(("ches", "shes", "xes", "sses")) and len(token) >= 5:
            forms.append(token[:-2])
        elif token.endswith("s") and not token.endswith(("ss", "us", "is", "series")) and len(token) >= 6:
            forms.append(token[:-1])
        elif token.endswith("y") and token[-2] not in "aeiou":
            forms.append(token[:-1] + "ies")
        elif not token.endswith(("s", "ing", "ed")):
            forms.append(token + ("es" if token.endswith(("ch", "sh", "x")) else "s"))
        if token in ("index", "indices"):
            forms.append("indices" if token == "index" else "index")
    elif re.fullmatch(r"[а-я]{5,}", token):
        endings = (("ами", ("ы",)), ("ями", ("и",)),
            ("иях", ("ии", "ия")), ("ах", ("ы", "а")), ("ях", ("и", "я")),
            ("ов", ("ы", "", "а")), ("ев", ("и", "ь")), ("ей", ("и", "ь")),
            ("ом", ("",)), ("а", ("",)), ("я", ("ь", "й")))
        for suffix, replacements in endings:
            if token.endswith(suffix) and len(token) - len(suffix) >= 3:
                stem = token[:-len(suffix)]
                forms.extend(stem + ("и" if ending == "ы" and stem[-1] in "гкхжчшщ" else ending)
                    for ending in replacements)
                break
        # Complete agreeing adjective forms support genitive/locative native
        # labels without permitting an arbitrary prefix of another subject.
        for suffix, replacements in (("ого", ("ый", "ой")), ("его", ("ий",)),
                ("ых", ("ые",)), ("их", ("ие",)), ("ом", ("ый", "ой")), ("ем", ("ий",))):
            if token.endswith(suffix) and len(token) - len(suffix) >= 4:
                forms.extend(token[:-len(suffix)] + ending for ending in replacements)
                break
    return tuple(dict.fromkeys(forms))


def _extract_denominators(text: str) -> tuple[str, tuple[tuple[str, ...], ...]]:
    """Keep a complete person denominator as one mandatory ratio facet."""
    positions, groups = set(), []
    for match in _DENOMINATOR_RE.finditer(text):
        group = (f"search-denominator-{_DENOMINATOR_COUNTS[match['count']]}-persons",)
        if group not in groups:
            groups.append(group)
        positions.update(range(match.start(), match.end()))
    return "".join(" " if index in positions else char for index, char in enumerate(text)), tuple(groups)


def _percentage_word_text(text: str) -> str:
    """Interest inside a complete known income subject is not a percent unit.

    Only exact multiword income subjects establish this role. A percentage word
    outside the subject, and every explicit percent symbol, remains mandatory.
    """
    positions = {position for aliases, alternatives in CONCEPTS
        if alternatives[0].endswith("-income") for alias in aliases if len(tokens(alias)) >= 2
        for start, end, _alias in _alias_occurrences(text, (alias,)) for position in range(start, end)}
    return "".join(" " if index in positions else char for index, char in enumerate(text))


def _extract_point_units(text: str) -> tuple[str, tuple[tuple[str, ...], ...]]:
    """Read exact point-unit compounds before an interest-rate rewrite can eat them.

    Aliases come from the shared native-unit registry. An explicit percent symbol
    or a percent word outside these spans remains a distinct required facet.
    """
    hits = [(start, end, group) for aliases, group in UNIT_CONCEPTS
        if group[0] == "search-unit-percentage-point"
        for start, end, _alias in _alias_occurrences(text, aliases)]
    positions, groups = set(), []
    for start, end, group in sorted(hits, key=lambda hit: (-(hit[1] - hit[0]), hit[0])):
        if positions.intersection(range(start, end)):
            continue
        positions.update(range(start, end))
        if group not in groups:
            groups.append(group)
    return "".join(" " if index in positions else char for index, char in enumerate(text)), tuple(groups)


def _outside_literal_query(query: str, literal: str | None) -> str:
    """Mask punctuation inside the authoritative literal as well as its words."""
    if not literal:
        return query
    matches, literal_matches = list(TOKEN_RE.finditer(query)), list(TOKEN_RE.finditer(normalize(literal)))
    parts = tuple(match[0] for match in literal_matches)
    if not parts:
        return query
    positions = set()
    for offset in range(len(matches) - len(parts) + 1):
        window = matches[offset:offset + len(parts)]
        if tuple(match[0] for match in window) == parts:
            start, end = window[0].start(), window[-1].end()
            prefix = normalize(literal)[:literal_matches[0].start()].strip()
            suffix = normalize(literal)[literal_matches[-1].end():].strip()
            if prefix:
                leading = re.search(re.escape(prefix) + r"\s*$", query[:start])
                if leading:
                    start = leading.start()
            if suffix:
                trailing = re.match(r"\s*" + re.escape(suffix), query[end:])
                if trailing:
                    end += trailing.end()
            positions.update(range(start, end))
    return "".join(" " if index in positions else char for index, char in enumerate(query))


def _percent_word_spans(text: str) -> set[int]:
    """Exact percent inflections are one unit role, never a duplicate qualifier."""
    percentage_text = _percentage_word_text(text)
    return {position for match in TOKEN_RE.finditer(percentage_text)
        if re.fullmatch(r"процент(?:ы|а|ах|ов|е|ом)?|percent(?:age)?s?", match[0])
        for position in range(match.start(), match.end())}


def _alias_occurrences(text: str, aliases: tuple[str, ...]):
    for alias in aliases:
        normalized = phrase(alias)
        if not normalized:
            continue
        for match in re.finditer(r"(?<!\w)" + re.escape(normalized) + r"(?!\w)", text):
            yield match.start(), match.end(), normalized


def _compile_concept_matchers() -> tuple:
    """Compile the immutable vocabulary once, retaining original tie ordering.

    Exact matches use the same normalized word boundaries as geography aliases.
    Phrase typo recovery retains the original alias and its token sequence; no
    vocabulary item, control facet or longest-span decision changes here.
    """
    return tuple((alternatives, tuple(
        (alias, normalized, tokens(alias), re.compile(r"(?<!\w)" + re.escape(normalized) + r"(?!\w)"))
        for alias in aliases if (normalized := phrase(alias))
    )) for aliases, alternatives in CONCEPTS)


CONCEPT_MATCHERS = _compile_concept_matchers()


def _russian_geo_cases(value: object) -> tuple[str, ...]:
    """Derive complete administrative-name cases from one actual catalogue name.

    Only the administrative head and its agreeing adjectives are inflected.
    Immutable proper-name parts and every catalogue suffix are preserved.
    """
    name = phrase(value)
    heads = {
        "область": ("области", "области", "области", "областью", "область"),
        "республика": ("республики", "республике", "республике", "республикой", "республику"),
        "край": ("края", "крае", "краю", "краем", "край"),
        "округ": ("округа", "округе", "округу", "округом", "округ"),
    }
    words = name.split()
    head_index = next((i for i, word in enumerate(words) if word in heads), None)
    if head_index is None:
        return ()
    head = words[head_index]
    # A leading official Republic name keeps its proper-name body unchanged:
    # «в Республике Марий Эл», «из Республики Коми» are full bounded aliases.
    if head_index == 0:
        if head != "республика" or len(words) < 2:
            return ()
        return tuple(" ".join((form, *words[1:])) for form in heads[head])
    feminine = head in ("область", "республика")
    adjective_endings = ("ая", "яя") if feminine else ("ский", "кий", "ый", "ий", "ой")
    if not any(word.endswith(adjective_endings) for word in words[:head_index]):
        return ()
    forms = []
    suffix = words[head_index + 1:]
    # Some actual catalogue names have a second proper name after an explicit
    # dash. Inflect only that complete known one-word noun alongside the head;
    # explanatory/exclusion tails and unknown extra words are never shortened.
    proper_suffix = suffix[0] if len(suffix) == 1 and re.search(
        r"[-–—]\s*" + re.escape(suffix[0]) + r"$", normalize(value)) else None
    suffix_cases = None
    if proper_suffix and proper_suffix.endswith("ия"):
        suffix_cases = tuple(proper_suffix[:-1] + end for end in ("и", "и", "и", "ей", "ю"))
    elif proper_suffix and proper_suffix.endswith("а"):
        gen = "и" if proper_suffix[-2:-1] in "гкхжчшщ" else "ы"
        instrumental = "ей" if proper_suffix[-2:-1] in "жчшщц" else "ой"
        suffix_cases = tuple(proper_suffix[:-1] + end for end in (gen, "е", "е", instrumental, "у"))
    elif proper_suffix and re.fullmatch(r"[а-я]+[бвгджзклмнпрстфхцчшщ]", proper_suffix):
        suffix_cases = tuple(proper_suffix + end for end in ("а", "е", "у", "ом", ""))
    for case, head_form in enumerate(heads[head]):
        inflected = []
        for word in words[:head_index]:
            if feminine and word.endswith("ая"):
                word = word[:-2] + ("ой", "ой", "ой", "ой", "ую")[case]
            elif feminine and word.endswith("яя"):
                word = word[:-2] + ("ей", "ей", "ей", "ей", "юю")[case]
            elif not feminine and word.endswith(("ский", "кий")):
                word = word[:-2] + ("ого", "ом", "ому", "им", "ий")[case]
            elif not feminine and word.endswith(("ый", "ой")):
                word = word[:-2] + ("ого", "ом", "ому", "ым", word[-2:])[case]
            elif not feminine and word.endswith("ий"):
                word = word[:-2] + ("его", "ем", "ему", "им", "ий")[case]
            inflected.append(word)
        forms.append(" ".join((*inflected, head_form, *words[head_index + 1:])))
        if suffix_cases:
            forms.append(" ".join((*inflected, head_form, suffix_cases[case])))
    return tuple(dict.fromkeys(forms))


def _geographic_possessive_aliases(item: dict) -> tuple[str, ...]:
    """Possessives of actual English names, excluding ambiguous prose ISO codes."""
    names = [item.get("name_en")]
    english_name = phrase(item.get("name_en"))
    if item["kind"] != "country":
        for prefix in ("republic of ", "republic ", "city of "):
            if english_name.startswith(prefix):
                names.append(english_name.removeprefix(prefix))
        if english_name.endswith(" republic"):
            names.append(english_name.removesuffix(" republic"))
    aliases = COUNTRY_ALIASES if item["kind"] == "country" else REGION_ALIASES
    names.extend(aliases.get(item["slug"], ()))
    return tuple(name + "'s" for name in names if name
        and re.fullmatch(r"[a-z]+(?:[ -][a-z]+)*", normalize(name))
        and phrase(name) not in _AMBIGUOUS_ISO)


def geo_aliases(item: dict) -> tuple[str, ...]:
    values = [item.get("slug"), item.get("name_ru"), item.get("name_en")]
    if item["kind"] == "country":
        values.append(item.get("country_code"))
        values.extend(COUNTRY_ALIASES.get(item["slug"], ()))
    else:
        values.extend(REGION_ALIASES.get(item["slug"], ()))
        ru_name, en_name = phrase(item.get("name_ru")), phrase(item.get("name_en"))
        for prefix in ("республика ", "г "):
            if ru_name.startswith(prefix):
                values.append(ru_name.removeprefix(prefix))
        if ru_name.endswith(" республика"):
            values.append(ru_name.removesuffix(" республика"))
        for prefix in ("republic of ", "republic ", "city of "):
            if en_name.startswith(prefix):
                values.append(en_name.removeprefix(prefix))
        if en_name.endswith(" republic"):
            values.append(en_name.removesuffix(" republic"))
    values.extend(_russian_geo_cases(item.get("name_ru")))
    values.extend(_geographic_possessive_aliases(item))
    # Predictable inflection for catalogue nouns, only for the actual entity.
    ru = phrase(item.get("name_ru"))
    if ru.endswith("ия"):
        values.append(ru[:-1] + "и")
        if " " not in ru:
            values.extend((ru[:-1] + "ю", ru[:-1] + "ей"))
    if ru.endswith("а") and " " not in ru:
        values.append(ru[:-1] + ("и" if len(ru) > 1 and ru[-2] in "гкхжчшщ" else "ы"))
        values.append(ru[:-1] + "е")
        values.append(ru[:-1] + "у")
        values.append(ru[:-1] + ("ей" if len(ru) > 1 and ru[-2] in "жчшщц" else "ой"))
    if (item["kind"] == "subnational_region" and item["country_slug"] == "united-states"
            and re.fullmatch(r"[а-я]+[бвгджзклмнпрстфхцчшщ]", ru)):
        values.extend(ru + ending for ending in ("а", "у", "ом", "е"))
    if (item["kind"] == "subnational_region" and item["country_slug"] == "united-states"
            and re.fullmatch(r"[а-я]+йи", ru)):
        # Russian plural proper names in -йи, only as complete supplied native
        # state names. A suffix alone cannot manufacture a catalogue entity.
        values.extend(ru[:-1] + ending for ending in ("ев", "ям", "ями", "ях"))
    return tuple(str(v) for v in values if v)


@dataclass(frozen=True)
class SearchIntent:
    query: str
    content: str
    terms: tuple[tuple[str, ...], ...]
    countries: frozenset[str] = frozenset()
    regions: frozenset[str] = frozenset()
    year: int | None = None
    month: int | None = None
    error: str | None = None
    corrected: str | None = None
    literal: str | None = None


def strip_geography(raw: str, geometry: list[dict], *, literal_content: str | None = None
        ) -> tuple[str, frozenset[str], frozenset[str], dict[str, str]]:
    """Remove longest actual geo spans, preserving identical-span ambiguity."""
    query = normalize(raw)
    text = phrase(query)
    literal = literal_content or literal_identifier(raw, geometry)
    protected_positions = {position for start, end, _alias in _alias_occurrences(text, (literal,))
        for position in range(start, end)} if literal else set()
    fx_subject_positions = {position for aliases, alternatives in CONCEPTS
        if alternatives[0] in _FX_SUBJECT_KEYS for alias in aliases if len(tokens(alias)) >= 2
        for start, end, _alias in _alias_occurrences(text, (alias,))
        if not protected_positions.intersection(range(start, end)) for position in range(start, end)}
    currency_aliases = tuple(alias for aliases, alternatives in UNIT_CONCEPTS
        if alternatives[0] in _CURRENCY_KEYS for alias in aliases if len(tokens(alias)) >= 2)
    protected_positions.update(position for start, end, _alias in _alias_occurrences(text, currency_aliases)
        if not fx_subject_positions.intersection(range(start, end)) for position in range(start, end))
    # A near currency phrase is not corrected. Keep its misspelt words so they
    # remain required, rather than letting fuzzy geography change CAD into USD.
    # An exact supplied place (e.g. «Australia dollars») retains its geo role.
    word_matches = list(TOKEN_RE.finditer(text))
    actual_geo_aliases = {phrase(alias) for item in geometry for alias in geo_aliases(item)}
    for alias in currency_aliases:
        parts = tokens(alias)
        if len(parts) > 4:
            continue
        for offset in range(len(word_matches) - len(parts) + 1):
            window = word_matches[offset:offset + len(parts)]
            mismatches = [(match[0], part) for match, part in zip(window, parts) if match[0] != part]
            if (len(mismatches) == 1 and min(map(len, mismatches[0])) >= 4
                    and mismatches[0][0] not in actual_geo_aliases and edit_distance_one(*mismatches[0])
                    and not fx_subject_positions.intersection(range(window[0].start(), window[-1].end()))):
                protected_positions.update(range(window[0].start(), window[-1].end()))
    original_words = re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", raw))
    # Preserve the register of two-letter Latin symbols, such as demographic
    # Mx or chemical Ca. Normal lowercase ISO prose and uppercase ISO codes
    # keep their established country role; mixed-case symbols remain content.
    case_text = " ".join(word if re.fullmatch(r"[A-Za-z]{2}", word) else piece.upper() if word.isupper() else piece
        for word in original_words for piece in tokens(word))
    # TOKEN_RE turns an English possessive into a separate «s» token. Remove it
    # with the known place only when an apostrophe actually occurs in the input.
    # «Russia s» therefore keeps the otherwise unknown qualifier «s».
    query_tokens = list(TOKEN_RE.finditer(query))
    possessive_ends, phrase_offset = set(), 0
    for index, match in enumerate(query_tokens):
        phrase_offset += len(match[0])
        if index and match[0] == "s":
            previous = query_tokens[index - 1]
            if re.fullmatch(r"[a-z]+", previous[0]) and query[previous.end():match.start()] in ("'", "’"):
                possessive_ends.add(phrase_offset)
        phrase_offset += 1
    geo_hits = []
    exact_spans, fuzzy_spans = set(), {}
    # Common grammar/domain vocabulary is not evidence of a misspelled place.
    # Otherwise «больше» can become Poland through its valid «польше» alias.
    domain_tokens = {token for aliases, _alternatives in CONCEPTS for alias in aliases for token in tokens(alias)}
    no_geo_typo = STOP_WORDS | domain_tokens
    geo_corrections, corrections = {}, {}
    for item in geometry:
        aliases = geo_aliases(item)
        possessive_aliases = {phrase(alias) for alias in _geographic_possessive_aliases(item)}
        for start, end, alias in _alias_occurrences(text, aliases):
            if alias in possessive_aliases and end not in possessive_ends:
                continue
            if protected_positions.intersection(range(start, end)):
                continue
            if (item["kind"] == "country" and alias in _AMBIGUOUS_ISO
                    and case_text[start:end] != alias.upper()):
                continue
            if (item["kind"] == "country" and alias == normalize(item.get("country_code"))
                    and re.fullmatch(r"[a-z]{2}", alias)
                    and case_text[start:end] not in (alias, alias.upper())):
                continue
            geo_hits.append((start, end, alias, item))
            exact_spans.add((start, end))
        normalized_aliases = tuple(phrase(alias) for alias in aliases)
        for token_match in re.finditer(r"[а-яa-z]+", text):
            token = token_match[0]
            if protected_positions.intersection(range(token_match.start(), token_match.end())):
                continue
            if len(token) < 5 or token in normalized_aliases or token in no_geo_typo:
                continue
            for alias in normalized_aliases:
                if " " not in alias and len(alias) >= 5 and edit_distance_one(token, alias):
                    geo_hits.append((token_match.start(), token_match.end(), token, item))
                    fuzzy_spans.setdefault((token_match.start(), token_match.end()), set()).add(item["key"])
                    geo_corrections.setdefault((token_match.start(), token_match.end(), item["key"]), alias)
    geo_hits = [hit for hit in geo_hits if (hit[0], hit[1], hit[3]["key"]) not in geo_corrections
        or ((hit[0], hit[1]) not in exact_spans and len(fuzzy_spans[(hit[0], hit[1])]) == 1)]
    occupied: set[int] = set()
    accepted_spans: set[tuple[int, int, str]] = set()
    countries, regions = set(), set()
    for start, end, alias, item in sorted(geo_hits, key=lambda h: (-(h[1] - h[0]), h[0])):
        positions = set(range(start, end))
        # A shorter nested alias never overrides the already chosen full name.
        # Only exactly the same span may add a genuinely ambiguous second place.
        if occupied & positions and (start, end, alias) not in accepted_spans:
            continue
        accepted_spans.add((start, end, alias))
        occupied |= positions
        corrected = geo_corrections.get((start, end, item["key"]))
        if corrected:
            corrections[alias] = corrected
        countries.add(item["country_slug"])
        if item["kind"] != "country":
            regions.add(item["key"])
    text = "".join(" " if i in occupied else ch for i, ch in enumerate(text))
    return text, frozenset(countries), frozenset(regions), corrections


def literal_identifier(raw: str, geometry: list[dict] | None = None) -> str | None:
    """Protect technical identifiers, never ordinary alphabetic compounds.

    Exact catalogue alpha codes can be supplied through literal_content. Syntax
    alone requires digits/underscores, a bounded control abbreviation suffix or
    a non-prose ISO prefix with multiple code components.
    """
    matches = tuple(_CODE_RE.finditer(normalize(raw)))
    if not matches:
        return None
    known_phrases = {phrase(alias) for aliases, _alternatives in CONCEPTS for alias in aliases}
    text = phrase(raw)
    geo_spans = [(start, end) for item in geometry or ()
        for start, end, _alias in _alias_occurrences(text, geo_aliases(item))]
    iso_codes = {normalize(item.get("country_code")) for item in geometry or () if item["kind"] == "country"}
    candidates = []
    for match in matches:
        candidate = match[0]
        if phrase(candidate) in known_phrases:
            continue
        if any(start >= geo_start and end <= geo_end
                for start, end, _alias in _alias_occurrences(text, (candidate,)) for geo_start, geo_end in geo_spans):
            continue
        prefix = candidate.split("-", 1)[0]
        technical = (bool(re.search(r"[0-9_]", candidate))
            or bool(re.search(r"-(?:avg|eop|yoy|mom|qoq|pop)(?:-(?:month|quarter|year))?$", candidate))
            or (prefix in iso_codes and prefix not in _AMBIGUOUS_ISO and candidate.count("-") >= 2))
        if technical:
            candidates.append(candidate)
    return candidates[0] if len(candidates) == 1 else None


def _unmasked_query(query: str, text: str) -> str:
    """Project token masking back to punctuation-bearing text for date syntax."""
    original = list(query)
    phrase_offset = 0
    for match in TOKEN_RE.finditer(query):
        if not text[phrase_offset:phrase_offset + len(match[0])].strip():
            original[match.start():match.end()] = " " * len(match[0])
        phrase_offset += len(match[0]) + 1
    return "".join(original)


def parse_intent(raw: str, geometry: list[dict], *, allow_layout: bool = True,
        literal_content: str | None = None) -> SearchIntent:
    query = normalize(raw)
    literal = normalize(literal_content) if literal_content else literal_identifier(raw, geometry)
    text, countries, regions, corrections = strip_geography(raw, geometry, literal_content=literal)
    if literal:
        literal_hits = tuple(_alias_occurrences(text, (literal,)))
        if literal_hits:
            literal_positions = {position for start, end, _ in literal_hits for position in range(start, end)}
            text = "".join(" " if i in literal_positions else ch for i, ch in enumerate(text))
        else:
            literal = None
    text, point_unit_terms = _extract_point_units(text)
    text, denominator_terms = _extract_denominators(text)
    # Preserve alignment with original punctuation before any role rewrite.
    period_query = _unmasked_query(query, text)
    # A complete monetary price-base span is a unit descriptor, not a second
    # observation year. Preserve its valuation/currency words and require the
    # actual native base-year facet; incomplete/unknown numeric spans survive.
    price_base_terms = []
    price_base_patterns = (
        r"\b(?P<basis>constant|chained)\s+(?P<year>[12]\d{3})\s+(?P<currency>dollars|usd|euros|eur|rubles|rub)\b",
        r"\b(?P<basis>цепных|постоянных)\s+(?P<currency>долларов|долларах|ценах)\s+(?P<year>[12]\d{3})(?:\s+года)?\b",
    )
    def price_base_replacement(match):
        price_base_terms.append(("search-price-base-" + match["year"],))
        basis = "chained prices" if match["basis"] in ("chained", "цепных") else "constant prices"
        currency = match["currency"] if match["currency"] != "ценах" else ""
        return basis + " " + currency
    for price_base_pattern in price_base_patterns:
        text = re.sub(price_base_pattern, price_base_replacement, text)
    # The year remains an observation year while a complete end-of-year phrase
    # gains independently required end-of-period mode and annual frequency.
    text = re.sub(r"\b(?:end of|end|на конец)\s+([12]\d{3})(?:\s+(?:года|year))?\b", r"end period annual \1", text)
    # Project masked tokens to the original punctuation before rewriting an age
    # span. This keeps the outside ISO date aligned while numeric age members
    # become opaque nonnumeric aliases rather than observation-period words.
    text = prepare_dimensions(text)
    base_unit = re.search(r"(?<!\d)((?:1|2)\d{3})\s*=\s*100(?!\d)", period_query)
    unit_term = None
    if base_unit:
        unit_year = base_unit[1]
        text = re.sub(r"\b" + unit_year + r"\s+100\b", " ", text)
        unit_term = (f"{unit_year}=100", f"{unit_year} 100", f"i{unit_year[-2:]}")
    denominators = {position for match in re.finditer(r"\b(?:на|per)\s+\d+\b", text)
        for position in range(match.start(), match.end())}
    year_hits = [match for match in re.finditer(r"\b(?:1\d{3}|2\d{3})\b", text)
        if not denominators.intersection(range(match.start(), match.end()))]
    years = [match[0] for match in year_hits]
    year = int(years[0]) if len(years) == 1 else None
    error = "unsupported_period" if len(years) > 1 else None
    month = None
    iso = re.search(r"(?<!\d)((?:1|2)\d{3})[-/](\d{1,2})(?!\d)", period_query)
    if iso:
        year, month = int(iso[1]), int(iso[2])
        if month < 1 or month > 12:
            error = "unsupported_period"
        text = re.sub(r"\b" + str(year) + r"\s+" + str(month).zfill(2) + r"\b", " ", text)
        text = re.sub(r"\b" + str(year) + r"\s+" + str(month) + r"\b", " ", text)
        if re.search(r"(?:1|2)\d{3}[-/]\d{1,2}[-/]\d{1,2}", period_query):
            error = "unsupported_period"
    for index, aliases in enumerate(MONTHS, 1):
        for token in tokens(text):
            if any(token == alias or (len(alias) >= 4 and token.startswith(alias)) for alias in aliases):
                if month is not None and month != index:
                    error = "unsupported_period"
                month = index
                text = re.sub(r"\b" + re.escape(token) + r"\b", " ", text)
    if month is not None and year is None:
        error = "unsupported_period"
    if years:
        for year_token in set(years):
            text = re.sub(r"\b" + year_token + r"\b", " ", text)
    # A period used as a comparison/aggregation role is not an absolute point
    # request. Longest known spans become independent mode and frequency words;
    # outside Q1/quarter/day tokens are deliberately retained by this helper.
    text = prepare_temporal_roles(text)
    # Explicit day/quarter requests are not silently reduced to a year.
    frequency_positions = {position for alternatives, matchers in CONCEPT_MATCHERS if alternatives[0].startswith("search-freq-")
        for _alias, _normalized, _parts, matcher in matchers for hit in matcher.finditer(text)
        for position in range(hit.start(), hit.end())}
    if any(not frequency_positions.intersection(range(match.start(), match.end()))
            for match in re.finditer(r"\b(?:q[1-4]|квартал|квартала|quarter|сегодня|yesterday|today)\b", text)):
        error = "unsupported_period"
    # Explicit unit tokens belong to the nonliteral input, even when a bounded
    # natural-language rewrite consumes «проценты» as rate-question wording.
    explicit_percent = "%" in _outside_literal_query(query, literal) or bool(_percent_word_spans(text))
    # Keep stop words until phrase resolution: «ВВП на душу» is one concept.
    content = phrase(prepare_vocabulary(prepare_language(text)))
    # Keep percent wording through semantic rewriting (e.g. mortgage rates),
    # then consume the exact surviving unit words. Unknown typos stay required.
    if explicit_percent:
        percent_positions = _percent_word_spans(content)
        content = "".join(" " if index in percent_positions else char for index, char in enumerate(content))
        content = phrase(content)
    term_hits, term_occupied = [], set()
    for alternatives, matchers in CONCEPT_MATCHERS:
        for _original, alias, _parts, matcher in matchers:
            for hit in matcher.finditer(content):
                term_hits.append((hit.start(), hit.end(), alias, alternatives))
    # One misspelt token in a known multiword economic phrase is recoverable;
    # unknown qualifiers outside that exact phrase remain mandatory.
    content_tokens = list(TOKEN_RE.finditer(content))
    phrase_corrections = {}
    for alternatives, matchers in CONCEPT_MATCHERS:
        if alternatives[0].startswith("search-"):
            continue
        for alias, _normalized, parts, _matcher in matchers:
            if not 2 <= len(parts) <= 5:
                continue
            for offset in range(len(content_tokens) - len(parts) + 1):
                window = content_tokens[offset:offset + len(parts)]
                mismatches = [(match[0], part) for match, part in zip(window, parts) if match[0] != part]
                if (len(mismatches) == 1 and min(map(len, mismatches[0])) >= 3
                        and not _control_neighbour(mismatches[0][0]) and edit_distance_one(*mismatches[0])):
                    start, end = window[0].start(), window[-1].end()
                    if any(hit[0] == start and hit[1] == end for hit in term_hits):
                        continue
                    term_hits.append((start, end, alias, alternatives))
                    phrase_corrections[(start, end, alias)] = mismatches[0]
    terms = ([(literal,)] if literal else []) + list(denominator_terms) + list(point_unit_terms) + list(dict.fromkeys(price_base_terms))
    if explicit_percent:
        terms.append(("search-unit-percent",))
    if unit_term:
        terms.append(unit_term)
    for start, end, alias, alternatives in sorted(term_hits, key=lambda h: (-len(h[2]), h[0])):
        positions = set(range(start, end))
        if positions & term_occupied:
            continue
        term_occupied |= positions
        if alternatives not in terms:
            terms.append(alternatives)
    residual = "".join(" " if i in term_occupied else ch for i, ch in enumerate(content))
    for token in tokens(residual):
        if token in STOP_WORDS or token in ("год", "года", "году", "year"):
            continue
        alternatives = (token,)
        typo = _concept_correction(token)
        if typo:
            corrections[token], alternatives = typo
        elif len(alternatives) == 1 and re.fullmatch(r"[а-я]{4,}(?:ами|ями)", token):
            # Retain the established instrumental-case DTO. Other productive
            # nominal forms are expanded only in matching_alternatives, keeping
            # the raw unknown word as the parser's mandatory public identity.
            alternatives = nominal_variants(token)
        terms.append(alternatives)
    corrected_query = query
    for needle, replacement in corrections.items():
        corrected_query = re.sub(r"(?<!\w)" + re.escape(needle) + r"(?!\w)", replacement, corrected_query)
    if len({term[0] for term in terms if term[0].startswith("search-freq-")}) > 1:
        error = "unsupported_query"
    if len(denominator_terms) > 1:
        error = "unsupported_query"
    result = SearchIntent(query, content, tuple(terms), frozenset(countries), frozenset(regions), year, month, error,
        corrected_query if corrected_query != query else None, literal)
    if allow_layout and not literal and not countries and not regions and not term_hits and content:
        table = _LAYOUT_RU_EN if re.search(r"[а-я]", query) else _LAYOUT_EN_RU
        candidate = normalize(query.translate(table))
        if candidate != query:
            parsed = parse_intent(candidate, geometry, allow_layout=False)
            if parsed.countries or parsed.regions or any(term in CONCEPTS_ALTERNATIVES for term in parsed.terms):
                return SearchIntent(result.query, parsed.content, parsed.terms, parsed.countries,
                    parsed.regions, parsed.year, parsed.month, parsed.error, parsed.corrected or candidate, parsed.literal)
    return result


CONCEPTS_ALTERNATIVES = frozenset(alternatives for _aliases, alternatives in CONCEPTS)


@lru_cache(maxsize=4096)
def matching_alternatives(group: tuple[str, ...], *, literal: str | None = None) -> tuple[str, ...]:
    """Expand one unresolved nominal group identically for native SQL/scoring.

    The parser retains its raw required word. Expansion never crosses groups,
    affects a typed concept or modifies an authoritative literal identifier.
    Every generated complete word remains an alternative in the same AND facet.
    """
    if len(group) != 1 or group in CONCEPTS_ALTERNATIVES or group[0] == literal:
        return group
    return nominal_variants(group[0])


def complete_nominal_alternative(source_group: tuple[str, ...], alternatives: tuple[str, ...], alternative: str) -> bool:
    """Added complete forms cannot change the original singleton prefix role.

    Previously parsed nominal OR groups still require complete words throughout.
    For an expanded raw singleton, only additional alternatives are complete
    forms: the original mandatory word keeps its established identity prefix.
    """
    return (len(alternatives) > 1 and alternatives == nominal_variants(alternatives[0])
        and (len(source_group) > 1 or alternative != source_group[0]))


@lru_cache(maxsize=4096)
def _alternative_plan(source_group: tuple[str, ...], literal: str | None):
    """Per-term data that depends on the query only, never on the scored row."""
    alternatives = matching_alternatives(source_group, literal=literal)
    plan = []
    for alternative in alternatives:
        nominal_group = complete_nominal_alternative(source_group, alternatives, alternative)
        alt = normalize(alternative)
        p = phrase(alt)
        unresolved = alternatives not in CONCEPTS_ALTERNATIVES and literal != alt
        control_neighbour = unresolved and " " not in p and _control_neighbour(p)
        bounded = re.compile(r"(?<![a-zа-я0-9])" + re.escape(p) + r"(?![a-zа-я0-9])")
        plan.append((alt, p, nominal_group, unresolved, control_neighbour, bounded))
    return tuple(plan)


def match_score(intent: SearchIntent, *, code: str = "", names: tuple[str, ...] = (), metadata: str = "") -> int | None:
    """Every content term is required; names/code outrank metadata and edits."""
    if not intent.terms:
        return 20
    code_norm, name_norms = normalize(code), tuple(normalize(n) for n in names if n)
    exact_code = intent.literal == code_norm or intent.content == code_norm or intent.query == code_norm
    exact_name = phrase(intent.literal) in tuple(phrase(n) for n in name_norms) if intent.literal else False
    exact = 1000 if exact_code else 900 if exact_name or intent.content in name_norms or intent.content in tuple(phrase(n) for n in name_norms) else 0
    hay = phrase(" ".join((code, *names, metadata)))
    hay_tokens = tokens(hay)
    identity_tokens = tokens(" ".join((code, *names)))
    score = 0
    for source_group in intent.terms:
        best = None
        for alt, p, nominal_group, unresolved, control_neighbour, bounded in _alternative_plan(source_group, intent.literal):
            if len(p) < 3 and len(intent.terms) == 1 and not intent.literal and (phrase(code).startswith(p) or any(phrase(name).startswith(p) for name in name_norms)):
                # A short autocomplete prefix is anchored to a real identity or
                # title; it never matches an interior syllable/SEO keyword.
                value = 35
            elif intent.literal == alt and len(p) >= 24 and len(p.split()) >= 4 and any(phrase(name).startswith(p) for name in name_norms):
                value = 70
            elif bounded.search(phrase(code)):
                # Whole-token identity only: sport cannot match transport.
                value = 100 if code_norm == alt else 80
            elif any(bounded.search(phrase(name)) for name in name_norms):
                value = 70
            elif not nominal_group and len(p) >= 3 and " " not in p and any(t.startswith(p) for t in identity_tokens):
                # A real title/code token is evidence for an autocomplete prefix,
                # even if that unfinished token resembles a control word. Unit
                # markers and fuzzy metadata matches do not establish identity.
                value = 15
            elif bounded.search(hay):
                value = 20
            elif not nominal_group and not control_neighbour and len(p) >= 3 and " " not in p and any(t.startswith(p) for t in hay_tokens):
                value = 15
            elif not nominal_group and not control_neighbour and len(p) >= (5 if unresolved else 4) and " " not in p and any(len(t) >= 4 and edit_distance_one(p, t) for t in hay_tokens):
                value = 5
            else:
                continue
            best = max(best or 0, value)
        if best is None:
            return None
        score += best
    # The punctuation-free title/code may be exact while an explicit unit is
    # different. Exactness never bypasses another required content/facet term.
    return max(score, exact)

"""Bounded, explainable RU/EN search intent; no network or learned claims."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

SEARCH_VERSION = "federated-v1"
TOKEN_RE = re.compile(r"[a-zа-я0-9]+")
STOP_WORDS = frozenset(("в", "во", "по", "за", "на", "из", "для", "и", "к", "the", "in", "of", "for", "and"))

# Equivalent concepts only. Minimum wage deliberately does not alias average wages.
CONCEPTS = (
    (("ввп на душу", "gdp per capita", "per capita gdp"), ("gdp-per-capita", "gdp per capita", "ввп на душу")),
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

COUNTRY_ALIASES = {
    "russia": ("россия", "россии", "россию", "рф", "russia", "russian federation"),
    "germany": ("германия", "германии", "германию", "фрг", "deutschland", "germany"),
    "united-states": ("сша", "соединенные штаты", "united states", "usa", "us", "america"),
    "united-kingdom": ("великобритания", "великобритании", "британия", "britain", "uk", "united kingdom"),
    "china": ("китай", "китая", "китае", "кнр", "china"),
    "japan": ("япония", "японии", "японию", "japan"),
    "france": ("франция", "франции", "францию", "france"),
    "india": ("индия", "индии", "индию", "india"),
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


def normalize(value: object) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).casefold().replace("ё", "е").split())


def tokens(value: object) -> tuple[str, ...]:
    return tuple(TOKEN_RE.findall(normalize(value)))


def phrase(value: object) -> str:
    return " ".join(tokens(value))


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


def _alias_occurrences(text: str, aliases: tuple[str, ...]):
    for alias in aliases:
        normalized = phrase(alias)
        if not normalized:
            continue
        for match in re.finditer(r"(?<!\w)" + re.escape(normalized) + r"(?!\w)", text):
            yield match.start(), match.end(), normalized


def geo_aliases(item: dict) -> tuple[str, ...]:
    values = [item.get("slug"), item.get("name_ru"), item.get("name_en")]
    if item["kind"] == "country":
        values.append(item.get("country_code"))
        values.extend(COUNTRY_ALIASES.get(item["slug"], ()))
    else:
        values.extend(REGION_ALIASES.get(item["slug"], ()))
    # Predictable inflection for catalogue nouns, only for the actual entity.
    ru = phrase(item.get("name_ru"))
    if ru.endswith("ия"):
        values.append(ru[:-1] + "и")
    if ru.endswith("а") and " " not in ru:
        values.append(ru[:-1] + "ы")
        values.append(ru[:-1] + "е")
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


def parse_intent(raw: str, geometry: list[dict], *, allow_layout: bool = True) -> SearchIntent:
    query = normalize(raw)
    text = phrase(query)
    geo_hits = []
    geo_corrections, corrections = {}, {}
    for item in geometry:
        for start, end, alias in _alias_occurrences(text, geo_aliases(item)):
            geo_hits.append((start, end, alias, item))
        for token_match in re.finditer(r"[а-яa-z]+", text):
            token = token_match[0]
            if len(token) < 5:
                continue
            aliases = tuple(phrase(alias) for alias in geo_aliases(item))
            if token in aliases:
                # A recognized case/inflection is valid, not a nearby alias
                # spelling that should be corrected to the dictionary form.
                continue
            for alias in aliases:
                alias = phrase(alias)
                if " " not in alias and len(alias) >= 5 and token != alias and edit_distance_one(token, alias):
                    geo_hits.append((token_match.start(), token_match.end(), token, item))
                    geo_corrections.setdefault((token_match.start(), token_match.end(), item["key"]), alias)
    occupied: set[int] = set()
    countries, regions = set(), set()
    for start, end, alias, item in sorted(geo_hits, key=lambda h: (-len(h[2]), h[0])):
        positions = set(range(start, end))
        if occupied & positions:
            # Identical aliases can denote multiple regions; keep ambiguity.
            if not all(i in occupied for i in positions):
                continue
            same = [h for h in geo_hits if h[:3] == (start, end, alias)]
            if len({h[3]["key"] for h in same}) == 1:
                continue
        occupied |= positions
        corrected = geo_corrections.get((start, end, item["key"]))
        if corrected:
            corrections[alias] = corrected
        countries.add(item["country_slug"])
        if item["kind"] != "country":
            regions.add(item["key"])
    text = "".join(" " if i in occupied else ch for i, ch in enumerate(text))
    base_unit = re.search(r"(?<!\d)((?:1|2)\d{3})\s*=\s*100(?!\d)", query)
    unit_term = None
    if base_unit:
        unit_year = base_unit[1]
        text = re.sub(r"\b" + unit_year + r"\s+100\b", " ", text)
        unit_term = (f"{unit_year}=100", f"{unit_year} 100", f"i{unit_year[-2:]}")
    years = re.findall(r"(?<!\d)(?:1\d{3}|2\d{3})(?!\d)", text)
    year = int(years[0]) if len(years) == 1 else None
    error = "unsupported_period" if len(years) > 1 else None
    month = None
    iso = re.search(r"(?<!\d)((?:1|2)\d{3})[-/](\d{1,2})(?!\d)", query)
    if iso:
        year, month = int(iso[1]), int(iso[2])
        if month < 1 or month > 12:
            error = "unsupported_period"
        text = re.sub(r"\b" + str(year) + r"\s+" + str(month).zfill(2) + r"\b", " ", text)
        text = re.sub(r"\b" + str(year) + r"\s+" + str(month) + r"\b", " ", text)
        if re.search(r"(?:1|2)\d{3}[-/]\d{1,2}[-/]\d{1,2}", query):
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
        text = re.sub(r"\b(?:1\d{3}|2\d{3})\b", " ", text)
    # Explicit day/quarter requests are not silently reduced to a year.
    if re.search(r"\b(?:q[1-4]|квартал|квартала|quarter|сегодня|yesterday|today)\b", text):
        error = "unsupported_period"
    # Keep stop words until phrase resolution: «ВВП на душу» is one concept.
    content = " ".join(tokens(text))
    term_hits, term_occupied = [], set()
    for aliases, alternatives in CONCEPTS:
        for start, end, alias in _alias_occurrences(content, aliases):
            term_hits.append((start, end, alias, alternatives))
    terms = []
    if "%" in query:
        terms.append(("search-unit-percent",))
    if unit_term:
        terms.append(unit_term)
    for start, end, alias, alternatives in sorted(term_hits, key=lambda h: (-len(h[2]), h[0])):
        positions = set(range(start, end))
        if positions & term_occupied:
            continue
        term_occupied |= positions
        terms.append(alternatives)
    residual = "".join(" " if i in term_occupied else ch for i, ch in enumerate(content))
    for token in tokens(residual):
        if token in STOP_WORDS or token in ("год", "года", "году", "year"):
            continue
        alternatives = (token,)
        if len(token) >= 4 or (not allow_layout and len(token) == 3):
            typo = next(((alias, alts) for aliases, alts in CONCEPTS for alias in aliases
                if " " not in alias and len(alias) >= (4 if allow_layout else 3) and edit_distance_one(token, alias)), None)
            if typo:
                corrections[token], alternatives = typo
        terms.append(alternatives)
    corrected_query = query
    for needle, replacement in corrections.items():
        corrected_query = re.sub(r"(?<!\w)" + re.escape(needle) + r"(?!\w)", replacement, corrected_query)
    if len({term[0] for term in terms if term[0].startswith("search-freq-")}) > 1:
        error = "unsupported_query"
    result = SearchIntent(query, content, tuple(terms), frozenset(countries), frozenset(regions), year, month, error,
        corrected_query if corrected_query != query else None)
    if allow_layout and not countries and not regions and not term_hits and content:
        table = _LAYOUT_RU_EN if re.search(r"[а-я]", query) else _LAYOUT_EN_RU
        candidate = normalize(query.translate(table))
        if candidate != query:
            parsed = parse_intent(candidate, geometry, allow_layout=False)
            if parsed.countries or parsed.regions or any(term in CONCEPTS_ALTERNATIVES for term in parsed.terms):
                return SearchIntent(result.query, parsed.content, parsed.terms, parsed.countries,
                    parsed.regions, parsed.year, parsed.month, parsed.error, parsed.corrected or candidate)
    return result


CONCEPTS_ALTERNATIVES = frozenset(alternatives for _aliases, alternatives in CONCEPTS)


def match_score(intent: SearchIntent, *, code: str = "", names: tuple[str, ...] = (), metadata: str = "") -> int | None:
    """Every content term is required; names/code outrank metadata and edits."""
    if not intent.terms:
        return 20
    code_norm, name_norms = normalize(code), tuple(normalize(n) for n in names if n)
    exact = 1000 if intent.content == code_norm or intent.query == code_norm else 900 if intent.content in name_norms or intent.content in tuple(phrase(n) for n in name_norms) else 0
    hay = phrase(" ".join((code, *names, metadata)))
    hay_tokens = tokens(hay)
    score = 0
    for alternatives in intent.terms:
        best = None
        for alternative in alternatives:
            alt = normalize(alternative)
            p = phrase(alt)
            if p in phrase(code):
                # CPI inside REER37CPI is metadata-like, not a CPI identity.
                bounded = re.search(r"(?<![a-zа-я0-9])" + re.escape(p) + r"(?![a-zа-я0-9])", phrase(code))
                value = 100 if code_norm == alt else 80 if bounded else 20
            elif any(p in phrase(name) for name in name_norms):
                value = 70
            elif p in hay:
                value = 20
            elif len(p) >= 3 and " " not in p and any(t.startswith(p) for t in hay_tokens):
                value = 15
            elif len(p) >= 4 and " " not in p and any(len(t) >= 4 and edit_distance_one(p, t) for t in hay_tokens):
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

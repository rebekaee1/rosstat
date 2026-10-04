"""Shared explicit quantity facets: actual native units, not title keywords."""
from __future__ import annotations

import re
from functools import lru_cache

# Controlled regex grammar also has a faithful SQLite implementation. A unit
# qualifier stays mandatory and cannot be satisfied by a similarly named topic.
UNIT_RULES = {
    "money": r"rub|руб|usd|dollar|доллар|eur|евро|cad|aud|gbp|jpy|yen|иен|йен|cny|юан|nac|national currency|национальн.*валют",
    "million": r"million|млн|миллион|mio|mn|mmbtu",
    "billion": r"billion|млрд|миллиард|bn",
    "thousand": r"thousand|thous|тыс|тысяч|ths",
    "rub": r"rub|rur|руб",
    "usd": r"usd|us dollar|доллар сша",
    "cad": r"cad|canadian dollar|канадск.*доллар",
    "aud": r"aud|australian dollar|австралийск.*доллар",
    "gbp": r"gbp|pound sterling|pounds sterling|фунт.*стерлинг",
    "cny": r"cny|yuan|юан",
    "jpy": r"jpy|yen|йен|иен",
    "eur": r"eur|евро",
    "persons": r"person|people|inhabit|чел|mio_per|ths_per|тысяч.*населен",
    "index": r"index|индекс|=100|= 100|i15|i10|i20|i05",
    "percentage-point": r"pc_pnt|percentage point|percent point|процентных пункт|процентные пункт",
    "litre": r"litre|liter|литр",
    "tonne": r"tonne|tons|тонн|ths_t",
    "kilogram": r"kilogram|кг|kg|килограмм",
    "square-metre": r"square metr|square met|sq.*m|кв.*м|квадратн.*метр",
    "chained-prices": r"chained|цепн",
    "btu": r"btu|бте",
    "cubic-metre": r"cubic met|куб.*м|m3|м3|m³|м³",
    "solid-cubic-metre": r"solid cubic met|плотн.*куб",
}
UNIT_EXCLUDES = {"square-metre": r"kilomet|km|mile|километр",
    "cubic-metre": r"kilomet|km3|km³|км3|км³|километр"}
UNIT_CONCEPTS = (
    (("percentage points", "percentage point", "percent points", "percent point", "процентных пунктах", "процентные пункты", "процентных пунктов", "процентных пункта", "процентный пункт", "п.п."), ("search-unit-percentage-point",)),
    (("стоимость", "в денежном выражении", "monetary value"), ("search-unit-money",)),
    (("million", "millions", "млн", "миллионов", "миллион", "миллиона", "миллионах"), ("search-unit-million",)),
    (("billion", "billions", "млрд", "миллиард", "миллиардов", "миллиарда"), ("search-unit-billion",)),
    (("thousand", "thousands", "thous", "тыс", "тысяч", "тысячи"), ("search-unit-thousand",)),
    (("rubles", "ruble", "roubles", "rouble", "rub", "рублей", "рублях", "рубли", "руб", "рубля"), ("search-unit-rub",)),
    (("usd", "us dollar", "us dollars", "доллар сша", "доллары сша", "долларов сша", "долларе сша", "долларах сша", "долларам сша", "долларами сша", "доллару сша", "долларом сша", "долларов", "долларах", "долларами", "dollars"), ("search-unit-usd",)),
    (("cad", "canadian dollar", "canadian dollars", "канадский доллар", "канадские доллары", "канадских долларов"), ("search-unit-cad",)),
    (("aud", "australian dollar", "australian dollars", "австралийский доллар", "австралийские доллары", "австралийских долларов"), ("search-unit-aud",)),
    (("gbp", "pound sterling", "pounds sterling", "british pound", "british pounds", "фунт стерлингов", "фунты стерлингов", "фунтов стерлингов"), ("search-unit-gbp",)),
    (("cny", "yuan", "chinese yuan", "китайские юани", "юань", "юани", "юаней", "юанях"), ("search-unit-cny",)),
    (("jpy", "yen", "japanese yen", "японские иены", "японских иен", "иены", "иен", "йены", "йен"), ("search-unit-jpy",)),
    (("eur", "евро", "euro", "euros"), ("search-unit-eur",)),
    (("persons", "number of people", "number of persons", "in people", "in persons", "число человек", "в людях", "в человеках"), ("search-unit-persons",)),
    (("index units", "в единицах индекса", "индексных пунктах", "индексные пункты"), ("search-unit-index",)),
    (("chained prices", "цепных ценах", "цепные цены"), ("search-unit-chained-prices",)),
    (("btu", "бте", "british thermal units", "британских тепловых единиц"), ("search-unit-btu",)),
    (("cubic metre", "cubic meter", "cubic metres", "cubic meters", "кубических метров", "кубометров", "куб м", "m3", "м3"), ("search-unit-cubic-metre",)),
    (("solid cubic metre", "solid cubic meter", "solid cubic metres", "solid cubic meters", "плотных кубических метров"), ("search-unit-solid-cubic-metre",)),
    (("square metre", "square meter", "square metres", "square meters", "квадратный метр", "квадратных метров", "кв м"), ("search-unit-square-metre",)),
    (("per litre", "per liter", "per litres", "per liters", "за литр", "за один литр", "на литр", "litre", "litres", "liter", "liters", "литр", "литров", "литра", "литре"), ("search-unit-litre",)),
    (("per tonne", "per ton", "per tonnes", "per tons", "за тонну", "на тонну", "tonne", "tonnes", "tons", "тонн", "тонны", "тонна"), ("search-unit-tonne",)),
    (("per kilogram", "per kilograms", "за килограмм", "на килограмм", "kilogram", "kilograms", "kg", "кг", "килограммов", "килограмм", "килограммы"), ("search-unit-kilogram",)),
)

# Denominators describe the measure, not the native scale of its numerator.
# Both title guards and metadata matching use these exact controlled patterns.
DENOMINATOR_RULES = {
    f"search-denominator-{number}-persons": "|".join(
        f"{prefix} {value} {noun}" for value in (str(number), f"{number:,}", f"{number:,}".replace(",", " "))
        for prefix, nouns in (("per", ("person", "people", "population", "inhabitant", "resident")),
            ("на", ("человек", "чел", "жител", "населен"))) for noun in nouns
    ) for number in (1000, 10000, 100000)
}
DENOMINATOR_RULES["search-denominator-1000-persons"] += (
    "|birth rate.*‰|death rate.*‰|коэффициент рождаемости.*‰|коэффициент смертности.*‰"
)

# Only native price-basis monetary units establish these dynamic base-year
# facets. Fixed separator normalization and plain patterns have SQL parity.
PRICE_BASE_UNIT_SEPARATORS = "-–—(),./:;=[]\t\n\r\v\f\u00a0\u202f"
PRICE_BASE_VALUATIONS = ("constant", "chained", "постоянн", "цепн")
PRICE_BASE_CURRENCIES = ("dollar", "доллар", "usd", "eur", "евро", "rub", "руб", "gbp", "pound", "фунт", "nac")


def price_base_unit_pattern(year: int) -> str:
    """Return one SQLite-compatible native-unit pattern with a whole year token."""
    if not 1000 <= year <= 2999:
        raise ValueError("unsupported native price-base year")
    return "|".join(f"{valuation}.* {year} .*{currency}|{valuation}.*{currency}.* {year} |{currency}.*{valuation}.* {year} "
        for valuation in PRICE_BASE_VALUATIONS for currency in PRICE_BASE_CURRENCIES)


def price_base_years(*units: str | None) -> tuple[int, ...]:
    """Read base years only from complete declared native monetary-unit labels."""
    separator_table = str.maketrans({char: " " for char in PRICE_BASE_UNIT_SEPARATORS})
    years = set()
    for unit in units:
        text = " " + " ".join((unit or "").casefold().replace("ё", "е").translate(separator_table).split()) + " "
        for year in map(int, re.findall(r"(?<!\S)([12]\d{3})(?!\S)", text)):
            if re.search(price_base_unit_pattern(year), text):
                years.add(year)
    return tuple(sorted(years))


@lru_cache(maxsize=65536)
def unit_metadata(*units: str | None, native_currency: str | None = None) -> str:
    """Encode only facets supported by native stored/translatable unit labels."""
    text = " ".join(unit or "" for unit in units).casefold().replace("ё", "е")
    facets = {"search-unit-" + key for key, pattern in UNIT_RULES.items()
        if re.search(pattern, text) and not (key in UNIT_EXCLUDES and re.search(UNIT_EXCLUDES[key], text))}
    facets.update(f"search-price-base-{year}" for year in price_base_years(*units))
    # Canonical valuation descriptors let scoring read a verified native unit
    # such as constant-2017-dollars without requiring adjacent title words.
    # Reuse the same scoped identity/exclusion rules as Python and SQL guards.
    from app.services.search_language import measure_matches
    for valuation in ("current-prices", "constant-prices"):
        if measure_matches(((valuation,),), code="", names=(), unit_names=units):
            facets.add(valuation)
    if "п.п." in text:
        facets.add("search-unit-percentage-point")
    for key, symbols in (("litre", ("l", "л")), ("tonne", ("t", "т"))):
        if any((compact := re.sub(r"\s+", "", (unit or "").casefold())) in symbols or re.search(
            r"/(?:" + "|".join(symbols) + r")(?:\W|$)", compact
        ) for unit in units):
            facets.add("search-unit-" + key)
    # The US BEA state catalogue declares its currency through country_code.
    # Generic native dollar wording is USD only with this producer identity;
    # titles and unknown/non-US countries never establish a currency.
    currencies = {"usd", "cad", "aud", "gbp", "cny", "jpy", "eur", "rub"}
    if native_currency == "USD" and re.search(r"dollar|долл", text) and not any(
        "search-unit-" + code in facets for code in currencies - {"usd"}
    ):
        facets.add("search-unit-usd")
    return " ".join(sorted(facets))


@lru_cache(maxsize=65536)
def denominator_metadata(*labels: str | None) -> str:
    """Only actual title/unit wording establishes a population denominator."""
    text = " ".join(" ".join(label or "" for label in labels).casefold().replace("ё", "е").replace("-", " ").split())
    return " ".join(key for key, pattern in DENOMINATOR_RULES.items() if re.search(pattern, text))

"""Канонический реестр субъектов РФ для регионального блока.

Единственный источник истины «имя строки Росстата -> регион».
85 субъектов + РФ + 8 федеральных округов + 2 статистических остатка
(«без автономных округов»). Slug'и — детерминированный translit, руками
зафиксированы для городов и сложных имён.

Используется и host-парсером (scripts/regional/parse_pril_2025.py),
и backend-сидером (backend/seed_regional.py) — файл копируется в
backend/app/data/regional/ при сборке артефакта.
"""

# kind: country | district | region | remainder
REGIONS = [
    # --- Российская Федерация ---
    {"slug": "russia", "name": "Российская Федерация", "kind": "country", "district": None},
    # --- Федеральные округа ---
    {"slug": "cfo", "name": "Центральный федеральный округ", "kind": "district", "district": None},
    {"slug": "szfo", "name": "Северо-Западный федеральный округ", "kind": "district", "district": None},
    {"slug": "ufo-south", "name": "Южный федеральный округ", "kind": "district", "district": None},
    {"slug": "skfo", "name": "Северо-Кавказский федеральный округ", "kind": "district", "district": None},
    {"slug": "pfo", "name": "Приволжский федеральный округ", "kind": "district", "district": None},
    {"slug": "urfo", "name": "Уральский федеральный округ", "kind": "district", "district": None},
    {"slug": "sfo", "name": "Сибирский федеральный округ", "kind": "district", "district": None},
    {"slug": "dfo", "name": "Дальневосточный федеральный округ", "kind": "district", "district": None},
    # --- Центральный ФО ---
    {"slug": "belgorodskaya-oblast", "name": "Белгородская область", "kind": "region", "district": "cfo"},
    {"slug": "bryanskaya-oblast", "name": "Брянская область", "kind": "region", "district": "cfo"},
    {"slug": "vladimirskaya-oblast", "name": "Владимирская область", "kind": "region", "district": "cfo"},
    {"slug": "voronezhskaya-oblast", "name": "Воронежская область", "kind": "region", "district": "cfo"},
    {"slug": "ivanovskaya-oblast", "name": "Ивановская область", "kind": "region", "district": "cfo"},
    {"slug": "kaluzhskaya-oblast", "name": "Калужская область", "kind": "region", "district": "cfo"},
    {"slug": "kostromskaya-oblast", "name": "Костромская область", "kind": "region", "district": "cfo"},
    {"slug": "kurskaya-oblast", "name": "Курская область", "kind": "region", "district": "cfo"},
    {"slug": "lipetskaya-oblast", "name": "Липецкая область", "kind": "region", "district": "cfo"},
    {"slug": "moskovskaya-oblast", "name": "Московская область", "kind": "region", "district": "cfo"},
    {"slug": "orlovskaya-oblast", "name": "Орловская область", "kind": "region", "district": "cfo"},
    {"slug": "ryazanskaya-oblast", "name": "Рязанская область", "kind": "region", "district": "cfo"},
    {"slug": "smolenskaya-oblast", "name": "Смоленская область", "kind": "region", "district": "cfo"},
    {"slug": "tambovskaya-oblast", "name": "Тамбовская область", "kind": "region", "district": "cfo"},
    {"slug": "tverskaya-oblast", "name": "Тверская область", "kind": "region", "district": "cfo"},
    {"slug": "tulskaya-oblast", "name": "Тульская область", "kind": "region", "district": "cfo"},
    {"slug": "yaroslavskaya-oblast", "name": "Ярославская область", "kind": "region", "district": "cfo"},
    {"slug": "moskva", "name": "г. Москва", "kind": "region", "district": "cfo"},
    # --- Северо-Западный ФО ---
    {"slug": "respublika-kareliya", "name": "Республика Карелия", "kind": "region", "district": "szfo"},
    {"slug": "respublika-komi", "name": "Республика Коми", "kind": "region", "district": "szfo"},
    {"slug": "arhangelskaya-oblast", "name": "Архангельская область", "kind": "region", "district": "szfo"},
    {"slug": "nenetskiy-ao", "name": "Ненецкий автономный округ", "kind": "region", "district": "szfo"},
    {"slug": "vologodskaya-oblast", "name": "Вологодская область", "kind": "region", "district": "szfo"},
    {"slug": "kaliningradskaya-oblast", "name": "Калининградская область", "kind": "region", "district": "szfo"},
    {"slug": "leningradskaya-oblast", "name": "Ленинградская область", "kind": "region", "district": "szfo"},
    {"slug": "murmanskaya-oblast", "name": "Мурманская область", "kind": "region", "district": "szfo"},
    {"slug": "novgorodskaya-oblast", "name": "Новгородская область", "kind": "region", "district": "szfo"},
    {"slug": "pskovskaya-oblast", "name": "Псковская область", "kind": "region", "district": "szfo"},
    {"slug": "sankt-peterburg", "name": "г. Санкт-Петербург", "kind": "region", "district": "szfo"},
    # --- Южный ФО ---
    {"slug": "respublika-adygeya", "name": "Республика Адыгея", "kind": "region", "district": "ufo-south"},
    {"slug": "respublika-kalmykiya", "name": "Республика Калмыкия", "kind": "region", "district": "ufo-south"},
    {"slug": "respublika-krym", "name": "Республика Крым", "kind": "region", "district": "ufo-south"},
    {"slug": "krasnodarskiy-kray", "name": "Краснодарский край", "kind": "region", "district": "ufo-south"},
    {"slug": "astrahanskaya-oblast", "name": "Астраханская область", "kind": "region", "district": "ufo-south"},
    {"slug": "volgogradskaya-oblast", "name": "Волгоградская область", "kind": "region", "district": "ufo-south"},
    {"slug": "rostovskaya-oblast", "name": "Ростовская область", "kind": "region", "district": "ufo-south"},
    {"slug": "sevastopol", "name": "г. Севастополь", "kind": "region", "district": "ufo-south"},
    # --- Северо-Кавказский ФО ---
    {"slug": "respublika-dagestan", "name": "Республика Дагестан", "kind": "region", "district": "skfo"},
    {"slug": "respublika-ingushetiya", "name": "Республика Ингушетия", "kind": "region", "district": "skfo"},
    {"slug": "kabardino-balkarskaya-respublika", "name": "Кабардино-Балкарская Республика", "kind": "region", "district": "skfo"},
    {"slug": "karachaevo-cherkesskaya-respublika", "name": "Карачаево-Черкесская Республика", "kind": "region", "district": "skfo"},
    {"slug": "respublika-severnaya-osetiya", "name": "Республика Северная Осетия — Алания", "kind": "region", "district": "skfo"},
    {"slug": "chechenskaya-respublika", "name": "Чеченская Республика", "kind": "region", "district": "skfo"},
    {"slug": "stavropolskiy-kray", "name": "Ставропольский край", "kind": "region", "district": "skfo"},
    # --- Приволжский ФО ---
    {"slug": "respublika-bashkortostan", "name": "Республика Башкортостан", "kind": "region", "district": "pfo"},
    {"slug": "respublika-mariy-el", "name": "Республика Марий Эл", "kind": "region", "district": "pfo"},
    {"slug": "respublika-mordoviya", "name": "Республика Мордовия", "kind": "region", "district": "pfo"},
    {"slug": "respublika-tatarstan", "name": "Республика Татарстан", "kind": "region", "district": "pfo"},
    {"slug": "udmurtskaya-respublika", "name": "Удмуртская Республика", "kind": "region", "district": "pfo"},
    {"slug": "chuvashskaya-respublika", "name": "Чувашская Республика", "kind": "region", "district": "pfo"},
    {"slug": "permskiy-kray", "name": "Пермский край", "kind": "region", "district": "pfo"},
    {"slug": "kirovskaya-oblast", "name": "Кировская область", "kind": "region", "district": "pfo"},
    {"slug": "nizhegorodskaya-oblast", "name": "Нижегородская область", "kind": "region", "district": "pfo"},
    {"slug": "orenburgskaya-oblast", "name": "Оренбургская область", "kind": "region", "district": "pfo"},
    {"slug": "penzenskaya-oblast", "name": "Пензенская область", "kind": "region", "district": "pfo"},
    {"slug": "samarskaya-oblast", "name": "Самарская область", "kind": "region", "district": "pfo"},
    {"slug": "saratovskaya-oblast", "name": "Саратовская область", "kind": "region", "district": "pfo"},
    {"slug": "ulyanovskaya-oblast", "name": "Ульяновская область", "kind": "region", "district": "pfo"},
    # --- Уральский ФО ---
    {"slug": "kurganskaya-oblast", "name": "Курганская область", "kind": "region", "district": "urfo"},
    {"slug": "sverdlovskaya-oblast", "name": "Свердловская область", "kind": "region", "district": "urfo"},
    {"slug": "tyumenskaya-oblast", "name": "Тюменская область", "kind": "region", "district": "urfo"},
    {"slug": "hanty-mansiyskiy-ao", "name": "Ханты-Мансийский автономный округ — Югра", "kind": "region", "district": "urfo"},
    {"slug": "yamalo-nenetskiy-ao", "name": "Ямало-Ненецкий автономный округ", "kind": "region", "district": "urfo"},
    {"slug": "chelyabinskaya-oblast", "name": "Челябинская область", "kind": "region", "district": "urfo"},
    # --- Сибирский ФО ---
    {"slug": "respublika-altay", "name": "Республика Алтай", "kind": "region", "district": "sfo"},
    {"slug": "respublika-tyva", "name": "Республика Тыва", "kind": "region", "district": "sfo"},
    {"slug": "respublika-hakasiya", "name": "Республика Хакасия", "kind": "region", "district": "sfo"},
    {"slug": "altayskiy-kray", "name": "Алтайский край", "kind": "region", "district": "sfo"},
    {"slug": "krasnoyarskiy-kray", "name": "Красноярский край", "kind": "region", "district": "sfo"},
    {"slug": "irkutskaya-oblast", "name": "Иркутская область", "kind": "region", "district": "sfo"},
    {"slug": "kemerovskaya-oblast", "name": "Кемеровская область — Кузбасс", "kind": "region", "district": "sfo"},
    {"slug": "novosibirskaya-oblast", "name": "Новосибирская область", "kind": "region", "district": "sfo"},
    {"slug": "omskaya-oblast", "name": "Омская область", "kind": "region", "district": "sfo"},
    {"slug": "tomskaya-oblast", "name": "Томская область", "kind": "region", "district": "sfo"},
    # --- Дальневосточный ФО ---
    {"slug": "respublika-buryatiya", "name": "Республика Бурятия", "kind": "region", "district": "dfo"},
    {"slug": "respublika-saha", "name": "Республика Саха (Якутия)", "kind": "region", "district": "dfo"},
    {"slug": "zabaykalskiy-kray", "name": "Забайкальский край", "kind": "region", "district": "dfo"},
    {"slug": "kamchatskiy-kray", "name": "Камчатский край", "kind": "region", "district": "dfo"},
    {"slug": "primorskiy-kray", "name": "Приморский край", "kind": "region", "district": "dfo"},
    {"slug": "habarovskiy-kray", "name": "Хабаровский край", "kind": "region", "district": "dfo"},
    {"slug": "amurskaya-oblast", "name": "Амурская область", "kind": "region", "district": "dfo"},
    {"slug": "magadanskaya-oblast", "name": "Магаданская область", "kind": "region", "district": "dfo"},
    {"slug": "sahalinskaya-oblast", "name": "Сахалинская область", "kind": "region", "district": "dfo"},
    {"slug": "evreyskaya-ao", "name": "Еврейская автономная область", "kind": "region", "district": "dfo"},
    {"slug": "chukotskiy-ao", "name": "Чукотский автономный округ", "kind": "region", "district": "dfo"},
    # --- Статистические остатки ---
    {"slug": "arhangelskaya-oblast-bez-ao", "name": "Архангельская область (без автономного округа)", "kind": "remainder", "district": "szfo"},
    {"slug": "tyumenskaya-oblast-bez-ao", "name": "Тюменская область (без автономных округов)", "kind": "remainder", "district": "urfo"},
]

# Алиасы: нормализованное имя строки Росстата -> slug.
# Нормализация (см. normalize_row_name): схлопнуть пробелы, убрать сноски,
# унифицировать дефисы/тире, кириллизовать латинские двойники.
ALIASES = {
    "российская федерация": "russia",
    "центральный федеральный округ": "cfo",
    "северо-западный федеральный округ": "szfo",
    "южный федеральный округ": "ufo-south",
    "северо-кавказский федеральный округ": "skfo",
    "приволжский федеральный округ": "pfo",
    "уральский федеральный округ": "urfo",
    "сибирский федеральный округ": "sfo",
    "дальневосточный федеральный округ": "dfo",
    "белгородская область": "belgorodskaya-oblast",
    "брянская область": "bryanskaya-oblast",
    "владимирская область": "vladimirskaya-oblast",
    "воронежская область": "voronezhskaya-oblast",
    "ивановская область": "ivanovskaya-oblast",
    "калужская область": "kaluzhskaya-oblast",
    "костромская область": "kostromskaya-oblast",
    "курская область": "kurskaya-oblast",
    "липецкая область": "lipetskaya-oblast",
    "московская область": "moskovskaya-oblast",
    "орловская область": "orlovskaya-oblast",
    "рязанская область": "ryazanskaya-oblast",
    "смоленская область": "smolenskaya-oblast",
    "тамбовская область": "tambovskaya-oblast",
    "тверская область": "tverskaya-oblast",
    "тульская область": "tulskaya-oblast",
    "ярославская область": "yaroslavskaya-oblast",
    "г. москва": "moskva",
    "г.москва": "moskva",
    "москва": "moskva",
    "республика карелия": "respublika-kareliya",
    "республика коми": "respublika-komi",
    "архангельская область": "arhangelskaya-oblast",
    "ненецкий автономный округ": "nenetskiy-ao",
    "вологодская область": "vologodskaya-oblast",
    "калининградская область": "kaliningradskaya-oblast",
    "ленинградская область": "leningradskaya-oblast",
    "мурманская область": "murmanskaya-oblast",
    "новгородская область": "novgorodskaya-oblast",
    "псковская область": "pskovskaya-oblast",
    "г. санкт-петербург": "sankt-peterburg",
    "г.санкт-петербург": "sankt-peterburg",
    "санкт-петербург": "sankt-peterburg",
    "республика адыгея": "respublika-adygeya",
    "республика калмыкия": "respublika-kalmykiya",
    "республика крым": "respublika-krym",
    "краснодарский край": "krasnodarskiy-kray",
    "астраханская область": "astrahanskaya-oblast",
    "волгоградская область": "volgogradskaya-oblast",
    "ростовская область": "rostovskaya-oblast",
    "г. севастополь": "sevastopol",
    "г.севастополь": "sevastopol",
    "севастополь": "sevastopol",
    "республика дагестан": "respublika-dagestan",
    "республика ингушетия": "respublika-ingushetiya",
    "кабардино-балкарская республика": "kabardino-balkarskaya-respublika",
    "карачаево-черкесская республика": "karachaevo-cherkesskaya-respublika",
    "республика северная осетия-алания": "respublika-severnaya-osetiya",
    "чеченская республика": "chechenskaya-respublika",
    "ставропольский край": "stavropolskiy-kray",
    "республика башкортостан": "respublika-bashkortostan",
    "республика марий эл": "respublika-mariy-el",
    "республика мордовия": "respublika-mordoviya",
    "республика татарстан": "respublika-tatarstan",
    "удмуртская республика": "udmurtskaya-respublika",
    "чувашская республика": "chuvashskaya-respublika",
    "пермский край": "permskiy-kray",
    # редакции до 2005: Пермская область включала Коми-Пермяцкий АО (итог
    # сопоставим с Пермским краем)
    "пермская область": "permskiy-kray",
    "кировская область": "kirovskaya-oblast",
    "нижегородская область": "nizhegorodskaya-oblast",
    "оренбургская область": "orenburgskaya-oblast",
    "пензенская область": "penzenskaya-oblast",
    "самарская область": "samarskaya-oblast",
    "саратовская область": "saratovskaya-oblast",
    "ульяновская область": "ulyanovskaya-oblast",
    "курганская область": "kurganskaya-oblast",
    "свердловская область": "sverdlovskaya-oblast",
    "тюменская область": "tyumenskaya-oblast",
    "ханты-мансийский автономный округ-югра": "hanty-mansiyskiy-ao",
    "ханты-мансийский автономный округ": "hanty-mansiyskiy-ao",
    "ямало-ненецкий автономный округ": "yamalo-nenetskiy-ao",
    "челябинская область": "chelyabinskaya-oblast",
    "республика алтай": "respublika-altay",
    "республика тыва": "respublika-tyva",
    "республика хакасия": "respublika-hakasiya",
    "алтайский край": "altayskiy-kray",
    "красноярский край": "krasnoyarskiy-kray",
    "иркутская область": "irkutskaya-oblast",
    "кемеровская область": "kemerovskaya-oblast",
    "кемеровская область-кузбасс": "kemerovskaya-oblast",
    "новосибирская область": "novosibirskaya-oblast",
    "омская область": "omskaya-oblast",
    "томская область": "tomskaya-oblast",
    "республика бурятия": "respublika-buryatiya",
    "республика саха (якутия)": "respublika-saha",
    "забайкальский край": "zabaykalskiy-kray",
    # редакции до 2008: Читинская область включала Агинский Бурятский АО
    "читинская область": "zabaykalskiy-kray",
    "камчатский край": "kamchatskiy-kray",
    "приморский край": "primorskiy-kray",
    "хабаровский край": "habarovskiy-kray",
    "амурская область": "amurskaya-oblast",
    "магаданская область": "magadanskaya-oblast",
    "сахалинская область": "sahalinskaya-oblast",
    "еврейская автономная область": "evreyskaya-ao",
    "чукотский автономный округ": "chukotskiy-ao",
    "архангельская область без автономного округа": "arhangelskaya-oblast-bez-ao",
    "архангельская область без ао": "arhangelskaya-oblast-bez-ao",
    "тюменская область без автономных округов": "tyumenskaya-oblast-bez-ao",
    "тюменская область без ао": "tyumenskaya-oblast-bez-ao",
    # Опечатки и артефакты источника (реально встречаются в Excel-приложении 2025)
    "владимировская область": "vladimirskaya-oblast",
    "ханты мансийский автономный округ-югра": "hanty-mansiyskiy-ao",
    "ханты-мансийский автономный": "hanty-mansiyskiy-ao",
    "ямало-ненецкий автономный округ-югра": "yamalo-nenetskiy-ao",
    "г. санкт петербург": "sankt-peterburg",
    "республика саха(якутия)": "respublika-saha",
    "республтка адыгея": "respublika-adygeya",
    "еврейская автономная": "evreyskaya-ao",
    "тюменская область без автономного округа": "tyumenskaya-oblast-bez-ao",
    "камчатская область": "kamchatskiy-kray",  # имя до 2007 г.
}

# Латинские двойники кириллицы, встречающиеся в исходниках Росстата
_LATIN_TO_CYR = str.maketrans({
    "a": "а", "c": "с", "e": "е", "o": "о", "p": "р", "x": "х", "y": "у",
    "A": "А", "B": "В", "C": "С", "E": "Е", "H": "Н", "K": "К", "M": "М",
    "O": "О", "P": "Р", "T": "Т", "X": "Х",
})

import re as _re


_SUPERSCRIPTS = str.maketrans("", "", "⁰¹²³⁴⁵⁶⁷⁸⁹⁾⁽")

# Суффикс единицы в имени строки РФ («Российская Федерация, млрд руб.») —
# значение строки в 1000 раз крупнее, чем у регионов (млрд↔млн, млн↔тыс).
_UNIT_SUFFIX_RE = _re.compile(r",\s*(млрд\s*руб|млн\s*т|млн\s*га|тыс)\.?\s*$", _re.I)


def normalize_row_name(raw: str) -> str:
    """Нормализовать имя строки таблицы Росстата для поиска в ALIASES."""
    s = raw.replace("\xa0", " ").replace("\n", " ").replace("\u00ad", "").strip()
    s = s.translate(_SUPERSCRIPTS)
    s = _re.sub(r"\d+\)", "", s)            # сноски 1) 2), в т.ч. цепочки 1);2)
    s = s.translate(_LATIN_TO_CYR)
    s = _re.sub(r"[–—−‐-]+", "-", s)        # все тире/дефисы -> '-'
    s = _re.sub(r"\s*-\s*", "-", s)          # 'Осетия - Алания' -> 'Осетия-Алания'
    s = _re.sub(r"\s+", " ", s).strip(" .;,")
    return s.lower()


def resolve_region(raw: str) -> tuple[str | None, float]:
    """Имя строки -> (slug региона | None, множитель значения).

    Множитель 1000 — для строк РФ с укрупнённой единицей
    («Российская Федерация, млрд руб.» при таблице в млн руб.).
    """
    scale = 1.0
    m = _UNIT_SUFFIX_RE.search(raw.replace("\xa0", " "))
    if m:
        raw = raw[: m.start()]
        scale = 1000.0
    slug = ALIASES.get(normalize_row_name(raw))
    return slug, scale

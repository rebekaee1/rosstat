"""Предмет интереса и темы для персонального выпуска (ADR-0033).

Предмет — то, о чём может быть блок письма. Ключ — строка:

* ``ru:<code>`` — показатель России (``indicators``), валюты тоже здесь;
* ``w:<country>:<code>`` — ряд страны мира (``world_indicators``), тот же вид, что у ключей сравнения;
* ``r:<region>:<code>`` — показатель региона России (``region_indicators`` × ``regions``);
* ``ri:<code>`` — показатель регионов без конкретного региона (карта, рейтинг);
* ``reg:<region>`` — регион России; ``c:<country>`` — страна;
* ``t:<topic>`` — тема.

Здесь же — разбор параметров событий сайта в предметы и темы для читателя. Только чистые
функции, без базы.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

RUSSIA = "russia"

# Темы для читателя: порядок — порядок важности по спросу (замер 14.11.2026).
TOPICS: dict[str, tuple[str, str]] = {
    "prices": ("Цены и инфляция", "Prices and inflation"),
    "fuel": ("Топливо", "Fuel"),
    "rates": ("Ставки и кредиты", "Interest rates"),
    "currencies": ("Рубль и валюты", "Currencies"),
    "commodities": ("Нефть, золото и сырьё", "Oil, gold and commodities"),
    "indices": ("Биржевые индексы", "Stock indices"),
    "wages": ("Зарплаты и доходы", "Wages and income"),
    "labor": ("Работа", "Jobs"),
    "gdp": ("ВВП и рост", "GDP and growth"),
    "housing": ("Жильё и ипотека", "Housing and mortgages"),
    "finance": ("Деньги и бюджет", "Money and budget"),
    "business": ("Бизнес и инвестиции", "Business and investment"),
    "trade": ("Внешняя торговля", "Trade"),
    "population": ("Население", "Population"),
    "science": ("Наука и образование", "Science and education"),
}

# Категория показателя России (поле `indicators.category`) → тема.
CATEGORY_RU_TOPIC = {
    "Цены": "prices", "Ставки": "rates", "Валюты": "currencies", "Финансы": "finance",
    "Бюджет": "finance", "Государственные финансы": "finance", "Индексы": "indices",
    "Товарные рынки": "commodities", "Рынок труда": "labor", "ВВП": "gdp", "Население": "population",
    "Демография": "population", "Торговля": "trade", "Бизнес": "business", "Наука": "science",
}
# Слаг категории сайта (параметр `category` событий) → тема.
CATEGORY_SLUG_TOPIC = {
    "prices": "prices", "rates": "rates", "currencies": "currencies", "finance": "finance",
    "indices": "indices", "commodities": "commodities", "labor": "labor", "gdp": "gdp",
    "population": "population", "trade": "trade", "business": "business", "science": "science",
}
# Код → тема поточнее категории.
_CODE_TOPIC_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^(fuel-|ceni-(ai|dt|benzin|dizel|gaz-))"), "fuel"),
    (re.compile(r"^(mortgage|housing|ceni-.*(kvartir|zhil))"), "housing"),
    (re.compile(r"^(wages|income|.*zarabotn|.*dohod)"), "wages"),
    (re.compile(r"^(gold|brent|urals|coal|silver)"), "commodities"),
)
_WORLD_TOPIC_WORDS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("инфляц", "цен", "hicp", "cpi", "price"), "prices"),
    (("безработ", "занят", "труд", "unemploy", "employ", "labour", "labor"), "labor"),
    (("зарплат", "заработ", "доход", "wage", "earning", "income"), "wages"),
    (("ставк", "процент", "доходност", "rate", "yield"), "rates"),
    (("валют", "курс", "exchange"), "currencies"),
    (("ввп", "национальные счета", "валовой", "gdp", "national accounts"), "gdp"),
    (("долг", "бюджет", "дефицит", "государственн", "debt", "deficit", "government"), "finance"),
    (("торгов", "экспорт", "импорт", "trade", "export", "import"), "trade"),
    (("насел", "демограф", "рождаем", "population", "demograph"), "population"),
    (("жиль", "ипотек", "недвижим", "house", "dwelling", "mortgage"), "housing"),
    (("промышл", "строит", "бизнес", "industr", "construct", "business"), "business"),
    (("наук", "образован", "science", "education", "research"), "science"),
)


def topic_for_code(code: str, category: str | None = None) -> str | None:
    """Тема показателя России или регионов: правило по коду, затем категория (слаг или русское имя)."""
    c = (code or "").lower()
    for pattern, topic in _CODE_TOPIC_RULES:
        if pattern.search(c):
            return topic
    if c.startswith("ceni-"):
        return "prices"
    if category:
        return CATEGORY_SLUG_TOPIC.get(category) or CATEGORY_RU_TOPIC.get(category)
    return None


def topic_for_text(*texts: str | None) -> str | None:
    """Тема ряда мира или региона по словам категории/раздела/названия."""
    hay = " ".join(t for t in texts if t).lower()
    if not hay:
        return None
    for words, topic in _WORLD_TOPIC_WORDS:
        if any(w in hay for w in words):
            return topic
    return None


def topic_label(topic: str, locale: str) -> str:
    ru, en = TOPICS.get(topic, (topic, topic))
    return en if locale == "en" else ru


@dataclass(frozen=True)
class Subject:
    kind: str           # ru / w / r / ri / reg / c / t
    code: str = ""      # код ряда (ru, w, r, ri) или тема (t)
    place: str = ""     # страна (w, c) или регион (r, reg)

    @property
    def key(self) -> str:
        if self.kind == "ru":
            return f"ru:{self.code}"
        if self.kind == "w":
            return f"w:{self.place}:{self.code}"
        if self.kind == "r":
            return f"r:{self.place}:{self.code}"
        if self.kind == "ri":
            return f"ri:{self.code}"
        if self.kind == "reg":
            return f"reg:{self.place}"
        if self.kind == "c":
            return f"c:{self.place}"
        return f"t:{self.code}"

    @property
    def is_series(self) -> bool:
        return self.kind in ("ru", "w", "r")


_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,119}$")
_CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$")


def _ok_slug(s: str | None) -> bool:
    return bool(s) and bool(_SLUG_RE.match(s))


def _ok_code(s: str | None) -> bool:
    return bool(s) and bool(_CODE_RE.match(s))


def parse_key(key: str | None) -> Subject | None:
    """Ключ предмета → Subject; мусор → None (ключи приходят и из событий браузера)."""
    if not key or len(key) > 200:
        return None
    parts = key.split(":")
    kind = parts[0]
    if kind == "ru" and len(parts) == 2 and _ok_code(parts[1]):
        return Subject("ru", parts[1])
    if kind == "w" and len(parts) == 3 and _ok_slug(parts[1]) and _ok_code(parts[2]):
        if parts[1] == RUSSIA:
            return Subject("ru", parts[2])
        return Subject("w", parts[2], parts[1])
    if kind == "r" and len(parts) == 3 and _ok_slug(parts[1]) and _ok_code(parts[2]):
        return Subject("r", parts[2], parts[1])
    if kind == "ri" and len(parts) == 2 and _ok_code(parts[1]):
        return Subject("ri", parts[1])
    if kind == "reg" and len(parts) == 2 and _ok_slug(parts[1]):
        return Subject("reg", place=parts[1])
    if kind == "c" and len(parts) == 2 and _ok_slug(parts[1]):
        return Subject("c", place=parts[1])
    if kind == "t" and len(parts) == 2 and parts[1] in TOPICS:
        return Subject("t", parts[1])
    return None


def _indicator_param(value: str | None, region: str | None = None) -> list[Subject]:
    """Параметр `indicator` событий: «cpi» или «region:<slug>:<code>»."""
    if not value or not isinstance(value, str):
        return []
    if value.startswith("region:"):
        parts = value.split(":")
        if len(parts) == 3 and _ok_slug(parts[1]) and _ok_code(parts[2]):
            return [Subject("r", parts[2], parts[1]), Subject("reg", place=parts[1])]
        return []
    if _ok_code(value):
        return [Subject("ru", value)]
    return []


def _world_or_russia(code: str | None, country: str | None) -> list[Subject]:
    if not _ok_code(code):
        return []
    if country and country != RUSSIA and _ok_slug(country):
        return [Subject("w", code, country), Subject("c", place=country)]
    return [Subject("ru", code)]


def _compare_codes(raw: str | None) -> list[Subject]:
    out: list[Subject] = []
    for part in (raw or "").split(",")[:8]:
        part = part.strip()
        if not part:
            continue
        sub = parse_key(part) if ":" in part else (Subject("ru", part) if _ok_code(part) else None)
        if sub is not None:
            out.append(sub)
    return out


# Событие сайта → (вид сигнала, предметы). Вид сигнала задаёт вес и полураспад (profile.SIGNALS).
def subjects_from_event(event_name: str, params: dict | None) -> tuple[str | None, list[Subject]]:
    p = params if isinstance(params, dict) else {}
    cat = p.get("category") if isinstance(p.get("category"), str) else None
    if event_name == "indicator_view":
        subs = _world_or_russia(p.get("code"), p.get("country")) if p.get("country") else _indicator_param(p.get("indicator"))
        if cat and cat in CATEGORY_SLUG_TOPIC and not p.get("country"):
            subs.append(Subject("t", CATEGORY_SLUG_TOPIC[cat]))
        return "view", subs
    if event_name == "region_indicator_view":
        region, code = p.get("region"), p.get("code")
        if _ok_slug(region) and _ok_code(code):
            return "view", [Subject("r", code, region), Subject("reg", place=region)]
        return "view", _indicator_param(p.get("indicator"))
    if event_name in ("download_csv", "download_excel", "chart_image_download", "regions_map_gif_download"):
        subs = _indicator_param(p.get("indicator"))
        if not subs and p.get("world") and isinstance(p.get("world"), str):
            subs = _compare_codes(p.get("world"))
        return "download", subs
    if event_name == "download_limit":
        return "download_limit", _indicator_param(p.get("indicator"))
    if event_name == "forecast_view":
        return "forecast_view", _indicator_param(p.get("indicator"))
    if event_name == "search_select":
        scope, code, country, region = p.get("scope"), p.get("code"), p.get("country"), p.get("region")
        if scope == "region_indicator" and _ok_slug(region) and _ok_code(code):
            return "search_select", [Subject("r", code, region), Subject("reg", place=region)]
        if scope == "region" and _ok_slug(region or code):
            return "search_select", [Subject("reg", place=region or code)]
        if scope == "country" and _ok_slug(country or code):
            return "search_select", [Subject("c", place=country or code)]
        if scope == "world" or (country and country != RUSSIA):
            return "search_select", _world_or_russia(code, country)
        if _ok_code(code):
            return "search_select", [Subject("ru", code)]
        return "search_select", []
    if event_name == "compare_open":
        return "compare", _compare_codes(p.get("codes"))
    if event_name == "related_indicator_click":
        return "related_click", _indicator_param(p.get("to"))
    if event_name in ("category_tile_click", "home_indicator_click"):
        subs = _indicator_param(p.get("indicator"))
        if cat in CATEGORY_SLUG_TOPIC:
            subs.append(Subject("t", CATEGORY_SLUG_TOPIC[cat]))
        return "tile_click", subs
    if event_name in ("home_category_click", "nav_category_open"):
        slug = p.get("category") or p.get("slug")
        return "topic_click", [Subject("t", CATEGORY_SLUG_TOPIC[slug])] if slug in CATEGORY_SLUG_TOPIC else []
    if event_name == "regions_map_metric":
        metric = p.get("metric")
        if isinstance(metric, str) and ":" in metric:
            code = metric.split(":", 1)[1]
            if _ok_code(code):
                return "topic_click", [Subject("ri", code)]
        return "topic_click", []
    if event_name in ("calc_mortgage", "calc_use", "calc_compound"):
        topic = "housing" if event_name == "calc_mortgage" or p.get("tool") == "mortgage" else "rates"
        return "topic_click", [Subject("t", topic)]
    return None, []


# Путь страницы (посадочная при регистрации) → предметы.
_PATH_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^/currencies/indicator/([A-Za-z0-9._-]+)"), "ru"),
    (re.compile(r"^/russia/indicator/([A-Za-z0-9._-]+)"), "ru"),
    (re.compile(r"^/indicator/([A-Za-z0-9._-]+)"), "ru"),
    (re.compile(r"^/russia/region/(?!map/)([a-z0-9-]+)/([A-Za-z0-9._-]+)"), "r"),
    (re.compile(r"^/russia/region/(?!map/)([a-z0-9-]+)/?$"), "reg"),
    (re.compile(r"^/russia/region/map/([A-Za-z0-9._-]+)"), "ri"),
    (re.compile(r"^/russia/region-rating/([A-Za-z0-9._-]+)"), "ri"),
    (re.compile(r"^/([a-z0-9-]+)/indicator/([A-Za-z0-9._-]+)"), "w"),
)


def subjects_from_path(path: str | None) -> list[Subject]:
    if not path:
        return []
    path = re.sub(r"^https?://[^/]+", "", path).split("?", 1)[0].split("#", 1)[0]
    for pattern, kind in _PATH_PATTERNS:
        m = pattern.match(path)
        if not m:
            continue
        if kind == "ru":
            return [Subject("ru", m.group(1))]
        if kind == "r":
            return [Subject("r", m.group(2), m.group(1)), Subject("reg", place=m.group(1))]
        if kind == "reg":
            return [Subject("reg", place=m.group(1))]
        if kind == "ri":
            return [Subject("ri", m.group(1))]
        if kind == "w":
            return _world_or_russia(m.group(2), m.group(1))
    return []


def normalize_query(q: str | None) -> str:
    """Нормализация поискового запроса для таблицы «запрос → ряд» (хэшируется, текст не хранится)."""
    s = (q or "").casefold().replace("ё", "е")
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()[:120]

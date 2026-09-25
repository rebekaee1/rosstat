"""EN catalog: which public paths have a real English twin (hreflang-safe).

Until a path is listed here, SSR must NOT emit ``hreflang="en"`` for it.
Content agents expand prefixes/exact paths as EN pages ship.
Do NOT treat arbitrary first segments as countries — that would advertise
hreflang to 404s.

Scale contract (~5.04M URLs on each of apex and ``ru.``): a mirror pair is
the same canonical path with the host swapped. This module is an O(1)
allowlist of exact paths, prefixes, and path shapes. It does not query the
database, does not store a pair list, and must not grow a per-URL exception
for a family that already has a template in ``site_paths``. A false negative
silently unpairs every URL of that shape. Sitemap ``xhtml:link`` alternates
are out of scope: Yandex does not read them, Google treats one HTML cluster
as enough, and expanding 5M URLs × 3 links does not ship.
"""

from __future__ import annotations

from functools import lru_cache

# Exact paths with curated EN SEO + UI.
EN_EXACT_PATHS: frozenset[str] = frozenset({
    "/",
    "/about",
    "/methodology",
    "/privacy",
    "/terms",
    "/compare",
    "/calculator",
    "/calculator/mortgage",
    "/calculator/compound",
    "/russia",
    "/russia/category",
    "/russia/today",
    "/russia/calendar",
    "/russia/demographics",
    "/russia/region",
    "/russia/region-rating",
    "/widgets",
})

# Prefixes: path == prefix.rstrip("/") or path.startswith(prefix).
EN_PATH_PREFIXES: tuple[str, ...] = (
    # Рейтинг мира: /world/rating/{concept} и годовые /world/rating/{concept}/{year}.
    "/world/rating",
    # Россия: карточка категории, показатель (+ годовой {code}/{year} и
    # месячный {code}/{year}-{mm} лендинги), сегодня, календарь, регион
    # (+ годовой {slug}/{code}/{year}), рейтинг и сравнение регионов.
    "/russia/category/",
    "/russia/indicator/",
    "/russia/today/",
    "/russia/calendar/",
    "/russia/region/",
    "/russia/region-rating/",
    "/russia/region-vs/",
)


@lru_cache(maxsize=1)
def _country_slugs() -> frozenset[str]:
    """Статические слаги стран мира, которым можно обещать EN-твин.

    Источник — канонический каталог ``WORLD_COUNTRIES`` (eurostat_parser):
    лоадер стран создаёт ``world_countries`` только из него, поэтому frozenset
    консервативен без обращения к БД. Россия добавлена явно — она живёт
    отдельным data plane, но её годовые/месячные лендинги уже покрыты
    префиксом ``/russia/``, а в сравнениях стран первый слаг пары бывает «russia».

    Ленивый импорт внутри кэша: eurostat_parser тянет HTTP-зависимости,
    которые не нужны при обычном импорте ``app.data.i18n``.
    """
    from app.services.eurostat_parser import WORLD_COUNTRIES

    return frozenset(meta[0] for meta in WORLD_COUNTRIES.values()) | {"russia"}


def has_en_path(path: str) -> bool:
    """True if this path may advertise an English alternate.

    Decision is a pure function of the path shape. Bulk families (Russia
    region × indicator × year, world indicator years, subnational region
    years, country and region comparisons) match a prefix or a segment
    pattern — never a stored list of URLs.
    """
    if not path:
        return False
    if not path.startswith("/"):
        path = f"/{path}"
    path = path.split("?", 1)[0]
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    if path in EN_EXACT_PATHS:
        return True
    if len(path.split("/")) == 2 and path.split("/")[1] in _country_slugs():
        return True
    for prefix in EN_PATH_PREFIXES:
        if path == prefix.rstrip("/") or path.startswith(prefix):
            return True

    # Сравнения стран /{a}-vs-{b}/{concept}: первый сегмент содержит «-vs-»,
    # разрез пары — по последнему «-vs-» (тот же алгоритм, что в роуте
    # /seo/world-vs: слаг «united-states» не разъедается). Оба слага должны
    # быть в каталоге стран — иначе обещали бы EN-твин будущей 404.
    segments = path.split("/")
    if len(segments) == 3 and "-vs-" in segments[1]:
        slug_a, sep, slug_b = segments[1].rpartition("-vs-")
        if sep and slug_a and slug_b:
            slugs = _country_slugs()
            if slug_a in slugs and slug_b in slugs:
                return True

    # /{country}/indicator/… — карточка показателя страны, годовой
    # /{country}/indicator/{code}/{year}. Первый сегмент — только реальная
    # страна каталога: произвольные первые сегменты не объявляем (404-риск).
    if len(segments) >= 3 and segments[2] == "indicator":
        if segments[1] in _country_slugs():
            return True
    if len(segments) >= 3 and segments[2] in ("regions", "region"):
        if segments[1] in _country_slugs() and segments[1] != "russia":
            return True
    # /{country}/region-vs/{a}-vs-{b} — site_paths.country_region_vs.
    # Россия уже покрыта префиксом /russia/region-vs/. Слаги регионов
    # не ищем в БД: пара зеркал — подмена хоста у пути этой формы.
    if (
        len(segments) == 4
        and segments[2] == "region-vs"
        and "-vs-" in segments[3]
        and segments[1] in _country_slugs()
        and segments[1] != "russia"
    ):
        return True
    return False

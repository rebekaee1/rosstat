"""Все действующие публичные canonical-страницы доступны для индексации.

Решение владельца 2026-09-20: sitemap не отбирает контент по теме,
возрасту, популярности или объёму данных сверх условий самого SSR.
Priority задаёт очередность обхода, а не исключение страниц.
Служебные поверхности, preview, редиректы и несуществующие страницы
не являются дополнительными публичными canonical-страницами.
Уточнения только для Google на ru.: метка `googlebot` (11.11.2026), короткий
индекс sitemap и запрет обхода годовых страниц мира в robots.txt (13.11.2026) —
блоки ниже; реестр не меняется.

noindex здесь не инструмент бюджета обхода: робот всё равно скачивает URL,
чтобы прочитать тег. На каталоге ~5 млн URL на хост эта политика ставит
noindex только ханипоту. Кабинет, виджеты и оболочка SPA закрываются
заголовком своих маршрутов. Дубли с неканоническим query режутся в
robots.txt (`*` и Googlebot) и склеиваются Clean-param у Яндекса.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Literal

Tier = Literal[1, 2, 3]

# --- Пороги (одна таблица) -------------------------------------------------

# Годовая SSR-страница РФ существует при хотя бы одном наблюдении.
RUSSIA_YEAR_MIN_POINTS = 1

TIER1_PRIORITY = "0.8"
TIER2_PRIORITY = "0.4"

# `?mode=` никогда не каноничен: в view_model_families нет per-mode seo-title.
MODE_CANONICAL = False

_HONEYPOT_PATH = "/__honeypot__/trap"


def robots_for_path(path: str, *, today: date | None = None) -> str:
    """Содержимое meta robots для SSR. Preview-локаль обрабатывает renderer."""
    if is_noindex_path(path, today=today):
        return (
            "noindex, follow, max-snippet:-1, max-image-preview:large, "
            "max-video-preview:-1"
        )
    return (
        "index, follow, max-snippet:-1, max-image-preview:large, "
        "max-video-preview:-1"
    )


def is_noindex_path(path: str, *, today: date | None = None) -> bool:
    """Tier 3: страница живая, но не для индекса."""
    raw = (path or "").split("?", 1)[0].rstrip("/") or "/"
    if raw == honeypot_path() or raw.startswith("/__honeypot__/"):
        return True
    # Возраст не определяет полезность истории. Наличие данных и канон
    # проверяют маршруты и sitemap, а не календарный cutoff по URL.
    return False


# --- Google-only noindex на ru. (решение владельца 11.11.2026) ----------------
# Google выбросил ru. из индекса 02–05.10: новый хост, 23 внешние ссылки, 10 млн
# почти одинаковых годовых страниц. Годовые страницы стран мира и их регионов
# (8,6 млн из 10 млн адресов ru.) получают `<meta name="googlebot" content="noindex,
# follow">`: Google их не индексирует и оценивает ru. по России, регионам РФ,
# карточкам, рейтингам и сравнениям. Яндекс и люди видят всё как раньше (Яндекс
# meta googlebot не читает). Apex (EN) не трогается — контроль. Это не меняет
# состав sitemap: робот должен прочесть метку. Откат — флаг
# RUSTATS_RU_GOOGLE_NOINDEX_WORLD_YEARS=false. Основание —
# .artifacts/google-drop-2026-11-11/консультация.md.
_RU_GOOGLE_NOINDEX = re.compile(
    r"^/(?!(?:russia|currencies|world)/)[a-z0-9-]+/"
    r"(?:indicator/[a-z0-9_.-]+|region/[a-z0-9-]+/[a-z0-9_.-]+)/[0-9]{4}$"
)
GOOGLEBOT_NOINDEX_META = '<meta name="googlebot" content="noindex, follow">'


def is_ru_google_noindex_path(path: str) -> bool:
    """Годовая страница страны мира или её региона (не России, не валют, не /world/)."""
    raw = (path or "").split("?", 1)[0].rstrip("/")
    return bool(_RU_GOOGLE_NOINDEX.match(raw))


def googlebot_meta_for_path(path: str, locale: str) -> str:
    """Тег только для Google на русской версии; пусто для EN и остальных страниц."""
    from app.config import settings

    if locale != "ru" or not settings.ru_google_noindex_world_years:
        return ""
    return GOOGLEBOT_NOINDEX_META if is_ru_google_noindex_path(path) else ""


# --- Короткий sitemap для Google на ru. (решение владельца 13.11.2026) --------
# Замер 13.11: три семейства годовых шардов — 9,57 млн из 10,1 млн адресов хоста
# (94,7%); входы из поиска за 28 дней получили около 400 таких страниц. Googlebot
# тратил на них 63% обхода, на показатели России и их годы — 0,5%, хотя они дают
# 68% входов из Яндекса. Роботу Google на ru. индекс `/sitemap.xml` перечисляет
# всё, кроме этих трёх семейств: хабы, показатели России с годами и месяцами,
# сравнения, рейтинги, карточки стран и регионов, приоритетный шард (в нём
# остаются годовые страницы с доказанным спросом).
#
# Это уточняет решение 20.09 только для одного читателя: реестр, файлы шардов,
# robots.txt и ответ всем остальным роботам прежние. Отдельный адрес в robots.txt
# не подошёл: Яндекс знает sitemap только из robots.txt, а его инструмент «Файлы
# Sitemap» 13.11 работал только на чтение. Apex (EN) не трогается — контроль.
# Откат — RUSTATS_RU_GOOGLE_SHORT_SITEMAP=false.
_GOOGLE_SHORT_SITEMAP_EXCLUDED = re.compile(
    r"^(?:world-years|world-region-years|regional-years)(?:-[0-9]+)?$"
)
# Googlebot (все его виды читают sitemap под этим именем) и живая проверка URL в
# Search Console. Подделка под Googlebot получит подмножество того же реестра.
_GOOGLE_SITEMAP_AGENTS = ("googlebot", "google-inspectiontool")


def is_google_sitemap_agent(user_agent: str | None) -> bool:
    """User-Agent робота Google, который читает sitemap для поиска."""
    agent = (user_agent or "").lower()
    return any(token in agent for token in _GOOGLE_SITEMAP_AGENTS)


def ru_google_short_sitemap_enabled(*, ru_host: bool) -> bool:
    """На этом хосте индекс sitemap зависит от робота (нужен ``Vary: User-Agent``)."""
    from app.config import settings

    return bool(ru_host and settings.apex_locale_en and settings.ru_google_short_sitemap)


def is_google_short_sitemap_excluded(section: str) -> bool:
    """Шард массовых годовых страниц: мир, регионы мира, регионы России."""
    return bool(_GOOGLE_SHORT_SITEMAP_EXCLUDED.match(section or ""))


def google_short_sitemap_names(names: list[str]) -> list[str]:
    """Имена шардов для Google в прежнем порядке; пустой индекс не отдаём."""
    kept = [name for name in names if not is_google_short_sitemap_excluded(name)]
    return kept or list(names)


# --- Запрет обхода годовых страниц мира роботу Google на ru. (решение владельца 13.11.2026) ---
# Руководство Google об обходе больших сайтов: метка noindex обход не экономит — робот всё
# равно скачивает страницу; адреса, которые не нужны в поиске, закрывают в robots.txt. На ru.
# это те же 8,6 млн годовых страниц стран мира и их регионов, что несут метку googlebot с
# 11.11 (`_RU_GOOGLE_NOINDEX`). robots.txt не умеет «четыре цифры», поэтому правило шире
# регулярного выражения: любой хвост, начинающийся с 1 или 2, после кода показателя. Таких
# публичных адресов, кроме годовых, у стран мира нет. Длина разрешающего правила больше
# длины запрещающего — по правилам Google побеждает более длинное, поэтому Россия, валюты и
# OG-картинки остаются открытыми. Правила дописываются в группу Googlebot при ответе: шаблоны
# robots.txt трёх мест (RU, EN, frontend) остаются одинаковыми. Яндекс, Bing и apex не
# затронуты. Откат — RUSTATS_RU_GOOGLE_DISALLOW_WORLD_YEARS=false.
RU_GOOGLE_CRAWL_BLOCK_RULES: tuple[str, ...] = (
    "# Годовые страницы других стран: обход роботом Google закрыт. Россия и валюты открыты.",
    "Disallow: /*/indicator/*/1",
    "Disallow: /*/indicator/*/2",
    "Disallow: /*/region/*/*/1",
    "Disallow: /*/region/*/*/2",
    "Allow: /russia/indicator/*/1",
    "Allow: /russia/indicator/*/2",
    "Allow: /russia/region/*/*/1",
    "Allow: /russia/region/*/*/2",
    "Allow: /currencies/indicator/*/1",
    "Allow: /currencies/indicator/*/2",
    "Allow: /og/*/region/*/*/1",
    "Allow: /og/*/region/*/*/2",
)


# Приоритетный шард общий для хостов и роботов; 13.11.2026 в нём 6 876 из 15 485 адресов —
# годовые страницы стран мира. Роботу Google на ru. они закрыты, поэтому в его индексе
# вместо `priority` стоит `priority-google`: тот же шард без закрытых адресов.
GOOGLE_PRIORITY_SECTION = "priority-google"


def google_priority_swap(names: list[str], *, priority: str) -> list[str]:
    """Заменить имя приоритетного шарда на вариант для Google; порядок прежний."""
    return [GOOGLE_PRIORITY_SECTION if name == priority else name for name in names]


def drop_blocked_urls(urlset_xml: str) -> str:
    """Убрать из XML шарда записи ``<url>``, закрытые роботу Google на ru."""
    from html import unescape
    from urllib.parse import urlparse

    def keep(match: re.Match) -> str:
        loc = _URL_LOC.search(match.group(0))
        if loc is None:
            return match.group(0)
        path = urlparse(unescape(loc.group(1)).strip()).path
        return "" if is_ru_google_noindex_path(path) else match.group(0)

    return _URL_BLOCK.sub(keep, urlset_xml)


_URL_BLOCK = re.compile(r"[ \t]*<url>.*?</url>\n?", re.S)
_URL_LOC = re.compile(r"<loc>([^<]+)</loc>")


def ru_google_crawl_block_rules(*, ru_host: bool) -> tuple[str, ...]:
    """Строки для группы Googlebot в robots.txt хоста; пусто — ничего не дописывать."""
    from app.config import settings

    if ru_host and settings.apex_locale_en and settings.ru_google_disallow_world_years:
        return RU_GOOGLE_CRAWL_BLOCK_RULES
    return ()


def add_rules_to_agent_group(robots_text: str, agent: str, rules: tuple[str, ...]) -> str:
    """Дописать строки в конец группы ``User-agent: <agent>``.

    Группы нет — текст возвращается без изменений: молча создавать группу нельзя, у нового
    ``User-agent`` пропали бы общие запреты, которые в шаблоне повторены для Googlebot.
    """
    if not rules:
        return robots_text
    lines = robots_text.split("\n")
    start = next(
        (i for i, line in enumerate(lines)
         if line.strip().lower() == f"user-agent: {agent.lower()}"),
        None,
    )
    if start is None:
        return robots_text
    end = next((i for i in range(start + 1, len(lines)) if not lines[i].strip()), len(lines))
    return "\n".join(lines[:end] + list(rules) + lines[end:])


def strip_mode_query(path: str) -> str:
    """Канон карточки — без ?mode=, кроме curated per-mode (их нет)."""
    if MODE_CANONICAL:
        return path
    if "?" not in path:
        return path
    base, _, query = path.partition("?")
    kept = [
        part for part in query.split("&")
        if part and not part.startswith("mode=")
    ]
    return f"{base}?{'&'.join(kept)}" if kept else base


def honeypot_path() -> str:
    return _HONEYPOT_PATH

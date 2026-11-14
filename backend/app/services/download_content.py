"""Что скачивают и где упираются в лимит — по содержанию (14.11.2026).

Вопрос партнёра (созвон 14.11.2026): «Что за картинки, что за данные они скачивают? Что им
интересно?» и «люди упираются в лимит скачиваний… регистрируются, но кто-то отваливается».
Слова владельца: события «в Telegram тоже в виде отчёта приходили… в информационном боте всё
что угодно выгрузить, посмотреть, когда душе угодно».

Устройство:
- источник — `frontend_events` событий групп «выгрузки» (`GROUP_DOWNLOAD` + PDF-отчёты) и
  «упёрлись в лимит» (`GROUP_WALL`); объём мал (на 14.11 ≈ 100 событий в неделю), поэтому
  события читаются целиком по индексу имя+время;
- содержание берётся из **адреса страницы** (`url`): у половины событий параметр только
  `source: table-range`, без кода показателя. Параметр `indicator` (`region:slug:code`,
  `regions-leaders:code` …) — запасной путь, если адрес ничего не говорит;
- названия — из справочников (`indicators`, `world_indicators`, `region_indicators`, `regions`,
  `subnational_*`, `WORLD_CONCEPTS`) одной выборкой на таблицу;
- роботы и своя активность исключены тем же правилом, что в витринах
  (`server_sessions.is_bot/is_internal` + `admin_identity`), но проверка идёт только по
  посетителям из выборки: подзапрос по всем сессиям за 90 дней не нужен;
- «зарегистрировались потом» — посетитель упора связан с аккаунтом (`identity_links`), и
  аккаунт создан не раньше чем за 5 минут до первого упора.

Имён, почт, телефонов, `user_id` здесь нет: человек в выгрузке — короткий хэш посетителя.
"""
from __future__ import annotations

import io
import logging
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from html import escape
from typing import Any, Iterable
from urllib.parse import parse_qs, urlsplit

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    BehaviorSession,
    FrontendEvent,
    IdentityLink,
    Indicator,
    Region,
    RegionIndicator,
    ServerSession,
    SubnationalIndicator,
    SubnationalRegion,
    User,
    WorldCountry,
    WorldIndicator,
)
from app.services.analytics_period import MSK_OFFSET, Period, resolve_period
from app.services.goal_taxonomy import GROUP_DOWNLOAD, GROUP_WALL, events_in_group

logger = logging.getLogger(__name__)

# Скачанное: группа «выгрузки» и PDF-отчёты раздела «Исследования».
DOWNLOAD_EVENTS: frozenset[str] = events_in_group(GROUP_DOWNLOAD) | {"research_download"}
WALL_EVENTS: frozenset[str] = events_in_group(GROUP_WALL)
ALL_EVENTS: frozenset[str] = DOWNLOAD_EVENTS | WALL_EVENTS

FORMAT_LABELS: dict[str, str] = {
    "download_excel": "Excel",
    "download_csv": "CSV",
    "demographics_csv": "CSV",
    "download_ical": "календарь",
    "chart_image_download": "картинка графика",
    "compare_image_download": "картинка сравнения",
    "regions_map_gif_download": "анимация карты",
    "export_run": "выгрузка из кабинета",
    "research_download": "PDF-отчёт",
}
WALL_LABELS: dict[str, str] = {
    "download_limit": "таблица (лимит скачиваний)",
    "chart_image_blocked": "картинка графика",
    "compare_image_blocked": "картинка сравнения",
    "compare_limit_hit": "больше рядов в сравнении",
    "regions_map_gif_blocked": "анимация карты",
}
SECTION_LABELS: dict[str, str] = {
    "russia": "Россия", "currency": "валюты", "world": "страны мира", "region": "регионы России",
    "world_region": "регионы других стран", "compare": "сравнение", "rating": "рейтинги",
    "calculator": "калькуляторы", "demographics": "демография", "calendar": "календарь",
    "research": "исследования", "other": "другие страницы",
}
CHANNEL_LABELS: dict[str, str] = {
    "search": "поиск", "direct": "прямой заход", "social": "соцсети", "referral": "с другого сайта",
    "ad": "реклама", "campaign": "рассылка", "internal": "внутренний переход", "unknown": "неизвестно",
}
DEVICE_LABELS: dict[str, str] = {
    "mobile": "телефон", "desktop": "компьютер", "tablet": "планшет", "unknown": "неизвестно",
}

# Окна кнопок бота (дни; 1 = сегодня, -1 = вчера). Потолок 90: события живут 180 дней.
WINDOWS: dict[str, str] = {"0": "сегодня", "1": "вчера", "7": "7 дней", "30": "30 дней", "90": "90 дней"}
MAX_DAYS = 90
# Регистрация «после упора»: аккаунт создан не раньше чем за 5 минут до упора
# (часы браузера и сервера расходятся; событие могло прийти после ответа о регистрации).
_SIGNUP_SLACK = timedelta(minutes=5)
_IN_CHUNK = 500

_RESERVED_FIRST = frozenset({
    "compare", "world", "calculator", "calculators", "widgets", "embed", "currencies", "research",
    "forecasts", "login", "register", "account", "admin", "about", "privacy", "api", "og",
})


# ---------------------------------------------------------------------------
# Содержание события (чистые функции)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ContentRef:
    """Что скачано: раздел, вид страницы и коды для поиска названия."""

    section: str
    kind: str  # ru | world | region | region_map | region_rating | region_page | world_region |
    #            world_region_map | compare | world_rating | research | page
    code: str = ""
    place: str = ""   # регион России / страна / «страна/регион»
    codes: tuple[str, ...] = ()  # ряды сравнения

    @property
    def key(self) -> str:
        return "|".join((self.kind, self.code, self.place, ",".join(self.codes)))


def _path_parts(url: str | None) -> tuple[list[str], dict[str, list[str]]]:
    if not url:
        return [], {}
    try:
        parts = urlsplit(str(url))
    except ValueError:
        return [], {}
    segs = [p for p in (parts.path or "").strip("/").split("/") if p]
    return segs, parse_qs(parts.query or "")


def _from_params(event_name: str, params: dict) -> ContentRef | None:
    """Запасной путь: параметр `indicator` (адрес события ничего не сказал)."""
    raw = str(params.get("indicator") or "").strip()
    if event_name == "research_download" and params.get("report"):
        return ContentRef("research", "research", code=str(params["report"]))
    if not raw:
        return None
    bits = raw.split(":")
    head = bits[0]
    if head == "region" and len(bits) >= 3:
        return ContentRef("region", "region", code=bits[2], place=bits[1])
    if head in ("regions-leaders", "regions-map") and len(bits) >= 2:
        if bits[1] in ("", "overview"):
            return ContentRef("region", "page", code="карта регионов")
        return ContentRef("region", "region_map", code=bits[1])
    if head == "world-region" and len(bits) >= 3:
        return ContentRef("world_region", "world_region", code=bits[2], place=bits[1])
    if head == "world-regions-map":
        return ContentRef("world_region", "page", code="карта регионов стран")
    if head == "world" and len(bits) >= 3:  # «world:страна:код» (так пишет просмотр страницы страны)
        return ContentRef("world", "world", code=bits[2], place=bits[1])
    if head == "rating" and len(bits) >= 2:
        return ContentRef("rating", "world_rating", code=bits[1])
    if raw == "regions-compare":
        return ContentRef("region", "page", code="сравнение регионов")
    if params.get("world"):
        return ContentRef("world", "world", code=raw)
    return ContentRef("russia", "ru", code=raw)


def _split(value: Any) -> tuple[str, ...]:
    return tuple(v.strip() for v in str(value or "").split(",") if v.strip())[:8]


def _more(value: Any) -> str:
    """Сколько кодов не вошло в 200 знаков (фронт: `codes_more` / `regions_more`), строкой для ContentRef.place."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return ""
    return str(n) if n > 0 else ""


def _more_tail(ref: "ContentRef") -> str:
    return f" и ещё {ref.place}" if ref.place.isdigit() else ""


def _from_subject(params: dict, segs: list[str]) -> ContentRef | None:
    """Явное содержание события (`code`, `country`, `region`, `codes`, `regions`; фронт с 14.11.2026,
    `lib/downloadSubject.js`). Вид страницы — по префиксу прежнего параметра `indicator`."""
    codes, regions = _split(params.get("codes")), _split(params.get("regions"))
    if codes:
        return ContentRef("compare", "compare", codes=codes, place=_more(params.get("codes_more")))
    if regions:
        return ContentRef("region", "regions_compare", codes=regions, place=_more(params.get("regions_more")))
    code = str(params.get("code") or "").strip()
    if not code:
        return None
    country = str(params.get("country") or "").strip()
    region = str(params.get("region") or "").strip()
    head = str(params.get("indicator") or "").split(":")[0]
    if head == "rating":
        return ContentRef("rating", "world_rating", code=code)
    if head in ("regions-leaders", "regions-map"):
        return ContentRef("region", "region_map", code=code)
    if head == "world-regions-map" and country:
        return ContentRef("world_region", "world_region_map", code=code, place=country)
    if country and region:
        return ContentRef("world_region", "world_region", code=code, place=f"{country}/{region}")
    if region:
        return ContentRef("region", "region", code=code, place=region)
    if country:
        return ContentRef("world", "world", code=code, place=country)
    section = "currency" if segs[:1] == ["currencies"] else "russia"
    return ContentRef(section, "ru", code=code)


def content_ref(event_name: str, params: dict | None, url: str | None) -> ContentRef:
    """Содержание события: явные параметры (с 14.11.2026), иначе адрес страницы, иначе прежний
    параметр `indicator`. Адрес — запасной источник для событий до 14.11 и мест без показателя."""
    params = params or {}
    segs, query = _path_parts(url)
    if event_name == "download_ical":
        return ContentRef("calendar", "page", code="календарь событий")
    if event_name == "demographics_csv":
        return ContentRef("demographics", "page", code="демография")
    if event_name == "research_download":
        return _from_params(event_name, params) or ContentRef("research", "page", code="исследования")
    ref = _from_subject(params, segs) or _from_path(segs, query)
    if ref is not None:
        return ref
    return _from_params(event_name, params) or ContentRef("other", "page", code="/" + "/".join(segs))


def _from_path(segs: list[str], query: dict[str, list[str]]) -> ContentRef | None:
    if not segs:
        return None
    first = segs[0]
    rest = segs[1:]
    if first == "compare":
        raw = (query.get("codes") or [""])[0]
        codes = [c.strip() for c in raw.split(",") if c.strip()]
        if not codes:
            codes = [v for k in ("a", "b") for v in query.get(k, [])[:1] if v]
        return ContentRef("compare", "compare", codes=tuple(codes[:8]))
    if first == "currencies":
        if len(rest) >= 2 and rest[0] == "indicator":
            return ContentRef("currency", "ru", code=rest[1])
        return ContentRef("currency", "page", code="валюты")
    if first == "world":
        if len(rest) >= 2 and rest[0] == "rating":
            return ContentRef("rating", "world_rating", code=rest[1])
        return ContentRef("world", "page", code="мировой раздел")
    if first in ("calculator", "calculators"):
        return ContentRef("calculator", "page", code=rest[0] if rest else "калькулятор")
    if first == "research":
        return ContentRef("research", "research", code=rest[0]) if rest else None
    if first in _RESERVED_FIRST:
        return None
    if first == "russia":
        if len(rest) >= 2 and rest[0] in ("indicator", "today"):
            return ContentRef("russia", "ru", code=rest[1])
        if len(rest) >= 3 and rest[0] == "region" and rest[1] == "map":
            return ContentRef("region", "region_map", code=rest[2])
        if len(rest) >= 3 and rest[0] == "region":
            return ContentRef("region", "region", code=rest[2], place=rest[1])
        if len(rest) == 2 and rest[0] == "region":
            return ContentRef("region", "region_page", place=rest[1])
        if len(rest) >= 2 and rest[0] == "region-rating":
            return ContentRef("rating", "region_rating", code=rest[1])
        if rest and rest[0] == "demographics":
            return ContentRef("demographics", "page", code="демография")
        if rest and rest[0] == "calendar":
            return ContentRef("calendar", "page", code="календарь событий")
        return None
    # Страна: /{страна}/indicator/{код}, /{страна}/region/{регион}/{код}, /{страна}/region/map/{код}
    if len(rest) >= 2 and rest[0] == "indicator":
        return ContentRef("world", "world", code=rest[1], place=first)
    if len(rest) >= 3 and rest[0] == "region" and rest[1] == "map":
        return ContentRef("world_region", "world_region_map", code=rest[2], place=first)
    if len(rest) >= 3 and rest[0] == "region":
        return ContentRef("world_region", "world_region", code=rest[2], place=f"{first}/{rest[1]}")
    return None


# ---------------------------------------------------------------------------
# Названия из справочников
# ---------------------------------------------------------------------------

@dataclass
class Names:
    ru: dict[str, str] = field(default_factory=dict)
    world: dict[str, tuple[str, str]] = field(default_factory=dict)   # код → (название, страна)
    region_ind: dict[str, str] = field(default_factory=dict)
    regions: dict[str, str] = field(default_factory=dict)
    countries: dict[str, tuple[str, str]] = field(default_factory=dict)  # slug → (код страны, название)
    sub_ind: dict[tuple[str, str], str] = field(default_factory=dict)  # (код страны, код) → название
    sub_regions: dict[tuple[str, str], str] = field(default_factory=dict)
    concepts: dict[str, str] = field(default_factory=dict)


def _chunks(values: Iterable[str]) -> Iterable[list[str]]:
    items = sorted({v for v in values if v})
    for i in range(0, len(items), _IN_CHUNK):
        yield items[i:i + _IN_CHUNK]


async def load_names(db: AsyncSession, refs: Iterable[ContentRef]) -> Names:
    refs = list(refs)
    names = Names()
    ru_codes = {r.code for r in refs if r.kind == "ru"} | {c for r in refs if r.kind == "compare" for c in r.codes}
    world_codes = {r.code for r in refs if r.kind == "world"} | {c for r in refs if r.kind == "compare" for c in r.codes}
    reg_codes = {r.code for r in refs if r.kind in ("region", "region_map", "region_rating")}
    reg_slugs = ({r.place for r in refs if r.kind in ("region", "region_page")}
                 | {s for r in refs if r.kind == "regions_compare" for s in r.codes})
    country_slugs = {r.place.split("/")[0] for r in refs if r.kind in ("world", "world_region", "world_region_map")}

    for part in _chunks(ru_codes):
        for code, name in (await db.execute(
            select(Indicator.code, Indicator.name).where(Indicator.code.in_(part)))).all():
            names.ru[code] = name
    for part in _chunks(world_codes - set(names.ru)):
        for code, name, country in (await db.execute(
            select(WorldIndicator.code, WorldIndicator.name_ru, WorldCountry.name_ru)
            .join(WorldCountry, WorldCountry.id == WorldIndicator.country_id)
            .where(WorldIndicator.code.in_(part)))).all():
            names.world[code] = (name, country)
    for part in _chunks(reg_codes):
        for code, name in (await db.execute(
            select(RegionIndicator.code, RegionIndicator.name).where(RegionIndicator.code.in_(part)))).all():
            names.region_ind[code] = name
    for part in _chunks(reg_slugs):
        for slug, name in (await db.execute(select(Region.slug, Region.name).where(Region.slug.in_(part)))).all():
            names.regions[slug] = name
    for part in _chunks(country_slugs):
        for slug, code, name in (await db.execute(
            select(WorldCountry.slug, WorldCountry.code, WorldCountry.name_ru)
            .where(WorldCountry.slug.in_(part)))).all():
            names.countries[slug] = (code, name)

    sub_pairs = []
    for r in refs:
        if r.kind in ("world_region", "world_region_map"):
            country = names.countries.get(r.place.split("/")[0])
            if country:
                sub_pairs.append((country[0], r.code, r.place.split("/")[1] if "/" in r.place else ""))
    if sub_pairs:
        codes = {c for _, c, _ in sub_pairs}
        slugs = {s for _, _, s in sub_pairs if s}
        for part in _chunks(codes):
            for cc, code, name in (await db.execute(
                select(SubnationalIndicator.country_code, SubnationalIndicator.code, SubnationalIndicator.name_ru)
                .where(SubnationalIndicator.code.in_(part)))).all():
                names.sub_ind[(cc, code)] = name
        for part in _chunks(slugs):
            for cc, slug, name in (await db.execute(
                select(SubnationalRegion.country_code, SubnationalRegion.slug, SubnationalRegion.name_ru)
                .where(SubnationalRegion.slug.in_(part)))).all():
                names.sub_regions[(cc, slug)] = name

    if any(r.kind == "world_rating" for r in refs):
        from app.data.world_concepts import WORLD_CONCEPTS
        names.concepts = {c.slug: c.name_ru for c in WORLD_CONCEPTS}
    return names


def _series_name(code: str, names: Names) -> str:
    if code in names.ru:
        return names.ru[code]
    if code in names.world:
        name, country = names.world[code]
        return f"{name} ({country})"
    return code


def content_title(ref: ContentRef, names: Names) -> str:
    """Название содержания простыми словами (без кодов, если справочник знает ряд)."""
    k = ref.kind
    if k == "ru":
        return names.ru.get(ref.code) or ref.code
    if k == "world":
        if ref.code in names.world:
            name, country = names.world[ref.code]
            return f"{name} — {country}"
        country = names.countries.get(ref.place, ("", ref.place))[1]
        return f"{ref.code} — {country}"
    if k == "region":
        ind = names.region_ind.get(ref.code) or ref.code
        return f"{ind} — {names.regions.get(ref.place) or ref.place}"
    if k == "region_map":
        return f"{names.region_ind.get(ref.code) or ref.code} — карта регионов"
    if k == "region_rating":
        return f"{names.region_ind.get(ref.code) or ref.code} — рейтинг регионов"
    if k == "regions_compare":
        return "Сравнение регионов: " + ", ".join(names.regions.get(s) or s for s in ref.codes) + _more_tail(ref)
    if k == "region_page":
        return f"{names.regions.get(ref.place) or ref.place} — страница региона"
    if k in ("world_region", "world_region_map"):
        country_slug, _, region_slug = ref.place.partition("/")
        cc, country = names.countries.get(country_slug, ("", country_slug))
        ind = names.sub_ind.get((cc, ref.code)) or ref.code
        if k == "world_region_map":
            return f"{ind} — карта регионов, {country}"
        region = names.sub_regions.get((cc, region_slug)) or region_slug
        return f"{ind} — {region}, {country}"
    if k == "compare":
        if not ref.codes:
            return "Сравнение"
        return "Сравнение: " + ", ".join(_series_name(c, names) for c in ref.codes) + _more_tail(ref)
    if k == "world_rating":
        return f"{names.concepts.get(ref.code) or ref.code} — рейтинг стран"
    if k == "research":
        return f"Отчёт «{ref.code}»"
    text = ref.code or SECTION_LABELS.get(ref.section, "страница")
    return text[:1].upper() + text[1:]


# ---------------------------------------------------------------------------
# Сбор за период
# ---------------------------------------------------------------------------

def period_for_window(window: str, today: date | None = None) -> Period:
    """Окно кнопки: «0» сегодня, «1» вчера, «N» последние N дней включая сегодня (МСК)."""
    from app.services.display import today_msk

    day = today or today_msk()
    if window == "0":
        return resolve_period("custom", day, day)
    if window == "1":
        y = day - timedelta(days=1)
        return resolve_period("custom", y, y)
    n = max(1, min(MAX_DAYS, int(window)))
    return resolve_period("custom", day - timedelta(days=n - 1), day)


async def _excluded_visitors(db: AsyncSession, visitors: set[str], period: Period) -> set[str]:
    """Роботы и своя активность среди посетителей выборки (правило витрин, ADR-0010)."""
    from app.services.analytics_marts import admin_identity

    out: set[str] = set()
    for part in _chunks(visitors):
        out |= set((await db.execute(
            select(ServerSession.visitor_id_hash).where(
                ServerSession.visitor_id_hash.in_(part),
                ServerSession.day >= period.start_date, ServerSession.day <= period.end_date,
                or_(ServerSession.is_bot.is_(True), ServerSession.is_internal.is_(True)),
            ).distinct())).scalars())
    _admin_users, admin_visitors = await admin_identity(db)
    return out | (admin_visitors & visitors)


async def _signup_times(db: AsyncSession, visitors: set[str]) -> dict[str, datetime]:
    """Посетитель → время создания самого раннего его аккаунта (через identity_links)."""
    # identity_links.user_id — строка, users.id — UUID: прямой JOIN на Postgres не сравнит типы.
    links: list[tuple[str, str]] = []
    for part in _chunks(visitors):
        links += [(v, u) for v, u in (await db.execute(
            select(IdentityLink.visitor_id_hash, IdentityLink.user_id)
            .where(IdentityLink.visitor_id_hash.in_(part)))).all()]
    ids: set[uuid.UUID] = set()
    for _v, u in links:
        try:
            ids.add(uuid.UUID(str(u)))
        except ValueError:
            continue
    created_by_user: dict[str, datetime] = {}
    id_list = sorted(ids, key=str)
    for i in range(0, len(id_list), _IN_CHUNK):
        for uid, created in (await db.execute(
            select(User.id, User.created_at).where(User.id.in_(id_list[i:i + _IN_CHUNK])))).all():
            if created is not None:
                created_by_user[str(uid)] = created.replace(tzinfo=None) if created.tzinfo else created
    out: dict[str, datetime] = {}
    for visitor, user in links:
        created = created_by_user.get(str(user))
        if created is not None and (visitor not in out or created < out[visitor]):
            out[visitor] = created
    return out


async def _session_portraits(db: AsyncSession, sessions: set[str]) -> dict[str, tuple[str, str, str]]:
    out: dict[str, tuple[str, str, str]] = {}
    for part in _chunks(sessions):
        for sid, channel, device, country in (await db.execute(
            select(BehaviorSession.session_id_hash, BehaviorSession.channel,
                   BehaviorSession.device_type, BehaviorSession.country)
            .where(BehaviorSession.session_id_hash.in_(part)))).all():
            out[sid] = (channel or "unknown", device or "unknown", country or "")
    return out


def _person(visitor: str | None, session: str | None) -> str:
    return visitor or (f"s:{session}" if session else "")


async def collect(db: AsyncSession, period: Period) -> dict[str, Any]:
    """Строки событий с содержанием и сводка: что скачали, где упёрлись, кто потом вошёл."""
    raw = (await db.execute(
        select(FrontendEvent.occurred_at, FrontendEvent.event_name, FrontendEvent.session_id_hash,
               FrontendEvent.visitor_id_hash, FrontendEvent.user_id, FrontendEvent.authed,
               FrontendEvent.url, FrontendEvent.params_json)
        .where(FrontendEvent.event_name.in_(sorted(ALL_EVENTS)),
               FrontendEvent.occurred_at >= period.start, FrontendEvent.occurred_at < period.end)
        .order_by(FrontendEvent.occurred_at)
    )).all()
    visitors = {r.visitor_id_hash for r in raw if r.visitor_id_hash}
    excluded = await _excluded_visitors(db, visitors, period) if visitors else set()
    from app.services.analytics_marts import admin_identity
    admin_users, _ = await admin_identity(db)
    kept = [r for r in raw
            if r.visitor_id_hash not in excluded and not (r.user_id and r.user_id in admin_users)]

    refs = [content_ref(r.event_name, r.params_json if isinstance(r.params_json, dict) else {}, r.url) for r in kept]
    # Серверный счёт отказов 403 (wall_counter): путь страницы → то же содержание, что у событий.
    from app.services.wall_counter import read_walls
    server_counts = await read_walls(period)
    server_refs = {f: content_ref("download_limit", {}, f.split("|", 1)[1]) for f in (server_counts or {})}
    names = await load_names(db, refs + list(server_refs.values()))
    wall_visitors = {r.visitor_id_hash for r in kept if r.event_name in WALL_EVENTS and r.visitor_id_hash}
    signups = await _signup_times(db, wall_visitors) if wall_visitors else {}
    portraits = await _session_portraits(db, {r.session_id_hash for r in kept if r.session_id_hash})

    rows: list[dict[str, Any]] = []
    for r, ref in zip(kept, refs):
        is_wall = r.event_name in WALL_EVENTS
        signed = None
        if is_wall and r.visitor_id_hash:
            created = signups.get(r.visitor_id_hash)
            signed = bool(created and created >= r.occurred_at - _SIGNUP_SLACK)
        channel, device, country = portraits.get(r.session_id_hash or "", ("unknown", "unknown", ""))
        segs, query = _path_parts(r.url)
        mode = (query.get("mode") or [""])[0]
        rows.append({
            "at": r.occurred_at,
            "event": r.event_name,
            "wall": is_wall,
            "what": (WALL_LABELS if is_wall else FORMAT_LABELS).get(r.event_name, r.event_name),
            "title": content_title(ref, names),
            "key": ref.key,
            "section": ref.section,
            "page": "/" + "/".join(segs) + (f"?mode={mode}" if mode else ""),
            "authed": bool(r.authed),
            "person": _person(r.visitor_id_hash, r.session_id_hash),
            "session": r.session_id_hash,  # только для «Пути до упора», в файлы не выводится
            "signed_up_after": signed,
            "channel": channel,
            "device": device,
            "country": country,
        })
    summary = summarize(rows)
    summary["server"] = server_summary(
        server_counts, {f: content_title(ref, names) for f, ref in server_refs.items()},
        browser=sum(1 for r in raw if r.event_name == "download_limit"))
    return {"period": period, "rows": rows, "summary": summary}


def server_summary(counts: dict[str, int] | None, titles: dict[str, str], *, browser: int) -> dict[str, Any]:
    """Сервер против браузера по упорам в лимит скачиваний. `count=None` — Redis не ответил.
    `browser` — все события `download_limit` за период, до исключения роботов (сервер их тоже не отличает)."""
    items = []
    for field, n in sorted((counts or {}).items(), key=lambda kv: -kv[1]):
        fmt, _, path = field.partition("|")
        items.append({"title": titles.get(field) or path, "path": path, "format": fmt, "count": n})
    return {"count": None if counts is None else sum(counts.values()), "browser": browser, "items": items}


def _walls_by_device(walls: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Упёрлись и зарегистрировались потом — по устройству (14.11.2026: телефон 7 % против компьютера 29 %;
    замер после окна стены с входом в одно касание). Человек считается один раз на устройство."""
    people: dict[str, dict[str, set]] = {}
    for r in walls:
        if not r.get("person"):
            continue
        cell = people.setdefault(r.get("device") or "unknown", {"people": set(), "signed": set()})
        cell["people"].add(r["person"])
        if r.get("signed_up_after"):
            cell["signed"].add(r["person"])
    order = sorted(people.items(), key=lambda kv: -len(kv[1]["people"]))
    return {device: {"people": len(c["people"]), "signed": len(c["signed"])} for device, c in order}


def _device_line(by_device: dict[str, dict[str, int]] | None) -> str:
    if not by_device:
        return ""
    parts = [f"{DEVICE_LABELS.get(d, d)} {_n(c['signed'])} из {_n(c['people'])} ({_pct(c['signed'], c['people'])})"
             for d, c in by_device.items() if c["people"]]
    return "Со стены зарегистрировались: " + " · ".join(parts) if parts else ""


def summarize(rows: list[dict[str, Any]], top: int = 10) -> dict[str, Any]:
    """Сводка по строкам `collect` (чистая функция: тестируется без базы)."""
    dl = [r for r in rows if not r["wall"]]
    wl = [r for r in rows if r["wall"]]

    def by_content(items: list[dict[str, Any]], *, walls: bool) -> list[dict[str, Any]]:
        groups: dict[str, dict[str, Any]] = {}
        for r in items:
            g = groups.setdefault(r["key"], {"title": r["title"], "section": r["section"], "count": 0,
                                             "people": set(), "what": Counter(), "signed": set()})
            g["count"] += 1
            if r["person"]:
                g["people"].add(r["person"])
            g["what"][r["what"]] += 1
            if walls and r["signed_up_after"]:
                g["signed"].add(r["person"])
        out = []
        for g in sorted(groups.values(), key=lambda g: (-len(g["people"]), -g["count"], g["title"])):
            out.append({"title": g["title"], "section": g["section"], "count": g["count"],
                        "people": len(g["people"]) or g["count"], "what": dict(g["what"].most_common()),
                        "signed_up": len(g["signed"])})
        return out

    dl_people = {r["person"] for r in dl if r["person"]}
    wall_people = {r["person"] for r in wl if r["person"]}
    signed_people = {r["person"] for r in wl if r["signed_up_after"]}
    guest_people = {r["person"] for r in dl if r["person"] and not r["authed"]}
    return {
        "downloads": {
            "count": len(dl), "people": len(dl_people),
            "guest_people": len(guest_people), "authed_people": len(dl_people - guest_people),
            "by_what": dict(Counter(r["what"] for r in dl).most_common()),
            "by_section": dict(Counter(r["section"] for r in dl).most_common()),
            "by_channel": dict(Counter(r["channel"] for r in dl).most_common()),
            "top": by_content(dl, walls=False)[:top],
            "contents": len({r["key"] for r in dl}),
        },
        "walls": {
            "count": len(wl), "people": len(wall_people), "signed_up": len(signed_people),
            "by_what": dict(Counter(r["what"] for r in wl).most_common()),
            "by_channel": dict(Counter(r["channel"] for r in wl).most_common()),
            "by_device": _walls_by_device(wl),
            "top": by_content(wl, walls=True)[:top],
            "contents": len({r["key"] for r in wl}),
        },
    }


# ---------------------------------------------------------------------------
# Текст для Telegram
# ---------------------------------------------------------------------------

def _n(v: int) -> str:
    return f"{v:,}".replace(",", " ")


def _pct(part: int, whole: int) -> str:
    return f"{round(100 * part / whole)} %" if whole else "—"


def _people(n: int) -> str:
    tail = n % 100
    if 11 <= tail <= 14:
        word = "человек"
    elif n % 10 == 1:
        word = "человек"
    elif n % 10 in (2, 3, 4):
        word = "человека"
    else:
        word = "человек"
    return f"{_n(n)} {word}"


def _mix(mapping: dict[str, int], labels: dict[str, str] | None = None, limit: int = 6) -> str:
    items = list(mapping.items())[:limit]
    return " · ".join(f"{escape((labels or {}).get(k, k))} {_n(v)}" for k, v in items)


_TITLE_LIMIT = 90


def _short(title: str, limit: int = _TITLE_LIMIT) -> str:
    """Название для текста Telegram: длинные названия рядов Росстата режем (в Excel — полностью)."""
    return escape(title if len(title) <= limit else title[:limit - 1].rstrip() + "…")


def _times(n: int) -> str:
    tail = n % 100
    if n % 10 in (2, 3, 4) and not 12 <= tail <= 14:
        return f"{_n(n)} раза"
    return f"{_n(n)} раз"


def _server_line(server: dict[str, Any] | None) -> str:
    """«Лимит скачиваний: сервер видел упоров N / браузер сообщил M» (обе цифры с роботами)."""
    if not server:
        return ""
    if server["count"] is None:
        return f"Лимит скачиваний: сервер — нет ответа счётчика / браузер сообщил {_n(server['browser'])}"
    if not server["count"] and not server["browser"]:
        return ""
    return (f"Лимит скачиваний: сервер видел упоров {_n(server['count'])} / "
            f"браузер сообщил {_n(server['browser'])}")


def format_report(summary: dict[str, Any], period_label: str, *, top: int = 10) -> str:
    """Отчёт «Что скачивают»: сначала смысл, подробности — в раскрывающемся блоке."""
    d, w = summary["downloads"], summary["walls"]
    lines = [f"📥 <b>Что скачивают — {escape(period_label)}</b>"]
    if not d["count"] and not w["count"]:
        lines.append("За этот срок никто ничего не скачивал и в лимит не упирался.")
        if _server_line(summary.get("server")):
            lines.append(_server_line(summary.get("server")))
        return "\n".join(lines)

    if d["count"]:
        lines.append(
            f"Скачали {_times(d['count'])}: {_people(d['people'])} "
            f"(гости {_n(d['guest_people'])}, с аккаунтом {_n(d['authed_people'])})")
    else:
        lines.append("Скачиваний не было.")
    if w["count"]:
        lines.append(
            f"Упёрлись в лимит: {_people(w['people'])} ({_times(w['count'])}), "
            f"из них зарегистрировались {_n(w['signed_up'])} ({_pct(w['signed_up'], w['people'])}), "
            f"ушли без регистрации {_n(w['people'] - w['signed_up'])}")
    server_line = _server_line(summary.get("server"))
    if server_line:
        lines.append(server_line)

    if d["top"]:
        lines.append("")
        lines.append("<b>Что скачивали</b>")
        for i, item in enumerate(d["top"][:top], 1):
            lines.append(f"{i}. {_short(item['title'])} — {_people(item['people'])} · {_mix(item['what'], limit=3)}")
    if w["top"]:
        lines.append("")
        lines.append("<b>Где упёрлись в лимит</b>")
        for i, item in enumerate(w["top"][:top], 1):
            tail = f", зарегистрировались {_n(item['signed_up'])}" if item["signed_up"] else ""
            lines.append(f"{i}. {_short(item['title'])} — {_people(item['people'])}{tail}")

    details = []
    if d["by_what"]:
        details.append(f"Как скачивали: {_mix(d['by_what'])}")
    if d["by_section"]:
        details.append(f"Разделы: {_mix(d['by_section'], SECTION_LABELS)}")
    if d["by_channel"]:
        details.append(f"Откуда пришли скачавшие: {_mix(d['by_channel'], CHANNEL_LABELS)}")
    if w["by_what"]:
        details.append(f"Что не дал лимит: {_mix(w['by_what'])}")
    if w["by_channel"]:
        details.append(f"Откуда пришли упёршиеся: {_mix(w['by_channel'], CHANNEL_LABELS)}")
    device_line = _device_line(w.get("by_device"))
    if device_line:
        details.append(device_line)
    details.append(f"Разных страниц: скачивали {_n(d['contents'])}, упирались {_n(w['contents'])}")
    lines.append("")
    lines.append(f"<blockquote expandable>{chr(10).join(details)}</blockquote>")
    lines.append("Роботы и наши собственные заходы не считаются. Полный список — кнопкой «Файл Excel».")
    return "\n".join(lines)


def digest_lines(summary: dict[str, Any], top: int = 3) -> list[str]:
    """Короткий блок для утреннего дайджеста: пусто, если за день ничего не было."""
    d, w = summary["downloads"], summary["walls"]
    if not d["count"] and not w["count"]:
        return []
    out = ["", "📥 <b>Что скачивали вчера</b>"]
    if d["top"]:
        out.append(f"Скачали {_people(d['people'])}: " + "; ".join(
            f"{_short(i['title'], 60)} ({_n(i['people'])})" for i in d["top"][:top]))
    if w["top"]:
        out.append(
            f"Упёрлись в лимит {_people(w['people'])}, зарегистрировались {_n(w['signed_up'])}: "
            + "; ".join(f"{_short(i['title'], 60)} ({_n(i['people'])})" for i in w["top"][:top]))
    out.append("Подробно — кнопка «📥 Скачивания» в меню.")
    return out


def _delta(cur: int, prev: int) -> str:
    if not prev:
        return ""
    diff = cur - prev
    return f" ({'+' if diff > 0 else '−' if diff < 0 else '±'}{_n(abs(diff))} к прошлой неделе)"


def week_digest_lines(summary: dict[str, Any], prev: dict[str, Any] | None, label: str, top: int = 5) -> list[str]:
    """Недельный блок понедельничного дайджеста (вместо дневного, отдельного сообщения нет —
    спокойный режим 08.11.2026). Пусто, если за неделю ничего не было."""
    d, w = summary["downloads"], summary["walls"]
    if not d["count"] and not w["count"]:
        return []
    pd = (prev or {}).get("downloads", {})
    pw = (prev or {}).get("walls", {})
    out = ["", f"📥 <b>Что скачивали за неделю ({escape(label)})</b>"]
    out.append(f"Скачали {_people(d['people'])}{_delta(d['people'], pd.get('people', 0))}")
    if w["count"]:
        out.append(
            f"Упёрлись в лимит {_people(w['people'])}{_delta(w['people'], pw.get('people', 0))}, "
            f"зарегистрировались {_n(w['signed_up'])} ({_pct(w['signed_up'], w['people'])})")
    server_line = _server_line(summary.get("server"))
    if server_line:
        out.append(server_line)
    if d["top"]:
        out.append("Чаще скачивали: " + "; ".join(
            f"{_short(i['title'], 60)} ({_n(i['people'])})" for i in d["top"][:top]))
    if w["top"]:
        out.append("Чаще упирались: " + "; ".join(
            f"{_short(i['title'], 60)} ({_n(i['people'])})" for i in w["top"][:top]))
    out.append("Подробно и файлом — кнопка «📥 Скачивания» → «7 дней».")
    return out


# ---------------------------------------------------------------------------
# Файл Excel
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Путь до упора (утверждено 14.11.2026: окно ≤ 30 дней, лёгкий ограниченный запрос)
# ---------------------------------------------------------------------------

PATH_MAX_DAYS = 30
PATH_TIMEOUT_MS = 10_000
PATH_ROW_CAP = 20_000
PATH_STEPS = 6
PATH_TOO_LONG = (f"Слишком большой период: путь до упора строится не больше чем за {PATH_MAX_DAYS} дней. "
                 "Возьмите срок короче.")
PATH_TIMEOUT = "База не успела ответить за 10 секунд — путь до упора не построен. Повторите позже или возьмите срок короче."


def _page_label(page: str, titles: dict[str, str]) -> str:
    path = (page or "").split("?")[0].split("#")[0] or "/"
    if path == "/":
        return "главная"
    return titles.get(path) or path


def build_paths(rows: list[dict[str, Any]], pageviews: list[tuple[str, str, datetime]],
                titles: dict[str, str]) -> list[dict[str, Any]]:
    """Чистая сборка: для каждого упора — страницы той же сессии до него (последние PATH_STEPS без повторов
    подряд), зарегистрировался ли потом, скачал ли то же содержание после упора."""
    by_session: dict[str, list[tuple[datetime, str]]] = {}
    for session, page, at in pageviews:
        by_session.setdefault(session, []).append((at, page))
    for views in by_session.values():
        views.sort()
    out = []
    for r in rows:
        if not r["wall"]:
            continue
        views = [p for at, p in by_session.get(r.get("session") or "", []) if at <= r["at"]]
        labels: list[str] = []
        for page in views:
            label = _page_label(page, titles)
            if not labels or labels[-1] != label:
                labels.append(label)
        same_after = any(
            o["person"] == r["person"] and not o["wall"] and o["key"] == r["key"] and o["at"] > r["at"]
            for o in rows) if r["person"] else False
        out.append({
            "at": r["at"], "person": r["person"], "title": r["title"], "what": r["what"], "channel": r["channel"],
            "pages_before": len(views), "path": labels[-PATH_STEPS:], "signed_up_after": r["signed_up_after"],
            "same_after": same_after,
        })
    return out


async def collect_paths(db: AsyncSession, data: dict[str, Any]) -> dict[str, Any]:
    """Просмотры страниц в сессиях упоров (`behavior_events`, индекс по сессии), с потолком времени запроса
    и числа строк. Период длиннее 30 дней не считается: `status="too_long"`."""
    from app.database import set_local_statement_timeout
    from app.models import BehaviorEvent

    period: Period = data["period"]
    if period.days > PATH_MAX_DAYS:
        return {"status": "too_long", "items": []}
    walls = [r for r in data["rows"] if r["wall"]]
    sessions = sorted({r["session"] for r in walls if r.get("session")})
    if not sessions:
        return {"status": "ok", "items": build_paths(data["rows"], [], {}), "cut": False}
    pageviews: list[tuple[str, str, datetime]] = []
    cut = False
    try:
        await set_local_statement_timeout(db, PATH_TIMEOUT_MS)
        for i in range(0, len(sessions), _IN_CHUNK):
            part = sessions[i:i + _IN_CHUNK]
            got = (await db.execute(
                select(BehaviorEvent.session_id_hash, BehaviorEvent.page, BehaviorEvent.occurred_at)
                .where(BehaviorEvent.session_id_hash.in_(part), BehaviorEvent.event_type == "pageview",
                       BehaviorEvent.occurred_at >= period.start - timedelta(hours=6),
                       BehaviorEvent.occurred_at < period.end)
                .limit(PATH_ROW_CAP - len(pageviews) + 1)
            )).all()
            pageviews += [(s, p or "/", at) for s, p, at in got]
            if len(pageviews) > PATH_ROW_CAP:
                pageviews, cut = pageviews[:PATH_ROW_CAP], True
                break
    except Exception:  # noqa: BLE001 — в т.ч. statement timeout: лист скажет словами, файл уйдёт
        logger.warning("download paths query failed", exc_info=True)
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return {"status": "timeout", "items": []}
    paths = {(p or "/").split("?")[0].split("#")[0] for _s, p, _a in pageviews}
    refs = {p: content_ref("download_limit", {}, p) for p in paths if p != "/"}
    names = await load_names(db, refs.values())
    titles = {p: content_title(ref, names) for p, ref in refs.items() if ref.kind != "page"}
    return {"status": "ok", "items": build_paths(data["rows"], pageviews, titles), "cut": cut}


def _paths_sheet_rows(paths: dict[str, Any], anonymous: bool = False) -> list[list[Any]]:
    if paths["status"] == "too_long":
        return [[PATH_TOO_LONG, "", "", "", "", "", "", ""]]
    if paths["status"] == "timeout":
        return [[PATH_TIMEOUT, "", "", "", "", "", "", ""]]
    yes_no = {True: "да", False: "нет", None: ""}
    out = [[(i["at"] + MSK_OFFSET).strftime("%d.%m.%Y %H:%M"), _who(i["person"], anonymous), i["title"], i["what"],
            CHANNEL_LABELS.get(i["channel"], i["channel"]), i["pages_before"], " → ".join(i["path"]),
            yes_no[i["signed_up_after"]], yes_no[i["same_after"]]] for i in paths["items"]]
    if paths.get("cut"):
        out.append([f"Показаны первые {PATH_ROW_CAP} просмотров страниц — возьмите срок короче.",
                    "", "", "", "", "", "", "", ""])
    return out


def _who(person: str | None, anonymous: bool) -> str:
    """Короткий хэш посетителя; в роли «только отчёты» (anonymous) — пусто."""
    return "" if anonymous else (person or "")[:10]


def build_xlsx(data: dict[str, Any], *, anonymous: bool = False) -> bytes:
    """Книга: «Сводка», «Что скачивали», «Где упёрлись», «Все события» (время МСК), при наличии —
    «Путь до упора» и «Сервер — упоры». `anonymous=True` (роль «только отчёты») — без хэшей посетителей."""
    from openpyxl import Workbook
    from openpyxl.styles import Font

    summary = summarize(data["rows"], top=10_000)
    period: Period = data["period"]
    wb = Workbook()
    bold = Font(bold=True)

    def sheet(ws, header: list[str], rows: Iterable[list[Any]], widths: list[int]) -> None:
        ws.append(header)
        for cell in ws[1]:
            cell.font = bold
        for row in rows:
            ws.append(row)
        for i, width in enumerate(widths):
            ws.column_dimensions[chr(ord("A") + i)].width = width
        ws.freeze_panes = "A2"

    d, w = summary["downloads"], summary["walls"]
    ws = wb.active
    ws.title = "Сводка"
    sheet(ws, ["Показатель", "Значение"], [
        ["Период", period.label],
        ["Скачиваний", d["count"]],
        ["Скачивали, человек", d["people"]],
        ["из них гости", d["guest_people"]],
        ["из них с аккаунтом", d["authed_people"]],
        ["Упоров в лимит", w["count"]],
        ["Упёрлись, человек", w["people"]],
        ["Зарегистрировались после упора, человек", w["signed_up"]],
        *[[f"Скачано: {k}", v] for k, v in d["by_what"].items()],
        *[[f"Раздел: {SECTION_LABELS.get(k, k)}", v] for k, v in d["by_section"].items()],
        *[[f"Откуда пришли скачавшие: {CHANNEL_LABELS.get(k, k)}", v] for k, v in d["by_channel"].items()],
        *[[f"Не дал лимит: {k}", v] for k, v in w["by_what"].items()],
        *[[f"Со стены зарегистрировались, {DEVICE_LABELS.get(d, d)}", f"{c['signed']} из {c['people']}"]
          for d, c in (w.get("by_device") or {}).items()],
        *_server_rows(data["summary"].get("server") if "summary" in data else None),
        ["Примечание", "Роботы и собственные заходы исключены. Человек = посетитель сайта (браузер)."],
    ], [48, 60])
    sheet(wb.create_sheet("Что скачивали"), ["Что", "Раздел", "Человек", "Скачиваний", "Как скачивали"], [
        [i["title"], SECTION_LABELS.get(i["section"], i["section"]), i["people"], i["count"],
         ", ".join(f"{k} {v}" for k, v in i["what"].items())]
        for i in d["top"]
    ], [70, 18, 10, 12, 40])
    sheet(wb.create_sheet("Где упёрлись"), ["Что", "Раздел", "Человек", "Упоров", "Что не дал лимит",
                                             "Зарегистрировались потом"], [
        [i["title"], SECTION_LABELS.get(i["section"], i["section"]), i["people"], i["count"],
         ", ".join(f"{k} {v}" for k, v in i["what"].items()), i["signed_up"]]
        for i in w["top"]
    ], [70, 18, 10, 10, 34, 14])
    sheet(wb.create_sheet("Все события"), [
        "Время (МСК)", "Действие", "Что именно", "Что", "Раздел", "Страница", "Аккаунт",
        "Посетитель", "Зарегистрировался потом", "Откуда пришёл", "Устройство", "Страна",
    ], [
        [(r["at"] + MSK_OFFSET).strftime("%d.%m.%Y %H:%M"),
         "упёрся в лимит" if r["wall"] else "скачал", r["what"], r["title"],
         SECTION_LABELS.get(r["section"], r["section"]), r["page"], "да" if r["authed"] else "гость",
         _who(r["person"], anonymous), {True: "да", False: "нет", None: ""}[r["signed_up_after"]],
         CHANNEL_LABELS.get(r["channel"], r["channel"]), DEVICE_LABELS.get(r["device"], r["device"]),
         r["country"]]
        for r in data["rows"]
    ], [17, 15, 24, 60, 16, 50, 9, 12, 12, 16, 12, 14])
    if data.get("paths") is not None:
        sheet(wb.create_sheet("Путь до упора"), [
            "Время упора (МСК)", "Посетитель", "Где упёрся", "Что не дал лимит", "Откуда пришёл",
            "Страниц до упора", "Последние страницы до упора", "Зарегистрировался потом", "Скачал то же потом",
        ], _paths_sheet_rows(data["paths"], anonymous), [17, 12, 60, 24, 16, 10, 90, 14, 14])
    server = (data.get("summary") or {}).get("server")
    if server is not None:
        sheet(wb.create_sheet("Сервер — упоры"), ["Что", "Страница", "Формат", "Отказов"], [
            [i["title"], i["path"], i["format"], i["count"]] for i in server["items"]
        ] + [["Примечание", "Счёт сервера: каждый отказ 403 по лимиту скачиваний, включая роботов; "
              "без IP и идентификаторов. Браузер не сообщает об упоре, если посетитель отказался от "
              "аналитики или стоит блокировщик.", "", ""]], [70, 50, 10, 10])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _server_rows(server: dict[str, Any] | None) -> list[list[Any]]:
    if not server:
        return []
    count = "нет ответа счётчика" if server["count"] is None else server["count"]
    return [["Лимит скачиваний: сервер видел упоров", count],
            ["Лимит скачиваний: браузер сообщил (с роботами)", server["browser"]]]


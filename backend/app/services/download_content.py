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


def _from_subject(params: dict, segs: list[str]) -> ContentRef | None:
    """Явное содержание события (`code`, `country`, `region`, `codes`, `regions`; фронт с 14.11.2026,
    `lib/downloadSubject.js`). Вид страницы — по префиксу прежнего параметра `indicator`."""
    codes, regions = _split(params.get("codes")), _split(params.get("regions"))
    if codes:
        return ContentRef("compare", "compare", codes=codes)
    if regions:
        return ContentRef("region", "regions_compare", codes=regions)
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
        return "Сравнение регионов: " + ", ".join(names.regions.get(s) or s for s in ref.codes)
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
        return "Сравнение: " + ", ".join(_series_name(c, names) for c in ref.codes)
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
    names = await load_names(db, refs)
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
            "signed_up_after": signed,
            "channel": channel,
            "device": device,
            "country": country,
        })
    return {"period": period, "rows": rows, "summary": summarize(rows)}


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


def format_report(summary: dict[str, Any], period_label: str, *, top: int = 10) -> str:
    """Отчёт «Что скачивают»: сначала смысл, подробности — в раскрывающемся блоке."""
    d, w = summary["downloads"], summary["walls"]
    lines = [f"📥 <b>Что скачивают — {escape(period_label)}</b>"]
    if not d["count"] and not w["count"]:
        lines.append("За этот срок никто ничего не скачивал и в лимит не упирался.")
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


# ---------------------------------------------------------------------------
# Файл Excel
# ---------------------------------------------------------------------------

def build_xlsx(data: dict[str, Any]) -> bytes:
    """Книга: «Сводка», «Что скачивали», «Где упёрлись», «Все события» (время МСК)."""
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
         (r["person"] or "")[:10], {True: "да", False: "нет", None: ""}[r["signed_up_after"]],
         CHANNEL_LABELS.get(r["channel"], r["channel"]), DEVICE_LABELS.get(r["device"], r["device"]),
         r["country"]]
        for r in data["rows"]
    ], [17, 15, 24, 60, 16, 50, 9, 12, 12, 16, 12, 14])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


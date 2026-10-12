"""Приоритетный шард sitemap: самые ценные страницы первыми (круг 13, SEO).

В sitemap каждого хоста ~10 млн адресов (1 028 файлов по 10 000). Googlebot
берёт из программных страниц доли процента, потому что порядок обхода ему
ничего не говорит. ``sitemap-priority.xml`` ставится первым в ``sitemap.xml``
и перечисляет:

* целиком простые секции-хабы (главная, разделы, рейтинги, карты, регионы
  России, страны, календарь, рейтинги мира);
* карточки показателей стран, на которых строятся рейтинги мира (ключевые
  мировые показатели);
* годовые страницы текущего и прошлого года у показателей России;
* страницы, которые уже получали показы и клики (Google Search Console за
  90 дней), визиты (``daily_pages`` за 30 дней) и страницы, на которые
  маршрутизируются поисковые запросы Яндекса (``webmaster_search_queries``).

Шард не заменяет остальные: те же адреса остаются в своих шардах. Состав
выбирается из тех же страниц, что идут в ночную сборку, поэтому в нём нет
редиректов, 404 и noindex (последнее проверяет ``_publish_section``), а
``lastmod`` — тот самый, что у страницы в основном шарде (дата данных).
Ошибка загрузки спроса не ломает сборку: шард собирается из хабов.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from urllib.parse import unquote, urlparse

from sqlalchemy import func, select

from app.services.site_urls import SiteUrl

logger = logging.getLogger(__name__)

PRIORITY_SECTION = "priority"

# Секции-хабы, которые входят целиком (в порядке публикации в шарде).
WHOLE_SECTIONS = (
    "core", "today", "ratings", "maps", "regions", "world-ratings", "world", "calendar",
)

# Веса источников спроса: итоговый балл страницы — сумма весов по рангам.
_W_GSC = 1.0
_W_WEBMASTER = 0.9
_W_KEY_WORLD = 0.8
_W_VISITS = 0.6
_W_YEARS = 0.5

_GSC_DAYS = 90
_VISITS_DAYS = 30
_WEBMASTER_DAYS = 90
_GSC_LIMIT = 30_000
_VISITS_LIMIT = 20_000
_WEBMASTER_LIMIT = 3_000
# Клик ценнее показа: страница, которую открывали из выдачи, нужна в индексе.
_CLICK_WEIGHT = 25


@dataclass(slots=True)
class PriorityPlan:
    """Что хотим видеть в приоритетном шарде, ещё не сверено с реестром."""

    scores: dict[str, float] = field(default_factory=dict)
    sources: dict[str, int] = field(default_factory=dict)

    def add(self, path: str | None, score: float) -> None:
        if not path or not path.startswith("/") or "?" in path or "#" in path:
            return
        self.scores[path] = self.scores.get(path, 0.0) + score

    def add_ranked(self, paths: list[str], weight: float, source: str) -> None:
        """Путь на первом месте получает ``weight``, на последнем — почти 0."""
        normalized = [item for item in map(normalize_demand_path, paths) if item is not None]
        total = len(normalized)
        added = 0
        for index, path in enumerate(normalized):
            self.add(path, weight * (1.0 - index / total))
            added += 1
        self.sources[source] = added


def normalize_demand_path(value: str | None) -> str | None:
    """Адрес из GSC/аналитики → путь без хоста; запросные и якорные варианты — None."""
    if not value:
        return None
    raw = value.strip()
    parsed = urlparse(raw)
    if parsed.query or parsed.fragment:
        return None
    path = unquote(parsed.path or "")
    if not path.startswith("/"):
        return None
    if len(path) > 1:
        path = path.rstrip("/")
    return path or "/"


async def load_priority_plan(db, today: date) -> PriorityPlan:
    """Собрать спрос. Каждый источник независим: сбой одного не отменяет остальные."""
    plan = PriorityPlan()
    for loader in (_load_gsc, _load_webmaster, _load_key_world_cards, _load_visits):
        try:
            await loader(db, plan, today)
        except Exception:  # noqa: BLE001 — спрос не должен ломать публикацию sitemap
            logger.warning("Priority sitemap: source %s failed", loader.__name__, exc_info=True)
            try:
                await db.rollback()
            except Exception:  # noqa: BLE001
                pass
    return plan


async def _load_gsc(db, plan: PriorityPlan, today: date) -> None:
    from app.models import GscSearchQuery

    since = today - timedelta(days=_GSC_DAYS)
    score = func.coalesce(func.sum(GscSearchQuery.impressions), 0) + _CLICK_WEIGHT * func.coalesce(
        func.sum(GscSearchQuery.clicks), 0
    )
    rows = (await db.execute(
        select(GscSearchQuery.page)
        .where(GscSearchQuery.date >= since, GscSearchQuery.page.is_not(None))
        .group_by(GscSearchQuery.page)
        .order_by(score.desc())
        .limit(_GSC_LIMIT)
    )).all()
    plan.add_ranked([page for (page,) in rows], _W_GSC, "gsc")


async def _load_webmaster(db, plan: PriorityPlan, today: date) -> None:
    from app.services.demand_router import build_demand_routes

    del today
    routes = await build_demand_routes(db, days=_WEBMASTER_DAYS, limit=_WEBMASTER_LIMIT)
    best: dict[str, int] = {}
    for route in routes:
        if route.matched and route.path:
            best[route.path] = max(best.get(route.path, 0), route.impressions)
    ranked = sorted(best, key=lambda p: -best[p])
    plan.add_ranked(ranked, _W_WEBMASTER, "webmaster")


async def _load_key_world_cards(db, plan: PriorityPlan, today: date) -> None:
    """Карточки стран, из которых собраны рейтинги мира."""
    del today
    from app.data.world_concepts import WORLD_CONCEPTS
    from app.services import site_paths as paths
    from app.services.seo_world import _world_rating_members

    found: list[str] = []
    for concept in WORLD_CONCEPTS:
        if "rating" not in concept.enabled_surfaces:
            continue
        for country, indicator in await _world_rating_members(db, concept):
            found.append(paths.indicator(country.slug, indicator.code))
    for path in found:
        plan.add(path, _W_KEY_WORLD)
    plan.sources["key_world"] = len(set(found))


async def _load_visits(db, plan: PriorityPlan, today: date) -> None:
    from app.models import DailyPage

    since = today - timedelta(days=_VISITS_DAYS)
    visitors = func.sum(DailyPage.visitors)
    rows = (await db.execute(
        select(DailyPage.page)
        .where(DailyPage.day >= since)
        .group_by(DailyPage.page)
        .having(func.sum(DailyPage.views) >= 3, visitors >= 2)
        .order_by(visitors.desc())
        .limit(_VISITS_LIMIT)
    )).all()
    plan.add_ranked([page for (page,) in rows], _W_VISITS, "visits")


def _is_recent_year_page(path: str, today: date) -> bool:
    """/russia/indicator/{code}/{год}: текущий и прошлый год."""
    parts = path.strip("/").split("/")
    return (
        len(parts) == 4
        and parts[1] == "indicator"
        and parts[3] in {str(today.year), str(today.year - 1)}
    )


class PriorityCollector:
    """Отбирает адреса приоритетного шарда из потока секций ночной сборки.

    Реестр не копится: сохраняются только хабы целиком и адреса из плана,
    поэтому память ограничена размером шарда.
    """

    def __init__(self, plan: PriorityPlan, today: date, max_urls: int):
        self.plan = plan
        self.today = today
        self.max_urls = max(0, int(max_urls))
        self._whole: dict[str, list[SiteUrl]] = {name: [] for name in WHOLE_SECTIONS}
        self._picked: dict[str, tuple[float, SiteUrl]] = {}

    def feed(self, section: str, urls: list[SiteUrl]) -> None:
        if self.max_urls == 0:
            return
        if section in self._whole:
            self._whole[section].extend(urls)
            return
        scores = self.plan.scores
        for url in urls:
            score = scores.get(url.path, 0.0)
            if score <= 0.0 and section == "years" and _is_recent_year_page(url.path, self.today):
                score = _W_YEARS
            if score > 0.0 and url.path not in self._picked:
                self._picked[url.path] = (score, url)

    def result(self) -> list[SiteUrl]:
        if self.max_urls == 0:
            return []
        seen: set[str] = set()
        out: list[SiteUrl] = []
        for name in WHOLE_SECTIONS:
            for url in self._whole[name]:
                if url.path not in seen:
                    seen.add(url.path)
                    out.append(url)
        room = max(0, self.max_urls - len(out))
        extras = sorted(
            (item for path, item in self._picked.items() if path not in seen),
            key=lambda item: (-item[0], item[1].path),
        )
        out.extend(url for _score, url in extras[:room])
        return out[: self.max_urls]

"""Маршрутизатор спроса: поисковые запросы → наши страницы.

Замыкает контур «спрос → картинка → визит»: запросы из
`webmaster_search_queries` (сбор — `analytics_backfill`) матчатся на URL,
которые мы реально отдаём (карточки, годовые лендинги, категории), ранжируются
по потерянным показам (показ есть — клика нет) и отдаются:
- в приоритетный переобход Вебмастера (`webmaster_recrawl.submit_paths`),
  чтобы Яндекс переобошёл именно страницы со свежим постером и таблицей;
- в отчёт владельцу в Telegram (что люди ищут, куда попадают, где дыра).

Матчинг трёхслойный: точные словари (имена индикаторов/категорий/источники),
год из запроса, синонимы (инфляция→cpi, курс доллара→usd-rub, …). Никаких
LLM — детерминированно, быстро и воспроизводимо.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Indicator
from app.services.site_paths import russia_indicator, russia_indicator_year

# --- Словарь соответствия «корни запроса → код индикатора» -------------------
# Каждый ключ — КОРТЕЖ ОБЯЗАТЕЛЬНЫХ СТЕМОВ (lowercase): матч есть, когда все
# стемы присутствуют в запросе в виде подстрок, порядок слов не важен. Это
# обходит русскую морфологию: «ставк по вклад» не ловил «ставка по вкладам»,
# потому что прилагательное слева от пробела меняет падежное окончание.
# Проверяются по убыванию суммарной длины стемов, первый hit выигрывает —
# специфичные корни («процент по вклад») бьют общие («вклад»). Пополняется
# по факту спроса: новые бакеты — новые строки.
_SYNONYMS: tuple[tuple[tuple[str, ...], str | None], ...] = (
    (("инфляц",), "cpi"),
    (("ипц",), "cpi"),
    (("потребительск", "цен"), "cpi"),
    (("рост цен",), "cpi"),
    # RUONIA во всех написаниях: кириллица, латиница, транслит. Ниже — корни
    # key-rate («ключев…», «ставк цб»); длину приоритета даёт сортировка.
    (("руония",), "ruonia"),
    (("ruonia",), "ruonia"),
    (("mronia",), "ruonia"),
    (("мрония",), "ruonia"),
    (("ключев", "став"), "key-rate"),
    (("ключев",), "key-rate"),
    (("ставк", "цб"), "key-rate"),
    (("ставк", "центробанк"), "key-rate"),
    (("автокред",), "auto-loan-rate"),
    (("кредит", "автомобил"), "auto-loan-rate"),
    (("ставк", "вклад"), "deposit-rate"),
    (("процент", "вклад"), "deposit-rate"),
    (("депозит", "физлиц"), "deposits-individual"),
    (("депозит", "юридическ"), "deposits-business"),
    (("депозит", "организац"), "deposits-business"),
    # Чередование к/ч («ипотек-а» но «ипотечн-ая») — якорь до него.
    (("ипот",), "mortgage-rate"),
    # Федеральный бюджет: три ряда Минфина. Голое «бюджет» не маршрутизируем —
    # рядов несколько, пусть запрос остаётся в карте пробелов отчёта.
    (("доходы", "бюджет"), "budget-revenue"),
    (("расходы", "бюджет"), "budget-expenditure"),
    (("дефицит", "бюджет"), "budget-deficit"),
    # Объёмы вкладов/депозитов: короткий корень добирает всё, что не попало
    # в ставки выше («вклады населения 2026», «объём депозитов»).
    (("вклад",), "deposits-individual"),
    (("депозит",), "deposits-individual"),
    # ИПП и его разделы: оба слова меняются по падежам, поэтому требуем пары
    # стемов — голое «производств» ловило бы любую отрасль. Разделы конкретнее
    # общего ряда и выигрывают у него по суммарной длине.
    (("обрабатывающ", "производств"), "ipi-manufacturing"),
    (("добыча", "полезн"), "ipi-mining"),
    (("промышленн", "производств"), "ipi"),
    # Отдельный ряд «Кредиты физическим лицам» (портфель): длиннее общего
    # «потребительск», чтобы не забирать запросы про потребительские цены.
    (("потребительск", "кредит"), "consumer-credit"),
    (("потребкредит",), "consumer-credit"),
    (("рефинансир",), "refinancing-rate"),
    (("курс доллар",), "usd-rub"),
    (("доллар",), "usd-rub"),
    (("usd",), "usd-rub"),
    (("евро",), "eur-rub"),
    (("eur",), "eur-rub"),
    (("юан",), "usd-cny"),
    (("ввп",), "gdp-nominal"),
    (("валовой", "внутренний"), "gdp-nominal"),
    (("безработиц",), "unemployment"),
    (("зарплат",), "wages-nominal"),
    (("прожиточн", "минимум"), "living-wage"),
    (("мрот",), "minimum-wage"),
    (("бензин",), "fuel-ai95"),
    (("дизельн", "топлив"), "fuel-diesel"),
    (("дт ",), "fuel-diesel"),
    (("золот",), "gold"),
    (("серебр",), "silver"),
    (("нефт",), "brent"),
    (("брент",), "brent"),
    (("imoex",), "imoex"),
    (("мосбирж",), "imoex"),
    (("сп 500",), None),  # индикатор удалён: явно не маршрутизируем
    (("сбербанк", "акций"), None),
)

# Токены, которые сами по себе не сужают матчинг («индекс потребительских цен
# на 2026 год» → cpi + 2026).
_STOP_TOKENS = re.compile(
    r"\b(в|на|за|по|и|с|из|у|к|что|какой|какая|сколько|сегодня|сейчас|"
    r"график|динамика|статистика|россия|рф|данные)\b",
    re.I,
)

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


@dataclass(slots=True)
class DemandRoute:
    query: str
    impressions: int = 0
    clicks: int = 0
    lost: int = 0          # показы без кликов — потенциал роста
    path: str | None = None
    code: str | None = None
    year: int | None = None
    matched: bool = False
    reasons: list[str] = field(default_factory=list)


def match_query(query: str, *, codes_by_token: dict[str, str] | None = None) -> DemandRoute:
    """Детерминированный матчинг одного запроса на код/год."""
    q = (query or "").lower()
    route = DemandRoute(query=query)
    code: str | None = None

    for stems, mapped in sorted(_SYNONYMS, key=lambda s: -sum(len(t) for t in s[0])):
        if all(stem in q for stem in stems):
            if mapped is None:
                route.reasons.append("blacklist:" + "+".join(stems))
                return route
            code = mapped
            route.reasons.append("synonym:" + "+".join(stems))
            break

    if code is None and codes_by_token:
        cleaned = _STOP_TOKENS.sub(" ", q)
        for name, candidate in sorted(
            codes_by_token.items(), key=lambda kv: -len(kv[0])
        ):
            if name and name in cleaned:
                code = candidate
                route.reasons.append(f"name:{name}")
                break

    if code is None:
        return route

    route.code = code
    years = [int(m.group(0)) for m in _YEAR_RE.finditer(q)]
    if years:
        route.year = max(years)
    if route.year and route.year >= 1991:
        route.path = russia_indicator_year(code, route.year)
    else:
        route.path = russia_indicator(code)
    route.matched = True
    return route


async def _codes_by_name(db: AsyncSession) -> dict[str, str]:
    rows = (await db.execute(
        select(Indicator.name, Indicator.code).where(
            Indicator.is_active.is_(True), Indicator.is_listed.is_(True)
        )
    )).all()
    mapping: dict[str, str] = {}
    for name, code in rows:
        n = (name or "").strip().lower()
        if len(n) >= 5:  # короткие имена матчат слишком широко
            mapping[n] = code
    return mapping


async def build_demand_routes(
    db: AsyncSession, *, days: int = 30, limit: int = 200, host: str | None = None
) -> list[DemandRoute]:
    """Сводка спроса за N дней: агрегат по запросу + маршрут на страницу.

    Ранжирование — по потерянным показам (impressions − clicks): это прямая
    мера того, сколько людей видели нас в выдаче и не кликнули. Запросы без
    маршрута тоже возвращаются (хвост «other») — это карта пробелов.
    ``host`` — host_id свойства Вебмастера; None = оба контура вместе.
    """
    from app.models import WebmasterSearchQuery

    since = date.today() - timedelta(days=days)
    stmt = select(
        WebmasterSearchQuery.query,
        WebmasterSearchQuery.impressions,
        WebmasterSearchQuery.clicks,
    ).where(WebmasterSearchQuery.date >= since)
    if host:
        stmt = stmt.where(WebmasterSearchQuery.host == host)
    rows = (await db.execute(stmt)).all()
    agg: dict[str, list[int]] = {}
    for query, shows, clicks in rows:
        cell = agg.setdefault((query or "").strip(), [0, 0])
        cell[0] += int(shows or 0)
        cell[1] += int(clicks or 0)

    codes = await _codes_by_name(db)
    routes: list[DemandRoute] = []
    for query, (shows, clicks) in agg.items():
        route = match_query(query, codes_by_token=codes)
        route.impressions = shows
        route.clicks = clicks
        route.lost = max(shows - clicks, 0)
        routes.append(route)
    routes.sort(key=lambda r: (-r.lost, -r.impressions))
    return routes[:limit]


def demand_report_text(routes: list[DemandRoute], *, days: int = 30) -> str:
    """Человекочитаемый отчёт «что искали → куда ведём» для Telegram/BI."""
    matched = [r for r in routes if r.matched]
    unmatched = [r for r in routes if not r.matched]
    lost_total = sum(r.lost for r in routes)
    lines = [
        f"Спрос за {days} дней: {len(routes)} уникальных запросов, "
        f"{lost_total} потерянных показов.",
        f"Замаршрутизовано на страницы: {len(matched)}.",
        "",
        "Топ потерянных показов:",
    ]
    for r in matched[:10]:
        target = r.year and f" ({r.year})" or ""
        lines.append(
            f"• {r.impressions} показов / {r.clicks} кликов — "
            f"«{r.query}» → {r.code}{target}"
        )
    holes = [r for r in unmatched[:6] if r.impressions >= 5]
    if holes:
        lines.append("")
        lines.append("Пробелы (нет целевой страницы):")
        for r in holes:
            lines.append(f"• {r.impressions} показов — «{r.query}»")
    return "\n".join(lines)


async def priority_recrawl_paths(
    db: AsyncSession, *, days: int = 30, limit: int = 150, host: str | None = None
) -> list[tuple[str, int]]:
    """URL для приоритетного переобхода: топ страниц по потерянным показам.

    Возвращает [(path, lost_impressions)] — подаётся в очередь Вебмастера
    до квоты, чтобы переобход шёл по спросу, а не по алфавиту реестра.
    """
    routes = await build_demand_routes(db, days=days, limit=limit * 4, host=host)
    best: dict[str, int] = {}
    for r in routes:
        if r.matched and r.path and r.lost > 0:
            best[r.path] = max(best.get(r.path, 0), r.lost)
    ranked = sorted(best.items(), key=lambda kv: -kv[1])[:limit]
    return ranked

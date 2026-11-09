"""Инструменты ИИ-агента публичного бота: сам ищет и читает ряды нашей базы (ADR-0027, дополнение 09.11.2026).

Владелец 09.11: «блок данные скудный… сделать, чтобы агент сам заходил в нашу базу, доставал — максимально
автономного агента». Модель получает описание инструментов (TOOLS, формат OpenAI/OpenRouter) и вызывает их
по ходу ответа; `run_tool` исполняет вызов и возвращает короткий текст.

Только чтение. Каждый запрос — в своей транзакции с `statement_timeout` 3 с (база прода общая, 4 vCPU),
поиск — по индексированным полям и с лимитами; ответ инструмента — не длиннее _MAX_OUT знаков.
Прогноз отдаётся одним числом на дату (без диапазонов — правило владельца).
"""
from __future__ import annotations

import ast
import json
import logging
import operator
import re
from datetime import date, timedelta

from sqlalchemy import and_, func, or_, select, text

from app.models import (
    EconomicEvent, Forecast, ForecastValue, Indicator, IndicatorData, Region, RegionDataPoint,
    RegionIndicator, RegionMonthlyPoint, WorldCountry, WorldDataPoint, WorldIndicator,
)
from app.services import site_paths
from app.services.locale import ru_public_origin

logger = logging.getLogger(__name__)

_MAX_OUT = 3500
_MAX_POINTS = 36

TOOLS = [
    {"type": "function", "function": {
        "name": "find_series",
        "description": (
            "Найти ряды в базе сайта по словам. Россия — 1000+ официальных рядов (цены, ставки, курсы, рынок труда, "
            "ВВП, бюджет, торговля, население…); регион России — 495 показателей по 96 регионам (зарплаты, цены на "
            "топливо по месяцам, население…); страна мира — ряды 55 стран. Возвращает код, название, единицу, "
            "последнее значение с датой и адрес страницы. Пиши запрос существительными: «медианная зарплата», "
            "«безработица», «бензин аи-92», «инфляция»."),
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "что искать, 1–4 слова"},
            "place": {"type": "string", "description": "регион России («Татарстан», «Москва») или страна («Германия»); пусто — Россия в целом"},
        }, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "get_series",
        "description": (
            "История ряда по коду из find_series: точки за период (до 36, прорежено), первое/последнее, минимум и "
            "максимум, изменение; для рядов России — наш расчёт (прогноз) одним числом на ближайшие даты."),
        "parameters": {"type": "object", "properties": {
            "code": {"type": "string"},
            "place": {"type": "string", "description": "тот же регион или страна, что в find_series; пусто — Россия"},
            "start": {"type": "string", "description": "YYYY-MM-DD или YYYY, по умолчанию 3 года назад"},
            "end": {"type": "string", "description": "YYYY-MM-DD или YYYY, по умолчанию сегодня"},
        }, "required": ["code"]}}},
    {"type": "function", "function": {
        "name": "rank_regions",
        "description": "Рейтинг регионов России по показателю (код из find_series с place-регионом): первые и последние места, всего регионов, год; с place — место и значение этого региона.",
        "parameters": {"type": "object", "properties": {
            "code": {"type": "string"},
            "place": {"type": "string", "description": "регион, чьё место нужно («Татарстан»)"},
            "year": {"type": "integer", "description": "по умолчанию — последний год с данными"},
        }, "required": ["code"]}}},
    {"type": "function", "function": {
        "name": "calendar",
        "description": "Ближайшие выходы данных и события (инфляция, заседания Банка России по ставке и др.) на N дней вперёд.",
        "parameters": {"type": "object", "properties": {
            "days": {"type": "integer", "description": "1–90, по умолчанию 30"},
            "query": {"type": "string", "description": "фильтр по названию, например «ставк» или «инфляц»"},
        }}}},
    {"type": "function", "function": {
        "name": "calculate",
        "description": "Точная арифметика: + - * / ** скобки, round(), min(), max(), abs(). Используй для процентов, сложных процентов, платежей, пересчёта валют.",
        "parameters": {"type": "object", "properties": {
            "expression": {"type": "string", "description": "например «1000000/(1+0.0635)» или «round(12*104976, 0)»"},
        }, "required": ["expression"]}}},
]


# ---------------------------------------------------------------------------
# помощники
# ---------------------------------------------------------------------------

def _num(v) -> str:
    v = float(v)
    s = f"{v:,.2f}" if abs(v) < 1000 or v != int(v) else f"{v:,.0f}"
    return s.replace(",", " ").replace(".", ",")


def _stems(query: str) -> list[str]:
    """Основы слов запроса: «медианная зарплата» → [«медианн», «зарпла»]."""
    words = [w for w in re.findall(r"[a-zа-яё0-9-]+", (query or "").lower().replace("ё", "е")) if len(w) >= 2]
    out = []
    for w in words[:5]:
        if w in ("в", "по", "на", "и", "за", "для", "россии", "россия", "рф", "цена", "цены"):
            continue
        out.append(w if len(w) <= 4 else w[: max(4, len(w) - 2)])
    return out


def _url(path: str) -> str:
    return f"{ru_public_origin()}{path}"


def _date_arg(s: str | None, default: date, end: bool = False) -> date:
    if not s:
        return default
    s = s.strip()
    try:
        if re.fullmatch(r"\d{4}", s):
            return date(int(s), 12, 31) if end else date(int(s), 1, 1)
        return date.fromisoformat(s[:10])
    except ValueError:
        return default


def _thin(points: list[tuple[date, float]]) -> list[tuple[date, float]]:
    if len(points) <= _MAX_POINTS:
        return points
    step = len(points) / (_MAX_POINTS - 1)
    picked = [points[int(i * step)] for i in range(_MAX_POINTS - 1)]
    return picked + [points[-1]]


def _clip(s: str) -> str:
    return s if len(s) <= _MAX_OUT else s[: _MAX_OUT - 20] + "\n…(обрезано)"


# Синонимы основ: в названиях рядов стран «инфляция» — это «индекс потребительских цен», зарплата — «заработная».
_SYN = {"инфля": ("инфля", "потребительских цен", "потребительские цен"), "зарпла": ("зарпла", "заработн"),
        "ввп": ("ввп", "валов"), "безрабо": ("безрабо",), "ставк": ("ставк",), "курс": ("курс", "обменн")}


def _alts(stem: str) -> tuple[str, ...]:
    for k, v in _SYN.items():
        if stem.startswith(k) or k.startswith(stem):
            return v
    return (stem,)


def _runs(points: list[tuple[date, float]]) -> list[tuple[date, float]]:
    """Сжать повторы (ставка держится месяцами): первая точка каждого значения и последняя точка ряда."""
    out = [p for i, p in enumerate(points) if i == 0 or p[1] != points[i - 1][1]]
    return out if out[-1] == points[-1] else out + [points[-1]]


async def _place(db, place: str | None):
    """Регион России, страна мира или None (Россия в целом)."""
    if not place or not place.strip():
        return None
    p = place.strip().lower().replace("ё", "е")
    if p in ("россия", "рф", "russia", "российская федерация"):
        return None
    st = _stems(p)
    if not st:
        return None
    key = st[0]
    regs = (await db.execute(select(Region).where(func.lower(Region.name).like(f"%{key}%")).limit(5))).scalars().all()
    if regs:
        regs.sort(key=lambda r: (r.kind != "region", len(r.name)))
        return ("region", regs[0])
    c = (await db.execute(select(WorldCountry).where(or_(
        func.lower(WorldCountry.name_ru).like(f"{key}%"), func.lower(WorldCountry.name_en).like(f"{key}%"),
        WorldCountry.slug == p,
    )).limit(1))).scalar_one_or_none()
    return ("country", c) if c else ("unknown", place)


# ---------------------------------------------------------------------------
# инструменты
# ---------------------------------------------------------------------------

async def _find_series(db, query: str, place: str | None = None) -> str:
    st = _stems(query)
    if not st:
        return "Пустой запрос: напиши, что искать."
    where = await _place(db, place)
    if where and where[0] == "unknown":
        return f"Место «{where[1]}» не нашёл: у нас есть регионы России и 55 стран. Уточни название."
    lines: list[str] = []
    if where is None:
        conds = [or_(*[func.lower(Indicator.name).like(f"%{a}%") for a in _alts(s)], Indicator.code.like(f"%{s}%")) for s in st]
        rows = (await db.execute(select(Indicator).where(Indicator.is_active.is_(True), and_(*conds))
                                 .order_by(func.length(Indicator.name)).limit(10))).scalars().all()
        if not rows and len(st) > 1:
            rows = (await db.execute(select(Indicator).where(Indicator.is_active.is_(True), or_(*conds))
                                     .order_by(func.length(Indicator.name)).limit(10))).scalars().all()
        for ind in rows:
            last = (await db.execute(select(IndicatorData.date, IndicatorData.value)
                                     .where(IndicatorData.indicator_id == ind.id)
                                     .order_by(IndicatorData.date.desc()).limit(1))).first()
            if not last:
                continue
            lines.append(f"- {ind.code} | {ind.name}, {ind.unit} | {ind.frequency} | последнее {_num(last[1])} на {last[0]}"
                         f" | {ind.source} | {_url(site_paths.russia_indicator(ind.code))}")
        head = "Россия"
    elif where[0] == "region":
        reg = where[1]
        conds = [or_(*[func.lower(RegionIndicator.name).like(f"%{a}%") for a in _alts(s)]) for s in st]
        rows = (await db.execute(select(RegionIndicator).where(RegionIndicator.is_listed.is_(True), and_(*conds))
                                 .order_by(func.length(RegionIndicator.name)).limit(8))).scalars().all()
        for ind in rows:
            m = (await db.execute(select(RegionMonthlyPoint.month, RegionMonthlyPoint.value).where(
                RegionMonthlyPoint.indicator_id == ind.id, RegionMonthlyPoint.region_id == reg.id)
                .order_by(RegionMonthlyPoint.month.desc()).limit(1))).first()
            y = (await db.execute(select(RegionDataPoint.year, RegionDataPoint.value).where(
                RegionDataPoint.indicator_id == ind.id, RegionDataPoint.region_id == reg.id)
                .order_by(RegionDataPoint.year.desc()).limit(1))).first()
            if m:
                last = f"последнее {_num(m[1])} за {str(m[0])[:4]}-{str(m[0])[4:]} (по месяцам)"
            elif y:
                last = f"последнее {_num(y[1])} за {y[0]} год"
            else:
                continue
            lines.append(f"- {ind.code} | {ind.name}, {ind.unit} | {last} | Росстат | "
                         f"{_url(site_paths.region_indicator(reg.slug, ind.code))}")
        head = f"Регион: {reg.name}"
    else:
        c = where[1]
        conds = [or_(*[func.lower(WorldIndicator.name_ru).like(f"%{a}%") for a in _alts(s)]) for s in st]
        raw = (await db.execute(select(WorldIndicator).where(
            WorldIndicator.country_id == c.id, WorldIndicator.is_listed.is_(True), and_(*conds))
            .order_by(WorldIndicator.points_count.desc()).limit(60))).scalars().all()
        # У стран одно название — много разрезов (пол, возраст, сезонность); берём «всего» и самый длинный ряд.
        best: dict[str, WorldIndicator] = {}
        for ind in raw:
            key = ind.name_ru
            score = (("tot" in ind.code or "total" in ind.code), ind.points_count, -len(ind.code))
            cur = best.get(key)
            if cur is None or score > (("tot" in cur.code or "total" in cur.code), cur.points_count, -len(cur.code)):
                best[key] = ind
        rows = list(best.values())[:8]
        for ind in rows:
            last = (await db.execute(select(WorldDataPoint.date, WorldDataPoint.value)
                                     .where(WorldDataPoint.indicator_id == ind.id)
                                     .order_by(WorldDataPoint.date.desc()).limit(1))).first()
            if not last:
                continue
            lines.append(f"- {ind.code} | {ind.name_ru}, {ind.unit_ru} | {ind.frequency} | последнее {_num(last[1])} на {last[0]}"
                         f" | {ind.source} | {_url(site_paths.indicator(c.slug, ind.code))}")
        head = f"Страна: {c.name_ru}"
    if not lines:
        return f"{head}: по «{query}» ничего не нашёл. Попробуй другое слово (синоним, короче)."
    return _clip(f"{head}. Найдено (код | название | частота | последнее | источник | страница):\n" + "\n".join(lines))


async def _get_series(db, code: str, place: str | None = None, start: str | None = None, end: str | None = None) -> str:
    today = date.today()
    d0 = _date_arg(start, today - timedelta(days=3 * 365))
    d1 = _date_arg(end, today, end=True)
    where = await _place(db, place)
    forecast: list[tuple[date, float]] = []
    if where is None:
        ind = (await db.execute(select(Indicator).where(Indicator.code == code))).scalar_one_or_none()
        if ind is None:
            return f"Ряда {code} по России нет — сначала find_series."
        pts = [(d, float(v)) for d, v in (await db.execute(
            select(IndicatorData.date, IndicatorData.value).where(
                IndicatorData.indicator_id == ind.id, IndicatorData.date >= d0, IndicatorData.date <= d1)
            .order_by(IndicatorData.date))).all()]
        fc = (await db.execute(
            select(ForecastValue.date, ForecastValue.value).join(Forecast, Forecast.id == ForecastValue.forecast_id)
            .where(Forecast.indicator_id == ind.id, Forecast.is_current.is_(True), ForecastValue.date > (pts[-1][0] if pts else today))
            .order_by(ForecastValue.date).limit(3))).all()
        forecast = [(d, float(v)) for d, v in fc]
        title = f"{ind.name}, {ind.unit} (Россия, {ind.source})"
        url = _url(site_paths.russia_indicator(ind.code))
    elif where[0] == "region":
        reg = where[1]
        ind = (await db.execute(select(RegionIndicator).where(RegionIndicator.code == code))).scalar_one_or_none()
        if ind is None:
            return f"Регионального ряда {code} нет — сначала find_series с place."
        mp = (await db.execute(select(RegionMonthlyPoint.month, RegionMonthlyPoint.value).where(
            RegionMonthlyPoint.indicator_id == ind.id, RegionMonthlyPoint.region_id == reg.id,
            RegionMonthlyPoint.month >= d0.year * 100 + d0.month, RegionMonthlyPoint.month <= d1.year * 100 + d1.month)
            .order_by(RegionMonthlyPoint.month))).all()
        if mp:
            pts = [(date(m // 100, m % 100, 1), float(v)) for m, v in mp]
        else:
            yp = (await db.execute(select(RegionDataPoint.year, RegionDataPoint.value).where(
                RegionDataPoint.indicator_id == ind.id, RegionDataPoint.region_id == reg.id,
                RegionDataPoint.year >= d0.year, RegionDataPoint.year <= d1.year).order_by(RegionDataPoint.year))).all()
            pts = [(date(y, 1, 1), float(v)) for y, v in yp]
        title = f"{ind.name}, {ind.unit} ({reg.name}, Росстат{'; помесячно' if mp else '; по годам'})"
        url = _url(site_paths.region_indicator(reg.slug, ind.code))
    elif where[0] == "country":
        c = where[1]
        ind = (await db.execute(select(WorldIndicator).where(WorldIndicator.code == code))).scalar_one_or_none()
        if ind is None or ind.country_id != c.id:
            return f"Ряда {code} у страны {c.name_ru} нет — сначала find_series с place."
        pts = [(d, float(v)) for d, v in (await db.execute(
            select(WorldDataPoint.date, WorldDataPoint.value).where(
                WorldDataPoint.indicator_id == ind.id, WorldDataPoint.date >= d0, WorldDataPoint.date <= d1)
            .order_by(WorldDataPoint.date))).all()]
        title = f"{ind.name_ru}, {ind.unit_ru} ({c.name_ru}, {ind.source})"
        url = _url(site_paths.indicator(c.slug, ind.code))
    else:
        return f"Место «{where[1]}» не нашёл."
    if not pts:
        return f"{title}: за {d0}…{d1} точек нет. Попробуй другой период."
    first, last = pts[0], pts[-1]
    lo = min(pts, key=lambda p: p[1])
    hi = max(pts, key=lambda p: p[1])
    ch = last[1] - first[1]
    pct = f", {ch / first[1] * 100:+.1f} %".replace(".", ",") if first[1] else ""
    out = [f"{title}. Точек за период: {len(pts)}.",
           f"Первое {_num(first[1])} на {first[0]}; последнее {_num(last[1])} на {last[0]}; изменение {_num(ch)}{pct}.",
           f"Минимум {_num(lo[1])} на {lo[0]}; максимум {_num(hi[1])} на {hi[0]}.",
           "Точки: " + "; ".join(f"{d} {_num(v)}" for d, v in _thin(_runs(pts)))
           + (" (повторы одинаковых значений сжаты)" if len(_runs(pts)) < len(pts) else "")]
    if forecast:
        out.append("Наш расчёт (прогноз, одним числом): " + "; ".join(f"{d} {_num(v)}" for d, v in forecast))
    out.append(f"Страница: {url}")
    return _clip("\n".join(out))


async def _rank_regions(db, code: str, year: int | None = None, place: str | None = None) -> str:
    ind = (await db.execute(select(RegionIndicator).where(RegionIndicator.code == code))).scalar_one_or_none()
    if ind is None:
        return f"Регионального ряда {code} нет — сначала find_series с place-регионом."
    if year is None:
        year = (await db.execute(select(func.max(RegionDataPoint.year)).where(RegionDataPoint.indicator_id == ind.id))).scalar()
    if year is None:
        return f"По {ind.name} годовых данных по регионам нет."
    rows = (await db.execute(select(Region.name, RegionDataPoint.value).join(Region, Region.id == RegionDataPoint.region_id)
                             .where(RegionDataPoint.indicator_id == ind.id, RegionDataPoint.year == year,
                                    Region.kind == "region").order_by(RegionDataPoint.value.desc()))).all()
    if not rows:
        return f"За {year} год по регионам данных нет."
    top = "; ".join(f"{i + 1}. {n} {_num(v)}" for i, (n, v) in enumerate(rows[:5]))
    bottom = "; ".join(f"{len(rows) - 4 + i}. {n} {_num(v)}" for i, (n, v) in enumerate(rows[-5:]))
    mine = ""
    where = await _place(db, place) if place else None
    if where and where[0] == "region":
        for i, (n, v) in enumerate(rows):
            if n == where[1].name:
                mine = f"\n{n}: {i + 1}-е место из {len(rows)}, {_num(v)}"
                break
        else:
            mine = f"\n{where[1].name}: за {year} год значения нет"
    return _clip(f"{ind.name}, {ind.unit}, {year} год, регионов: {len(rows)} (Росстат).\nВыше всех: {top}\nНиже всех: {bottom}{mine}\n"
                 f"Карта: {_url(site_paths.region_map(ind.code))}")


async def _calendar(db, days: int | None = 30, query: str | None = None) -> str:
    days = max(1, min(int(days or 30), 90))
    today = date.today()
    q = select(EconomicEvent.scheduled_date, EconomicEvent.title, EconomicEvent.is_estimated).where(
        EconomicEvent.scheduled_date >= today, EconomicEvent.scheduled_date <= today + timedelta(days=days))
    for s in _stems(query or ""):
        q = q.where(func.lower(EconomicEvent.title).like(f"%{s}%"))
    seen: set = set()
    rows = []
    for r in (await db.execute(q.order_by(EconomicEvent.scheduled_date).limit(80))).all():
        if (r[0], r[1]) not in seen:
            seen.add((r[0], r[1]))
            rows.append(r)
    rows = rows[:20]
    if not rows:
        return f"На {days} дней вперёд событий{' по «' + query + '»' if query else ''} в календаре нет."
    return _clip("Календарь:\n" + "\n".join(f"- {d}{' (ориентировочно)' if est else ''}: {t}" for d, t, est in rows))


_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos, ast.Mod: operator.mod}
_FUNCS = {"round": round, "min": min, "max": max, "abs": abs}


def calculate(expression: str) -> str:
    """Безопасная арифметика: только числа, операторы и round/min/max/abs (без имён и вызовов чего-то ещё)."""
    expr = (expression or "").replace(",", ".").replace("×", "*").replace("^", "**").replace(" ", "")
    expr = re.sub(r"(?<=\d)\.(?=\d{3}(?!\d))", "", expr) if expr.count(".") > 1 else expr

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow) and abs(b) > 1000:
                raise ValueError("слишком большая степень")
            return _OPS[type(n.op)](a, b)
        if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](ev(n.operand))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FUNCS and not n.keywords:
            return _FUNCS[n.func.id](*[ev(a) for a in n.args])
        raise ValueError("недопустимое выражение")
    try:
        v = ev(ast.parse(expr[:300], mode="eval"))
        return f"{expression} = {_num(v) if isinstance(v, (int, float)) else v}"
    except Exception as e:  # noqa: BLE001
        return f"Не посчитал «{expression}»: {e}"


async def run_tool(name: str, raw_args: str | dict | None) -> str:
    """Исполнить вызов инструмента моделью; любая ошибка — короткий текст для модели, не исключение."""
    from app.database import async_session

    try:
        args = raw_args if isinstance(raw_args, dict) else json.loads(raw_args or "{}")
    except json.JSONDecodeError:
        return "Аргументы не разобраны: нужен JSON."
    if name == "calculate":
        return calculate(str(args.get("expression", "")))
    funcs = {"find_series": _find_series, "get_series": _get_series, "rank_regions": _rank_regions, "calendar": _calendar}
    fn = funcs.get(name)
    if fn is None:
        return f"Инструмента {name} нет."
    allowed = {"find_series": ("query", "place"), "get_series": ("code", "place", "start", "end"),
               "rank_regions": ("code", "year", "place"), "calendar": ("days", "query")}[name]
    kwargs = {k: v for k, v in args.items() if k in allowed and v not in (None, "")}
    try:
        async with async_session() as db:
            if db.get_bind().dialect.name == "postgresql":
                await db.execute(text("SET LOCAL statement_timeout = '3s'"))
            return await fn(db, **kwargs)
    except TypeError:
        return f"Не хватает аргументов для {name}: нужны {', '.join(allowed)}."
    except Exception:  # noqa: BLE001 — сбой запроса не роняет ответ
        logger.warning("Public bot tool %s failed", name, exc_info=True)
        return f"Инструмент {name} не ответил (база занята или запрос слишком тяжёлый). Попробуй уже, или ответь без него."

"""Факты для блоков персонального выпуска (ADR-0033): каждое число — из базы, с источником и датой.

Главное число — как на карточке сайта:
* ряды цен России (ИПЦ и его части) показываются инфляцией за год (тот же выбор, что у поиска,
  `search_latest._FEDERAL_HEADLINE_YOY`); у стран мира — `world_price_headline`;
* значение и единица — `display.display_value_text` / `localize_unit`, период — `value_period_phrase`;
* ряд с устаревшими данными (`freshness.is_stale`) помечается и не называется «новым».

`FactCache` читает каждый ряд один раз за запуск сборки: стоимость пропорциональна числу разных
рядов у всех подписчиков, а не числу подписчиков. Региональные месячные цены — через быстрый путь
`regional_monthly_latest` (холодный диск, замер 09.11.2026).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import and_, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    EconomicEvent, Indicator, IndicatorData, Region, RegionDataPoint, RegionIndicator,
    WorldCountry, WorldDataPoint, WorldIndicator,
)
from app.services import freshness
from app.services.display import (
    contains_cyrillic, display_value, format_date_locale, format_number_ru, localize_unit,
    value_period_phrase,
)
from app.services.newsletter_personal.subjects import (
    RUSSIA, Subject, parse_key, topic_for_code, topic_for_text,
)

logger = logging.getLogger(__name__)

NBSP = " "
POINTS = 13

_EN_SOURCES = {
    "Росстат": "Rosstat", "Банк России": "Bank of Russia", "ЦБ РФ": "Bank of Russia",
    "Минфин России": "Ministry of Finance of Russia", "Минфин": "Ministry of Finance of Russia",
    "Московская биржа": "Moscow Exchange", "ЕМИСС": "EMISS (Rosstat)",
}


def source_text(source: str | None, locale: str) -> str:
    """Источник на языке письма; для английского без кириллицы (иначе пусто — блок не пройдёт проверку)."""
    s = (source or "").strip()
    if locale != "en" or not s:
        return s
    from app.data.i18n.glossary_en import GLOSSARY_EN

    if s in GLOSSARY_EN:
        return GLOSSARY_EN[s]
    if s in _EN_SOURCES:
        return _EN_SOURCES[s]
    out = s
    for ru, en in sorted({**GLOSSARY_EN, **_EN_SOURCES}.items(), key=lambda kv: -len(kv[0])):
        out = out.replace(ru, en)
    return "" if contains_cyrillic(out) else out


def _decimals(text: str) -> int:
    m = re.search(r"[.,](\d+)\s*$", text.replace(NBSP, " ").replace(" ", "").split(" ")[0])
    return len(m.group(1)) if m else 0


def number(value: float, locale: str, *, signed: bool = False, digits: int | None = None) -> str:
    if digits is not None:
        value = round(float(value), digits)
        text = f"{abs(value):,.{digits}f}"
        if locale != "en":
            text = text.replace(",", " ").replace(".", ",")
        if value < 0:
            text = "−" + text
        elif signed and value > 0:
            text = "+" + text
        return text
    return format_number_ru(value, signed=signed, locale=locale)


def with_unit(num: str, unit: str, locale: str | None = None) -> str:
    """Число с единицей: по-русски «6,3 %», по-английски «6.3%» (правило редакции 6)."""
    if not unit:
        return num
    if unit == "%":
        if locale is None:
            locale = "en" if ("." in num and "," not in num) else "ru"
        return f"{num}%" if locale == "en" else f"{num}{NBSP}%"
    return f"{num}{NBSP}{unit}"


# Ряды цен «за год»: название без «г/г» и «YoY» (правило редакции 4).
YOY_TITLES = {
    "cpi-yoy": {"ru": "Инфляция за год", "en": "Inflation over 12 months"},
    "cpi-food-yoy": {"ru": "Продовольствие: рост цен за год", "en": "Food prices over 12 months"},
    "cpi-nonfood-yoy": {"ru": "Непродовольственные товары: рост цен за год", "en": "Non-food prices over 12 months"},
    "cpi-services-yoy": {"ru": "Услуги: рост цен за год", "en": "Service prices over 12 months"},
}

_STEP_PHRASE = {
    "daily": ("за неделю", "over the week"),
    "weekly": ("за неделю", "over the week"),
    "monthly": ("за месяц", "over the month"),
    "quarterly": ("за квартал", "over the quarter"),
    "annual": ("за год", "over the year"),
}


@dataclass
class Fact:
    key: str
    kind: str
    title: str
    unit: str
    frequency: str
    source: str
    path: str
    topic: str | None
    as_of: date
    value: float
    value_text: str           # «70,01 руб./л» — крупное число блока
    period: str               # «на 9 ноября 2026» / «за октябрь 2026»
    stale: bool
    prev: tuple[date, float] | None = None
    change_text: str = ""     # «−0,70 руб./л за неделю»
    change_dir: str = "flat"  # up / down / flat
    points: list[tuple[date, float]] = field(default_factory=list)
    headline_yoy: bool = False
    compare: dict | None = None   # регион: {"label": "Россия", "value_text": …}
    indicator_id: int | None = None

    def value_on_or_before(self, day: date) -> tuple[date, float] | None:
        best = None
        for d, v in self.points:
            if d <= day:
                best = (d, v)
        return best


def _freq(f: str | None) -> str:
    return freshness.normalize_frequency(f)


def _finite(column):
    return and_(column.is_not(None), column > literal_column("-1e30"), column < literal_column("1e30"))


def _change(points: list[tuple[date, float]], freq: str, unit: str, locale: str, digits: int) -> tuple[
        tuple[date, float] | None, str, str]:
    if len(points) < 2:
        return None, "", "flat"
    last_day, last_val = points[-1]
    if freq == "daily":
        target = last_day - timedelta(days=7)
        prev = None
        for d, v in points[:-1]:
            if d <= target:
                prev = (d, v)
        if prev is None:
            return None, "", "flat"
    elif freq == "quarterly":
        # Квартал к предыдущему кварталу у несезонно сглаженных рядов — сезонный скачок («инвестиции
        # +44,5 % за квартал»); честное сравнение — с тем же кварталом год назад (16.11.2026).
        prev = next(((d, v) for d, v in points[:-1] if d.year == last_day.year - 1 and d.month == last_day.month), None)
        if prev is None:
            return None, "", "flat"
    else:
        prev = points[-2]
    delta = round(last_val - prev[1], digits)
    direction = "up" if delta > 0 else "down" if delta < 0 else "flat"
    ru_phrase, en_phrase = _STEP_PHRASE.get(freq, ("", ""))
    if freq == "quarterly":
        ru_phrase, en_phrase = "к тому же кварталу прошлого года", "from the same quarter a year earlier"
    phrase = en_phrase if locale == "en" else ru_phrase
    if delta == 0:
        text = ("unchanged " + phrase) if locale == "en" else ("без изменений " + phrase)
        return prev, text.strip(), "flat"
    if _is_share_unit(unit):   # доля, темп, ставка — в процентных пунктах, без «процента от процента»
        unit_pp = "pp" if locale == "en" else "п. п."
        text = f"{number(delta, locale, signed=True, digits=digits)}{NBSP}{unit_pp} {phrase}"
    else:
        text = f"{with_unit(number(delta, locale, signed=True, digits=digits), unit, locale)} {phrase}"
        if prev[1] and prev[1] > 0:
            pct = (last_val / prev[1] - 1.0) * 100.0
            # Сотни процентов у сальдо и чистых потоков (база около нуля) ничего не объясняют — только разница.
            if 0.05 <= abs(pct) <= 200:
                text += f" ({with_unit(number(pct, locale, signed=True, digits=1), '%', locale)})"
    return prev, text.strip(), direction


def _is_share_unit(unit: str) -> bool:
    u = (unit or "").strip().lower()
    return "%" in u or "percent" in u or "процент" in u


def _fmt_points(points, code: str | None):
    out = []
    for d, v in points:
        dv = display_value(code, v) if code else float(v)
        if dv is not None:
            out.append((d, float(dv)))
    return out


class FactCache:
    """Факты по ключам предметов на один запуск сборки (язык фиксирован)."""

    def __init__(self, db: AsyncSession, locale: str, today: date):
        self.db = db
        self.locale = "en" if locale == "en" else "ru"
        self.today = today
        self._facts: dict[str, Fact | None] = {}
        self._meta_topic: dict[str, str | None] = {}
        self._region_ids: dict[str, int] | None = None
        self._region_names: dict[str, str] = {}
        self._russia_region_id: int | None = None
        self._title_axes: dict[int, dict] = {}
        self.reads = 0

    # --- регионы ------------------------------------------------------------
    async def _regions(self) -> dict[str, int]:
        if self._region_ids is None:
            rows = (await self.db.execute(select(Region.id, Region.slug, Region.name, Region.kind))).all()
            self._region_ids = {slug: rid for rid, slug, _n, _k in rows}
            self._region_names = {slug: name for _rid, slug, name, _k in rows}
            self._russia_region_id = next((rid for rid, _s, _n, kind in rows if kind == "country"), None)
        return self._region_ids

    async def region_name(self, slug: str) -> str | None:
        await self._regions()
        name = self._region_names.get(slug)
        if name and self.locale == "en":
            from app.data.i18n.regions_en import REGIONS_EN

            return REGIONS_EN.get(slug)
        return name

    async def country_name(self, slug: str) -> str | None:
        row = (await self.db.execute(select(WorldCountry.name_ru, WorldCountry.name_en)
                                     .where(WorldCountry.slug == slug))).first()
        if row is None:
            return None
        return (row[1] if self.locale == "en" else row[0]) or row[0]

    # --- общее --------------------------------------------------------------
    async def get(self, key: str) -> Fact | None:
        if key in self._facts:
            return self._facts[key]
        sub = parse_key(key)
        fact = None
        try:
            if sub is None:
                fact = None
            elif sub.kind == "ru":
                fact = await self._russia(sub)
            elif sub.kind == "w":
                fact = await self._world(sub)
            elif sub.kind == "r":
                fact = await self._region(sub)
        except Exception as exc:  # noqa: BLE001 — один ряд не роняет выпуск
            logger.warning("newsletter fact failed for %s: %s", key, type(exc).__name__)
            await self._recover()
            fact = None
        self._facts[key] = fact
        if fact is not None:
            self._meta_topic[key] = fact.topic
        return fact

    async def _recover(self) -> None:
        try:
            await self.db.rollback()
        except Exception:  # noqa: BLE001
            pass

    async def topics(self, keys: list[str]) -> dict[str, str]:
        """Темы рядов одним запросом на вид (для профиля), без чтения значений."""
        out: dict[str, str] = {}
        ru_codes = [k.split(":", 1)[1] for k in keys if k.startswith("ru:")]
        if ru_codes:
            for code, cat in (await self.db.execute(
                    select(Indicator.code, Indicator.category).where(Indicator.code.in_(ru_codes)))).all():
                t = topic_for_code(code, cat)
                if t:
                    out[f"ru:{code}"] = t
        w = [parse_key(k) for k in keys if k.startswith("w:")]
        w_codes = [s.code for s in w if s is not None]
        if w_codes:
            for code, slug, cat, name in (await self.db.execute(
                    select(WorldIndicator.code, WorldCountry.slug, WorldIndicator.category_ru, WorldIndicator.name_ru)
                    .join(WorldCountry, WorldCountry.id == WorldIndicator.country_id)
                    .where(WorldIndicator.code.in_(w_codes)))).all():
                t = topic_for_text(cat, name)
                if t:
                    out[f"w:{slug}:{code}"] = t
        r = [parse_key(k) for k in keys if k.startswith(("r:", "ri:"))]
        r_codes = [s.code for s in r if s is not None]
        if r_codes:
            sections = {code: (sec, name) for code, sec, name in (await self.db.execute(
                select(RegionIndicator.code, RegionIndicator.section_name, RegionIndicator.name)
                .where(RegionIndicator.code.in_(r_codes)))).all()}
            for s in r:
                if s is None or s.code not in sections:
                    continue
                t = topic_for_code(s.code) or topic_for_text(*sections[s.code])
                if t:
                    out[s.key] = t
        return out

    async def world_country_for_code(self, codes: list[str]) -> dict[str, str]:
        if not codes:
            return {}
        rows = (await self.db.execute(
            select(WorldIndicator.code, WorldCountry.slug)
            .join(WorldCountry, WorldCountry.id == WorldIndicator.country_id)
            .where(WorldIndicator.code.in_(codes)))).all()
        return {code: slug for code, slug in rows}

    # --- Россия -------------------------------------------------------------
    async def _russia(self, sub: Subject) -> Fact | None:
        from app.services.search_latest import _FEDERAL_HEADLINE_YOY
        from app.services import site_paths

        code = sub.code
        shown_code = _FEDERAL_HEADLINE_YOY.get(code, code)
        # Ряд «за год» у цен — главное число карточки ИПЦ; сам он в каталоге может быть скрыт
        # (ссылка всё равно ведёт на карточку исходного показателя), поэтому без проверки листинга.
        listed = [Indicator.is_listed.is_(True)] if shown_code == code else []
        ind = await self.db.scalar(select(Indicator).where(
            Indicator.code == shown_code, Indicator.is_active.is_(True), *listed))
        if ind is not None and shown_code != code:
            base_listed = await self.db.scalar(select(Indicator.id).where(
                Indicator.code == code, Indicator.is_active.is_(True), Indicator.is_listed.is_(True)))
            if base_listed is None:
                return None
        if ind is None and shown_code != code:
            shown_code = code
            ind = await self.db.scalar(select(Indicator).where(
                Indicator.code == code, Indicator.is_active.is_(True), Indicator.is_listed.is_(True)))
        if ind is None:
            return None
        self.reads += 1
        rows = (await self.db.execute(
            select(IndicatorData.date, IndicatorData.value)
            .where(IndicatorData.indicator_id == ind.id, _finite(IndicatorData.value))
            .order_by(IndicatorData.date.desc()).limit(POINTS + 40 if _freq(ind.frequency) == "daily" else POINTS)
        )).all()
        if not rows:
            return None
        points = _fmt_points(sorted((d, float(v)) for d, v in rows), ind.code)
        freq = _freq(ind.frequency)
        if freq == "annual" and ind.code.startswith("weo-"):
            points = [(d, v) for d, v in points if d.year < self.today.year]   # прогноз МВФ — не факт
        if not points:
            return None
        unit = localize_unit(ind.unit, locale=self.locale) or ""
        last_day, last_val = points[-1]
        num = format_number_ru(last_val, signed=False, locale=self.locale)
        digits = max(_decimals(num), _decimals(format_number_ru(points[-2][1], locale=self.locale)) if len(points) > 1 else 0)
        if _decimals(num) > 2 and (unit.startswith("%") or abs(last_val) >= 10):
            # «16,3286 %» и «91,1107 трлн руб.» в письме читаются как ошибка — до двух знаков.
            # Курсы вроде 1,1014 остаются как на карточке.
            num = number(last_val, self.locale, digits=2)
        prev, change, direction = _change(points, freq, unit, self.locale, min(digits, 2))
        title = YOY_TITLES.get(ind.code, {}).get(self.locale) or (
            (ind.name_en if self.locale == "en" else ind.name) or ind.name or "").strip()
        return Fact(
            key=sub.key, kind="ru", title=title, unit=unit, frequency=freq,
            source=source_text(ind.source, self.locale), path=site_paths.russia_indicator(code),
            topic=topic_for_code(code, ind.category), as_of=last_day, value=last_val,
            value_text=with_unit(num, unit, self.locale), period=value_period_phrase(last_day, freq, locale=self.locale),
            stale=freshness.is_stale(last_day, freq, self.today), prev=prev, change_text=change,
            change_dir=direction, points=points, headline_yoy=shown_code != code, indicator_id=ind.id,
        )

    # --- мир ----------------------------------------------------------------
    async def _world(self, sub: Subject) -> Fact | None:
        from app.api.world import _indicator_public_unit
        from app.services import site_paths
        from app.services.locale import reset_locale, set_locale
        from app.services.search_latest import world_price_headline

        row = (await self.db.execute(
            select(WorldIndicator, WorldCountry.name_ru, WorldCountry.name_en)
            .join(WorldCountry, WorldCountry.id == WorldIndicator.country_id)
            .where(WorldIndicator.code == sub.code, WorldCountry.slug == sub.place,
                   WorldIndicator.is_listed.is_(True)))).first()
        if row is None:
            return None
        ind, c_ru, c_en = row
        self.reads += 1
        rows = (await self.db.execute(
            select(WorldDataPoint.date, WorldDataPoint.value)
            .where(WorldDataPoint.indicator_id == ind.id, _finite(WorldDataPoint.value))
            .order_by(WorldDataPoint.date.desc()).limit(POINTS + 40 if _freq(ind.frequency) == "daily" else POINTS)
        )).all()
        if not rows:
            return None
        series = sorted((d, float(v)) for d, v in rows)
        if _freq(ind.frequency) == "annual":
            # Год ещё не закончился — это оценка или прогноз источника (МВФ), а не факт (16.11.2026:
            # «численность населения Грузии за 2026 год» стояла в письме как свершившаяся).
            series = [(d, v) for d, v in series if d.year < self.today.year]
            if not series:
                return None
        token = set_locale(self.locale)
        try:
            unit = (_indicator_public_unit(ind) or "").strip()
        finally:
            reset_locale(token)
        freq = _freq(ind.frequency)
        headline = world_price_headline(ind, series)
        country = (c_en if self.locale == "en" else c_ru) or c_ru or ""
        name = await self._world_title(ind)
        title = f"{country}: {name}" if country and not name.lower().startswith(country.lower()) else name
        last_day, last_val = series[-1]
        yoy = False
        if headline:
            yoy = True
            last_val = float(headline["value"])
            unit_text = "%"
            num = number(last_val, self.locale, digits=1)
            value_text = with_unit(num, unit_text, self.locale) + (" over the year" if self.locale == "en" else " за год")
            points, prev, change, direction = series, None, "", "flat"
        else:
            num = format_number_ru(last_val, locale=self.locale)
            digits = max(_decimals(num), _decimals(format_number_ru(series[-2][1], locale=self.locale)) if len(series) > 1 else 0)
            if _decimals(num) > 2 and ("%" in unit or abs(last_val) >= 10):
                num = number(last_val, self.locale, digits=2)   # «3.4514 %» → «3.45 %»
            points = series
            prev, change, direction = _change(points, freq, unit, self.locale, min(digits, 2))
            value_text = with_unit(num, unit, self.locale)
        return Fact(
            key=sub.key, kind="w", title=title, unit=unit, frequency=freq,
            source=source_text(ind.source, self.locale), path=site_paths.indicator(sub.place, sub.code),
            topic=topic_for_text(ind.category_ru, ind.name_ru), as_of=last_day, value=last_val,
            value_text=value_text, period=value_period_phrase(last_day, freq, locale=self.locale),
            stale=freshness.is_stale(last_day, freq, self.today), prev=prev, change_text=change,
            change_dir=direction, points=points, headline_yoy=yoy, indicator_id=ind.id,
        )

    async def _world_title(self, ind) -> str:
        """Название как на карточке: базовое имя + уточнение среза (`world_series_title`)."""
        try:
            from app.services.world_series_title import _base_and_bits, load_title_axes

            if ind.country_id not in self._title_axes:
                self._title_axes[ind.country_id] = await load_title_axes(self.db, ind.country_id)
            base, bits = _base_and_bits(ind, self.locale, self._title_axes[ind.country_id])
            return (f"{base} ({', '.join(bits)})" if bits else base).strip()
        except Exception:  # noqa: BLE001 — без уточнения, но с базовым именем
            return ((ind.name_en if self.locale == "en" else ind.name_ru) or ind.name_ru or "").strip()

    # --- регионы России -------------------------------------------------------
    async def _region(self, sub: Subject) -> Fact | None:
        from app.services import site_paths
        from app.services.regional_monthly_latest import latest_monthly_points

        regions = await self._regions()
        rid = regions.get(sub.place)
        ind = await self.db.scalar(select(RegionIndicator).where(
            RegionIndicator.code == sub.code, RegionIndicator.is_listed.is_(True)))
        if rid is None or ind is None:
            return None
        self.reads += 1
        en_meta = None
        if self.locale == "en":
            from app.data.i18n.region_indicators_en import REGION_INDICATORS_EN

            en_meta = REGION_INDICATORS_EN.get(ind.code)
            if not en_meta:
                return None
        unit_raw = (en_meta or {}).get("unit") if en_meta else ind.unit
        unit = (unit_raw or "").strip()
        # «Средняя цена: бензин …, рублей за литр» — единица уже в названии; в письме — без неё.
        base_name = (en_meta or {}).get("name") if en_meta else ind.name
        base_name = clean_region_name(base_name or "")
        unit = _short_unit(unit, self.locale)
        ids = [rid] + ([self._russia_region_id] if self._russia_region_id else [])
        monthly = await latest_monthly_points(self.db, [ind.id], ids, n=POINTS)
        mine = monthly.get((ind.id, rid))
        russia = monthly.get((ind.id, self._russia_region_id)) if self._russia_region_id else None
        if mine:
            freq = "monthly"
            pts = sorted((date(m // 100, m % 100, 1), v) for m, v in mine)
            rus = {date(m // 100, m % 100, 1): v for m, v in (russia or [])}
        else:
            rows = (await self.db.execute(
                select(RegionDataPoint.region_id, RegionDataPoint.year, RegionDataPoint.value)
                .where(RegionDataPoint.indicator_id == ind.id, RegionDataPoint.region_id.in_(ids))
                .order_by(RegionDataPoint.year.desc()).limit(40))).all()
            freq = "annual"
            pts = sorted((date(y, 1, 1), float(v)) for r, y, v in rows if r == rid)[-POINTS:]
            rus = {date(y, 1, 1): float(v) for r, y, v in rows if r == self._russia_region_id}
        if not pts:
            return None
        region_name = await self.region_name(sub.place) or sub.place
        last_day, last_val = pts[-1]
        num = format_number_ru(last_val, locale=self.locale)
        digits = max(_decimals(num), _decimals(format_number_ru(pts[-2][1], locale=self.locale)) if len(pts) > 1 else 0)
        prev, change, direction = _change(pts, freq, unit, self.locale, min(digits, 2))
        compare = None
        # Строка «по России» у самой Российской Федерации не нужна: сравнение с собой.
        if last_day in rus and rid != self._russia_region_id:
            compare = {"label": "Russia" if self.locale == "en" else "Россия",
                       "value": rus[last_day],
                       "value_text": with_unit(format_number_ru(rus[last_day], locale=self.locale), unit, self.locale)}
        return Fact(
            key=sub.key, kind="r", title=f"{_fit(base_name, 108 - len(region_name))}, {region_name}", unit=unit,
            frequency=freq,
            source="Rosstat" if self.locale == "en" else "Росстат",
            path=site_paths.region_indicator(sub.place, sub.code),
            topic=topic_for_code(ind.code) or topic_for_text(ind.section_name, ind.name),
            as_of=last_day, value=last_val, value_text=with_unit(num, unit, self.locale),
            period=value_period_phrase(last_day, freq, locale=self.locale),
            stale=freshness.is_stale(last_day, freq, self.today), prev=prev, change_text=change,
            change_dir=direction, points=pts, compare=compare, indicator_id=ind.id,
        )

    # --- календарь ------------------------------------------------------------
    async def upcoming_events(self, codes: list[str], *, days: int = 21) -> list[dict]:
        """Ближайшие публичные выходы данных по показателям России (условия как у календаря сайта)."""
        if not codes:
            return []
        from app.api.calendar import _public_calendar_conditions

        rows = (await self.db.execute(
            select(EconomicEvent, Indicator.code)
            .join(Indicator, Indicator.id == EconomicEvent.indicator_id)
            # Ежедневные публикации (курсы) не новость для календаря письма.
            .where(Indicator.code.in_(codes), Indicator.frequency != "daily",
                   EconomicEvent.scheduled_date >= self.today,
                   EconomicEvent.scheduled_date <= self.today + timedelta(days=days),
                   *_public_calendar_conditions())
            .order_by(EconomicEvent.scheduled_date).limit(40))).all()
        out = []
        seen_codes: set[str] = set()
        for ev, code in rows:
            if code in seen_codes:
                continue
            seen_codes.add(code)
            title = (ev.title_en if self.locale == "en" else ev.title) or ev.title or ""
            if self.locale == "en" and contains_cyrillic(title):
                continue
            if ev.reference_period and self.locale != "en":
                title = f"{title} ({ev.reference_period})"
            out.append({
                "code": code, "date_iso": ev.scheduled_date.isoformat(),
                "date": _day_label(ev.scheduled_date, self.locale),
                "time": (f"{ev.scheduled_time} {'MSK' if self.locale == 'en' else 'мск'}" if ev.scheduled_time else ""),
                "title": title[0].lower() + title[1:] if title and self.locale != "en" else title,
            })
        return out


_UNIT_SHORT_RU = {
    "рублей за литр": "₽/л", "рублей за кг": "₽/кг", "рублей": "₽", "рублей за шт.": "₽/шт.",
    "рублей за 10 шт.": "₽ за 10 шт.", "рублей за 1000 мл": "₽ за 1000 мл",
}
_UNIT_SHORT_EN = {"roubles per litre": "RUB/l", "roubles per kg": "RUB/kg", "roubles": "RUB"}


_RU_UNIT_PER = {"литр": "₽/л", "кг": "₽/кг", "шт.": "₽/шт."}


def _short_unit(unit: str, locale: str) -> str:
    """«рублей за литр» → «₽/л», «рублей» → «₽», «рублей за билет» → «₽ за билет»."""
    u = (unit or "").strip()
    if locale == "en":
        return _UNIT_SHORT_EN.get(u, u)
    if u in _UNIT_SHORT_RU:
        return _UNIT_SHORT_RU[u]
    m = re.match(r"^рубл\w*\s+(за|в расч[её]те на)\s+(.+)$", u)
    if m:
        return _RU_UNIT_PER.get(m.group(2), f"₽ {m.group(1)} {m.group(2)}")
    if re.match(r"^рубл\w*$", u):
        return "₽"
    return u


_REGION_NAME_PREFIXES = re.compile(
    r"^(Средняя цена:\s*|Потребительские цены на\s+|Потребительская цена на\s+|Consumer price of\s+)", re.I)


def _fit(name: str, limit: int) -> str:
    """Длинное название показателя сокращается само, чтобы после него уцелело название региона."""
    if len(name) <= max(limit, 30):
        return name
    return name[:max(limit, 30)].rsplit(" ", 1)[0].rstrip(",;:—- ") + "…"


def clean_region_name(name: str) -> str:
    """«Потребительские цены на бензин АИ-95, рублей за литр» → «Бензин АИ-95»."""
    out = _REGION_NAME_PREFIXES.sub("", name.strip())
    out = re.sub(r",\s*(рубл\w*|руб\.)\b.*$", "", out)
    return out[:1].upper() + out[1:] if out else out


_RU_MONTHS_GEN = ("января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа",
                  "сентября", "октября", "ноября", "декабря")
_EN_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
              "September", "October", "November", "December")


def _day_label(d: date, locale: str) -> str:
    if locale == "en":
        return f"{d.day} {_EN_MONTHS[d.month - 1]}"
    return f"{d.day} {_RU_MONTHS_GEN[d.month - 1]}"


def day_label(d: date, locale: str) -> str:
    return _day_label(d, locale)


def full_date(d: date, locale: str) -> str:
    return format_date_locale(d, locale=locale)


__all__ = ["Fact", "FactCache", "source_text", "number", "with_unit", "day_label", "full_date", "RUSSIA"]

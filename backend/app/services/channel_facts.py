"""Данные для автора Telegram-канала и сторож чисел (17.11.2026, ADR-0035).

Две задачи, обе без модели:

1. Сводка (`build_briefing`): что нового в рядах, календарь выходов, спрос на сайте, как читали прошлые посты и что
   решал владелец. Каждое число, которое код пишет в сводку, попадает в «основания» (`Corpus`) с подписью, откуда оно:
   ряд, дата, источник. Это и есть контекст модели.
2. Сторож (`check_post`): после того как модель написала пост, каждое число текста сверяется с основаниями —
   число из сводки или из ответа инструмента, пересчитанный расчёт, названное допущение или число со страницы,
   которую модель нашла поиском. Что не сошлось — названо, и публикация такого поста закрыта до правки.

Правила владельца, которые сторож проверяет сам: прогноз одним числом и с пометкой «наш расчёт», без диапазона;
без жаргона; источник у каждого числа (строка источника собирается из оснований, а не со слов модели).
"""
from __future__ import annotations

import ast
import logging
import operator
import re
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from html import unescape

from sqlalchemy import func, select, text

from app.models import EconomicEvent, Forecast, ForecastValue, Indicator, IndicatorData

logger = logging.getLogger(__name__)

MSK = timezone(timedelta(hours=3))
MONTHS_GEN = ("января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа",
              "сентября", "октября", "ноября", "декабря")
MONTHS_NOM = ("январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август",
              "сентябрь", "октябрь", "ноябрь", "декабрь")
WEEKDAYS = ("понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье")
WEEKDAYS_SHORT = ("пн", "вт", "ср", "чт", "пт", "сб", "вс")
TANK_L = 50


# ---------------------------------------------------------------------------
# Ряды, за которыми следит автор
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Watch:
    code: str
    title: str
    unit: str                     # как писать после числа: «₽ за литр», «%»
    is_rate: bool = False         # проценты: изменение в пунктах
    chart: str | None = None      # ключ картинки-графика (темы публичного бота)
    release: bool = False         # новая точка — повод для рубрики «Цифра вышла» / «Бензин»
    release_code: str | None = None   # код ряда в календаре выходов, если отличается
    fuel: bool = False
    digits: int = 2
    period: bool = False          # точка относится к периоду (месяц, квартал), а не к дню


WATCH: tuple[Watch, ...] = (
    Watch("fuel-diesel", "Дизель", "₽ за литр", chart="diesel", release=True, fuel=True),
    Watch("fuel-ai92", "Бензин АИ-92", "₽ за литр", chart="ai92", release=True, fuel=True),
    Watch("fuel-ai95", "Бензин АИ-95", "₽ за литр", chart="ai95", release=True, fuel=True),
    Watch("cpi-yoy", "Инфляция за год", "%", is_rate=True, chart="inflation", release=True, release_code="cpi", period=True),
    Watch("cpi-food-yoy", "Продукты, рост цен за год", "%", is_rate=True, period=True),
    Watch("cpi-nonfood-yoy", "Непродовольственные товары, рост цен за год", "%", is_rate=True, period=True),
    Watch("cpi-services-yoy", "Услуги, рост цен за год", "%", is_rate=True, period=True),
    Watch("key-rate", "Ключевая ставка", "%", is_rate=True, chart="keyrate"),
    Watch("deposit-rate", "Средняя ставка по вкладам", "%", is_rate=True, chart="deposit", release=True, period=True),
    Watch("mortgage-rate", "Средняя ставка по ипотеке", "%", is_rate=True, chart="mortgage", release=True, period=True),
    Watch("usd-rub", "Доллар, официальный курс", "₽", chart="usd"),
    Watch("eur-rub", "Евро, официальный курс", "₽", chart="eur"),
    Watch("cny-rub", "Юань, официальный курс", "₽"),
    Watch("gold-price", "Золото, учётная цена Банка России", "₽ за грамм", chart="gold"),
    Watch("brent", "Нефть Brent", "$ за баррель"),
    Watch("imoex", "Индекс Мосбиржи", "пунктов"),
    Watch("wages-nominal", "Средняя зарплата", "₽ в месяц", release=True, digits=0, period=True),
    Watch("unemployment", "Безработица", "%", is_rate=True, release=True, digits=1, period=True),
    Watch("gdp-real-yoy", "ВВП, к тому же кварталу прошлого года", "%", is_rate=True, release=True, period=True),
)
WATCH_BY_CODE = {w.code: w for w in WATCH}
CHART_KEYS = tuple(sorted({w.chart for w in WATCH if w.chart}))


# ---------------------------------------------------------------------------
# Числа и даты по-русски
# ---------------------------------------------------------------------------

def fmt_num(v: float, digits: int = 2) -> str:
    """Число по-русски. Округление — «половина вверх», как считает человек (3 112,5 → 3 113): обычное
    форматирование Python округляет к чётному и расходилось бы со сторожем на рубль."""
    q = Decimal(1).scaleb(-digits) if digits else Decimal(1)
    d = Decimal(repr(round(float(v), 9))).quantize(q, rounding=ROUND_HALF_UP)
    s = f"{d:,.{digits}f}".replace(",", " ").replace(".", ",")
    return s.replace("-", "−")


def fmt_day(d: date, year: bool = True) -> str:
    return f"{d.day} {MONTHS_GEN[d.month - 1]}" + (f" {d.year}" if year else "")


def fmt_period(d: date, freq: str) -> str:
    if freq == "monthly":
        return f"{MONTHS_NOM[d.month - 1]} {d.year}"
    if freq == "quarterly":
        return f"{(d.month - 1) // 3 + 1}-й квартал {d.year}"
    if freq == "annual":
        return f"{d.year} год"
    return fmt_day(d)


def plural(n: int, one: str, few: str, many: str) -> str:
    n10, n100 = abs(n) % 10, abs(n) % 100
    if n10 == 1 and n100 != 11:
        return one
    if 2 <= n10 <= 4 and not 12 <= n100 <= 14:
        return few
    return many


def _half_up(v: float, decimals: int) -> Decimal:
    """Округление «половина вверх» по модулю. Хвост двоичной дроби срезается заранее: (74,72 − 70,01) × 50 в
    числах с плавающей точкой — 235,49999999999997, а человек и калькулятор видят 235,5 → 236."""
    q = Decimal(1).scaleb(-decimals) if decimals else Decimal(1)
    return Decimal(repr(round(abs(float(v)), 9))).quantize(q, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Основания: откуда взято каждое число
# ---------------------------------------------------------------------------

@dataclass
class Basis:
    value: float
    label: str                  # «Дизель · 9 ноября 2026 · Росстат»
    source: str | None = None   # «Росстат» — попадёт в строку источника поста
    kind: str = "data"          # data | derived | forecast | tool | web
    jump: bool = False          # число из ряда с необычным скачком: нужна перепроверка
    digits: int = 2             # с каким числом знаков оно показано модели
    series: str | None = None   # код ряда, к которому относится число


_SP = " \u00a0\u202f\u2009"   # пробелы между разрядами: обычный, неразрывный, узкий
_NUM_RE = re.compile(r"(?<![\d.,])(\d{1,3}(?:[" + _SP + r"]\d{3})+|\d+)(?:[.,](\d+))?")
_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


class Corpus:
    """Все числа и даты, которые модель видела из проверенных мест, с подписью происхождения."""

    def __init__(self) -> None:
        self.items: list[Basis] = []
        self.dates: set[date] = set()
        self.web: list[dict] = []           # [{url, title, content}] — что нашёл поиск

    def n(self, value: float, label: str, digits: int = 2, *, source: str | None = None, kind: str = "data",
          jump: bool = False, series: str | None = None) -> str:
        """Записать число в основания и вернуть его текстом для сводки."""
        self.items.append(Basis(float(value), label, source, kind, jump, digits, series))
        return fmt_num(value, digits)

    def d(self, d: date, year: bool = True) -> str:
        self.dates.add(d)
        return fmt_day(d, year)

    def add_text(self, raw: str, label: str, kind: str = "tool", source: str | None = None) -> None:
        """Числа и даты из свободного текста: ответ инструмента по базе или выдержка из поиска."""
        for m in _ISO_DATE_RE.finditer(raw or ""):
            try:
                self.dates.add(date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
            except ValueError:
                pass
        cleaned = _ISO_DATE_RE.sub(" ", raw or "")
        for m in _NUM_RE.finditer(cleaned):
            whole = re.sub("[" + _SP + "]", "", m.group(1))
            try:
                self.items.append(Basis(float(f"{whole}.{m.group(2)}" if m.group(2) else whole), label, source, kind,
                                        False, len(m.group(2) or "")))
            except ValueError:
                continue

    def add_web(self, url: str, title: str = "", content: str = "") -> None:
        if not url or any(w["url"] == url for w in self.web):
            return
        self.web.append({"url": url, "title": (title or "")[:200], "content": (content or "")[:1500]})
        if content:
            self.add_text(content, f"интернет: {url}", kind="web")

    def find(self, value: float, decimals: int, *, scale: float = 1.0) -> list[Basis]:
        """Основания, совпадающие с числом после округления до его же точности."""
        target = Decimal(repr(abs(value))).quantize(Decimal(1).scaleb(-decimals) if decimals else Decimal(1))
        out = []
        for b in self.items:
            try:
                if _half_up(b.value / scale, decimals) == target:
                    out.append(b)
            except Exception:  # noqa: BLE001 — бесконечность или NaN в основаниях
                continue
        # Свои данные раньше расчётов, расчёты раньше интернета.
        order = {"data": 0, "derived": 1, "forecast": 2, "tool": 3, "report": 4, "web": 5}
        return sorted(out, key=lambda b: order.get(b.kind, 9))


# ---------------------------------------------------------------------------
# Факты по ряду
# ---------------------------------------------------------------------------

@dataclass
class Fact:
    watch: Watch
    source: str
    freq: str
    points: list[tuple[date, float]]              # последние точки по возрастанию даты
    year_ago: tuple[date, float] | None = None
    week_ago: tuple[date, float] | None = None    # для дневных рядов
    month_ago: tuple[date, float] | None = None   # для дневных рядов
    forecast: tuple[date, float] | None = None
    next_release: date | None = None
    high_since: date | None = None                # прошлый раз так высоко было в эту дату
    low_since: date | None = None
    all_time_high: bool = False
    all_time_low: bool = False
    first_date: date | None = None
    streak: int = 0                               # сколько шагов подряд в одну сторону (со знаком)
    jump: float | None = None                     # во сколько раз последний шаг больше обычного, если это скачок
    window_jumps: list = field(default_factory=list)   # [(«за месяц», кратность)] — необычное накопленное изменение
    same_since: date | None = None                # с какой даты значение не меняется (ставки)

    @property
    def last(self) -> tuple[date, float]:
        return self.points[-1]

    @property
    def prev(self) -> tuple[date, float] | None:
        return self.points[-2] if len(self.points) > 1 else None


JUMP_RATIO = 4.0
JUMP_MIN_STEPS = 12


def detect_jump(points: list[tuple[date, float]], is_rate: bool) -> float | None:
    """Последний шаг ряда против обычного шага. Возвращает кратность, если шаг необычно велик.

    Повод: 14.11.2026 золото в базе −4,5 % за день, 09.2026 ставка по ипотеке 10,08 → 8,61. Такое число не должно
    уйти в канал без перепроверки по первоисточнику.
    """
    vals = [v for _, v in points]
    if len(vals) < JUMP_MIN_STEPS + 2:
        return None
    diffs = [abs(b - a) for a, b in zip(vals[:-2], vals[1:-1]) if b != a][-60:]
    if len(diffs) < JUMP_MIN_STEPS:
        return None
    typical = statistics.median(diffs)
    last = abs(vals[-1] - vals[-2])
    if typical <= 0 or last <= 0:
        return None
    ratio = last / typical
    # Мелкие ряды: скачком считаем только заметное изменение (≥ 1 % уровня или ≥ 0,5 пункта у ставок).
    big_enough = last >= 0.5 if is_rate else (vals[-2] != 0 and last / abs(vals[-2]) >= 0.01)
    return round(ratio, 1) if ratio >= JUMP_RATIO and big_enough else None


# Скачок «по накоплению»: дневные шаги обычные, а за неделю или месяц набежало необычно много
# (17.11.2026: нефть за месяц −29 % при обычных дневных шагах). (шагов в окне, слово, порог изменения в %)
JUMP_WINDOWS = ((5, "за неделю", 7.0), (21, "за месяц", 15.0))
JUMP_WINDOW_RATIO = 3.0


def detect_window_jumps(points: list[tuple[date, float]]) -> list[tuple[str, float]]:
    """Для дневного ряда цен: окна, где накопленное изменение и велико само по себе, и в разы больше обычного
    для такого окна. Возвращает [(«за месяц», кратность)]."""
    vals = [v for _, v in points]
    out = []
    for size, word, min_pct in JUMP_WINDOWS:
        if len(vals) < size * 8 or not vals[-1 - size]:
            continue
        last = abs(vals[-1] / vals[-1 - size] - 1) * 100
        past = [abs(vals[i] / vals[i - size] - 1) * 100 for i in range(size, len(vals) - size, size) if vals[i - size]]
        if len(past) < 6:
            continue
        typical = statistics.median(past)
        if typical > 0 and last >= min_pct and last / typical >= JUMP_WINDOW_RATIO:
            out.append((word, round(last / typical, 1)))
    return out


def streak_of(points: list[tuple[date, float]]) -> int:
    """+N — N шагов роста подряд, −N — падения; 0 — последнее изменение нулевое или точек мало."""
    n = 0
    sign = 0
    for (_, a), (_, b) in zip(reversed(points[:-1]), reversed(points[1:])):
        s = (b > a) - (b < a)
        if s == 0 or (sign and s != sign):
            break
        sign = s
        n += 1
    return n * sign


def _nearest(points: list[tuple[date, float]], target: date, tolerance: int) -> tuple[date, float] | None:
    """Точка, ближайшая к дате (при равенстве — более ранняя), не дальше `tolerance` дней."""
    best = None
    for d, v in points:
        gap = abs((d - target).days)
        if gap <= tolerance and (best is None or gap < abs((best[0] - target).days)):
            best = (d, v)
    return best


async def load_fact(db, w: Watch, today: date) -> Fact | None:
    ind = (await db.execute(select(Indicator).where(Indicator.code == w.code))).scalar_one_or_none()
    if ind is None:
        return None
    freq = ind.frequency or ""
    limit = 420 if freq == "daily" else 70
    rows = (await db.execute(
        select(IndicatorData.date, IndicatorData.value).where(IndicatorData.indicator_id == ind.id)
        .order_by(IndicatorData.date.desc()).limit(limit))).all()
    if not rows:
        return None
    points = [(r[0], float(r[1])) for r in reversed(rows)]
    last_d, last_v = points[-1]
    fact = Fact(watch=w, source=ind.source or "", freq=freq, points=points)
    fact.year_ago = _nearest(points[:-1], last_d - timedelta(days=365), 40 if freq != "daily" else 6)
    if freq == "daily":
        fact.week_ago = _nearest(points[:-1], last_d - timedelta(days=7), 3)
        fact.month_ago = _nearest(points[:-1], last_d - timedelta(days=30), 5)
    fact.streak = streak_of(points[-40:])
    fact.jump = detect_jump(points, w.is_rate)
    if freq == "daily" and not w.is_rate:
        fact.window_jumps = detect_window_jumps(points)
    # Рекорды: когда в прошлый раз было так же высоко или так же низко.
    fact.first_date = (await db.execute(
        select(func.min(IndicatorData.date)).where(IndicatorData.indicator_id == ind.id))).scalar_one_or_none()
    prev_v = points[-2][1] if len(points) > 1 else None
    if prev_v is not None and last_v != prev_v:
        if last_v > prev_v:
            hi = (await db.execute(select(func.max(IndicatorData.date)).where(
                IndicatorData.indicator_id == ind.id, IndicatorData.date < last_d,
                IndicatorData.value >= last_v))).scalar_one_or_none()
            fact.high_since, fact.all_time_high = hi, hi is None
        else:
            lo = (await db.execute(select(func.max(IndicatorData.date)).where(
                IndicatorData.indicator_id == ind.id, IndicatorData.date < last_d,
                IndicatorData.value <= last_v))).scalar_one_or_none()
            fact.low_since, fact.all_time_low = lo, lo is None
    elif w.is_rate:
        changed = (await db.execute(select(func.max(IndicatorData.date)).where(
            IndicatorData.indicator_id == ind.id, IndicatorData.value != last_v))).scalar_one_or_none()
        if changed:
            fact.same_since = (await db.execute(select(func.min(IndicatorData.date)).where(
                IndicatorData.indicator_id == ind.id, IndicatorData.date > changed))).scalar_one_or_none()
    fc = (await db.execute(
        select(ForecastValue.date, ForecastValue.value).join(Forecast, Forecast.id == ForecastValue.forecast_id)
        .where(Forecast.indicator_id == ind.id, Forecast.is_current.is_(True), ForecastValue.date > last_d)
        .order_by(ForecastValue.date).limit(1))).first()
    if fc:
        fact.forecast = (fc[0], float(fc[1]))
    from app.api.calendar import _public_calendar_conditions

    nxt = (await db.execute(
        select(func.min(EconomicEvent.scheduled_date)).join(Indicator, Indicator.id == EconomicEvent.indicator_id)
        .where(Indicator.code == (w.release_code or w.code), EconomicEvent.scheduled_date >= today,
               *_public_calendar_conditions()))).scalar_one_or_none()
    fact.next_release = nxt
    return fact


def _change_text(c: Corpus, f: Fact, now: float, before: tuple[date, float], word: str, *, step: bool = False,
                 window_jump: bool = False) -> str:
    """«неделей раньше (2 ноября 2026) 86,38 (+0,25; +0,3 %)» — с записью чисел в основания.
    `step` — сравнение с предыдущей точкой: у ряда со скачком такие числа требуют перепроверки."""
    w = f.watch
    bd, bv = before
    when_plain = fmt_period(bd, f.freq) if w.period else fmt_day(bd)
    label = f"{w.title} · изменение к {when_plain}"
    jump = (bool(f.jump) and step) or window_jump
    was = c.n(bv, f"{w.title} · {when_plain} · {f.source}", w.digits, source=f.source, series=w.code)
    diff = now - bv
    sign = "+" if diff > 0 else ("−" if diff < 0 else "")
    when = when_plain if w.period else c.d(bd)
    if diff == 0:
        return f"{word} ({when}) {was} (без изменений)"
    if w.is_rate:
        ch = f"{sign}{c.n(abs(diff), label, 2, source=f.source, series=w.code, kind='derived', jump=jump)} пункта"
    else:
        pct = (now / bv - 1) * 100 if bv else 0.0
        ch = (f"{sign}{c.n(abs(diff), label, w.digits, source=f.source, series=w.code, kind='derived', jump=jump)}; "
              f"{sign}{c.n(abs(pct), label, 1, source=f.source, series=w.code, kind='derived', jump=jump)} %")
    return f"{word} ({when}) {was} ({ch})"


def fact_lines(c: Corpus, f: Fact, today: date) -> list[str]:
    """Блок ряда для сводки. Все числа записываются в основания."""
    w = f.watch
    ld, lv = f.last
    when = fmt_period(ld, f.freq) if w.period else c.d(ld)
    step_word = {"weekly": "неделей раньше", "monthly": "месяцем раньше", "quarterly": "кварталом раньше",
                 "daily": "в прошлую дату"}.get(f.freq, "раньше")
    freq_word = {"weekly": "раз в неделю", "monthly": "раз в месяц", "quarterly": "раз в квартал",
                 "daily": "по рабочим дням"}.get(f.freq, "")
    head = (f"{w.title} [{w.code}] — {c.n(lv, f'{w.title} · {when} · {f.source}', w.digits, source=f.source, series=w.code, jump=bool(f.jump))} "
            f"{w.unit}, {'за ' if w.period else 'на '}{when}. Источник: {f.source}; выходит {freq_word}.")
    lines = [head]
    cmp_bits = []
    if f.prev:
        cmp_bits.append(_change_text(c, f, lv, f.prev, step_word, step=True))
    wj = {word for word, _ in f.window_jumps}
    if f.week_ago and f.prev and f.week_ago[0] != f.prev[0]:
        cmp_bits.append(_change_text(c, f, lv, f.week_ago, "неделю назад", window_jump="за неделю" in wj))
    if f.month_ago:
        cmp_bits.append(_change_text(c, f, lv, f.month_ago, "месяц назад", window_jump="за месяц" in wj))
    if f.year_ago:
        cmp_bits.append(_change_text(c, f, lv, f.year_ago, "год назад"))
    if cmp_bits:
        lines.append("  Сравнение: " + "; ".join(cmp_bits) + ".")
    notes = []

    def moment(d: date) -> str:
        return fmt_period(d, f.freq) if w.period else c.d(d)

    if abs(f.streak) >= 3:
        forms = {"weekly": ("неделю", "недели", "недель"), "monthly": ("месяц", "месяца", "месяцев"),
                 "quarterly": ("квартал", "квартала", "кварталов")}.get(f.freq, ("рабочий день", "рабочих дня", "рабочих дней"))
        n = abs(f.streak)
        notes.append(f"{'растёт' if f.streak > 0 else 'снижается'} "
                     f"{c.n(n, f'{w.title} · длина серии', 0, kind='derived', series=w.code)} {plural(n, *forms)} подряд")
    if f.all_time_high and f.first_date:
        notes.append(f"это самое высокое значение за всю историю ряда на сайте (с {f.first_date.year} года)")
    elif f.high_since and (ld - f.high_since).days >= 180:
        notes.append(f"так высоко в прошлый раз было: {moment(f.high_since)}")
    if f.all_time_low and f.first_date:
        notes.append(f"это самое низкое значение за всю историю ряда на сайте (с {f.first_date.year} года)")
    elif f.low_since and (ld - f.low_since).days >= 180:
        notes.append(f"так низко в прошлый раз было: {moment(f.low_since)}")
    if f.same_since:
        notes.append(f"значение не меняется, начиная с: {moment(f.same_since)}")
    if notes:
        lines.append("  Замечено: " + "; ".join(notes) + ".")
    if w.fuel:
        tank = f"  Бак {TANK_L} л: {c.n(lv * TANK_L, f'{w.title} · бак {TANK_L} л = цена × {TANK_L}', 0, source=f.source, series=w.code, kind='derived')} ₽"
        if f.year_ago:
            tank += (f"; год назад {c.n(f.year_ago[1] * TANK_L, f'{w.title} · бак {TANK_L} л год назад', 0, source=f.source, series=w.code, kind='derived')} ₽ "
                     f"(разница {c.n(abs(lv - f.year_ago[1]) * TANK_L, f'{w.title} · разница бака к году назад', 0, source=f.source, series=w.code, kind='derived')} ₽)")
        lines.append(tank + ".")
    if w.code == "cpi-yoy":
        lines.append(f"  Для кошелька: что год назад стоило 1 000 ₽, сейчас стоит "
                     f"{c.n(1000 * (1 + lv / 100), 'Инфляция · 1 000 ₽ × (1 + инфляция)', 0, source=f.source, series=w.code, kind='derived')} ₽.")
    if f.forecast:
        fd, fv = f.forecast
        lines.append(f"  Наш расчёт на {fmt_period(fd, f.freq) if w.period else c.d(fd)}: "
                     f"{c.n(fv, f'{w.title} · наш расчёт на {fmt_period(fd, f.freq)}', w.digits, source='расчёт Forecast Economy', kind='forecast', series=w.code)} "
                     f"{w.unit} (одно число; в посте — только с пометкой «наш расчёт»).")
    if f.next_release:
        lines.append(f"  Следующий выход данных: {c.d(f.next_release)}.")
    stale = {"daily": 6, "weekly": 12, "monthly": 95, "quarterly": 230}.get(f.freq, 400)
    if (today - ld).days > stale:
        lines.append("  Внимание: новее у нас пока нет. Вышла ли новая цифра у источника — неизвестно; при необходимости проверь в интернете.")
    if f.jump:
        lines.append(f"  ВНИМАНИЕ, необычный скачок: последнее изменение в {c.n(f.jump, f'{w.title} · во сколько раз шаг больше обычного', 1, kind='derived', series=w.code)} раза больше обычного для этого ряда. "
                     "До публикации перепроверь число в интернете по первоисточнику; не подтвердилось — не используй.")
    for word, ratio in f.window_jumps:
        lines.append(f"  ВНИМАНИЕ, необычный скачок {word}: изменение в "
                     f"{c.n(ratio, f'{w.title} · во сколько раз изменение {word} больше обычного', 1, kind='derived', series=w.code)} "
                     f"раза больше обычного для такого срока. Сравнение «{word.replace('за ', '')} назад» до публикации "
                     "перепроверь в интернете; не подтвердилось — не используй.")
    return lines


def cross_lines(c: Corpus, facts: dict[str, Fact]) -> list[str]:
    """Готовые сопоставления между рядами — частые «подмеченные» детали, посчитанные кодом."""
    out = []
    cpi = facts.get("cpi-yoy")
    for code, word in (("deposit-rate", "Вклады"), ("key-rate", "Ключевая ставка")):
        f = facts.get(code)
        if f and cpi:
            gap = f.last[1] - cpi.last[1]
            out.append(f"{word} против инфляции: {fmt_num(f.last[1])} % и {fmt_num(cpi.last[1])} % — "
                       f"{'выше' if gap > 0 else 'ниже'} на {c.n(abs(gap), f'{word} минус инфляция за год', 2, source=f.source, kind='derived', series=code)} пункта.")
    dz, a95, a92 = facts.get("fuel-diesel"), facts.get("fuel-ai95"), facts.get("fuel-ai92")
    if dz and a95 and dz.last[0] == a95.last[0]:
        gap = dz.last[1] - a95.last[1]
        line = (f"Дизель {'дороже' if gap > 0 else 'дешевле'} АИ-95 на "
                f"{c.n(abs(gap), 'Дизель минус АИ-95, ₽ за литр', 2, source=dz.source, kind='derived', series='fuel-diesel')} ₽ за литр")
        if dz.year_ago and a95.year_ago:
            g0 = dz.year_ago[1] - a95.year_ago[1]
            line += (f"; год назад {'дороже' if g0 > 0 else 'дешевле'} на "
                     f"{c.n(abs(g0), 'Дизель минус АИ-95 год назад', 2, source=dz.source, kind='derived', series='fuel-diesel')} ₽")
        out.append(line + ".")
    if a95 and a92 and a95.last[0] == a92.last[0]:
        out.append(f"АИ-95 дороже АИ-92 на {c.n(a95.last[1] - a92.last[1], 'АИ-95 минус АИ-92', 2, source=a95.source, kind='derived', series='fuel-ai95')} ₽ за литр.")
    for code, word in (("gold-price", "Золото"), ("usd-rub", "Доллар")):
        f = facts.get(code)
        if f and f.year_ago and cpi:
            pct = (f.last[1] / f.year_ago[1] - 1) * 100
            out.append(f"{word} за год: {'+' if pct > 0 else '−'}{fmt_num(abs(pct), 1)} % при росте цен на {fmt_num(cpi.last[1])} %.")
    return out


# ---------------------------------------------------------------------------
# Сторож чисел
# ---------------------------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")
_MONTH_AFTER = re.compile(r"^\s*(" + "|".join(MONTHS_GEN) + r")", re.I)
_UNIT_AFTER = re.compile(r"^\s*(%|₽|\$|руб|пункт|процент|копе|литр|л\b|тыс|млн|млрд|трлн|раз)", re.I)
_SCALE_AFTER = re.compile(r"^\s*(тыс|млн|млрд|трлн)", re.I)
_SCALES = {"тыс": 1e3, "млн": 1e6, "млрд": 1e9, "трлн": 1e12}
_ORDINAL_AFTER = re.compile(r"^-?(й|я|е|го|му|ю|ая|ый|ой|ом|м|х|ти|летн|процентн)\b", re.I)
_OWN_CALC = re.compile(r"наш(его|ему|им|ем)?\s+расч[её]т|по\s+нашему\s+расч[её]ту|наш(его|ему)?\s+прогноз", re.I)
_RANGE = re.compile(r"(?:от\s+)?\d+(?:[.,]\d+)?\s*(?:%|₽)?\s*(?:[–—-]|до)\s*\d+(?:[.,]\d+)?\s*(?:%|₽|пункт)", re.I)
_FORECAST_WORD = re.compile(r"прогноз|расч[её]т|ожида|буд(е|у)т", re.I)
# Слова внутренней кухни и биржевой жаргон: читатель канала их не знает (правило владельца).
JARGON = ("п. п.", "п.п.", "г/г", "м/м", "кв/кв", "ипц", "ицп", "var", "σ", "эластичн", "волатильн", "базисн",
          "дефлятор", "парсер", "etl", "api", "ruonia", "yoy", "mom", "сезонно скорректир", "индекс хвоста",
          "датасет", "эндпоинт", "б.п.")
SMALL_INT_MAX = 12


def plain_text(html_text: str) -> str:
    t = _TAG_RE.sub("", html_text or "")
    t = unescape(t)
    for ch in _SP[1:]:
        t = t.replace(ch, " ")
    t = t.replace("\u2212", "-")
    return t


_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos}
_CONSTANTS = {0, 1, 2, 3, 4, 5, 6, 7, 10, 12, 50, 52, 100, 365, 1000, 10000, 100000, 1000000}


def eval_expr(expr: str) -> tuple[float, list[tuple[float, int]]]:
    """Значение выражения и его числа-операнды (значение, знаков после запятой). Только арифметика.
    Запятая читается как в Python («round(10222.10, 0)»); если так не разбирается — как десятичная («86,63*50»)."""
    base = re.sub(r"\s", "", (expr or "").replace("×", "*").replace("\u2212", "-").replace("^", "**"))[:300]

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return float(n.value)
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow) and abs(b) > 100:
                raise ValueError("слишком большая степень")
            return _OPS[type(n.op)](a, b)
        if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](ev(n.operand))
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("round", "abs", "min", "max")
                and not n.keywords):
            args = [ev(a) for a in n.args]
            if n.func.id == "round":
                return float(_half_up(args[0], int(args[1]) if len(args) > 1 else 0)) * (-1 if args[0] < 0 else 1)
            return float({"abs": abs, "min": min, "max": max}[n.func.id](*args))
        raise ValueError("недопустимое выражение")

    last_error: Exception | None = None
    for src in (base, re.sub(r"(?<=\d),(?=\d)", ".", base)):
        try:
            value = ev(ast.parse(src, mode="eval"))
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue
        operands = [(float(m.group(0)), len(m.group(1) or "")) for m in re.finditer(r"\d+(?:\.(\d+))?", src)]
        return value, operands
    raise ValueError(str(last_error))


@dataclass
class NumToken:
    raw: str
    value: float
    decimals: int
    kind: str            # number | small | date | year | skip
    scale: float = 1.0
    pos: int = 0


def extract_numbers(text_plain: str) -> list[NumToken]:
    out: list[NumToken] = []
    for m in _NUM_RE.finditer(text_plain):
        raw = m.group(0)
        whole = re.sub(r"\s", "", m.group(1))
        frac = m.group(2) or ""
        value = float(f"{whole}.{frac}" if frac else whole)
        before = text_plain[max(0, m.start() - 4):m.start()]
        after = text_plain[m.end():m.end() + 14]
        grouped = bool(re.search(r"\s", m.group(1)))
        kind = "number"
        scale = 1.0
        if re.search(r"(аи|АИ|Аи)-?\s?$", before) or before.endswith("№"):
            kind = "skip"                                   # марка бензина, номер
        elif not frac and re.match(r"^:\d\d", after):
            kind = "skip"                                   # время 10:00
        elif before.endswith(":") and re.search(r"\d:$", before):
            kind = "skip"
        elif not frac and _MONTH_AFTER.match(after):
            kind = "date"
        elif not frac and not grouped and 1900 <= value <= 2100 and not _UNIT_AFTER.match(after):
            kind = "year"
        elif not frac and _ORDINAL_AFTER.match(after):
            kind = "skip"                                   # «95-го», «5-я неделя»
        else:
            sm = _SCALE_AFTER.match(after)
            if sm:
                scale = _SCALES[sm.group(1).lower()]
            elif not frac and not grouped and value <= SMALL_INT_MAX and not re.match(r"^\s*(%|₽|\$|руб|пункт|процент)", after):
                kind = "small"
        out.append(NumToken(raw, value, len(frac), kind, scale, m.start()))
    return out


@dataclass
class Audit:
    numbers: list[dict] = field(default_factory=list)   # {shown, status, basis}
    issues: list[str] = field(default_factory=list)     # закрывают публикацию
    warnings: list[str] = field(default_factory=list)   # показываются владельцу, публикацию не закрывают
    sources: list[str] = field(default_factory=list)    # для строки «Источник: …»

    @property
    def blocked(self) -> bool:
        return bool(self.issues)

    def as_dict(self) -> dict:
        return {"numbers": self.numbers, "issues": self.issues, "warnings": self.warnings, "sources": self.sources}


def _declared_for(tok: NumToken, declared: list[dict]) -> dict | None:
    for d in declared or []:
        shown = plain_text(str(d.get("shown", "")))
        for t in extract_numbers(shown):
            if t.kind in ("number", "small", "year") and t.value == tok.value and t.decimals == tok.decimals:
                return d
    return None


def check_post(text_html: str, corpus: Corpus, declared: list[dict] | None = None, *,
               checks: list[dict] | None = None, web_searches: int = 0, banned: list[str] | None = None,
               reports: bool = False) -> Audit:
    """Сверить каждое число поста с основаниями. Возвращает разбор: что откуда и что не сошлось."""
    audit = Audit()
    plain = plain_text(text_html)
    used_forecast = False
    used_jump: list[str] = []
    tokens = extract_numbers(plain)
    # Ряды «в игре»: те, чьё приметное число (три значащие цифры и больше) стоит в тексте точно как в сводке.
    # Округлённое совпадение засчитывается только с числом ряда в игре или с ответом инструмента: иначе «12,5»
    # случайно совпало бы с курсом юаня 12,54, о котором в посте нет ни слова.
    in_play: set[str] = set()
    for tok in tokens:
        if tok.kind != "number" or len(re.sub(r"\D", "", tok.raw).lstrip("0")) < 3:
            continue
        for b in corpus.find(tok.value, tok.decimals):
            if b.series and b.digits == tok.decimals:
                in_play.add(b.series)

    def candidates(tok: NumToken) -> list[Basis]:
        # «724,30 млрд $»: в данных ряд может уже быть в миллиардах (724,30) или в единицах (724 300 000 000).
        found = corpus.find(tok.value, tok.decimals)
        return found + (corpus.find(tok.value, tok.decimals, scale=tok.scale) if tok.scale != 1.0 else [])

    def usable(tok: NumToken) -> list[Basis]:
        cands = candidates(tok)
        # Числа отчётов раздела «Исследования» — основания только для поста об исследовании (`reports`):
        # иначе «3,4» в посте о топливе совпало бы с «×3,4» из чужого отчёта.
        cands = [b for b in cands if b.kind != "report" or reports]
        good = [b for b in cands if b.digits == tok.decimals
                or (b.series and b.series in in_play) or b.kind in ("tool", "web", "report")]
        order = {"data": 0, "derived": 1, "forecast": 2, "tool": 3, "report": 4, "web": 5}
        # В посте об исследовании число отчёта важнее случайного совпадения с рядом, о котором в посте нет ни слова.
        return sorted(good, key=lambda b: (0 if (b.series and b.series in in_play) else (1 if b.kind == "report" else 2),
                                           0 if b.digits == tok.decimals else 1, order.get(b.kind, 9)))

    for tok in tokens:
        if tok.kind == "skip":
            continue
        if tok.kind == "date":
            m = _MONTH_AFTER.match(plain[tok.pos + len(tok.raw):tok.pos + len(tok.raw) + 14])
            month = MONTHS_GEN.index(m.group(1).lower()) + 1 if m else 0
            ok = any(d.day == int(tok.value) and d.month == month for d in corpus.dates)
            shown = f"{tok.raw} {m.group(1) if m else ''}".strip()
            audit.numbers.append({"shown": shown, "status": "date" if ok else "date_unknown",
                                  "basis": "дата есть в данных" if ok else "такой даты в данных нет"})
            if not ok:
                audit.warnings.append(f"дата «{shown}» не найдена в данных — проверьте")
            continue
        if tok.kind == "year":
            audit.numbers.append({"shown": tok.raw, "status": "year", "basis": "год"})
            continue
        decl = _declared_for(tok, declared or [])
        basis_kind = (decl or {}).get("basis")
        if decl and basis_kind == "calc":
            try:
                value, operands = eval_expr(str(decl.get("expr", "")))
                same = _half_up(tok.value, tok.decimals) in (_half_up(value, tok.decimals),
                                                             _half_up(value / tok.scale, tok.decimals))
                foreign = [o for o, dec in operands
                           if not corpus.find(o, dec) and not (dec == 0 and o in _CONSTANTS)
                           and not any(_half_up(float(x.value), dec) == _half_up(o, dec)
                                       for dd in (declared or []) if dd.get("basis") == "assumption"
                                       for x in extract_numbers(plain_text(str(dd.get("shown", "")))))]
                if same and not foreign:
                    audit.numbers.append({"shown": tok.raw, "status": "calc",
                                          "basis": f"расчёт: {decl.get('expr')} = {fmt_num(value, max(tok.decimals, 2))}"})
                    for o, dec in operands:
                        if dec == 0 and o in _CONSTANTS:
                            continue
                        for b in [x for x in corpus.find(o, dec) if x.kind != "report"][:1]:
                            if b.source and b.source not in audit.sources:
                                audit.sources.append(b.source)
                            used_forecast = used_forecast or b.kind == "forecast"
                    continue
                why = ("результат расчёта другой: " + fmt_num(value, max(tok.decimals, 2))) if not same else \
                    ("в расчёте есть числа не из данных: " + ", ".join(fmt_num(o, 2) for o in foreign))
            except Exception:  # noqa: BLE001
                why = f"расчёт «{decl.get('expr')}» не разобран"
            # Расчёт не подтвердился. Если само число есть в данных (модель объявила расчётом простое округление),
            # оно сверяется обычным порядком ниже; иначе — не сошлось.
            if not [b for b in usable(tok) if b.kind != "web"]:
                audit.numbers.append({"shown": tok.raw, "status": "unmatched", "basis": why})
                audit.issues.append(f"число «{tok.raw}»: {why}")
                continue
        if decl and basis_kind == "assumption" and not [b for b in usable(tok) if b.kind != "web"]:
            # Допущением число считается, только если его нет в данных: данные важнее объявления автора.
            audit.numbers.append({"shown": tok.raw, "status": "assumption",
                                  "basis": "условное допущение: " + str(decl.get("note") or "названо в тексте")})
            continue
        found = usable(tok)
        if decl and basis_kind == "web":
            url = str(decl.get("url") or "")
            web_hit = [b for b in found if b.kind == "web" and (not url or url in b.label)]
            if web_hit:
                audit.numbers.append({"shown": tok.raw, "status": "web", "basis": web_hit[0].label})
                host = re.sub(r"^https?://(www\.)?([^/]+).*$", r"\2", url or web_hit[0].label.split(": ", 1)[-1])
                if host and host not in audit.sources:
                    audit.sources.append(host)
                continue
            if not [b for b in found if b.kind != "web"]:
                audit.numbers.append({"shown": tok.raw, "status": "unmatched",
                                      "basis": f"числа нет в выдержке со страницы {url or '(адрес не назван)'}"})
                audit.issues.append(f"число «{tok.raw}» из интернета не подтверждено выдержкой страницы")
                continue
        own = [b for b in found if b.kind != "web"]
        if own:
            b = own[0]
            status = {"data": "data", "derived": "derived", "forecast": "forecast", "tool": "tool",
                      "report": "report"}.get(b.kind, "data")
            audit.numbers.append({"shown": tok.raw, "status": status, "basis": b.label})
            if b.source and b.source not in audit.sources:
                audit.sources.append(b.source)
            # Прогноз считаем использованным, только если у числа нет другого основания.
            if all(x.kind == "forecast" for x in own):
                used_forecast = True
            if all(x.jump for x in own):
                used_jump.append(tok.raw)
            continue
        if found:   # только в выдержках поиска, а модель не объявила число как взятое из интернета
            audit.numbers.append({"shown": tok.raw, "status": "unmatched",
                                  "basis": "число есть только на странице из поиска и не объявлено как число из интернета"})
            audit.issues.append(f"число «{tok.raw}» взято из интернета без объявления источника")
            continue
        if tok.kind == "small":
            audit.numbers.append({"shown": tok.raw, "status": "small", "basis": "малое целое, не сверялось"})
            continue
        audit.numbers.append({"shown": tok.raw, "status": "unmatched", "basis": "нет ни в данных, ни в расчётах"})
        audit.issues.append(f"число «{tok.raw}» не найдено в данных и не объявлено как расчёт или допущение")
    if used_forecast and not _OWN_CALC.search(plain):
        audit.issues.append("в тексте есть наш прогноз, но нет слов «наш расчёт»")
    for sent in re.split(r"(?<=[.!?])\s+|\n+", plain):
        if _FORECAST_WORD.search(sent) and _RANGE.search(sent):
            audit.issues.append(f"прогноз дан диапазоном: «{sent.strip()[:90]}»")
            break
    if used_jump:
        confirmed = web_searches > 0 and any((ch.get("result") or "").strip() for ch in (checks or []))
        if not confirmed:
            audit.issues.append("в посте число из ряда с необычным скачком (" + ", ".join(used_jump[:3])
                                + "), а перепроверки в интернете нет")
        else:
            audit.warnings.append("число из ряда с необычным скачком (" + ", ".join(used_jump[:3])
                                  + ") — редактор перепроверил его в интернете; посмотрите, чем подтверждено, прежде чем публиковать")
    from app.services.channel_voice import find_banned

    # Слова «не пишем»: словарь автора (файл + ответы владельца); без него — встроенный список жаргона.
    words = find_banned(plain, banned if banned is not None else list(JARGON))
    if words:
        audit.issues.append("слова из списка «не пишем»: " + ", ".join(f"«{w}»" for w in words))
    return audit


# ---------------------------------------------------------------------------
# Сводка для модели
# ---------------------------------------------------------------------------

@dataclass
class Briefing:
    text: str
    corpus: Corpus
    facts: dict[str, Fact]
    now: datetime
    fresh: list[str]            # коды рядов с новой точкой — повод запуска
    words: str = ""             # словарь автора для системного промпта (раздел words)
    banned: list[str] | None = None   # слова «не пишем» для сторожа


async def _calendar_lines(db, c: Corpus, today: date) -> list[str]:
    from app.api.calendar import _public_calendar_conditions

    rows = (await db.execute(
        select(EconomicEvent.scheduled_date, EconomicEvent.scheduled_time, EconomicEvent.title,
               EconomicEvent.reference_period, EconomicEvent.source, EconomicEvent.importance,
               EconomicEvent.previous_value, Indicator.code)
        .outerjoin(Indicator, Indicator.id == EconomicEvent.indicator_id)
        .where(EconomicEvent.scheduled_date >= today - timedelta(days=1),
               EconomicEvent.scheduled_date <= today + timedelta(days=9),
               EconomicEvent.importance >= 2, ~EconomicEvent.title.ilike("%RUONIA%"),
               *_public_calendar_conditions())
        .order_by(EconomicEvent.scheduled_date, EconomicEvent.importance.desc()).limit(40))).all()
    names = {"rosstat": "Росстат", "cbr": "Банк России", "minfin": "Минфин", "eurostat": "Евростат", "bea": "BEA (США)"}
    release_codes = {(w.release_code or w.code): w.code for w in WATCH}
    out, seen = [], set()
    # У одного выхода бывает несколько строк (ИПЦ: общий, продукты, услуги) — оставляем строку основного ряда.
    for d, t, title, period, source, imp, _prev, code in sorted(rows, key=lambda r: (r[0], -(r[5] or 0), len(r[7] or "zzzzzzzzzz"))):
        key = (d, title)
        if key in seen:
            continue
        seen.add(key)
        line = f"{WEEKDAYS_SHORT[d.weekday()]}, {c.d(d, year=False)}{' ' + t if t else ''} — {title}"
        if period:
            line += f" ({period})"
        line += f". {names.get(source, source)}"
        if imp and imp >= 3:
            line += "; главное событие"
        if code in release_codes:
            line += f"; прошлое значение — в данных, ряд {release_codes[code]}"
        elif code:
            line += f"; ряд {code} (прошлое значение достань через get_series)"
        out.append(line + ".")
    return out


async def _demand_lines(db) -> list[str]:
    """Что смотрели на сайте за 7 дней против предыдущих 7 (русская версия, люди). Только суммы."""
    try:
        if db.get_bind().dialect.name != "postgresql":
            return []
        rows = (await db.execute(text(
            "select regexp_replace(split_part(entry_page,'?',1),'/(19|20)[0-9]{2}(/.*)?$','') p, "
            "count(*) filter (where day >= current_date - 7) w1, count(*) filter (where day < current_date - 7) w0 "
            "from server_sessions where day >= current_date - 14 and not is_bot and not coalesce(is_internal,false) "
            "and coalesce(bot_score,0) < 50 and site_locale = 'ru' group by 1 order by 2 desc limit 14"))).all()
    except Exception:  # noqa: BLE001 — спрос не обязателен для сводки
        logger.info("channel briefing: спрос на сайте не посчитан", exc_info=True)
        return []
    return [f"{p} — {w1} заходов за 7 дней (неделей раньше {w0})" for p, w1, w0 in rows if p and p != "/"]


def _first_last(text_html: str) -> tuple[str, str]:
    lines = [ln.strip() for ln in plain_text(text_html).split("\n") if ln.strip()]
    if not lines:
        return "", ""
    return lines[0][:120], (lines[-1][:120] if len(lines) > 1 else "")


async def _history_lines(db) -> tuple[list[str], list[str]]:
    """(прошлые посты: как начинались, чем заканчивались и как их читали; решения владельца по черновикам)."""
    from app.models import ChannelPost
    from app.services.channel_stats import latest_views

    views = {v["message_id"]: v["views"] for v in await latest_views(db, limit=30)}
    rows = (await db.execute(
        select(ChannelPost).where(ChannelPost.status.in_(("published", "approved", "skipped", "draft")))
        .order_by(ChannelPost.id.desc()).limit(14))).scalars().all()
    from app.services.channel_posts import post_size

    posts, decisions = [], []
    mix = {"short": 0, "medium": 0, "long": 0}
    for p in rows:
        head, tail = _first_last((p.audit or {}).get("body") or p.text)
        if p.status in ("published", "approved"):
            mix[post_size(p)] += 1
        day = fmt_day((p.published_at or p.created_at).date(), year=False)
        if p.status in ("published", "approved"):
            v = views.get(p.telegram_message_id or -1)
            posts.append(f"{day}, {p.rubric}: начало «{head}»" + (f"; конец «{tail}»" if tail else "")
                         + (f" — {v} просмотров" if v is not None else ""))
        if p.status == "draft":
            posts.append(f"{day}, {p.rubric}: «{head}» — черновик ждёт решения владельца, второй такой же не нужен")
        elif p.status == "skipped":
            decisions.append(f"{day}, {p.rubric}: «{head}» — отклонён" + (f": {p.feedback}" if p.feedback else ""))
        elif p.feedback:
            decisions.append(f"{day}, {p.rubric}: «{head}» — правка владельца: {p.feedback}")
        elif p.parent_id is None:
            decisions.append(f"{day}, {p.rubric}: «{head}» — принят без правок")
    if sum(mix.values()):
        posts.insert(0, f"Размеры последних {sum(mix.values())} постов: коротких строк {mix['short']}, средних {mix['medium']}, "
                        f"больших {mix['long']} (ориентир на десять постов — 6, 3 и 1).")
    return posts, decisions[:10]


def _research_lines(limit: int = 6, corpus: "Corpus | None" = None) -> list[str]:
    import json
    from pathlib import Path

    try:
        data = json.loads((Path(__file__).resolve().parent.parent / "data" / "research_catalog.json").read_text("utf-8"))
    except Exception:  # noqa: BLE001
        return []
    out = []
    for it in (data.get("items") or [])[:limit]:
        figs = "; ".join(f"{f.get('value')} — {f.get('label')}" for f in (it.get("figures") or [])[:3])
        line = (f"research:{it.get('slug')} — «{it.get('title')}». {str(it.get('annotation') or '')[:260]}"
                + (f" Цифры отчёта: {figs}." if figs else ""))
        if corpus is not None:
            # Числа аннотации и карточек отчёта — тоже основания: пост об исследовании пишется по ним.
            corpus.add_text(line, f"отчёт «{it.get('title')}» (раздел «Исследования» сайта)", kind="report",
                            source="исследование Forecast Economy")
        out.append(line)
    return out


async def build_briefing(db, now: datetime | None = None, *, fresh: list[str] | None = None,
                         plan_note: str | None = None) -> Briefing:
    """Собрать сводку и основания. `fresh` — коды рядов, у которых появилась новая точка (повод запуска)."""
    from app.services import site_paths
    from app.services.channel_stats import subscribers_trend
    from app.services.locale import ru_public_origin

    now = now or datetime.now(MSK)
    today = now.date()
    c = Corpus()
    facts: dict[str, Fact] = {}
    for w in WATCH:
        try:
            f = await load_fact(db, w, today)
        except Exception:  # noqa: BLE001 — один ряд не должен ронять сводку
            logger.warning("channel briefing: ряд %s не прочитан", w.code, exc_info=True)
            f = None
        if f:
            facts[w.code] = f
    parts = [f"<today>{WEEKDAYS[today.weekday()].capitalize()}, {fmt_day(today)}, {now:%H:%M} по Москве.</today>"]
    if fresh:
        names = ", ".join(f"{WATCH_BY_CODE[code].title} [{code}]" for code in fresh if code in WATCH_BY_CODE)
        parts.append(f"<new_today>С прошлого запуска появились новые точки: {names}.</new_today>")
    data_lines: list[str] = []
    for code, f in facts.items():
        data_lines.extend(fact_lines(c, f, today))
        data_lines.append("")
    parts.append("<fresh_data>\n" + "\n".join(data_lines).rstrip() + "\n</fresh_data>")
    cross = cross_lines(c, facts)
    if cross:
        parts.append("<ready_comparisons>\n" + "\n".join(cross) + "\n</ready_comparisons>")
    cal = await _calendar_lines(db, c, today)
    parts.append("<calendar>\n" + ("\n".join(cal) if cal else "В ближайшие 9 дней в календаре сайта событий нет.") + "\n</calendar>")
    demand = await _demand_lines(db)
    if demand:
        parts.append("<site_demand>\nС каких страниц люди заходят на сайт из поиска (это то, что им интересно):\n"
                     + "\n".join(demand) + "\n</site_demand>")
    try:
        trend = await subscribers_trend(db, today)
        posts, decisions = await _history_lines(db)
    except Exception:  # noqa: BLE001 — таблиц канала может ещё не быть (показ на боевой базе до миграции)
        logger.info("channel briefing: история канала не прочитана", exc_info=True)
        await db.rollback()
        trend, posts, decisions = None, [], []
    ch = []
    if trend:
        ch.append(f"Подписчиков: {trend[0]}" + (f" ({'+' if trend[1] > 0 else ''}{trend[1]} за неделю)" if trend[1] else "") + ".")
    ch.append("Последние посты (не повторяй их ходы — начни и закончи иначе):\n" + "\n".join(posts) if posts else
              "Автор ещё ничего не публиковал: это первые посты канала в новом виде. "
              "До этого в канале шли PDF-отчёты пачками, их почти не открывали.")
    parts.append("<channel>\n" + "\n".join(ch) + "\n</channel>")
    if decisions:
        parts.append("<owner_decisions>\nЧто владелец решал по прошлым черновикам (учись на этом его вкусу):\n"
                     + "\n".join(decisions) + "\n</owner_decisions>")
    if plan_note:
        parts.append("<week_plan>\n" + plan_note.strip()[:1500] + "\n</week_plan>")
    research = _research_lines(corpus=c)
    if research:
        parts.append("<research_queue>\n" + "\n".join(research) + "\n</research_queue>")
    pages = "; ".join(f"{w.code} → {ru_public_origin()}{site_paths.russia_indicator(w.code)}" for w in WATCH)
    parts.append("<pages>\nСтраницы сайта, на которые может вести ссылка под постом (поле link — код ряда): "
                 + pages + f"; calendar → {ru_public_origin()}{site_paths.calendar()}; home → {ru_public_origin()}/.\n</pages>")
    from app.services.channel_voice import load_voice

    words, banned = await load_voice(db)
    return Briefing(text="\n\n".join(parts), corpus=c, facts=facts, now=now, fresh=list(fresh or []),
                    words=words, banned=banned)

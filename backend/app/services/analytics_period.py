"""Единый период BI-аналитики: московское время как ось всего дашборда.

Директива владельца (BI 2.1, 2026-07-06): «день» — это 00:00 МСК → текущий
момент, а не «последние 24 часа»; произвольный период задаётся датами МСК.
Все витрины получают один объект Period и фильтруют им оба слоя данных:

- datetime-колонки (occurred_at/started_at, UTC naive) — `start <= x < end`;
- day-колонки rollup'ов и Метрики — `start_date <= day <= end_date`
  (день везде определён по МСК: Метрика отдаёт визиты в таймзоне счётчика,
  сессионизация с BI 2.1 кладёт day по МСК — см. analytics_rollups).

Пресеты: today / yesterday / 7d / 30d / 90d / custom(from,to — даты МСК).
N-дневные окна выровнены по границе МСК-суток и включают сегодня.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

MSK = timezone(timedelta(hours=3))
MSK_OFFSET = timedelta(hours=3)

PRESETS = ("today", "yesterday", "7d", "30d", "90d", "custom")

_PRESET_LABELS = {
    "today": "Сегодня",
    "yesterday": "Вчера",
    "7d": "7 дней",
    "30d": "30 дней",
    "90d": "90 дней",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _msk_now() -> datetime:
    return _utcnow() + MSK_OFFSET


def _to_utc(msk_naive: datetime) -> datetime:
    return msk_naive - MSK_OFFSET


@dataclass(frozen=True)
class Period:
    """Полуинтервал [start, end) в UTC naive + МСК-даты для day-колонок."""
    start: datetime
    end: datetime
    preset: str
    start_date: date  # первый МСК-день периода
    end_date: date    # последний МСК-день периода (включительно)

    @property
    def days(self) -> int:
        """Длина периода в днях (≥1) — для лимитов и legacy-подокон."""
        return max(1, (self.end_date - self.start_date).days + 1)

    @property
    def label(self) -> str:
        if self.preset in _PRESET_LABELS:
            return _PRESET_LABELS[self.preset]
        if self.start_date == self.end_date:
            return self.start_date.strftime("%d.%m.%Y")
        return f"{self.start_date.strftime('%d.%m.%Y')}–{self.end_date.strftime('%d.%m.%Y')}"

    def tail(self, n: int) -> "Period":
        """Хвостовое подокно: последние n МСК-дней периода (для тяжёлых
        витрин надёжности, где 90-дневный скан избыточен)."""
        if self.days <= n:
            return self
        d_from = self.end_date - timedelta(days=n - 1)
        start = _to_utc(datetime.combine(d_from, datetime.min.time()))
        return Period(max(start, self.start), self.end, "custom", d_from, self.end_date)

    def to_meta(self) -> dict:
        """Блок для ответа API: фронт подписывает окна на карточках."""
        return {
            "preset": self.preset,
            "label": self.label,
            "from": self.start_date.isoformat(),
            "to": self.end_date.isoformat(),
            "days": self.days,
            "tz": "Europe/Moscow",
        }


def resolve_period(
    preset: str = "30d",
    date_from: date | str | None = None,
    date_to: date | str | None = None,
) -> Period:
    """Пресет либо custom-даты (МСК) → Period. Некорректный ввод мягко
    падает в 30d — дашборд не должен 500-ить из-за кривого query-параметра."""
    now_msk = _msk_now()
    today_msk = now_msk.date()

    if preset == "custom":
        d_from = _coerce_date(date_from)
        d_to = _coerce_date(date_to) or today_msk
        if not d_from:
            return resolve_period("30d")
        if d_to < d_from:
            d_from, d_to = d_to, d_from
        d_to = min(d_to, today_msk)
        start_msk = datetime.combine(d_from, datetime.min.time())
        end_msk = min(datetime.combine(d_to + timedelta(days=1), datetime.min.time()), now_msk)
        return Period(_to_utc(start_msk), _to_utc(end_msk), "custom", d_from, d_to)

    if preset == "today":
        d = today_msk
        return Period(_to_utc(datetime.combine(d, datetime.min.time())), _to_utc(now_msk), "today", d, d)

    if preset == "yesterday":
        d = today_msk - timedelta(days=1)
        return Period(
            _to_utc(datetime.combine(d, datetime.min.time())),
            _to_utc(datetime.combine(today_msk, datetime.min.time())),
            "yesterday", d, d,
        )

    n = {"7d": 7, "30d": 30, "90d": 90}.get(preset)
    if n is None:
        return resolve_period("30d")
    d_from = today_msk - timedelta(days=n - 1)
    start_msk = datetime.combine(d_from, datetime.min.time())
    return Period(_to_utc(start_msk), _to_utc(now_msk), preset, d_from, today_msk)


def as_period(value: "Period | int | None") -> Period:
    """Нормализация аргумента витрины: int (легаси «дней назад») → период
    последних N МСК-дней; None → 30d; Period — как есть."""
    if isinstance(value, Period):
        return value
    if isinstance(value, int):
        n = max(1, min(int(value), 365))
        if n in (7, 30, 90):
            return resolve_period(f"{n}d")
        today_msk = _msk_now().date()
        d_from = today_msk - timedelta(days=n - 1)
        return Period(
            _to_utc(datetime.combine(d_from, datetime.min.time())),
            _to_utc(_msk_now()),
            "custom", d_from, today_msk,
        )
    return resolve_period("30d")


def _coerce_date(v: date | str | None) -> date | None:
    if isinstance(v, date):
        return v
    if isinstance(v, str) and v:
        try:
            return date.fromisoformat(v[:10])
        except ValueError:
            return None
    return None


def msk_day(dt: datetime) -> date:
    """МСК-день для UTC naive datetime — каноническое определение «дня»
    во всех rollup'ах и сессионизации (BI 2.1)."""
    return (dt + MSK_OFFSET).date()


def msk_day_expr(col, dialect: str):
    """SQL-выражение «МСК-день» для UTC naive datetime-колонки.
    Postgres: date(col + interval '3 hours'); sqlite (тесты): date(col, '+3 hours')."""
    from sqlalchemy import func, text
    if dialect == "postgresql":
        return func.date(col + text("interval '3 hours'"))
    return func.date(col, "+3 hours")


def msk_day_start_utc(d: date) -> datetime:
    """UTC naive момент начала МСК-суток d — нижняя граница для datetime-колонок."""
    return _to_utc(datetime.combine(d, datetime.min.time()))

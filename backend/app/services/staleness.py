"""Мониторинг свежести рядов (Н-3): пороги по частоте, классификация, сводка.

«Источник молча умер» виден не через failed, а через вечный no_new_data:
ежедневная сверка max(data.date) с SLA частоты. Сырой список «все ряды старше
SLA» оказался шумом (2026-09-26: 428 рядов, из них почти всё — годовые
демографические ряды Росстата, которых источник давно не публикует, и их
производные), поэтому просроченные ряды делятся на классы:

* ``source_problem`` — последний прогон парсера упал/деградировал
  (failed/timeout/parsed_zero/fallback_used) или прогонов не было неделю:
  чинится на нашей стороне;
* ``derived_orphan`` — производный ряд просрочен, хотя его первоисточник
  свежий: пересчёт сломан;
* ``frozen`` — парсер читает источник без ошибок, но новых точек нет уже больше
  SLA + один полный период частоты (пропущен целый выпуск): источник не
  публикует, сделать нечего — только счётчик;
* ``derived_follow`` — производные от просроченных первоисточников: отдельной
  информации не несут, только счётчик;
* «в пределах лага» — читаем без ошибок и просрочка не превышает один период
  сверх SLA: не сообщаем (обычная задержка публикации).

Сообщение: ежедневно — только новые просрочки (которых не было в прошлый
прогон), раз в неделю (или при первом прогоне) — полная сводка по группам
«источник · тип парсера», а не строка на каждый ряд.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from html import escape
from typing import Iterable, Mapping, Sequence

# Пороги с запасом на лаг публикации источника (месячный ряд Росстата выходит
# через 4-6 недель после периода). Синхронизированы по духу с freshness-SLA
# страниц /today (`seo_today._STALE_AFTER_DAYS`), но мягче: здесь алерт
# оператору, там — честная рамка пользователю.
STALENESS_SLA_DAYS: dict[str, int] = {
    "daily": 7,
    "weekly": 21,
    "monthly": 75,
    "quarterly": 150,
    "annual": 550,
}
STALENESS_DEFAULT_DAYS = 550  # irregular и незнакомые частоты

# Длина одного периода частоты в днях (календарь, не оценка): сверх SLA ряд
# считается «замороженным», если пропущен целый выпуск.
PERIOD_DAYS: dict[str, int] = {
    "daily": 1,
    "weekly": 7,
    "monthly": 31,
    "quarterly": 92,
    "annual": 366,
}
DEFAULT_PERIOD_DAYS = 366  # как у годового дефолта SLA

# ETL идёт ежедневно (утро + вечер): неделя без единой записи fetch_log —
# парсер не запускался, источник тут ни при чём.
FETCH_SILENCE_DAYS = 7

# fetch_log.status, при которых парсер сам не смог прочитать/разобрать источник
# (словарь — app.services.base_parser). success/no_new_data — прогон здоров.
UNHEALTHY_FETCH_STATUSES = frozenset(
    {"failed", "timeout", "interrupted", "parsed_zero", "fallback_used"}
)

KIND_SOURCE_PROBLEM = "source_problem"
KIND_DERIVED_ORPHAN = "derived_orphan"
KIND_FROZEN = "frozen"

_KIND_LABEL = {
    KIND_SOURCE_PROBLEM: "прогон парсера не удался или давно не шёл",
    KIND_DERIVED_ORPHAN: "производный ряд не пересчитан при свежем источнике",
}

_MAX_GROUPS = 12
_CODES_PER_GROUP = 3


def sla_days(frequency: str | None) -> int:
    return STALENESS_SLA_DAYS.get((frequency or "").lower(), STALENESS_DEFAULT_DAYS)


def period_days(frequency: str | None) -> int:
    return PERIOD_DAYS.get((frequency or "").lower(), DEFAULT_PERIOD_DAYS)


def find_stale(
    rows: Sequence[tuple[str, str | None, date | None]],
    today: date | None = None,
) -> list[tuple[str, int]]:
    """Из (code, frequency, max_date) — [(code, возраст_дней)] сверх SLA.

    Чистая функция для тестируемости; ряды без точек пропускаются (их ловит
    startup catch-up, Н-9).
    """
    today = today or date.today()
    stale: list[tuple[str, int]] = []
    for code, frequency, max_date in rows:
        if max_date is None:
            continue
        age = (today - max_date).days
        if age > sla_days(frequency):
            stale.append((code, age))
    return stale


@dataclass(frozen=True)
class StaleRow:
    code: str
    frequency: str | None
    max_date: date | None
    parser_type: str = ""
    source: str = ""
    last_status: str | None = None        # статус последней записи fetch_log
    last_fetch_at: datetime | None = None


@dataclass(frozen=True)
class StaleItem:
    code: str
    age: int
    family: str
    kind: str
    frequency: str = ""


@dataclass
class StalenessReport:
    """Итог классификации. ``flagged`` = требует внимания + замороженные."""

    attention: list[StaleItem] = field(default_factory=list)   # чинится у нас
    frozen: list[StaleItem] = field(default_factory=list)      # источник молчит
    derived_follow: int = 0                                    # производные от просроченных
    within_lag: int = 0                                        # здоровы, лаг публикации
    total_stale: int = 0                                       # всего старше SLA
    total_active: int = 0

    @property
    def flagged_codes(self) -> set[str]:
        return {i.code for i in self.attention} | {i.code for i in self.frozen}


def family_label(source: str | None, parser_type: str | None) -> str:
    src = (source or "").strip() or "—"
    parser = (parser_type or "").strip() or "—"
    return f"{src} · {parser}"


def derived_roots(
    code: str, derived_sources: Mapping[str, Sequence[str]], _seen: frozenset[str] = frozenset(),
) -> set[str]:
    """Первоисточники (не производные) ряда по графу DERIVED_SPECS."""
    sources = derived_sources.get(code)
    if not sources or code in _seen:
        return set()
    roots: set[str] = set()
    for src in sources:
        if src in derived_sources:
            roots |= derived_roots(src, derived_sources, _seen | {code})
        else:
            roots.add(src)
    return roots


def _fetch_unhealthy(row: StaleRow, now: datetime) -> bool:
    if row.last_status in UNHEALTHY_FETCH_STATUSES:
        return True
    if row.last_fetch_at is not None and (now - row.last_fetch_at).days > FETCH_SILENCE_DAYS:
        return True
    return False


def build_report(
    rows: Iterable[StaleRow],
    derived_sources: Mapping[str, Sequence[str]],
    *,
    today: date | None = None,
    now: datetime | None = None,
) -> StalenessReport:
    today = today or date.today()
    now = now or datetime.combine(today, datetime.min.time())
    rows = list(rows)
    report = StalenessReport(total_active=len(rows))

    stale_rows: list[tuple[StaleRow, int]] = []
    for row in rows:
        if row.max_date is None:
            continue
        age = (today - row.max_date).days
        if age > sla_days(row.frequency):
            stale_rows.append((row, age))
    report.total_stale = len(stale_rows)
    stale_codes = {row.code for row, _ in stale_rows}

    for row, age in stale_rows:
        family = family_label(row.source, row.parser_type)
        freq = (row.frequency or "").lower()
        if row.parser_type == "derived":
            roots = derived_roots(row.code, derived_sources)
            if not roots or all(root in stale_codes for root in roots):
                report.derived_follow += 1
            else:
                report.attention.append(
                    StaleItem(row.code, age, family, KIND_DERIVED_ORPHAN, freq)
                )
            continue
        if _fetch_unhealthy(row, now):
            report.attention.append(
                StaleItem(row.code, age, family, KIND_SOURCE_PROBLEM, freq)
            )
        elif age > sla_days(row.frequency) + period_days(row.frequency):
            report.frozen.append(StaleItem(row.code, age, family, KIND_FROZEN, freq))
        else:
            report.within_lag += 1
    report.attention.sort(key=lambda i: -i.age)
    report.frozen.sort(key=lambda i: -i.age)
    return report


def _group(items: Sequence[StaleItem]) -> list[tuple[tuple[str, str], list[StaleItem]]]:
    groups: dict[tuple[str, str], list[StaleItem]] = {}
    for item in items:
        groups.setdefault((item.family, item.kind), []).append(item)
    ordered = sorted(
        groups.items(), key=lambda kv: (-len(kv[1]), -max(i.age for i in kv[1]), kv[0]),
    )
    return ordered


def _format_groups(items: Sequence[StaleItem]) -> list[str]:
    lines: list[str] = []
    grouped = _group(items)
    for (family, kind), its in grouped[:_MAX_GROUPS]:
        its = sorted(its, key=lambda i: -i.age)
        examples = ", ".join(
            f"<code>{escape(i.code)}</code> {i.age} дн." for i in its[:_CODES_PER_GROUP]
        )
        more = f" и ещё {len(its) - _CODES_PER_GROUP}" if len(its) > _CODES_PER_GROUP else ""
        reason = _KIND_LABEL.get(kind, "")
        reason_part = f" ({escape(reason)})" if reason else ""
        lines.append(
            f"• {escape(family)}: {len(its)}{reason_part} — {examples}{more}"
        )
    if len(grouped) > _MAX_GROUPS:
        rest = sum(len(its) for _, its in grouped[_MAX_GROUPS:])
        lines.append(f"…ещё {len(grouped) - _MAX_GROUPS} групп ({rest} рядов)")
    return lines


def _counters_line(report: StalenessReport) -> str:
    parts = []
    if report.frozen:
        parts.append(
            f"заморожены источником (читаем без ошибок, новых точек нет): {len(report.frozen)}"
        )
    if report.derived_follow:
        parts.append(f"производные от просроченных: {report.derived_follow}")
    if report.within_lag:
        parts.append(f"в пределах лага публикации: {report.within_lag}")
    return "Не требуют действий — " + "; ".join(parts) if parts else ""


def plan_staleness_message(
    report: StalenessReport,
    known: set[str] | None,
    *,
    weekly_due: bool,
    fd_line: str = "",
) -> str | None:
    """Текст сообщения или None (молчим).

    ``known`` — коды, отмеченные в прошлый прогон; None = состояния нет (первый
    прогон/сброс) — тогда шлём полную сводку. Ежедневно — только новые просрочки
    (из ``attention`` и ``frozen``, которых не было), раз в неделю — вся сводка.
    """
    full = weekly_due or known is None
    if full:
        if not report.attention and not report.frozen and not report.derived_follow:
            return None
        head = (
            f"🟡 <b>Staleness check — недельная сводка</b>\n"
            f"Старше SLA: {report.total_stale} из {report.total_active} активных."
        )
        body: list[str] = []
        if report.attention:
            body.append(f"Требуют внимания: {len(report.attention)}")
            body.extend(_format_groups(report.attention))
        else:
            body.append("Требующих действий рядов нет.")
        counters = _counters_line(report)
        if counters:
            body.append(counters)
        return "\n".join([head, *body]) + fd_line

    new_attention = [i for i in report.attention if i.code not in known]
    new_frozen = [i for i in report.frozen if i.code not in known]
    if not new_attention and not new_frozen:
        return None
    new_items = new_attention + new_frozen
    lines = [
        "🟡 <b>Staleness check — новые просрочки</b>",
        f"Новых рядов старше SLA: {len(new_items)}",
        *_format_groups(new_items),
    ]
    chronic = len(report.attention) - len(new_attention)
    if chronic:
        lines.append(f"Прежние просрочки ({chronic}) — в недельной сводке.")
    return "\n".join(lines) + fd_line


# ---------------------------------------------------------------------------
# Память «что уже сообщали» в state-Redis (DB 1). Fail-open: при недоступности
# Redis шлём полную сводку — лучше шум, чем слепота.
# ---------------------------------------------------------------------------

_KNOWN_KEY = "fe:staleness:flagged"
_KNOWN_TTL = 40 * 24 * 3600


async def load_known_flagged() -> set[str] | None:
    try:
        from app.core.cache import get_state_redis

        r = await get_state_redis()
        if not await r.exists(_KNOWN_KEY):
            return None
        return {m.decode() if isinstance(m, bytes) else str(m) for m in await r.smembers(_KNOWN_KEY)}
    except Exception:  # noqa: BLE001
        return None


async def store_known_flagged(codes: set[str]) -> None:
    try:
        from app.core.cache import get_state_redis

        r = await get_state_redis()
        await r.delete(_KNOWN_KEY)
        # Пустой набор тоже должен оставить ключ: «состояние есть, просрочек нет».
        await r.sadd(_KNOWN_KEY, "__seeded__", *sorted(codes))
        await r.expire(_KNOWN_KEY, _KNOWN_TTL)
    except Exception:  # noqa: BLE001
        pass

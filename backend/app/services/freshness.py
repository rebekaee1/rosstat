"""Сторож свежести (круг 12): какие публичные ряды платформы отстали и почему.

Правило «просрочен» то же, что видит посетитель в значке свежести страницы
(`frontend/src/lib/dataFreshness.js`): возраст считается от **конца периода**
последней точки (точка «2026-08-01» месячного ряда описывает август, возраст идёт
с 31 августа), порог `stale` зависит от частоты. Так серверный сторож, аудит и
надпись «Устарело: данные до …» на странице не расходятся.

Покрытие: Россия (`indicators`), мир (`world_indicators`, только листингованные
ряды), регионы России (`region_indicators`, `region_monthly_data`), зарубежные
регионы (`subnational_*`). Для каждого источника считается число рядов, число
просроченных, примеры и причина по классам:

* ``source``   (а) сам источник не публикует или закрыл ряд;
* ``parser``   (б) наш парсер/срез сломан или заморожен, а источник жив;
* ``schedule`` (в) задача расписания падала, молчала или опаздывала;
* ``display``  (г) данные свежие, страница показывает старое (не определяется
  по БД, сторож такой класс не выставляет; фиксируется аудитом вручную);
* ``duplicate`` (д) дубль или производный ряд: остановленный дубль с живым каноном
  либо производная от просроченного первоисточника.
"""
from __future__ import annotations

import calendar
import hashlib
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Iterable

logger = logging.getLogger(__name__)

# Дней после конца периода: (fresh, aging). Дальше — stale. Зеркало LIMITS из
# frontend/src/lib/dataFreshness.js; менять только вместе с ним.
FRESHNESS_LIMITS: dict[str, tuple[int, int]] = {
    "daily": (5, 14),
    "weekly": (14, 35),
    "monthly": (60, 120),
    "quarterly": (120, 220),
    "annual": (480, 700),
}
DEFAULT_FREQUENCY = "monthly"

CAUSE_SOURCE = "source"
CAUSE_PARSER = "parser"
CAUSE_SCHEDULE = "schedule"
CAUSE_DUPLICATE = "duplicate"
CAUSE_LABELS = {
    CAUSE_SOURCE: "источник не публикует",
    CAUSE_PARSER: "наш парсер/срез",
    CAUSE_SCHEDULE: "сбой расписания",
    CAUSE_DUPLICATE: "дубль/производный",
}

SUMMARY_KEY = "fe:freshness:summary"
LAST_SENT_KEY = "fe:freshness:last_sent"
SUMMARY_TTL_S = 3 * 24 * 3600
EXAMPLES_PER_GROUP = 3
MAX_GROUPS_IN_MESSAGE = 12
REMINDER_DAYS = 7

# Порог шума (круг 13). Без него сообщение приходило бы через день: на стенде при неизменных данных подпись менялась 15 раз за 30 суток,
# потому что мелкие источники по одному ряду переходят границу «Устарело» и появляются в списке. Теперь в подпись и в решение «слать»
# входят только заметные группы, а изменение считается с запасом (гистерезис), от последнего отправленного сообщения.
MATERIAL_MIN_STALE = 10        # группа заметна, если просрочено не меньше стольких рядов
MATERIAL_SHARE = 0.5           # ... или просрочена половина группы (не меньше MATERIAL_SHARE_MIN рядов): источник целиком встал
MATERIAL_SHARE_MIN = 3
CHANGE_RATIO = 0.25            # группа «изменилась», если просрочено на четверть больше или меньше, чем в прошлом сообщении
CHANGE_MIN_ABS = 5             # ... и не меньше, чем на столько рядов
CHANGE_MIN_SIZE = 20           # ... и если в группе (сейчас или тогда) не меньше стольких просроченных: мелочь у границы не считается
MAJOR_CAUSE_SHARE = 0.2        # причина учитывается, если за ней не меньше пятой доли просроченных группы


def normalize_frequency(freq: str | None) -> str:
    f = (freq or "").strip().lower()
    if f == "yearly":
        return "annual"
    return f if f in FRESHNESS_LIMITS else DEFAULT_FREQUENCY


def period_end(d: date, freq: str | None) -> date:
    """Последний день периода, к которому относится дата точки."""
    f = normalize_frequency(freq)
    if f == "annual":
        return date(d.year, 12, 31)
    if f == "quarterly":
        last_month = ((d.month - 1) // 3 + 1) * 3
        return date(d.year, last_month, calendar.monthrange(d.year, last_month)[1])
    if f == "weekly":
        return date.fromordinal(d.toordinal() + 6)
    if f == "daily":
        return d
    return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


def age_days(last: date, freq: str | None, today: date) -> int:
    return max(0, (today - period_end(last, freq)).days)


def freshness_level(last: date | None, freq: str | None, today: date) -> str | None:
    """fresh | aging | stale (None — даты нет, говорить нечего)."""
    if last is None:
        return None
    fresh, aging = FRESHNESS_LIMITS[normalize_frequency(freq)]
    age = age_days(last, freq, today)
    if age <= fresh:
        return "fresh"
    return "aging" if age <= aging else "stale"


def is_stale(last: date | None, freq: str | None, today: date) -> bool:
    return freshness_level(last, freq, today) == "stale"


@dataclass
class FreshnessGroup:
    domain: str                      # ru | world | regions | subnational
    source: str                      # человекочитаемый источник
    total: int = 0
    stale: int = 0
    causes: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    examples: list[str] = field(default_factory=list)
    example_ages: dict[str, int] = field(default_factory=dict)
    example_counts: dict[str, int] = field(default_factory=dict)
    _candidates: list[tuple[int, int, str]] = field(default_factory=list, repr=False)

    def add(self, total: int, stale: int, cause: str | None = None, example: str | None = None,
            age: int | None = None) -> None:
        self.total += total
        self.stale += stale
        if stale and cause:
            self.causes[cause] += stale
        if stale and example:
            # Примеры — самые крупные по числу рядов, при равенстве самые старые.
            self._candidates.append((stale, age or 0, example))

    def finalize(self) -> "FreshnessGroup":
        best = sorted(self._candidates, key=lambda c: (-c[0], -c[1], c[2]))
        self.examples, self.example_ages, self.example_counts = [], {}, {}
        for weight, age, name in best:
            if name in self.example_ages or name in self.examples:
                continue
            self.examples.append(name)
            self.example_counts[name] = weight
            if age:
                self.example_ages[name] = age
            if len(self.examples) >= EXAMPLES_PER_GROUP:
                break
        return self

    def is_material(self) -> bool:
        """Заметная группа: достаточно просроченных рядов либо источник встал целиком."""
        if self.stale >= MATERIAL_MIN_STALE:
            return True
        return self.stale >= MATERIAL_SHARE_MIN and self.total > 0 and self.stale / self.total >= MATERIAL_SHARE

    def is_whole_source(self) -> bool:
        """Источник встал целиком: просрочена половина его рядов (не меньше трёх)."""
        return self.stale >= MATERIAL_SHARE_MIN and self.total > 0 and self.stale / self.total >= MATERIAL_SHARE

    def major_causes(self) -> list[str]:
        if not self.stale:
            return []
        return sorted(c for c, n in self.causes.items() if n / self.stale >= MAJOR_CAUSE_SHARE)

    def as_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "source": self.source,
            "total": self.total,
            "stale": self.stale,
            "material": self.is_material(),
            "share": round(self.stale / self.total, 4) if self.total else 0.0,
            "causes": dict(self.causes),
            "examples": list(self.examples),
        }


@dataclass
class FreshnessReport:
    generated_at: str
    today: str
    groups: list[FreshnessGroup]

    @property
    def total(self) -> int:
        return sum(g.total for g in self.groups)

    @property
    def stale(self) -> int:
        return sum(g.stale for g in self.groups)

    def stale_groups(self) -> list[FreshnessGroup]:
        return sorted(
            (g for g in self.groups if g.stale), key=lambda g: (-g.stale, g.domain, g.source),
        )

    def as_dict(self) -> dict[str, Any]:
        stale_groups = self.stale_groups()
        by_cause: dict[str, int] = defaultdict(int)
        for g in stale_groups:
            for cause, n in g.causes.items():
                by_cause[cause] += n
        return {
            "generated_at": self.generated_at,
            "today": self.today,
            "rule": "возраст от конца периода последней точки; порог stale как у значка свежести на странице",
            "limits_days": {f: {"fresh": a, "stale_after": b} for f, (a, b) in FRESHNESS_LIMITS.items()},
            "total_series": self.total,
            "stale_series": self.stale,
            "stale_by_cause": dict(by_cause),
            "groups": [g.as_dict() for g in stale_groups],
            "fresh_groups": sum(1 for g in self.groups if not g.stale),
        }

    def material_groups(self) -> list[FreshnessGroup]:
        return [g for g in self.stale_groups() if g.is_material()]

    def digest(self) -> dict[str, dict[str, Any]]:
        """Все группы с просроченными рядами: ключ «домен|источник» → число, главные причины, «источник встал целиком».

        Хранится рядом с последним отправленным сообщением и служит точкой отсчёта для гистерезиса (``digest_changed``).
        """
        return {
            f"{g.domain}|{g.source}": {"stale": g.stale, "causes": g.major_causes(), "whole": g.is_whole_source()}
            for g in self.stale_groups()
        }

    def signature(self) -> str:
        """Устойчивая подпись состава заметных проблем: источник, главные причины, порядок величины."""
        parts = []
        for g in self.material_groups():
            bucket = len(str(g.stale))      # порядок величины, не точное число
            parts.append((g.domain, g.source, bucket, tuple(g.major_causes())))
        return hashlib.sha1(json.dumps(parts, ensure_ascii=False).encode()).hexdigest()[:16]


def digest_changed(current: dict[str, dict[str, Any]], previous: dict[str, dict[str, Any]]) -> str | None:
    """Чем текущая картина заметно отличается от той, о которой сообщали в последний раз (None — ничем).

    Меняется только то, что заметно: источник встал целиком либо снова ожил (``whole``); число просроченных в группе
    выросло или упало на CHANGE_RATIO и не меньше чем на CHANGE_MIN_ABS рядов, когда в группе (сейчас или тогда)
    не меньше CHANGE_MIN_SIZE; в такой группе поменялись главные причины. Мелкая группа у границы порога
    (9 ↔ 10 рядов) сообщения не вызывает.
    """
    empty = {"stale": 0, "causes": [], "whole": False}
    for key in sorted(set(current) | set(previous)):
        cur, prev = current.get(key, empty), previous.get(key, empty)
        if bool(cur.get("whole")) != bool(prev.get("whole")):
            return "whole"
        a, b = int(cur.get("stale") or 0), int(prev.get("stale") or 0)
        if max(a, b) < CHANGE_MIN_SIZE:
            continue
        if abs(a - b) >= CHANGE_MIN_ABS and abs(a - b) >= CHANGE_RATIO * max(b, 1):
            return "size"
        if list(cur.get("causes") or []) != list(prev.get("causes") or []):
            return "causes"
    return None


# ---------------------------------------------------------------------------
# Сбор из БД
# ---------------------------------------------------------------------------

async def collect_freshness(db, today: date | None = None) -> FreshnessReport:
    """Свежесть всех публичных рядов платформы (чистое чтение)."""
    today = today or date.today()
    groups: list[FreshnessGroup] = []
    for collector in (_collect_ru, _collect_world, _collect_regions, _collect_subnational):
        try:
            groups.extend(await collector(db, today))
        except Exception:  # noqa: BLE001 — один домен не должен ронять сводку
            logger.exception("freshness collector %s failed", collector.__name__)
    return FreshnessReport(
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        today=today.isoformat(),
        groups=[g.finalize() for g in groups],
    )


def _ru_cause(parser_type: str, last_status: str | None, last_fetch_at, now: datetime,
              derived_roots_stale: bool) -> str:
    if parser_type == "derived":
        return CAUSE_DUPLICATE if derived_roots_stale else CAUSE_SCHEDULE
    if last_status == "parsed_zero":
        return CAUSE_PARSER
    if last_status in {"failed", "timeout", "interrupted"}:
        return CAUSE_SCHEDULE
    if last_fetch_at is not None and (now - last_fetch_at).days > 7:
        return CAUSE_SCHEDULE
    return CAUSE_SOURCE        # fallback_used / no_new_data / success: источник не даёт нового


async def _collect_ru(db, today: date) -> list[FreshnessGroup]:
    from sqlalchemy import func, select

    from app.models import FetchLog, Indicator, IndicatorData
    from app.services.calculation_engine import DERIVED_SPECS
    from app.services.staleness import derived_roots

    last_status = (
        select(FetchLog.status).where(FetchLog.indicator_id == Indicator.id)
        .order_by(FetchLog.started_at.desc()).limit(1).correlate(Indicator).scalar_subquery()
    )
    last_fetch_at = (
        select(func.max(FetchLog.started_at)).where(FetchLog.indicator_id == Indicator.id)
        .correlate(Indicator).scalar_subquery()
    )
    rows = (
        await db.execute(
            select(
                Indicator.code, Indicator.frequency, Indicator.source, Indicator.parser_type,
                func.max(IndicatorData.date), last_status, last_fetch_at,
            )
            .outerjoin(IndicatorData, IndicatorData.indicator_id == Indicator.id)
            .where(Indicator.is_active.is_(True), Indicator.is_listed.is_(True))
            .group_by(Indicator.id)
        )
    ).all()
    derived_sources = {s.dst_code: s.src_codes for s in DERIVED_SPECS}
    stale_codes = {
        code for code, freq, _src, _pt, last, _s, _f in rows if is_stale(last, freq, today)
    }
    now = datetime.combine(today, datetime.min.time())
    groups: dict[str, FreshnessGroup] = {}
    for code, freq, source, parser_type, last, status, fetched_at in rows:
        group = groups.setdefault(
            source or "—", FreshnessGroup("ru", f"Россия · {source or '—'}"),
        )
        stale = is_stale(last, freq, today)
        cause = None
        if stale:
            roots = derived_roots(code, derived_sources) if parser_type == "derived" else set()
            cause = _ru_cause(parser_type or "", status, fetched_at, now,
                              bool(roots) and roots <= stale_codes)
        group.add(1, int(stale), cause, code if stale else None,
                  age_days(last, freq, today) if stale and last else None)
    return list(groups.values())


async def _collect_world(db, today: date) -> list[FreshnessGroup]:
    from sqlalchemy import func, select

    from app.data.world_superseded import is_superseded_dataset
    from app.models import WorldDatasetState, WorldIndicator

    rows = (
        await db.execute(
            select(
                WorldIndicator.provider, WorldIndicator.dataset_id, WorldIndicator.frequency,
                WorldIndicator.history_end, func.count(),
            )
            .where(WorldIndicator.is_listed.is_(True), WorldIndicator.history_end.is_not(None))
            .group_by(
                WorldIndicator.provider, WorldIndicator.dataset_id, WorldIndicator.frequency,
                WorldIndicator.history_end,
            )
        )
    ).all()
    state_rows = (
        await db.execute(
            select(
                WorldDatasetState.provider, WorldDatasetState.dataset_id,
                WorldDatasetState.status, WorldDatasetState.last_update_of_data,
            )
        )
    ).all()
    state = {(p, d): (st, upd) for p, d, st, upd in state_rows}

    # Свежайшая точка набора: отличает «весь набор встал» от «отстала одна страна».
    newest: dict[tuple[str, str], date] = {}
    for provider, dataset, _freq, he, _n in rows:
        key = (provider, dataset)
        if he and (key not in newest or he > newest[key]):
            newest[key] = he

    per_dataset: dict[tuple[str, str], dict[str, Any]] = {}
    for provider, dataset, freq, he, n in rows:
        slot = per_dataset.setdefault(
            (provider, dataset), {"total": 0, "stale": 0, "freq": freq, "age": 0},
        )
        slot["total"] += n
        if is_stale(he, freq, today):
            slot["stale"] += n
            slot["age"] = max(slot["age"], age_days(he, freq, today))

    groups: dict[str, FreshnessGroup] = {}
    for (provider, dataset), slot in per_dataset.items():
        group = groups.setdefault(provider, FreshnessGroup("world", f"Мир · {provider}"))
        cause = None
        if slot["stale"]:
            cause = _world_cause(
                provider, dataset, slot["freq"], state.get((provider, dataset)),
                newest.get((provider, dataset)), today,
                is_superseded_dataset(dataset),
            )
        group.add(slot["total"], slot["stale"], cause,
                  dataset if slot["stale"] else None, slot["age"] or None)
    return list(groups.values())


def _world_cause(provider: str, dataset: str, freq: str | None, state, newest: date | None,
                 today: date, superseded: bool) -> str:
    """Причина просрочки набора (по тому, что известно из базы).

    * остановленный дубль с живым каноном — ``duplicate``;
    * набор в error/skipped — ``schedule``, в карантине структуры — ``parser``;
    * набор целиком встал у нас (самая свежая точка тоже просрочена), хотя по
      оглавлению источника он обновлялся заметно позже конца этой точки (больше
      суммы порогов fresh и stale) — ``parser``: данные есть, срез/база заморожены у нас
      (образец: sts_* Евростата, перешедшие с базы 2015 на 2021);
    * остальное (отстала страна или срез при живом наборе, набор закрыт) — ``source``.
    """
    if superseded:
        return CAUSE_DUPLICATE
    status, upd = state if state else (None, None)
    if status in {"error", "skipped"}:
        return CAUSE_SCHEDULE
    if status == "quarantine":
        return CAUSE_PARSER
    if newest is not None and upd is not None and is_stale(newest, freq, today):
        gap = (upd - period_end(newest, freq)).days
        fresh_lim, aging_lim = FRESHNESS_LIMITS[normalize_frequency(freq)]
        if gap > fresh_lim + aging_lim:
            return CAUSE_PARSER
    return CAUSE_SOURCE


async def _collect_regions(db, today: date) -> list[FreshnessGroup]:
    from sqlalchemy import func, select

    from app.models import RegionIndicator, RegionMonthlyPoint

    group = FreshnessGroup("regions", "Регионы России · Росстат/ЕМИСС")
    annual = (
        await db.execute(
            select(RegionIndicator.code, RegionIndicator.year_max)
            .where(RegionIndicator.is_listed.is_(True), RegionIndicator.year_max.is_not(None))
        )
    ).all()
    for code, year_max in annual:
        last = date(int(year_max), 1, 1)
        stale = is_stale(last, "annual", today)
        group.add(1, int(stale), CAUSE_SOURCE if stale else None, code if stale else None,
                  age_days(last, "annual", today) if stale else None)
    monthly = (
        await db.execute(
            select(RegionMonthlyPoint.indicator_id, func.max(RegionMonthlyPoint.month))
            .group_by(RegionMonthlyPoint.indicator_id)
        )
    ).all()
    for indicator_id, yyyymm in monthly:
        last = date(int(yyyymm) // 100, int(yyyymm) % 100, 1)
        stale = is_stale(last, "monthly", today)
        label = f"region-monthly:{indicator_id}"
        group.add(1, int(stale), CAUSE_SCHEDULE if stale else None, label if stale else None,
                  age_days(last, "monthly", today) if stale else None)
    return [group]


async def _collect_subnational(db, today: date) -> list[FreshnessGroup]:
    from sqlalchemy import func, select

    from app.models import SubnationalDataPoint, SubnationalIndicator

    latest = (
        select(SubnationalDataPoint.indicator_id.label("iid"), func.max(SubnationalDataPoint.period).label("mp"))
        .group_by(SubnationalDataPoint.indicator_id).subquery()
    )
    rows = (
        await db.execute(
            select(
                SubnationalIndicator.country_code, SubnationalIndicator.provider,
                SubnationalIndicator.frequency, SubnationalIndicator.code, latest.c.mp,
            )
            .join(latest, latest.c.iid == SubnationalIndicator.id)
            .where(SubnationalIndicator.is_listed.is_(True))
        )
    ).all()
    groups: dict[tuple[str, str], FreshnessGroup] = {}
    for country, provider, freq, code, mp in rows:
        group = groups.setdefault(
            (country, provider), FreshnessGroup("subnational", f"Регионы · {country} · {provider}"),
        )
        stale = is_stale(mp, freq, today)
        group.add(1, int(stale), CAUSE_SOURCE if stale else None, code if stale else None,
                  age_days(mp, freq, today) if stale else None)
    return list(groups.values())


# ---------------------------------------------------------------------------
# Сообщение и решение «слать/молчать»
# ---------------------------------------------------------------------------

def _html(text: str) -> str:
    from html import escape

    return escape(str(text))


def _example_text(g: FreshnessGroup, name: str) -> str:
    n = g.example_counts.get(name, 1)
    age = g.example_ages.get(name)
    tail = ""
    if n > 1:
        tail = f" ×{n}" + (f" (старейший {age} дн.)" if age else "")
    elif age:
        tail = f" {age} дн."
    return f"<code>{_html(name)}</code>{tail}"


def format_message(
    report: FreshnessReport, *, limit: int = MAX_GROUPS_IN_MESSAGE, previous: dict | None = None,
) -> str:
    """Одно сгруппированное сообщение: источник · рядов · примеры · причины.

    Заметные группы перечислены по одной, мелкие (один-два ряда на границе порога) одной строкой «ещё N».
    ``previous`` — запись последнего отправленного сообщения: показываем, как изменилась картина.
    """
    groups = report.material_groups()
    small = [g for g in report.stale_groups() if not g.is_material()]
    head = (
        f"Просрочено {report.stale} из {report.total} публичных рядов "
        f"(правило как у значка «Устарело» на страницах)."
    )
    prev_stale = (previous or {}).get("stale")
    if isinstance(prev_stale, int) and prev_stale != report.stale:
        diff = report.stale - prev_stale
        head += f" В прошлом сообщении: {prev_stale} ({'+' if diff > 0 else '−'}{abs(diff)})."
    lines = ["🟡 <b>Сторож свежести</b>", head]
    for g in groups[:limit]:
        examples = ", ".join(_example_text(g, e) for e in g.examples)
        causes = ", ".join(
            f"{_html(CAUSE_LABELS.get(c, c))} {n}"
            for c, n in sorted(g.causes.items(), key=lambda kv: -kv[1])
        )
        lines.append(
            f"• {_html(g.source)}: {g.stale} из {g.total}"
            + (f" — {examples}" if examples else "")
            + (f" [{causes}]" if causes else "")
        )
    hidden = groups[limit:]
    if hidden:
        lines.append(f"…ещё {len(hidden)} источников ({sum(g.stale for g in hidden)} рядов)")
    if small:
        lines.append(
            f"Мелких источников с отдельными рядами за порогом: {len(small)} ({sum(g.stale for g in small)} рядов), "
            "в сообщении не перечислены; полный список: /api/v1/health/freshness."
        )
    return "\n".join(lines)


def decide_send(
    report: FreshnessReport,
    *,
    min_stale: int,
    previous: dict | None,
    now: datetime,
) -> tuple[bool, str]:
    """(слать?, причина). Одно и то же не повторяем чаще напоминания раз в неделю.

    * просрочено меньше порога — молчим;
    * сообщений ещё не было — шлём;
    * картина заметно изменилась относительно **последнего отправленного** сообщения
      (``digest_changed``: появилась или исчезла заметная группа, поменялись главные причины,
      группа выросла или сократилась на четверть и не меньше чем на 5 рядов) — шлём;
    * иначе, если напоминание старше REMINDER_DAYS суток — шлём;
    * иначе молчим (мелкие колебания на границе порога не считаются).
    Состояние старого формата (только подпись) сравнивается по подписи.
    """
    if report.stale < min_stale:
        return False, "below_threshold"
    if not previous:
        return True, "first"
    prev_digest = previous.get("digest")
    if isinstance(prev_digest, dict):
        change = digest_changed(report.digest(), prev_digest)
        if change:
            return True, f"changed:{change}"
    elif previous.get("signature") != report.signature():
        return True, "changed"
    try:
        sent_at = datetime.fromisoformat(previous.get("sent_at", ""))
    except ValueError:
        return True, "bad_state"
    if (now - sent_at).days >= REMINDER_DAYS:
        return True, "reminder"
    return False, "unchanged"


async def load_last_sent() -> dict | None:
    try:
        from app.core.cache import get_state_redis

        r = await get_state_redis()
        raw = await r.get(LAST_SENT_KEY)
        if not raw:
            return None
        return json.loads(raw if isinstance(raw, str) else raw.decode())
    except Exception:  # noqa: BLE001
        return None


async def store_last_sent(
    signature: str, now: datetime, digest: dict | None = None, stale: int | None = None,
) -> None:
    try:
        from app.core.cache import get_state_redis

        r = await get_state_redis()
        await r.set(
            LAST_SENT_KEY,
            json.dumps(
                {
                    "signature": signature, "sent_at": now.replace(microsecond=0).isoformat(),
                    "digest": digest, "stale": stale,
                },
                ensure_ascii=False,
            ),
            ex=30 * 24 * 3600,
        )
    except Exception:  # noqa: BLE001
        pass


async def store_summary(summary: dict) -> None:
    try:
        from app.core.cache import get_state_redis

        r = await get_state_redis()
        await r.set(SUMMARY_KEY, json.dumps(summary, ensure_ascii=False), ex=SUMMARY_TTL_S)
    except Exception:  # noqa: BLE001
        pass


async def load_summary() -> dict | None:
    try:
        from app.core.cache import get_state_redis

        r = await get_state_redis()
        raw = await r.get(SUMMARY_KEY)
        if not raw:
            return None
        return json.loads(raw if isinstance(raw, str) else raw.decode())
    except Exception:  # noqa: BLE001
        return None

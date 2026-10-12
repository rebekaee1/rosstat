"""Смена базы индекса у Евростата: один показатель, один смысл, актуальные данные.

Круг 12 (12.10.2026). Евростат с 2024 пересчитывает индексы короткосрочной статистики
(`sts_*`) на базу 2021=100 (единица ``I21``), а старую базу 2015=100 (``I15``) оставляет
в кодлисте набора без новых данных. Наши срезы были закреплены на ``I15`` и стояли на
декабре 2023, хотя у источника есть данные до 2026-08 (6 511 публичных рядов 61 набора).

Что делает этот модуль при записи среза с индексной единицей:

* **Перенос базы на месте.** Если у страны уже есть карточка того же набора и того же
  среза, отличающаяся только более старой базой (``I15`` против ``I21``), и новый ряд
  повторяет её по форме на всей общей истории (смена базы индекса — умножение на
  константу; у сезонно скорректированных рядов к этому добавляются пересмотры истории),
  карточка переподключается к новому срезу: тот же
  код и адрес страницы, та же страница в поиске и sitemap, история не теряется,
  значения берутся из источника в новой базе. Один показатель, никаких двойников и
  редиректов. Прогнозы такой карточки снимаются с публикации (они в старом масштабе),
  ближайший прогон пересчитает их по новым данным.
* **Двойник.** Если пересчёт не подтвердился (новая база с короткой историей, ряд
  пересмотрен так, что множитель не постоянен), ряды разных баз не склеиваются: создаётся
  карточка новой базы, старая снимается с листинга и ведёт 301 на неё
  (``resolve_world_base_twin``). Это честная замена, а не склейка.

Каждое событие попадает в ``REBASE_EVENTS`` и в журнал загрузки набора
(``world_ingest_dataset_logs.note``), структурная проверка (`eurostat_structure`) считает
такую смену ожидаемой и не отправляет набор в карантин.
"""
from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable

from sqlalchemy import select, update

logger = logging.getLogger(__name__)

# Подтверждение «тот же ряд в другой базе». Чистое умножение на константу бывает только
# у несезонных рядов; у сезонно скорректированных (SCA) история пересчитывается заново
# с каждым выпуском, и за три года заморозки отклонения от постоянного множителя
# достигали 2-8 % (медиана) и до 30 % на хвостах (Македония, розница). Поэтому смысл
# проверки: карточка и новый срез описывают один и тот же ряд (форма совпадает), а не
# «числа совпадают дословно». Значения всё равно перезаписываются данными источника.
MIN_OVERLAP = 6
MIN_LEVEL_CORR = 0.8       # корреляция уровней на общих датах (чужой ряд: около 0 или меньше)
MIN_CHANGE_CORR = 0.5      # корреляция изменений период к периоду
MIN_COVERAGE = 0.97        # доля прежних дат, которые есть в новом ряду (история не теряется)
FACTOR_RANGE = (0.2, 5.0)
EXACT_REL_TOL = 0.02       # «точное» совпадение с множителем: для отчёта, не для решения
EXACT_ROUND_TOL = 0.055


@dataclass(frozen=True)
class RebaseFit:
    ok: bool
    factor: float = 0.0
    overlap: int = 0
    share: float = 0.0         # доля точек, совпавших с множителем в пределах допуска (справочно)
    coverage: float = 0.0
    reason: str = ""
    level_corr: float = 0.0
    change_corr: float = 0.0


def _index_base_year(unit: str | None) -> int | None:
    from app.services.eurostat_parser import index_base_year

    return index_base_year(unit)


def _index_suffix(unit: str | None) -> str:
    from app.services.eurostat_parser import index_unit_suffix

    return index_unit_suffix(unit)


def is_base_coded_index(unit: str | None) -> bool:
    return _index_base_year(unit) is not None


def rebase_twin_slice(old_slice: dict | None, new_slice: dict | None) -> bool:
    """Срезы совпадают во всём, кроме единицы: индекс более старой базы → более новой."""
    old, new = old_slice or {}, new_slice or {}
    if not old or set(old) != set(new):
        return False
    old_unit, new_unit = str(old.get("unit") or ""), str(new.get("unit") or "")
    old_base, new_base = _index_base_year(old_unit), _index_base_year(new_unit)
    if old_base is None or new_base is None or old_base >= new_base:
        return False
    if _index_suffix(old_unit) != _index_suffix(new_unit):
        return False
    return all(old[key] == new[key] for key in old if key != "unit")


def _corr(xs: list[float], ys: list[float]) -> float:
    try:
        return statistics.correlation(xs, ys)
    except (statistics.StatisticsError, ZeroDivisionError):
        return 0.0


def fit_rebase(
    old: list[tuple[date, float]], new: list[tuple[date, float]],
) -> RebaseFit:
    """Новый срез описывает тот же ряд, что прежняя карточка (смена базы индекса)?"""
    new_by_date = {d: float(v) for d, v in new}
    old_dates = {d for d, _ in old}
    if not old_dates:
        return RebaseFit(False, reason="у прежней карточки нет точек")
    coverage = len(old_dates & set(new_by_date)) / len(old_dates)
    pairs = sorted(
        (d, float(v), new_by_date[d]) for d, v in old
        if d in new_by_date and float(v) != 0 and new_by_date[d] != 0
    )
    if len(pairs) < MIN_OVERLAP:
        return RebaseFit(False, overlap=len(pairs), coverage=coverage,
                         reason="мало общих точек для сверки")
    factor = statistics.median(o / n for _d, o, n in pairs)
    if not (FACTOR_RANGE[0] <= factor <= FACTOR_RANGE[1]):
        return RebaseFit(False, factor=factor, overlap=len(pairs), coverage=coverage,
                         reason="множитель вне разумных пределов")
    olds = [o for _d, o, _n in pairs]
    news = [n for _d, _o, n in pairs]
    level_corr = _corr(olds, news)
    old_chg = [olds[i + 1] / olds[i] - 1 for i in range(len(olds) - 1)]
    new_chg = [news[i + 1] / news[i] - 1 for i in range(len(news) - 1)]
    change_corr = _corr(old_chg, new_chg)
    hits = sum(
        1 for o, n in zip(olds, news)
        if abs(o - factor * n) <= EXACT_REL_TOL * abs(o) + EXACT_ROUND_TOL * (1.0 + factor)
    )
    share = hits / len(pairs)
    common = dict(factor=factor, overlap=len(pairs), share=share, coverage=coverage,
                  level_corr=level_corr, change_corr=change_corr)
    if level_corr < MIN_LEVEL_CORR or change_corr < MIN_CHANGE_CORR:
        return RebaseFit(False, reason="форма рядов не совпадает: это не пересчёт базы", **common)
    if coverage < MIN_COVERAGE:
        return RebaseFit(False, reason="в новой базе короче история: ряды не склеиваются", **common)
    return RebaseFit(True, reason="пересчёт базы подтверждён", **common)


@dataclass
class RebaseEvent:
    kind: str                      # rebased | twin | skipped
    dataset_id: str
    geo_country_id: int
    from_unit: str
    to_unit: str
    indicator_id: int
    code: str
    fit: RebaseFit | None = None
    twin_ids: list[int] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "kind": self.kind, "dataset_id": self.dataset_id,
            "from_unit": self.from_unit, "to_unit": self.to_unit, "code": self.code,
        }
        if self.fit is not None:
            out["factor"] = round(self.fit.factor, 6)
            out["share"] = round(self.fit.share, 3)
            out["level_corr"] = round(self.fit.level_corr, 3)
            out["change_corr"] = round(self.fit.change_corr, 3)
            out["coverage"] = round(self.fit.coverage, 3)
            if not self.fit.ok:
                out["reason"] = self.fit.reason
        return out


REBASE_EVENTS: list[RebaseEvent] = []


def summarize_events(events: Iterable[RebaseEvent]) -> list[dict[str, Any]]:
    """Сводка по набору для журнала загрузки и сообщения в Telegram."""
    by_ds: dict[str, dict[str, Any]] = {}
    for ev in events:
        item = by_ds.setdefault(ev.dataset_id, {
            "dataset_id": ev.dataset_id, "from_unit": ev.from_unit, "to_unit": ev.to_unit,
            "rebased": 0, "twins": 0, "skipped": 0, "examples": [], "twin_reasons": [],
        })
        if ev.kind == "rebased":
            item["rebased"] += 1
        elif ev.kind == "skipped":
            item["skipped"] += 1
        else:
            item["twins"] += 1
            reason = ev.fit.reason if ev.fit is not None else "нет данных для сверки"
            if reason not in item["twin_reasons"] and len(item["twin_reasons"]) < 3:
                item["twin_reasons"].append(reason)
        if len(item["examples"]) < 3:
            item["examples"].append(ev.code)
    return list(by_ds.values())


def describe_summary(summary: dict[str, Any]) -> str:
    """Строка для столбца note журнала загрузки."""
    text_ = (
        f"смена базы индекса {summary['from_unit']}→{summary['to_unit']}: "
        f"перенесено на месте {summary['rebased']}"
    )
    if summary.get("skipped"):
        text_ += f", без новой базы осталось {summary['skipped']} (у источника ряд кончился раньше)"
    if summary.get("twins"):
        text_ += f", заменено новой карточкой {summary['twins']}"
        if summary.get("twin_reasons"):
            text_ += " (" + "; ".join(summary["twin_reasons"]) + ")"
    return text_


@dataclass
class _Row:
    id: int
    code: str
    slice_json: dict
    slice_hash: str
    is_listed: bool
    history_end: date | None


class RebaseContext:
    """Состояние набора на время записи одного среза: карточки по странам."""

    def __init__(self, dataset_id: str, new_slice: dict, new_hash: str, rows: list[tuple]):
        self.dataset_id = dataset_id
        self.new_slice = dict(new_slice)
        self.new_hash = new_hash
        self.new_unit = str(new_slice.get("unit") or "")
        self.by_country: dict[int, list[_Row]] = {}
        for rid, cid, code, sj, sh, listed, hend in rows:
            self.by_country.setdefault(int(cid), []).append(
                _Row(int(rid), str(code), dict(sj or {}), str(sh), bool(listed), hend)
            )

    @classmethod
    async def load(cls, db, dataset_id: str, new_slice: dict, new_hash: str) -> "RebaseContext | None":
        """None, если у среза нет индексной единицы с базой в коде (почти все наборы)."""
        if not is_base_coded_index(str((new_slice or {}).get("unit") or "")):
            return None
        from app.models import WorldIndicator

        rows = (await db.execute(
            select(
                WorldIndicator.id, WorldIndicator.country_id, WorldIndicator.code,
                WorldIndicator.slice_json, WorldIndicator.slice_hash,
                WorldIndicator.is_listed, WorldIndicator.history_end,
            ).where(
                WorldIndicator.provider == "eurostat",
                WorldIndicator.dataset_id == dataset_id,
            )
        )).all()
        ctx = cls(dataset_id, new_slice, new_hash, [tuple(r) for r in rows])
        return ctx if any(
            rebase_twin_slice(r.slice_json, ctx.new_slice)
            for rs in ctx.by_country.values() for r in rs
        ) else None

    def _candidates(self, country_id: int) -> list[_Row]:
        rows = self.by_country.get(country_id, [])
        if any(r.slice_hash == self.new_hash for r in rows):
            return []                      # карточка новой базы уже есть
        olds = [r for r in rows if rebase_twin_slice(r.slice_json, self.new_slice)]
        olds.sort(key=lambda r: _index_base_year(r.slice_json.get("unit")) or 0, reverse=True)
        return olds

    async def retarget(
        self, db, *, country_id: int, points: list[tuple[date, float]],
    ) -> RebaseEvent | None:
        """Переподключить прежнюю карточку к новому срезу, если пересчёт подтверждён."""
        olds = self._candidates(country_id)
        if not olds:
            return None
        from app.models import WorldDataPoint, WorldForecast, WorldIndicator

        last_fit: RebaseFit | None = None
        for old in olds:
            rows = (await db.execute(
                select(WorldDataPoint.date, WorldDataPoint.value)
                .where(WorldDataPoint.indicator_id == old.id)
                .order_by(WorldDataPoint.date)
            )).all()
            fit = fit_rebase([(d, float(v)) for d, v in rows], points)
            last_fit = fit
            if not fit.ok:
                continue
            ind = await db.get(WorldIndicator, old.id)
            from_unit = str(old.slice_json.get("unit") or "")
            ind.slice_json = dict(self.new_slice)
            ind.slice_hash = self.new_hash
            old.slice_json, old.slice_hash = dict(self.new_slice), self.new_hash
            # Прогноз в старом масштабе: снимаем с публикации до пересчёта.
            await db.execute(
                update(WorldForecast)
                .where(WorldForecast.world_indicator_id == old.id, WorldForecast.is_current.is_(True))
                .values(is_current=False)
            )
            await db.flush()
            event = RebaseEvent("rebased", self.dataset_id, country_id, from_unit,
                                self.new_unit, old.id, old.code, fit)
            REBASE_EVENTS.append(event)
            logger.info("Eurostat rebase %s %s: %s→%s x%.4f share=%.2f",
                        self.dataset_id, old.code, from_unit, self.new_unit, fit.factor, fit.share)
            return event
        top = olds[0]
        new_end = points[-1][0] if points else None
        if new_end is not None and top.history_end is not None and new_end <= top.history_end:
            # Новая база не свежее прежней карточки (ряд у источника давно закончился):
            # двойник не создаётся, чтобы не множить устаревшие карточки одного предмета.
            event = RebaseEvent("skipped", self.dataset_id, country_id,
                                str(top.slice_json.get("unit") or ""), self.new_unit, top.id,
                                top.code, last_fit)
            REBASE_EVENTS.append(event)
            logger.info("Eurostat rebase %s %s: new base is not fresher (%s <= %s), twin not created",
                        self.dataset_id, top.code, new_end, top.history_end)
            return event
        event = RebaseEvent("twin", self.dataset_id, country_id,
                            str(top.slice_json.get("unit") or ""), self.new_unit, top.id,
                            top.code, last_fit, [o.id for o in olds])
        REBASE_EVENTS.append(event)
        logger.warning("Eurostat rebase %s %s not confirmed (%s): new card replaces old",
                       self.dataset_id, top.code, last_fit.reason if last_fit else "?")
        return event

    async def retire_twins(self, db, event: RebaseEvent | None, *, new_id: int, new_listed: bool,
                           new_end: date | None) -> None:
        """Прежние карточки без подтверждённого пересчёта уходят с листинга (301 на новую)."""
        if event is None or event.kind != "twin" or not new_listed:
            return
        from app.models import WorldIndicator

        for rid in event.twin_ids:
            if rid == new_id:
                continue
            ind = await db.get(WorldIndicator, rid)
            if ind is None or not ind.is_listed:
                continue
            if new_end is not None and ind.history_end is not None and ind.history_end >= new_end:
                continue                   # прежняя не отстаёт: не трогаем
            ind.is_listed = False
        await db.flush()

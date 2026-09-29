"""Сверка смены структуры набора Eurostat с опубликованными карточками.

TOC Eurostat сообщает дату «last table structure change». Карточки привязаны к
срезам (коды измерений), поэтому новая структура не применяется вслепую: до
записи каждая карточка набора сопоставляется с новой версией.

- Срез с тем же набором кодов есть в новой версии → карточка сохраняется,
  пересмотры значений принимаются как официальные (loader полностью
  перечитывает ряд, смешения старых и новых чисел не бывает).
- Срез пропал (код переименован, добавлено измерение) → ищется единственный
  НОВЫЙ срез той же страны и частоты, чья история совпадает по значениям;
  карточка переподключается к нему с прежним кодом/URL.
- Замены нет → ряд больше не публикуется в этой форме: карточка остаётся с
  прежней историей. Если таких публичных карточек много — это разлом набора,
  и он остаётся в карантине с конкретным отчётом (не вслепую).

Проверено на проде 2026-09-29: у 5 из 21 набора, ушедших в вечный карантин
24–28 сентября, ни один срез не пропал — структура менялась добавлением кодов.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

# Совпадение истории при поиске замены: пересмотры допускаются, другой ряд —
# нет. Сезонная корректировка пересчитывает часть точек; ребазирование индекса
# или другой показатель расходится почти во всех.
_MIN_OVERLAP = 6
_MATCH_SHARE = 0.9
_REL_TOL = 0.01
_ABS_TOL = 1e-9

# Сколько публичных карточек без замены набор может потерять и всё же быть
# принят автоматически: max(абсолют, доля от публичных карточек набора).
_ORPHAN_ABS = 2
_ORPHAN_SHARE = 0.2


@dataclass(frozen=True)
class ExistingSlice:
    indicator_id: int
    geo: str
    slice_json: dict
    slice_hash: str
    is_listed: bool


@dataclass
class StructureVerdict:
    accept: bool
    kept: int = 0
    remapped: dict[int, tuple[dict, str]] = field(default_factory=dict)
    orphans: list[int] = field(default_factory=list)
    orphans_listed: int = 0
    reason: str = ""

    def as_dict(self) -> dict:
        return {
            "accept": self.accept,
            "kept": self.kept,
            "remapped": len(self.remapped),
            "orphans": len(self.orphans),
            "orphans_listed": self.orphans_listed,
            "reason": self.reason,
        }


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= max(_ABS_TOL, _REL_TOL * max(abs(a), abs(b)))


def series_match(
    old: list[tuple[date, float]], new: list[tuple[date, float]]
) -> bool:
    """Тот же ряд: на общем участке ≥ 90% точек совпадают с допуском 1%."""
    new_by_date = dict(new)
    common = [(v, new_by_date[d]) for d, v in old if d in new_by_date]
    if len(common) < _MIN_OVERLAP:
        return False
    hits = sum(1 for a, b in common if _close(float(a), float(b)))
    return hits / len(common) >= _MATCH_SHARE


def _slice_similarity(a: dict, b: dict) -> int:
    return sum(1 for key, value in a.items() if b.get(key) == value)


def _freq(slice_json: dict | None) -> str:
    return str((slice_json or {}).get("freq") or "").upper()


def plan_structure_migration(
    existing: list[ExistingSlice],
    new_series: dict[tuple[str, str], tuple[dict, list[tuple[date, float]]]],
    *,
    old_points: dict[int, list[tuple[date, float]]],
) -> StructureVerdict:
    """Решение по набору: принять (с переподключениями) или оставить в карантине.

    ``new_series`` — (geo, slice_hash) → (slice, points) новой версии;
    ``old_points`` — история только тех карточек, чей срез пропал.
    """
    verdict = StructureVerdict(accept=True)
    claimed = {(e.geo, e.slice_hash) for e in existing if (e.geo, e.slice_hash) in new_series}
    missing: list[ExistingSlice] = []
    for item in existing:
        if (item.geo, item.slice_hash) in new_series:
            verdict.kept += 1
        else:
            missing.append(item)

    taken: set[tuple[str, str]] = set(claimed)
    for item in missing:
        history = old_points.get(item.indicator_id) or []
        candidates = []
        for (geo, new_hash), (new_slice, points) in new_series.items():
            if geo != item.geo or (geo, new_hash) in taken:
                continue
            if _freq(new_slice) != _freq(item.slice_json):
                continue
            if series_match(history, points):
                candidates.append((_slice_similarity(item.slice_json or {}, new_slice), new_hash, new_slice))
        if candidates:
            candidates.sort(key=lambda c: c[0], reverse=True)
            best = candidates[0]
            if len(candidates) == 1 or candidates[1][0] < best[0]:
                verdict.remapped[item.indicator_id] = (best[2], best[1])
                taken.add((item.geo, best[1]))
                continue
        verdict.orphans.append(item.indicator_id)
        if item.is_listed:
            verdict.orphans_listed += 1

    listed_total = sum(1 for e in existing if e.is_listed)
    allowed = max(_ORPHAN_ABS, int(_ORPHAN_SHARE * listed_total))
    if verdict.orphans_listed > allowed:
        verdict.accept = False
        verdict.reason = (
            f"{verdict.orphans_listed} из {listed_total} публичных карточек "
            "не нашли срез в новой структуре"
        )
    else:
        verdict.reason = (
            f"срезов сохранено {verdict.kept}, переподключено {len(verdict.remapped)}, "
            f"без замены {len(verdict.orphans)}"
        )
    return verdict


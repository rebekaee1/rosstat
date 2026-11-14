"""Профиль интересов подписчика (ADR-0033): веса сигналов, затухание, насыщение, уровень данных.

Чистые функции: на вход — список сигналов (вид, предмет, время), на выход — профиль.
Сбор сигналов из базы — `signals.py`.

Правила:
* вклад сигнала = вес × 2^(−возраст / полураспад); у явных сигналов кабинета без затухания;
* повтор того же вида сигнала по тому же предмету в тот же день не суммируется;
* сигналы до регистрации (история посетителя через `identity_links`) × ``PRE_SIGNUP_FACTOR``;
* вес предмета сжимается ``log1p``: сто просмотров одного ряда не забивают остальные интересы;
* показ блока без клика ослабляет предмет (×0,6 за выпуск подряд, до трёх), клик и новое значение сбрасывают.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime

from app.services.newsletter_personal.subjects import Subject, parse_key, topic_for_code

PROFILE_VERSION = 1

# вид сигнала → (вес, полураспад в днях; None — без затухания)
SIGNALS: dict[str, tuple[float, float | None]] = {
    "watch": (10.0, None),
    "favorite": (8.0, 180.0),
    "saved_compare": (3.0, 120.0),
    "pref_topic": (6.0, None),
    "export": (6.0, 60.0),
    "download": (6.0, 60.0),
    "download_limit": (5.0, 30.0),
    "search_select": (4.0, 45.0),
    "search_query": (1.5, 30.0),
    "compare": (2.0, 45.0),
    "forecast_view": (2.0, 45.0),
    "view": (1.0, 30.0),
    "related_click": (1.5, 30.0),
    "tile_click": (0.5, 30.0),
    "topic_click": (0.5, 30.0),
    "landing": (2.0, 90.0),
    "landing_gate": (2.0, 90.0),
    "mail_click": (3.0, 60.0),
}
EXPLICIT = frozenset({"watch", "favorite", "saved_compare", "pref_topic", "export"})
BEHAVIOR = frozenset(SIGNALS) - EXPLICIT - {"landing", "landing_gate", "mail_click"}
PRE_SIGNUP_FACTOR = 0.7
# Показ без клика: множитель за каждый выпуск подряд, не больше FATIGUE_MAX раз.
FATIGUE_FACTOR = 0.6
FATIGUE_MAX = 3
# Уровень данных.
RICH_MIN_SUBJECTS = 3
RICH_MIN_SCORE = 1.4   # log1p-шкала: ≈ 3 «сырых» очка
LIGHT_MIN_SCORE = 0.5  # хотя бы один заметный предмет
MAX_SUBJECTS = 30


@dataclass(frozen=True)
class Signal:
    kind: str
    subject: Subject
    at: datetime
    pre_signup: bool = False


@dataclass
class Profile:
    user_id: str
    locale: str = "ru"
    tier: str = "cold"
    subjects: list[dict] = field(default_factory=list)   # [{key, score, signals, last}]
    topics: dict[str, float] = field(default_factory=dict)
    geo: dict = field(default_factory=dict)
    timezone: str | None = None
    stats: dict = field(default_factory=dict)

    def score(self, key: str) -> float:
        for s in self.subjects:
            if s["key"] == key:
                return float(s["score"])
        return 0.0

    def top_topics(self, n: int = 3) -> list[str]:
        return [t for t, _ in sorted(self.topics.items(), key=lambda kv: -kv[1])[:n]]

    def series(self) -> list[dict]:
        return [s for s in self.subjects if s["key"].split(":", 1)[0] in ("ru", "w", "r")]

    def as_row(self) -> dict:
        return {"tier": self.tier, "locale": self.locale, "timezone": self.timezone, "topics": self.topics,
                "subjects": self.subjects, "geo": self.geo, "stats": self.stats}


def decay(weight: float, half_life: float | None, age_days: float) -> float:
    if half_life is None:
        return weight
    return weight * math.pow(2.0, -max(0.0, age_days) / half_life)


def _topic_of(sub: Subject, topic_hint: dict[str, str]) -> str | None:
    if sub.kind == "t":
        return sub.code
    if sub.key in topic_hint:
        return topic_hint[sub.key]
    if sub.kind in ("ru", "r", "ri"):
        return topic_for_code(sub.code)
    return None


def build_profile(
    user_id: str,
    signals: list[Signal],
    *,
    now: datetime,
    locale: str = "ru",
    fatigue: dict[str, int] | None = None,
    topic_hint: dict[str, str] | None = None,
    geo: dict | None = None,
    timezone: str | None = None,
    stats: dict | None = None,
) -> Profile:
    """Сигналы → профиль. `fatigue` — сколько выпусков подряд предмет показан без клика."""
    topic_hint = topic_hint or {}
    fatigue = fatigue or {}
    seen: set[tuple[str, str, date]] = set()
    raw: dict[str, float] = defaultdict(float)
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    last: dict[str, datetime] = {}
    topics_raw: dict[str, float] = defaultdict(float)
    for sig in signals:
        spec = SIGNALS.get(sig.kind)
        if spec is None:
            continue
        key = sig.subject.key
        day = sig.at.date()
        dedupe = (sig.kind, key, day)
        if dedupe in seen:
            continue
        seen.add(dedupe)
        weight, half = spec
        value = decay(weight, half, (now - sig.at).total_seconds() / 86400.0)
        if sig.pre_signup:
            value *= PRE_SIGNUP_FACTOR
        topic = _topic_of(sig.subject, topic_hint)
        if topic:
            # Тема получает вклад каждого предмета: «смотрит бензин и дизель» — сильная тема «топливо».
            topics_raw[topic] += value
        if sig.subject.kind == "t":
            continue
        raw[key] += value
        counts[key][sig.kind] += 1
        if key not in last or sig.at > last[key]:
            last[key] = sig.at
    subjects = []
    for key, value in raw.items():
        n = min(int(fatigue.get(key, 0)), FATIGUE_MAX)
        value *= FATIGUE_FACTOR ** n
        subjects.append({
            "key": key, "score": round(math.log1p(value), 4),
            "signals": dict(counts[key]), "last": last[key].date().isoformat(),
        })
    subjects.sort(key=lambda s: (-s["score"], s["key"]))
    subjects = subjects[:MAX_SUBJECTS]
    topics = {t: round(math.log1p(v), 4) for t, v in sorted(topics_raw.items(), key=lambda kv: -kv[1])}
    strong = [s for s in subjects if s["score"] >= RICH_MIN_SCORE and parse_key(s["key"]) is not None
              and parse_key(s["key"]).is_series]
    if len(strong) >= RICH_MIN_SUBJECTS:
        tier = "rich"
    elif any(s["score"] >= LIGHT_MIN_SCORE for s in subjects) or any(v >= LIGHT_MIN_SCORE for v in topics.values()):
        tier = "light"
    else:
        tier = "cold"
    return Profile(user_id=user_id, locale=locale, tier=tier, subjects=subjects, topics=topics,
                   geo=geo or {}, timezone=timezone, stats=stats or {})


def explicit_region(profile_signals: list[Signal]) -> str | None:
    """Регион, который человек сам смотрел/искал/скачивал (регион по IP не используется)."""
    weight: dict[str, float] = defaultdict(float)
    for sig in profile_signals:
        if sig.subject.kind in ("reg", "r") and sig.subject.place:
            weight[sig.subject.place] += SIGNALS.get(sig.kind, (0.0, None))[0]
    if not weight:
        return None
    best, score = max(weight.items(), key=lambda kv: kv[1])
    return best if score >= 2.0 else None

"""Люди в Пульсе: человеком считается только сессия с признаком живого посетителя (18.11.2026).

Пульс за 17.11 назвал людьми семь заходов одной программы на английском хосте («7 нажатий „Регистрация“,
0 регистраций — проверить регистрацию»): одно нажатие «Sign up» в одну точку и больше ничего. До этого дня
событие сайта считалось событием человека, если у сессии не было сигнала робота.

Правило перевёрнуто (`bot_score.human_evidence`, колонка `server_sessions.is_human`): у каждой сессии одно
из состояний — `human` (есть признак: траектория указателя, прокрутка, ввод дольше одного действия, два
нажатия, вход в аккаунт), `unconfirmed` (признаков нет, но и сигнала робота нет), `bot`, `internal`
(владелец и админы), `unknown` (сессия посчитана до правила или событие не попало ни в одну сессию).

Модуль читает сессии окна один раз и раскладывает по ним события фронта и клики поведенческого потока.
Сессии посетителя разделены паузой не меньше 30 минут (`analytics_rollups.SESSION_GAP_MIN`), поэтому
событие с запасом в 5 минут от границ попадает не больше чем в одну сессию: так событие нажатия, которое
дошло, а клик поведенческого потока потерялся при переходе страницы, всё равно находит свою сессию.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select

from app.models import BehaviorEvent, FrontendEvent, ServerSession

RULE = "human-evidence-2026-11-18"
MATCH_MARGIN = timedelta(minutes=5)  # меньше половины разрыва сессий (30 мин): двух совпадений не бывает
STATUSES = ("human", "unconfirmed", "bot", "internal", "unknown")
LONG_SESSION = timedelta(days=5)


def session_status(is_bot: bool, is_internal: bool, is_human: bool | None) -> str:
    if is_internal:
        return "internal"
    if is_bot:
        return "bot"
    if is_human is None:
        return "unknown"
    return "human" if is_human else "unconfirmed"


def _key(visitor: str | None, session: str | None) -> str | None:
    """Ключ посетителя как у сессионизации: постоянный id, иначе id вкладки."""
    return (visitor or None) or (session or None)


class PeopleIndex:
    """Сессии окна по посетителям; `find(key, at)` — состояние сессии, в которую попадает момент."""

    def __init__(self, rows):
        by_visitor: dict[str, list[tuple[datetime, datetime, str, int]]] = defaultdict(list)
        for visitor, started, ended, is_bot, is_internal, is_human, sid in rows:
            status = session_status(bool(is_bot), bool(is_internal), is_human)
            by_visitor[visitor].append((started, ended or started, status, sid))
        for spans in by_visitor.values():
            spans.sort()
        self._starts = {v: [s[0] for s in spans] for v, spans in by_visitor.items()}
        self._spans = by_visitor

    def find(self, key: str | None, at: datetime | None) -> tuple[str, int | None]:
        """(состояние, id сессии) для события посетителя `key` в момент `at`."""
        if not key or at is None or key not in self._spans:
            return "unknown", None
        spans = self._spans[key]
        i = bisect_right(self._starts[key], at + MATCH_MARGIN) - 1
        if i >= 0:
            started, ended, status, sid = spans[i]
            if at <= ended + MATCH_MARGIN:
                return status, sid
        return "unknown", None


async def load_index(db, start: datetime, end: datetime) -> PeopleIndex:
    """Сессии, которые пересекают окно [start, end) с запасом. День — не больше нескольких тысяч строк."""
    rows = (await db.execute(
        select(ServerSession.visitor_id_hash, ServerSession.started_at, ServerSession.ended_at,
               ServerSession.is_bot, ServerSession.is_internal, ServerSession.is_human, ServerSession.id)
        .where(ServerSession.day >= (start - LONG_SESSION).date(),  # индекс по дню; цепочка открытой вкладки
               ServerSession.started_at < end + MATCH_MARGIN,     # длится сутками (видели 3,7 дня)
               ServerSession.ended_at >= start - MATCH_MARGIN)
    )).all()
    return PeopleIndex(rows)


async def people_snapshot(db, start: datetime, end: datetime) -> dict[str, Any]:
    """Сессии, начавшиеся в окне, по состояниям и по языку сайта; число разных людей-посетителей."""
    rows = (await db.execute(
        select(ServerSession.visitor_id_hash, ServerSession.is_bot, ServerSession.is_internal,
               ServerSession.is_human, ServerSession.site_locale)
        .where(ServerSession.day >= (start - timedelta(days=1)).date(),
               ServerSession.started_at >= start, ServerSession.started_at < end)
    )).all()
    sessions: Counter[str] = Counter({s: 0 for s in STATUSES})
    by_locale: dict[str, Counter[str]] = defaultdict(Counter)
    human_visitors: set[str] = set()
    for visitor, is_bot, is_internal, is_human, locale in rows:
        status = session_status(bool(is_bot), bool(is_internal), is_human)
        sessions[status] += 1
        by_locale[locale or "unknown"][status] += 1
        if status == "human":
            human_visitors.add(visitor)
    return {
        "rule": RULE,
        "sessions": dict(sessions),
        "human_visitors": len(human_visitors),
        "by_locale": {loc: dict(c) for loc, c in sorted(by_locale.items())},
    }


async def events_by_people(db, start: datetime, end: datetime, index: PeopleIndex,
                           names: list[str]) -> dict[str, dict[str, int]]:
    """События фронта `names` по состояниям сессий: сколько событий и сколько разных сессий-людей.

    `people` — события из подтверждённых сессий, `people_sessions` — сколько таких сессий; остальное — чьи
    события (неподтверждённые, роботы, свои, без сессии). Читаем только время, ключ и имя — по индексу имя+время.
    """
    if not names:
        return {}
    rows = (await db.execute(
        select(FrontendEvent.event_name, FrontendEvent.visitor_id_hash, FrontendEvent.session_id_hash,
               FrontendEvent.occurred_at)
        .where(FrontendEvent.occurred_at >= start, FrontendEvent.occurred_at < end,
               FrontendEvent.event_name.in_(names))
    )).all()
    out: dict[str, dict[str, Any]] = {}
    people_sessions: dict[str, set] = defaultdict(set)
    for name, visitor, session, at in rows:
        status, sid = index.find(_key(visitor, session), at)
        item = out.setdefault(name, {"people": 0, "unconfirmed": 0, "bot": 0, "internal": 0, "unknown": 0})
        item["people" if status == "human" else status] += 1
        if status == "human":
            people_sessions[name].add(sid)
    for name, item in out.items():
        item["people_sessions"] = len(people_sessions[name])
    return out


async def friction_people(db, start: datetime, end: datetime, index: PeopleIndex,
                          dead: list[dict], rage: list[dict]) -> None:
    """Дописывает в строки dead/rage `people` — сколько из `sessions` подтверждённые люди."""
    if not dead and not rage:
        return
    window = (BehaviorEvent.occurred_at >= start, BehaviorEvent.occurred_at < end,
              BehaviorEvent.event_type == "click")
    dead_paths = [row["element"] for row in dead]
    rage_keys = {(row["page"], row["element"]) for row in rage}
    rows = (await db.execute(
        select(BehaviorEvent.visitor_id_hash, BehaviorEvent.session_id_hash, BehaviorEvent.occurred_at,
               BehaviorEvent.element_path, BehaviorEvent.page, BehaviorEvent.is_dead, BehaviorEvent.is_rage)
        .where(*window, (BehaviorEvent.is_dead.is_(True)) | (BehaviorEvent.is_rage.is_(True)),
               BehaviorEvent.element_path.in_(dead_paths + [k[1] for k in rage_keys]))
    )).all()
    dead_people: dict[str, set] = defaultdict(set)
    rage_people: dict[tuple, set] = defaultdict(set)
    for visitor, session, at, path, page, is_dead, is_rage in rows:
        status, sid = index.find(_key(visitor, session), at)
        if status != "human":
            continue
        if is_dead and path in dead_paths:
            dead_people[path].add(sid)
        if is_rage and (page, path) in rage_keys:
            rage_people[(page, path)].add(sid)
    for row in dead:
        row["people"] = len(dead_people[row["element"]])
    for row in rage:
        row["people"] = len(rage_people[(row["page"], row["element"])])


def digits_line(people: dict | None) -> str | None:
    """Строка сырых цифр Пульса; None — у снимка нет раздела (собран до 18.11.2026)."""
    if not isinstance(people, dict) or not isinstance(people.get("sessions"), dict):
        return None
    s = people["sessions"]
    line = (f"Люди (есть признак живого посетителя): сессий {s.get('human', 0)}, разных посетителей "
            f"{people.get('human_visitors', 0)}; не подтверждено {s.get('unconfirmed', 0)}, роботов {s.get('bot', 0)}")
    if s.get("unknown"):
        line += f", без оценки {s['unknown']}"
    return line


def memory_core(people: dict | None) -> dict[str, int]:
    if not isinstance(people, dict) or not isinstance(people.get("sessions"), dict):
        return {}
    s = people["sessions"]
    return {"people_sessions": int(s.get("human", 0)), "unconfirmed_sessions": int(s.get("unconfirmed", 0)),
            "people_visitors": int(people.get("human_visitors", 0))}


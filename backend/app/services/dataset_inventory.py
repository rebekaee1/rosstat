"""Инвентаризация DS-датасета: сколько и чего мы накопили (2026-07-03).

Стратегия владельца: хранилище должно быть проверяемым — видно, что собрано
«столько-то строк, столько-то параметров, главные такие-то». Эта функция —
единственная точка истины про объём датасета; её показывают кнопка бота
«Датасет» и ежедневный дайджест, а Пульс-LLM получает её в снапшоте.

Слои датасета (каждый — отдельная секция отчёта):
- behavior_events    — сырой поведенческий поток сайта (клики/мышь/скролл);
- frontend_events    — бизнес-события фронта (просмотры, поиск, скачивания);
- raw_metrika_visits — повизитная выгрузка Метрики (фразы/источники/гео/UTM);
- metrika_search_phrases / metrika_daily_page_metrics / metrika_report_snapshots
                     — дневные агрегаты привлечения;
- webmaster_search_queries — запросы из поиска Яндекса (показы/клики/позиция);
- hypotheses         — булев слой знаний (подтверждено/опровергнуто/открыто);
- users / indicator_data / region_data — продуктовое ядро.

«Параметры» считаем честно: колонки таблицы + фактические ключи params_json /
raw_json (по свежей выборке строк) + кардинальности типов событий. Никаких
выдуманных чисел — всё из БД.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    BehaviorEvent,
    FrontendEvent,
    Hypothesis,
    IndicatorData,
    MetrikaDailyPageMetric,
    MetrikaReportSnapshot,
    MetrikaSearchPhrase,
    RawMetrikaVisit,
    RegionDataPoint,
    User,
    WebmasterSearchQuery,
)

# Выборка последних строк для подсчёта фактических JSON-ключей: достаточно,
# чтобы увидеть весь словарь параметров, и дёшево для ежедневного вызова.
_JSON_SAMPLE_ROWS = 2000


def _table_columns(model) -> int:
    return len(model.__table__.columns)


async def _json_keys(db: AsyncSession, model, json_col, order_col) -> set[str]:
    rows = (await db.execute(
        select(json_col).order_by(order_col.desc()).limit(_JSON_SAMPLE_ROWS)
    )).scalars().all()
    keys: set[str] = set()
    for payload in rows:
        if isinstance(payload, dict):
            keys.update(payload.keys())
    return keys


async def _time_range(db: AsyncSession, col) -> tuple[str | None, str | None]:
    row = (await db.execute(select(func.min(col), func.max(col)))).one()
    def _fmt(v: Any) -> str | None:
        if v is None:
            return None
        return v.isoformat() if isinstance(v, datetime) else str(v)
    return _fmt(row[0]), _fmt(row[1])


async def build_inventory(db: AsyncSession) -> dict[str, Any]:
    """Полная инвентаризация датасета. Возвращает JSON-совместимый dict."""
    inv: dict[str, Any] = {"generated_at": datetime.utcnow().isoformat(timespec="seconds")}
    sections: dict[str, dict[str, Any]] = {}

    # --- Поведенческий поток -------------------------------------------------
    b_total = await db.scalar(select(func.count(BehaviorEvent.id))) or 0
    b_by_type = dict((await db.execute(
        select(BehaviorEvent.event_type, func.count()).group_by(BehaviorEvent.event_type)
    )).all())
    b_keys = await _json_keys(db, BehaviorEvent, BehaviorEvent.params_json, BehaviorEvent.id)
    b_from, b_to = await _time_range(db, BehaviorEvent.occurred_at)
    sections["behavior_events"] = {
        "rows": b_total, "by_type": b_by_type,
        "columns": _table_columns(BehaviorEvent), "json_keys": sorted(b_keys),
        "from": b_from, "to": b_to,
    }

    # --- Бизнес-события фронта ----------------------------------------------
    f_total = await db.scalar(select(func.count(FrontendEvent.id))) or 0
    f_names = await db.scalar(select(func.count(func.distinct(FrontendEvent.event_name)))) or 0
    f_keys = await _json_keys(db, FrontendEvent, FrontendEvent.params_json, FrontendEvent.id)
    f_from, f_to = await _time_range(db, FrontendEvent.occurred_at)
    sections["frontend_events"] = {
        "rows": f_total, "event_names": f_names,
        "columns": _table_columns(FrontendEvent), "json_keys": sorted(f_keys),
        "from": f_from, "to": f_to,
    }

    # --- Повизитная Метрика (Logs API) ----------------------------------------
    v_total = await db.scalar(select(func.count(RawMetrikaVisit.id))) or 0
    v_keys = await _json_keys(db, RawMetrikaVisit, RawMetrikaVisit.raw_json, RawMetrikaVisit.id)
    v_from, v_to = await _time_range(db, RawMetrikaVisit.visit_date)
    sections["raw_metrika_visits"] = {
        "rows": v_total, "columns": _table_columns(RawMetrikaVisit),
        "json_keys": sorted(v_keys), "from": v_from, "to": v_to,
    }

    # --- Агрегаты привлечения --------------------------------------------------
    sections["metrika_search_phrases"] = {
        "rows": await db.scalar(select(func.count(MetrikaSearchPhrase.id))) or 0,
        "columns": _table_columns(MetrikaSearchPhrase),
        "distinct_phrases": await db.scalar(
            select(func.count(func.distinct(MetrikaSearchPhrase.phrase)))) or 0,
    }
    sections["metrika_daily_page_metrics"] = {
        "rows": await db.scalar(select(func.count(MetrikaDailyPageMetric.id))) or 0,
        "columns": _table_columns(MetrikaDailyPageMetric),
    }
    sections["metrika_report_snapshots"] = {
        "rows": await db.scalar(select(func.count(MetrikaReportSnapshot.id))) or 0,
        "report_types": dict((await db.execute(
            select(MetrikaReportSnapshot.report_type, func.count())
            .group_by(MetrikaReportSnapshot.report_type)
        )).all()),
    }
    sections["webmaster_search_queries"] = {
        "rows": await db.scalar(select(func.count(WebmasterSearchQuery.id))) or 0,
        "columns": _table_columns(WebmasterSearchQuery),
    }

    # --- Булев слой знаний -----------------------------------------------------
    h_by_verdict = {"open": 0, "true": 0, "false": 0}
    for verdict, n in (await db.execute(
        select(Hypothesis.verdict, func.count()).group_by(Hypothesis.verdict)
    )).all():
        key = "open" if verdict is None else ("true" if verdict else "false")
        h_by_verdict[key] = n
    sections["hypotheses"] = {
        "rows": sum(h_by_verdict.values()), "by_verdict": h_by_verdict,
    }

    # --- Продуктовое ядро --------------------------------------------------------
    sections["core"] = {
        "users": await db.scalar(select(func.count(User.id))) or 0,
        "indicator_points": await db.scalar(select(func.count(IndicatorData.id))) or 0,
        "region_points": await db.scalar(select(func.count(RegionDataPoint.id))) or 0,
    }

    inv["sections"] = sections
    inv["totals"] = {
        "rows": sum(
            s.get("rows", 0) for s in sections.values() if isinstance(s.get("rows"), int)
        ) + sections["core"]["indicator_points"] + sections["core"]["region_points"],
        # «Параметры» = колонки таблиц + фактические JSON-ключи + типы событий.
        "parameters": (
            sum(s.get("columns", 0) for s in sections.values())
            + sum(len(s.get("json_keys", [])) for s in sections.values())
            + len(b_by_type) + f_names
        ),
    }
    return inv


def _n(value: int) -> str:
    """1234567 → «1 234 567» (тонкая типографика для Telegram)."""
    return f"{value:,}".replace(",", " ")


def format_inventory_html(inv: dict[str, Any]) -> str:
    """Инвентаризация → Telegram HTML (кнопка «Датасет» и дайджест)."""
    s = inv["sections"]
    t = inv["totals"]
    b, f, v = s["behavior_events"], s["frontend_events"], s["raw_metrika_visits"]
    ph, hy, core = s["metrika_search_phrases"], s["hypotheses"], s["core"]
    by_type = ", ".join(f"{k} {_n(n)}" for k, n in sorted(b["by_type"].items()))
    lines = [
        f"📦 <b>Датасет: строк {_n(t['rows'])}, параметров {_n(t['parameters'])}</b>",
        f"🎥 Поведение: событий {_n(b['rows'])} ({by_type})",
        f"⚡ Бизнес-события: строк {_n(f['rows'])}, типов {f['event_names']}",
        f"🧲 Визиты Метрики: строк {_n(v['rows'])}, полей {len(v['json_keys'])}",
        f"🔍 Поисковые фразы: строк {_n(ph['rows'])}, уникальных {_n(ph['distinct_phrases'])}",
        f"🧠 Гипотезы: открытых {hy['by_verdict']['open']}, "
        f"подтверждено {hy['by_verdict']['true']}, опровергнуто {hy['by_verdict']['false']}",
        f"🏛 Ядро: пользователей {_n(core['users'])}, точек макро {_n(core['indicator_points'])}, "
        f"точек регионов {_n(core['region_points'])}",
    ]
    if b["from"]:
        lines.insert(1, f"Окно поведения: {b['from'][:10]} → {(b['to'] or '')[:10]}, копим без удаления")
    return "\n".join(lines)

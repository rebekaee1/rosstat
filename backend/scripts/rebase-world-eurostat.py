#!/usr/bin/env python3
"""Перевод индексных наборов Евростата на живую базу (круг 12): план и постановка в очередь.

Евростат с 2024 ведёт индексы короткосрочной статистики (`sts_*`) на базе 2021=100 (I21),
наши срезы остались на 2015=100 (I15) и стоят на декабре 2023. Загрузчик теперь сам
находит живую базу и переносит карточки на месте (`app/services/eurostat_rebase.py`), но
по расписанию он берёт набор только когда меняется дата в оглавлении Евростата, а
квартальные и годовые наборы обновляются редко. Этот скрипт находит наборы, чей срез
стоит на остановленной базе, и ставит их в очередь ближайшего прогона (02:20 и 14:20 МСК).

    сухой прогон (по умолчанию): таблица «набор · карточек · публичных · данные до · база»;
    --apply: у найденных наборов `world_dataset_state` → status=pending, last_update_of_data=NULL
             (идемпотентно; сам набор загрузит обычная задача `world_eurostat_ingest` с
             журналом и сообщением в Telegram, не больше 200 наборов и 3 часов за прогон).

    docker compose exec backend python /app/scripts/rebase-world-eurostat.py
    docker compose exec backend python /app/scripts/rebase-world-eurostat.py --apply
    ... --only sts_trtu_m --only sts_trtu_q      # ограничить наборами

Ограничители: проверяются только наборы, у которых лучшая публичная дата старше
``--stale-days`` (120 по умолчанию), по одному лёгкому запросу структуры в 0,6 с;
не больше ``--max-probes`` (150) запросов. Боевые окна ETL 05:30–07:30 и 19:30–22:30 МСК
скрипт не занимает: он только читает базу и один запрос на набор к Евростату.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from datetime import date, timedelta

import requests
from sqlalchemy import select

sys.path.insert(0, "/app")

from app.database import async_session  # noqa: E402
from app.models import WorldDatasetState, WorldIndicator  # noqa: E402
from app.services.eurostat_parser import (  # noqa: E402
    _structure_and_live,
    build_data_url,
    extract_dimensions,
    index_base_year,
    replace_dead_index_unit,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("rebase-world-eurostat")
PROBE_TIMEOUT_S = 25
PROBE_PERIODS = 3                   # три последних периода: у страны последний месяц набора бывает ещё пуст
PROBE_ATTEMPTS = 3                  # холодный запрос у Евростата бывает долгим: короткий таймаут и повтор вместо одной минуты ожидания
# Страны для пробы: сначала крупные, затем остальные — у части наборов (`sts_rb_*`, `sts_sepr_m`) в последнем периоде
# наблюдений у Германии, Франции и Италии ещё нет (круг 13: «проба не удалась: None»), а у других стран есть.
PROBE_GEOS = (
    "DE", "FR", "IT", "ES", "NL", "PL", "AT", "BE", "SE", "CZ", "RO", "HU", "PT", "BG", "DK", "FI", "IE", "SK",
    "SI", "HR", "LT", "LV", "EE", "EL", "LU", "MT", "CY", "NO", "CH",
)


def live_units_at_latest_period(payload: dict) -> set[str]:
    """Члены unit с наблюдением в **последнем периоде, где у этой страны вообще есть данные**.

    Окно из нескольких периодов нужно, чтобы не промахнуться мимо пустого последнего месяца, но «живой» считается
    только база, у которой есть данные в самом свежем периоде окна: у годового набора мёртвая I15 кончилась в 2023,
    а окно из трёх лет это 2023–2025, и по всему окну она выглядела бы живой.
    """
    ids, sizes = list(payload.get("id") or []), [int(x) for x in payload.get("size") or []]
    if "unit" not in ids or "time" not in ids or len(ids) != len(sizes):
        return set()
    members = extract_dimensions(payload).get("unit") or []
    value = payload.get("value")
    if isinstance(value, dict):
        keys = [int(k) for k, v in value.items() if v is not None]
    elif isinstance(value, list):
        keys = [i for i, v in enumerate(value) if v is not None]
    else:
        return set()
    if not keys or not members:
        return set()

    def stride(dim: str) -> tuple[int, int]:
        pos = ids.index(dim)
        step = 1
        for size in sizes[pos + 1:]:
            step *= size
        return step, sizes[pos]

    t_step, t_size = stride("time")
    u_step, u_size = stride("unit")
    latest = max((k // t_step) % t_size for k in keys)
    return {
        members[(k // u_step) % u_size] for k in keys
        if (k // t_step) % t_size == latest and (k // u_step) % u_size < len(members)
    }


def probe_units(dataset_id: str) -> tuple[list[str], set[str]]:
    """Члены unit и живые из них (есть наблюдение в последнем периоде набора).

    Лёгкая проба по одной стране (полный ответ по всем странам у больших наборов
    не укладывается в таймаут): первая страна из списка, у которой есть данные.
    """
    last_error: Exception | None = None
    answered = False
    for geo in PROBE_GEOS:
        url = build_data_url(dataset_id, {"geo": geo}, last_time_period=PROBE_PERIODS, pin_geo=True)
        for _attempt in range(PROBE_ATTEMPTS):   # холодный запрос у Евростата бывает долгим, повтор быстрый
            try:
                resp = requests.get(url, timeout=PROBE_TIMEOUT_S)
                resp.raise_for_status()
                payload = resp.json()
                dims, _live_all = _structure_and_live(payload)
                live = {"unit": live_units_at_latest_period(payload)} if dims.get("unit") else {}
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                continue
            answered = True
            if live.get("unit"):
                return dims.get("unit") or [], live["unit"]
            break                           # ответ получен, но живых единиц нет: следующая страна
        if not answered and geo == PROBE_GEOS[2]:
            break                           # три страны подряд без единого ответа: источник недоступен, остальных не ждать
    if answered:
        raise RuntimeError("в последнем периоде набора нет наблюдений ни у одной проверенной страны")
    raise RuntimeError(f"проба не удалась: {last_error}")


async def collect(only: set[str], stale_days: int) -> list[dict]:
    """Наборы с индексными карточками, отставшими от остальных данных."""
    cutoff = date.today() - timedelta(days=stale_days)
    async with async_session() as db:
        rows = (await db.execute(
            select(
                WorldIndicator.dataset_id, WorldIndicator.slice_json, WorldIndicator.is_listed,
                WorldIndicator.history_end,
            ).where(WorldIndicator.provider == "eurostat")
        )).all()
    by_ds: dict[str, dict] = {}
    for dataset_id, slice_json, listed, history_end in rows:
        unit = str((slice_json or {}).get("unit") or "")
        if index_base_year(unit) is None:
            continue
        if only and dataset_id not in only:
            continue
        item = by_ds.setdefault(dataset_id, {
            "dataset_id": dataset_id, "cards": 0, "listed": 0, "units": set(), "best_end": None,
        })
        item["cards"] += 1
        item["listed"] += 1 if listed else 0
        item["units"].add(unit)
        if history_end and (item["best_end"] is None or history_end > item["best_end"]):
            item["best_end"] = history_end
    out = [i for i in by_ds.values() if i["best_end"] is None or i["best_end"] < cutoff]
    out.sort(key=lambda i: (-i["listed"], i["dataset_id"]))
    return out


async def run(apply: bool, only: set[str], stale_days: int, max_probes: int) -> int:
    candidates = await collect(only, stale_days)
    log.info("наборов с индексом и отставшими данными: %d", len(candidates))
    plan: list[dict] = []
    probes = 0
    for item in candidates:
        if probes >= max_probes:
            log.warning("достигнут предел проб %d, остальное при следующем запуске", max_probes)
            break
        probes += 1
        try:
            members, live_units = await asyncio.to_thread(probe_units, item["dataset_id"])
        except Exception as exc:  # noqa: BLE001
            log.warning("%s: структура не получена (%s)", item["dataset_id"], exc)
            continue
        finally:
            await asyncio.sleep(0.6)
        moves = {
            unit: replace_dead_index_unit(unit, members, live_units)
            for unit in item["units"]
        }
        moves = {a: b for a, b in moves.items() if b and b != a}
        if not moves:
            log.info("%s: живая база уже совпадает со срезом, не трогаем", item["dataset_id"])
            continue
        plan.append({**item, "moves": moves})

    print("| набор | карточек | публичных | данные до | база |")
    print("|---|---:|---:|---|---|")
    for p in plan:
        move = ", ".join(f"{a}→{b}" for a, b in sorted(p["moves"].items()))
        print(f"| {p['dataset_id']} | {p['cards']} | {p['listed']} | {p['best_end']} | {move} |")
    print(f"\nитого: наборов {len(plan)}, карточек {sum(p['cards'] for p in plan)}, "
          f"публичных {sum(p['listed'] for p in plan)}")
    if not apply:
        log.info("сухой прогон: ничего не записано (--apply поставит наборы в очередь)")
        return len(plan)

    from app.config import settings

    if not settings.eurostat_rebase_enabled:
        log.error("RUSTATS_EUROSTAT_REBASE_ENABLED выключен: набор в очереди загрузился бы по "
                  "прежнему срезу I15. Включите флаг в .env, перезапустите scheduler и повторите.")
        return len(plan)
    queued = 0
    async with async_session() as db:
        for p in plan:
            state = await db.get(WorldDatasetState, ("eurostat", p["dataset_id"]))
            if state is None:
                state = WorldDatasetState(provider="eurostat", dataset_id=p["dataset_id"])
                db.add(state)
            if state.status == "pending" and state.last_update_of_data is None:
                continue
            state.status = "pending"
            state.last_update_of_data = None
            state.last_error = None
            queued += 1
        await db.commit()
    log.info("поставлено в очередь ближайшего прогона: %d из %d", queued, len(plan))
    return len(plan)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="поставить найденные наборы в очередь")
    ap.add_argument("--only", action="append", default=[], help="только этот набор (можно несколько раз)")
    ap.add_argument("--stale-days", type=int, default=120)
    ap.add_argument("--max-probes", type=int, default=150)
    args = ap.parse_args()
    t0 = time.time()
    asyncio.run(run(args.apply, set(args.only), args.stale_days, args.max_probes))
    log.info("готово за %.0f с", time.time() - t0)

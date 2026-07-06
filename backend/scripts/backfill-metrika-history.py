"""Бэкфилл всей доступной истории Яндекс.Метрики в накопительное хранилище.

Ежедневный `acquisition_daily_job` собирает только «вчера» — исторические дни
(счётчик работает с весны 2026) в raw_metrika_visits/фразах/страницах
отсутствовали. Скрипт закрывает дыру за один прогон:

1. **Повизитные данные (Logs API)** — ОДИН logrequest на весь диапазон
   (create → poll → download TSV → upsert → clean): для истории это на два
   порядка дешевле, чем суточный запрос на каждый день. Парсинг и upsert —
   реюз `metrika_acquisition` (те же `_VISIT_FIELDS`/`_upsert_visit`),
   поэтому строки байт-в-байт совместимы с ежедневным синком.
2. **Дневные агрегаты (Reporting API)** — `sync_acquisition_reports_for_day`
   за каждый день диапазона: снапшоты источников/поисковиков/рефереров/
   кампаний + metrika_search_phrases + metrika_daily_page_metrics.

Идемпотентно (upsert по (counter_id, visit_id) / (day, …)) — можно
перезапускать с любого места; прогресс печатается по дням, при обрыве
перезапустить с последнего напечатанного дня.

Запуск (диапазон включительно; date_to не может быть сегодняшним днём —
Logs API отдаёт только завершённые дни):

    docker compose exec -T backend python scripts/backfill-metrika-history.py \
        2026-03-05 2026-07-05 [visits|reports|all]
"""
from __future__ import annotations

import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

# При запуске через stdin (docker compose exec -T backend python - < script)
# __file__ отсутствует — cwd контейнера уже /app, импорты работают и так.
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
except NameError:
    pass

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.database import async_session  # noqa: E402
from app.services.analytics_ingestion import finish_sync_run, start_sync_run  # noqa: E402
from app.services.metrika_acquisition import (  # noqa: E402
    _VISIT_FIELDS,
    _primary_counter_id,
    _upsert_visit,
    parse_visits_tsv,
    sync_acquisition_reports_for_day,
)
from app.services.yandex_client import YandexApiError  # noqa: E402
from app.services.yandex_metrika_logs import MetrikaLogsClient  # noqa: E402

_POLL_SECONDS = 15
_POLL_MAX = 240  # до часа ожидания подготовки широкой выгрузки

# VARCHAR-лимиты колонок raw_metrika_visits: рекламные URL Яндекса с
# etext-токеном бывают >1000 символов — без клипа падает вся выгрузка
# (StringDataRightTruncation). Канонический фикс — _clip в metrika_acquisition;
# обёртка ниже нужна, пока работающий контейнер несёт версию без клипа.
_CLIP_LIMITS = {
    "ym:s:startURL": 1000,
    "ym:s:referer": 1000,
    "ym:s:lastTrafficSource": 100,
    "ym:s:lastSearchEngine": 100,
    "ym:s:lastSearchEngineRoot": 100,
    "ym:s:lastSearchPhrase": 500,
}


class _ClippingRow(dict):
    """Строка Logs API, чей .get отдаёт значения, обрезанные под лимиты
    колонок; dict(row) / raw_json / row_hash сохраняют полные значения."""

    def get(self, key, default=None):  # noqa: ANN001
        value = super().get(key, default)
        limit = _CLIP_LIMITS.get(key)
        if limit and isinstance(value, str) and len(value) > limit:
            return value[:limit]
        return value


async def backfill_visits_range(db: AsyncSession, date_from: date, date_to: date,
                                counter_id: str | None = None) -> int:
    """Повизитная выгрузка Logs API за диапазон одним logrequest'ом."""
    counter_id = counter_id or _primary_counter_id()
    client = MetrikaLogsClient()
    fields = list(_VISIT_FIELDS)
    run = await start_sync_run(
        db, source="yandex_metrika_logs", job_type="visits_log_backfill",
        date_from=date_from, date_to=date_to, metadata={"counter_id": counter_id},
    )
    await db.commit()
    try:
        # lastSearchPhrase доступна не на всех счётчиках — пробуем с ней.
        try:
            created = await client.create_request(
                counter_id, source="visits", fields=fields + ["ym:s:lastSearchPhrase"],
                date_from=date_from, date_to=date_to,
            )
        except YandexApiError as exc:
            print(f"lastSearchPhrase отклонена ({exc}), повтор без неё", flush=True)
            created = await client.create_request(
                counter_id, source="visits", fields=fields,
                date_from=date_from, date_to=date_to,
            )
        request_id = str(created.data["log_request"]["request_id"])
        print(f"logrequest {request_id} создан за {date_from}..{date_to}", flush=True)

        parts: list[int] = []
        for attempt in range(_POLL_MAX):
            info = await client.request_info(counter_id, request_id)
            status = info.data["log_request"]["status"]
            if status == "processed":
                parts = [p["part_number"] for p in info.data["log_request"].get("parts", [])]
                break
            if status in ("processing_failed", "canceled", "cleaned_by_user"):
                raise RuntimeError(f"logrequest {request_id} failed: {status}")
            if attempt % 4 == 0:
                print(f"  poll #{attempt}: {status}", flush=True)
            await asyncio.sleep(_POLL_SECONDS)
        else:
            raise RuntimeError(f"logrequest {request_id} not processed in time")

        processed = 0
        for part in parts:
            payload = await client.download_part(counter_id, request_id, part)
            tsv = payload.data if isinstance(payload.data, str) else str(payload.data)
            for row in parse_visits_tsv(tsv):
                await _upsert_visit(db, counter_id, _ClippingRow(row))
                processed += 1
            await db.flush()
            print(f"  part {part}: суммарно {processed} строк", flush=True)

        try:
            await client.clean_request(counter_id, request_id)
        except YandexApiError:
            print("clean_request не прошёл (не фатально)", flush=True)

        await finish_sync_run(db, run, records_processed=processed)
        await db.commit()
        return processed
    except Exception as exc:
        await db.rollback()
        await finish_sync_run(db, run, status="failed", error_message=str(exc)[:500])
        await db.commit()
        raise


async def main() -> None:
    date_from = date.fromisoformat(sys.argv[1])
    date_to = date.fromisoformat(sys.argv[2])
    mode = sys.argv[3] if len(sys.argv) > 3 else "all"
    if date_to >= date.today():
        raise SystemExit("date_to должен быть завершённым днём (вчера или раньше)")

    if mode in ("visits", "all"):
        async with async_session() as db:
            n = await backfill_visits_range(db, date_from, date_to)
        print(f"VISITS {date_from}..{date_to}: {n} строк", flush=True)

    if mode in ("reports", "all"):
        day = date_from
        while day <= date_to:
            # Reporting API отвечает 429 при исчерпании квоты (6 запросов на
            # день × ~30 дней хватает, чтобы упереться) — ждём и повторяем
            # тот же день, upsert идемпотентен.
            for attempt in range(8):
                try:
                    async with async_session() as db:
                        n = await sync_acquisition_reports_for_day(db, day)
                    break
                except YandexApiError as exc:
                    if exc.status_code != 429:
                        raise
                    wait = min(60 * (attempt + 1), 300)
                    print(f"REPORTS {day}: 429, жду {wait}с (попытка {attempt + 1})", flush=True)
                    await asyncio.sleep(wait)
            else:
                raise RuntimeError(f"REPORTS {day}: квота 429 не отпустила за 8 попыток")
            print(f"REPORTS {day}: {n} строк", flush=True)
            await asyncio.sleep(2)  # щадим квоту Reporting API
            day += timedelta(days=1)

    print("DONE", flush=True)


if __name__ == "__main__":
    asyncio.run(main())

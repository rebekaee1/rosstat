"""Слой привлечения: повизитные данные Метрики → накопительное хранилище.

Стратегия владельца (2026-07-03): собирать про каждый визит то же, что видно
в интерфейсе Метрики (Вебвизор-список) — поисковую фразу, откуда пришёл
(поисковик / сайт / реклама / прямой заход), UTM-метки, гео, устройство,
длительность, глубину, достигнутые цели. Фразы — карта того, что добавлять
на сайт; источники — куда бьёт реклама и где растёт органика.

Два контура:

1. **Logs API** (`sync_visits_for_day`) — повизитная выгрузка за день в
   `raw_metrika_visits`. Это сырьё для data science: одна строка = один визит
   со всеми полями (`_VISIT_FIELDS`). Идемпотентно по (counter_id, visit_id).
   Пайплайн Logs API: create logrequest → poll до processed → download
   TSV-части → parse → upsert → clean (чистим слот на стороне Яндекса,
   данные уже у нас).

2. **Reporting API** (`sync_acquisition_reports_for_day`) — дневные агрегаты:
   - разрез по источникам трафика (`traffic_sources` snapshot);
   - разрез по поисковикам (`search_engines` snapshot);
   - переходы с сайтов (`referrers` snapshot);
   - поисковые фразы → структурная таблица `metrika_search_phrases`;
   - постраничные метрики дня → `metrika_daily_page_metrics`
     (реюз `analytics_backfill.backfill_metrika_daily_pages`).

Снапшоты — в `metrika_report_snapshots` (JSON, идемпотентно по query_hash);
их читает «Пульс» (`pulse.build_acquisition`) для LLM-отчёта владельцу.

Retention: НЕ удаляем ничего — накопительное хранилище под Big Data/ML
(см. ADR-0009 «Subsequent additions»). Один день ≈ сотни визитов ≈ килобайты.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import RawMetrikaVisit
from app.services.analytics_backfill import (
    backfill_metrika_daily_pages,
    backfill_metrika_search_phrases,
)
from app.services.analytics_ingestion import (
    finish_sync_run,
    start_sync_run,
    store_metrika_report_snapshot,
    utcnow_naive,
)
from app.services.yandex_client import YandexApiError, stable_hash
from app.services.yandex_metrika_logs import MetrikaLogsClient
from app.services.yandex_metrika_reporting import MetrikaReportingClient

logger = logging.getLogger(__name__)

# Поля повизитной выгрузки Logs API (source=visits). Порядок важен только
# для читаемости — parse идёт по header'у TSV. Держим один источник истины:
# добавление поля здесь автоматически попадает и в запрос, и в raw_json.
_VISIT_FIELDS: list[str] = [
    "ym:s:visitID",
    "ym:s:clientID",
    "ym:s:date",
    "ym:s:dateTime",
    "ym:s:isNewUser",
    "ym:s:startURL",
    "ym:s:endURL",
    "ym:s:pageViews",
    "ym:s:visitDuration",
    "ym:s:bounce",
    "ym:s:referer",
    "ym:s:lastTrafficSource",
    "ym:s:lastSearchEngineRoot",
    "ym:s:lastSearchEngine",
    "ym:s:lastAdvEngine",
    "ym:s:lastReferalSource",
    "ym:s:UTMSource",
    "ym:s:UTMMedium",
    "ym:s:UTMCampaign",
    "ym:s:UTMContent",
    "ym:s:UTMTerm",
    "ym:s:regionCountry",
    "ym:s:regionCity",
    "ym:s:deviceCategory",
    "ym:s:operatingSystemRoot",
    "ym:s:browser",
    "ym:s:mobilePhoneModel",
    "ym:s:goalsID",
]

# Поля, доступные не на всех тарифах/счётчиках — Яндекс отвечает 400 на весь
# запрос, если хотя бы одно недоступно. Пробуем "жадно", при отказе снимаем их
# по одному с хвоста (см. _create_request_with_optional_fields).
_OPTIONAL_FIELDS: list[str] = [
    "ym:s:lastSearchPhrase",
    # isRobot — роботы по строгим правилам и по поведению (Logs API).
    # Снимаем с хвоста при 400: сначала Pro-only, потом общее поле.
    "ym:s:isRobot",
    # isRobotPro — доля роботности по антифрод-данным Директа; только Метрика
    # Pro и только с 2025-04-19 (Н-24, аудит правдивости BI 2026-07-08). Летит
    # в raw_json как есть; helper — analytics_marts.py::visit_is_robot.
    "ym:s:isRobotPro",
]

_POLL_INTERVAL_SECONDS = 15
_POLL_MAX_ATTEMPTS = 40  # ~10 минут — за глаза для суточной выгрузки


def _primary_counter_id() -> str:
    return settings.analytics_allowed_counter_ids.split(",")[0].strip()


def parse_visits_tsv(tsv: str) -> list[dict[str, str]]:
    """TSV Logs API → список dict {field: value}. Header — имена полей."""
    lines = [ln for ln in tsv.split("\n") if ln.strip()]
    if not lines:
        return []
    header = lines[0].split("\t")
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        values = line.split("\t")
        if len(values) != len(header):
            continue  # битая строка — не роняем всю выгрузку
        rows.append(dict(zip(header, values)))
    return rows


async def _create_visits_request(
    client: MetrikaLogsClient, counter_id: str, day: date,
) -> tuple[Any, list[str]]:
    """Создать logrequest, прогрессивно снимая недоступные опциональные поля.

    Разные счётчики/тарифы дают разный набор прав (Pro-only isRobotPro,
    lastSearchPhrase зависит от настроек) — Яндекс на HTTP 400 не говорит,
    какое именно поле виновато, поэтому снимаем с хвоста по одному вместо
    одного жёстко закодированного фолбэка."""
    optional = list(_OPTIONAL_FIELDS)
    while True:
        fields = list(_VISIT_FIELDS) + optional
        try:
            created = await client.create_request(
                counter_id, source="visits", fields=fields,
                date_from=day, date_to=day,
            )
            return created, fields
        except YandexApiError as exc:
            if not optional:
                raise
            dropped = optional.pop()
            logger.info("Logs API rejected field %s (%s), retrying without it", dropped, exc)


def _visit_int(row: dict[str, str], field: str) -> int | None:
    raw = (row.get(field) or "").strip()
    try:
        return int(float(raw)) if raw else None
    except ValueError:
        return None


def _clip(value: str | None, limit: int) -> str | None:
    """Обрезка под VARCHAR-лимит колонки. Рекламные URL Яндекса с etext-токеном
    бывают длиннее 1000 символов — без клипа падает вся суточная выгрузка
    (StringDataRightTruncation). Полное значение остаётся в raw_json."""
    if not value:
        return None
    return value[:limit]


async def _upsert_visit(db: AsyncSession, counter_id: str, row: dict[str, str]) -> bool:
    """Одна строка Logs API → raw_metrika_visits. True = новая строка."""
    visit_id = (row.get("ym:s:visitID") or "").strip()
    if not visit_id:
        return False
    existing = (await db.execute(
        select(RawMetrikaVisit).where(
            RawMetrikaVisit.counter_id == counter_id,
            RawMetrikaVisit.visit_id == visit_id,
        )
    )).scalar_one_or_none()
    is_new = existing is None
    item = existing or RawMetrikaVisit(counter_id=counter_id, visit_id=visit_id)

    raw_date = (row.get("ym:s:date") or "").strip()
    item.visit_date = date.fromisoformat(raw_date) if raw_date else None
    raw_dt = (row.get("ym:s:dateTime") or "").strip()
    if raw_dt:
        try:
            item.start_time = datetime.fromisoformat(raw_dt)
        except ValueError:
            item.start_time = None
    item.client_id_hash = stable_hash(row.get("ym:s:clientID") or "")[:80]
    item.start_url = _clip(row.get("ym:s:startURL"), 1000)
    item.referer = _clip(row.get("ym:s:referer"), 1000)
    item.traffic_source = _clip(row.get("ym:s:lastTrafficSource"), 100)
    item.search_engine = _clip(row.get("ym:s:lastSearchEngine")
                               or row.get("ym:s:lastSearchEngineRoot"), 100)
    item.search_phrase = _clip(row.get("ym:s:lastSearchPhrase"), 500)
    item.duration_seconds = _visit_int(row, "ym:s:visitDuration")
    goals_raw = (row.get("ym:s:goalsID") or "").strip()
    item.goals_json = {"goals": goals_raw} if goals_raw and goals_raw not in ("[]", "") else None
    item.raw_json = dict(row)
    item.row_hash = stable_hash(row)
    item.ingested_at = utcnow_naive()
    db.add(item)
    return is_new


async def sync_visits_for_day(db: AsyncSession, day: date, counter_id: str | None = None) -> int:
    """Повизитная выгрузка Logs API за день → raw_metrika_visits.

    Возвращает число обработанных строк. Идемпотентно: повторный прогон дня
    обновляет существующие визиты по (counter_id, visit_id).
    """
    counter_id = counter_id or _primary_counter_id()
    client = MetrikaLogsClient()

    run = await start_sync_run(
        db, source="yandex_metrika_logs", job_type="daily_visits_log",
        date_from=day, date_to=day, metadata={"counter_id": counter_id},
    )
    await db.commit()
    try:
        created, _fields_used = await _create_visits_request(client, counter_id, day)
        request_id = str(created.data["log_request"]["request_id"])

        parts: list[int] = []
        for _ in range(_POLL_MAX_ATTEMPTS):
            info = await client.request_info(counter_id, request_id)
            status = info.data["log_request"]["status"]
            if status == "processed":
                parts = [p["part_number"] for p in info.data["log_request"].get("parts", [])]
                break
            if status in ("processing_failed", "canceled", "cleaned_by_user"):
                raise RuntimeError(f"Logs API request {request_id} failed: {status}")
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)
        else:
            raise RuntimeError(f"Logs API request {request_id} not processed in time")

        processed = 0
        for part in parts:
            payload = await client.download_part(counter_id, request_id, part)
            tsv = payload.data if isinstance(payload.data, str) else str(payload.data)
            for row in parse_visits_tsv(tsv):
                await _upsert_visit(db, counter_id, row)
                processed += 1
        await db.flush()

        # Слот выгрузки на стороне Яндекса чистим — данные уже в нашей БД.
        try:
            await client.clean_request(counter_id, request_id)
        except YandexApiError:
            logger.warning("Logs API clean_request failed (non-fatal)", exc_info=True)

        await finish_sync_run(db, run, records_processed=processed)
        await db.commit()
        logger.info("Metrika visits log for %s: %s rows", day, processed)
        return processed
    except Exception as exc:
        await db.rollback()
        await finish_sync_run(db, run, status="failed", error_message=str(exc)[:500])
        await db.commit()
        raise


# --- Живой слой «сегодня» (Reporting API) ------------------------------------

_LIVE_TODAY_CACHE_KEY = "bi:metrika_live_today"
_LIVE_TODAY_TTL = 600  # 10 минут — свежесть «сегодня» без спама в API


async def live_today_reference() -> dict[str, Any] | None:
    """Живые агрегаты Метрики за сегодня через Reporting API.

    Logs API отдаёт повизитные данные только за завершённые дни, поэтому на
    периоде «Сегодня» все Метрика-блоки BI были нулями. Reporting API текущий
    день отдаёт — берём сводку (визиты/посетители) и базовые разрезы
    (источники, поисковики, устройства, города). Кэш 10 минут в cache-Redis.
    Ошибка API → None: BI показывает честное «данных пока нет», не 500.
    """
    if not settings.yandex_metrika_read_token:
        return None
    from app.core.cache import cache_get, cache_set
    cached = await cache_get(_LIVE_TODAY_CACHE_KEY)
    if cached:
        return cached

    counter_id = _primary_counter_id()
    rep = MetrikaReportingClient()

    async def _breakdown(dimension: str, limit: int = 15, key: str = "id") -> dict[str, int]:
        # key="id" — машинные коды (organic/desktop/yandex), совместимые с
        # ключами Logs-слоя (`_acquisition`); key="name" — человекочитаемо (города).
        r = await rep.table(
            counter_id=counter_id, metrics=["ym:s:visits"],
            dimensions=[dimension], date_from="today", date_to="today",
            sort=["-ym:s:visits"], limit=limit,
        )
        out: dict[str, int] = {}
        for row in (r.data or {}).get("data") or []:
            dims = row.get("dimensions") or []
            d0 = dims[0] or {} if dims else {}
            label = d0.get(key) or d0.get("name")
            visits = (row.get("metrics") or [0])[0]
            if label and visits:
                out[str(label)] = int(visits)
        return out

    try:
        totals_resp = await rep.table(
            counter_id=counter_id, metrics=["ym:s:visits", "ym:s:users"],
            date_from="today", date_to="today", limit=1,
        )
        totals = (totals_resp.data or {}).get("totals") or []
        if totals and isinstance(totals[0], list):
            totals = totals[0]
        visits = int(totals[0]) if totals else 0
        users = int(totals[1]) if len(totals) > 1 else 0
        live = {
            "visits": visits,
            "users": users,
            "sources": await _breakdown("ym:s:lastTrafficSource", 10),
            "search_engines": await _breakdown("ym:s:lastSearchEngineRoot", 8),
            "devices": await _breakdown("ym:s:deviceCategory", 4),
            "cities": await _breakdown("ym:s:regionCity", 15, key="name"),
        }
    except Exception:  # noqa: BLE001 — live-слой не должен ронять BI
        logger.warning("Metrika live today fetch failed", exc_info=True)
        return None

    await cache_set(_LIVE_TODAY_CACHE_KEY, live, ttl=_LIVE_TODAY_TTL)
    return live


# --- Reporting-агрегаты дня -------------------------------------------------

_ACQ_REPORTS: list[dict[str, Any]] = [
    {
        "report_type": "traffic_sources",
        "dimensions": ["ym:s:lastsignTrafficSource"],
        "metrics": ["ym:s:visits", "ym:s:users", "ym:s:bounceRate",
                    "ym:s:pageDepth", "ym:s:avgVisitDurationSeconds"],
        "limit": 20,
    },
    {
        "report_type": "search_engines",
        "dimensions": ["ym:s:lastsignSearchEngine"],
        "metrics": ["ym:s:visits", "ym:s:users"],
        "filters": "ym:s:lastsignTrafficSource=='organic'",
        "limit": 20,
    },
    {
        "report_type": "referrers",
        "dimensions": ["ym:s:lastsignReferalSource"],
        "metrics": ["ym:s:visits", "ym:s:users"],
        "filters": "ym:s:lastsignTrafficSource=='referral'",
        "limit": 50,
    },
    {
        "report_type": "ad_campaigns",
        "dimensions": ["ym:s:lastsignUTMCampaign"],
        "metrics": ["ym:s:visits", "ym:s:users", "ym:s:bounceRate"],
        "filters": "ym:s:lastsignTrafficSource=='ad'",
        "limit": 30,
    },
]


async def sync_acquisition_reports_for_day(db: AsyncSession, day: date,
                                           counter_id: str | None = None) -> int:
    """Дневные агрегаты привлечения Reporting API → снапшоты + структурные таблицы."""
    counter_id = counter_id or _primary_counter_id()
    client = MetrikaReportingClient()
    run = await start_sync_run(
        db, source="yandex_metrika", job_type="daily_acquisition_reports",
        date_from=day, date_to=day, metadata={"counter_id": counter_id},
    )
    await db.commit()
    processed = 0
    try:
        for spec in _ACQ_REPORTS:
            response = await client.table(
                counter_id=counter_id,
                metrics=spec["metrics"],
                dimensions=spec["dimensions"],
                filters=spec.get("filters"),
                date_from=day, date_to=day,
                limit=spec["limit"],
            )
            await store_metrika_report_snapshot(
                db, counter_id=counter_id, report_type=spec["report_type"],
                query={k: spec[k] for k in ("dimensions", "metrics") },
                response=response, date_from=day, date_to=day,
            )
            processed += len((response.data or {}).get("data", []))
        await db.commit()

        # Структурные таблицы: фразы + постраничные метрики (реюз backfill'а).
        processed += await backfill_metrika_search_phrases(
            db, date_from=day, date_to=day, counter_id=counter_id)
        processed += await backfill_metrika_daily_pages(
            db, date_from=day, date_to=day, counter_id=counter_id)

        await finish_sync_run(db, run, records_processed=processed)
        await db.commit()
        logger.info("Metrika acquisition reports for %s: %s rows", day, processed)
        return processed
    except Exception as exc:
        await db.rollback()
        await finish_sync_run(db, run, status="failed", error_message=str(exc)[:500])
        await db.commit()
        raise


async def sync_acquisition_for_day(db: AsyncSession, day: date) -> dict[str, int]:
    """Полный дневной сбор привлечения: агрегаты + повизитное сырьё.

    Каждый контур падает независимо: сбой Logs API не лишает нас агрегатов
    (и наоборот). Возвращает счётчики для логов/инвентаризации.
    """
    out = {"reports": 0, "visits": 0}
    failed_layers: list[str] = []
    try:
        out["reports"] = await sync_acquisition_reports_for_day(db, day)
    except Exception:
        logger.exception("Acquisition reports sync failed for %s", day)
        failed_layers.append("reports")
    try:
        out["visits"] = await sync_visits_for_day(db, day)
    except Exception:
        logger.exception("Acquisition visits log sync failed for %s", day)
        failed_layers.append("visits")
    # Н-23: partial-провал не должен выглядеть успешной job'ой — дыра в
    # DS-датасете (raw_metrika_visits/фразы) копится молча.
    if failed_layers:
        try:
            from app.services.alerting import send_telegram
            await send_telegram(
                "🟡 <b>Metrika acquisition partial</b>\n"
                f"День {day}: провалился слой {', '.join(failed_layers)} "
                f"(собрано: reports={out['reports']}, visits={out['visits']}).",
                kind="acquisition_alert",
            )
        except Exception:
            logger.warning("Acquisition partial alert failed", exc_info=True)
    return out

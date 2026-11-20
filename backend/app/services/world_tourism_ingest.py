"""Загрузка рядов раздела «Туризм» стран мира в `world_indicators`/`world_data_points` (20.11.2026).

Описание рядов и разбор файлов — `world_tourism_sources`. Запись карточки, точек и копии последних точек —
общая с международными издателями (`world_intl_ingest.upsert_series`). Повторный прогон идемпотентен;
с пустой базы загружается вся история.

Один смысл — один ряд у страны (ADR-0012, official-first):
- «Туристы из России»: национальная служба страны (Кипр — CYSTAT, Турция — министерство туризма) важнее
  ОЭСР; у этих стран ряд ОЭСР не пишется никогда, даже если национальный файл в этот прогон не скачался.
- «Доля туризма в ВВП»: ОЭСР (свежее, год 2025) важнее UN Tourism; если ОЭСР в этот прогон не ответила,
  ряд UN Tourism не пишется, чтобы карточка не перескакивала между издателями.

Национальные службы стран назначения (Турция, Армения, Азербайджан, Индия, Израиль, Япония, Корея, Черногория,
Сербия, Испания) и Евростат «ночёвки по стране проживания» загружаются из таблиц сбора c5 20.11.2026
(`raw/<страна>/tidy.csv`, `--tidy-dir`): их сайты отдают файлы с плавающими именами, часть не отвечает с прода
(Турция). Ночная задача их не трогает; обновление — новый сбор и повторный запуск.

Запуск::

    # все издатели из сети (кроме Турции)
    docker compose exec backend python -m app.services.world_tourism_ingest
    # выбранные издатели
    docker compose exec backend python -m app.services.world_tourism_ingest imf_bop untourism
    # из сохранённых файлов (каталог raw/ сбора 20.11.2026: imf_bop_travel.csv.gz, untourism/, oecd/, …)
    docker compose exec backend python -m app.services.world_tourism_ingest --raw-dir /tmp/tourism-raw
    # национальные службы стран назначения из таблиц сбора (каталог c5/raw с папками стран)
    docker compose exec backend python -m app.services.world_tourism_ingest --tidy-dir /tmp/c5raw
"""

from __future__ import annotations

import asyncio
import gzip
import logging
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

from sqlalchemy import select

from app.core.cache import bump_namespaces
from app.database import async_session
from app.models import WorldCountry, WorldDatasetState, WorldIngestDatasetLog, WorldIngestRun
from app.services import world_tourism_sources as src
from app.services.world_intl_ingest import _now, upsert_series

logger = logging.getLogger(__name__)

NETWORK_PROVIDERS = (
    src.IMF_PROVIDER, src.UNT_PROVIDER, src.OECD_PROVIDER, src.ESTAT_PROVIDER, src.CYSTAT_PROVIDER,
    src.GEOSTAT_PROVIDER,
)
TIMEOUT_SEC = 180
_DATASET_BY_PROVIDER = {
    src.IMF_PROVIDER: "bop", src.UNT_PROVIDER: "bulk", src.OECD_PROVIDER: "tourism",
    src.ESTAT_PROVIDER: "bop_its6_det", src.CYSTAT_PROVIDER: "2021010E", src.GEOSTAT_PROVIDER: "0505EN0204",
    **{provider: "national" for provider in src.TIDY_PROVIDERS},
}
# Ряд, который издатель не продолжает дольше этого срока (Канада по лечению — 2011 год), не заводится:
# карточка с последним значением десятилетней давности вводит в заблуждение.
MAX_SILENT_YEARS = 8
_GDP_SHARE = "tourism-gdp-share"
_RU_ARRIVALS = "tour-arrivals-russia"


def _session():
    from app.services.http_client import create_session

    return create_session(timeout=TIMEOUT_SEC)


def _get(url: str, *, accept: str = "*/*") -> bytes:
    response = _session().get(url, timeout=TIMEOUT_SEC, headers={"Accept": accept, "User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    return response.content


def _post_json(url: str, payload: dict) -> bytes:
    response = _session().post(url, json=payload, timeout=TIMEOUT_SEC)
    response.raise_for_status()
    return response.content


def _text(blob: bytes) -> str:
    return blob.decode("utf-8-sig", errors="replace")


# --- сеть -------------------------------------------------------------------

def fetch_network(provider: str, iso3_codes: list[str]) -> tuple[src.Parsed, dict]:
    """Сеть → разобранные ряды издателя и частоты рядов (у МВФ — квартал или год по стране)."""
    if provider == src.IMF_PROVIDER:
        items = "+".join(sorted({item.series_id.split(".", 1)[1] for item in src.IMF_SERIES}))
        url = src.IMF_URL.format(countries="+".join(sorted(iso3_codes)), items=items)
        return src.parse_imf_bop_csv(_text(_get(url, accept="application/vnd.sdmx.data+csv;version=1.0.0")))
    if provider == src.UNT_PROVIDER:
        link = src.untourism_zip_link(_text(_get(src.UNT_PAGE_URL, accept="text/html")))
        if not link:
            raise RuntimeError("UN Tourism: на странице базы не найдена ссылка на архив")
        return src.parse_untourism_workbooks(src.untourism_workbooks_from_zip(_get(link))), {}
    if provider == src.OECD_PROVIDER:
        accept = "application/vnd.sdmx.data+csv; charset=utf-8"
        parsed = src.parse_oecd_key_csv(_text(_get(src.OECD_KEY_URL, accept=accept)))
        parsed.update(src.parse_oecd_inbound_russia_csv(_text(_get(src.OECD_INBOUND_RU_URL, accept=accept))))
        return parsed, {}
    if provider == src.ESTAT_PROVIDER:
        return src.parse_estat_travel_russia_csv(_text(_get(src.ESTAT_URL))), {}
    if provider == src.CYSTAT_PROVIDER:
        blob = _post_json(src.CYSTAT_URL, {"query": [], "response": {"format": "csv"}})
        return src.parse_cystat_csv(_text(blob)), {}
    if provider == src.GEOSTAT_PROVIDER:
        link = src.geostat_visits_link(_text(_get(src.GEOSTAT_PAGE_URL, accept="text/html")))
        if not link:
            raise RuntimeError("Geostat: на странице не найдена таблица визитов по гражданству")
        return src.parse_geostat_visits_xlsx(_get(link)), {}
    raise RuntimeError(f"{provider}: загрузка из сети не поддерживается, нужен файл")


# --- сохранённые файлы ----------------------------------------------------------

def _read(path: Path) -> bytes:
    data = path.read_bytes()
    return gzip.decompress(data) if path.suffix == ".gz" else data


def fetch_tidy(provider: str, tidy_dir: Path) -> tuple[src.Parsed, dict]:
    """Таблица сбора страны (`<tidy_dir>/<папка>/tidy.csv`) → ряды издателя."""
    specs = [spec for spec in src.TIDY_SPECS if spec.series.provider == provider]
    path = tidy_dir / src.TIDY_FOLDERS[provider] / "tidy.csv"
    return src.parse_tidy_csv(path.read_text(encoding="utf-8-sig"), specs), {}


def fetch_local(provider: str, raw_dir: Path) -> tuple[src.Parsed, dict]:
    """Каталог сбора (`raw/` агента a4) → разобранные ряды; имена файлов — как у сбора 20.11.2026."""
    if provider == src.IMF_PROVIDER:
        return src.parse_imf_bop_csv(_text(_read(raw_dir / "imf_bop_travel.csv.gz")))
    if provider == src.UNT_PROVIDER:
        books = [path.read_bytes() for path in sorted((raw_dir / "untourism").rglob("*.xlsx"))]
        return src.parse_untourism_workbooks(books), {}
    if provider == src.OECD_PROVIDER:
        parsed = src.parse_oecd_key_csv(_text(_read(raw_dir / "oecd" / "DF_KEY_IND_PC.csv.gz")))
        parsed.update(src.parse_oecd_inbound_russia_csv(_text(_read(raw_dir / "oecd" / "DF_INBOUND.csv.gz"))))
        return parsed, {}
    if provider == src.ESTAT_PROVIDER:
        return src.parse_estat_travel_russia_csv(_text(_read(raw_dir / "eurostat" / "bop_its6_det_travel.csv"))), {}
    if provider == src.CYSTAT_PROVIDER:
        return src.parse_cystat_csv(_text(_read(raw_dir / "cyprus" / "arrivals_by_country_monthly.csv"))), {}
    if provider == src.GEOSTAT_PROVIDER:
        files = sorted((raw_dir / "georgia").glob("0505EN0204*.xlsx"))
        if not files:
            raise FileNotFoundError("georgia/0505EN0204*.xlsx")
        return src.parse_geostat_visits_xlsx(files[0].read_bytes()), {}
    raise ValueError(provider)


# --- кто владеет рядом ----------------------------------------------------------

def plan_writes(
    fetched: dict[str, tuple[src.Parsed, dict]],
    failed: set[str],
    catalog: set[str],
    *,
    today: date | None = None,
) -> dict[str, list[tuple[src.TourismSeries, str, src.Points]]]:
    """{издатель: [(ряд, страна, точки)]} после правил «один смысл — один ряд у страны»."""
    today = today or date.today()
    oecd_gdp = {
        country for (suffix, country) in fetched.get(src.OECD_PROVIDER, ({}, {}))[0] if suffix == _GDP_SHARE
    }
    plan: dict[str, list] = {}
    for provider, (parsed, freqs) in fetched.items():
        rows = plan.setdefault(provider, [])
        for (suffix, country), points in sorted(parsed.items()):
            if country not in catalog or not points or points[-1][0].year < today.year - MAX_SILENT_YEARS:
                continue
            if suffix == _GDP_SHARE and provider == src.UNT_PROVIDER:
                if src.OECD_PROVIDER in failed or country in oecd_gdp:
                    continue
            if suffix == _RU_ARRIVALS and provider == src.OECD_PROVIDER and country in src.NATIONAL_RU_ARRIVALS:
                continue
            series = src.series_lookup(provider, suffix)
            freq = freqs.get((suffix, country))
            if freq and freq != series.frequency:
                series = replace(series, frequency=freq)
            rows.append((series, country, points))
    return plan


# --- запись ---------------------------------------------------------------------

async def _write_provider(provider: str, rows: list, countries: dict[str, WorldCountry], today: date) -> dict:
    dataset_id = _DATASET_BY_PROVIDER[provider]
    async with async_session() as db:
        run = WorldIngestRun(source=provider, is_shadow=False, started_at=_now(), datasets_selected=1)
        db.add(run)
        await db.commit()
        await db.refresh(run)
        run_id = run.id
        try:
            touched = 0
            for series, iso2, points in rows:
                touched += await upsert_series(db, country=countries[iso2], series=series, points=points, is_listed=True)
            if not rows:
                raise RuntimeError(f"{provider}: издатель не вернул ни одного ряда стран каталога")
            state = await db.get(WorldDatasetState, (provider, dataset_id))
            if state is None:
                state = WorldDatasetState(provider=provider, dataset_id=dataset_id)
                db.add(state)
            state.last_update_of_data = today
            state.status = "ok"
            state.last_success_at = _now()
            state.last_error = None
            db.add(WorldIngestDatasetLog(
                run_id=run_id, provider=provider, dataset_id=dataset_id, status="ok",
                source_updated_at=today, rows_fetched=touched,
            ))
            run = await db.get(WorldIngestRun, run_id)
            run.datasets_succeeded = 1
            run.status = "ok"
            run.completed_at = _now()
            await db.commit()
        except Exception as exc:  # noqa: BLE001 — журнал прогона и проброс
            await db.rollback()
            await _log_failure(run_id, provider, dataset_id, str(exc))
            raise
    return {"provider": provider, "run_id": run_id, "series": len(rows), "points_touched": touched}


async def _log_failure(run_id: int | None, provider: str, dataset_id: str, error: str) -> None:
    async with async_session() as db:
        if run_id is None:
            run = WorldIngestRun(source=provider, is_shadow=False, started_at=_now(), datasets_selected=1)
            db.add(run)
            await db.flush()
            run_id = run.id
        failed = await db.get(WorldIngestRun, run_id)
        failed.status = "failed"
        failed.completed_at = _now()
        failed.error_message = error[:2000]
        failed.datasets_failed = 1
        db.add(WorldIngestDatasetLog(
            run_id=run_id, provider=provider, dataset_id=dataset_id, status="error", error_message=error[:2000],
        ))
        await db.commit()


async def run_world_tourism_ingest(
    providers: tuple[str, ...] = NETWORK_PROVIDERS,
    *,
    raw_dir: Path | None = None,
    tidy_dir: Path | None = None,
    today: date | None = None,
) -> dict:
    """Издатели по очереди; сбой одного виден в журнале и не останавливает остальных."""
    today = today or date.today()
    async with async_session() as db:
        countries = {row.code: row for row in (await db.execute(select(WorldCountry))).scalars().all()}
    iso3 = sorted({iso3 for iso3, code in src.ISO3_TO_CATALOG.items() if code in countries and iso3 != "XKX"})
    fetched: dict[str, tuple[src.Parsed, dict]] = {}
    failed: set[str] = set()
    results: dict[str, object] = {}
    for provider in providers:
        try:
            if provider in src.TIDY_PROVIDERS:
                if tidy_dir is None:
                    raise RuntimeError(f"{provider}: нужен каталог таблиц сбора (--tidy-dir)")
                fetched[provider] = await asyncio.to_thread(fetch_tidy, provider, Path(tidy_dir))
            elif raw_dir is not None:
                fetched[provider] = await asyncio.to_thread(fetch_local, provider, Path(raw_dir))
            else:
                fetched[provider] = await asyncio.to_thread(fetch_network, provider, iso3)
        except Exception as exc:  # noqa: BLE001 — сбой издателя пишется в журнал прогона
            logger.exception("world tourism fetch failed: %s", provider)
            failed.add(provider)
            results[provider] = {"error": str(exc)[:300]}
            await _log_failure(None, provider, _DATASET_BY_PROVIDER[provider], str(exc))
    for provider, rows in plan_writes(fetched, failed, set(countries), today=today).items():
        try:
            results[provider] = await _write_provider(provider, rows, countries, today)
        except Exception as exc:  # noqa: BLE001
            logger.exception("world tourism write failed: %s", provider)
            results[provider] = {"error": str(exc)[:300]}
    await bump_namespaces("world", "world-catalog", "ssr-world")
    logger.info("world tourism ingest: %s", results)
    return results


def _cli(argv: list[str]) -> dict:
    raw_dir = tidy_dir = None
    chosen: list[str] = []
    args = iter(argv)
    for arg in args:
        if arg == "--raw-dir":
            raw_dir = Path(next(args))
        elif arg == "--tidy-dir":
            tidy_dir = Path(next(args))
        elif arg in src.PROVIDERS:
            chosen.append(arg)
    if not chosen:
        chosen = list(src.TIDY_PROVIDERS) if tidy_dir and not raw_dir else list(NETWORK_PROVIDERS)
        if tidy_dir and raw_dir:
            chosen += list(src.TIDY_PROVIDERS)
    return asyncio.run(run_world_tourism_ingest(tuple(chosen), raw_dir=raw_dir, tidy_dir=tidy_dir))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(_cli(sys.argv[1:]))

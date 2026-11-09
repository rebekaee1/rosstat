"""Раздел «Исследования»: каталог PDF-отчётов к роликам ForecastEconomy и счётчик скачиваний (09.11.2026).

Каталог — `app/data/research_catalog.json` (готовит `content-factory/материалы/выгрузить_на_сайт.py`), файлы лежат
в `frontend/public/research/`. Скачивание идёт через `/api/v1/research/{slug}/download`: счётчик +1 (один адрес —
не чаще раза в сутки на отчёт, метка в Redis с хэшем) и 302 на статический PDF. ПДн не храним.

Источник скачивания (09.11.2026, владелец: «нужно ещё трекерить, сколько с сайта загрузили»): `site` — переход со
страницы сайта (Referer с нашего хоста; браузер шлёт его при клике), `bot` / `tg` — метки `?src=` у ссылок бота и
канала (в HTML сайта их нет, обходчик по ссылкам страниц их не получит), `direct` — без перехода с сайта и без метки. Ферма 05-09.11 ходила с десятков тысяч адресов браузерным UA и
без Referer, поэтому `direct` в публичный счёт не входит и показывается владельцу отдельной строкой.
"""
import hashlib
import json
import logging
from datetime import date
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import ResearchDownload
from app.services.display import today_msk

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/research", tags=["research"])
CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "research_catalog.json"
DEDUP_TTL = 24 * 3600
SOURCES = ("site", "bot", "tg", "direct")
PUBLIC_SOURCES = ("site", "bot", "tg")
_LINK_SOURCES = ("bot", "tg")
_OWN_HOST_SUFFIX = "forecasteconomy.com"


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    try:
        return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.exception("research catalog unreadable")
        return {"items": []}


def catalog_item(slug: str) -> dict | None:
    return next((i for i in load_catalog().get("items", []) if i.get("slug") == slug), None)


async def download_counts(db: AsyncSession) -> dict[str, int]:
    """Публичный счёт по отчётам: без `direct` (переходы не с сайта и без метки — почти всегда ферма)."""
    try:
        rows = (await db.execute(
            select(ResearchDownload.slug, func.sum(ResearchDownload.count))
            .where(ResearchDownload.source.in_(PUBLIC_SOURCES))
            .group_by(ResearchDownload.slug)
        )).all()
    except Exception:  # таблицы ещё нет (до миграции) — раздел всё равно работает
        logger.warning("research_downloads unavailable", exc_info=True)
        await db.rollback()
        return {}
    return {slug: int(total or 0) for slug, total in rows}


@router.get("")
async def research_list(response: Response, db: AsyncSession = Depends(get_db)):
    cat = load_catalog()
    counts = await download_counts(db)
    response.headers["Cache-Control"] = "public, max-age=60"
    items = [{**i, "downloads": counts.get(i["slug"], 0)} for i in cat.get("items", [])]
    return {"release": cat.get("release"), "release_en": cat.get("release_en"), "group_url": cat.get("group_url") or None,
            "items": items,
            "total_downloads": sum(counts.values())}


def _client_ip(request: Request) -> str:
    from app.main import pick_client_ip  # лениво: app.main импортирует роутеры

    return pick_client_ip(request.headers.get("x-forwarded-for", ""), request.client.host if request.client else "unknown")


def download_source(request: Request) -> str:
    """bot / tg по метке `src`, site по Referer с нашего хоста; иначе direct. Метки `site` нет нарочно: ссылка
    со страницы с такой меткой досталась бы и обходчику."""
    from urllib.parse import urlsplit

    src = (request.query_params.get("src") or "").strip().lower()
    if src in _LINK_SOURCES:
        return src
    host = (urlsplit(request.headers.get("referer") or "").hostname or "").lower()
    if host == _OWN_HOST_SUFFIX or host.endswith("." + _OWN_HOST_SUFFIX):
        return "site"
    return "direct"


async def downloads_by_source(db: AsyncSession, day) -> dict[str, int]:
    """Скачивания за день по источникам (для утреннего дайджеста)."""
    try:
        rows = (await db.execute(
            select(ResearchDownload.source, func.sum(ResearchDownload.count))
            .where(ResearchDownload.date == day).group_by(ResearchDownload.source)
        )).all()
    except Exception:  # noqa: BLE001 - до миграции таблицы нет
        await db.rollback()
        return {}
    return {src: int(n or 0) for src, n in rows}


async def _first_today(slug: str, request: Request, source: str = "site") -> bool:
    """True, если этот адрес сегодня этот отчёт из этого источника ещё не скачивал. Без Redis — считаем каждое.

    Источник в метке: заход без перехода (direct) не должен съедать учёт настоящего скачивания с того же адреса."""
    try:
        from app.core.cache import get_redis
        r = await get_redis()
        key = "fe:research:dl:" + hashlib.sha256(f"{slug}|{source}|{_client_ip(request)}|{today_msk()}".encode()).hexdigest()[:32]
        return bool(await r.set(key, "1", ex=DEDUP_TTL, nx=True))
    except Exception:
        return True


async def _bump(slug: str, db: AsyncSession, source: str = "site") -> None:
    """+1 к счётчику отчёта за сегодня по источнику (обновление, а если строки ещё нет — вставка; гонка — повтор)."""
    from sqlalchemy import update
    from sqlalchemy.exc import IntegrityError

    day = today_msk()
    upd = update(ResearchDownload).where(
        ResearchDownload.slug == slug, ResearchDownload.date == day, ResearchDownload.source == source,
    ).values(count=ResearchDownload.count + 1)
    try:
        res = await db.execute(upd)
        if not res.rowcount:
            db.add(ResearchDownload(slug=slug, date=day, source=source, count=1))
            try:
                await db.flush()
            except IntegrityError:
                await db.rollback()
                await db.execute(upd)
        await db.commit()
    except Exception:
        logger.warning("research download count failed", exc_info=True)
        await db.rollback()


@router.get("/{slug}/download", include_in_schema=False)
async def research_download(slug: str, request: Request, db: AsyncSession = Depends(get_db)):
    item = catalog_item(slug)
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    ua = (request.headers.get("user-agent") or "").lower()
    is_bot = any(b in ua for b in ("bot", "spider", "crawl", "preview", "slurp"))
    source = download_source(request)
    if not is_bot and request.method == "GET" and await _first_today(slug, request, source):
        await _bump(slug, db, source)
    resp = RedirectResponse(item["file"], status_code=302)
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Robots-Tag"] = "noindex"
    return resp

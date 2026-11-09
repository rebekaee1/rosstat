"""Раздел «Исследования»: каталог PDF-отчётов к роликам ForecastEconomy и счётчик скачиваний (09.11.2026).

Каталог — `app/data/research_catalog.json` (готовит `content-factory/материалы/выгрузить_на_сайт.py`), файлы лежат
в `frontend/public/research/`. Скачивание идёт через `/api/v1/research/{slug}/download`: счётчик +1 (один адрес —
не чаще раза в сутки на отчёт, метка в Redis с хэшем) и 302 на статический PDF. ПДн не храним.
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
    try:
        rows = (await db.execute(
            select(ResearchDownload.slug, func.sum(ResearchDownload.count)).group_by(ResearchDownload.slug)
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


async def _first_today(slug: str, request: Request) -> bool:
    """True, если этот адрес сегодня этот отчёт ещё не скачивал. Без Redis — считаем каждое скачивание."""
    try:
        from app.core.cache import get_redis
        r = await get_redis()
        key = "fe:research:dl:" + hashlib.sha256(f"{slug}|{_client_ip(request)}|{today_msk()}".encode()).hexdigest()[:32]
        return bool(await r.set(key, "1", ex=DEDUP_TTL, nx=True))
    except Exception:
        return True


async def _bump(slug: str, db: AsyncSession) -> None:
    """+1 к счётчику отчёта за сегодня (обновление, а если строки ещё нет — вставка; гонка — повтор обновлением)."""
    from sqlalchemy import update
    from sqlalchemy.exc import IntegrityError

    day = today_msk()
    upd = update(ResearchDownload).where(ResearchDownload.slug == slug, ResearchDownload.date == day) \
        .values(count=ResearchDownload.count + 1)
    try:
        res = await db.execute(upd)
        if not res.rowcount:
            db.add(ResearchDownload(slug=slug, date=day, count=1))
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
    if not is_bot and request.method == "GET" and await _first_today(slug, request):
        await _bump(slug, db)
    resp = RedirectResponse(item["file"], status_code=302)
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Robots-Tag"] = "noindex"
    return resp

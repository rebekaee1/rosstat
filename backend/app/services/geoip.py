"""Гео по IP своими силами: DB-IP City Lite (CC-BY 4.0) + maxminddb.

Определяем страну/регион/город посетителя в момент приёма session_start —
сам IP НЕ сохраняем (152-ФЗ): в БД уходят только названия. Файл базы живёт в
docker-томе (settings.geoip_db_path); при отсутствии backend скачивает свежую
месячную сборку в фоне при старте (~100 МБ, gzip). Ежемесячное обновление —
job в планировщике: та же функция скачивания, ссылка помесячная.

Reader создаётся лениво и кэшируется; отсутствие файла = гео просто NULL,
ни один запрос не падает.
"""
from __future__ import annotations

import gzip
import logging
import os
import shutil
import tempfile
from datetime import datetime, timezone

from app.config import settings

logger = logging.getLogger(__name__)

_reader = None
_reader_mtime: float | None = None


def _get_reader():
    """Ленивый maxminddb.Reader; перечитывает файл после обновления базы."""
    global _reader, _reader_mtime
    path = settings.geoip_db_path
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None
    if _reader is not None and _reader_mtime == mtime:
        return _reader
    try:
        import maxminddb
        _reader = maxminddb.open_database(path)
        _reader_mtime = mtime
        logger.info("GeoIP database loaded: %s", path)
    except Exception as exc:  # noqa: BLE001 — гео опционально
        logger.warning("GeoIP database open failed: %s", exc)
        _reader = None
    return _reader


def _name(block: dict | None, lang: str = "ru") -> str | None:
    if not isinstance(block, dict):
        return None
    names = block.get("names") or {}
    return names.get(lang) or names.get("en") or None


def lookup(ip: str | None) -> dict[str, str | None]:
    """IP → {country, region, city} (русские имена, фолбэк en). Никогда не бросает."""
    empty = {"country": None, "region": None, "city": None}
    if not ip:
        return empty
    reader = _get_reader()
    if reader is None:
        return empty
    try:
        rec = reader.get(ip)
    except Exception:
        return empty
    if not isinstance(rec, dict):
        return empty
    subdivisions = rec.get("subdivisions") or []
    region = _name(subdivisions[0]) if subdivisions else None
    return {
        "country": _name(rec.get("country")),
        "region": region,
        "city": _name(rec.get("city")),
    }


def client_ip_from_headers(x_forwarded_for: str | None, fallback: str | None) -> str | None:
    """Первый адрес из X-Forwarded-For (Caddy ставит реальный клиентский IP)."""
    if x_forwarded_for:
        first = x_forwarded_for.split(",")[0].strip()
        if first:
            return first
    return fallback


async def download_geoip_db(force: bool = False) -> bool:
    """Скачивает месячную сборку DB-IP Lite в settings.geoip_db_path.

    Возвращает True при успехе. Пробует текущий месяц, затем предыдущий
    (сборка публикуется в первых числах). Идемпотентно: при живом файле
    моложе 45 дней и force=False ничего не делает.
    """
    import httpx

    path = settings.geoip_db_path
    if not force:
        try:
            age_days = (datetime.now(timezone.utc).timestamp() - os.path.getmtime(path)) / 86400
            if age_days < 45:
                return True
        except OSError:
            pass

    os.makedirs(os.path.dirname(path), exist_ok=True)
    now = datetime.now(timezone.utc)
    candidates = []
    year, month = now.year, now.month
    for _ in range(2):
        candidates.append(settings.geoip_download_url_template.format(yyyy=f"{year:04d}", mm=f"{month:02d}"))
        month -= 1
        if month == 0:
            year, month = year - 1, 12

    async with httpx.AsyncClient(timeout=300, follow_redirects=True) as client:
        for url in candidates:
            try:
                resp = await client.get(url)
                if resp.status_code != 200 or len(resp.content) < 1_000_000:
                    continue
                with tempfile.NamedTemporaryFile(delete=False, dir=os.path.dirname(path)) as tmp:
                    tmp.write(gzip.decompress(resp.content))
                    tmp_path = tmp.name
                shutil.move(tmp_path, path)
                logger.info("GeoIP database downloaded: %s (%d MB)", url, len(resp.content) // 1_048_576)
                return True
            except Exception as exc:  # noqa: BLE001
                logger.warning("GeoIP download failed (%s): %s", url, exc)
    return False

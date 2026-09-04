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
_asn_reader = None
_asn_reader_mtime: float | None = None


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


def db_age_days() -> float | None:
    """Возраст файла базы в днях; None — файла нет (Н-29: метрика свежести гео)."""
    try:
        return (datetime.now(timezone.utc).timestamp()
                - os.path.getmtime(settings.geoip_db_path)) / 86400
    except OSError:
        return None


def _name(block: dict | None, lang: str = "ru") -> str | None:
    if not isinstance(block, dict):
        return None
    names = block.get("names") or {}
    return names.get(lang) or names.get("en") or None


def _get_asn_reader():
    global _asn_reader, _asn_reader_mtime
    path = settings.geoip_asn_db_path
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None
    if _asn_reader is not None and _asn_reader_mtime == mtime:
        return _asn_reader
    try:
        import maxminddb
        _asn_reader = maxminddb.open_database(path)
        _asn_reader_mtime = mtime
        logger.info("GeoIP ASN database loaded: %s", path)
    except Exception as exc:  # noqa: BLE001 — ASN опционален
        logger.warning("GeoIP ASN database open failed: %s", exc)
        _asn_reader = None
    return _asn_reader


def lookup(ip: str | None) -> dict[str, str | None]:
    """IP → {country, region, city} (русские имена, фолбэк en). Никогда не бросает."""
    empty = {"country": None, "country_code": None, "region": None, "city": None}
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
        "country_code": (rec.get("country") or {}).get("iso_code"),
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


def lookup_asn(ip: str | None) -> dict[str, int | str | None]:
    """IP → {asn, org}. Пусто, если базы нет. Никогда не бросает."""
    empty: dict[str, int | str | None] = {"asn": None, "org": None}
    if not ip:
        return empty
    reader = _get_asn_reader()
    if reader is None:
        return empty
    try:
        rec = reader.get(ip)
    except Exception:
        return empty
    if rec is None:
        return empty
    asn: int | None = None
    org: str | None = None
    if isinstance(rec, dict):
        raw_asn = rec.get("autonomous_system_number") or rec.get("asn")
        raw_org = (
            rec.get("autonomous_system_organization")
            or rec.get("as_org")
            or rec.get("organization")
        )
        if isinstance(raw_asn, int):
            asn = raw_asn
        elif isinstance(raw_asn, str) and raw_asn.isdigit():
            asn = int(raw_asn)
        if isinstance(raw_org, str) and raw_org.strip():
            org = raw_org.strip()
    return {"asn": asn, "org": org}


async def _download_mmdb(
    path: str, url_template: str, *, min_bytes: int, force: bool
) -> bool:
    import httpx

    if not force:
        try:
            age_days = (
                datetime.now(timezone.utc).timestamp() - os.path.getmtime(path)
            ) / 86400
            if age_days < 45:
                return True
        except OSError:
            pass

    os.makedirs(os.path.dirname(path), exist_ok=True)
    now = datetime.now(timezone.utc)
    candidates = []
    year, month = now.year, now.month
    for _ in range(2):
        candidates.append(url_template.format(yyyy=f"{year:04d}", mm=f"{month:02d}"))
        month -= 1
        if month == 0:
            year, month = year - 1, 12

    async with httpx.AsyncClient(timeout=300, follow_redirects=True) as client:
        for url in candidates:
            try:
                resp = await client.get(url)
                if resp.status_code != 200 or len(resp.content) < min_bytes:
                    continue
                with tempfile.NamedTemporaryFile(
                    delete=False, dir=os.path.dirname(path)
                ) as tmp:
                    tmp.write(gzip.decompress(resp.content))
                    tmp_path = tmp.name
                shutil.move(tmp_path, path)
                logger.info(
                    "GeoIP database downloaded: %s (%d MB)",
                    url,
                    len(resp.content) // 1_048_576,
                )
                return True
            except Exception as exc:  # noqa: BLE001
                logger.warning("GeoIP download failed (%s): %s", url, exc)
    return False


async def download_geoip_db(force: bool = False) -> bool:
    """Скачивает City Lite и ASN Lite в том geoip_data.

    Возвращает True, если городская база на месте. ASN качается рядом;
    отсутствие ASN = хостинг-блок fail-open до появления файла.
    """
    city_ok = await _download_mmdb(
        settings.geoip_db_path,
        settings.geoip_download_url_template,
        min_bytes=1_000_000,
        force=force,
    )
    await _download_mmdb(
        settings.geoip_asn_db_path,
        settings.geoip_asn_download_url_template,
        min_bytes=100_000,
        force=force,
    )
    return city_ok

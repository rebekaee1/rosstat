"""Ночная сборка статических sitemap на диск (план 2026-09-03).

Робот читает файлы через nginx try_files — ни одного запроса в БД на обходе.
Индекс `/sitemap.xml` остаётся на backend (host-aware: до cutover ru. = пустой).
Секции `sitemap-{name}.xml` пишутся в `settings.sitemap_dir`.
"""
from __future__ import annotations

import gzip
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.database import analytics_session

logger = logging.getLogger(__name__)

STATS_NAME = "sitemap-stats.json"


def sitemap_dir() -> Path:
    return Path(settings.sitemap_dir)


def section_file(name: str) -> Path:
    return sitemap_dir() / f"sitemap-{name}.xml"


def stats_file() -> Path:
    return sitemap_dir() / STATS_NAME


def read_stats() -> dict:
    path = stats_file()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def url_count_from_stats() -> int | None:
    stats = read_stats()
    total = stats.get("urls_total")
    return int(total) if total is not None else None


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=path.suffix)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_xml(name: str, xml: str) -> Path:
    """Пишет XML и gzip-близнец (nginx gzip_static)."""
    raw = xml.encode("utf-8")
    dest = section_file(name)
    _atomic_write(dest, raw)
    _atomic_write(Path(str(dest) + ".gz"), gzip.compress(raw, compresslevel=6))
    return dest


def write_stats(payload: dict) -> Path:
    dest = stats_file()
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    _atomic_write(dest, body)
    return dest


async def build_static_sitemaps() -> dict:
    """Собрать все секции на диск. Тяжёлая работа — только analytics_session."""
    from app.api.sitemap import _render_urlset
    from app.services.locale import en_public_origin
    from app.services.site_urls import resolve_section, section_names

    origin = en_public_origin().rstrip("/")
    started = datetime.now(timezone.utc).replace(tzinfo=None)
    sections: dict[str, int] = {}
    errors: list[str] = []

    async with analytics_session() as db:
        names = await section_names(db)
        for name in names:
            try:
                urls = await resolve_section(db, name)
            except Exception as exc:  # noqa: BLE001
                logger.exception("sitemap section %s failed", name)
                errors.append(f"{name}: {exc}")
                continue
            xml = _render_urlset(urls or [], origin=origin)
            write_xml(name, xml)
            sections[name] = len(urls)
            logger.info("sitemap %s: %d urls", name, len(urls))

    stats = {
        "built_at": started.isoformat(timespec="seconds"),
        "origin": origin,
        "sections": sections,
        "urls_total": sum(sections.values()),
        "section_count": len(sections),
        "errors": errors,
    }
    write_stats(stats)
    logger.info(
        "static sitemaps: %d sections, %d urls, %d errors",
        len(sections), stats["urls_total"], len(errors),
    )
    return stats


async def sitemap_build_job() -> None:
    try:
        await build_static_sitemaps()
    except Exception:
        logger.exception("sitemap_build_job failed")

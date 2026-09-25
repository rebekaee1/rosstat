"""Publish complete, host-specific sitemap generations for nginx.

Readers use ``current/<host>/sitemap-*.xml``. A failed build never replaces
current; legacy shared-origin files are deliberately not consumed.
"""
from __future__ import annotations

import fcntl
import gzip
import json
import logging
import os
import re
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.config import settings
from app.database import analytics_session
from app.services.index_policy import is_noindex_path
from app.services.site_urls import (
    SITEMAP_MAX_BYTES,
    SITEMAP_MAX_URLS,
    section_fingerprint,
    section_lastmod,
)

logger = logging.getLogger(__name__)
STATS_NAME = "sitemap-stats.json"
_GENERATION = re.compile(r"^[0-9a-f]{32}$")
_SECTION = re.compile(r"^[a-z0-9-]+$")


def sitemap_dir() -> Path:
    return Path(settings.sitemap_dir)


def _current_generation() -> Path | None:
    root = sitemap_dir()
    current = root / "current"
    if not current.is_symlink():
        return None
    resolved = current.resolve()
    if resolved.parent != (root / "generations").resolve() or not _GENERATION.fullmatch(resolved.name):
        return None
    return resolved if resolved.is_dir() else None


def section_file(name: str, origin: str) -> Path | None:
    if not _SECTION.fullmatch(name):
        return None
    generation = _current_generation()
    if generation is None:
        return None
    host = urlparse(origin).hostname
    stats = _read_json(generation / STATS_NAME)
    host_stats = stats.get("hosts", {}).get(host, {})
    if name not in host_stats.get("sections", {}):
        return None
    return generation / host / f"sitemap-{name}.xml"


def _read_json(path: Path) -> dict:
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        return result if isinstance(result, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def read_stats() -> dict:
    generation = _current_generation()
    return _read_json(generation / STATS_NAME) if generation else {}


def published_sections(origin: str) -> list[str] | None:
    host = urlparse(origin).hostname
    entry = read_stats().get("hosts", {}).get(host)
    return list(entry["sections"]) if entry is not None else None


def published_section_size(name: str, origin: str) -> int | None:
    """URL count for one published section, or None when absent/unknown."""
    host = urlparse(origin).hostname
    entry = read_stats().get("hosts", {}).get(host)
    if entry is None:
        return None
    sections = entry.get("sections") or {}
    raw = sections.get(name)
    return int(raw) if raw is not None else None


def section_lastmods(origin: str) -> dict[str, str]:
    """lastmod дочерних файлов из последней публикации. Пусто, пока билд старый."""
    host = urlparse(origin).hostname
    raw = read_stats().get("hosts", {}).get(host, {}).get("section_lastmod") or {}
    if not isinstance(raw, dict):
        return {}
    return {str(name): str(stamp) for name, stamp in raw.items() if stamp}


def url_count_from_stats() -> int | None:
    total = read_stats().get("urls_total")
    return int(total) if total is not None else None


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    os.chmod(path.parent, 0o755)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=path.suffix)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fchmod(fh.fileno(), 0o644)
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise


def _link_or_copy(src: Path, dest: Path) -> None:
    """Жёсткая ссылка на неизменный шард. Копия — если файловая система не даёт link."""
    dest.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    os.chmod(dest.parent, 0o755)
    try:
        os.link(src, dest)
    except OSError:
        shutil.copyfile(src, dest)
        os.chmod(dest, 0o644)


def _reuse_shard(previous: Path, generation: Path, name: str, origins: list[str]) -> bool:
    """Перенести оба хоста шарда из прошлой генерации, если файлы на месте."""
    sources: list[tuple[Path, Path]] = []
    for origin in origins:
        host = urlparse(origin).hostname or ""
        src = previous / host / f"sitemap-{name}.xml"
        src_gz = Path(str(src) + ".gz")
        if not src.is_file() or not src_gz.is_file():
            return False
        sources.append((src, src_gz))
    for origin, (src, src_gz) in zip(origins, sources, strict=True):
        host = urlparse(origin).hostname or ""
        dest_dir = generation / host
        _link_or_copy(src, dest_dir / src.name)
        _link_or_copy(src_gz, dest_dir / src_gz.name)
    return True


def _write_xml(directory: Path, name: str, xml: str) -> None:
    raw = xml.encode("utf-8")
    if len(raw) > SITEMAP_MAX_BYTES:
        raise ValueError(
            f"Sitemap {name} is {len(raw)} bytes; protocol limit is {SITEMAP_MAX_BYTES}"
        )
    dest = directory / f"sitemap-{name}.xml"
    _atomic_write(dest, raw)
    _atomic_write(Path(str(dest) + ".gz"), gzip.compress(raw, compresslevel=6, mtime=0))


async def build_static_sitemaps() -> dict:
    """Resolve each section once; publish both hosts as one atomic generation.

    flock is nonblocking so another scheduler/manual build cannot interleave
    publication or cleanup, without blocking the async worker's event loop.
    """
    # Includes the same path -> image discovery as the dynamic response.
    # Publishing XML must never invoke the expensive image renderer.
    from app.api.sitemap import SITEMAP_ORIGIN_TOKEN, _render_urlset
    from app.services.locale import en_public_origin, ru_public_origin, apex_locale_en_enabled
    from app.services.site_urls import iter_url_sections

    root = sitemap_dir()
    root.mkdir(parents=True, exist_ok=True, mode=0o755)
    os.chmod(root, 0o755)
    with (root / ".build.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("A sitemap build is already running") from None
        parent = root / "generations"
        parent.mkdir(exist_ok=True, mode=0o755)
        os.chmod(parent, 0o755)
        generation = parent / uuid.uuid4().hex
        generation.mkdir(mode=0o755)
        os.chmod(generation, 0o755)
        previous = _current_generation()
        origins = [en_public_origin().rstrip("/")]
        if apex_locale_en_enabled():
            origins.append(ru_public_origin().rstrip("/"))
        sections: dict[str, int] = {}
        section_stamps: dict[str, str] = {}
        section_digests: dict[str, str] = {}
        reused = 0
        rewritten = 0
        started = datetime.now(timezone.utc)
        previous_digests = {}
        if previous is not None:
            raw_digests = _read_json(previous / STATS_NAME).get("section_digest") or {}
            if isinstance(raw_digests, dict):
                previous_digests = {str(key): str(value) for key, value in raw_digests.items()}
        try:
            async with analytics_session() as db:
                async for name, urls in iter_url_sections(db):
                    if not _SECTION.fullmatch(name):
                        raise ValueError(f"Invalid sitemap section: {name}")
                    if not urls:
                        continue  # Empty chunks must not be advertised.
                    if len(urls) > SITEMAP_MAX_URLS:
                        raise ValueError(
                            f"Sitemap section {name} has {len(urls)} URLs; "
                            f"protocol limit is {SITEMAP_MAX_URLS}"
                        )
                    blocked = [url.path for url in urls if is_noindex_path(url.path)]
                    if blocked:
                        raise ValueError(
                            f"Sitemap section {name} includes noindex URLs: {blocked[:5]}"
                        )
                    stamp = section_lastmod(urls)
                    if stamp:
                        section_stamps[name] = stamp
                    digest = section_fingerprint(urls)
                    section_digests[name] = digest
                    # ~5,04 млн URL на хост. Неизменный шард не рендерим и не
                    # gzip'аем заново: жёсткая ссылка на прошлую генерацию.
                    # Отпечаток не включает хост — EN и RU остаются парой.
                    if (
                        previous is not None
                        and previous_digests.get(name) == digest
                        and _reuse_shard(previous, generation, name, origins)
                    ):
                        reused += 1
                    else:
                        template = _render_urlset(urls, origin=SITEMAP_ORIGIN_TOKEN)
                        for origin in origins:
                            xml = template.replace(SITEMAP_ORIGIN_TOKEN, origin.rstrip("/"))
                            _write_xml(generation / urlparse(origin).hostname, name, xml)
                        rewritten += 1
                    sections[name] = len(urls)
            if not sections:
                raise ValueError("Refusing to publish an empty sitemap generation")
            hosts = {urlparse(origin).hostname: {
                "origin": origin, "sections": sections,
                "section_lastmod": section_stamps,
                "section_digest": section_digests,
                "urls_total": sum(sections.values()), "section_count": len(sections),
            } for origin in origins}
            stats = {
                "built_at": started.isoformat(timespec="seconds"),
                "completed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "generation": generation.name,
                "origin": origins[0], "sections": sections,
                "section_lastmod": section_stamps,
                "section_digest": section_digests,
                "sections_reused": reused,
                "sections_rewritten": rewritten,
                "urls_total": sum(sections.values()), "section_count": len(sections),
                "hosts": hosts, "published_urls_total": sum(h["urls_total"] for h in hosts.values()),
                "errors": [],
            }
            _atomic_write(generation / STATS_NAME, json.dumps(stats, ensure_ascii=False, indent=2).encode())
            link = root / f".current-{generation.name}"
            link.symlink_to(Path("generations") / generation.name)
            os.replace(link, root / "current")
        except Exception:
            shutil.rmtree(generation)
            raise
        # Only this module's UUID directories; keep the previous generation
        # for in-flight reads and rollback. Never touch legacy files/other dirs.
        keep = {generation, previous}
        for candidate in parent.iterdir():
            if candidate not in keep and _GENERATION.fullmatch(candidate.name) and candidate.is_dir() and not candidate.is_symlink():
                try:
                    shutil.rmtree(candidate)
                except OSError:
                    logger.warning("Cannot remove old sitemap generation %s", candidate, exc_info=True)
        logger.info(
            "Published sitemap generation %s: %d URLs across %d hosts (%d reused, %d rewritten)",
            generation.name, stats["published_urls_total"], len(hosts), reused, rewritten,
        )
        return stats


async def sitemap_build_job() -> None:
    # Let the scheduler's existing error listener observe a failed publication.
    await build_static_sitemaps()

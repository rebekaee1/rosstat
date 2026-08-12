#!/usr/bin/env python3
"""Авто-догрузка независимых deep-срезов для всех Eurostat dataset_id в БД.

Устойчивый режим:
  - checkpoint ``done.txt`` / ``failed.txt`` (переживает рестарт)
  - без предварительного полного plan-прохода (он сжигал время и 413)
  - fail-open: один датасет не валит весь прогон

Запуск (отдельный контейнер — не умирает при restart backend)::

    docker compose run -d --name rosstat-eurostat-deep --no-deps \\
      -e PYTHONPATH=/app -e PYTHONUNBUFFERED=1 \\
      -e AUTO_DEEP_WORKERS=2 \\
      -v \"$PWD/backend/.cache/eurostat-deep:/var/lib/eurostat-deep\" \\
      backend python /app/scripts/load-world-auto-deep.py

Опции через env:
  AUTO_DEEP_LIMIT=50
  AUTO_DEEP_ONLY=ilc_di07,demo_pjan
  AUTO_DEEP_OFFSET=783
  AUTO_DEEP_WORKERS=2
  AUTO_DEEP_CHECKPOINT_DIR=/var/lib/eurostat-deep
  AUTO_DEEP_SKIP_PLAN=1   (default) — не гонять structure по всем заранее
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, "/app")

from sqlalchemy import select  # noqa: E402

from app.core.cache import bump_namespaces  # noqa: E402
from app.database import async_session  # noqa: E402
from app.models import WorldCountry, WorldIndicator  # noqa: E402
from app.services.eurostat_parser import (  # noqa: E402
    WORLD_COUNTRIES,
    fetch_deep_slices,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
    force=True,
)
log = logging.getLogger("load-world-auto-deep")


def _checkpoint_dir() -> Path:
    raw = os.environ.get("AUTO_DEEP_CHECKPOINT_DIR", "").strip()
    candidates = []
    if raw:
        candidates.append(Path(raw))
    candidates.extend(
        [
            Path("/var/lib/eurostat-deep"),
            Path("/app/.cache/eurostat-deep"),
            Path(__file__).resolve().parents[1] / ".cache" / "eurostat-deep",
            Path("/tmp/eurostat-deep"),
        ]
    )
    for p in candidates:
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except OSError:
            continue
    return Path("/tmp")


def _load_mod():
    import importlib.util

    path = Path("/app/scripts/load-world-eurostat.py")
    if not path.exists():
        path = Path(__file__).resolve().with_name("load-world-eurostat.py")
    spec = importlib.util.spec_from_file_location("load_world_eurostat", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _read_set(path: Path) -> set[str]:
    if not path.exists():
        return set()
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip().lower()
        if s and not s.startswith("#"):
            out.add(s)
    return out


def _append_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line.rstrip() + "\n")
        fh.flush()
        os.fsync(fh.fileno())


async def _dataset_ids() -> list[str]:
    only = os.environ.get("AUTO_DEEP_ONLY", "").strip()
    if only:
        return [x.strip().lower() for x in only.split(",") if x.strip()]
    async with async_session() as db:
        rows = (
            await db.execute(
                select(WorldIndicator.dataset_id)
                .where(WorldIndicator.provider == "eurostat")
                .distinct()
            )
        ).all()
    ids = sorted({(r[0] or "").lower() for r in rows if r[0]})
    offset = os.environ.get("AUTO_DEEP_OFFSET", "").strip()
    if offset:
        ids = ids[int(offset) :]
    limit = os.environ.get("AUTO_DEEP_LIMIT", "").strip()
    if limit:
        ids = ids[: int(limit)]
    return ids


async def main() -> int:
    # Avoid competing with uvicorn memory: sequential deep fetch (workers inside parser)
    os.environ.setdefault("AUTO_DEEP_WORKERS", "2")

    ckpt = _checkpoint_dir()
    done_path = ckpt / "done.txt"
    fail_path = ckpt / "failed.txt"
    done = _read_set(done_path)
    previously_failed = _read_set(fail_path)
    log.info("checkpoint dir=%s done=%s failed=%s", ckpt, len(done), len(previously_failed))

    mod = _load_mod()
    await mod.ensure_countries(set(WORLD_COUNTRIES.keys()))
    async with async_session() as db:
        rows = (await db.execute(select(WorldCountry))).scalars().all()
        country_ids = {c.code: c.id for c in rows}
        country_names = {c.code: c.name_ru for c in rows}
        for geo, meta in WORLD_COUNTRIES.items():
            slug = meta[0]
            for c in rows:
                if c.slug == slug:
                    country_ids.setdefault(geo, c.id)
                    country_names.setdefault(geo, c.name_ru)

    all_ids = await _dataset_ids()
    dataset_ids = [ds for ds in all_ids if ds not in done]
    log.info(
        "datasets to process: %s (skipped_done=%s of listed=%s)",
        len(dataset_ids),
        len(all_ids) - len(dataset_ids),
        len(all_ids),
    )

    t0 = time.time()
    total_ind = total_pts = 0
    ok = fail = 0

    for i, ds in enumerate(dataset_ids, 1):
        try:
            results = fetch_deep_slices(ds)
            for one in results:
                missing = set(one.series_by_geo) - set(country_ids)
                if missing:
                    extra = await mod.ensure_countries(missing)
                    country_ids.update(extra)
                    for g in missing:
                        country_names[g] = WORLD_COUNTRIES.get(g, ("", g, g, "", 0))[1]
                n_ind, n_pts = await mod.persist_result(one, country_ids, country_names)
                total_ind += n_ind
                total_pts += n_pts
            _append_line(done_path, ds)
            done.add(ds)
            ok += 1
        except Exception as exc:  # noqa: BLE001
            log.warning("FETCH FAIL %s: %s", ds, exc)
            _append_line(fail_path, f"{ds}\t{exc}")
            fail += 1
            # still mark done so we don't infinite-loop the same brick
            _append_line(done_path, ds)
            done.add(ds)

        if i % 10 == 0 or i == len(dataset_ids):
            log.info(
                "progress %s/%s ok=%s fail=%s ind=%s pts=%s elapsed=%.0fs",
                i,
                len(dataset_ids),
                ok,
                fail,
                total_ind,
                total_pts,
                time.time() - t0,
            )

    try:
        await bump_namespaces("world", "ssr-world")
    except Exception as exc:  # noqa: BLE001
        log.warning("cache bump failed: %s", exc)

    log.info(
        "DONE in %.1fs | ok=%d fail=%d indicators upserted=%d points touched=%d | fail_log=%s",
        time.time() - t0,
        ok,
        fail,
        total_ind,
        total_pts,
        fail_path,
    )
    return 0 if fail == 0 else 0  # never fail the job hard — fails are logged


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

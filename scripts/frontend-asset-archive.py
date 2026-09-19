#!/usr/bin/env python3
"""Publish immutable Vite assets before container replacement; retain three releases.

Only hashed assets enter the archive. HTML, fixed-name scripts and source maps
are never served from it. Each file and release manifest is published by rename
on the same filesystem; pruning runs only after deploy acceptance (or rollback).
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

HASHED_ASSET = re.compile(r"^.+-[A-Za-z0-9_-]{8}\.(?:js|css|woff2?|ttf|otf|svg|png|jpe?g|webp|gif|avif|ico)$")


def atomic_write(path: Path, content: bytes) -> None:
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
        temporary = Path(tmp.name)
        try:
            tmp.write(content)
            tmp.flush()
            os.fsync(tmp.fileno())
            temporary.chmod(0o644)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def publish(source: Path, archive: Path) -> str:
    index = (source / "index.html").read_bytes()
    release = hashlib.sha256(index).hexdigest()
    files = sorted(p for p in (source / "assets").iterdir() if p.is_file() and HASHED_ASSET.fullmatch(p.name))
    if not files:
        raise ValueError("Build contains no hashed assets")
    names = []
    for source_file in files:
        if source_file.is_symlink():
            raise ValueError(f"Asset must not be a symlink: {source_file.name}")
        target = archive / "assets" / source_file.name
        content = source_file.read_bytes()
        if target.exists():
            if target.read_bytes() != content:
                raise ValueError(f"Immutable asset collision: {source_file.name}")
        else:
            atomic_write(target, content)
        names.append(source_file.name)
    atomic_write(archive / "releases" / f"{release}.json", json.dumps(names).encode())
    return release


def prune(archive: Path, keep: int) -> None:
    if keep < 2:
        raise ValueError("Keep at least current and previous release")
    manifests = sorted((archive / "releases").glob("*.json"), key=lambda p: p.stat().st_mtime_ns, reverse=True)
    retained = set()
    for manifest in manifests[:keep]:
        retained.update(json.loads(manifest.read_text()))
    for asset in (archive / "assets").iterdir():
        if asset.is_file() and asset.name not in retained:
            asset.unlink()
    for manifest in manifests[keep:]:
        manifest.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("publish", "prune"))
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--keep", type=int, default=3)
    args = parser.parse_args()
    for name in ("assets", "releases"):
        (args.archive / name).mkdir(parents=True, exist_ok=True, mode=0o755)
    with (args.archive / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.command == "publish":
            if args.source is None:
                parser.error("publish requires --source")
            print(publish(args.source, args.archive))
        else:
            prune(args.archive, args.keep)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Фикстуры «после» для perf-serve.mjs (круг 12, SPEED2): те же записи боевого, но в новой форме.

Исходные записи (`--cache`, снимки SSR `--snap`) сняты с боевого до правок. Скрипт строит из них то, что отдаёт новый
backend, без обращения к боевому:
  * каталог страны `?slim=1` из записанного полного ответа (`slim_country_payload`);
  * WebP-варианты записанных OG-карточек (`?fmt=webp&w=720|1080|1200`, `png_to_webp`);
  * снимки SSR: `<picture>` с WebP (порядок источников как в `_responsive_charts`), без preload картинки и без
    `fetchpriority=high` у неё.
Запуск: backend/.venv/bin/python scripts/dev/perf_after_fixtures.py --cache C --snap S --out-cache C2 --out-snap S2
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from bs4 import BeautifulSoup  # noqa: E402

from app.api.world import slim_country_payload  # noqa: E402
from app.services import seo_renderer as r  # noqa: E402
from app.services.og_webp import png_to_webp  # noqa: E402


def key_of(name: str) -> str:
    stem = name[:-5]
    return base64.urlsafe_b64decode(stem + "=" * ((4 - len(stem) % 4) % 4)).decode()


def file_for(api_dir: Path, key: str) -> Path:
    return api_dir / (base64.urlsafe_b64encode(key.encode()).decode().rstrip("=")[:180] + ".json")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--snap", required=True)
    ap.add_argument("--out-cache", required=True)
    ap.add_argument("--out-snap", required=True)
    a = ap.parse_args()
    src, dst = Path(a.cache), Path(a.out_cache)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    api = dst / "api"
    made = []
    for f in sorted((src / "api").iterdir()):
        key = key_of(f.name)
        loc, method, target = key.split("|", 2)
        rec = json.loads(f.read_text())
        body = base64.b64decode(rec["body"])
        if re.fullmatch(r"/api/v1/world/countries/[a-z-]+", target) and rec["status"] == 200:
            slim = json.dumps(slim_country_payload(json.loads(body)), ensure_ascii=False, separators=(",", ":"))
            new = dict(rec, body=base64.b64encode(slim.encode()).decode())
            file_for(api, f"{loc}|{method}|{target}?slim=1").write_text(json.dumps(new))
            made.append((target + "?slim=1", len(body), len(slim)))
        if target.startswith("/og/") and ".png" in target and rec["status"] == 200 and len(body) > 50_000:
            portrait = "portrait=1" in target
            widths = (720, 1080) if portrait else (1200,)
            for w in widths:
                webp = png_to_webp(body, w)
                new = dict(rec, type="image/webp", body=base64.b64encode(webp).decode())
                file_for(api, f"{loc}|{method}|{target}&fmt=webp&w={w}" if "?" in target else f"{loc}|{method}|{target}?fmt=webp&w={w}").write_text(json.dumps(new))
                made.append((f"{target} webp {w}", len(body), len(webp)))
    # снимки SSR
    out_snap = Path(a.out_snap)
    if out_snap.exists():
        shutil.rmtree(out_snap)
    shutil.copytree(a.snap, out_snap)
    for html_file in out_snap.rglob("*.html"):
        html = html_file.read_text(encoding="utf8")
        if 'class="seo-chart"' not in html:
            continue
        html = re.sub(r'^\s*<link[^>]+rel="preload"[^>]+as="image"[^>]*>\s*$', "", html, flags=re.M)
        soup = BeautifulSoup(html, "html.parser")
        for picture in soup.select(".seo-chart picture"):
            img = picture.find("img")
            for source in picture.find_all("source"):
                source.decompose()
            picture.unwrap()
            img.attrs.pop("fetchpriority", None)
        body, _ = r._responsive_charts(str(soup))
        html_file.write_text(body, encoding="utf8")
        made.append((str(html_file.relative_to(out_snap)), 0, 0))
    for item in made:
        print(item)


if __name__ == "__main__":
    main()

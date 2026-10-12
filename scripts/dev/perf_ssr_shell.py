#!/usr/bin/env python3
"""Кусочки шапки SSR-страницы из собранного frontend/dist/index.html.

Те же функции, что в backend/app/services/seo_renderer.py (get_app_assets +
_nonblocking_stylesheets + _split_early_head_links + _css_preload), без HTTP и БД.
Нужен perf-serve.mjs: подставляет актуальную сборку в снимок боевой SSR-страницы.
Запуск: backend/.venv/bin/python scripts/dev/perf_ssr_shell.py frontend/dist/index.html
Печатает JSON: {plain: {...}, lcp: {...}} (lcp — вариант страницы с предзагрузкой картинки).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from bs4 import BeautifulSoup  # noqa: E402

from app.services import seo_renderer as r  # noqa: E402


def shell_parts(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for link in soup.find_all("link"):
        rel = {x.lower() for x in (link.get("rel") or [])}
        if rel & {"stylesheet", "modulepreload", "preconnect", "icon", "shortcut icon", "manifest", "apple-touch-icon"} or (
            "preload" in rel and link.get("as") == "font"
        ):
            links.append(str(link))
    head_links = "\n".join(r._sort_head_links(links))
    scripts = "\n".join(
        str(s) for s in soup.find_all("script") if s.get("src") and s.get("type") == "module"
    )
    out = {}
    for name, lcp in (("plain", False), ("lcp", True)):
        hl = head_links
        bs = scripts
        if lcp:
            hl = r._deprioritize_modulepreload(hl)
            bs = r._low_priority_module_scripts(bs)
        early, late = r._split_early_head_links(r._nonblocking_stylesheets(hl), prioritize_modules=not lcp)
        out[name] = {
            "css_preload": r._css_preload(head_links),
            "head_early": early,
            "head_late": late,
            "body_scripts": bs,
        }
    return out


if __name__ == "__main__":
    print(json.dumps(shell_parts(Path(sys.argv[1]).read_text(encoding="utf8")), ensure_ascii=False))

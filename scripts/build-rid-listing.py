#!/usr/bin/env python3
"""
Сборка листинга исходного кода для подачи заявки на регистрацию
программы для ЭВМ (РИД, Роспатент / ФИПС).

Стратегия:
  - Включаем только «обвязку» (entry points, модели данных, утилиты, UI shells,
    конфиги, реестры стратегий), которая регистрирует систему как «программу
    для ЭВМ» в формальном виде.
  - Полностью исключаем ядро (парсеры источников, forecast-модели,
    calculation engine, derived ops, SEO renderer, ETL-таски, аналитику) —
    это ноу-хау, которое мы оставляем за рамками РИД, чтобы иметь возможность
    переиспользовать алгоритмы в других продуктах.

Запуск:
  python3 scripts/build-rid-listing.py
Выход:
  RID_listing.txt — текстовая версия с шапками «Файл X» и footer «N of M»
  RID_listing.pdf — PDF-версия, моноширинный шрифт, A4
"""
from __future__ import annotations
from pathlib import Path
from fpdf import FPDF
from fpdf.enums import XPos, YPos

ROOT = Path(__file__).resolve().parent.parent
FONT_TTF = "/System/Library/Fonts/SFNSMono.ttf"

# Безопасный листинг: обвязка + UI shells + конфиги. Без ноу-хау.
FILES = [
    # Backend bootstrap + infra
    "backend/app/main.py",
    "backend/app/config.py",
    "backend/app/database.py",
    "backend/app/models.py",
    "backend/app/schemas.py",
    "backend/app/api/system.py",
    "backend/app/api/router.py",
    "backend/app/api/indicators.py",
    "backend/app/api/sitemap.py",
    # Лёгкий слой прогнозов (registry + одна простая стратегия — без алгоритмов)
    "backend/app/services/forecast_strategies/__init__.py",
    "backend/app/services/forecast_strategies/registry.py",
    "backend/app/services/forecast_strategies/approved.py",
    # Frontend bootstrap + infra
    "frontend/src/main.jsx",
    "frontend/src/App.jsx",
    "frontend/src/lib/format.js",
    "frontend/src/lib/utm.js",
    "frontend/src/lib/cleanUrl.js",
    "frontend/src/lib/categories.js",
    # UI components / pages (без алгоритмов)
    "frontend/src/components/Navbar.jsx",
    "frontend/src/components/Footer.jsx",
    "frontend/src/components/Skeleton.jsx",
    "frontend/src/components/ErrorBoundary.jsx",
    "frontend/src/components/IndicatorTile.jsx",
    "frontend/src/components/DataTable.jsx",
    "frontend/src/components/ForecastTable.jsx",
    "frontend/src/pages/Dashboard.jsx",
    "frontend/src/pages/CategoryPage.jsx",
    # Infrastructure
    "Caddyfile",
    "docker-compose.yml",
    "frontend/nginx.conf",
    "backend/Dockerfile",
    "frontend/Dockerfile",
]

FONT_SIZE = 8.5
LINE_HEIGHT = 3.6  # mm
LEFT_MARGIN = 12   # mm
TOP_MARGIN = 10    # mm
BOTTOM_MARGIN = 12 # mm
MAX_CHARS = 92     # переносим длинные строки

def wrap_line(s: str, width: int = MAX_CHARS) -> list[str]:
    if len(s) <= width:
        return [s]
    out = []
    i = 0
    while i < len(s):
        out.append(s[i:i + width])
        i += width
    return out

def build_text_lines() -> list[str]:
    out: list[str] = []
    for rel in FILES:
        path = ROOT / rel
        if not path.is_file():
            print(f"  MISS {rel}")
            continue
        out.append(f"Файл {rel}")
        raw = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for ln in raw:
            ln = ln.rstrip().expandtabs(4)
            for piece in wrap_line(ln):
                out.append(piece)
        out.append("")  # пустая строка между файлами
    return out

class Listing(FPDF):
    def __init__(self) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.add_font("Mono", "", FONT_TTF)
        self.set_auto_page_break(auto=False)
        self.set_margins(LEFT_MARGIN, TOP_MARGIN, LEFT_MARGIN)

def render_pdf(lines: list[str], out_pdf: Path) -> int:
    pdf = Listing()
    pdf.set_font("Mono", size=FONT_SIZE)
    page_h = pdf.h
    usable_h = page_h - TOP_MARGIN - BOTTOM_MARGIN - 8  # footer reserve
    rows_per_page = int(usable_h // LINE_HEIGHT)

    # пагинация: сначала разрежем lines на страницы
    pages: list[list[str]] = []
    chunk: list[str] = []
    for ln in lines:
        chunk.append(ln)
        if len(chunk) >= rows_per_page:
            pages.append(chunk)
            chunk = []
    if chunk:
        pages.append(chunk)

    total = len(pages)
    for idx, page_lines in enumerate(pages, start=1):
        pdf.add_page()
        pdf.set_xy(LEFT_MARGIN, TOP_MARGIN)
        for ln in page_lines:
            pdf.set_x(LEFT_MARGIN)
            pdf.cell(0, LINE_HEIGHT, ln, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        # footer
        pdf.set_xy(LEFT_MARGIN, page_h - BOTTOM_MARGIN + 2)
        pdf.cell(0, 4, f"-- {idx} of {total} --", align="C")

    pdf.output(str(out_pdf))
    return total

def render_txt(lines: list[str], out_txt: Path, rows_per_page: int = 50) -> int:
    pages = []
    chunk = []
    for ln in lines:
        chunk.append(ln)
        if len(chunk) >= rows_per_page:
            pages.append(chunk)
            chunk = []
    if chunk:
        pages.append(chunk)
    total = len(pages)

    with out_txt.open("w", encoding="utf-8") as f:
        for idx, page_lines in enumerate(pages, start=1):
            for ln in page_lines:
                f.write(ln + "\n")
            f.write(f"\n-- {idx} of {total} --\n\n")
    return total

def main() -> None:
    lines = build_text_lines()
    out_txt = ROOT / "RID_listing.txt"
    out_pdf = ROOT / "RID_listing.pdf"
    pages_txt = render_txt(lines, out_txt)
    pages_pdf = render_pdf(lines, out_pdf)
    print(f"OK: {out_txt.relative_to(ROOT)} ({pages_txt} pages, txt)")
    print(f"OK: {out_pdf.relative_to(ROOT)} ({pages_pdf} pages, pdf)")
    print(f"Files included: {len(FILES)}; total text lines: {len(lines)}")

if __name__ == "__main__":
    main()

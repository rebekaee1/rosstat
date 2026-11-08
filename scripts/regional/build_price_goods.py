#!/usr/bin/env python3
"""Справочник всех позиций ЕМИСС 31448 с опубликованными ценами → JSON-артефакт.

Вход: каталог помесячных ответов dataGrid.do (``YYYYMM.json.gz``, все позиции ×
все территории, как их запрашивает ``emiss_regional_parser``) и справочник
позиций измерения 58273 (``oid → название``, снят со страницы витрины).
Выход: ``backend/app/data/regional/emiss_price_goods.json`` — позиции, у которых
есть хотя бы одна цена, с кодом ряда, названием, единицей и границами истории.

Код ряда — ``ceni-`` + транслит названия; позиции, отобранные вручную
(``PRICE_GOODS`` в ``app/data/emiss_price_goods.py``), сохраняют свои коды и
названия и в артефакт не входят. Повторный запуск детерминирован.

    python3 scripts/regional/build_price_goods.py SCAN_DIR GOODS_JSON
    python3 scripts/regional/build_price_goods.py SCAN_DIR GOODS_JSON --points OUT.csv.gz

С ``--points`` дополнительно пишет все точки (топливо и товары) в CSV для
``backend/load_regional_monthly.py`` — тем же разбором, что у парсера.
"""

from __future__ import annotations

import gzip
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.data.emiss_price_goods import PRICE_FUELS_OIDS, PRICE_GOODS  # noqa: E402

OUT = ROOT / "backend/app/data/regional/emiss_price_goods.json"

_TR = dict(zip(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
    ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t",
     "u", "f", "h", "c", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"],
))


def translit(text: str) -> str:
    out = "".join(_TR.get(ch, ch) for ch in text.casefold())
    return re.sub(r"[^a-z0-9]+", "-", out).strip("-")


def split_title(title: str) -> tuple[str, str]:
    title = re.sub(r"\s+", " ", html.unescape(title)).strip()
    if "," in title:
        label, per = title.rsplit(",", 1)
        return label.strip(), per.strip()
    return title, ""


def main(scan_dir: Path, goods_path: Path) -> None:
    goods = json.loads(goods_path.read_text(encoding="utf-8"))
    curated = {g.oid for g in PRICE_GOODS} | set(PRICE_FUELS_OIDS)
    first: dict[str, int] = {}
    last: dict[str, int] = {}
    territories: dict[str, set[str]] = {}
    for path in sorted(scan_dir.glob("*.json.gz")):
        period = int(path.name[:6])
        payload = json.loads(gzip.open(path).read())
        for row in payload.get("results", []):
            territory = str(row.get("dim57831") or "")
            for key, raw in row.items():
                if "_d" not in key or raw in (None, "", "-"):
                    continue
                oid = key[3:].split("_", 1)[0]
                if oid not in goods:
                    continue
                first[oid] = min(first.get(oid, period), period)
                last[oid] = max(last.get(oid, period), period)
                territories.setdefault(oid, set()).add(territory)

    used_codes = {g.code for g in PRICE_GOODS}
    rows = []
    for oid in sorted(first, key=lambda o: (split_title(goods[o])[0].casefold(), o)):
        if oid in curated:
            continue
        label, per = split_title(goods[oid])
        base = "ceni-" + translit(label)[:60].strip("-")
        code = base if base not in used_codes else f"{base}-{oid}"
        used_codes.add(code)
        rows.append({
            "oid": oid, "code": code, "label": label[:1].lower() + label[1:] if label[1:2].islower() else label, "per": per,
            "first": first[oid], "last": last[oid], "territories": len(territories[oid]),
        })
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(rows)} позиций (вручную отобрано {len(PRICE_GOODS)}) → {OUT.relative_to(ROOT)}")
    refresh_indicator_artifact()


def refresh_indicator_artifact() -> None:
    """Метаданные регионального каталога: строки позиций витрины заменяются целиком."""
    import importlib

    import app.data.emiss_price_goods as goods_module

    importlib.reload(goods_module)
    path = ROOT / "backend/app/data/regional/indicators.json"
    current = json.loads(path.read_text(encoding="utf-8"))
    goods_codes = {g.code for g in goods_module.ALL_PRICE_GOODS}
    kept = [row for row in current if not str(row.get("table_code", "")).startswith("22.m")
            and row["code"] not in goods_codes]
    rows = kept + goods_module.artifact_rows()
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"indicators.json: {len(kept)} прежних + {len(rows) - len(kept)} позиций цен")


def write_points(scan_dir: Path, out: Path) -> None:
    import importlib

    import app.data.emiss_price_goods as goods_module
    import app.services.emiss_regional_parser as parser

    importlib.reload(goods_module)
    importlib.reload(parser)
    dimnames = parser.load_dimnames()
    total = 0
    with gzip.open(out, "wt", encoding="utf-8") as fh:
        fh.write("indicator_code;region_slug;period;value\n")
        for path in sorted(scan_dir.glob("*.json.gz")):
            period = int(path.name[:6])
            payload = json.loads(gzip.open(path).read())
            points = parser.parse_grid_response(
                payload, year=period // 100, month=period % 100, dimnames=dimnames, fuels=parser.PRICE_SERIES,
            )
            for code, slug, per, value in points:
                fh.write(f"{code};{slug};{per};{value}\n")
            total += len(points)
    print(f"точек: {total} → {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
    if "--points" in sys.argv:
        write_points(Path(sys.argv[1]), Path(sys.argv[sys.argv.index("--points") + 1]))

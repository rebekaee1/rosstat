#!/usr/bin/env python3
"""Реестр растровых картинок: хватает ли пикселей файла на самый большой показ при нужной плотности (DPR).

Принцип владельца №9 (docs/design-system.md): никакого пикселя; растр ставится только в разрешении не ниже 2x
от размера показа (на телефонах и мелких картинках — 3x), иначе не ставится вовсе.

Что делает скрипт (из корня репозитория, зависимости: Pillow):
    python3 scripts/dev/check-raster-dpr.py            # таблица markdown; код 1, если есть нарушения
    python3 scripts/dev/check-raster-dpr.py --json     # то же, JSON

1. Обходит frontend/public/{brand,art,icons,planet}, читает размеры растров (png/webp/jpg).
2. Находит в frontend/src/** (кроме тестов) места показа: CSS `url(...)`, JSX `src=`/`srcSet=`, строки-пути
   в JS (в том числе шаблон `/art/quicklinks/${CATEGORY_ART[...]}-320.webp`, он раскрывается значениями карты).
3. Считает максимальный CSS-размер показа по CSS класса картинки (width / max-width: px, rem, vw при окне
   1920, min/max/clamp; проценты и calc не вычисляются) и по размеру `<Emblem size={N}>`. Где вычислить нельзя,
   берёт `max_display_px` из frontend/public/brand/manifest.json. Если вычисленное по CSS больше заявленного
   в манифесте, манифест занижает показ: это нарушение.
4. Сверяет `px >= показ x dpr` (dpr из манифеста: 2 для обычных, 3 для картинок на телефоне и мелких, меньше
   только у мягких фонов с отметкой `soft` и причиной). Файлы с `pending` ждут замены или удаления другой зоной
   и не валят код выхода, но в таблице они видны как «нет».
Планетные текстуры (WebGL) в манифест не входят: для них считается плотность на видимом полушарии шара.
Сторож для vitest: frontend/src/styles/no-lowres.test.js (читает тот же манифест).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
FE = ROOT / "frontend"
PUBLIC = FE / "public"
SRC = FE / "src"
MANIFEST = PUBLIC / "brand" / "manifest.json"
DIRS = ["brand", "art", "icons", "planet"]
EXTS = {".png", ".webp", ".jpg", ".jpeg"}
VW_REF = 1920  # окно, при котором считаются vw (ультрашироких экранов за пределом max-width нет)
PLANET_DIAMETER = 700  # CSS px: самый большой шар на десктопе (контейнер 1360, высота сцены до ~700)

# ───────────────────────── чтение исходников ─────────────────────────


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def src_files() -> list[Path]:
    out = []
    for p in sorted(SRC.rglob("*")):
        if not p.is_file() or p.suffix not in {".css", ".js", ".jsx"}:
            continue
        if ".test." in p.name or "/embed/" in str(p) or p.name.endswith(".generated.json"):
            continue
        out.append(p)
    return out


def css_rules(files: list[Path]) -> list[tuple[str, dict[str, str], Path]]:
    rules = []
    for f in files:
        if f.suffix != ".css":
            continue
        text = re.sub(r"/\*.*?\*/", "", read(f), flags=re.S)
        for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", text):
            sel = m.group(1).strip()
            if sel.startswith("@"):
                continue
            decls = {}
            for d in m.group(2).split(";"):
                if ":" in d:
                    k, v = d.split(":", 1)
                    decls[k.strip()] = v.strip()
            rules.append((sel, decls, f))
    return rules


# ───────────────────────── вычисление CSS-длин ─────────────────────────


def split_args(s: str) -> list[str]:
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return [a.strip() for a in out]


def ev(val: str) -> float | None:
    """Верхняя оценка длины в CSS px или None, если не вычисляется (%, calc, auto, var)."""
    v = val.strip().replace("!important", "").strip()
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)(px|rem|em|vw)?", v)
    if m:
        n = float(m.group(1))
        unit = m.group(2)
        if unit in (None, "px"):
            return n
        if unit in ("rem", "em"):
            return n * 16
        if unit == "vw":
            return n * VW_REF / 100
    m = re.fullmatch(r"(min|max|clamp)\((.*)\)", v, flags=re.S)
    if not m:
        return None
    fn, args = m.group(1), [ev(a) for a in split_args(m.group(2))]
    if fn == "min":
        known = [a for a in args if a is not None]
        return min(known) if known else None  # min(...) не больше любого известного аргумента
    if fn == "max":
        return max(args) if all(a is not None for a in args) else None
    lo, pref, hi = args
    if hi is None:
        return None
    top = hi if pref is None else min(hi, max(lo or 0, pref))
    return top


def class_width(classes: list[str], rules) -> tuple[float | None, str]:
    """Показ по CSS самого элемента: width/max-width правил, чей последний компонент селектора содержит класс."""
    best = None
    where = ""
    for sel, decls, f in rules:
        for part in sel.split(","):
            last = re.split(r"[\s>+~]+", part.strip())[-1]
            if not any(re.search(rf"\.{re.escape(c)}(?![\w-])", last) for c in classes):
                continue
            vals = [ev(decls[k]) for k in ("width", "max-width") if k in decls]
            vals = [x for x in vals if x is not None]
            if vals:
                w = min(vals)
                if best is None or w > best:
                    best, where = w, f"{f.name}: {part.strip()}"
    return best, where


# ───────────────────────── поиск мест показа ─────────────────────────


def category_art_values() -> list[str]:
    f = SRC / "components" / "CategoryBlock.jsx"
    if not f.exists():
        return []
    m = re.search(r"const CATEGORY_ART = \{(.*?)\};", read(f), flags=re.S)
    return sorted(set(re.findall(r":\s*'([a-z0-9-]+)'", m.group(1)))) if m else []


def emblem_size_max(files: list[Path]) -> float | None:
    sizes = []
    for f in files:
        if f.suffix != ".jsx":
            continue
        for m in re.finditer(r"<Emblem\b([^>]*)>", read(f)):
            if 'variant="photo"' in m.group(1):
                s = re.search(r"size=\{(\d+)\}", m.group(1))
                sizes.append(float(s.group(1)) if s else 96.0)
    return max(sizes) if sizes else None


def find_usages(files: list[Path], rasters: list[str]) -> dict[str, list[dict]]:
    """raster (путь от public/) -> [{file, kind, classes}]"""
    slugs = category_art_values()
    usage: dict[str, list[dict]] = {r: [] for r in rasters}
    for f in files:
        text = read(f)
        rel = str(f.relative_to(SRC))
        for r in rasters:
            needle = "/" + r
            cands = [needle]
            if r.startswith("art/quicklinks/"):
                base = r[len("art/quicklinks/"):]
                for suffix in ("-320.webp", "-640.webp"):
                    if base.endswith(suffix) and base[: -len(suffix)] in slugs:
                        cands.append(f"/art/quicklinks/${{CATEGORY_ART[category.slug]}}{suffix}")
            for needle in cands:
                start = 0
                while (i := text.find(needle, start)) != -1:
                    start = i + len(needle)
                    classes: list[str] = []
                    kind = "css" if f.suffix == ".css" else "jsx/js"
                    if f.suffix == ".css":
                        head = text[:i].rsplit("{", 1)[0].rsplit("}", 1)[-1]
                        sel = re.sub(r"/\*.*?\*/", "", head, flags=re.S).strip()
                        classes = re.findall(r"\.([\w-]+)", sel.split(",")[0].split()[-1] if sel else "")
                    else:
                        a, b = text.rfind("<", 0, i), text.find(">", i)
                        tag = text[a:b] if a != -1 and b != -1 else ""
                        m = re.search(r'className="([^"]+)"', tag)
                        classes = m.group(1).split() if m else []
                        if "<Emblem" in text[max(0, i - 400):i] or f.name == "Emblem.jsx":
                            kind = "emblem"
                    usage[r].append({"file": rel, "kind": kind, "classes": classes})
    return usage


# ───────────────────────── основная логика ─────────────────────────


def main() -> int:
    as_json = "--json" in sys.argv
    manifest = json.loads(read(MANIFEST)) if MANIFEST.exists() else {"files": {}}
    entries = manifest.get("files", {})
    rasters: dict[str, tuple[int, int]] = {}
    for d in DIRS:
        for p in sorted((PUBLIC / d).rglob("*")):
            if p.is_file() and p.suffix.lower() in EXTS:
                with Image.open(p) as im:
                    rasters[str(p.relative_to(PUBLIC))] = im.size
    files = src_files()
    rules = css_rules(files)
    usage = find_usages(files, list(rasters))
    emblem = emblem_size_max(files)

    rows, failures = [], []
    for r, (w, h) in rasters.items():
        side = max(w, h) if r.startswith("planet/") else w
        used = bool(usage[r])
        e = entries.get(r)
        note = []
        if r.startswith("planet/"):
            need = PLANET_DIAMETER * 2
            have = side // 2  # видимое полушарие занимает половину ширины развёртки
            ok = "да" if have >= need else "вне стража (WebGL, зона G)"
            rows.append({"file": r, "px": w, "display": PLANET_DIAMETER, "dpr": 2, "need": need,
                         "src": "шар (WebGL)", "ok": ok, "used": used})
            continue
        if e is None:
            rows.append({"file": r, "px": w, "display": None, "dpr": None, "need": None, "src": "-", "ok": "нет: нет в манифесте", "used": used})
            failures.append(f"{r}: нет в манифесте")
            continue
        if e.get("used") is False and used:
            failures.append(f"{r}: в манифесте used=false, но подключён в src")
        if e.get("used") is True and not used and not e.get("external") and not e.get("vector") and not e.get("pending"):
            failures.append(f"{r}: в манифесте used=true, но в src не найден (если файл читает ОС или index.html, поставь external=true)")
        if e.get("used") is False and not used:
            rows.append({"file": r, "px": w, "display": None, "dpr": None, "need": None, "src": "-", "ok": "не показывается", "used": False})
            continue
        auto, auto_src = None, ""
        for u in usage[r]:
            if u["kind"] == "emblem" and emblem:
                cand, s = emblem, "Emblem size"
            elif u["classes"]:
                cand, s = class_width(u["classes"], rules)
            else:
                cand, s = None, ""
            if cand is not None and (auto is None or cand > auto):
                auto, auto_src = cand, s
        declared = e.get("max_display_px")
        shown = auto if auto is not None else declared
        src_name = f"css ({auto_src})" if auto is not None else "манифест"
        problem = None
        if declared is not None and auto is not None and auto > declared + 0.5:
            problem = f"манифест занижает показ: по CSS {auto:.0f} > заявлено {declared}"
        dpr = e.get("dpr", 2)
        need = (shown or 0) * dpr
        if e.get("vector"):
            ok = "вектор"
        elif problem:
            ok = "нет: " + problem
        elif shown is None:
            ok = "нет: показ неизвестен"
        elif w + 1e-6 >= need - 0.5:
            ok = "да (мягкий фон)" if e.get("soft") else "да"
        else:
            ok = "нет"
        if ok.startswith("нет"):
            if e.get("pending"):
                ok += f" (ждёт: {e['pending']})"
            else:
                failures.append(f"{r}: {ok}; нужно {need:.0f}, есть {w}")
        rows.append({"file": r, "px": w, "display": shown, "dpr": dpr, "need": need, "src": src_name, "ok": ok, "used": used})

    for k in entries:
        if k not in rasters and not entries[k].get("vector"):
            failures.append(f"{k}: в манифесте есть, файла нет")

    if as_json:
        print(json.dumps({"rows": rows, "failures": failures}, ensure_ascii=False, indent=1))
    else:
        print("| файл | px | макс. показ css px | dpr | нужно px | ×dpr ok? | источник показа |")
        print("|---|---|---|---|---|---|---|")
        for x in rows:
            disp = "-" if x["display"] is None else f"{x['display']:.0f}"
            need = "-" if x.get("need") is None else f"{x['need']:.0f}"
            print(f"| {x['file']} | {x['px']} | {disp} | {x['dpr'] if x['dpr'] is not None else '-'} | {need} | {x['ok']} | {x['src']} |")
        print()
        print(f"Растров: {len(rows)}; нарушений без отметки pending: {len(failures)}")
        for f in failures:
            print("  -", f)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

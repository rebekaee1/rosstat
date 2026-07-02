#!/usr/bin/env python3
"""Генерация компактной SVG-карты субъектов РФ для фронтенда.

Источник геометрии: https://github.com/imsha/russia_geojson_regions_2021
(`ru.json`, 84 субъекта, включая Крым; Севастополь добавляется маркером).

Пайплайн:
1. GeoJSON → фичи, имя региона → slug через regions_registry.resolve_region.
2. Долгота < 0 сдвигается на +360 (Чукотка не рвётся на 180-м меридиане).
3. Проекция Альберса для России (стандартные параллели 52°/64°, λ0=100°E).
4. Упрощение Дугласа-Пекера + отбрасывание мелких колец (острова-пиксели).
5. Результат — frontend/src/lib/regionsMap.json:
   { viewBox, regions: [{slug, path}], markers: [{slug, cx, cy}] }
   Маркеры — города федерального значения (Москва, СПб, Севастополь):
   полигоны крошечные, кликать удобнее по кружку.

Запуск:  python3 scripts/regional/build_map_paths.py
Файл коммитится в репозиторий; перегенерация нужна только при смене геометрии.
"""

from __future__ import annotations

import json
import math
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from regions_registry import resolve_region  # noqa: E402

# Сокращения источника → канонические имена registry («АО» в датасете — и
# автономный округ, и автономная область: мапим явно, без эвристик).
NAME_OVERRIDES = {
    "Ненецкий АО": "Ненецкий автономный округ",
    "Ханты-Мансийский АО — Югра": "Ханты-Мансийский автономный округ",
    "Чукотский АО": "Чукотский автономный округ",
    "Ямало-Ненецкий АО": "Ямало-Ненецкий автономный округ",
    "Еврейская АО": "Еврейская автономная область",
}

SRC_URL = "https://raw.githubusercontent.com/imsha/russia_geojson_regions_2021/main/ru.json"
CACHE = Path("/tmp/ru_regions.json")
OUT = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "regionsMap.json"

# Альберс для РФ
LAT1, LAT2 = math.radians(52), math.radians(64)
LON0, LAT0 = math.radians(100), math.radians(56)

_n = (math.sin(LAT1) + math.sin(LAT2)) / 2
_C = math.cos(LAT1) ** 2 + 2 * _n * math.sin(LAT1)
_rho0 = math.sqrt(_C - 2 * _n * math.sin(LAT0)) / _n


def project(lon: float, lat: float) -> tuple[float, float]:
    if lon < 0:
        lon += 360
    lam, phi = math.radians(lon), math.radians(lat)
    rho = math.sqrt(max(_C - 2 * _n * math.sin(phi), 0)) / _n
    theta = _n * (lam - LON0)
    x = rho * math.sin(theta)
    y = _rho0 - rho * math.cos(theta)
    return x, -y  # SVG: y вниз


def rdp(points: list[tuple[float, float]], eps: float) -> list[tuple[float, float]]:
    """Douglas-Peucker (итеративный, чтобы не упереться в recursion limit)."""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay = points[a]
        bx, by = points[b]
        dx, dy = bx - ax, by - ay
        norm = math.hypot(dx, dy)
        degenerate = norm < 1e-9  # замкнутое кольцо: A == B, меряем до точки A
        dmax, imax = 0.0, -1
        for i in range(a + 1, b):
            px, py = points[i]
            if degenerate:
                d = math.hypot(px - ax, py - ay)
            else:
                d = abs(dx * (ay - py) - dy * (ax - px)) / norm
            if d > dmax:
                dmax, imax = d, i
        if dmax > eps and imax > 0:
            keep[imax] = True
            stack.append((a, imax))
            stack.append((imax, b))
    return [p for p, k in zip(points, keep) if k]


def ring_area(points: list[tuple[float, float]]) -> float:
    s = 0.0
    for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]):
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


def load_geojson() -> dict:
    if not CACHE.exists():
        print(f"downloading {SRC_URL}")
        urllib.request.urlretrieve(SRC_URL, CACHE)
    return json.loads(CACHE.read_text())


def main() -> None:
    gj = load_geojson()

    # Первый проход: собрать все спроецированные кольца, найти bbox.
    raw: list[tuple[str, list[list[tuple[float, float]]]]] = []
    for feat in gj["features"]:
        name = feat["properties"]["name"]
        slug, score = resolve_region(NAME_OVERRIDES.get(name, name))
        if not slug:
            print(f"!! регион не распознан: {name}", file=sys.stderr)
            continue
        geom = feat["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        rings = []
        for poly in polys:
            outer = poly[0]  # дырки игнорируем: на карте-миниатюре не читаются
            rings.append([project(lon, lat) for lon, lat in outer])
        raw.append((slug, rings))

    xs = [x for _, rings in raw for ring in rings for x, _ in ring]
    ys = [y for _, rings in raw for ring in rings for _, y in ring]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    W = 1000.0
    scale = W / (maxx - minx)
    H = (maxy - miny) * scale

    eps = 1.1  # в экранных единицах (viewBox 1000 wide)
    min_ring_area = 3.0

    def tx(p: tuple[float, float]) -> tuple[float, float]:
        return ((p[0] - minx) * scale, (p[1] - miny) * scale)

    regions = []
    centroids: dict[str, tuple[float, float]] = {}
    for slug, rings in raw:
        parts = []
        best_ring, best_area = None, 0.0
        for ring in rings:
            pts = [tx(p) for p in ring]
            area = ring_area(pts)
            if area > best_area:
                best_area, best_ring = area, pts
            if area < min_ring_area:
                continue
            simplified = rdp(pts, eps)
            if len(simplified) < 4:
                continue
            d = "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in simplified) + "Z"
            parts.append(d)
        if not parts:
            continue
        if best_ring:
            cx = sum(x for x, _ in best_ring) / len(best_ring)
            cy = sum(y for _, y in best_ring) / len(best_ring)
            centroids[slug] = (round(cx, 1), round(cy, 1))
        regions.append({"slug": slug, "path": "".join(parts)})

    # Города федерального значения: кликабельные маркеры.
    markers = []
    for slug, anchor_slug, dx, dy in (
        ("moskva", "moskva", 0, 0),
        ("sankt-peterburg", "sankt-peterburg", 0, 0),
        # Севастополя нет в геометрии — ставим рядом с крымским центроидом
        ("sevastopol", "respublika-krym", -14, 8),
    ):
        base = centroids.get(anchor_slug)
        if base:
            markers.append({"slug": slug, "cx": base[0] + dx, "cy": base[1] + dy})

    out = {
        "viewBox": f"0 0 {W:.0f} {H:.0f}",
        "regions": regions,
        "markers": markers,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    size_kb = OUT.stat().st_size / 1024
    print(f"OK: {len(regions)} регионов, {len(markers)} маркеров, {size_kb:.0f} KB → {OUT}")


if __name__ == "__main__":
    main()

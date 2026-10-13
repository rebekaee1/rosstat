#!/usr/bin/env python3
"""Доля различающихся пикселей между двумя кадрами: python3 scripts/dev/perf-shot-diff.py A.png B.png [порог 0..255, по умолчанию 8]."""
import sys

from PIL import Image, ImageChops

a, b = Image.open(sys.argv[1]).convert("RGB"), Image.open(sys.argv[2]).convert("RGB")
thr = int(sys.argv[3]) if len(sys.argv) > 3 else 8
if a.size != b.size:
    sys.exit(f"размеры разные: {a.size} и {b.size}")
d = ImageChops.difference(a, b).convert("L")
px = d.load()
w, h = d.size
bad = sum(1 for y in range(h) for x in range(w) if px[x, y] > thr)
print(f"различающихся пикселей: {bad} из {w * h} ({100 * bad / (w * h):.3f} %), максимум различия {max(d.getdata())}")

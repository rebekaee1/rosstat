#!/usr/bin/env python3
"""Контактный лист из кадров perf-film.mjs: python3 scripts/dev/perf-contact.py DIR OUT.png [cols]. Подпись — время кадра, мс."""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

d, out = Path(sys.argv[1]), sys.argv[2]
cols = int(sys.argv[3]) if len(sys.argv) > 3 else 6
files = sorted(d.glob("*.jpg"))
if not files:
    sys.exit("нет кадров")
w, h = 195, 422
rows = (len(files) + cols - 1) // cols
sheet = Image.new("RGB", (cols * w, rows * (h + 16)), "white")
dr = ImageDraw.Draw(sheet)
for i, f in enumerate(files):
    im = Image.open(f).convert("RGB").resize((w, h))
    x, y = (i % cols) * w, (i // cols) * (h + 16)
    sheet.paste(im, (x, y + 16))
    dr.text((x + 4, y + 2), f"{int(f.stem)} мс", fill="black")
sheet.save(out)
print(out, len(files))

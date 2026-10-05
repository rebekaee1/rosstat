#!/usr/bin/env python3
"""Рисует иконки веб-приложения (PWA) из знака бренда (frontend/public/favicon.svg).

Результат (коммитится как обычные статические файлы, скрипт нужен только для
пересборки):
  frontend/public/icons/icon-192.png            purpose "any"
  frontend/public/icons/icon-512.png            purpose "any"
  frontend/public/icons/icon-maskable-512.png   purpose "maskable" (знак внутри безопасной зоны 60%)
  frontend/public/apple-touch-icon.png          180x180 для iOS «На экран Домой»

Запуск: backend/.venv/bin/python scripts/build-pwa-icons.py  (нужен Pillow).
Знак (буква F и золотой квадрат) — те же контуры, что в favicon.svg (viewBox 48).
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1] / "frontend" / "public"
NAVY = (32, 42, 60, 255)      # #202A3C
PAPER = (238, 240, 244, 255)  # #EEF0F4
GOLD = (173, 138, 72, 255)    # #AD8A48

# Границы знака в координатах favicon.svg: x 12..39, y 5..38.
MARK_W, MARK_H = 27.0, 33.0
MARK_X0, MARK_Y0 = 12.0, 5.0
SS = 4  # суперсэмплинг для гладких кромок


def _quad(p0, p1, p2, steps=24):
    pts = []
    for i in range(1, steps + 1):
        t = i / steps
        pts.append((
            (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0],
            (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1],
        ))
    return pts


def _f_polygon():
    """M12 38V17Q12 5 25 5H38V13H26Q21 13 21 19V20H35V28H21V38Z"."""
    pts = [(12, 38), (12, 17)]
    pts += _quad((12, 17), (12, 5), (25, 5))
    pts += [(38, 5), (38, 13), (26, 13)]
    pts += _quad((26, 13), (21, 13), (21, 19))
    pts += [(21, 20), (35, 20), (35, 28), (21, 28), (21, 38)]
    return pts


def render(size: int, mark_fraction: float) -> Image.Image:
    """Квадрат на всю площадь (углы скругляет ОС), знак высотой mark_fraction от стороны."""
    big = size * SS
    img = Image.new("RGBA", (big, big), NAVY)
    draw = ImageDraw.Draw(img)
    scale = big * mark_fraction / MARK_H
    ox = (big - MARK_W * scale) / 2 - MARK_X0 * scale
    oy = (big - MARK_H * scale) / 2 - MARK_Y0 * scale

    def tx(p):
        return (ox + p[0] * scale, oy + p[1] * scale)

    draw.polygon([tx(p) for p in _f_polygon()], fill=PAPER)
    draw.rectangle([tx((33, 30)), tx((39, 38))], fill=GOLD)
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    (ROOT / "icons").mkdir(parents=True, exist_ok=True)
    render(192, 0.62).save(ROOT / "icons" / "icon-192.png", optimize=True)
    render(512, 0.62).save(ROOT / "icons" / "icon-512.png", optimize=True)
    # maskable: ОС может обрезать до круга диаметром 80% — знак должен жить в центральных ~60%.
    render(512, 0.52).save(ROOT / "icons" / "icon-maskable-512.png", optimize=True)
    render(180, 0.62).convert("RGB").save(ROOT / "apple-touch-icon.png", optimize=True)
    print("ok")


if __name__ == "__main__":
    main()

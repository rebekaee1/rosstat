#!/usr/bin/env python3
"""Расчёт контраста и различимости палитры карты мира (frontend/src/lib/worldMapColors.js).

Печатает для каждой ступени светлоту L*, цветность, ΔE2000 и контраст WCAG с океаном и сушей «нет данных»,
затем наименьшие шаги между соседними и любыми ступенями при нормальном зрении и трёх видах дальтонизма
(Machado 2009, тяжесть 1,0). Без аргументов читает шкалу из worldMapColors.js.
Запуск: python3 scripts/dev/world-map-palette-check.py [#hex ... семь цветов]
"""
import itertools
import pathlib
import re
import sys

import numpy as np

SRC = pathlib.Path(__file__).resolve().parents[2] / 'frontend/src/lib/worldMapColors.js'
M = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750], [0.0193339, 0.1191920, 0.9503041]])
WP = np.array([0.95047, 1, 1.08883])
CVD = {
    'protan': np.array([[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]]),
    'deutan': np.array([[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]]),
    'tritan': np.array([[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.303900]]),
}


def rgb(h): return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)]) / 255
def lin(c): return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
def delin(c): return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.clip(c, 0, None) ** (1 / 2.4) - 0.055)


def lab(c):
    xyz = M @ lin(c) / WP
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.array([116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])])


def de2000(l1, l2):
    L1, a1, b1 = l1
    L2, a2, b2 = l2
    cb = (np.hypot(a1, b1) + np.hypot(a2, b2)) / 2
    g = 0.5 * (1 - np.sqrt(cb ** 7 / (cb ** 7 + 25 ** 7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1, c2 = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1, h2 = np.degrees(np.arctan2(b1, a1p)) % 360, np.degrees(np.arctan2(b2, a2p)) % 360
    dh = h2 - h1
    if c1 * c2 == 0: dh = 0
    elif dh > 180: dh -= 360
    elif dh < -180: dh += 360
    dH = 2 * np.sqrt(c1 * c2) * np.sin(np.radians(dh) / 2)
    lb, cbp = (L1 + L2) / 2, (c1 + c2) / 2
    if c1 * c2 == 0: hb = h1 + h2
    elif abs(h1 - h2) <= 180: hb = (h1 + h2) / 2
    elif h1 + h2 < 360: hb = (h1 + h2 + 360) / 2
    else: hb = (h1 + h2 - 360) / 2
    t = (1 - 0.17 * np.cos(np.radians(hb - 30)) + 0.24 * np.cos(np.radians(2 * hb))
         + 0.32 * np.cos(np.radians(3 * hb + 6)) - 0.2 * np.cos(np.radians(4 * hb - 63)))
    rc = 2 * np.sqrt(cbp ** 7 / (cbp ** 7 + 25 ** 7))
    sl = 1 + 0.015 * (lb - 50) ** 2 / np.sqrt(20 + (lb - 50) ** 2)
    sc, sh = 1 + 0.045 * cbp, 1 + 0.015 * cbp * t
    rt = -np.sin(np.radians(2 * 30 * np.exp(-((hb - 275) / 25) ** 2))) * rc
    dl, dc = (L2 - L1) / sl, (c2 - c1) / sc
    return float(np.sqrt(dl ** 2 + dc ** 2 + (dH / sh) ** 2 + rt * dc * (dH / sh)))


def lum(c): l = lin(c); return 0.2126 * l[0] + 0.7152 * l[1] + 0.0722 * l[2]
def contrast(a, b):
    hi, lo = sorted((lum(rgb(a)), lum(rgb(b))), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def de(a, b, kind=None):
    ca, cb = (rgb(a), rgb(b)) if kind is None else (delin(np.clip(CVD[kind] @ lin(rgb(a)), 0, 1)), delin(np.clip(CVD[kind] @ lin(rgb(b)), 0, 1)))
    return de2000(lab(ca), lab(cb))


def main():
    if len(sys.argv) > 1:
        scale = sys.argv[1:]
    else:
        text = SRC.read_text()
        scale = re.search(r"WORLD_MAP_SCALE = \[([^\]]+)\]", text).group(1)
        scale = re.findall(r"#[0-9A-Fa-f]{6}", scale)
    ocean, nodata = '#DCE8F3', '#E6E3DC'
    for i, h in enumerate(scale):
        l = lab(rgb(h))
        print(i, h, 'L*=%.0f C=%.0f' % (l[0], np.hypot(l[1], l[2])),
              'океан: ΔE %.1f, контраст %.2f' % (de(h, ocean), contrast(h, ocean)),
              '| нет данных: ΔE %.1f, контраст %.2f' % (de(h, nodata), contrast(h, nodata)))
    for kind in (None, 'protan', 'deutan', 'tritan'):
        adj = [de(scale[i], scale[i + 1], kind) for i in range(len(scale) - 1)]
        pair = min(de(a, b, kind) for a, b in itertools.combinations(scale, 2))
        far = min(min(de(h, ocean, kind), de(h, nodata, kind)) for h in scale)
        print('%-7s соседние ΔE: %s | наименьший шаг между любыми: %.1f | наименьший от океана/суши: %.1f'
              % (kind or 'норма', ' '.join('%.1f' % x for x in adj), pair, far))


if __name__ == '__main__':
    main()

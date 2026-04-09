"""
Embed API — server-side SVG generation + impression tracking.

Endpoints:
  GET  /api/v1/embed/spark/{code}.svg  — sparkline SVG (0 JS, cacheable)
  GET  /api/v1/embed/card/{code}.svg   — card SVG (name + value + sparkline)
  POST /api/v1/embed/impression        — fire-and-forget impression counter
  GET  /api/v1/embed/pixel.gif         — 1×1 tracking pixel for <img> embeds
"""

import re
import logging
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Indicator, IndicatorData
from app.core.cache import cache_get, cache_set, get_redis

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/embed", tags=["embed"])

_CODE_RE = re.compile(r"^[a-z0-9-]+$")
_COLOR_RE = re.compile(r"^[0-9a-fA-F]{6}$")

FONT = "system-ui,-apple-system,sans-serif"
MONO = "ui-monospace,'SF Mono',monospace"

# ─── SVG utilities ────────────────────────────────────────────────


def _validate_code(code: str):
    if not _CODE_RE.match(code):
        raise HTTPException(400, "Invalid indicator code")


def _safe_color(color: str) -> str:
    return color if _COLOR_RE.match(color) else "B8942F"


def _xml(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _period_days(period: str) -> Optional[int]:
    return {
        "1m": 30, "3m": 90, "6m": 180,
        "1y": 365, "3y": 1095, "5y": 1825,
        "10y": 3650,
    }.get(period)


async def _fetch_points(
    code: str, period: str, db: AsyncSession, limit: int = 300
) -> tuple[Optional[Indicator], list]:
    q = await db.execute(select(Indicator).where(Indicator.code == code))
    ind = q.scalar_one_or_none()
    if not ind:
        return None, []

    stmt = select(IndicatorData).where(IndicatorData.indicator_id == ind.id)
    days = _period_days(period)
    if days:
        stmt = stmt.where(IndicatorData.date >= date.today() - timedelta(days=days))
    stmt = stmt.order_by(desc(IndicatorData.date)).limit(limit)
    rows = list(reversed((await db.execute(stmt)).scalars().all()))
    return ind, rows


def _to_svg_coords(
    values: list[float], w: float, h: float, pad: float = 3.0
) -> list[tuple[float, float]]:
    n = len(values)
    if n < 2:
        return [(w / 2, h / 2)]
    lo, hi = min(values), max(values)
    span = hi - lo or 1.0
    uw, uh = w - 2 * pad, h - 2 * pad
    return [
        (round(pad + uw * i / (n - 1), 1), round(pad + uh * (1 - (v - lo) / span), 1))
        for i, v in enumerate(values)
    ]


def _catmull_rom(pts: list[tuple[float, float]]) -> str:
    """Catmull-Rom spline → SVG cubic-bézier path."""
    n = len(pts)
    if n < 2:
        return ""
    if n == 2:
        return f"M{pts[0][0]:.1f},{pts[0][1]:.1f}L{pts[1][0]:.1f},{pts[1][1]:.1f}"
    d = [f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"]
    for i in range(n - 1):
        p0 = pts[max(i - 1, 0)]
        p1 = pts[i]
        p2 = pts[min(i + 1, n - 1)]
        p3 = pts[min(i + 2, n - 1)]
        c1x = p1[0] + (p2[0] - p0[0]) / 6
        c1y = p1[1] + (p2[1] - p0[1]) / 6
        c2x = p2[0] - (p3[0] - p1[0]) / 6
        c2y = p2[1] - (p3[1] - p1[1]) / 6
        d.append(f"C{c1x:.1f},{c1y:.1f} {c2x:.1f},{c2y:.1f} {p2[0]:.1f},{p2[1]:.1f}")
    return " ".join(d)


def _fmt_value(v: float, digits: int = 2) -> str:
    s = f"{v:,.{digits}f}"
    int_part, *dec = s.split(".")
    int_part = int_part.replace(",", "\u00A0")
    return f"{int_part}.{dec[0]}" if dec else int_part


def _svg_response(svg: str, max_age: int = 3600) -> Response:
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={
            "Cache-Control": f"public, max-age={max_age}, s-maxage={max_age * 2}",
            "Access-Control-Allow-Origin": "*",
        },
    )


# ─── Sparkline SVG ────────────────────────────────────────────────


@router.get("/spark/{code}.svg")
async def sparkline_svg(
    code: str,
    w: int = Query(200, ge=50, le=1200),
    h: int = Query(60, ge=20, le=600),
    period: str = Query("1y"),
    color: str = Query("B8942F"),
    fill: bool = Query(True),
    dot: bool = Query(True),
    stroke: float = Query(1.5, ge=0.5, le=4),
    db: AsyncSession = Depends(get_db),
):
    _validate_code(code)
    color = _safe_color(color)
    ck = f"fe:embed:spark:{code}:{w}:{h}:{period}:{color}:{fill}:{dot}:{stroke}"
    cached = await cache_get(ck)
    if cached:
        return _svg_response(cached)

    _, rows = await _fetch_points(code, period, db)
    if not rows:
        return _svg_response(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}"'
            f' width="{w}" height="{h}"/>',
            max_age=300,
        )

    values = [float(r.value) for r in rows]
    pts = _to_svg_coords(values, w, h)
    line = _catmull_rom(pts)
    c = f"#{color}"

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}"',
        f' width="{w}" height="{h}" role="img"',
        f' aria-label="{_xml(code)} sparkline">',
    ]

    if fill:
        fp = f"{line} L{pts[-1][0]:.1f},{h} L{pts[0][0]:.1f},{h} Z"
        parts.append(
            f'<defs><linearGradient id="sg" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0%" stop-color="{c}" stop-opacity="0.18"/>'
            f'<stop offset="100%" stop-color="{c}" stop-opacity="0"/>'
            f"</linearGradient></defs>"
            f'<path d="{fp}" fill="url(#sg)"/>'
        )

    parts.append(
        f'<path d="{line}" fill="none" stroke="{c}"'
        f' stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round"/>'
    )

    if dot:
        lx, ly = pts[-1]
        parts.append(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="{stroke + 1}" fill="{c}"/>')

    parts.append("</svg>")
    svg = "".join(parts)
    await cache_set(ck, svg, 3600)
    return _svg_response(svg)


# ─── Card SVG ─────────────────────────────────────────────────────


@router.get("/card/{code}.svg")
async def card_svg(
    code: str,
    w: int = Query(320, ge=200, le=600),
    h: int = Query(160, ge=100, le=400),
    theme: str = Query("light"),
    period: str = Query("1y"),
    db: AsyncSession = Depends(get_db),
):
    _validate_code(code)
    ck = f"fe:embed:card:{code}:{w}:{h}:{theme}:{period}"
    cached = await cache_get(ck)
    if cached:
        return _svg_response(cached)

    ind, rows = await _fetch_points(code, period, db, limit=200)
    if not ind:
        raise HTTPException(404, f"Indicator '{code}' not found")

    cur = float(rows[-1].value) if rows else None
    prev = float(rows[-2].value) if len(rows) > 1 else None
    change = round(cur - prev, 4) if cur is not None and prev is not None else None

    dark = theme == "dark"
    bg = "#1a1a1e" if dark else "#FFFFFF"
    border = "#333" if dark else "#e5e5e5"
    t1 = "#e5e5e5" if dark else "#1a1a1a"
    t2 = "#aaa" if dark else "#666"
    t3 = "#555" if dark else "#bbb"
    accent = "#B8942F"
    pos_c, neg_c = "#22c55e", "#ef4444"

    val_str = _fmt_value(cur) if cur is not None else "—"
    unit = _xml(ind.unit or "")

    chg_arrow, chg_str, chg_color = "", "", t2
    if change is not None:
        chg_arrow = "▲" if change > 0 else ("▼" if change < 0 else "")
        chg_str = f'{"+" if change >= 0 else ""}{change:.2f}'
        chg_color = pos_c if change > 0 else (neg_c if change < 0 else t2)

    # Sparkline in lower portion
    sy = h * 0.58
    sh = h * 0.30
    sw = w - 32

    spark_line, spark_fill = "", ""
    if len(rows) > 1:
        vals = [float(r.value) for r in rows]
        sp = _to_svg_coords(vals, sw, sh, pad=2)
        spark_line = _catmull_rom(sp)
        spark_fill = f"{spark_line} L{sp[-1][0]:.1f},{sh} L{sp[0][0]:.1f},{sh} Z"

    p = [
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"'
        f' viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
        f'<rect width="{w}" height="{h}" rx="12" fill="{bg}" stroke="{border}" stroke-width="1"/>',
        f'<text x="16" y="24" font-family="{FONT}" font-size="11" fill="{t2}"'
        f' font-weight="500">{_xml(ind.name)}</text>',
        f'<text x="16" y="54" font-family="{MONO}" font-size="26" fill="{t1}"'
        f' font-weight="700">{val_str}'
        f'<tspan font-size="12" fill="{t2}"> {unit}</tspan></text>',
    ]

    if chg_str:
        p.append(
            f'<text x="16" y="74" font-family="{MONO}" font-size="12"'
            f' fill="{chg_color}" font-weight="600">{chg_arrow} {chg_str}</text>'
        )

    if spark_line:
        p.append(f'<g transform="translate(16,{sy:.0f})">')
        p.append(
            f'<defs><linearGradient id="cg" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0%" stop-color="{accent}" stop-opacity="0.15"/>'
            f'<stop offset="100%" stop-color="{accent}" stop-opacity="0"/>'
            f"</linearGradient></defs>"
        )
        if spark_fill:
            p.append(f'<path d="{spark_fill}" fill="url(#cg)"/>')
        p.append(
            f'<path d="{spark_line}" fill="none" stroke="{accent}"'
            f' stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'
        )
        p.append("</g>")

    p.append(
        f'<a href="https://forecasteconomy.com/indicator/{code}" target="_blank">'
        f'<text x="{w - 12}" y="{h - 8}" font-family="{FONT}" font-size="9"'
        f' fill="{t3}" text-anchor="end">forecasteconomy.com</text></a>'
    )

    p.append("</svg>")
    svg = "".join(p)
    await cache_set(ck, svg, 3600)
    return _svg_response(svg)


# ─── Badge SVG (shields.io style) ─────────────────────────────────


@router.get("/badge/{code}.svg")
async def badge_svg(
    code: str,
    theme: str = Query("light"),
    period: str = Query("1y"),
    db: AsyncSession = Depends(get_db),
):
    """shields.io-compatible badge: ``label | value  ▲change``."""
    _validate_code(code)
    ck = f"fe:embed:badge:{code}:{theme}:{period}"
    cached = await cache_get(ck)
    if cached:
        return _svg_response(cached)

    ind, rows = await _fetch_points(code, period, db, limit=2)
    if not ind:
        raise HTTPException(404, f"Indicator '{code}' not found")

    cur = float(rows[-1].value) if rows else None
    prev = float(rows[-2].value) if len(rows) > 1 else None
    change = round(cur - prev, 4) if cur is not None and prev is not None else None
    val_str = _fmt_value(cur) if cur is not None else "—"
    unit = ind.unit or ""

    label = _xml(ind.name)[:40]
    value_text = f"{val_str} {_xml(unit)}".strip()
    if change is not None:
        arrow = "\u25B2" if change > 0 else ("\u25BC" if change < 0 else "")
        chg_str = f'{"+" if change >= 0 else ""}{change:.2f}'
        value_text += f"  {arrow}{chg_str}"

    dark = theme == "dark"
    label_bg = "#333" if dark else "#555"
    value_bg = "#22c55e" if (change is not None and change > 0) else (
        "#ef4444" if (change is not None and change < 0) else "#999"
    )
    text_color = "#fff"

    char_w = 6.5
    pad = 12
    label_w = len(label) * char_w + pad * 2
    value_w = len(value_text) * char_w + pad * 2
    total_w = label_w + value_w
    h = 22
    r = 4

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w:.0f}" height="{h}"'
        f' role="img" aria-label="{label}: {_xml(value_text)}">'
        f'<rect width="{total_w:.0f}" height="{h}" rx="{r}" fill="{label_bg}"/>'
        f'<rect x="{label_w:.0f}" width="{value_w:.0f}" height="{h}"'
        f' rx="{r}" fill="{value_bg}"/>'
        f'<rect x="{label_w:.0f}" width="{min(r, value_w)}" height="{h}" fill="{value_bg}"/>'
        f'<text x="{label_w / 2:.0f}" y="15" fill="{text_color}"'
        f' font-family="{FONT}" font-size="11" font-weight="500" text-anchor="middle">'
        f'{label}</text>'
        f'<text x="{label_w + value_w / 2:.0f}" y="15" fill="{text_color}"'
        f' font-family="{MONO}" font-size="11" font-weight="600" text-anchor="middle">'
        f'{_xml(value_text)}</text>'
        f'</svg>'
    )
    await cache_set(ck, svg, 3600)
    return _svg_response(svg)


# ─── Impression tracking ─────────────────────────────────────────

PIXEL_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff"
    b"\x00\x00\x00!\xf9\x04\x00\x00\x00\x00\x00,\x00"
    b"\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


def _extract_domain(referrer: str) -> str:
    if not referrer or not referrer.startswith("http"):
        return "direct"
    try:
        from urllib.parse import urlparse
        return urlparse(referrer).netloc or "direct"
    except Exception:
        return "direct"


@router.post("/impression")
async def track_impression(request: Request):
    try:
        body = await request.json()
        code = str(body.get("code", "unknown"))[:64]
        wtype = str(body.get("type", "unknown"))[:32]
        domain = _extract_domain(str(body.get("referrer", "")))

        today = date.today().isoformat()
        r = await get_redis()
        key = f"fe:embed:imp:{today}"
        await r.hincrby(key, f"{code}:{wtype}:{domain}", 1)
        await r.expire(key, 90 * 86400)
    except Exception:
        logger.debug("Impression tracking failed", exc_info=True)
    return {"ok": True}


@router.get("/pixel.gif")
async def tracking_pixel(
    code: str = Query("unknown"),
    t: str = Query("spark"),
    request: Request = None,
):
    try:
        ref = request.headers.get("referer", "") if request else ""
        domain = _extract_domain(ref)
        today = date.today().isoformat()
        r = await get_redis()
        await r.hincrby(f"fe:embed:imp:{today}", f"{code}:{t}:{domain}", 1)
    except Exception:
        pass
    return Response(
        content=PIXEL_GIF,
        media_type="image/gif",
        headers={"Cache-Control": "no-cache, no-store", "Access-Control-Allow-Origin": "*"},
    )

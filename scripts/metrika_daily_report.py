#!/usr/bin/env python3
"""Дневной PDF-отчёт трафика forecasteconomy.com — все слои данных.

Один запуск → папка analytics/reports/YYYY-MM-DD/ + PDF:
  • Яндекс.Метрика (Reporting API): KPI, каналы, поминутка, все фразы/страницы
  • First-party: события фронта (внутренний поиск, скачивания), поведение (клики/dwell)
  • Склад: Logs API, снапшоты привлечения, агрегаты фраз/страниц из БД
  • Яндекс.Вебмастер: все запросы выдачи, сопоставление с Метрикой
  • Инвентаризация датасета + гипотезы Пульса

  python3 scripts/metrika_daily_report.py --day 2026-07-03 --open
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import textwrap
import urllib.parse
import urllib.request
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
BASELINE_START = date(2026, 6, 3)
COUNTER = "107136069"
CHANNEL_ORDER = [
    "Ad traffic",
    "Search engine traffic",
    "Direct traffic",
    "Internal traffic",
    "Link traffic",
    "Social network traffic",
]
CHANNEL_RU = {
    "Ad traffic": "Реклама",
    "Search engine traffic": "Поиск",
    "Direct traffic": "Прямой",
    "Internal traffic": "Внутренний",
    "Link traffic": "Ссылки",
    "Social network traffic": "Соцсети",
}
CHANNEL_COLORS = {
    "Ad traffic": "#EF4444",
    "Search engine traffic": "#22C55E",
    "Direct traffic": "#3B82F6",
    "Internal traffic": "#A855F7",
    "Link traffic": "#F59E0B",
    "Social network traffic": "#EC4899",
}
ROWS_PER_PAGE = 32  # строк на страницу графика/таблицы — без обрезки топ-N
WEBMASTER_HOST = "https:forecasteconomy.com:443"


def _close_figs(figs: list[plt.Figure]) -> None:
    for f in figs:
        plt.close(f)


def _pdf_add(pdf: PdfPages, fig: plt.Figure | list[plt.Figure]) -> None:
    if isinstance(fig, list):
        for f in fig:
            pdf.savefig(f)
            plt.close(f)
    else:
        pdf.savefig(fig)
        plt.close(fig)


def _token() -> str:
    tok = os.environ.get("RUSTATS_YANDEX_METRIKA_READ_TOKEN", "")
    if tok:
        return tok.strip()
    env_path = ROOT / "backend" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("RUSTATS_YANDEX_METRIKA_READ_TOKEN="):
                return line.split("=", 1)[1].strip()
    sys.exit("Нет RUSTATS_YANDEX_METRIKA_READ_TOKEN")


def api_get(path: str, params: dict[str, Any]) -> dict:
    q = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    url = f"https://api-metrika.yandex.net/stat/v1/{path}?id={COUNTER}&{q}"
    req = urllib.request.Request(url, headers={"Authorization": f"OAuth {_token()}"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)


def fetch_totals(d1: date, d2: date) -> tuple[int, int, int]:
    data = api_get("data", {
        "metrics": "ym:s:users,ym:s:visits,ym:s:pageviews",
        "date1": d1.isoformat(),
        "date2": d2.isoformat(),
        "limit": 1,
    })
    t = data["totals"]
    return int(t[0]), int(t[1]), int(t[2])


def fetch_cumulative_users(end: date) -> int:
    data = api_get("data", {
        "metrics": "ym:s:users",
        "date1": BASELINE_START.isoformat(),
        "date2": end.isoformat(),
        "limit": 1,
    })
    return int(data["totals"][0])


def fetch_dimension_rows_all(
    d1: date,
    d2: date,
    dimension: str,
    *,
    sort: str = "-ym:s:visits",
    extra_metrics: str | None = None,
    filters: str | None = None,
) -> tuple[int, list[dict], dict[str, Any]]:
    """Все строки из Reporting API с пагинацией (не обрезаем топ-N)."""
    metrics = extra_metrics or "ym:s:visits,ym:s:users,ym:s:pageviews"
    merged: list[dict] = []
    offset = 1
    total_visits = 0
    api_meta: dict[str, Any] = {"api_total_rows": None, "fetched_rows": 0, "complete": False}
    while True:
        params: dict[str, Any] = {
            "metrics": metrics,
            "dimensions": dimension,
            "date1": d1.isoformat(),
            "date2": d2.isoformat(),
            "sort": sort,
            "limit": 10000,
            "offset": offset,
        }
        if filters:
            params["filters"] = filters
        data = api_get("data", params)
        if offset == 1:
            total_visits = int(data["totals"][0])
            api_meta["api_total_rows"] = data.get("total_rows")
        batch = data.get("data") or []
        if not batch:
            break
        for row in batch:
            dims = row["dimensions"]
            name = dims[0]["name"]
            if name in ("", "(not set)", "None"):
                continue
            m = row["metrics"]
            item: dict[str, Any] = {
                "name": name,
                "visits": int(m[0]),
                "users": int(m[1]) if len(m) > 1 else 0,
                "pageviews": int(m[2]) if len(m) > 2 else 0,
            }
            if len(dims) > 1:
                item["search_engine"] = dims[1].get("name")
            merged.append(item)
        if len(batch) < 10000:
            break
        offset += 10000
    api_meta["fetched_rows"] = len(merged)
    tr = api_meta["api_total_rows"]
    api_meta["complete"] = tr is None or len(merged) >= int(tr)
    for item in merged:
        item["share_pct"] = round(100 * item["visits"] / total_visits, 1) if total_visits else 0
    merged.sort(key=lambda x: x["visits"], reverse=True)
    return total_visits, merged, api_meta


def fetch_dimension_rows(
    d1: date,
    d2: date,
    dimension: str,
    *,
    limit: int = 25,
    sort: str = "-ym:s:visits",
    extra_metrics: str | None = None,
) -> tuple[int, list[dict]]:
    metrics = extra_metrics or "ym:s:visits,ym:s:users,ym:s:pageviews"
    data = api_get("data", {
        "metrics": metrics,
        "dimensions": dimension,
        "date1": d1.isoformat(),
        "date2": d2.isoformat(),
        "sort": sort,
        "limit": limit,
    })
    total_visits = int(data["totals"][1] if len(data["totals"]) > 1 else data["totals"][0])
    if "visits" in metrics.split(",")[0]:
        total_visits = int(data["totals"][0])
    rows: list[dict] = []
    for row in data["data"]:
        name = row["dimensions"][0]["name"]
        if name in ("", "(not set)", "None"):
            continue
        m = row["metrics"]
        rows.append({
            "name": name,
            "visits": int(m[0]),
            "users": int(m[1]) if len(m) > 1 else 0,
            "pageviews": int(m[2]) if len(m) > 2 else 0,
            "share_pct": round(100 * int(m[0]) / total_visits, 1) if total_visits else 0,
        })
    return total_visits, rows


def fetch_channels(d1: date, d2: date) -> tuple[int, list[dict]]:
    tv, rows = fetch_dimension_rows(
        d1, d2, "ym:s:lastTrafficSource", limit=10,
        extra_metrics="ym:s:visits,ym:s:users,ym:s:pageviews,ym:s:bounceRate,ym:s:pageDepth",
    )
    out = []
    for row in rows:
        # bounce/depth not in simple fetch — refetch if needed; skip for now
        out.append(row)
    return tv, out


def fetch_channels_detailed(d1: date, d2: date) -> tuple[int, list[dict]]:
    data = api_get("data", {
        "metrics": "ym:s:visits,ym:s:users,ym:s:pageviews,ym:s:bounceRate,ym:s:pageDepth",
        "dimensions": "ym:s:lastTrafficSource",
        "date1": d1.isoformat(),
        "date2": d2.isoformat(),
        "sort": "-ym:s:visits",
        "limit": 10,
    })
    tv = int(data["totals"][0])
    rows = []
    for row in data["data"]:
        name = row["dimensions"][0]["name"]
        m = row["metrics"]
        rows.append({
            "name": name,
            "visits": int(m[0]),
            "users": int(m[1]),
            "pageviews": int(m[2]),
            "bounce_pct": round(m[3], 1),
            "depth": round(m[4], 2),
            "share_pct": round(100 * int(m[0]) / tv, 1) if tv else 0,
        })
    return tv, rows


def fetch_search_channel_visits(d: date) -> int:
    data = api_get("data", {
        "metrics": "ym:s:visits",
        "dimensions": "ym:s:lastTrafficSource",
        "date1": d.isoformat(),
        "date2": d.isoformat(),
        "sort": "-ym:s:visits",
        "limit": 10,
    })
    for row in data["data"]:
        if row["dimensions"][0]["name"] == "Search engine traffic":
            return int(row["metrics"][0])
    return 0


def fetch_search_phrases_reporting(d1: date, d2: date) -> tuple[list[dict], dict[str, Any]]:
    """Уникальные поисковые фразы за период [d1, d2] из Reporting API."""
    _, rows, meta = fetch_dimension_rows_all(
        d1, d2,
        "ym:s:searchPhrase,ym:s:searchEngine",
        filters="ym:s:trafficSource=='organic'",
        extra_metrics="ym:s:visits,ym:s:users,ym:s:pageviews",
    )
    meta["period"] = f"{d1.isoformat()}..{d2.isoformat()}"
    meta["scope"] = "day" if d1 == d2 else "period"
    return rows, meta


def fetch_phrases_warehouse(d: date) -> list[dict]:
    """Повизитные фразы из локального склада Logs API (если docker/postgres доступен)."""
    sql = f"""
    SELECT search_phrase AS name, search_engine, COUNT(*)::int AS visits
    FROM raw_metrika_visits
    WHERE visit_date = '{d.isoformat()}'
      AND search_phrase IS NOT NULL AND search_phrase <> ''
    GROUP BY 1, 2 ORDER BY visits DESC;
    """
    try:
        proc = subprocess.run(
            [
                "docker", "compose", "-f", str(ROOT / "docker-compose.yml"),
                "exec", "-T", "postgres",
                "psql", "-U", "rustats", "-d", "rustats", "-t", "-A", "-F", "\t",
                "-c", sql,
            ],
            capture_output=True, text=True, timeout=15, cwd=ROOT,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    if proc.returncode != 0:
        return []
    rows: list[dict] = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        phrase, engine = parts[0], parts[1] if len(parts) > 2 else ""
        visits = int(parts[-1])
        rows.append({
            "name": phrase,
            "search_engine": engine or None,
            "visits": visits,
            "users": visits,
            "pageviews": 0,
            "source": "logs_warehouse",
        })
    return rows


def merge_search_phrases(*sources: list[dict]) -> list[dict]:
    """Объединяем reporting + warehouse: одна фраза = max(визиты), движок если есть."""
    by_key: dict[str, dict] = {}
    for src in sources:
        for row in src:
            key = row["name"].strip().lower()
            if not key:
                continue
            cur = by_key.get(key)
            if cur is None:
                by_key[key] = {**row, "name": row["name"].strip()}
            else:
                # Один текст из Reporting (разные ПС) — суммируем визиты.
                # Reporting + склад — max, чтобы не задвоить один визит.
                if row.get("source") == "logs_warehouse" or cur.get("source") == "logs_warehouse":
                    if row["visits"] > cur["visits"]:
                        cur["visits"] = row["visits"]
                else:
                    cur["visits"] += row["visits"]
                if row.get("search_engine") and cur.get("search_engine") and row["search_engine"] != cur["search_engine"]:
                    cur["search_engine"] = f"{cur['search_engine']}; {row['search_engine']}"
                elif row.get("search_engine") and not cur.get("search_engine"):
                    cur["search_engine"] = row["search_engine"]
                cur["source"] = "merged"
    out = sorted(by_key.values(), key=lambda x: x["visits"], reverse=True)
    total = sum(r["visits"] for r in out)
    for r in out:
        r["share_pct"] = round(100 * r["visits"] / total, 1) if total else 0
    return out


def fetch_phrases(d1: date, d2: date, limit: int | None = None) -> list[dict]:
    _, rows, _ = fetch_dimension_rows_all(d1, d2, "ym:s:searchPhrase")
    return rows[:limit] if limit else rows


def fetch_pages(d1: date, d2: date, limit: int | None = None) -> list[dict]:
    _, rows, _ = fetch_dimension_rows_all(d1, d2, "ym:s:startURL")
    return rows[:limit] if limit else rows


def fetch_devices(d1: date, d2: date) -> list[dict]:
    _, rows, _ = fetch_dimension_rows_all(
        d1, d2, "ym:s:deviceCategory",
        extra_metrics="ym:s:visits,ym:s:users,ym:s:pageviews,ym:s:bounceRate,ym:s:pageDepth",
    )
    return rows


def fetch_search_engines(d1: date, d2: date) -> list[dict]:
    _, rows, _ = fetch_dimension_rows_all(
        d1, d2, "ym:s:lastSearchEngineRoot",
        extra_metrics="ym:s:visits,ym:s:users,ym:s:pageviews",
    )
    return rows


def fetch_referrers(d1: date, d2: date) -> list[dict]:
    _, rows, _ = fetch_dimension_rows_all(
        d1, d2, "ym:s:lastReferalSource",
        extra_metrics="ym:s:visits,ym:s:users,ym:s:pageviews",
    )
    return rows


def fetch_webmaster_queries(d1: date, d2: date) -> dict[str, Any]:
    """Все популярные запросы из Яндекс.Вебмастера (через docker backend)."""
    script = f'''
import asyncio, json
from app.services.yandex_webmaster_client import YandexWebmasterClient

async def main():
    d1, d2 = "{d1.isoformat()}", "{d2.isoformat()}"
    c = YandexWebmasterClient()
    uid = (await c.user()).data["user_id"]
    hid = "{WEBMASTER_HOST}"
    out = []
    offset = 0
    total_count = 0
    while True:
        r = (await c.search_queries_popular(
            uid, hid, date_from=d1, date_to=d2,
            order_by="TOTAL_SHOWS", query_indicator="TOTAL_SHOWS",
            limit=500, offset=offset,
        )).data
        batch = r.get("queries", [])
        if offset == 0:
            total_count = int(r.get("count", 0) or 0)
        if not batch:
            break
        for q in batch:
            ind = q.get("indicators", {{}})
            shows = int(ind.get("TOTAL_SHOWS", 0) or 0)
            clicks = int(ind.get("TOTAL_CLICKS", 0) or 0)
            pos = ind.get("TOTAL_AVG_SHOW_POSITION") or ind.get("AVG_SHOW_POSITION")
            pos_f = float(pos) if pos is not None else None
            out.append({{
                "query": q["query_text"],
                "shows": shows,
                "clicks": clicks,
                "position": round(pos_f, 1) if pos_f is not None else None,
                "ctr_pct": round(100 * clicks / shows, 2) if shows else 0.0,
            }})
        offset += 500
        if len(batch) < 500:
            break
    total_shows = sum(x["shows"] for x in out)
    for x in out:
        x["share_pct"] = round(100 * x["shows"] / total_shows, 2) if total_shows else 0.0
    out.sort(key=lambda z: z["shows"], reverse=True)
    print(json.dumps({{
        "queries": out,
        "count": total_count,
        "fetched": len(out),
        "date_from": d1,
        "date_to": d2,
        "total_shows": total_shows,
        "total_clicks": sum(x["clicks"] for x in out),
    }}, ensure_ascii=False))

asyncio.run(main())
'''
    try:
        proc = subprocess.run(
            [
                "docker", "compose", "-f", str(ROOT / "docker-compose.yml"),
                "exec", "-T", "backend", "python", "-c", script,
            ],
            capture_output=True, text=True, timeout=180, cwd=ROOT,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return {"queries": [], "error": str(exc), "count": 0, "fetched": 0}
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "webmaster fetch failed").strip()
        return {"queries": [], "error": err[:500], "count": 0, "fetched": 0}
    line = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "{}"
    return json.loads(line)


def fetch_first_party_bundle(day: date, period_start: date | None = None) -> dict[str, Any]:
    """First-party + склад из Postgres (docker backend)."""
    cmd = [
        "docker", "compose", "-f", str(ROOT / "docker-compose.yml"),
        "exec", "-T", "backend",
        "python", "-m", "app.services.analytics_report_bundle", day.isoformat(),
    ]
    if period_start:
        cmd.append(period_start.isoformat())
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=120, cwd=ROOT,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return {"error": str(exc), "day": day.isoformat()}
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "bundle fetch failed").strip()
        return {"error": err[:800], "day": day.isoformat()}
    line = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "{}"
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return {"error": "invalid JSON from bundle", "raw": proc.stdout[:500]}


def _rows_with_visits(items: list[dict], name_key: str, count_key: str = "count") -> list[dict]:
    """Адаптер для _fig_hbar_pages (ожидает visits + name)."""
    out = []
    total = sum(int(r.get(count_key, 0) or 0) for r in items) or 1
    for r in items:
        n = int(r.get(count_key, 0) or 0)
        out.append({
            "name": str(r.get(name_key, "—")),
            "visits": n,
            "share_pct": round(100 * n / total, 1),
            **r,
        })
    return out


def _norm_query(s: str) -> str:
    return " ".join(s.strip().lower().split())


def compare_phrase_layers(
    metrika: list[dict],
    webmaster: list[dict],
) -> dict[str, Any]:
    """Сопоставление фраз Метрики (визиты) и Вебмастера (показы)."""
    m_by: dict[str, dict] = {}
    for row in metrika:
        key = _norm_query(row.get("name") or row.get("query") or "")
        if key:
            m_by[key] = row
    w_by: dict[str, dict] = {}
    for row in webmaster:
        key = _norm_query(row.get("query") or row.get("name") or "")
        if key:
            w_by[key] = row

    both_keys = sorted(set(m_by) & set(w_by))
    only_m = sorted(set(m_by) - set(w_by), key=lambda k: m_by[k].get("visits", 0), reverse=True)
    only_w = sorted(set(w_by) - set(m_by), key=lambda k: w_by[k].get("shows", 0), reverse=True)

    both_rows = []
    for key in both_keys:
        both_rows.append({
            "query": m_by[key].get("name") or w_by[key].get("query"),
            "metrika_visits": m_by[key].get("visits", 0),
            "webmaster_shows": w_by[key].get("shows", 0),
            "webmaster_clicks": w_by[key].get("clicks", 0),
            "webmaster_position": w_by[key].get("position"),
        })
    both_rows.sort(key=lambda x: x["metrika_visits"] + x["webmaster_shows"], reverse=True)

    return {
        "metrika_distinct": len(m_by),
        "webmaster_distinct": len(w_by),
        "both": both_rows,
        "only_metrika": [
            {"query": m_by[k].get("name"), "visits": m_by[k].get("visits", 0)} for k in only_m
        ],
        "only_webmaster": [
            {"query": w_by[k].get("query"), "shows": w_by[k].get("shows", 0),
             "clicks": w_by[k].get("clicks", 0)} for k in only_w
        ],
    }


def fetch_daily_engagement(d1: date, d2: date) -> list[dict]:
    data = api_get("data", {
        "metrics": "ym:s:users,ym:s:visits,ym:s:pageviews,ym:s:bounceRate,ym:s:pageDepth",
        "dimensions": "ym:s:date",
        "date1": d1.isoformat(),
        "date2": d2.isoformat(),
        "sort": "ym:s:date",
        "limit": 100,
    })
    out = []
    for row in data["data"]:
        m = row["metrics"]
        out.append({
            "date": row["dimensions"][0]["name"],
            "users": int(m[0]),
            "visits": int(m[1]),
            "pageviews": int(m[2]),
            "bounce_pct": round(m[3], 1),
            "depth": round(m[4], 2),
        })
    return out


def fetch_by_minute(day: date) -> list[tuple[datetime, float, float]]:
    data = api_get("data/bytime", {
        "metrics": "ym:s:users,ym:s:visits",
        "date1": day.isoformat(),
        "date2": day.isoformat(),
        "group": "minute",
        "limit": 500,
    })
    intervals = data["time_intervals"]
    users, visits = data["data"][0]["metrics"]
    return [
        (datetime.fromisoformat(iv[0]), float(users[i]), float(visits[i]))
        for i, iv in enumerate(intervals)
    ]


def fetch_daily_series(d1: date, d2: date) -> list[tuple[date, int, int]]:
    data = api_get("data", {
        "metrics": "ym:s:users,ym:s:visits",
        "dimensions": "ym:s:date",
        "date1": d1.isoformat(),
        "date2": d2.isoformat(),
        "sort": "ym:s:date",
        "limit": 100,
    })
    return [
        (date.fromisoformat(r["dimensions"][0]["name"]), int(r["metrics"][0]), int(r["metrics"][1]))
        for r in data["data"]
    ]


def fetch_daily_channels(d1: date, d2: date) -> dict[str, dict[str, int]]:
    data = api_get("data", {
        "metrics": "ym:s:visits",
        "dimensions": "ym:s:date,ym:s:lastTrafficSource",
        "date1": d1.isoformat(),
        "date2": d2.isoformat(),
        "sort": "ym:s:date",
        "limit": 500,
    })
    by_day: dict[str, dict[str, int]] = {}
    for row in data["data"]:
        d = row["dimensions"][0]["name"]
        ch = row["dimensions"][1]["name"]
        by_day.setdefault(d, {})[ch] = int(row["metrics"][0])
    return by_day


def _short_url(url: str, max_len: int = 52) -> str:
    u = url.replace("https://forecasteconomy.com", "")
    if not u:
        return "/"
    if len(u) <= max_len:
        return u
    return u[: max_len - 1] + "…"


def _short_phrase(s: str, max_len: int = 48) -> str:
    s = s.strip()
    return s if len(s) <= max_len else s[: max_len - 1] + "…"


def _fig_title_page(
    day: date,
    users: int,
    visits: int,
    pageviews: int,
    channels: list[dict],
    launch_time: time | None,
    cum_users: int,
    cum_visits: int,
    sitemap_note: str,
) -> plt.Figure:
    fig = plt.figure(figsize=(11.69, 8.27))  # A4 landscape
    fig.patch.set_facecolor("#f8fafc")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")

    ax.text(0.05, 0.92, "forecasteconomy.com", fontsize=22, fontweight="bold", color="#0f172a")
    ax.text(
        0.05, 0.84,
        f"Дневной отчёт · {day.strftime('%d.%m.%Y')} · Метрика + Вебмастер",
        fontsize=14, color="#475569",
    )

    boxes = [
        ("Уникальные", f"{users:,}".replace(",", " ")),
        ("Визиты", f"{visits:,}".replace(",", " ")),
        ("Просмотры", f"{pageviews:,}".replace(",", " ")),
        ("Кумулятив уник. (с 3 июня)", f"{cum_users:,}".replace(",", " ")),
    ]
    for i, (label, val) in enumerate(boxes):
        x = 0.05 + i * 0.23
        rect = FancyBboxPatch((x, 0.62), 0.21, 0.14, boxstyle="round,pad=0.01",
                              facecolor="white", edgecolor="#e2e8f0", linewidth=1.5,
                              transform=ax.transAxes)
        ax.add_patch(rect)
        ax.text(x + 0.02, 0.72, label, fontsize=9, color="#64748b", transform=ax.transAxes)
        ax.text(x + 0.02, 0.65, val, fontsize=16, fontweight="bold", color="#0f172a",
                transform=ax.transAxes)

    ax.text(0.05, 0.55, "Каналы захода (доля визитов)", fontsize=12, fontweight="bold", color="#0f172a")
    y = 0.50
    for ch in channels:
        ru = CHANNEL_RU.get(ch["name"], ch["name"])
        bar_w = ch["share_pct"] / 100 * 0.55
        ax.add_patch(FancyBboxPatch(
            (0.22, y - 0.018), bar_w, 0.028, boxstyle="round,pad=0.002",
            facecolor=CHANNEL_COLORS.get(ch["name"], "#94a3b8"), transform=ax.transAxes,
        ))
        ax.text(0.05, y, f"{ru}", fontsize=10, va="center", transform=ax.transAxes)
        ax.text(0.22 + bar_w + 0.01, y, f"{ch['share_pct']}%  ({ch['visits']} виз.)",
                fontsize=10, va="center", color="#334155", transform=ax.transAxes)
        y -= 0.045

    notes = [
        f"Базовая линия: с {BASELINE_START.strftime('%d.%m.%Y')} · накоплено {cum_visits:,} визитов".replace(",", " "),
        sitemap_note,
    ]
    if launch_time:
        notes.append(f"Отметка запуска нового сервиса: {launch_time.strftime('%H:%M')} МСК")
    ax.text(0.05, 0.12, "\n".join(notes), fontsize=10, color="#475569", va="top",
            transform=ax.transAxes, linespacing=1.6)
    ax.text(0.05, 0.03, f"Сгенерировано {datetime.now().strftime('%d.%m.%Y %H:%M')} · counter {COUNTER}",
            fontsize=8, color="#94a3b8", transform=ax.transAxes)
    return fig


def _fig_intraday(
    minute_rows: list[tuple[datetime, float, float]],
    day: date,
    launch_time: time | None,
) -> plt.Figure:
    ts = [r[0] for r in minute_rows]
    visits = np.array([r[2] for r in minute_rows])
    cum = np.cumsum(visits)

    fig, ax1 = plt.subplots(figsize=(11.69, 8.27))
    fig.patch.set_facecolor("#fafafa")
    ax1.bar(ts, visits, width=1 / 1440, alpha=0.55, color="#6366F1", label="Визиты / мин")
    ax1.set_ylabel("Визиты за минуту")
    ax1.grid(True, alpha=0.25)

    if launch_time:
        launch_dt = datetime.combine(day, launch_time)
        ax1.axvline(launch_dt, color="#DC2626", linewidth=2, linestyle="--", label="Запуск сервиса 14:00 МСК")
        pre = int(visits[: launch_dt.hour * 60 + launch_dt.minute].sum())
        post = int(visits.sum()) - pre
        ax1.text(launch_dt, ax1.get_ylim()[1] * 0.95, f"  до 14:00: {pre}  |  после: {post}",
                 fontsize=9, color="#DC2626", va="top")

    ax2 = ax1.twinx()
    ax2.plot(ts, cum, color="#059669", linewidth=2.2, label="Накоплено визитов")
    ax2.set_ylabel("Кумулятив визитов за день")

    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax1.xaxis.set_major_locator(mdates.HourLocator(interval=2))
    lines1, lab1 = ax1.get_legend_handles_labels()
    lines2, lab2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, lab1 + lab2, loc="upper left")
    ax1.set_title(
        f"Поминутная динамика · {day.strftime('%d.%m.%Y')} · всего {int(visits.sum())} визитов",
        fontweight="bold", fontsize=13,
    )
    plt.tight_layout()
    return fig


def _wrap_text(s: str, width: int = 95) -> str:
    return "\n".join(textwrap.wrap(s.strip(), width=width)) if s else ""


def _fig_hbar_pages(
    items: list[dict],
    title: str,
    *,
    name_key: str = "name",
    value_key: str = "visits",
    formatter=None,
    extra_cols: list[tuple[str, str]] | None = None,
    rows_per_page: int = ROWS_PER_PAGE,
) -> list[plt.Figure]:
    """Горизонтальные столбцы — ВСЕ строки, постранично (без топ-N)."""
    if not items:
        fig, ax = plt.subplots(figsize=(11.69, 8.27))
        ax.axis("off")
        ax.text(0.5, 0.5, "Нет данных", ha="center", fontsize=14)
        return [fig]

    total_pages = (len(items) + rows_per_page - 1) // rows_per_page
    figures: list[plt.Figure] = []
    fmt = formatter or (lambda x: x)
    vmax = max(i[value_key] for i in items) or 1

    for page_i in range(total_pages):
        chunk = items[page_i * rows_per_page : (page_i + 1) * rows_per_page]
        n = len(chunk)
        fig_h = max(8.27, 0.21 * n + 1.8)
        fig, ax = plt.subplots(figsize=(11.69, min(fig_h, 40)))
        fig.patch.set_facecolor("#fafafa")

        labels = [fmt(row[name_key]) for row in chunk][::-1]
        vals = [row[value_key] for row in chunk][::-1]
        colors = plt.cm.Blues(np.linspace(0.35, 0.9, n))
        bars = ax.barh(range(n), vals, color=colors, height=0.72)
        ax.set_yticks(range(n))
        ax.set_yticklabels(labels, fontsize=7.5)
        ax.set_xlabel("Визиты")
        suffix = f" · {page_i + 1}/{total_pages} · строки {page_i * rows_per_page + 1}–{page_i * rows_per_page + n} из {len(items)}"
        ax.set_title(title + suffix, fontweight="bold", fontsize=11, loc="left")
        ax.set_xlim(0, vmax * 1.18)

        for bar, row in zip(bars, chunk[::-1]):
            label = str(row[value_key])
            if extra_cols:
                parts = [label] + [str(row.get(k, "")) for _, k in extra_cols]
                label = "  ·  ".join(parts)
            ax.text(
                bar.get_width() + vmax * 0.02,
                bar.get_y() + bar.get_height() / 2,
                label,
                va="center",
                fontsize=7,
                color="#334155",
            )
        ax.grid(True, axis="x", alpha=0.2)
        fig.subplots_adjust(left=0.38, right=0.95, top=0.92, bottom=0.06)
        figures.append(fig)
    return figures


def _fig_data_table_pages(
    rows: list[dict],
    title: str,
    columns: list[tuple[str, str, callable]],
    *,
    rows_per_page: int = ROWS_PER_PAGE,
) -> list[plt.Figure]:
    """Полные таблицы (все колонки, полный текст) — постранично."""
    figures: list[plt.Figure] = []
    if not rows:
        fig, ax = plt.subplots(figsize=(11.69, 8.27))
        ax.axis("off")
        ax.text(0.5, 0.5, "Нет данных", ha="center", fontsize=14)
        return [fig]

    total_pages = (len(rows) + rows_per_page - 1) // rows_per_page
    col_labels = [c[0] for c in columns]

    for page_i in range(total_pages):
        chunk = rows[page_i * rows_per_page : (page_i + 1) * rows_per_page]
        cell_text = []
        for row in chunk:
            cell_text.append([str(fn(row)) for _, _, fn in columns])

        fig, ax = plt.subplots(figsize=(11.69, 8.27))
        fig.patch.set_facecolor("#fafafa")
        ax.axis("off")
        suffix = f" · {page_i + 1}/{total_pages} · {len(rows)} строк всего"
        ax.set_title(title + suffix, fontweight="bold", fontsize=11, loc="left", pad=12)

        table = ax.table(
            cellText=cell_text,
            colLabels=col_labels,
            loc="upper center",
            cellLoc="left",
            colLoc="left",
        )
        table.auto_set_font_size(False)
        table.set_fontsize(7)
        table.scale(1, 1.35)
        # ширина первой колонки (текст)
        for (row_i, col_i), cell in table.get_celld().items():
            if col_i == 0 and row_i > 0:
                cell.set_width(0.62)
            if row_i == 0:
                cell.set_text_props(fontweight="bold", color="#0f172a")
                cell.set_facecolor("#e2e8f0")
        figures.append(fig)
    return figures


def _fig_channels_detail(channels: list[dict], title: str) -> plt.Figure:
    """Таблица каналов: визиты, доля, отказ, глубина, просмотры."""
    fig, ax = plt.subplots(figsize=(11.69, 8.27))
    fig.patch.set_facecolor("#fafafa")
    ax.axis("off")
    ax.set_title(title, fontweight="bold", fontsize=12, loc="left")

    headers = ["Канал", "Визиты", "Доля %", "Уник.", "Просм.", "Отказ %", "Глубина"]
    cells = []
    for ch in channels:
        cells.append([
            CHANNEL_RU.get(ch["name"], ch["name"]),
            str(ch["visits"]),
            str(ch.get("share_pct", "")),
            str(ch.get("users", "")),
            str(ch.get("pageviews", "")),
            str(ch.get("bounce_pct", "")),
            str(ch.get("depth", "")),
        ])
    table = ax.table(cellText=cells, colLabels=headers, loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.6)
    for (r, c), cell in table.get_celld().items():
        if r == 0:
            cell.set_facecolor("#e2e8f0")
            cell.set_text_props(fontweight="bold")
    return fig


def _fig_channels_pie(channels: list[dict], title: str) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(11.69, 8.27))
    fig.patch.set_facecolor("#fafafa")
    labels = [
        f"{CHANNEL_RU.get(c['name'], c['name'])}: {c['visits']} ({c['share_pct']}%)"
        for c in channels
    ]
    sizes = [c["visits"] for c in channels]
    colors = [CHANNEL_COLORS.get(c["name"], "#94a3b8") for c in channels]
    wedges, texts, autotexts = ax.pie(
        sizes, labels=None, autopct="%1.1f%%", colors=colors, startangle=90,
        pctdistance=0.75, textprops={"fontsize": 9},
    )
    ax.legend(wedges, labels, loc="center left", bbox_to_anchor=(1, 0.5), fontsize=9)
    ax.set_title(title, fontweight="bold", fontsize=13)
    return fig


def _fig_hourly(minute_rows: list[tuple[datetime, float, float]], day: date, launch_time: time | None) -> plt.Figure:
    """Почасовая агрегация с подписями на каждом столбце."""
    hourly = [0.0] * 24
    for ts, _, v in minute_rows:
        hourly[ts.hour] += v
    hours = list(range(24))
    labels = [f"{h:02d}" for h in hours]

    fig, ax = plt.subplots(figsize=(11.69, 8.27))
    fig.patch.set_facecolor("#fafafa")
    bars = ax.bar(hours, hourly, color="#6366F1", alpha=0.75, width=0.75)
    ax.set_xticks(hours)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_xlabel("Час (МСК)")
    ax.set_ylabel("Визиты")
    ax.grid(True, axis="y", alpha=0.25)

    if launch_time:
        ax.axvline(launch_time.hour, color="#DC2626", linestyle="--", linewidth=2, label="Запуск 14:00")
        ax.legend()

    for bar, v in zip(bars, hourly):
        if v > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{int(v)}",
                    ha="center", va="bottom", fontsize=7)
    ax.set_title(f"Почасовая динамика · {day.strftime('%d.%m.%Y')} · всего {int(sum(hourly))} визитов",
                 fontweight="bold", fontsize=13)
    plt.tight_layout()
    return fig


def _fig_channel_daily_matrix(by_day: dict[str, dict[str, int]], highlight: str) -> list[plt.Figure]:
    """Матрица день × канал — все числа, постранично."""
    days = sorted(by_day)
    channels = [c for c in CHANNEL_ORDER if any(c in by_day[d] for d in days)]
    channels += sorted({ch for d in days for ch in by_day[d]} - set(channels))

    rows = []
    for d in days:
        row = {"date": d, **{CHANNEL_RU.get(ch, ch): by_day[d].get(ch, 0) for ch in channels}}
        row["Итого"] = sum(by_day[d].values())
        rows.append(row)

    col_fns: list[tuple[str, str, callable]] = [("Дата", "date", lambda r: r["date"])]
    for ch in channels:
        ru = CHANNEL_RU.get(ch, ch)
        col_fns.append((ru, ru, lambda r, k=ru: str(r.get(k, 0))))
    col_fns.append(("Итого", "Итого", lambda r: str(r["Итого"])))

    return _fig_data_table_pages(
        rows,
        "Каналы по дням — полная матрица (визиты)",
        col_fns,
        rows_per_page=14,
    )


def _fig_growth(rows: list[tuple[date, int, int]], highlight: date, daily_engagement: list[dict]) -> list[plt.Figure]:
    dates = [r[0] for r in rows]
    daily_users = np.array([r[1] for r in rows])
    daily_visits = np.array([r[2] for r in rows])
    cum_users = np.array([fetch_cumulative_users(d) for d in dates])
    cum_visits = np.cumsum(daily_visits)
    pageviews = np.array([e["pageviews"] for e in daily_engagement])

    fig1, ax1 = plt.subplots(figsize=(11.69, 8.27))
    fig1.patch.set_facecolor("#fafafa")
    colors = ["#DC2626" if d == highlight else "#4A90D9" for d in dates]
    ax1.bar(dates, daily_users, width=0.35, alpha=0.5, color=colors, label="Уникальные")
    ax1.bar([d + timedelta(days=0.35) for d in dates], daily_visits, width=0.35, alpha=0.45,
            color="#7C3AED", label="Визиты")
    ax1.set_ylabel("За день")
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.25)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha="right")
    ax1.set_title(
        f"Посещаемость по дням с {BASELINE_START.strftime('%d.%m.%Y')} · выделен {highlight.strftime('%d.%m')}",
        fontweight="bold", fontsize=12,
    )
    plt.tight_layout()

    fig2, ax2 = plt.subplots(figsize=(11.69, 8.27))
    fig2.patch.set_facecolor("#fafafa")
    ax2.plot(dates, cum_users, color="#059669", marker="o", markersize=3, linewidth=2, label="Уник. накопл.")
    ax2.plot(dates, cum_visits, color="#2563EB", marker="s", markersize=2, linewidth=1.8, label="Визиты накопл.")
    ax2.set_ylabel("Накоплено с 3 июня")
    ax2.legend()
    ax2.grid(True, alpha=0.25)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha="right")
    for d, u, v in zip(dates, cum_users, cum_visits):
        if d == highlight:
            ax2.annotate(f"{u}/{v}", (d, u), textcoords="offset points", xytext=(4, 4), fontsize=8, color="#DC2626")
    ax2.set_title("Кумулятив с базовой линии", fontweight="bold", fontsize=12)
    plt.tight_layout()

    fig3, ax3 = plt.subplots(figsize=(11.69, 8.27))
    fig3.patch.set_facecolor("#fafafa")
    ax3.bar(dates, pageviews, color="#F59E0B", alpha=0.7, width=0.7)
    ax3.set_ylabel("Просмотры страниц")
    ax3.grid(True, alpha=0.25)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha="right")
    ax3.set_title("Просмотры по дням", fontweight="bold", fontsize=12)
    plt.tight_layout()

    return [fig1, fig2, fig3]


def _fig_phrases_coverage(
    day: date,
    search_visits: int,
    phrases: list[dict],
    reporting_count: int,
) -> plt.Figure:
    with_phrase = sum(p["visits"] for p in phrases)
    distinct = len(phrases)
    fig = plt.figure(figsize=(11.69, 8.27))
    fig.patch.set_facecolor("#f8fafc")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.text(0.05, 0.88, f"Поисковые запросы · полнота данных · {day.strftime('%d.%m.%Y')}",
            fontsize=16, fontweight="bold")
    lines = [
        f"Визитов из поисковиков за день: {search_visits}",
        f"Визитов с известной фразой (объединённый источник): {with_phrase}",
        f"Уникальных фраз: {distinct}  (Reporting API отдельно: {reporting_count})",
        "",
        "Почему не 100%: Яндекс.Метрика не передаёт текст запроса для части визитов",
        "(HTTPS, приватный режим, голосовой поиск, брендовые переходы без фразы в referrer).",
        "",
        "Источники в отчёте:",
        "  1) Reporting API — агрегат по органике (официальный отчёт Метрики)",
        "  2) Logs API / склад raw_metrika_visits — повизитные фразы (полнее, если синк отработал)",
    ]
    if search_visits:
        pct = round(100 * with_phrase / search_visits, 1)
        lines.insert(2, f"Покрытие: {pct}% поисковых визитов с текстом запроса")
    ax.text(0.05, 0.72, "\n".join(lines), fontsize=11, va="top", linespacing=1.5, family="sans-serif")
    return fig


def _fig_report_index(day: date, sections: list[str]) -> plt.Figure:
    fig = plt.figure(figsize=(11.69, 8.27))
    fig.patch.set_facecolor("#f8fafc")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.text(0.05, 0.92, f"Содержание отчёта · {day.strftime('%d.%m.%Y')}",
            fontsize=18, fontweight="bold", color="#0f172a")
    ax.text(0.05, 0.86, "Все разделы без обрезки топ-N — полные списки постранично.",
            fontsize=10, color="#64748b")
    y = 0.80
    for i, title in enumerate(sections, 1):
        ax.text(0.07, y, f"{i:02d}. {title}", fontsize=10.5, color="#334155", transform=ax.transAxes)
        y -= 0.028
        if y < 0.05:
            break
    ax.text(0.05, 0.04,
            "Источники: Метрика API · first-party (frontend/behavior) · склад БД · Вебмастер",
            fontsize=8, color="#94a3b8")
    return fig


def _fig_data_stack_explainer() -> plt.Figure:
    """Четыре слоя: зачем и Яндекс, и своё."""
    fig = plt.figure(figsize=(11.69, 8.27))
    fig.patch.set_facecolor("#f8fafc")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.text(0.05, 0.92, "Архитектура данных: Яндекс + first-party",
            fontsize=16, fontweight="bold")
    lines = [
        "Стратегия: копим максимум в своё хранилище, Яндекс — эталон каналов и выдачи.",
        "",
        "1. Яндекс.Метрика (API) — официальный трафик: визиты, реклама, каналы, поминутка.",
        "2. Яндекс.Вебмастер — поисковая выдача: показы, клики, позиции (лаг 1–3 дня).",
        "3. Склад Метрики (наша БД) — Logs API + дневные снапшоты: повизитные фразы,",
        "   UTM, рефереры; не зависит от лимитов отчёта в UI Метрики.",
        "4. First-party — behavior.js (клики, dwell, скролл) + track.js (поиск на сайте,",
        "   скачивания, регионы): детальнее Метрики, без сэмплирования, копим навсегда.",
        "",
        "Ни один слой не заменяет другой: рекламный биллинг — только Метрика;",
        "внутренний поиск — только мы; SERP — только Вебмастер.",
        "В отчёте — полные списки из каждого доступного слоя.",
    ]
    ax.text(0.05, 0.82, "\n".join(lines), fontsize=10.5, va="top", linespacing=1.42)
    return fig


def _fig_inventory_summary(inv: dict[str, Any]) -> plt.Figure:
    fig = plt.figure(figsize=(11.69, 8.27))
    fig.patch.set_facecolor("#f8fafc")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.text(0.05, 0.90, "Инвентаризация датасета (накопительное хранилище)",
            fontsize=16, fontweight="bold")
    if not inv or "sections" not in inv:
        ax.text(0.05, 0.70, "Нет данных инвентаризации (docker/postgres недоступен)", fontsize=11)
        return fig
    s = inv["sections"]
    t = inv.get("totals", {})
    lines = [
        f"Всего строк в слоях: {t.get('rows', 0):,}".replace(",", " "),
        f"Параметров (колонки + JSON-ключи + типы событий): {t.get('parameters', 0):,}".replace(",", " "),
        "",
        f"Поведение (behavior_events): {s['behavior_events']['rows']:,} событий".replace(",", " "),
        f"Бизнес-события (frontend_events): {s['frontend_events']['rows']:,}, типов {s['frontend_events']['event_names']}".replace(",", " "),
        f"Визиты Logs API (raw_metrika_visits): {s['raw_metrika_visits']['rows']:,}".replace(",", " "),
        f"Фразы привлечения (metrika_search_phrases): {s['metrika_search_phrases']['rows']:,}, "
        f"уник. {s['metrika_search_phrases'].get('distinct_phrases', 0):,}".replace(",", " "),
        f"Страницы/день (metrika_daily_page_metrics): {s['metrika_daily_page_metrics']['rows']:,}".replace(",", " "),
        f"Вебмастер в БД: {s['webmaster_search_queries']['rows']:,}".replace(",", " "),
        f"Гипотезы: открытых {s['hypotheses']['by_verdict']['open']}, "
        f"подтверждено {s['hypotheses']['by_verdict']['true']}, "
        f"опровергнуто {s['hypotheses']['by_verdict']['false']}",
        f"Ядро: пользователей {s['core']['users']:,}, макро-точек {s['core']['indicator_points']:,}, "
        f"региональных {s['core']['region_points']:,}".replace(",", " "),
    ]
    ax.text(0.05, 0.78, "\n".join(lines), fontsize=10.5, va="top", linespacing=1.45)
    return fig


def _fig_first_party_summary(fp: dict[str, Any], day: date) -> plt.Figure:
    fig = plt.figure(figsize=(11.69, 8.27))
    fig.patch.set_facecolor("#f8fafc")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.text(0.05, 0.90, f"First-party за {day.strftime('%d.%m.%Y')}",
            fontsize=16, fontweight="bold")
    if fp.get("error"):
        ax.text(0.05, 0.70, f"Ошибка: {fp['error']}", fontsize=10, color="#DC2626")
        return fig
    fe = fp.get("frontend", {})
    be = fp.get("behavior", {})
    us = fp.get("users", {})
    lines = [
        f"События фронта (track.js): {fe.get('total', 0)}",
        f"  гость: {fe.get('by_audience', {}).get('guest', 0)} · "
        f"авторизован: {fe.get('by_audience', {}).get('authed', 0)}",
        f"  сессий гостей: {fe.get('audience', {}).get('guest_sessions', 0)} · "
        f"активных user_id: {fe.get('audience', {}).get('authed_active', 0)}",
        f"  внутренний поиск (уник. запросов): {len(fe.get('search_queries', []))}",
        f"  скачиваний: {sum(d.get('count', 0) for d in fe.get('downloads', []))}",
        "",
        f"Поведение (behavior.js): {sum(be.get('by_type', {}).values())} событий",
    ]
    for et, n in sorted(be.get("by_type", {}).items(), key=lambda x: -x[1]):
        lines.append(f"  {et}: {n}")
    lines += [
        "",
        f"Пользователи: всего {us.get('total', 0)}, новых за день {us.get('new', 0)}",
    ]
    ax.text(0.05, 0.78, "\n".join(lines), fontsize=10.5, va="top", linespacing=1.4)
    return fig


def _fig_warehouse_summary(wh: dict[str, Any], day: date) -> plt.Figure:
    fig = plt.figure(figsize=(11.69, 8.27))
    fig.patch.set_facecolor("#f8fafc")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.text(0.05, 0.90, f"Склад Метрики за {day.strftime('%d.%m.%Y')}",
            fontsize=16, fontweight="bold")
    raw = wh.get("raw_visits", {})
    lines = [
        f"Повизитных строк Logs API: {raw.get('total', 0)}",
        f"Фраз в агрегате metrika_search_phrases: {len(wh.get('search_phrases', []))}",
        f"Строк metrika_daily_page_metrics: {len(wh.get('page_metrics', []))}",
        "",
        "Снапшоты Reporting API в БД:",
    ]
    for key in ("traffic_sources", "search_engines", "referrers", "ad_campaigns"):
        rows = wh.get(key) or []
        lines.append(f"  {key}: {len(rows)} строк")
    if raw.get("total", 0) == 0 and not any(wh.get(k) for k in ("search_phrases", "page_metrics")):
        lines.append("")
        lines.append("Пусто — утренний синк (08:20 МСК) ещё не отработал или день неполный.")
    ax.text(0.05, 0.78, "\n".join(lines), fontsize=10.5, va="top", linespacing=1.45)
    return fig


def _fig_hypotheses_list(hypotheses: list[dict]) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(11.69, 8.27))
    fig.patch.set_facecolor("#fafafa")
    ax.axis("off")
    ax.set_title("Гипотезы Пульса (булев слой знаний)", fontweight="bold", fontsize=12, loc="left")
    if not hypotheses:
        ax.text(0.5, 0.5, "Гипотез пока нет", ha="center", fontsize=12)
        return fig
    cells = []
    for h in hypotheses:
        v = h.get("verdict")
        verdict = "открыта" if v is None else ("да" if v else "нет")
        cells.append([
            verdict,
            str(h.get("confidence") or "—"),
            (h.get("statement") or "")[:200],
        ])
    table = ax.table(
        cellText=cells,
        colLabels=["Вердикт", "Увер.", "Утверждение"],
        loc="center", cellLoc="left",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(7)
    table.scale(1, 1.25)
    return fig


def _fig_data_layers_explainer() -> plt.Figure:
    fig = plt.figure(figsize=(11.69, 8.27))
    fig.patch.set_facecolor("#f8fafc")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.text(0.05, 0.90, "Поисковые данные: Метрика API × Вебмастер × наш склад",
            fontsize=16, fontweight="bold")
    lines = [
        "Яндекс.Метрика API — визиты и фразы referrer (если переданы).",
        "Склад Logs API — повизитные фразы из raw_metrika_visits (полнее при синке).",
        "Внутренний поиск сайта — frontend_events search_query (только у нас).",
        "Вебмастер — показы/клики в выдаче Яндекса (лаг 1–3 дня).",
        "",
        "Пример: «клубника Тульская область» — визит в Метрике 03.07;",
        "в Вебмастере появится после индексации региональных URL.",
        "",
        "Ниже — сопоставление Метрика × Вебмастер и полные таблицы каждого слоя.",
    ]
    ax.text(0.05, 0.78, "\n".join(lines), fontsize=11, va="top", linespacing=1.45)
    return fig


def _fig_webmaster_summary(
    wm: dict[str, Any],
    period_label: str,
    report_day: date,
) -> plt.Figure:
    fig = plt.figure(figsize=(11.69, 8.27))
    fig.patch.set_facecolor("#f8fafc")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.text(0.05, 0.88, f"Яндекс.Вебмастер · {period_label}",
            fontsize=16, fontweight="bold")
    err = wm.get("error")
    if err:
        ax.text(0.05, 0.70, f"Ошибка загрузки: {err}", fontsize=11, color="#DC2626")
        return fig
    lines = [
        f"Период API: {wm.get('date_from')} — {wm.get('date_to')}",
        f"Запросов в выдаче (count): {wm.get('count', 0):,} · выгружено строк: {wm.get('fetched', 0):,}".replace(",", " "),
        f"Сумма показов: {wm.get('total_shows', 0):,} · кликов: {wm.get('total_clicks', 0):,}".replace(",", " "),
        "",
        f"Отчётный день: {report_day.strftime('%d.%m.%Y')}.",
        "Вебмастер обычно отстаёт на 1–3 дня — срез «только за отчётный день» часто пуст.",
        "В PDF ниже — полный период 2 недели и кумулятив с 3 июня (все строки).",
    ]
    ax.text(0.05, 0.72, "\n".join(lines), fontsize=11, va="top", linespacing=1.5)
    return fig


def _fig_layer_compare_summary(compare: dict[str, Any], period_label: str) -> plt.Figure:
    fig = plt.figure(figsize=(11.69, 8.27))
    fig.patch.set_facecolor("#f8fafc")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.text(0.05, 0.88, f"Сопоставление слоёв · {period_label}",
            fontsize=16, fontweight="bold")
    lines = [
        f"Уникальных фраз в Метрике: {compare['metrika_distinct']}",
        f"Уникальных запросов в Вебмастере: {compare['webmaster_distinct']}",
        f"Пересечение (одна и та же фраза): {len(compare['both'])}",
        f"Только Метрика (визит с фразой, нет в Вебмастере за период): {len(compare['only_metrika'])}",
        f"Только Вебмастер (показ в выдаче, нет визита с фразой в Метрике): {len(compare['only_webmaster'])}",
        "",
        "Далее — полные таблицы пересечения и «только в одном слое».",
    ]
    ax.text(0.05, 0.72, "\n".join(lines), fontsize=11, va="top", linespacing=1.5)
    return fig


def _fig_fetch_completeness_audit(audit: dict[str, Any], day: date) -> plt.Figure:
    fig = plt.figure(figsize=(11.69, 8.27))
    fig.patch.set_facecolor("#f8fafc")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.text(0.05, 0.90, f"Проверка полноты выгрузки · {day.strftime('%d.%m.%Y')}",
            fontsize=16, fontweight="bold")
    lines = [
        "Каждый источник: выгружено строк vs ожидание API/БД. «Полная» = все строки получены.",
        "",
    ]
    for block in audit.get("sources", []):
        status = "полная" if block.get("complete") else "ПРОВЕРИТЬ"
        lines.append(
            f"{block['name']}: {block.get('fetched', 0)} уник. · {status}"
            + (f" (API total_rows={block.get('api_total_rows')})" if block.get("api_total_rows") is not None else "")
            + (f" · {block.get('note', '')}" if block.get("note") else "")
        )
    lines += [
        "",
        f"За день {day.strftime('%d.%m.%Y')}: только уникальные запросы этого дня.",
        f"В конце отчёта: уникальные за период {BASELINE_START.strftime('%d.%m.%Y')} – {day.strftime('%d.%m.%Y')}.",
    ]
    ax.text(0.05, 0.78, "\n".join(lines), fontsize=10, va="top", linespacing=1.4)
    return fig


def _fig_unique_queries_intro(
    scope: str,
    period_label: str,
    counts: dict[str, int],
) -> plt.Figure:
    fig = plt.figure(figsize=(11.69, 8.27))
    fig.patch.set_facecolor("#f8fafc")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    title = f"Уникальные запросы · {scope} · {period_label}"
    ax.text(0.05, 0.88, title, fontsize=16, fontweight="bold")
    lines = ["Счётчик = число уникальных текстов запроса (не визитов).", ""]
    for k, v in counts.items():
        lines.append(f"  {k}: {v}")
    ax.text(0.05, 0.72, "\n".join(lines), fontsize=11, va="top", linespacing=1.45)
    return fig


def _fig_channels_stacked(by_day: dict[str, dict[str, int]], highlight: str) -> plt.Figure:
    days = sorted(by_day)
    dates = [date.fromisoformat(d) for d in days]
    channels = [c for c in CHANNEL_ORDER if any(c in by_day[d] for d in days)]
    channels += sorted({ch for d in days for ch in by_day[d]} - set(channels))

    fig, ax = plt.subplots(figsize=(11.69, 8.27))
    fig.patch.set_facecolor("#fafafa")
    bottom = np.zeros(len(days))
    for ch in channels:
        vals = np.array([by_day[d].get(ch, 0) for d in days])
        ax.bar(dates, vals, bottom=bottom, width=0.7, label=CHANNEL_RU.get(ch, ch),
               color=CHANNEL_COLORS.get(ch, "#94a3b8"), alpha=0.88)
        bottom += vals

    hl = date.fromisoformat(highlight)
    ax.axvline(hl, color="#DC2626", linestyle="--", linewidth=1.5)
    ax.set_title("Каналы по дням (2 недели до отчётного дня)", fontweight="bold", fontsize=13)
    ax.set_ylabel("Визиты")
    ax.legend(loc="upper left", fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")
    ax.grid(True, alpha=0.2, axis="y")
    plt.tight_layout()
    return fig


def sitemap_note_for(day: date) -> str:
    # Региональный sitemap выкатили 3 июля 2026 (~40 849 URL)
    if day < date(2026, 7, 3):
        return "Sitemap: ~2 420 URL (без регионального блока)"
    return "Sitemap: ~43 269 URL (+40 849 региональных страниц с 03.07)"


def build_report(day: date, launch: time | None, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    two_weeks_start = day - timedelta(days=13)

    users, visits, pageviews = fetch_totals(day, day)
    cum_users = fetch_cumulative_users(day)
    _, cum_visits, _ = fetch_totals(BASELINE_START, day)
    channels = fetch_channels_detailed(day, day)
    search_visits = fetch_search_channel_visits(day)
    phrases_reporting, meta_phrases_day = fetch_search_phrases_reporting(day, day)
    phrases_warehouse = fetch_phrases_warehouse(day)
    phrases_day = merge_search_phrases(phrases_reporting, phrases_warehouse)
    pages_day = fetch_pages(day, day)
    phrases_cum_reporting, meta_phrases_period = fetch_search_phrases_reporting(BASELINE_START, day)
    phrases_cum = merge_search_phrases(phrases_cum_reporting)
    pages_cum = fetch_pages(BASELINE_START, day)
    minute_rows = fetch_by_minute(day)
    growth_rows = fetch_daily_series(BASELINE_START, day)
    daily_engagement = fetch_daily_engagement(BASELINE_START, day)
    channels_2w = fetch_daily_channels(two_weeks_start, day)
    devices_day = fetch_devices(day, day)
    search_engines_day = fetch_search_engines(day, day)
    referrers_day = fetch_referrers(day, day)

    wm_day = fetch_webmaster_queries(day, day)
    wm_cum = fetch_webmaster_queries(BASELINE_START, day)
    wm_day_queries = wm_day.get("queries") or []
    wm_cum_queries = wm_cum.get("queries") or []
    compare_period = compare_phrase_layers(phrases_cum, wm_cum_queries)
    fp_bundle = fetch_first_party_bundle(day, BASELINE_START)
    fp_frontend = fp_bundle.get("frontend") or {}
    fp_behavior = fp_bundle.get("behavior") or {}
    fp_warehouse = fp_bundle.get("warehouse") or {}
    fp_inventory = fp_bundle.get("inventory") or {}
    fp_hypotheses = fp_bundle.get("hypotheses") or []

    fp_period = fp_bundle.get("period") or {}
    period_internal = fp_period.get("internal_search") or []
    period_wh_phrases = fp_period.get("warehouse_phrases") or []
    period_wh_table = fp_period.get("metrika_search_phrases") or []

    fetch_audit = {
        "sources": [
            {
                "name": "Метрика API · запросы за день",
                **meta_phrases_day,
                "fetched": len(phrases_day),
                "note": f"merged reporting {len(phrases_reporting)} + склад {len(phrases_warehouse)}",
            },
            {
                "name": f"Метрика API · запросы за период {BASELINE_START.isoformat()}–{day.isoformat()}",
                **meta_phrases_period,
                "fetched": len(phrases_cum),
                "note": f"API строк {meta_phrases_period.get('fetched_rows', '?')} → {len(phrases_cum)} уник. текста",
            },
            {
                "name": "Вебмастер · за день",
                "fetched": wm_day.get("fetched", 0),
                "api_total_rows": wm_day.get("count"),
                "complete": wm_day.get("fetched", 0) >= wm_day.get("count", 0) or wm_day.get("fetched", 0) == 0,
                "note": "лаг 1–3 дня" if wm_day.get("fetched", 0) == 0 else "",
            },
            {
                "name": f"Вебмастер · период {BASELINE_START.isoformat()}–{day.isoformat()}",
                "fetched": wm_cum.get("fetched", 0),
                "api_total_rows": wm_cum.get("count"),
                "complete": True,
            },
            {
                "name": "Внутренний поиск · за день",
                "fetched": len(fp_frontend.get("search_queries") or []),
                "complete": True,
            },
            {
                "name": f"Внутренний поиск · период",
                "fetched": len(period_internal),
                "complete": True,
            },
            {
                "name": "Склад Logs API · фразы за день",
                "fetched": len((fp_warehouse.get("raw_visits") or {}).get("phrases") or []),
                "complete": True,
            },
            {
                "name": f"Склад Logs API · фразы за период",
                "fetched": len(period_wh_phrases),
                "complete": True,
            },
        ],
    }

    phrase_cols = [
        ("Запрос", "name", lambda r: r["name"]),
        ("Виз.", "visits", lambda r: str(r["visits"])),
        ("Уник.", "users", lambda r: str(r.get("users", ""))),
        ("ПС", "search_engine", lambda r: str(r.get("search_engine") or "—")),
        ("Доля %", "share_pct", lambda r: str(r.get("share_pct", ""))),
    ]
    page_cols = [
        ("URL", "name", lambda r: r["name"]),
        ("Виз.", "visits", lambda r: str(r["visits"])),
        ("Уник.", "users", lambda r: str(r.get("users", ""))),
        ("Просм.", "pageviews", lambda r: str(r.get("pageviews", ""))),
        ("Доля %", "share_pct", lambda r: str(r.get("share_pct", ""))),
    ]
    wm_cols = [
        ("Запрос", "query", lambda r: r["query"]),
        ("Показы", "shows", lambda r: str(r["shows"])),
        ("Клики", "clicks", lambda r: str(r["clicks"])),
        ("CTR %", "ctr_pct", lambda r: str(r.get("ctr_pct", ""))),
        ("Поз.", "position", lambda r: str(r.get("position") if r.get("position") is not None else "—")),
        ("Доля %", "share_pct", lambda r: str(r.get("share_pct", ""))),
    ]
    compare_both_cols = [
        ("Запрос", "query", lambda r: r["query"]),
        ("Метрика виз.", "metrika_visits", lambda r: str(r["metrika_visits"])),
        ("ВМ показы", "webmaster_shows", lambda r: str(r["webmaster_shows"])),
        ("ВМ клики", "webmaster_clicks", lambda r: str(r["webmaster_clicks"])),
        ("ВМ поз.", "webmaster_position", lambda r: str(
            r["webmaster_position"] if r["webmaster_position"] is not None else "—")),
    ]
    compare_only_m_cols = [
        ("Запрос", "query", lambda r: r["query"]),
        ("Визиты Метрика", "visits", lambda r: str(r["visits"])),
    ]
    compare_only_w_cols = [
        ("Запрос", "query", lambda r: r["query"]),
        ("Показы ВМ", "shows", lambda r: str(r["shows"])),
        ("Клики ВМ", "clicks", lambda r: str(r["clicks"])),
    ]
    fe_name_cols = [
        ("Событие", "name", lambda r: r["name"]),
        ("Кол-во", "count", lambda r: str(r["count"])),
    ]
    internal_search_cols = [
        ("Запрос", "query", lambda r: r["query"]),
        ("Поисков", "count", lambda r: str(r["count"])),
        ("0 рез.", "zero_results", lambda r: str(r.get("zero_results", 0))),
    ]
    wh_phrase_cols = [
        ("Фраза", "phrase", lambda r: r["phrase"]),
        ("ПС", "search_engine", lambda r: str(r.get("search_engine") or "—")),
        ("Виз.", "visits", lambda r: str(r["visits"])),
        ("Лендинг", "landing_url", lambda r: str(r.get("landing_url") or "—")[:80]),
    ]
    wh_page_cols = [
        ("URL", "url", lambda r: _short_url(r["url"], 70)),
        ("Источник", "source", lambda r: str(r.get("source") or "—")),
        ("Виз.", "visits", lambda r: str(r["visits"])),
        ("Уник.", "users", lambda r: str(r["users"])),
        ("Просм.", "pageviews", lambda r: str(r["pageviews"])),
    ]
    raw_phrase_cols = [
        ("Фраза", "phrase", lambda r: r["phrase"]),
        ("ПС", "search_engine", lambda r: str(r.get("search_engine") or "—")),
        ("Виз.", "visits", lambda r: str(r["visits"])),
    ]

    payload = {
        "day": day.isoformat(),
        "launch_msk": launch.isoformat() if launch else None,
        "kpi": {"users": users, "visits": visits, "pageviews": pageviews},
        "cumulative_from_baseline": {"users": cum_users, "visits": cum_visits},
        "channels": channels[1],
        "search_coverage": {
            "search_channel_visits": search_visits,
            "phrases_with_visits": sum(p["visits"] for p in phrases_day),
            "distinct_phrases": len(phrases_day),
            "reporting_api_phrases": len(phrases_reporting),
            "warehouse_phrases": len(phrases_warehouse),
        },
        "search_phrases_day": phrases_day,
        "search_phrases_day_reporting": phrases_reporting,
        "search_phrases_day_warehouse": phrases_warehouse,
        "search_phrases_period": phrases_cum,
        "search_phrases_period_meta": meta_phrases_period,
        "pages_day": pages_day,
        "pages_period": pages_cum,
        "devices_day": devices_day,
        "search_engines_day": search_engines_day,
        "referrers_day": referrers_day,
        "counts": {
            "unique_queries_day": len(phrases_day),
            "unique_queries_period": len(phrases_cum),
            "pages_day": len(pages_day),
            "pages_period": len(pages_cum),
            "webmaster_day": len(wm_day_queries),
            "webmaster_period": len(wm_cum_queries),
            "internal_search_day": len(fp_frontend.get("search_queries") or []),
            "internal_search_period": len(period_internal),
        },
        "webmaster_day": wm_day,
        "webmaster_period": {k: wm_cum.get(k) for k in wm_cum if k != "queries"},
        "webmaster_period_queries": wm_cum_queries,
        "layer_compare_period": compare_period,
        "period_first_party": fp_period,
        "fetch_audit": fetch_audit,
        "first_party": fp_bundle,
        "sitemap": sitemap_note_for(day),
    }
    (out_dir / "report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    pdf_path = out_dir / f"report-{day.isoformat()}.pdf"
    period_cum = f"{BASELINE_START.strftime('%d.%m')} – {day.strftime('%d.%m.%Y')}"
    day_label = day.strftime("%d.%m.%Y")
    toc = [
        "Архитектура данных (Яндекс + first-party)",
        "Инвентаризация датасета + проверка полноты выгрузки",
        "Титул и KPI дня (Метрика API)",
        f"Уникальные запросы · только {day_label} (все слои)",
        "First-party, склад, трафик, каналы за день",
        "Рост и каналы за 2 недели (контекст)",
        f"——— КОНЕЦ: уникальные запросы за период {period_cum} ———",
        "Гипотезы Пульса",
    ]

    day_query_counts = {
        "Метрика API": len(phrases_day),
        "Вебмастер": len(wm_day_queries),
        "Внутренний поиск": len(fp_frontend.get("search_queries") or []),
        "Склад Logs API": len((fp_warehouse.get("raw_visits") or {}).get("phrases") or []),
    }
    period_query_counts = {
        "Метрика API": len(phrases_cum),
        "Вебмастер": len(wm_cum_queries),
        "Внутренний поиск": len(period_internal),
        "Склад Logs API": len(period_wh_phrases),
        "Склад metrika_search_phrases": len(period_wh_table),
    }

    with PdfPages(pdf_path) as pdf:
        _pdf_add(pdf, _fig_report_index(day, toc))
        _pdf_add(pdf, _fig_data_stack_explainer())
        _pdf_add(pdf, _fig_inventory_summary(fp_inventory))
        _pdf_add(pdf, _fig_fetch_completeness_audit(fetch_audit, day))
        _pdf_add(pdf, _fig_title_page(
            day, users, visits, pageviews, channels[1], launch,
            cum_users, cum_visits, sitemap_note_for(day),
        ))
        _pdf_add(pdf, _fig_first_party_summary(fp_bundle, day))
        _pdf_add(pdf, _fig_unique_queries_intro("только за день", day_label, day_query_counts))
        _pdf_add(pdf, _fig_warehouse_summary(fp_warehouse, day))

        if fp_frontend.get("by_name"):
            fe_rows = _rows_with_visits(fp_frontend["by_name"], "name")
            _pdf_add(pdf, _fig_hbar_pages(
                fe_rows, f"События фронта (track.js) · {day.strftime('%d.%m.%Y')}",
                formatter=lambda x: x,
            ))
            _pdf_add(pdf, _fig_data_table_pages(
                fp_frontend["by_name"],
                f"События фронта (таблица) · {day.strftime('%d.%m.%Y')}",
                fe_name_cols,
            ))
        if fp_frontend.get("search_queries"):
            sq_rows = _rows_with_visits(fp_frontend["search_queries"], "query")
            _pdf_add(pdf, _fig_hbar_pages(
                sq_rows,
                f"Внутренний поиск · уникальные · только {day_label}",
                name_key="name", formatter=lambda x: _short_phrase(x, 56),
                extra_cols=[("0 рез.", "zero_results")],
            ))
            _pdf_add(pdf, _fig_data_table_pages(
                fp_frontend["search_queries"],
                f"Внутренний поиск (таблица) · только {day_label}",
                internal_search_cols,
            ))
        if fp_frontend.get("regions"):
            reg_rows = _rows_with_visits(
                [{"name": r["slug"], "count": r["count"]} for r in fp_frontend["regions"]], "name")
            _pdf_add(pdf, _fig_hbar_pages(
                reg_rows, f"Просмотры регионов (frontend) · {day.strftime('%d.%m.%Y')}",
                formatter=lambda x: x,
            ))

        if fp_behavior.get("by_type"):
            bt_rows = _rows_with_visits(
                [{"name": k, "count": v} for k, v in fp_behavior["by_type"].items()], "name")
            _pdf_add(pdf, _fig_hbar_pages(
                bt_rows, f"Поведение по типам · {day.strftime('%d.%m.%Y')}", formatter=lambda x: x,
            ))
        if fp_behavior.get("pageviews"):
            pv_rows = _rows_with_visits(fp_behavior["pageviews"], "page")
            _pdf_add(pdf, _fig_hbar_pages(
                pv_rows, f"Поведение: pageview по страницам · {day.strftime('%d.%m.%Y')}",
                name_key="name", formatter=lambda x: _short_url(x, 56),
            ))
        if fp_behavior.get("clicks"):
            cl_rows = _rows_with_visits(fp_behavior["clicks"], "element")
            _pdf_add(pdf, _fig_hbar_pages(
                cl_rows, f"Поведение: клики · {day.strftime('%d.%m.%Y')}",
                name_key="name", formatter=lambda x: _short_phrase(x, 48),
                extra_cols=[("текст", "text")],
            ))
        if fp_behavior.get("dwell"):
            _pdf_add(pdf, _fig_data_table_pages(
                fp_behavior["dwell"],
                f"Dwell / скролл по страницам · {day.strftime('%d.%m.%Y')}",
                [
                    ("Страница", "page", lambda r: _short_url(r["page"], 50)),
                    ("Сессий", "visits", lambda r: str(r["visits"])),
                    ("Сек.", "avg_seconds", lambda r: str(r["avg_seconds"])),
                    ("Скролл %", "avg_scroll_pct", lambda r: str(r["avg_scroll_pct"])),
                ],
            ))

        for wh_key, wh_title in (
            ("traffic_sources", "Склад: источники трафика"),
            ("search_engines", "Склад: поисковые системы"),
            ("referrers", "Склад: рефереры"),
            ("ad_campaigns", "Склад: рекламные кампании"),
        ):
            rows = fp_warehouse.get(wh_key) or []
            if rows:
                wh_vis = _rows_with_visits(rows, "name", "visits")
                _pdf_add(pdf, _fig_hbar_pages(
                    wh_vis, f"{wh_title} · {day.strftime('%d.%m.%Y')}", formatter=lambda x: x,
                    extra_cols=[("уник.", "users")],
                ))
        raw_vis = fp_warehouse.get("raw_visits") or {}
        if raw_vis.get("phrases"):
            rp = _rows_with_visits(raw_vis["phrases"], "phrase", "visits")
            _pdf_add(pdf, _fig_hbar_pages(
                rp, f"Склад Logs API · уникальные фразы · только {day_label}",
                name_key="name", formatter=lambda x: _short_phrase(x, 52),
                extra_cols=[("ПС", "search_engine")],
            ))
            _pdf_add(pdf, _fig_data_table_pages(
                raw_vis["phrases"], f"Logs API фразы · только {day_label}", raw_phrase_cols,
            ))
        if fp_warehouse.get("search_phrases"):
            wh_sp = _rows_with_visits(
                [{"name": r["phrase"], "visits": r["visits"], **r} for r in fp_warehouse["search_phrases"]],
                "name", "visits",
            )
            _pdf_add(pdf, _fig_hbar_pages(
                wh_sp, f"Склад: metrika_search_phrases · {day.strftime('%d.%m.%Y')}",
                formatter=lambda x: _short_phrase(x, 52),
            ))
            _pdf_add(pdf, _fig_data_table_pages(fp_warehouse["search_phrases"], "Склад фразы (таблица)", wh_phrase_cols))
        if fp_warehouse.get("page_metrics"):
            wh_pg = _rows_with_visits(
                [{"name": r["url"], "visits": r["visits"], **r} for r in fp_warehouse["page_metrics"]],
                "name", "visits",
            )
            _pdf_add(pdf, _fig_hbar_pages(
                wh_pg, f"Склад: страницы · {day.strftime('%d.%m.%Y')}",
                formatter=lambda x: _short_url(x, 52),
            ))
            _pdf_add(pdf, _fig_data_table_pages(fp_warehouse["page_metrics"], "Склад страницы (таблица)", wh_page_cols))

        _pdf_add(pdf, _fig_intraday(minute_rows, day, launch))
        _pdf_add(pdf, _fig_hourly(minute_rows, day, launch))
        _pdf_add(pdf, _fig_channels_pie(channels[1], f"Каналы захода · {day.strftime('%d.%m.%Y')}"))
        _pdf_add(pdf, _fig_channels_detail(channels[1], f"Каналы — все метрики · {day.strftime('%d.%m.%Y')}"))
        _pdf_add(pdf, _fig_phrases_coverage(day, search_visits, phrases_day, len(phrases_reporting)))

        if devices_day:
            _pdf_add(pdf, _fig_hbar_pages(devices_day, f"Устройства · {day.strftime('%d.%m.%Y')}",
                                          formatter=lambda x: x, extra_cols=[("уник.", "users")]))
        if search_engines_day:
            _pdf_add(pdf, _fig_hbar_pages(search_engines_day, f"Поисковые системы · {day.strftime('%d.%m.%Y')}",
                                          formatter=lambda x: x))
        if referrers_day:
            _pdf_add(pdf, _fig_hbar_pages(referrers_day, f"Переходы с сайтов · {day.strftime('%d.%m.%Y')}",
                                          formatter=lambda x: x))

        if phrases_day:
            n = len(phrases_day)
            _pdf_add(pdf, _fig_hbar_pages(
                phrases_day,
                f"Метрика API · {n} уник. запросов · только {day_label}",
                formatter=lambda x: x,
                extra_cols=[("ПС", "search_engine")],
            ))
            _pdf_add(pdf, _fig_data_table_pages(
                phrases_day,
                f"Метрика API · только {day_label} · {n} уник.",
                phrase_cols,
            ))
        _pdf_add(pdf, _fig_webmaster_summary(wm_day, f"только {day_label}", day))
        if wm_day_queries:
            _pdf_add(pdf, _fig_hbar_pages(
                wm_day_queries,
                f"Вебмастер · {len(wm_day_queries)} уник. · только {day_label}",
                name_key="query", value_key="shows",
                formatter=lambda x: _short_phrase(x, 56),
                extra_cols=[("кл.", "clicks"), ("поз.", "position")],
            ))
            _pdf_add(pdf, _fig_data_table_pages(
                wm_day_queries, f"Вебмастер · только {day_label}", wm_cols,
            ))
        if pages_day:
            _pdf_add(pdf, _fig_hbar_pages(
                pages_day,
                f"Страницы входа (график) · {day.strftime('%d.%m.%Y')}",
                formatter=_short_url,
                extra_cols=[("просм.", "pageviews")],
            ))
            _pdf_add(pdf, _fig_data_table_pages(
                pages_day,
                f"Страницы входа (таблица) · {day.strftime('%d.%m.%Y')}",
                page_cols,
            ))

        _pdf_add(pdf, _fig_growth(growth_rows, day, daily_engagement))
        _pdf_add(pdf, _fig_channels_stacked(channels_2w, day.isoformat()))
        _pdf_add(pdf, _fig_channel_daily_matrix(channels_2w, day.isoformat()))

        # --- Уникальные запросы за период выборки (только в конце) ---
        _pdf_add(pdf, _fig_unique_queries_intro("период выборки", period_cum, period_query_counts))
        _pdf_add(pdf, _fig_data_layers_explainer())

        if phrases_cum:
            n = len(phrases_cum)
            _pdf_add(pdf, _fig_hbar_pages(
                phrases_cum,
                f"Метрика API · {n} уник. · период {period_cum}",
                formatter=lambda x: x,
                extra_cols=[("ПС", "search_engine")],
            ))
            _pdf_add(pdf, _fig_data_table_pages(
                phrases_cum,
                f"Метрика API · период {period_cum} · {n} уник.",
                phrase_cols,
            ))
        if period_internal:
            pi_rows = _rows_with_visits(period_internal, "query")
            _pdf_add(pdf, _fig_hbar_pages(
                pi_rows,
                f"Внутренний поиск · {len(period_internal)} уник. · период {period_cum}",
                name_key="name", formatter=lambda x: _short_phrase(x, 56),
                extra_cols=[("0 рез.", "zero_results")],
            ))
            _pdf_add(pdf, _fig_data_table_pages(
                period_internal, f"Внутренний поиск · период {period_cum}", internal_search_cols,
            ))
        if period_wh_phrases:
            pwp = _rows_with_visits(period_wh_phrases, "phrase", "visits")
            _pdf_add(pdf, _fig_hbar_pages(
                pwp,
                f"Склад Logs API · {len(period_wh_phrases)} уник. · период {period_cum}",
                name_key="name", formatter=lambda x: _short_phrase(x, 52),
                extra_cols=[("ПС", "search_engine")],
            ))
            _pdf_add(pdf, _fig_data_table_pages(
                period_wh_phrases, f"Logs API · период {period_cum}", raw_phrase_cols,
            ))
        if period_wh_table:
            _pdf_add(pdf, _fig_data_table_pages(
                period_wh_table,
                f"Склад metrika_search_phrases · период {period_cum}",
                [
                    ("Фраза", "phrase", lambda r: r["phrase"]),
                    ("ПС", "search_engine", lambda r: str(r.get("search_engine") or "—")),
                    ("Виз.", "visits", lambda r: str(r["visits"])),
                    ("Дней", "days_seen", lambda r: str(r.get("days_seen", ""))),
                ],
            ))
        if pages_cum:
            _pdf_add(pdf, _fig_hbar_pages(
                pages_cum,
                f"Страницы входа · период {period_cum}",
                formatter=_short_url,
                extra_cols=[("просм.", "pageviews")],
            ))
            _pdf_add(pdf, _fig_data_table_pages(
                pages_cum, f"Страницы входа · период {period_cum}", page_cols,
            ))

        _pdf_add(pdf, _fig_webmaster_summary(wm_cum, f"период {period_cum}", day))
        if wm_cum_queries:
            _pdf_add(pdf, _fig_hbar_pages(
                wm_cum_queries,
                f"Вебмастер · {len(wm_cum_queries)} уник. · период {period_cum}",
                name_key="query", value_key="shows",
                formatter=lambda x: _short_phrase(x, 56),
                extra_cols=[("кл.", "clicks")],
            ))
            _pdf_add(pdf, _fig_data_table_pages(
                wm_cum_queries, f"Вебмастер · период {period_cum}", wm_cols,
            ))

        _pdf_add(pdf, _fig_layer_compare_summary(compare_period, period_cum))
        if compare_period["both"]:
            _pdf_add(pdf, _fig_data_table_pages(
                compare_period["both"],
                f"Пересечение Метрика × Вебмастер · период {period_cum}",
                compare_both_cols,
            ))
        if compare_period["only_metrika"]:
            _pdf_add(pdf, _fig_data_table_pages(
                compare_period["only_metrika"],
                f"Только Метрика · период {period_cum}",
                compare_only_m_cols,
            ))
        if compare_period["only_webmaster"]:
            _pdf_add(pdf, _fig_data_table_pages(
                compare_period["only_webmaster"],
                f"Только Вебмастер · период {period_cum}",
                compare_only_w_cols,
            ))

        _pdf_add(pdf, _fig_hypotheses_list(fp_hypotheses))

    # PNG — полные графики (первая страница каждого среза)
    _fig_intraday(minute_rows, day, launch).savefig(out_dir / "01-intraday.png", dpi=150, bbox_inches="tight")
    plt.close()
    _fig_hourly(minute_rows, day, launch).savefig(out_dir / "01b-hourly.png", dpi=150, bbox_inches="tight")
    plt.close()
    if phrases_day:
        (out_dir / "phrases-day-full.json").write_text(
            json.dumps(phrases_day, ensure_ascii=False, indent=2), encoding="utf-8")
        hbar_phr = _fig_hbar_pages(phrases_day, f"Фразы {day}", formatter=lambda x: x)
        hbar_phr[0].savefig(out_dir / "02-phrases-day.png", dpi=150, bbox_inches="tight")
        _close_figs(hbar_phr)
    if pages_day:
        hbar_pg = _fig_hbar_pages(pages_day, f"Страницы {day}", formatter=_short_url)
        hbar_pg[0].savefig(out_dir / "03-pages-day.png", dpi=150, bbox_inches="tight")
        _close_figs(hbar_pg)

    return pdf_path


def main() -> None:
    p = argparse.ArgumentParser(description="PDF-отчёт трафика за день")
    p.add_argument("--day", required=True, help="YYYY-MM-DD")
    p.add_argument("--launch", default="14:00", help="Время запуска сервиса МСК HH:MM (пусто = без отметки)")
    p.add_argument("--open", action="store_true", help="Открыть PDF на macOS")
    args = p.parse_args()

    day = date.fromisoformat(args.day)
    launch: time | None = None
    if args.launch:
        h, m = args.launch.split(":")
        launch = time(int(h), int(m))

    out_dir = ROOT / "analytics" / "reports" / day.isoformat()
    pdf = build_report(day, launch, out_dir)
    print(f"PDF → {pdf}")
    print(f"JSON → {out_dir / 'report.json'}")

    if args.open and sys.platform == "darwin":
        subprocess.run(["open", str(pdf)], check=False)


if __name__ == "__main__":
    main()

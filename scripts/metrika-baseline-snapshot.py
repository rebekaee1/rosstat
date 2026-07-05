#!/usr/bin/env python3
"""Снимок базовой линии трафика из Яндекс.Метрики (быстрый доступ).

Старт сравнения: 3 июня 2026. Артефакты → analytics/baseline/2026-06-03-start/.

Использование (нужен RUSTATS_YANDEX_METRIKA_READ_TOKEN в env или backend/.env):
  python scripts/metrika-baseline-snapshot.py
  python scripts/metrika-baseline-snapshot.py --intraday 2026-07-03
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.request
from datetime import date, datetime
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analytics" / "baseline" / "2026-06-03-start"
COUNTER = "107136069"
START = date(2026, 6, 3)


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


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"OAuth {_token()}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def fetch_daily(end: date) -> list[tuple[date, int, int]]:
    url = (
        f"https://api-metrika.yandex.net/stat/v1/data?"
        f"id={COUNTER}&metrics=ym:s:users,ym:s:visits&dimensions=ym:s:date"
        f"&date1={START}&date2={end}&sort=ym:s:date&limit=100"
    )
    rows = []
    for row in _get(url)["data"]:
        dt = date.fromisoformat(row["dimensions"][0]["name"])
        rows.append((dt, int(row["metrics"][0]), int(row["metrics"][1])))
    return rows


def fetch_cumulative_users(end: date) -> int:
    url = (
        f"https://api-metrika.yandex.net/stat/v1/data?"
        f"id={COUNTER}&metrics=ym:s:users&date1={START}&date2={end}&limit=1"
    )
    return int(_get(url)["totals"][0])


def fetch_by_minute(day: date) -> list[tuple[datetime, float, float]]:
    url = (
        f"https://api-metrika.yandex.net/stat/v1/data/bytime?"
        f"id={COUNTER}&metrics=ym:s:users,ym:s:visits"
        f"&date1={day}&date2={day}&group=minute&limit=500"
    )
    payload = _get(url)
    intervals = payload["time_intervals"]
    users, visits = payload["data"][0]["metrics"]
    out = []
    for i, iv in enumerate(intervals):
        ts = datetime.fromisoformat(iv[0])
        out.append((ts, float(users[i]), float(visits[i])))
    return out


def plot_growth(rows: list[tuple[date, int, int]], out_png: Path) -> dict:
    dates = [r[0] for r in rows]
    daily_users = np.array([r[1] for r in rows])
    daily_visits = np.array([r[2] for r in rows])
    cum_users = [fetch_cumulative_users(d) for d in dates]
    cum_visits = np.cumsum(daily_visits)
    x = np.arange(len(dates))
    coef = np.polyfit(x, daily_users, 1)
    trend = np.polyval(coef, x)

    fig, ax1 = plt.subplots(figsize=(14, 7))
    fig.patch.set_facecolor("#fafafa")
    ax1.bar(dates, daily_users, width=0.7, alpha=0.35, color="#4A90D9", label="Уникальные за день")
    ax1.plot(dates, daily_users, color="#2563EB", linewidth=1.5, marker="o", markersize=4)
    ax1.plot(dates, trend, color="#F59E0B", linewidth=2, linestyle="--",
             label=f"Тренд (≈ +{coef[0]:.1f} чел/день)")
    ax1.set_ylabel("Посетителей за день")
    ax1.grid(True, alpha=0.3)

    ax2 = ax1.twinx()
    ax2.plot(dates, cum_users, color="#059669", linewidth=2.5, marker="s", markersize=3,
             label="Кумулятивно уникальных (с 3 июня)")
    ax2.plot(dates, cum_visits, color="#7C3AED", linewidth=1.8, linestyle=":", alpha=0.85,
             label="Кумулятивно визитов")
    ax2.set_ylabel("Накоплено с 3 июня")

    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    ax1.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha="right")
    lines1, lab1 = ax1.get_legend_handles_labels()
    lines2, lab2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, lab1 + lab2, loc="upper left", fontsize=9)

    last = dates[-1]
    total_u, total_v = int(cum_users[-1]), int(cum_visits[-1])
    ax1.set_title(
        f"forecasteconomy.com — посещаемость с 3 июня 2026\n"
        f"Яндекс.Метрика · {last.strftime('%d.%m.%Y')}  ·  "
        f"{total_u:,} уникальных, {total_v:,} визитов".replace(",", " "),
        fontsize=13, fontweight="bold",
    )
    plt.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_png, dpi=150, bbox_inches="tight")
    plt.close()

    return {
        "baseline_start": START.isoformat(),
        "as_of": last.isoformat(),
        "total_unique_users": total_u,
        "total_visits": total_v,
        "trend_users_per_day": round(float(coef[0]), 2),
        "days": len(rows),
        "first_day_users": int(daily_users[0]),
        "last_day_users": int(daily_users[-1]),
        "source": "yandex_metrika",
        "counter_id": COUNTER,
    }


def plot_intraday(minute_rows: list[tuple[datetime, float, float]], day: date, out_png: Path) -> None:
    ts = [r[0] for r in minute_rows]
    users = np.array([r[1] for r in minute_rows])
    visits = np.array([r[2] for r in minute_rows])
    cum_visits = np.cumsum(visits)

    fig, ax1 = plt.subplots(figsize=(16, 6))
    fig.patch.set_facecolor("#fafafa")
    ax1.bar(ts, visits, width=1 / 1440, alpha=0.5, color="#6366F1", label="Визиты за минуту")
    ax1.set_ylabel("Визиты / мин")
    ax1.grid(True, alpha=0.25)

    ax2 = ax1.twinx()
    ax2.plot(ts, cum_visits, color="#059669", linewidth=2, label="Кумулятивно визитов за день")
    ax2.set_ylabel("Накоплено визитов")

    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax1.xaxis.set_major_locator(mdates.HourLocator(interval=1))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha="right")
    lines1, lab1 = ax1.get_legend_handles_labels()
    lines2, lab2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, lab1 + lab2, loc="upper left")

    total_u = int(users.sum())
    total_v = int(visits.sum())
    peak_i = int(np.argmax(visits))
    ax1.set_title(
        f"forecasteconomy.com — {day.strftime('%d.%m.%Y')} по минутам\n"
        f"Яндекс.Метрика  ·  {total_u} уник. (сумма минут), {total_v} визитов  ·  "
        f"пик {ts[peak_i].strftime('%H:%M')} ({int(visits[peak_i])} виз.)",
        fontsize=12, fontweight="bold",
    )
    plt.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_png, dpi=150, bbox_inches="tight")
    plt.close()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--end", default=date.today().isoformat(), help="конец периода YYYY-MM-DD")
    p.add_argument("--intraday", default=None, help="день для поминутного графика YYYY-MM-DD")
    args = p.parse_args()
    end = date.fromisoformat(args.end)
    OUT.mkdir(parents=True, exist_ok=True)

    rows = fetch_daily(end)
    with (OUT / "daily.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "users", "visits"])
        w.writerows(rows)

    meta = plot_growth(rows, OUT / "users-growth-from-jun3.png")
    meta["daily"] = [{"date": d.isoformat(), "users": u, "visits": v} for d, u, v in rows]
    (OUT / "metrics.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Baseline → {OUT}")
    print(json.dumps({k: v for k, v in meta.items() if k != "daily"}, ensure_ascii=False, indent=2))

    intraday = date.fromisoformat(args.intraday) if args.intraday else end
    minute_rows = fetch_by_minute(intraday)
    csv_path = OUT / f"intraday-{intraday.isoformat()}-by-minute.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["minute", "users", "visits"])
        for ts, u, v in minute_rows:
            w.writerow([ts.strftime("%Y-%m-%d %H:%M"), int(u), int(v)])
    png_path = OUT / f"intraday-{intraday.isoformat()}-by-minute.png"
    plot_intraday(minute_rows, intraday, png_path)
    print(f"Intraday {intraday} → {png_path}")


if __name__ == "__main__":
    main()
